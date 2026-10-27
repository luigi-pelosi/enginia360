# R05.a.5 — Chiusura dei tre punti sandbox aperti

**Esito: LOOKUP_ORDINE RESOLVED; RICEVIMENTO_PARZIALE_API PROVEN-NEGATIVE; BOZZA_D79 PROVEN-NEGATIVE sui percorsi testati.** Refs #45 / #44. Stesso scopo D83/D84 (sandbox nominato, isolamento per owner-assertion): **nessuna nuova decisione**. Matrice [r05a5-evidence.json](r05a5-evidence.json); R05.a.2–a.4 invariati byte per byte (hash nella matrice). Nessun adapter, schema, runtime, dipendenza o Docker.

Autenticazione api-server, discovery e legame CID/company rifatti in RAM protetta (vault, nessun token su disco, RAM svuotata a fine run). Ledger privato 0700/0600 prima di ogni scrittura, prefisso `E360-SB-R05A5-…`. Tetto 6 POST / 60 richieste / lookup limit5 / 0,5 s; effettuati **6 POST, 32 richieste, 3 oggetti propri** (2 ordini, 1 ricevimento) più letture UI. Intent R05.a.3 (UNCERTAIN, ERROR_NO_REPLAY) tenuti: nessun replay, cleanup o cancellazione.

## 1. D79 — bozza persistente: PROVEN-NEGATIVE (percorsi testati)

- **UI (sola lettura, nessun pulsante di emissione/invio premuto):** la nostra fattura numerata è «Creato»; azioni visibili Salva/Stampa/Invia/Incassa/e-Fattura/Copia/Elimina; nessun testo bozza/provvisorio; la nuova fattura ha Salva/Stampa/Invia/Incassa con controllo di stato senza opzioni; i filtri lista includono Stato, Documento Inviato, e-Fattura generata, nessun valore bozza. Nessuna distinzione bozza/conferma.
- **`simulation=true` su `POST /sales/invoices`** (cliente/prodotto propri, qty1): HTTP200/error0, risposta = **anteprima calcolata** (id null, numero vuoto, totali 1,00+0,22). Readback: id massimo lista invariato, prefisso proprio 0 risultati, stock (fisico 1, ordinato 2) invariato: **nulla persistito**. È un'anteprima non persistente, non una bozza.
- **Documentazione ufficiale:** tabella docStatus senza bozza; l'unica trasformazione vicina è ordine→proforma (altro tipo, non sostituto). Nessuna fattura numerata aggiuntiva creata.
- **Limite:** non è un negativo universale; nessun percorso persistente di bozza è documentato né osservato. D79 non è ridefinita né completata.

## 2. Correlazione ordine senza ID server: RESOLVED (caso osservato)

Parametri GET `/purchases/orders` dichiarati: `offset, limit, freeText, neDocStatus, idContact, docStatus, gtDocDateMillins`. Ordine A qty1 con fornitore proprio senza ordini precedenti (nome con prefisso univoco); chiave **decisa prima dell'oracle**: freeText sul nome fornitore, con idContact come candidato. Risposta scartata al confine client.

| Lookup | Risultato |
|---|---|
| freeText su reference esatta / prefisso nota | 0 |
| `idContact` = contatto del fornitore | 0 |
| freeText sul nome fornitore (**chiave**) | 1 testata, reference esatta, ID = oracle (letto dopo) |
| + `docStatus=CREATED`; ripetizione | 1, 1 |
| `gtDocDateMillins` = un'ora fa | 0 (docDate è solo data a mezzanotte) |
| `gtDocDateMillins` = inizio giorno −1 ms | 3 testate (limit5), 1 reference esatta filtrando lato client |

Primo lookup ~12 s dopo il POST già coerente (ritardi inferiori non provati; nessuna garanzia). Il server ha sostituito `docNumber` inviato: non è correlazione. Il recovery vale se la chiave è univoca per tentativo (un fornitore con prefisso per ordine) e si ferma (HOLD) se ≠1; vuoto non è assenza. Non è idempotenza server né exactly-once. 1 POST.

## 3. Ricevimento parziale via API: PROVEN-NEGATIVE

Nuovo ordine B (due righe qty1+qty2, stesso prodotto). Modello `POST /purchases/goodsreceipt` (DocumentApi) con riga `saleorderref=<ordine>`, `saleorderposref=2`, qty1, solo campi dichiarati:
1. `simulation=true`: HTTP200, anteprima (id null); i riferimenti non sono riecheggiati; avviso che `docStatus` in input è ignorato.
2. Persistenza con `docNumber` di 31 caratteri: HTTP400/errorCode3222 «massimo 20 caratteri»; nulla persistito (lista ricevimenti 0, stock invariato). La simulazione non aveva validato il campo.
3. Persistenza corretta (docNumber 10 caratteri, richiesta distinta dopo rifiuto definitivo): HTTP200, ricevimento creato. Readback: riga ricevimento con `saleorderref/saleorderposref/materialmovementref` **null**; ordine B resta CREATED con entrambe le righe CREATED; ordinato 6 invariato mentre il fisico sale 1→2. **Ricevimento standalone, collegamento non persistito** (rischio doppio conteggio).

`orderstogoodsreceipt` non ha selettore di riga. La variante `materialmovementref/posref` non è stata persistita (un solo ricevimento consentito). Il parziale via UI di R05.a.3 resta l'unica prova collegata.

## Altri esiti e limiti

- Prodotto 500: il prodotto UI proprio ha idType −1, idMaterialGroup null; il campione catalogo ha idType e gruppo null: i campi omessi non spiegano da soli l'errore; `id` stringa client resta candidato non provato. La lettura di confronto usò un path errato (405): **STILL-OPEN**.
- Incidenti registrati: sovrascrittura del ledger da oggetto obsoleto (osservazioni 10–17 ricostruite; raw dei tre lookup a zero righe perso, esiti da output); apertura UI in sola lettura per errore click di una fattura non propria, nessuna azione né salvataggio.
- Fixture proiettate di sole risposte proprie (`tests/fixtures/r05a5-owned-captures.json`); decoder testa-prima `scripts/r05a5_closure.py` (anteprima, set lookup, link ricevimento, testate ordine con ID interi) che riusa invariati i decoder R05.a.3/R05.a.4. CI solo offline `affected-r05a5-offline`, senza credenziali, runtime o Docker.

Rollback: PR tracciata dei soli documenti/test/wiring; gli oggetti ERP propri e lo storico stock non si cancellano. R04/R05/readiness, idempotenza e adapter restano aperti.
