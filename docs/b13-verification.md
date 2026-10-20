# B13 — Scrittura contabile tecnica

Stato: implementata e verificata localmente; consegna remota da verificare nella PR della issue #19. Baseline B12 main `703590533baab8f557df71b2c3f67c40ed4bd9ce` (PR #33, CI exact head push 39487596772 e PR 39487605553 success). D70–D73: un solo WIP, accettazione effimera isolata, nessun ambiente manuale persistente o gate di review di routine.

## Contratto e invarianti

- La scrittura nasce soltanto da una fattura tecnica **confermata** dello stesso tenant verificato: una bozza è rifiutata (404) e l'autorizzazione non viene nemmeno raggiunta. Una sola scrittura per fattura (`"InvoiceId"` univoco); un secondo comando con ID diverso è rifiutato 409 e non modifica nulla.
- Importi derivati esclusivamente dallo snapshot q6 della fattura confermata: Dare 120100 = totale documento; Avere 700100 = somma netti delle righe `Service`; Avere 700200 = somma netti delle righe `Part`; Avere 220100 = imposta aggregata. Nessun ricalcolo da catalogo, nessun arrotondamento aggiuntivo, nessun uso dell'imposta per riga.
- La quadratura è verificata nell'applicazione **e** imposta dal database (`journal_entries_balanced_check`, riga con un solo lato valorizzato). Valori incoerenti o non quadrati vengono rifiutati 409 (`invoice_values_inconsistent`, `journal_entry_unbalanced`), mai corretti silenziosamente. Il piano dei conti è customizing societario versionato: versione assente o incompleta → 409, nessun conto inventato.
- Registrazione insert-only e idempotente per ID comando: lo stesso comando restituisce 200 con lo stesso documento. Transazione locale al modulo Accounting con lock per fattura; il collegamento alla fattura appartiene a Billing e viene scritto nella sua transazione.
- Guasto intermodulo dopo il commit locale: la scrittura resta durevole, lo stato del collegamento è `Pending` ed è visibile; la fattura confermata non viene cancellata né modificata. Il ritentativo esatto completa il collegamento senza doppia registrazione. Nessuna atomicità globale promessa.
- Autorizzazione server-side sull'azione esatta (`accounting.journal-entries.post` / `.read`) con scope societario/sede e capability `internal-accounting` per la scrittura; RLS forzata su piano, scritture e righe. L'applicazione non ha privilegi UPDATE/DELETE e non può provisionare il piano dei conti.
- UI italiana: dichiara documento tecnico, ricalcola la quadratura dai valori ricevuti (non si fida del flag), conserva l'ID comando dopo una risposta persa, mostra il collegamento `Pending` e, al rifiuto, dichiara che la fattura confermata resta invariata.

## RED → GREEN eseguiti

I log sono in scratch, non nel repository.

| Prova | RED osservato | GREEN |
| --- | --- | --- |
| `AccountingBoundaryTests` (3 casi) | rotte inesistenti (404 invece di 401) e nessun guard di dipendenza: 3 test falliti (`b13-auth-red.log`) | 3 PASS: 401 prima di qualunque accesso al database e `InvalidOperationException` se la fatturazione interna è disabilitata (`b13-auth-green1.log`) |
| `scripts/test-b13.py` fixture del caso 001 | fixture B10 con 2 pezzi produceva 310.795000 invece di 200.690000 (`b13-full-attempt1.log`) | composizione esatta 74.25 + 90.25 + 36.19 = 200.69, con rientro carcassa e chiusura tecnica (`b13-full-attempt4.log`) |
| `scripts/test-b13-recovery.py` scope esatti | la prova usava una fattura non confermata: 404 prima dell'autorizzazione (`b13-full-attempt2.log`) | 403 separati per azione mancante, sede estranea, solo-magazzino e società estranea; capability disabilitata blocca la scrittura e lascia leggibile lo storico |
| Guasto del collegamento Billing dopo il commit Accounting | `('journal entry posted before link', 500, None)`: scrittura committata ma errore non gestito, stato invisibile (`b13-full-attempt3.log`) | 201 con `invoiceLinkState: Pending`, fattura confermata intatta, ritentativo esatto 200 → `Linked`, una sola scrittura e quattro righe |
| UI `src/B13.test.tsx` (8 test) | sabotaggio reale del componente (quadratura non ricalcolata, nessun minimo di righe, nessun formato conto, nessun messaggio 409): **6 test falliti** (`b13-ui-sabotage-red.log`) | componente ripristinato: 8 PASS (`b13-ui-unit-green1.log`) |
| `python3 scripts/test-b13-ci.py` | selezione B13 assente dalla CI (AssertionError sulla prima riga) | runner, build privata UI e host verificati, PASS |

