# R05.a.6 — Ordine di vendita o proforma per D85

**Esito: ORDINE DI VENDITA SUITABLE-WITH-LIMITS; PROFORMA SUITABLE-WITH-LIMITS solo come secondo passo da ordine, non come scrittura diretta. Tipo raccomandato per l'adapter: ordine di vendita — raccomandazione basata su evidenza, che l'owner può ribaltare; nessuna decisione presa.** Refs #45 / #44 / #102. Stesso scopo D83/D84/D85 (sandbox nominato, isolamento per owner-assertion): **nessuna nuova decisione**. Matrice [r05a6-evidence.json](r05a6-evidence.json); R05.a.2–a.5 invariati byte per byte (hash nella matrice). Nessun adapter, schema, runtime, dipendenza o Docker; nessuna conversione in fattura, emissione o invio.

Autenticazione api-server, discovery e legame CID/company rifatti in RAM protetta (vault, nessun token su disco, RAM svuotata a fine run); ledger privato 0700/0600 creato prima di ogni scrittura, un file append-only per osservazione. Tetto 4 POST / 40 richieste / limit5 / 0,5 s; effettuati **2 POST, 19 richieste, 2 oggetti propri** più tre viste UI in sola lettura. Cliente, prodotto e magazzino propri di R05.a.3 usati solo come riferimenti; intent R05.a.3 (UNCERTAIN, ERROR_NO_REPLAY) tenuti, nessun cleanup.

Le tre classi di evidenza restano separate: **dichiarazione pubblica** (Swagger/reference), **osservazione sandbox** (richieste e UI), **guardia locale** (decoder/assessor offline).

## 1. Dichiarazione pubblica

- Percorsi proforma dichiarati: solo `POST /sales/{id}/orderstoproformainvoice`, `…/goodissuestoproformainvoice`, `…/proformainvoicetoinvoice`. **Nessun percorso crea una proforma da zero**; docType 33 «Fattura Proforma», 3 «Ordine Cliente», 10 «Fattura di vendita» (reference). La UI ha invece una voce diretta «Fattura Proforma», non esposta come API.
- La trasformazione ordine→proforma dichiara `idNumerator`, `docNumber`, `docDate`, nessun `simulation` e nessuno schema di risposta (solo `default`): la «simulazione prima» non è possibile e il risultato è osservabile solo per sandbox.
- `POST /sales/orders` dichiara `simulation` (non usato qui) e il corpo `DocumentApi`; la tabella docStatus non contiene bozza.

## 2. Ordine di vendita (osservazione sandbox)

`POST /sales/orders` con `simulation=false`, cliente/prodotto propri, qty1, `idDocumentType 3`, `docStatus CREATED` inviato: HTTP200/error0, solo `idDocument` + avviso «docStatus … ignorato».

