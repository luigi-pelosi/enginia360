# R05.a.1 — contratto READ Giobby: stock, acquisti, ricevimenti

**Esito: BLOCKED_PROVIDER_READ_SCHEMA.** Consegna documentale finita, non adapter o connessione ERP funzionante. R04.b ERP BLOCKED; R04 e R05 restano incompleti. Nessuna readiness operativa o validazione runtime del setup. Refs #88 / #45 / #44. Acquisizione **25 ottobre 2026 UTC**, non data/versione di rilascio provider.

## Confine D82 e decisione

Stock e catena acquisti appartengono allo **stesso ERP esterno autorevole** nel pilota. Nessun writer misto, fallback locale o fonte tecnica locale sostitutiva. Nessuna scrittura locale di ricevimento nel profilo ERP. La regola approvata **3 ordinati / 2 ricevuti** resta condizionata all'autorità: non è permesso di carico locale. D80/D81 e prove sintetiche storiche preservate, non prove ERP. D76 non forza ogni futuro cliente all'ERP; nessun cambio automatico/retroattivo di autorità. Unica autorità anagrafica tenant-wide D26/D65, estensioni/prezzi/stock societari distinti.

Il gate riguarda **i fatti provider**, non una nuova domanda di policy al proprietario. Schema READ assente ⇒ impossibile verificare oggi un parser positivo o il legame ordine/ricevimento. Assenza di documentazione non significa funzionalità inesistente. HTTP 200 non è business ACK, autorizzazione di lettura/scrittura o prova di compatibilità. La bozza fattura D79 resta un **gate separato ancora aperto**: questo dossier non risolve creazione senza effetti, ACK o recupero dopo timeout.

## Fonti, metodo e limiti

Solo asset statici pubblici ufficiali acquisiti, nessun GET/POST business, login, discovery account, credenziale, contatto provider o risposta reale. Nessun Docker/install/deploy/ambiente persistente. Bootstrap/Tailscale/25 volumi/backups e branch R00 non toccati. Ricerca limitata a Swagger, reference e guida API.[1][2][3]

Due guide prodotto completano la ricerca; nessuna reiterazione per aggirare il gate schema.[4][5]

La [matrice machine-readable](r05a1-evidence.json) contiene per ogni osservazione Swagger URL primario, SHA-256 dei byte, istante, content type, percorso privato content-addressed, JSON pointer e hash canonico dell'estratto. Le fonti complete rimangono **PRIVATE scratch**, non fixture e non asset vendorizzati. Permessi locali read-only: il nome hash rileva modifiche, non offre garanzia di conservazione o autenticità provider. Gli URL sono mutabili; l'hash non è una versione API supportata. CI non dipende dai file scratch.

- `[1]` Swagger: `0c43f06fa1481fa39d5e0a63f61c5843ded5b82335e68bcb840dc974e13574a3`, `application/json`, 10:19:11.790687Z.
- `[2]` reference: `f81a2f67f6a302ab41dbba959c85097cb7e0032405b1d6fb64a4839aa13ed7aa`, `text/html`, 10:19:11.739721Z.
- `[3]` guida API: `66acacdab80e916233eb1bea3a304bd0e8a89625036ba2755c99820ec34580e4`, `text/html`, 10:19:11.681289Z.
- `[4–5]` hash/istanti/content type e URL finali nella sezione `sources` della matrice; estratti visibili adiacenti ai byte grezzi con suffisso `.visible.txt`.

Manifest: `/root/.hermes/cache/scratch/R05a1-public/manifest.json`. Contesto statico PUT/idPos e DELETE conservato in `/root/.hermes/cache/scratch/R05a1-public/dab7bca85aa229d0aa174b646181e675f01bb82ad58c9299941035895ca86e13.context.json`, hash SHA-256 `dab7bca85aa229d0aa174b646181e675f01bb82ad58c9299941035895ca86e13`, pointer e hash estratti nello stesso file; non risposta operativa. Ogni `private_path` è assoluto e content-addressed; l'estratto per pointer è riproducibile con `--assets`, senza rete. Tipi/nomi/esempi riportati sono dichiarazioni pubbliche, **mai risposte simulate**. Una definizione usata da POST non viene promossa a schema GET.

## 1. Superficie READ effettivamente pubblicata

Tutti i pointer seguenti sono in `[1]`, prefisso `#/paths/`, separatore `/` codificato `~1`. Il nome errato **avaibility** è preservato. Per tutte le operazioni qui sotto, `.../get/responses` contiene esclusivamente `default.description`, senza schema, examples o headers. Citazione ristretta dell'oggetto: `successful operation` non descrive l'esito business.[1]

