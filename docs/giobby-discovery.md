# Giobby — evidenza ufficiale pubblica per R05

## Provenienza e limiti

Acquisizione read-only il **21 ottobre 2026**, finestra UTC 13:26:55–13:29:34.753792. Sono date di acquisizione, non di revisione provider. Baseline di ricerca `2ba4d273686854870b1a7806103bf1c096fcd0be`. Il presente dossier integra la ricerca ufficiale nel repository durante P00; non completa R05.a (mapping operativo ancora da fissare), non certifica compatibilità live e non seleziona il profilo pilota. Nessun login, credenziale, account API, discovery runtime, sandbox o scrittura business eseguiti. SAP custom BTP escluso.

La ricerca originale è conservata temporaneamente in scratch `giobby-discovery-20261021/evidence-it.md` e `retrieval-manifest.json`; non dipendere da quei file effimeri per build/test. Questa sintesi e gli identificativi di fonte sono l'evidenza pubblicata; il raw Swagger non è vendorizzato. L'hash identifica i byte acquisiti, non garantisce immutabilità futura dell'URL.

| Fonte ufficiale | Asset acquisito | SHA-256 |
| --- | --- | --- |
| [1] Home | 3321 byte, HTTP 200 | `a7b0e7d1abe0b41acbca964b276418b263246618ce962905bcbc08f64df63000` |
| [2] Guida | 11094 byte, HTTP 200 | `66acacdab80e916233eb1bea3a304bd0e8a89625036ba2755c99820ec34580e4` |
| [3] Explorer | 4053 byte, HTTP 200 | `013c66a5849c1ea5bd6b5e0e8934cf413fe68c9a54d152937895aa5ad2e6da8d` |
| [4] Script explorer | 2298 byte, HTTP 200 | `45488e196185547bdf914afe7fd3e7e3f24a5517fd552141ae1e917e709d18e7` |
| [5] Swagger | 476457 byte, HTTP 200 | `0c43f06fa1481fa39d5e0a63f61c5843ded5b82335e68bcb840dc974e13574a3` |
| [6] Reference | 70335 byte, HTTP 200 | `f81a2f67f6a302ab41dbba959c85097cb7e0032405b1d6fb64a4839aa13ed7aa` |

## Specifica osservata, non contratto live completo

[5] è **Swagger 2.0**, titolo Giobby API, `info.version=1.0`: 271 path, 431 operazioni, 91 definizioni, nessun riferimento interno mancante. Non è OpenAPI 3; `00554` non prova versione semantica supportata. Mancano `host`, `basePath`, `schemes`, `securityDefinitions`, `security`. Tutte le operazioni espongono solo risposta `default` descrittiva: **zero schemi di risposta**, nessuna tassonomia HTTP/errori formalizzata. Un client generato non colma envelope, ID creati e semantica dei risultati mancanti.

Lo script [4] rimanda a `../swagger/swagger.json`; risolto rispetto all'explorer diventa `/swagger/swagger.json`, HTTP 404 nella raccolta. Il percorso [5] funziona. [7] contiene uno script di discovery con `cid=TEST`: HTML letto, servizio non chiamato; non è prova di sandbox autorizzata.

## Autenticazione ed endpoint

[1–2] distinguono api-client (accesso per conto degli utenti autorizzanti) e api-server (account proprio). Nessuna modalità scelta. La guida descrive authorization code/refresh nel realm `api-client`; per `api-server` un esempio password grant con `client_id`, `username`, `cid`, `password`. Non prova `client_credentials` né raccomanda tale flow per Enginia360.

Dopo login [2] prescrive discovery `GET https://app.giobby.com/GiobbyApiLogin/v1/endpoint?idCompany={idCompany}` e recupero di `GiobbyApiURL` **a ogni login**. Non fissare il percorso GiobbyApi00554 come endpoint account. Le richieste business usano Bearer, `Accept: application/json`, `X-Giobby-Realm` coerente. La guida mostra un envelope di discovery ma non definisce gli envelope business della specifica.

Requisiti Enginia360 da verificare prima di un adapter: flow approvato, PKCE/state/nonce ove pertinenti, custodia/revoca/refresh token, autorizzazione della società; decodificare JWT non prova un contesto affidabile. Validare HTTPS/origine dell'endpoint dinamico prima di inoltrare token. Questi sono requisiti/proposte tecniche, non garanzie del provider.

## Matrice documentale candidata [5–6]

Path relativi a `GiobbyApiURL`; comportamento e permessi su account non verificati.