Nota di metodo onesta: per la UI B13 il componente è stato scritto prima dei suoi test; la prova che i test mordono è un **sabotaggio eseguito** del componente, non un RED precedente. Per API, fixture, scope, guasto intermodulo e selezione CI il RED precede la correzione.

## Verifiche finali effettive

- `timeout 420 sh scripts/run-b13-tests.sh`: **PASS** (`b13-full-attempt4.log`). Tracer HTTP reale con identità sintetica reale, scrittura F04 quadrata, replay idempotente, secondo comando 409, link alla fattura, isolamento cross-tenant, input non fidato, rifiuto della bozza; scope esatti separati; guasto intermodulo e recupero; conteggi SQL (1 scrittura, 4 righe, 1 link); RLS con ruolo applicativo; audit strutturato; DOM reale con login e fetch; rollback rifiutato con scritture vive, poi eseguito e migrazione riapplicata; cleanup verificato dal trap (nessun container, rete o volume del progetto).
- `timeout 420 sh scripts/run-b12-tests.sh`: **PASS** (`b13-regression-b12.log`), otto marker B12 inclusi DOM, scope, storico immutabile, guasto intermodulo, RLS e audit.
- `timeout 560 sh scripts/run-b11-tests.sh`: **PASS** (`b13-regression-b11.log`), continuità, kill/restart reali, lease, riconciliazione, DOM e audit.
- SDK pinned: restore `--locked-mode`, API test **68 PASS**, audit NuGet API/test nessun package vulnerabile (`b13-dotnet-final.log`).
- Node pinned: **35 unit PASS, 11 runtime skip** fuori stack (il runtime B13 è eseguito e PASS dentro lo stack), tre build private e `npm audit` **zero vulnerabilità** (`b13-ui-full-audit.log`).
- `python3 scripts/test-b13-ci.py`, `test-b12-ci.py`, `test-ci-runtime.py` e `git diff --check`: PASS. La CI remota non è dedotta dai test locali.
- Risorse host protette: 25 volumi invariati, hash nomi/newline `18be04807d27c1f30683770dd421da191f0346e87aa8ebdb5fac2fe02d08390e`; soli container bootstrap originali attivi. Nessun prune, deploy pubblico, lettura di segreti o modifica di backup e configurazioni manuali.

## Migrazione, rollback e limiti

`database/b13/100_accounting.sql` introduce lo schema `accounting` con piano dei conti versionato per società, scritture e righe immutabili, vincoli di quadratura e RLS forzata; i grant applicativi sono SELECT sul piano e SELECT/INSERT su scritture e righe. `900_synthetic_fixtures.sql` contiene soltanto capability, permessi e il piano dimostrativo del riferimento F04. `950_rls_test.sql` esercita isolamento e privilegi con il ruolo applicativo reale. `990_rollback.sql` **rifiuta** se esistono scritture o collegamenti: prima del downgrade fermare le scritture, esportare o ripristinare secondo un piano approvato e risolvere i riferimenti; non cancella silenziosamente registrazioni. La suite esercita rifiuto, rollback e riapplicazione della migrazione.

La scrittura è tecnica e limitata al caso 001 validato tramite il proprietario (D43/D44): non è contabilità reale, non implementa piano dei conti universale, numerazione, periodi, partita doppia completa, IVA generale, incasso, costo del venduto, marginalità, bilancio, conservazione o invio fiscale. Il piano dimostrativo non è approvato come piano di produzione. B14 deve ancora esercitare i due percorsi congiunti e il backup/ripristino misurato; gli obiettivi RPO/RTO e i limiti di presidio restano dichiarazioni iniziali, non garanzie.
