# R05.a.7 — Contratto sandbox dell'ordine di acquisto Giobby

**Esito: ORDINE DI ACQUISTO OSSERVATO (1 scrittura persistita, 2 simulazioni); idVendor stringa richiesto, idContact risolto dal server; prezzo a 6 decimali riletto esatto sulla riga, totali di testata a 2 decimali; effetto stock solo «ordinato ai fornitori»; lookup per nome fornitore + stato + filtro client sulla reference. Nessuna garanzia provider.** Refs #124 / #44 / #45. Stesso scopo D83/D84 (sandbox nominato, isolamento per owner-assertion, non prova tecnica indipendente): **nessuna nuova decisione**. Matrice [r05a7-evidence.json](r05a7-evidence.json); R05.a.5 e R05.a.6 invariati byte per byte (hash nella matrice). Nessun connettore, schema, runtime, dipendenza o Docker; nessun ricevimento D86.

Autenticazione api-server, discovery e legame CID/company rifatti in RAM protetta (vault, nessun token su disco, RAM svuotata a fine run). Ledger privato 0700/0600 con un file append-only per richiesta: l'**intent è scritto prima di ogni richiesta** (anche delle simulazioni), la risposta grezza è conservata in file privato 0600 con SHA256; le fixture committate sono proiezioni con alias e SHA256 del payload proiettato. Tetti dichiarati: 3 POST persistiti, 2 simulazioni, 45 richieste, limit5, 0,5 s. Effettuati **1 POST persistito, 2 POST simulation=true, 14 GET (17 richieste), 1 oggetto proprio** (prefisso `E360-SB-R05A7-…`). Fornitore proprio R05.a.4 riusato (nessun nuovo fornitore); nessuna cancellazione, invio o ricevimento.

Le tre classi di evidenza restano separate: **dichiarazione pubblica** (Swagger, SHA256 uguale a R05.a.6), **osservazione sandbox** (richieste e risposte), **guardia locale** (assessor offline).

## 1. Campi richiesti (osservazione + dichiarazione)

Il modello `DocumentApi` dichiara obbligatori `docDate, idBu, idContact, idNumerator, payments, rows` e le righe `description, idMaterial, idPosType, price`. **Osservato diverso dalla dichiarazione:** `idContact` è stato accettato **null**; ciò che il server esige è `idVendor` **stringa** (identico alle richieste riuscite di R05.a.4/a.5). Corpo osservato (valori nel file matrice con alias): `idDocumentType 2`, `idOrderType 1`, `idContact null`, `idVendor "<id fornitore>"`, `docDate` (epoch millis come stringa), `docStatus CREATED` (inviato, **ignorato** con avviso), `docCurrency EUR`, `idBu`, `idNumerator`, `reference`, `note`, `payments: []`, righe con `idMaterial`, `idAttributeCombination 0`, `idPosType 1`, `description`, `quantity`, `price`, `idVat`, `idStorage`. `docNumber` **non inviato**: assegnato dal server (numero ODA non fiscale, non correlabile).

## 2. P1 — Fornitore e contatto numerico

| Prova | Osservato |
|---|---|
| `GET /vendors?name=…` | elenco con `id` fornitore (stringa) e `contact.id` (intero), `contact.idVendor` = id fornitore |
| POST simulazione con `idVendor` stringa, `idContact` null | HTTP200, anteprima |
| POST simulazione con solo `idContact` numerico | **HTTP400, errorCode 324** «Il campo Fornitore è obbligatorio» |
| Readback dell'ordine persistito | `idContact` **intero** = `contact.id` del fornitore, `idVendor` stringa |

Verdetto `VENDOR_STRING_ID_REQUIRED_CONTACT_SERVER_RESOLVED`: l'adapter invia l'**id fornitore stringa** e `idContact` null; l'id contatto numerico non è un input accettato da solo e non serve inviarlo. L'id numerico è solo letto in risposta (può servire per i filtri, ma il filtro `idContact` ha restituito 0 righe, vedi §5).

