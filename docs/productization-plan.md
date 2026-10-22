# Productizzazione finita — P00 / UI01 / R00–R06

## Stato e autorizzazione

21 ottobre 2026. D74 (sviluppo), D75 (Giobby/esclusione SAP), D76 (direzione e scope) sono le decisioni attive. Sviluppo autonomo autorizzato fino a R06 per operatività officina pilota con amministrazione ERP esterna; capability contabile interna preservata, non deprecata. Il proprietario autorizza ora la consegna P00 con commit, push, PR, CI exact-head, merge e CI merged-main. P00 include solo documenti e test di consistenza: nessun codice applicativo. UI01 può iniziare dopo P00 verificata; in questo incarico solo checkpoint e contratto/progetto finito, nessuna implementazione UI01. Baseline C00 `2ba4d273686854870b1a7806103bf1c096fcd0be`, CI 39592416386 success.

Nessun go-live, utente/dato reale, acquisto, nuovo ambiente persistente o deployment pubblico è autorizzato. Bootstrap web/API, Tailscale 443 → localhost:9119 e 25 volumi/backups/configurazioni conservati non si toccano. #37 resta differita. Il charter resta invariato; D1–D73 e il report C00 conservano il significato storico.

## Autorità e altri gate

**AUTHORITY — gate di setup, non blocco generale (D76):** direzione unilaterale configurabile per cliente/dominio nelle impostazioni societarie: Enginia360 → Giobby oppure Giobby → Enginia360. Tenant = cliente/gruppo, società = unità organizzativa interna; integrazione/capability/business data societari non cambiano l'unica autorità del nucleo anagrafico condiviso tenant-wide D26/D65. Estensioni/prezzi/stock societari separati. Il profilo tecnico concreto sarà scelto al setup prima della scrittura/sincronizzazione dipendente, con mapping, conflitti/cancellazioni e dataset espliciti. Non servono nuova approvazione D26 o scelta pilota anticipata per UI01/R00, ricerca documentale o comportamento configurabile neutrale. Nessun writer bidirezionale concorrente, cambio automatico/retroattivo di autorità o profilo concreto pilota è approvato.

**POLICY — al comando interessato:** concedente/revoca R01; create/disattivazione/deduplicazione R02; appuntamenti, autorizzazioni, tempi e riconsegna R03; ricevimento/reso/rilascio e stock R04. Riutilizzare decisioni già confermate, non chiedere nuovamente D14/D15/D63/D65/D67/D69–D73. Non inventare fallback.

**CONTRACT — R05:** Giobby primo ERP; [discovery ufficiale pubblicata](giobby-discovery.md) con fonti e hash acquisiti il 21 ottobre 2026. Swagger pubblico 2.0 osservato, ma risposte business senza schema, idempotenza e lookup dopo timeout ignoti. Nessun contratto live inventato o verificato; api-client/api-server non selezionato, nessun client registrato. SAP custom BTP del consulente **escluso da questo sprint**. Nessuna chiamata al gestionale reale. Ricerca R05.a indipendente consentita prima di R04, senza completare adapter/mapping.

**READINESS — R06:** validazioni fiscali/contabili oltre i casi D42/D44/D45 e OPE01–OPE05 restano evidenze da acquisire sul target effettivo. Dati sintetici e restore effimero non certificano conformità o RPO/RTO reali. Identità pilota/referenti e responsabili operativi da confermare prima dell'uso operativo, non da inventare.

## Sequenza e metodo

P00 → UI01 / R00 (indipendenti dopo la preparazione) → R01 → R02 → R03 → R04 → R05 → R06; R03 richiede anche UI01. Le dipendenze sono di integrazione: ricerche indipendenti possono procedere in parallelo, con ownership file/contratti esplicita e nessun cambio concorrente dello stesso contratto. WIP implementativo iniziale uno; nessuna promessa di date o stima universale. Autorizzato non significa Pronto o Completato: dipendenze e gate puntuali restano obbligatori.

Ogni scheda sotto è una capability finita, non un incarico di CRUD massivo. I suffissi .a/.b/.c identificano subincrementi ordinati, non nuovi significati Rxx. Prima del codice del singolo subincremento fissare contratto e accettazione; RED → GREEN → regressioni → prove UI/API/SQL reali → report limiti. Per ogni consegna autorizzata verificare CI exact-head e merged-main prima di chiudere; riportare identificativi reali nella PR/issue, senza far dipendere il guard documentale da futuri SHA o stati live.