| Path relativo documentato | operationId | Request pubblicata; non forma della risposta |
| --- | --- | --- |
| `/stocks/avaibility` | `getAllStockAvaibility` | limit/offset integer int32; idMaterial/idStorage/idLocation string; detailLevel integer int32; zeroQtyRows boolean. Tutti opzionali. idLocation richiede nella prosa idStorage e detailLevel, senza valori/enumerazione detailLevel. |
| `/stocks/avaibility/report` | `getAllReportStockAvaibility` | limit/offset int32, idMaterial/idStorage/idLocation string; zeroQtyRows/attributesDetail/storageDetail/lotsDetail boolean. idLocation richiede idStorage nella prosa. |
| `/storages`, `/storages/{id}` | `getAllLots`, `getStorage` | Lista limit/offset int32, id string, managed boolean; GET singolo id string richiesto. Non correggere operationId getAllLots. |
| `/storageLocations` | `getAllStorageLocations` | limit/offset int32, idStorage string, managedStorage boolean. Nessun GET su `/storages/{idStorage}/storageLocations`: quel path espone POST. |
| `/products`, `/products/{id}` | `getAllProducts`, `getProduct` | Lista limit/offset int32; description string; salesEnabled/locked/stockEnabled/pricelistEnabled boolean; idPlugin string enum 1/2; createDateMillis/modifyDateMillis string. Singolo id string richiesto, pattern `(.+)?`. |
| `/um`, `/um/{idUm}` | `getAllUms`, `getUm` | Lista limit/offset int32, description/shortdescription string, showdeleted boolean; singolo idUm string richiesto, showdeleted opzionale. |
| `/businessunit/{idBu}/storage`, `/businessunitpoint/{idBup}/storage` | `getAllBuStorages`, `getAllBupStorages` | limit/offset int32; idBU oppure idBUP e idStorage string **query** opzionali. I placeholder del path non sono dichiarati come parametri path: incoerenza da chiarire, non riparare. |
| `/purchases/orders` | `getAllPurchaseOrders` | offset/limit int32, freeText/neDocStatus/docStatus/gtDocDateMillins string, idContact int32; opzionali. Non pubblica gtModifyDateMillins. |
| `/purchases/{id}/orders` | `getPurchaseOrder` | id integer int32 path richiesto; onlyHeaderData boolean query opzionale. |
| `/purchases/goodsreceipt` | `getAllGoodsReceipt` | offset/limit int32, freeText string, idContact int32; opzionali. Nessun filtro modifica o stato dichiarato qui. |
| `/purchases/{id}/goodsreceipt` | `getGoodsReceipt` | id integer int32 path richiesto; onlyHeaderData boolean query opzionale. |

La matrice registra gli array `parameters` completi e i loro indici, required/type/format/description/enum dove pubblicati; nessun default aggiunto. In stock, i booleani descritti dalla prosa come false di default non hanno necessariamente un keyword `default`. Omissione, null e boolean false non sono equiparati.[1]

## 2. Proprietà pubblicate: contesto MODEL, non contratto READ

Pointer precisi `#/definitions/{Model}/properties/{property}`; metadati esatti, inclusi esempi dove esistono, nella matrice. **Nullabilità non esplicitata** per le proprietà elencate; presenza in required non prova null ammesso né valore di default. Gli esempi stringa su campi numerici non sono conversioni autorizzate.[1]