## 3. P2 — Simulazione `simulation=true` (non persiste)

Corpo completo con prezzo 12,345678: HTTP200/error0, `document.id` null, `docNumber` vuoto, riga con prezzo 12.345678 riecheggiato, totale 15,07 e una rata «Unica rata» calcolata anche con `payments: []`. Non persistenza: elenco ordini del fornitore (stessi id prima/dopo) e report stock identico (`NOT_PERSISTED_BY_VENDOR_LIST_AND_STOCK`); anche la prima pagina dell'elenco generale non mostra nuovi id (contiene una riga non propria, solo contata). Come in R05.a.5 la simulazione è anteprima non persistente, **non** prova di validazione completa né di idempotenza.

## 4. P3 — Ordine persistito: ack, readback, prezzo, stock

- **Ack**: HTTP200/error0, solo `idDocument` (intero) più avviso «docStatus … ignorato». Nessun documento nell'ack.
- **Readback** `GET /purchases/{id}/orders`: `idDocumentType 2`, `docStatus CREATED`, `reference` esatta, `idVendor` stringa, `idContact` intero, riga con `description` esatta, `quantity 1`, **`price 12.345678` esatto (6 decimali)**, `idVat`, `idStorage`, `idPos` intero; `taxableAmount 12.35`, `vatAmount 2.72`, `totalAmount 15.07`. I totali sono arrotondati a 2 decimali dal netto già arrotondato (`ROUNDED_2DP_FROM_ROUNDED_NET`, verificato dall'assessor): **il totale non conserva il q6**. L'adapter può confrontare il prezzo riga in esadecimale esatto, non il totale di testata a q6. Netto/IVA indipendenti non verificati su più righe.
- **Elenco** (`GET /purchases/orders`): le testate hanno `totalAmount`, `reference`, `idVendor`, `docStatus`, `idContact` **null**; **non** hanno prezzo né descrizione. Il prezzo si legge solo dal dettaglio.
- **Stock** (materiale proprio, magazzino MB, prima → dopo): fisico 2→2, impegnato 1→1, disponibile 1→1, **ordinato ai fornitori 6→7, prospettico 7→8** (`ORDERED_ONLY`). L'ordine di acquisto non cambia lo stock fisico né la disponibilità; la simulazione non cambia nulla (`NO_STOCK_EFFECT`).

## 5. P4 — Lookup dopo risposta persa (vincoli)

Chiave scelta e registrata **prima** della lettura: `freeText` = nome del fornitore + `docStatus=CREATED`, offset 0, limit 5, poi **filtro client sulla reference esatta**. Il fornitore ha 2 ordini propri: la pagina restituisce 2 testate, ordinate dal **più recente** (id decrescente), 1 sola con reference esatta (`UNIQUE_AFTER_CLIENT_REFERENCE_FILTER`).

| Verifica | Esito |
|---|---|
| `limit=1, offset=0` | testata più recente, reference esatta |
| `limit=1, offset=1` | 1 testata, nessuna reference esatta → `HOLD_PAGE_FULL_NOT_FOUND` |
| `freeText` sulla reference | 0 righe (`HOLD_NOT_FOUND`) |
| filtro `idContact` | 0 righe |
| `metadata.totalCount` | uguale al numero di righe della pagina (con limit 1 vale 1): **non è un segnale di completezza** |

Limiti onesti: il lookup è stato eseguito **dopo** aver ricevuto l'ack (risposta non persa), quindi non è una prova forense di lost-success; confronto con l'id dell'ack solo dopo. Pagina piena senza match, vuoto o più match restano HOLD, mai assenza e mai autorizzazione al replay. Un solo fornitore, un tentativo; prima lettura ~12 s dopo il POST già coerente (nessuna garanzia di ritardi inferiori).

## 6. Su cosa l'adapter PUÒ contare (osservato, non garantito) e su cosa NO

PUÒ (solo come comportamento osservato in questa sandbox): `idVendor` stringa con `idContact` null accettato; ack con `idDocument` intero poi readback per ID; prezzo riga q6 riletto esatto; effetto stock «solo ordinato»; lookup nome fornitore + stato + filtro client sulla reference.

NON PUÒ contare su: idempotenza server, exactly-once, collegamento ricevimento→ordine tramite reference (non provato), totale di testata a q6, `totalCount` come completezza, vuoto come assenza, `idContact` numerico da solo, prezzo nella testata di elenco, `docNumber` come correlazione, `docStatus` impostabile dal client, numeratore derivabile dal tipo documento (la query restituisce 2 numeratori), replay cieco dopo risposta persa.

## Brief per lo slice connettore R04.b.2b.3 (#124)

Prerequisiti ora disponibili come evidenza osservata: forma del corpo (§1), identità fornitore (§2), ack+readback (§4), lookup (§5), effetto stock (§4). Il connettore deve: (1) mappare l'id fornitore Giobby (estensione societaria D88) alla stringa `idVendor`, mai al solo id contatto; (2) inviare solo il prezzo congelato D91 come `price` di riga e completare solo se il readback per ID restituisce quel prezzo riga esatto, con descrizione, quantità, reference, fornitore e tipo 2 (il totale di testata non è confronto q6); (3) trattare `idDocument` come ricevuta, non come completamento; (4) su risposta persa/timeout/500 fermarsi in HOLD e usare solo il lookup del §5 (chiave unica per tentativo: un nome fornitore univoco o filtro client esatto sulla reference), con vuoto/pagina piena/più match = HOLD senza replay; (5) fallire in modo chiuso senza mapping host per `idBu`, `idNumerator`, `idVat`, `idStorage`, materiale; (6) non toccare lo stock locale (D82) e non creare ricevimenti (D86 resta separato e non provato per il collegamento). Test di accettazione con fake TLS e le sole fixture `tests/fixtures/r05a7-owned-captures.json`; nessuna affermazione di compatibilità live.

## Gap residui

Nessun ricevimento D86 né verifica del collegamento riga/ordine per l'ordine di acquisto; lost-response reale non simulata; una riga, quantità 1, IVA 22, magazzino MB, un numeratore; mapping `idBu/idNumerator/idVat/idStorage/idMaterial` come configurazione host da fornire; nessuna cancellazione/stato successivo; paginazione oltre 5 e ritardi non caratterizzati. L'ordine proprio resta nella sandbox (nessuna cancellazione).

## Incidenti (onesti)

Vedi la matrice: identificatori di login/CID/client id esposti al transcript del worker (non a repo/ledger/fixture); campo password riempito dal vault ma login digitato dai metadati; riga non propria conteggiata nel primo elenco generale; fornitore R05.a.4 riusato (l'elenco contiene anche un ordine R05.a.5); cronologia intent→risposta provata da mtime dei file privati; RED delle fixture-matrice di classe setup (file assente) distinto dai RED comportamentali degli assessor.

## Guardie

`scripts/r05a7_purchase_order.py` (decoder testa-prima, assessor identità fornitore, prezzo, stock, non persistenza, lookup, corpo richiesta, ledger e redazione) e `scripts/test-r05a7-evidence.py` (unit + matrice + 21 mutazioni CLI: false promozioni, redazione, cronologia intent-prima-della-richiesta, tetto POST, solo prefisso proprio). Fixture di sole risposte proprie proiettate (`tests/fixtures/r05a7-owned-captures.json`). CI solo offline `affected-r05a7-offline`, senza credenziali, runtime o Docker.

Rollback: PR tracciata dei soli documenti/test/wiring; gli oggetti ERP propri e lo storico stock non si cancellano. R04/R05/readiness, idempotenza e connettore restano aperti.