Definition of Done comune: isolamento tenant e azione/scope precisi, ownership moduli, immutabilità dei fatti, q6/D67, idempotenza/concorrenza, migrazione/rollback, audit minimizzato; API integration, UI test/typecheck/build, dipendenze/audit, Compose health e HTTP smoke applicabili realmente eseguiti. Preservare test Billing/Accounting interni anche se il primo pilota usa Giobby. Nessuna conclusione fiscale generale dai test tecnici.

**Aggiornamento CI del proprietario, 22 ottobre 2026:** la suite di routine è circoscritta all'ultima implementazione completata, ai file realmente cambiati e alle dipendenze dirette interessate; non all'intera architettura. Sicurezza, isolamento/RLS e acceptance reale interessata restano obbligatori. Full B02–B14/all-architecture disponibile solo come eccezione esplicita, non gate automatico o manuale per ogni consegna. PR automatiche rappresentative, runtime mirato exact-head su dispatch, nessuna nuova run automatica su push main; skip runtime non significa pass. Dopo merge verificare readback/tree del candidato provato e fare un nuovo check main solo se necessario e mirato. Per R00.b: [contratto, selettore ed evidenze browser/sessione](r00b-browser-session.md). Questa direttiva aggiorna il gate di routine precedente senza riscrivere gli esiti storici.

## Backlog tracciabile

La matrice strutturata `productization-backlog.json` è verificata dal test C00 evoluto; le issue non sono completate dalla pianificazione. Criteri e gate sono riportati anche nelle schede remote, senza duplicare UI01 #5.

### P00 — Perimetro pilota

- Dipende da: baseline C00 verificata.
- Gate: AUTHORITY: D76 conferma direzione unilaterale configurabile societaria e master unico tenant; profilo concreto al setup prima degli effetti dipendenti, non blocco generale UI/runtime. Identità pilota/referenti prima della readiness operativa.
- P00.a: delimitare percorso officina, ruoli operativi e consegna amministrativa esterna senza estendere il charter a tutto il DMS.
- P00.b: rendere espliciti matrice autorità, gate e criteri di readiness; mantenere aperte le risposte non ricevute.
- Accettazione/evidenze: Piano e registro coerenti; backlog finito, dipendenze acicliche, esclusioni e prove assegnate. Consegna documentale tramite PR e CI exact-head/merged-main verificate prima della chiusura; nessuna readiness pilota implicita.

### UI01 — Editor commessa

- Dipende da: P00.
- Gate: Nessuna nuova regola di workflow o autorità dati dedotta dalla UI; integrazione runtime solo dopo R00.
- UI01.a: editor isolato Ant Design con documento/cliente/veicolo, lavorazioni ripetute, righe modificabili e riepilogo persistente, dati sintetici.
- UI01.b: collegare solo comandi/letture già autorizzati dopo R00, senza creare CRUD o endpoint per riempire mock.
- Accettazione/evidenze: Full-width/full-height, densità leggibile come riferimento legacy, tastiera/focus, ricerca e modifica riga, errori, desktop/portatile e documento lungo esercitati; stati prelievo/installazione/carcassa/esito esterno distinti; nessun dato copiato da screenshot; licenze/versioni verificate; test UI e contratto runtime reale per la parte collegata.

### R00 — Runtime

- Dipende da: P00.
- Gate: Nessun nuovo ambiente persistente; identity baseline non equivale a provider di produzione approvato.
- R00.a: percorso avvio/configurazione e migrazioni ripetibili nello stack effimero protetto.
- R00.b: verificare isolamento, ciclo sessione, errori e recupero senza introdurre provisioning commerciale.
- Accettazione/evidenze: Avvio/stop ripetibili; API/UI/DB/identity esercitati end-to-end, anonimo e scope insufficienti negati, pooling/RLS, rollback, health e HTTP smoke; hardening/audit lock e segreti fuori repository; nessuna modifica bootstrap/Tailscale/storage conservato.

### R01 — Amministrazione organizzativa

- Dipende da: R00.
- Gate: Autorità concessione/revoca, ruoli e lifecycle da confermare prima di ciascun comando non già deciso; niente amministratore onnipotente inventato.
- R01.a: selezione e lettura autorizzate società/sedi/magazzini/capability con scope visibile.
- R01.b: singolo percorso amministrativo di configurazione/assegnazione autorizzato e auditato, dopo risoluzione della policy esatta.
- Accettazione/evidenze: Gerarchia D15/D16, customizing societario D14, grants espliciti D23 e storico con capability disabilitata; rifiuti cross-tenant/azione/scope e revoca esercitati; nessun CRUD organizzativo massivo.