| Aspetto | Osservato |
|---|---|
| Persistenza | readback `GET /sales/{id}/orders`: reference, note, riga qty1 prezzo1 IVA22 magazzino MB esatti; `docStatus` `CREATED` («Creato») |
| Numero | `docNumber` `"1"`, «ODV N. 1», numeratore ordini; **nessun numero fattura** (la fattura R05.a.3 è `"1659"`); numero non inviato, assegnato dal server |
| Stock (report prima/dopo) | fisico 2→2; impegnato 0→1; disponibile 2→1; ordinato fornitori 6→6; prospettico 8→7: **prenota, non scarica** |
| Pagamenti | inviato `payments: []`, creata una rata «Unica rata» 1,22 |
| Lookup senza ID | chiave **registrata prima** (file separato prima del POST): `freeText` = nome cliente + `docStatus=CREATED` → 1 testata, reference esatta, ID = oracolo (letto dopo). `freeText` su reference e `idContact` (id cliente e, dopo l'oracolo, id contatto del dettaglio) → 0. Testata di lista `idContact` **null**, dettaglio intero |
| UI (sola lettura) | pagina ordine: Salva, Stampa, Invia, Copia, Stampa Etichetta, Elimina; stato selezionato «Creato» con elenco (Ordine da confermare … Fatturato … Ordine evaso); **Lista Ordini ha «Genera DDT» e «Genera FT»** (non premuti); nessun «Genera proforma» |

## 3. Proforma (solo da ordine)

`POST /sales/{id}/orderstoproformainvoice` sull'ordine proprio, solo `idNumerator` e `docDate`, **una volta** (senza simulazione, non dichiarata): HTTP200, `idDocument`.

| Aspetto | Osservato |
|---|---|
| Tipo/stato | `idDocumentType 33`, `docStatus CREATED` |
| Numero | `docNumber` `"2"`; dettaglio `docTypeDescShort` «FTV», lista «FTP» (etichette discordanti); UI «Fattura proforma N° 2», lista «FTP N. 2». Numero diverso dalla fattura 1659: sequenza propria **sul campione**, non provata come separata |
| Stock | invariato rispetto all'ordine (fisico 2, impegnato 1, disponibile 1): **nessun ulteriore effetto**; l'ordine resta `CREATED`, la prenotazione dell'ordine persiste |
| Collegamento | righe proforma con `saleorderref`=ordine, `saleorderposref`=1 **persistiti** (a differenza del ricevimento R05.a.5); prima riga «Riferimento a ODV N. 1…» con `quantity` **null**, `idPosType` 5, `idMaterial` null; il decoder R05.a.3 la rifiuta (guardia locale `decode_document`, testa-prima, ammette il null solo sulle righe di puro riferimento) |
| Reference | ereditata dall'ordine (non impostabile), `GET …?onlyHeaderData=true` restituisce `documentHeader` senza righe |
| Lookup | stesso nome cliente restituisce **2 testate** (fattura numerata R05.a.3 + proforma): univoca solo filtrando lato client `idDocumentType 33` + reference; `freeText` sulla reference → 0 |
| UI (sola lettura) | pagina proforma: Salva, Stampa, Invia, Copia, Elimina, stato «Creato» in sola lettura; **nessun controllo di conversione in fattura**; la lista proforma ha «Genera XML», non «Genera FT». Conversione solo dichiarata via `POST /sales/{id}/proformainvoicetoinvoice`, **non esercitata** |

## 4. Confronto con D85

Requisiti: nessun numero fiscale, nessuno scarico stock fino alla decisione dell'operatore, conversione manuale, recuperabile senza ID server, readback esatto.

| Tipo | Verdetto | Limiti esatti |
|---|---|---|
| Ordine di vendita | **SUITABLE-WITH-LIMITS** | prenota (disponibile e prospettico −1; non è scarico fisico); chiave di lookup = nome cliente univoco per tentativo (reference/idContact vuoti); `docStatus` ignorato con avviso; `docNumber` assegnato dal server; rata creata nonostante `payments: []`; conversione in UI vista (Genera FT) ma non premuta |
| Proforma | **SUITABLE-WITH-LIMITS** solo come secondo passo; scrittura diretta **non dichiarata** | richiede prima l'ordine (2 scritture, ID ordine dal lookup); documento di classe fattura (tipo 33, «FTV/FTP N. 2»); lista mista con fattura e filtro client; riga di riferimento con quantità null; nessun controllo UI di conversione osservato, endpoint di conversione non esercitato; ordine e prenotazione persistono |

**Raccomandazione per l'adapter (evidence-based, owner-overrulable, non una decisione): ordine di vendita** — una sola scrittura, nessun artefatto di classe fattura, conversione manuale visibile nella lista ordini, lookup già verificato; la proforma aggiunge un secondo documento con lookup misto e senza conversione UI osservata. Se l'owner preferisce la proforma, restano da esercitare conversione e numerazione in un passo separato.

## Limiti e gap

- Osservato in questa sandbox, un cliente, un prodotto, qty1; nessuna garanzia provider, idempotenza o exactly-once; recovery di lost-response per ordini di vendita non provato.
- Prenotazione (rilascio/annullo, disponibile negativo) e conversioni ordine→fattura / proforma→fattura **non provate** (vietate qui). Nessuna conferma di invio/e-fattura/fiscalità.
- Incidenti: due 401 iniziali per campo password locale non popolato dal vault (nessuna credenziale esposta); RAM di sessione persa in navigazione UI e ribootstrap prima delle scritture; righe UI non proprie viste in sola lettura e non registrate.
- Guardie: `scripts/r05a6_document_type.py` (stock, numerazione, lookup tipizzato, verdetto, raccomandazione, decoder righe di riferimento) riusa invariati i decoder R05.a.3–a.5; fixture proiettate di sole risposte proprie (`tests/fixtures/r05a6-owned-captures.json`). CI solo offline `affected-r05a6-offline`, senza credenziali, runtime o Docker.

Rollback: PR tracciata dei soli documenti/test/wiring; gli oggetti ERP propri e lo storico stock non si cancellano. R04/R05/readiness, idempotenza e adapter restano aperti.
