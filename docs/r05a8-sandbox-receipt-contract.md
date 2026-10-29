# R05.a.8 — Ricevimento D86/D93: riproiezione read-only dei raw propri

Refs #128, #44, #45. **OBSERVED_CONTRACT_WITH_GAPS**: recuperati otto raw business propri del 27 ottobre 2026, con SHA-256 originali verificati, senza nuova chiamata sandbox, POST, simulazione o oggetto. Nuova matrice [r05a8-evidence.json](r05a8-evidence.json), nuove [proiezioni minimizzate](../tests/fixtures/r05a8-owned-captures.json). Nessun nuovo D-number: osservazioni, non decisioni. D93 documentale è già unita; questo incremento non implementa ricevimento, permessi, overlay o connettore.

## Contratto attivo e limiti

- READ_ONLY_REPROJECTION; new_business_requests=0; new_persisted_posts=0; new_simulations=0.
- GET_ONLY_HELD; pagina vuota/piena/duplicata, timeout/500 o dettaglio non concordante => HOLD_NO_REPOST, mai un altro POST.
- FRACTIONAL_Q6_UNPROVEN: prezzo ricevuto1.000000 / quantità1.000000 coincidono con l’input storico; la conservazione di una frazione a sei decimali non è stata esercitata sui ricevimenti.
- ORDINARY_LOOKUP_NOT_RECOVERY: lista UI storica positiva, non chiave preregistrata né lost-success e non lista del ricevimento API standalone.
- PER_ORDER_RESIDUAL_UNKNOWN; orderedToSuppliersQty è aggregato pool, non residuo del singolo ordine.
- D82_ERP_ONLY; D86_INTERNAL_SOURCE_LINK; D93_DISTINCT_OWNER_GRANT; D90_NO_REPLENISHMENT; D91_FROZEN_PRICE; D92_NO_EXPANSION.
- R04_R05_OPEN; NO_RUNTIME; NO_READINESS; FULL_ARCHITECTURE_FALSE.
- PARTIAL_3_2_APPROVED; OTHER_QUANTITY_OVERRECEIPT_WAREHOUSE_PRICING_FISCAL_UNDECIDED.

## 1. Che cosa cambia rispetto all’inventario precedente

L’inventario D86 descriveva correttamente le **vecchie proiezioni minimizzate**: i campi mancanti erano UNKNOWN lì, non assenti nel provider. Sono ora riproiettati i raw originali, non risposte ricostruite da parser ordine o nuovo GET con vecchia provenienza. Originali, ledger e vecchie fixture/matrici sono immutati; manifest privato prima/dopo e hash storici nella matrice nuova. SHA prova i byte conservati, non firma del provider né compatibilità futura.

| Capture originale | Osservazione conservata | Acquisizione UTC | Limite |
| --- | --- | --- | --- |
| R05.a.5 /28 | ack idDocument | 2026-10-27 12:04:06.035448 | Identità, non completamento |
| R05.a.5 /29 | dettaglio receipt tipo0 | 2026-10-27 12:04:06.780489 | Una riga, prezzo1/qty1 |
| R05.a.5 /21 e /30 | ordine sorgente prima/dopo | 12:03:11.940673 / 12:04:07.433214 | Testata e righe invariati |
| R05.a.5 /22 e /31 | stesso materiale/magazzino stock pool | 12:03:12.620230 / 12:04:08.109569 | Non residuo per ordine |
| R05.a.3 /23 | dettaglio ricevimento linked UI | 2026-10-27 10:36:37.049525 | Operazione diversa da standalone API |
| R05.a.3 /32 | lista receipt una testata, limit5/offset0 | 2026-10-27 10:38:06.897414 | Lookup ordinario postack; dettaglio già letto |

