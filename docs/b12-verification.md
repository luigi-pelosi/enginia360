# B12 — Fattura tecnica interna

Stato: implementata e verificata localmente; consegna remota da verificare nella PR della issue #18. Baseline B11 main `79db88ce2eb3df6f16b73c8daef82bb8d6731945`, PR #32 e CI main 39460723295 success. D70–D73: un solo WIP, accettazione effimera, nessun ambiente manuale persistente o gate di review di routine.

## Contratto e invarianti

- La fattura tecnica nasce soltanto da una commessa tecnicamente chiusa. Workshop resta proprietario della sorgente e alloca atomicamente una sola destinazione amministrativa: claim interno oppure richiesta esterna, mai entrambe. Il claim usa lock per commessa e vincolo univoco; due creazioni concorrenti producono un solo documento.
- Il draft conserva lo snapshot q6 esatto della chiusura Workshop: righe, configurazioni, pagante, revisione, imponibile, imposta e totale a sei decimali. Non rilegge catalogo o ordine mutabile. Tipo documento, versione, destinazione e capability sono espliciti; valuta limitata a EUR nel caso autorizzato.
- La conferma è insert-only e idempotente per ID comando. Congela emittente e destinatario dai dati configurati/controparte; non genera numerazione universale, emissione fiscale, SdI, ERP, incasso o scrittura contabile. Il riferimento è tecnico e fornito dal comando.
- Superficie autenticata `/api/v1/billing/workshop-invoices`: creazione richiede `billing.invoices.create`, conferma `billing.invoices.confirm`, lettura `billing.invoices.read`; capability `internal-billing` richiesta per le scritture. Membership, tenant, società e sede sono verificati server-side; RLS forzata su claim/configurazione/fatture/conferme/link futuri.
- Il contratto espone `journalEntryId` nullable come riferimento di storia futuro, senza creare servizio o semantica contabile B13. Billing possiede schema e documenti; Workshop espone la sorgente; Counterparties espone solo lo snapshot del pagante.
- UI italiana esplicita “documento interno” e “non emissione fiscale”, conserva gli ID dei comandi dopo risposta persa, valida la risposta, mostra righe/totale e abilita conferma soltanto dalla bozza.

## RED → GREEN eseguiti

I log sono in scratch e non nel repository.

| Prova | RED osservato | GREEN |
| --- | --- | --- |
| `BillingBoundaryTests` | route inesistenti, test exit 1 (`b12-auth-red.log`) | tre route rifiutano anonimi prima del DB (`b12-auth-green.log`) |
| `timeout 350 sh scripts/run-b12-tests.sh` | endpoint draft placeholder 501 (`b12-draft-red*.log`) | creazione/readback/conferma/idempotenza/isolamento/concorrenza PASS (`b12-full-green-attempt1.log`) |
| `npm test -- --run src/B12.test.tsx` | risposta malformata non mostrava errore (`b12-ui-unit-attempt1.log`) | due test UI PASS e build PASS (`b12-ui-unit-green.log`) |
| `python3 scripts/test-b12-ci.py` | selezione B12 assente dalla CI (`b12-ci-selection-red.log`) | runner reale selezionato (`b12-ci-selection-green.log`) |
| B10 regression | reset non includeva il nuovo FK, poi rollback B10 precedeva B12 (`b12-regression-b10*.log`) | B12 rollback prima di B11/B10, reset completo; suite B10 PASS |
| `scripts/test-b12-security.py` ritentativo concorrente con lock reale su `billing.invoices` | quattro retry dello stesso ID: `[201,500,500,500]` per snapshot di destinazione perduto, poi `[201,409,409,409]` (`b12-controlled-retry-red2.log`, `b12-controlled-retry-red4.log`) | `[200,200,200,201]` con un solo documento identico; claim riletto e inserimento concorrente risolto in replay (`b12-full-security-rls-green.log`) |
| Input non fidato della creazione | `reference: null` provocava 500 reale (`b12-full-security-rls-input.log`) | 400 per ID vuoto, riferimento nullo, valuta non EUR e campo estraneo |
| `database/b12/950_rls_test.sql` con ruolo applicativo reale | file assente: RLS/privilegi B12 non esercitati dal ruolo reale | PASS: nessun dato senza contesto, nessuna lettura/scrittura cross-tenant, UPDATE/DELETE negati, FORCE RLS su sei tabelle, reset di contesto |
| `scripts/test-b12-audit.py` | la suite verificava solo la presenza della stringa `Billing audit` | PASS su 200/201/403/404/409/500 reali con soli ID tecnici |
| UI `src/B12.test.tsx` contratti aggiuntivi | totale non numerico, riga malformata e confermata senza emittente accettati (`b12-ui-contract-red.log`, 3 test falliti) | rifiutati e nessun falso successo (`b12-ui-contract-green.log`) |
| `python3 scripts/test-b12-ci.py` host UI | `VITE_B12_TEST_UI` assente: la UI non era raggiungibile dall'host dell'ordine | flag Dockerfile/compose/host e selezione CI PASS |

