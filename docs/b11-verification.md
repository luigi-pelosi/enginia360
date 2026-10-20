# B11 — Continuità e riconciliazione

Stato: implementata/verificata localmente, consegna remota da verificare nella PR della issue #17. Baseline B10 main `a2e3604046650602aa87447ccc126b4d6cffc842`, PR #31, CI main 39429274945 success; issue #16 chiusa e Project Completato riletti prima di avviare B11. D70: un solo WIP, nessun nuovo ambiente manuale o gate di routine.

## Contratto e invarianti

- Prima del POST esterno il connettore salva **Uncertain** e numero del tentativo, mantenendo la lease. Risposta persa, timeout o crash non diventano prova di mancata esecuzione. Riavvio/esito incerto consulta GET per lo stesso ID; un nuovo POST con identità stabile è ammesso solo dopo un `NotFound` valido e correlato. `Received` resta sola acquisizione, `Completed` richiede riferimento stabile; esito di business Workshop insert-only, non riscritto dal recupero.
- Errori di trasporto: backoff tecnico esponenziale (ritardo base configurato, tetto cinque minuti), massimo quattro fallimenti automatici nel ciclo; poi **NeedsReconciliation**, nessun tentativo automatico e nessuna conferma fittizia. Non è una policy fiscale/business. Il rifiuto di business resta finale, non ritentabile; la sua eventuale risoluzione commerciale non è inventata.
- Recupero esplicito `POST /api/v1/workshop/orders/{orderId}/administrative-requests/{requestId}/reconciliation`, corpo solo `{id}` non vuoto. Workshop verifica tenant/membership, risorsa commessa/richiesta, capability e azione esatta `workshop.administrative-requests.reconcile` con scope societario/sede. Integrations registra il comando e riprogramma verifica-stato nella propria transazione. Retry esatto idempotente; ID estranei/conflitti non espongono dati. Il comando non muta snapshot, lavoro fisico, chiusura tecnica o esiti finali.
- Aggiornamenti del worker vincolati alla lease acquisita: un risultato tardivo non sovrascrive lease/stato di un nuovo proprietario. Scansione degli envelope paginata in lotti limitati e ciclica: richieste vecchie sospese/escalate non affamano quelle successive. La posizione di scansione è tecnica e ricostruibile; la richiesta, lease, tentativi, errore e recupero sono persistiti.
- Errore fra commit connettore e commit dell'esito Workshop: la consegna finale rimane durevole; il worker completa l'esito originale al riavvio senza reinviare. Nessuna transazione globale o promessa exactly-once. La chiusura amministrativa resta bloccata finché l'esito di business non è realmente registrato; chiusura tecnica e fatti locali preservati D37.
- UI italiana mostra incertezza/escalation, richiede un'azione esplicita di recupero, conserva l'ID del comando se la risposta si perde e abilita chiusura amministrativa soltanto dopo conferma. La stessa UI B10 è estesa, nessun nuovo ambiente o flag persistente.

## RED → GREEN eseguiti

Tutti i log citati sono in scratch, non generati o committati nel repository:

| Comando/prova prima del fix | RED osservato | GREEN |
| --- | --- | --- |
| `timeout 360 sh scripts/run-b11-tests.sh` (primo tracer) | `b11-uncertain-red.log`: effetto completato, risposta persa; due POST e zero GET | `b11-uncertain-green.log`: un POST e almeno un GET, stesso riferimento |
| `B11_BEHAVIOR=bounded timeout 360 sh scripts/run-b11-tests.sh` | `b11-bounded-red.log`: polling Uncertain senza limite, escalation assente | `b11-bounded-green.log`: quattro fallimenti, escalation e arresto |
| `B11_BEHAVIOR=reconcile timeout 360 sh scripts/run-b11-tests.sh` | `b11-reconcile-red.log`: endpoint 404 con contesto autorizzato valido | `b11-reconcile-green.log`: 202, retry 200, recupero effettivo |
| `B11_BEHAVIOR=restart timeout 360 sh scripts/run-b11-tests.sh` | `b11-restart-red.log`: SIGKILL reale dopo commit remoto, riavvio produce secondo POST | `b11-restart-green.log`: intento Uncertain già persistito, GET dopo lease, un POST |
| `B11_BEHAVIOR=lease timeout 360 sh scripts/run-b11-tests.sh` | `b11-lease-red.log`: worker tardivo sovrascrive lease/stato sostitutivo controllato | `b11-full-final2.log`: fencing preserva il nuovo proprietario |
| `B11_BEHAVIOR=fairness timeout 360 sh scripts/run-b11-tests.sh` | `b11-fairness-red.log`: venti vecchie richieste escalate affamano la ventunesima, che non viene inviata | `b11-full-final2.log`: nuova richiesta confermata senza reinviare le vecchie |
| UI unit `npm test -- --run src/B11.test.tsx` | `b11-ui-red.log`: stati nuovi rifiutati dal parser, recupero assente | `b11-ui-green.log`: stato esplicito, retry stesso ID, nessuna falsa conferma |
| `python3 scripts/test-b11-ci.py` | runner B11 assente nella selezione CI | PASS dopo integrazione esplicita |