Ogni riga nella matrice conserva hash sorgente, hash della proiezione canonica, UTC originale, fase/seq, ownership e pointer→tipo. Gli alias numerici/stringa sono coerenti nella nuova fixture e **non sono ID live**; non usare alias301/102/401 come mapping. Il prezzo/quantità restano numeri come osservati, null distinto da assente. Descrizioni materiale sintetiche conservate; sola nota generata UI con riferimento a documento sostituita esplicitamente da `[owned-generated-source-note-redacted]`. Esclusi vendorData, contatti, società/account/CID/client, destinatari, indirizzi, email/telefono, pagamenti e segreti. Nessun raw completo nel repository/CI.

## 2. Confronti indipendenti supportati

Sul ricevimento **API standalone**, il raw di dettaglio restituisce e coincide con la richiesta storica per `idDocumentType=0`, vendor stringa, reference, BU, numeratore e riga `idMaterial`, `idPosType`, quantità1, prezzo1, descrizione, storage, IVA. L’id del dettaglio coincide con quello dell’ack e con l’oggetto proprio del ledger. Ownership di vendor/materiale verificata sugli oggetti propri dei ledger anteriori; non da un nome display o ID arbitrario. Posizione restituita `idPos=1`: non dedurre uguaglianza con la posizione2 dell’ordine sorgente. L’input aveva un riferimento nativo sperimentale, ma i quattro riferimenti di riga restituiti sono **null**: non un legame provider. Reference receipt e ordine coincidono storicamente: NON è una chiave receipt-specifica univoca per un nuovo tentativo.

`sent-comparison` è la proiezione dei soli campi effettivamente comparati della richiesta storica; **non** un corpo completo da inviare. Le guardie confrontano campi, tipi, quantità e prezzo indipendenti, non un totale di testata come sostituto q6. Il valore1 è rappresentabile a q6, ma non dimostra che12.345678 sopravviva alla ricezione: R05.a.7 lo prova per un **ordine**, non un ricevimento. Una mutazione sintetica nei test non acquista quella prova provider.

L’ordine sorgente proprio (due righe stesso SKU: quantità1 e2) resta CREATED, righe CREATED e quantità invariate. Stock dello stesso pool: fisico1→2, disponibile1→2, riservato0→0, ordinato6→6, prospettico7→8. Questo conferma l’effetto standalone osservato, non quantità ricevuta/residua del singolo ordine. `receivedQty`/`residualQty` non aggiunti, né derivati dal pool. Il confronto storico non è una lettura dello stato corrente dell’ordine R05.a.7 e non abilita una nuova scrittura su quell’ordine.

## 3. Recovery: fatto storico separato dal guard locale

La lista R05.a.3 restituisce una sola testata propria su pagina non piena, con reference/tipo/vendor/id coincidenti col dettaglio linked UI. È prova di **lookup ordinario**, dopo che id e dettaglio erano già noti; nessuna chiave preregistrata, risposta persa o recovery standalone dimostrati. Non trasformare la seq32 del vecchio ledger in una preregistrazione moderna. I raw R05.a.5 /25 e /32 sono **byte vuoti**, non JSON con array vuoto: non sono nuove fixture di assenza né lookup positivi.

Per il futuro adapter, esito incerto = GET-only-held; una lista piena è incompleta anche con un match. La guardia offline richiede limit5/offset0, un unico match esatto tipo/vendor/reference su pagina non piena e dettaglio concordante; rifiuta vuoto/full/duplicati/errori/mismatch senza POST. Il caso locale con `precommitted=True` è **mutazione sintetica dichiarata**, non nuova osservazione provider. Nessuna idempotenza, exactly-once, ritardo massimo o assenza conclusiva provata.

## 4. Perché zero nuove scritture; gate ancora aperti

I raw conservati recuperano identità, campi di riga, confronto prezzo/destinazione e ordine/stock richiesti per il **contratto osservato limitato**. Il ramo prudente GET-only-held non richiede provocare una nuova creazione per mascherare il gap recovery. Perciò non è avviato un executor sandbox né speso il budget1 POST+1 simulazione/25 chiamate D83/D84; nessuna nuova autorizzazione richiesta. Non si dichiara tuttavia chiusa la prova forte del prezzo frazionario q6 o del recovery standalone. Se il prossimo slice richiede questi fatti, eseguire il distinto handoff bounded del runbook, non assumere successo da questa PR.