| Dato/processo | Superficie osservata | Gap e confine |
| --- | --- | --- |
| Controparti | `/contacts`, `/customers`, `/vendors`; ContactApi, CustomerApi | Contatto e codice ruolo cliente non equivalenti; ContactApi non dichiara `id` citato nella prosa POST. Nessuna unicità fiscale provata. Visibilità Giobby non è isolamento tenant. |
| Destinazioni | `/contacts/{idcontact}/offices`; ContactOfficeApi; campi destinazione DocumentApi | Legame office/deliveryAddress, identità restituita e privacy societaria da chiarire. |
| Articoli/prestazioni | `/products`, `/products/product`, varianti; ProductApi | Reference distingue `kindOf` 1 prodotto/2 servizio, non `idType`. Nucleo comune e prezzi/stock societari non vanno fusi. |
| Prezzi | `/pricelists`, schemi; ProductApi prezzi | Filtro esatto `validOnDateMillins`; risposta righe non tipizzata. PriceChange non è contratto di quella risposta. Composizione prezzi/sconti da confermare. |
| Stock | `/stocks/avaibility`, `/stocks/avaibility/report`, POST/PUT `/stocks`; StockApi; `/storages`, `/storageLocations` | Preservare grafia `avaibility`. Disponibilità considera impegni, ma risposta/detailLevel non sufficientemente descritti; nessuna prenotazione atomica identificata. Scrittura stock non equivale a prenotazione officina. |
| Ordine cliente | `/sales/orders`, `/sales/{id}/orders`; DocumentApi, `simulation` | Non equivale a commessa. Prosa PUT usa `idPos`, assente in DocumentRowApi. Simulation non prova assenza totale di effetti. |
| Amministrazione | `/sales/invoices`, `/sales/{id}/invoices`, trasformazioni `orderstoinvoice`; separato `/sales/invoices/{idDoc}/einvoice` | Non trovato comando generico richiesta amministrativa con ack asincrono. Creare/trasformare documento richiede significato business approvato, non autorizza emissione/SdI. |

DocumentApi richiede `docDate`, `idBu`, `idContact`, `idNumerator`, `payments`, `rows`, ma la prosa dice payments opzionale. DocumentRowApi richiede `idMaterial` mentre la prosa consente null. `docDate` string/date-time con esempio epoch-millisecondi; trasformazioni dichiarano millisecondi. La reference elenca `ORDER_CONFIRMED`, il filtro ordini `ORDER_TO_BE_CONFIRMED`. Non normalizzare o correggere silenziosamente queste discrepanze.

Numeri esterni spesso number/double: verificare precisione, scala e arrotondamento senza propagare double al dominio. Document types osservati (ordine 3, fattura 10, stock 109) non sono regole fiscali approvate.

## Affidabilità: lacune esplicite

- Liste con limit/offset, ma nessun massimo/default, ordine stabile, snapshot/cursore/totale formalizzato trovato. Fields solo dove dichiarato.
- Prodotti: createDateMillis/modifyDateMillis inclusivi, combinati OR; ordini: `gtModifyDateMillins`; fatture senza equivalente modifica osservato. Nessun delta/deletion feed generale provato.
- **Idempotenza ignota:** nessun contratto trovato per chiave idempotente, deduplica, retry/exactly-once o lookup univoco per chiave esterna. DocumentApi.reference è stringa, senza unicità o filtro dedicato provati. GET per ID noto non risolve un timeout POST prima della ricezione ID. Conservare esito incerto, niente reinvio automatico cieco.
- Quote, rate limit, 429/Retry-After e backoff non documentati nei materiali letti: non significa assenza di limiti.
- Nessun webhook outbound generale identificato; `/tilby/sales` riceve vendite Tilby, non dimostra feed eventi Giobby.

## Gate R05 e prossima prova finita

D76 autorizza configurazione unilaterale per società/dominio; D26/D65 impongono unica autorità tenant-wide per il nucleo comune. Non richiedere una nuova approvazione di tali invarianti. Al setup prima degli effetti dipendenti scegliere profilo concreto, società/CID e mapping; prezzi/stock/estensioni separati. Definire con il proprietario il documento amministrativo minimo e il suo ack business, senza dedurlo dai nomi API.

Provider: ottenere versione supportata/deprecazione, risposte/errori/ID e required effettivi; flow/security profile e accesso società; idempotenza e lookup dopo timeout, retention/concorrenza; office/merge/cancellazioni/privacy; pagine/delta/quote/webhook; effetti stock/prenotazioni; precisioni e distinzione bozza/conferma/emissione/SdI/simulation.

R05.b resta adapter anti-corruption offline con fixture **esplicitamente sintetiche**, non risposta inventata come compatibilità live. Test-first: endpoint dinamico e realm, isolamento, date/decimal, incoerenze rifiutate, pagine duplicate/vuote, 401/429/5xx e timeout sintetici, esito incerto persistito senza riscritture cieche. Nessun provider-specific field nel dominio. R05.a non è completata dalla sola discovery pubblica; R05 dipende dall'integrazione R04, mentre ricerca preparatoria può procedere prima. Credenziali, sandbox e traffico account richiedono separato scope sicuro. Nessun go-live o validazione fiscale generale.

## Fonti ufficiali

1. https://app.giobby.com/GiobbyApi00554/
2. https://app.giobby.com/GiobbyApi00554/documentation.html
3. https://app.giobby.com/GiobbyApi00554/apiexplorer.html
4. https://app.giobby.com/GiobbyApi00554/js/swagger-login.js
5. https://app.giobby.com/GiobbyApi00554/swagger/swagger.json
6. https://app.giobby.com/GiobbyApi00554/reference.html
7. https://www.giobby.com/apidoc/