| Model | Proprietà/tipi osservati | Limite |
| --- | --- | --- |
| ProductApi | id, barcode, basicCode, um, umDescription, defaultStorage string; kindOf integer/int32; createDate/modifyDate string/date-time; storageLocations array → ProductStorageLocationApi | ID/codice/barcode non intercambiabili; nessuna unicità/namespace/associazione con riga stock garantita dal GET. Non assumere che um abbia conversione o scala q6. |
| ProductStorageLocationApi / StorageLocationApi | idStorage/idLocation string; ProductStorageLocationApi aggiunge nameLocation string, seq int32 (solo contesto schema completo privato) | Nessun mapping dimostrato con WarehouseId/SiteId interni. |
| StorageApi | id string (esempio CS), managed integer/int32 (esempio stringa 1); required description,id,managed | Filtro managed boolean contro proprietà integer: non normalizzare. |
| UmApi | um, shortDescription_IT string | Nessun vincolo unità/conversione documentato per quantità ordine/ricevimento. |
| StockApi | idStorage/idLocation/idLot/idMaterial/um string; quantity number/double; stockState/idAttributeCombination integer/int32 | Usata in scritture `/stocks`, non collegata come response GET. quantity non prova fisico/disponibile/impegnato, stockState non prova stato acquisto/ricevimento. |
| DocumentApi | idBu string; idContact int32; idVendor/docStatus/docDate/destIdStorage/destIdLocation/reference string (docDate format date-time); rows array → DocumentRowApi | Body POST ordini/ricevimento rimanda a DocumentApi; nessun collegamento schema GET. required docDate,idBu,idContact,idNumerator,payments,rows. Non è identità documento restituito. |
| DocumentRowApi | idMaterial/idStorage/idLocation/idLot string; idAttributeCombination int32; quantity number/double; materialmovementref/materialmovementposref/saleorderref/saleorderposref int32 | required description,idMaterial,idPosType,price; nessun idPos dichiarato. Nomi ref non provano relazione **ordine acquisto → ricevimento** o identità stabile riga. La prosa PUT dei due documenti afferma che idPos viene restituito nel GET ordine (`#/paths/~1purchases~1{id}~1orders/put/description` e `#/paths/~1purchases~1{id}~1goodsreceipt/put/description`); mancano tipo, obbligatorietà, namespace, stabilità e schema response. Per il ricevimento la prosa nomina ancora ordine: non correggere l'ambiguità. Esempio stringa null non specifica nullability. |
| BupStorageApi | idBu/idBup/idStorage string | Associazione nominale, non garanzia di legal entity/company qualification o isolamento. |

Non propagare double nel dominio decimal/q6; precisione/rounding provider da confermare. La prosa POST consente idMaterial null mentre la proprietà è string required e payments opzionale mentre schema lo richiede: si registra l'incoerenza, senza costruire un payload per farla sparire.[1]

## 3. Semantica: fatti, unknown, non inferenze

**Stock:** Swagger descrive disponibilità comprensiva degli impegni. La guida UI `[4]` distingue fisico, impegni da clienti e ordinato ai fornitori; descrive il prospettico come somma di disponibile e ordini fornitori. La spiegazione introduttiva della stessa pagina usa disponibilità più ampiamente: non tradurla in un'equazione API. Citazione ristretta: «Giacenza Prospettica riporta la somma». **Unknown:** quali campi della risposta esprimano fisico/impegnato/disponibile/prospettico, segni, stock negativo, lot/variant/location aggregazione, istante di osservazione, righe a zero e detailLevel. Nessuna quantità ordinata futura può diventare fisico per deduzione.[1][4]

**Ordini/ricevimento:** la guida UI descrive passaggio da ordine a DDT-EM («Registra entrata merci»), ma non pubblica lo schema di lettura né identità riga o comportamento transazionale API. Reference `#docTypeTable` elenca tipo 2 ordine acquisto e 0 entrata merci; `#docStatusTable` contiene ORDER_CONFIRMED, COMPLETED_ORDER e GOOD_PARTIAL_DELIVERY, con etichetta «Merce parzialmente spedita». **Unknown:** sottoinsieme valido per acquisti, ricevuto parziale 3/2, residuo, eccedenze, annullato/rettificato, stato confermato, quando stock è aggiornato, legame riga ordine-ricevimento e destinazione realmente applicata. Non usare una label spedizione come prova ricevimento.[1][2][5]

**Identità/provenienza:** i GET documenti richiedono id int32, prodotti id string. Questo non prova nomi/tipi degli ID restituiti né loro unicità account/company/document kind; barcode/basicCode non diventano chiavi SKU. idBu/idBU/idBup/idBUP non equivalgono automaticamente a società/sede; CID/idCompany non sono TenantId. La guida API descrive endpoint dinamico GiobbyApiURL dopo login, non autorizza chiamarlo in questa ricerca. Permessi specifici di lettura, account/company scope e limitazioni non sono dimostrati dagli asset statici.[1][3]

**Pagine/delta:** limit/offset non garantiscono ordine stabile, totale/fine lista, snapshot o assenza di omissioni con aggiornamenti concorrenti. Prodotti documentano filtri create/modify inclusivi combinati OR; non trasferirli ad acquisti. gtDocDateMillins è nome filtro ordine, non prova delta per modifica; ricevimenti non dichiarano filtro delta. showdeleted unità non prova tombstone feed per prodotti/ordini/ricevimenti. Sono dichiarati DELETE `#/paths/~1purchases~1{id}~1orders/delete` e `#/paths/~1purchases~1{id}~1goodsreceipt/delete`, con description vuota e risposta default senza schema: il verbo non specifica annullamento business, effetti stock, reversibilità o visibilità successiva. **Unknown:** cancellazioni, revoche, trasferimenti, full reconciliation, retention e dati che spariscono tra pagine.[1]