### R02 — Anagrafiche

- Dipende da: R01.
- Gate: AUTHORITY: D76 configurabile per società/dominio, master condiviso con unica autorità tenant-wide; selezione concreta al setup prima di scrittura/sync dipendente. Creazione/disattivazione/duplicati da decidere solo al percorso necessario.
- R02.a: ricerca/selezione di controparte, veicolo e articolo/prestazione comuni nel tenant senza ampliare grant di gestione.
- R02.b: un percorso autorizzato di acquisizione o modifica, locale oppure proiezione ERP secondo autorità confermata, con mapping e storico.
- Accettazione/evidenze: D21/D26/D61/D63/D65 rispettati; pagante non sovrascritto da veicolo; destinazioni riservate e dati societari protetti; input e conflitti validati; test negativi più percorso UI/API/SQL reale e audit minimizzato.

### R03 — Ciclo officina

- Dipende da: UI01, R02.
- Gate: Dettagli appuntamento/accettazione/autorizzazione cliente/tempi/riconsegna non già decisi da confermare prima della relativa transizione; nessuna chiusura universale inventata.
- R03.a: collegare apertura e gestione commessa/lavorazioni/valori al percorso operatore, preservando D67.
- R03.b: un passaggio operativo mancante alla volta (pianificazione/accettazione/autorizzazione/consuntivo), con contratto e policy confermati.
- R03.c: chiusura tecnica ed attesa amministrativa visibili, senza incasso o riconsegna impliciti.
- Accettazione/evidenze: Percorso finito attraversabile, tempi pianificati/effettivi distinti ove introdotti, ruoli distinti, customizing versionato, retry/concorrenza; regressioni B04–B13 inclusa contabilità interna e D37/D40; ogni subincremento ha RED/GREEN e DoD propria.

### R04 — Magazzino e approvvigionamento

- Dipende da: R03.
- Gate: AUTHORITY: stock/prezzi societari con direzione unilaterale D76, profilo concreto al setup prima degli effetti dipendenti; causali, unità e parzialità ricevimento/reso/rilascio da confermare prima del nuovo comando; nessuna policy stock negativo dedotta.
- R04.a: rendere operabili prenotazione, picking, installazione/consumo e carcassa esistenti preservando D69–D73.
- R04.b: fabbisogno → richiesta/ordine fornitore tecnico → ricevimento collegato, un effetto alla volta, secondo autorità e policy approvate.
- R04.c: reso del nuovo o rilascio solo dopo policy esplicita, distinti dalla carcassa.
- Accettazione/evidenze: Nessun doppio movimento o impegno e concorrenza reale; provenienza/residui verificabili, ricevimento non prova fattura passiva/pagamento; niente ordine reale al fornitore o acquisto; regression stock/restore e UI/API/SQL.

### R05 — Integrazione Giobby

- Dipende da: R04.
- Gate: AUTHORITY: configurabilità unilaterale societaria D76, master unico tenant-wide e profilo concreto al setup prima della sincronizzazione dipendente. Contratto ufficiale da verificare: autenticazione, permessi account, endpoint/versione, idempotenza/esiti/limiti. Nessuna credenziale o connessione reale in questo incarico.
- R05.a: dossier contratto Giobby e matrice campo/transizione/autorità con gap documentati.
- R05.b: adattatore anti-corruption del percorso amministrativo minimo contro fixture contrattuali sintetiche, non risposta inventata come prova live.
- R05.c: esercitare coda, timeout incerto, ricerca esito, retry e riconciliazione; prova esterna solo con separato scope sicuro.
- Accettazione/evidenze: SDK/API proprietari fuori dal dominio; business acknowledgement distinto da ricezione, ID stabili e mapping societario, conflitti/errori visibili, nessun duplicato economico; capacità non documentate restano gap, non emulazioni di compatibilità; SAP custom BTP esplicitamente escluso.

### R06 — Migrazione e readiness

- Dipende da: R05.
- Gate: OPE01–OPE05, responsabili, validazioni specialistiche e target effettivo; go-live/dati reali/acquisti/ambiente persistente richiedono incarico separato.
- R06.a: inventario e mapping di migrazione senza estrarre dati reali, prova import/export con dataset sintetico e riconciliazione.
- R06.b: rehearsal effimero completo, backup/restore e rollback misurati, runbook e checklist con evidenze e gap.
- Accettazione/evidenze: Conteggi/provenienze/importi/stock riconciliati secondo autorità approvata, retry migrazione senza duplicati, entrambi i profili esterno/interno preservati; sicurezza/API/UI/build/audit/Compose/smoke e CI exact-head/main solo se eseguite; relazione readiness non equivale a rilascio operativo.

