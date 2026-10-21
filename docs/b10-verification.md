# B10 — Destinazione amministrativa esterna simulata

**Consegna verificata:** PR #31, CI exact-head 39424479525 success, merge `a2e3604046650602aa87447ccc126b4d6cffc842`; issue #16 chiusa/Completato. Il risultato è incluso nella baseline finale main `fa972837684e67b9e5094025acdd54848a46c62a`, CI main 39518931794 success. Solo dati sintetici e stack effimero; nessuna fiscalità reale, produzione o nuova esposizione.

## Contratto e confini

- Workshop possiede la chiusura tecnica durevole, richiesta immutabile, outbox, esito di business e chiusura amministrativa. B09 valutava soltanto il gate: non chiudeva la commessa. B10 introduce la transizione esplicita autorizzata D37/D39/D73. Il lock della commessa è condiviso con aggiunta righe e installazioni: dopo la chiusura nuove righe/installazioni sono rifiutate; nessuna riapertura o compensazione inventata. Il rientro rimane un fatto Inventory insert-only, fuori giacenza; nessuna transazione globale.
- La richiesta segue la chiusura tecnica esplicita, verifica la revisione commerciale e fotografa riepilogo q6, pagante/riferimenti delle righe, società/sede, destinazione societaria e versione. Destinazione assente rifiutata, nessun default. La versione rilevante non è un congelamento universale del customizing.
- Richiesta e outbox nella stessa transazione Workshop. ID client non vuoto, retry esatto, conflitto su payload/riferimento diverso, una richiesta per commessa; collisioni cross-tenant non rivelano dati. Storico leggibile con autorizzazione anche a capability disabilitata; scritture e nuovi usi del worker sospesi, ripresa senza perdere la richiesta.
- Integrations dipende solo da Workshop.Contracts: possiede consegna/lease e anti-corruption layer. Scoperta limitata a envelope tenant/request mediante funzione SECURITY DEFINER con proprietario NOLOGIN e grant di sole colonne outbox; tutte le letture/scritture successive impostano tenant context transazionale e RLS. Il ruolo applicativo non è BYPASSRLS.
- Simulatore privato v1: POST con Idempotency-Key e payload tecnico minimizzato; GET stato per ID. `Received` = sola acquisizione. Solo `Completed` con ID richiesta coerente e riferimento esterno stabile diventa `Confirmed`; rifiuto resta visibile/finale. La chiusura amministrativa è un comando separato e bloccato senza conferma. Nessuna fattura interna duplicata, emissione fiscale, incasso o registrazione reale.
- UI italiana mostra separatamente gate, chiusure, richiesta, consegna, conferma/rifiuto e azione successiva. Test DOM con fetch reale verso nginx/API/Keycloak/PostgreSQL/simulatore.

## RED → GREEN effettivi

- `timeout 580 sh scripts/run-b10-tests.sh`: RED iniziale HTTP 404 sul POST richiesta dopo login/workflow reale valido (`b10-request-red.log`). Test API di endpoint anonimi RED 404→401 prima del mapping; UI RED modulo assente. Tracer GREEN nei log `b10-green-request2.log`.
- Mutazione controllata della verifica chiusura nell'installazione: `B10_BEHAVIOR=race timeout 580 sh scripts/run-b10-tests.sh` fallisce con chiusura 201 e installazione successiva 201; codice ripristinato. Interleaving deterministici close-first e install-first GREEN nella suite finale: non esiste chiusura che aggiri un nuovo residuo carcassa.
- Test aggiuntivo prima della correzione: `B10_BEHAVIOR=paused timeout 580 sh scripts/run-b10-tests.sh` RED (`b10-paused-red.log`): worker confermava dopo disattivazione capability. Corretto il confine Workshop del worker; sospensione/ripresa GREEN nella suite finale.

## Comandi ed esiti locali

- `timeout 595 sh scripts/run-b10-tests.sh`: **PASS**, log scratch `b10-full-final.log`. Identità reale, happy path ricevuta/confermata/rifiutata; idempotenza e richieste concorrenti, ID vuoti, revisioni e riferimenti ostili, tenant alternati, pool 8 e 1; grant common-edit, sito estraneo, warehouse-only e azione errata provati separatamente; create/read indipendenti; capability API/worker e storico; versione destinazione; gate/late installation; DOM reale; RLS e privilegi; migrazione ripetuta, rollback ripetuto, schema B09 ancora leggibile e reapply; health/hardening cinque container, nessuna porta/volume; audit minimizzato. Cleanup EXIT verificato.
- `timeout 595 sh scripts/run-b05-tests.sh`: **PASS**, `b10-regression-b05.log` (righe/valorizzazione modificate).
- `timeout 595 sh scripts/run-b08-tests.sh`: **PASS**, `b10-regression-b08.log` (lock installazione modificato).
- SDK pin repository: restore locked + test API **62 PASS**, zero fallimenti; audit NuGet API/test nessun package vulnerabile (`b10-dotnet-final.log`).
- Node pin repository: `npm test`, build privata B06–B10 con `tsc --noEmit`, `npm audit --audit-level=high`: **PASS**, zero vulnerabilità (`b10-web-final.log`). DOM reale B10 esercitato separatamente dalla suite unit.
- `python3 scripts/test-b10-ci.py`, `git diff --check`: **PASS**. CI seleziona esplicitamente B10 e build privata, preserva incrementi precedenti.
- Bootstrap web/API ID e avvii originali invariati, Tailscale 443→9119 invariato. Volumi conservati: 25, SHA256 nomi/newline `18be04807d27c1f30683770dd421da191f0346e87aa8ebdb5fac2fe02d08390e`. Nessun prune, lettura segreti o modifica backup.

## Migrazione e rollback

`database/b10/070_administration.sql`, fixture esclusivamente sintetiche `900_synthetic_fixtures.sql`, negativi privilegi/RLS `950_rls_test.sql`, rollback `990_rollback.sql`. Per lo stack effimero il rollback elimina soltanto le tabelle B10/Integrations e il proprietario della funzione; preserva schema/fatti precedenti. In uso persistente futuro: fermare worker/scritture, backup verificato, ripristinare applicazione e schema compatibili; eliminare tabelle B10 distrugge richieste/conferme e non è una procedura ammessa senza backup/riconciliazione. Nessun deployment persistente eseguito.

## Limiti e prossimo incremento

B11 deve completare continuità: indisponibilità/backoff limitato, timeout incerto prima di reinvio, riconciliazione autorizzata e restart ai confini intermodulo. Nessuna promessa exactly-once. Simulatore in memoria, non ERP reale e non autorità fiscale; ripristino completo B14 ancora da provare. Riapertura commesse, allocazioni multi-pagante, eccezioni business, costi e policy fiscali generali non introdotti. La sessione delegata Claude è terminata con 429 `usage_limit_reached`; stderr vuoto. Il lavoro è stato recuperato e verificato con strumenti diretti, senza assumere la continuazione attiva. Prove CI remota/merge devono essere lette dal relativo run, non dedotte dai test locali.
