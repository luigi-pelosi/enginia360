# Giobby — stock/acquisti/ricevimenti READ: domande contrattuali

**Bozza NON inviata.** Nessun contatto provider, credenziale o dato cliente. Ricerca statica pubblica del 25 ottobre 2026. Refs #88 / #45 / #44; [dossier](r05a1-giobby-read-contract.md) e [matrice pointer/hash](r05a1-evidence.json).

Oggetto proposto: schemi e garanzie API READ stock, ordini acquisto e ricevimenti collegati.

Buongiorno, stiamo definendo una proiezione **in sola lettura** da un unico ERP autorevole per stock e acquisti. Chiediamo risposte documentali riferite alla versione API supportata, non accessi o un test operativo. L'autorità unica e la regola di ricevimento parziale sono già definite dal nostro prodotto: non chiediamo una nuova approvazione del processo.

## P1 — risposte realmente supportate, non schema di scrittura

Per GET `/stocks/avaibility`, `/stocks/avaibility/report`, `/storages`, `/storageLocations`, `/products`, `/um`, `/purchases/orders`, `/purchases/{id}/orders`, `/purchases/goodsreceipt`, `/purchases/{id}/goodsreceipt` chiediamo:

- Schemi response ufficiali/versionati e **risposte reali anonimizzate dal provider**, inclusi lista/singolo, nessun risultato, warning/errori e accesso negato; con garanzia scritta del loro ambito. Non occorrono dati cliente o token, né esempi creati da noi.
- Envelope, campo/tipo ID, required/opzionale/null/omesso, array vuoti, date/timezone, numeri/precisione/scala e unità. Le definizioni ProductApi/StockApi/DocumentApi/DocumentRowApi sono effettivamente le risposte? Se no, fornire quelle corrette. Nel pubblico i GET hanno soltanto `responses.default.description`.[1]
- Distinguere successo HTTP, lettura coerente completa e documento confermato. Quali stati provano il fatto ERP, senza implicare fattura/pagamento?

## P2 — mapping company/warehouse/SKU/unità e significato stock

- Namespace e stabilità degli ID: account/CID/idCompany, business unit idBu/idBU, sede idBup/idBUP, warehouse/storage/location, prodotto idMaterial/id/basicCode/barcode e variante. Scope unicità, merge/rename/deletion e associazioni ammesse; nessuna nostra equivalenza automatica.
- Correggere o spiegare parametri query idBU/idBUP sotto path con placeholder idBu/idBup; managed filtro boolean contro StorageApi.managed integer.[1]
- Quali campi/unità corrispondono a **fisico**, impegni cliente, disponibile, ordinato a fornitori e prospettico? Segni, stock negativo, lotti/varianti, aggregazione, detailLevel ammessi, righe a zero, istante di osservazione e relazione con report UI. Il report prodotto non è oggi uno schema wire.[1][4]
- Come correlare catalogo → SKU stock → righe ordine/ricevimento senza usare descrizione/barcode come ID? Unit conversion, quantità frazionarie e sei decimali sono garantiti? Quali arrotondamenti si applicano?

## P3 — ordine → ricevimento parziale, identità e destinazione

- Risposte anonimizzate coerenti di un ordine con quantità 3 e un ricevimento collegato di quantità 2: ID **stabili delle righe** e documenti, quantità ordinata/ricevuta/residua, unità e destinazione effettiva per riga. È un requisito di evidenza provider, non un invito a creare documenti su un account cliente.
- Quali proprietà identificano la riga di ordine acquisto sorgente? DocumentRowApi non dichiara idPos; materialmovementref/posref e saleorderref/posref non documentano tale relazione. Spiegare trasformazioni, righe ripetute stesso SKU e più ricevimenti per riga senza duplicare quantità.[1]
- Stati applicabili a ordini **acquisto** e ricevimenti, conferma/parziale/chiusura, annullamento, resi/rettifiche ed effetto sullo stock/residuo. Reference elenca GOOD_PARTIAL_DELIVERY come spedizione: non lo assumiamo come ricevimento.[2]
- Distinguere idStorage/idLocation di riga e destIdStorage/destIdLocation di testata: priorità, significato e restituzione della destinazione realmente contabilizzata. Quando i GET stock e documento riflettono il medesimo ricevimento? La guida UI ordine→DDT-EM non stabilisce atomicità API.[1][5]

## P4 — completezza, delta e consistenza

- Limiti/default/massimi, ordine stabile, criterio fine pagina/totale/cursore, snapshot e comportamento durante inserimenti/modifiche/annullamenti concorrenti. Come evitare omissioni/doppioni e riconciliare stock/ordini/ricevimenti da snapshot differenti?
- Delta **per modifica** per ciascun endpoint (non solo data documento), precisione/tie-break/timezone, watermark, retention e tombstone per cancellazioni/annullamenti/merge. Prodotti documentano create/modify inclusivi in OR; ordini acquisto espongono gtDocDateMillins e ricevimenti nessun filtro modifica: quali garanzie mancanti sono disponibili?[1]
- Versioni/revision/ETag, letture condizionali o snapshot coerenti, latenza read-after-change, risposte parziali e recupero. Un 404/lista vuota è concludente quando? Quote/rate-limit, errori retryable e Retry-After documentati.

## P5 — permessi integrazione e confine future scritture

- Quale profilo minimo consente **solo** queste letture per le società/magazzini autorizzati? Quali scope, licenze, configurazioni account e policy di revoca/isolamento sono necessari? Versione supportata/deprecazioni e documentazione endpoint dinamico; nessuna credenziale richiesta.[3]
- Separatamente, **solo per una futura autorizzazione di scrittura**, documentare idempotency key/dedupe scope, durata, concorrenza, stesso key/payload differente, lookup univoco dopo timeout, autorizzazioni e riconciliazione. Non inferiamo capacità da GET per ID noto e non effettueremo reinvii ciechi.

La bozza fattura vendita è un altro gate D79 e non si considera risolta da queste risposte. In attesa manteniamo proiezione positiva **BLOCKED_PROVIDER_READ_SCHEMA**, nessun writer locale sostitutivo, nessun payload inventato e nessuna dichiarazione di connessione funzionante. Eventuali test account richiederanno separato incarico sicuro. Grazie.

## Sources

[1] https://app.giobby.com/GiobbyApi00554/swagger/swagger.json
[2] https://app.giobby.com/GiobbyApi00554/reference.html
[3] https://app.giobby.com/GiobbyApi00554/documentation.html
[4] https://www.giobby.com/guida-gestionale-ecommerce-integrati/visual-report/report-magazzino/report-analisi-disponibilita-magazzino
[5] https://www.giobby.com/guida-gestionale-ecommerce-integrati/acquisti/crea-un-ordine-fornitore