Prerequisiti invariati per quell’executor: autentica protetta RAM-only e /loggeduser società esatta, ledger fsync prima di **ogni** richiesta, ordine/riga R05.a.7 reali e propri riletti con eleggibilità residua attuale verificata, vendor/materiale/magazzino originali, BU/numeratore receipt verificati; mai nuovi vendor/materiale/ordine, PUT/DELETE/cancel/transform/replay. Chiave con soli filtri dichiarati e reference receipt-specifica preregistrata **prima** dell’oracle; ambiguità o ownership/residuo incerti STOP/HOLD, nessuna seconda POST. Non usare i valori del vecchio receipt come configurazione host o come stato corrente. D84 resta owner-assertion outbound, non verifica tecnica universale; nessun invio/SdI/email.

Runtime successivo soltanto dopo merge dell’evidenza: contratto pubblico del modulo proprietario su ordine CONFIRMED e righe/prezzi/destinazione congelati, azione distinta D93 owner-controlled su membership già trusted/offline verificata/audit immutabile; acquisto/quote non concedono ricevimento e D77 non estende delega. Link interno esplicito, overlay non autorevole con stato ERP e discrepanza visibili; nessuno stock writer locale o correzione silenziosa, riapertura cap D90, repricing D91 o consultazione listini estesa D92. Parzialità3/2 già approvata; altre policy quantitative/overreceipt, cambio magazzino e pricing/fiscalità del ricevimento non decise da questi input di prova.

## 5. Incidenti, verifica e rollback

Conservati gli incidenti precedenti: R05.a.5 ledger sovrascritto da snapshot obsoleto, osservazioni10–17 ricostruite e tre lookup-zero raw persi; apertura accidentale di fattura non propria solo read-only; R05.a.7 identificatori login/CID/client esposti nel vecchio transcript, non in repo/fixture. Nessuno ripetuto qui, nessuna ricerca sessione/credenziale o lista vault. Nuovo incidente di minimizzazione: primo estrattore ha rifiutato la nota generata UI non prefissata; nessun contenuto stampato, redazione esplicita e nuovo run riuscito. Fallimento setup/minimizzazione, non RED applicativo.

Test offline `scripts/test-r05a8-evidence.py` e selezione `scripts/test-r05a8-impact.py`: decoder receipt separato da purchase-order, confronti indipendenti, HOLD di lookup e mutazioni di provenienza/ownership/hash/conteggi/cronologia/redazione/promozioni false. Il primo import senza modulo è setup, NON RED comportamentale; i successivi baseline permissivi sono falliti per rifiuti mancanti prima delle guardie. Dati synthetic test ≠ catture provider. CLI exit0 = coerenza documentale offline, non ricevimento completato né compatibilità live.

CI PR-only e dispatch exact-head `full_architecture=false`, solo job offline selezionati; nessuna credenziale o richiesta ERP in CI, runtime skipped non pass. Esiti/head/tree/job effettivi sono riportati soltanto dopo esecuzione nella PR/report, non anticipati qui. R04/R05/#128/#44/#45 restano aperti; D89 Esercizio OPEN/BACKLOG, finale architettura dopo completamento funzionale. Nessun SQL/migrazione/app/deployment/acquisto/dato reale/ambiente persistente o modifica bootstrap/Tailscale443→9119/25 volumi/ramo R00. Parent mantiene merge/chiusure/board e proprio readback indipendente.

Rollback: PR tracciata dei soli nuovi documenti/fixture/guardie/wiring; mai cancellare oggetti o storia ERP, riscrivere i vecchi raw/ledger o dichiarare completamento del runtime.