## Tracking GitHub verificato

Project privato esistente n. 3 riutilizzato (nessun nuovo Project); P00 #39 è il solo WIP di consegna iniziale. UI01 #5 riutilizzata, R00–R06 dipendono dai predecessori sotto. La tabella è una mappa stabile, non una copia immutabile dello stato live: transizioni e readback sono evidenze nei thread GitHub. UI01 passa In corso solo dopo P00 merged-main verde; #37 resta differita.

| ID | Issue | Dipendenze |
| --- | --- | --- |
| P00 | #39 | C00 #36 |
| UI01 | #5 | P00 #39 |
| R00 | #40 | P00 #39 |
| R01 | #41 | R00 #40 |
| R02 | #42 | R01 #41 |
| R03 | #43 | UI01 #5, R02 #42 |
| R04 | #44 | R03 #43 |
| R05 | #45 | R04 #44 |
| R06 | #46 | R05 #45 |

## Verifiche e consegna

- Preparazione storica: guard C00 e 10 mutation test già verdi, RED su autorizzazione D76 e invariante autorità tenant osservati.
- Consegna corrente: tre mutation test aggiunti prima della guardia: restrizione commit attiva, evidenza Giobby mancante, suite mutation rimossa da CI. RED osservato: 3 fallimenti `0 == 0`; il vecchio guard accettava tutte e tre le corruzioni.
- Eseguire `python3 scripts/test-c00-consistency.py`, `python3 scripts/test-productization-consistency.py` e `git diff --check`; CI conserva tutte le suite storiche e aggiunge i mutation test. Gli esiti/ID finali appartengono alla PR/issue dopo l'esecuzione, non sono anticipati da questo piano.
- Review diretta del diff: significati Rxx originali, D1–D73 e B01–B14/C00 storici preservati; D74–D76 separano autorizzazione corrente, setup concreto e go-live. Discovery Giobby documentale, non compatibilità live.
- Per la parte documentale: guard e mutation test locali; API/UI/audit/Compose/smoke restano nelle CI remote obbligatorie. Nessun runtime persistente o deploy modificato.
- CI PR iniziale 39610973956: fallimento reale B10 per deadlock tra TRUNCATE della fixture e discovery outbox (ordine lock invertito outcomes/outbox). La run push 39610965303 dello stesso head è passata: race preesistente, non evidenza per ignorare la run fallita. Riproduzione deterministica su PostgreSQL effimero con il TRUNCATE effettivo: RED `deadlock detected`, GREEN dopo ordine requests → outbox → outcomes. Nessun comportamento applicativo cambiato, retry/skip o check indebolito. Due tentativi di quiescenza API sono stati scartati perché troppo lenti; non fanno parte della consegna. I tentativi locali B10 limitati a 390 secondi sono scaduti e non sono prove di suite completa; gli esiti finali appartengono alle run successive verificate.

## Ruoli operativi e percorso P00

Ruoli funzionali, non assegnazioni a persone né nuovi grant: accettazione seleziona documento/pagante/veicolo; operatore officina gestisce lavorazioni/consuntivi; magazzino gestisce prenotazione/prelievo/installazione/carcassa secondo scope e policy esistenti; amministrazione riconcilia la richiesta ERP e il suo esito business. R01 confermerà concedente/revoca per ciascun comando nuovo. Identità pilota e referenti reali non comunicati, da acquisire prima dell'uso operativo.

Percorso finito: contesto autorizzato → selezione anagrafiche → commessa e lavorazioni → valori commerciali → prenotazione/prelievo/installazione/carcassa → chiusura tecnica → richiesta amministrativa esterna persistita → esito business/riconciliazione. D37/D40 separano chiusura tecnica e amministrativa, senza incasso/riconsegna impliciti. Appuntamenti/autorizzazioni/tempi ulteriori passano i gate puntuali R03. R06 raccoglie readiness senza autorizzare go-live. Il profilo interno Billing/Accounting e i suoi test restano preservati.

## Rollback

Ripristinare esclusivamente documenti/guard di questa consegna con una PR tracciata; tracking remoto aggiornato esplicitamente preservando cronologia. Nessuna migrazione o rollback runtime: comportamento, schema, bootstrap/Tailscale e volumi conservati non modificati.