**Consistenza/concorrenza/versione:** nessuno schema response/header nei GET esaminati, quindi nessun ETag/revision/watermark/snapshot pubblicato lì. info.version=1.0 non è versione account supportata; updated/modified non sono una fence transazionale. Letture ordine/ricevimento/stock separate non sono snapshot comune dimostrato. GET singolo per ID noto non recupera un ID perso in futuro POST. Idempotenza/dedupe/lookup/write permissions restano gate futuri separati, non requisito risolto da questa superficie READ.[1][3]

## 4. Minimo contratto indipendente futuro (proposta, NON implementato)

È implementabile successivamente la **specifica neutrale di una proiezione in sola lettura con stato unknown/not-ready**, non un reader Giobby positivo: nessuna DTO risposta, fixture business, migrazione, API, SDK, parser o enforcement setup creati qui.

1. Identità interna qualificata e lossless: TenantId + SourceId + ProfileId/version + namespace account provider + LegalEntityId + ExternalEntityKind + ExternalId. Mappatura distinta di WarehouseId/location, SKU/variant/unità e versioni mapping; nucleo master unico tenant-wide separato da estensioni societarie. Questi sono requisiti interni, non campi Giobby garantiti.
2. Evidenza immutabile di acquisizione: contratto verificato/versione e hash documentale separati, provenienza risposta autorizzata, timestamp raccolta versus timestamp provider, cursore/watermark **solo se garantito**. Mai binding retroattivo al profilo corrente. Una ricevuta tecnica locale non è ricevuta merce ERP.
3. Modelli concettuali minimi distinti: stock per warehouse/SKU/unità con quantità e semantica note; testata ordine e riga identificabile; ricevimento e riga con provenienza verso la riga ordine, quantità/unita/destinazione/stato. Campo non disponibile = unknown esplicito, non zero/default/null interpretato come assenza; nessun merge positivo finché manca schema necessario.
4. Query storiche autorizzate senza conferire writer; proiezione non prenota, riceve o rettifica stock. Stato stale/partial/unknown deve essere visibile. Nessun fallback al ledger locale o simulatore quando ERP assente; hold/reconciliation non inventa business ACK.
5. Pagine solo dopo prova ordine/fine/consistenza; overlap/dedupe non garantisce da solo completezza. Cancellazioni e correzioni devono riconciliarsi senza cancellare provenienza o trattare una lista vuota come assenza definitiva. Snapshot diversi non si sommano come fatti contemporanei.

**Condizione per il prossimo reader positivo:** schemi GET garantiti e risposte anonimizzate provider, mapping qualificati e semantica quantità/stati/provenienza/consistenza sufficienti; permessi e traffico autorizzati separatamente. Il gate non blocca UI o lavoro neutrale indipendente. La [bozza domande provider NON inviata](r05a1-provider-questions.md) richiede questi fatti senza riaprire D82 o la parzialità.

## Verifica, limiti e rollback

`python3 -I scripts/test-r05a1-impact.py` seleziona solo impact + affected-r05a1-offline per i sei path finiti più wiring; percorsi eseguibili ignoti falliscono chiusi, cambi misti mantengono security/runtime. Nessun runtime dispatch/full architecture per questi cambi non-runtime.

`python3 -I scripts/test-r05a1-evidence.py` e `python3 -I scripts/r05a1_evidence.py --check` verificano **coerenza documentale**, hash degli estratti e guardie negativi, non compatibilità provider. `--assets /root/.hermes/cache/scratch/R05a1-public` verifica anche hash dei byte e risoluzione pointer contro i veri asset acquisiti; nessuna rete. La mancanza dello scratch rende impossibile quella prova e deve fallire, non saltare o generare fixture. Risultati eseguiti/log/CI exact-head nella PR, non anticipati come connessione funzionante.

RED prima dei documenti e prima dell'enforcement guard, log privati `R05a1-logs/03-dossier-RED.log` e `04-guards-RED.log`; scope CI RED `01-impact-RED.log`. Nessun R04.b.1 o adapter R05 consegnato. Ripristino solo di questi documenti/test/wiring con PR tracciata; nessuna migrazione o rollback runtime.

## Sources

[1] https://app.giobby.com/GiobbyApi00554/swagger/swagger.json
[2] https://app.giobby.com/GiobbyApi00554/reference.html
[3] https://app.giobby.com/GiobbyApi00554/documentation.html
[4] https://www.giobby.com/guida-gestionale-ecommerce-integrati/visual-report/report-magazzino/report-analisi-disponibilita-magazzino
[5] https://www.giobby.com/guida-gestionale-ecommerce-integrati/acquisti/crea-un-ordine-fornitore