## Verifiche finali effettive

- `timeout 350 sh scripts/run-b12-tests.sh`: **PASS** (`b12-full-audit-green.log`). Nove marker reali: tracer HTTP, ritentativo concorrente controllato, scope esatti separati, storico immutabile dopo modifica anagrafica reale, guasto intermodulo con recupero, RLS con ruolo applicativo, audit strutturato, DOM reale e rollback guardato con cleanup verificato dal trap.
- `timeout 560 sh scripts/run-b10-tests.sh`: **PASS** (`b12-regression-b10-final2.log`); include DOM, RLS, hardening, audit e rollback/reapply B10–B12. Una precedente esecuzione con budget 350 s è stata interrotta dal timeout (`b12-regression-b10-final.log`, exit 124): la sua assenza di audit è artefatto del cleanup anticipato, non un fallimento della suite.
- `timeout 350 sh scripts/run-b11-tests.sh`: **PASS** (`b12-regression-b11-final.log`), inclusi fault, kill/restart, lease, riconciliazione, DOM e audit.
- SDK pinned: restore locked, API test **65 PASS**, audit NuGet API/test nessun package vulnerabile (`b12-dotnet-final2.log`).
- Node pinned: **27 unit PASS, 10 runtime skip** fuori stack; tre build private (default, B10, B12) e `npm audit` **zero vulnerabilità** (`b12-ui-full-audit2.log`). Il runtime B12 è eseguito e PASS nello stack, non confuso con gli skip.
- Compose renderizzato con configurazione sintetica: container nonroot/read-only, capability drop, no-new-privileges e nessuna porta pubblicata. `git diff --check` e selezione CI PASS.
- Risorse host protette: 25 volumi invariati; hash nativo nomi/newline `18be04807d27c1f30683770dd421da191f0346e87aa8ebdb5fac2fe02d08390e`. Nessun prune, deploy pubblico, lettura segreti o modifica backup/configurazioni manuali.

## Migrazione, rollback e limiti

`database/b12/090_billing.sql` estende la destinazione a `Internal`, aggiunge claim Workshop e schema Billing con configurazioni versionate, fatture, conferme e link journal. `900_synthetic_fixtures.sql` contiene soltanto capability, scope e configurazione sintetici. `990_rollback.sql` rifiuta se esistono link, fatture, claim o destinazioni interne: prima del downgrade fermare le scritture, esportare/ripristinare con piano approvato e risolvere i riferimenti; non cancella silenziosamente documenti.

La prova è una fattura tecnica interna, non documento fiscale. Non certifica SdI, numerazione legale, conservazione, imposte generali, contabilità, ERP, e-mail, pagamenti, disponibilità single-host o SLA. B13 deve materializzare la sola scrittura F04 approvata con recupero intermodulo; B14 deve provare profili congiunti e backup/destroy/restore misurato. Nessun ambiente persistente o dato reale è stato creato.