## Verifiche finali effettive

- `timeout 360 sh scripts/run-b11-tests.sh`: **PASS**, `b11-full-final2.log`. Lost response, quattro fallimenti/backoff/escalation, riconciliazione e otto retry concorrenti (un comando), tenant/input/riferimenti estranei, permesso esatto assente/sede estranea/warehouse-only separati, outcome confermato/rifiutato non sovrascrivibile; forced RLS e grant insert-only; lease fencing, venti vecchi elementi senza starvation; due kill/restart reali (durante effetto remoto e fra commit dei moduli), fault PostgreSQL mediante REVOKE/GRANT INSERT solo nel progetto effimero; **DOM con login/fetch reali**; audit; migrazione ripetuta e rollback protetto/ripetuto/reapply. Cleanup EXIT verifica assenza container/reti del progetto.
- `timeout 360 sh scripts/run-b10-tests.sh`: **PASS**, `b11-regression-b10.log`; comprende DOM B10, richieste/esiti/chiusure, gate carcassa/concorrenza, capability, due pool, RLS, hardening e rollback/reapply. Nessuna modifica ai fatti B05–B09.
- SDK pinned: restore locked + API test **62 PASS**; audit API e test nessun package vulnerabile (`b11-dotnet-final.log`). Nessuna dipendenza aggiunta.
- Node pinned: **22 test unit PASS, 9 runtime skip fuori stack**, typecheck/build privata PASS, npm audit **zero vulnerabilità** (`b11-web-final.log`). B11 runtime è invece eseguito e PASS nello stack, non confuso con gli skip ordinari.
- `python3 scripts/test-b11-ci.py`, `python3 scripts/test-b10-ci.py`, `python3 scripts/test-ci-runtime.py`, `git diff --check`: **PASS**. CI remota non dedotta dai test locali.
- Bootstrap web/API originali soli container rimasti, ID/avvii non cambiati. Volumi conservati 25, hash dei nomi/newline invariato `18be04807d27c1f30683770dd421da191f0346e87aa8ebdb5fac2fe02d08390e`. Nessun prune, lettura segreti, cambio backup o nuovo servizio pubblico.

## Migrazione, rollback e limiti

`database/b11/080_continuity.sql`: stati nuovi, contatore, audit recuperi e overload paginato della funzione di envelope; proprietario NOLOGIN con grant limitati, RLS e privilegio applicativo invariati. `900_synthetic_fixtures.sql` concede soltanto le azioni sintetiche per i test; non è provisioning reale. `950_rls_test.sql` esercita isolamento e privilegi. `990_rollback.sql` **rifiuta** in presenza di Uncertain/NeedsReconciliation per non permettere a un vecchio worker di reinviare alla cieca; fermare worker/scritture e risolvere oppure ripristinare un backup compatibile. Dopo la risoluzione, rimuove soltanto schema aggiunto B11 e ripristina il vincolo B10, senza alterare esiti di business. Rollback dello stack B10 passa prima da B11. In ambiente reale audit e richieste richiedono backup/retention approvati: nessun downgrade distruttivo eseguito su dati conservati.

Simulatore sintetico in memoria, non ERP reale; fault hold/lost-response e controlli non sono endpoint del prodotto. Queste prove non certificano trasporto exactly-once, disponibilità single-host, fiscalità, incasso o riconsegna. Eccezioni business, risoluzione commerciale di un rifiuto, destinatari ERP reali, multi-pagante e conformità restano fuori scope. B12/B13 devono ancora realizzare l'alternativa interna con F03/F04; B14 deve esercitare ripristino completo e limiti operativi. Nessun sottoinsieme è presentato come slice completa.
