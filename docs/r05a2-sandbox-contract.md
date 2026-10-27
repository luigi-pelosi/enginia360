# R05.a.2 — Giobby sandbox: letture osservate, scritture fermate dal gate outbound

**Esito finito: OBSERVED_READS_WRITE_SAFETY_BLOCKED.** Refs #92 / #45 / #44. Il 27 ottobre 2026 accesso API e UI autenticato al solo sandbox autorizzato realmente esercitato. **Nessun adapter**, reader/proiezione applicativa, writer stock, setup ERP, deployment o readiness consegnati. R04/R05 restano aperti. La [matrice sanitizzata](r05a2-evidence.json) contiene 14 osservazioni HTTP con UTC/hash/pointer/tipi, non payload provider inventati.

## D83: nuova autorizzazione limitata, storia preservata

Il proprietario autorizza pieno accesso al sandbox indicato, incluse scritture sintetiche condizionate alla sicurezza outbound, e indica SdI disabilitato. La correzione più recente sceglie esplicitamente `https://auth.giobby.com/auth/realms/api-server/protocol/openid-connect/token` e `X-Giobby-Realm: api-server`, superando la precedente indicazione api-client **soltanto per questo sandbox**. Client/account/CID rimangono privati e configurabili, mai literal applicativi. Registro D1–D82 verificato prima di assegnare D83; nessuna decisione storica riscritta.

Non sono autorizzati produzione, migrazione reale, acquisti, identità reali nuove, contatto provider, invio esterno, deployment, nuovo ambiente persistente o configurazione globale Hermes. D82 resta: stock e acquisti nello stesso ERP autorevole; **3 ordinati / 2 ricevuti** già approvato non è ricevimento locale sostitutivo. D26/D65 e D76 invariati. Il charset di una correlazione non la trasforma in identità o idempotency key provider.

## Accesso effettivo e minimizzazione

La sessione protetta iniziale non era presente (browser blank). Bootstrap nuovo via vault, password-grant con endpoint api-server esatto: HTTP200; issuer e client autorizzato verificati esclusivamente in memoria. Discovery ufficiale `/GiobbyApiLogin/v1/endpoint?idCompany={jwtCompany}`: HTTP200, responseCode200/errorCode0, endpoint restituito `https://app.giobby.com/GiobbyApi00554/v1`. `/loggeduser`: HTTP200, CID uguale al contesto owner privato e idCompany uguale al JWT. Permessi Product_View, SalesOrder_Change, CustomerInvoice_Change, PurchaseOrder_Change, GoodReceipt_Change tutti true osservati; non prova least-privilege o isolamento verso altre società.

Token/discovery iniziali hanno solo metadati protetti dell'esecuzione, **hash dei byte non conservato**: non ne viene inventato uno. Il successivo `/loggeduser` ha hash/UTC nella matrice. L'assenza di hash token non viene compensata serializzando segreti. Redirect negati, CA verificata e timeout30s; password, token e parametri privati soltanto RAM, mai CLI/env/file/log. Il browser si è poi resettato a blank: il tentativo ulteriore di discovery non è partito (`None` prima della costruzione della richiesta); nessun altro login o mutazione per riparare il browser. Errori di trasporto/setup non sono RED comportamentali né fallimenti password.

Nessun corpo business grezzo conservato. Gli SHA256 sono dei byte originali letti in RAM; `shape_sha256` è separato e copre la rappresentazione canonica pointer→tipo. SHA senza byte preservati non permette ricalcolo forense futuro della risposta: consente solo correlazione d'acquisizione, non autenticità/versione provider. La matrice contiene nomi campo/tipi e codici envelope, non nomi/indirizzi/numeri documenti o valori account. Scratch privato `R05a2-private` 0700, file0600: osservazioni sanitizzate, safety, ledger vuoto e asset Swagger pubblico. Nessuno screenshot o header Authorization acquisito.

## Superficie realmente letta

Swagger ufficiale riacquisito: SHA256 `0c43f06fa1481fa39d5e0a63f61c5843ded5b82335e68bcb840dc974e13574a3`, uguale a R05.a.1; nessuna nuova garanzia provider su schemi risposta. Request dichiarate e reference restano [R05.a.1](r05a1-giobby-read-contract.md), non schema response inferito dal modello POST.

| GET relativo | Limite effettivo | Osservazione sandbox, non garanzia |
| --- | --- | --- |
| `/loggeduser` | Oggetto singolo | Oggetto plain: `/cid` string, `/idCompany` integer, permessi boolean; nessun `/responseCode`. |
| `/storages`, `/storageLocations`, `/um`, `/products`, `/stocks/avaibility` | `limit=1&offset=0`, una sola pagina | HTTP200 + responseCode200/errorCode0; array rispettivamente storages/storageLocations/ums/products/stocks, un elemento ciascuno. `avaibility` preservato. |
| `/purchases/orders`, `/purchases/goodsreceipt` | `limit=1&offset=0`, una sola pagina | HTTP200 + responseCode200/errorCode0; `/documentsHeaders` array con un elemento, `/metadata` oggetto. Nessun export account o scansione pagine. |
| `/purchases/{id}/orders`, `/purchases/{id}/goodsreceipt` | Un ID noto dalla rispettiva lista, `onlyHeaderData=false` | `/document/id` integer, `/document/rows` array; primo `/idPos` integer. La prima riga ordine ha quantity e idMaterial **null**; la prima ricevimento quantity number e idMaterial string. Non convertirli in zero/non-null. |
| `/settings` | Una sola richiesta, nessun parametro limit dichiarato | 16 settings osservate, chiavi/valori privati scartati; nessuna categoria outbound individuata. Non è prova di disabilitazione. |
| `/businessunit` | `limit=1&offset=0` | Unità reale nota solo in RAM per leggere lo stato plugin; nessun valore business copiato. |
| `/plugins/archivium/{idBu}/settings` | Una sola BU nota, nessun ID inventato | `/archSettings/archIdAzienda` null, tre agreement flags false; nessun flag autorevole “tutti gli invii SdI disabilitati”. |

`field_types` ricorre **solo sul primo elemento di ogni array**. Un tipo osservato non stabilisce requiredness, tutti i valori ammessi, nullabilità supportata, stabilità ID, paginazione completa o consistenza. Le detail possono contenere più righe: nessun array completo è stato esportato su disco. Valori docStatus esistenti non conservati: HTTP/envelope positivo non diventa conferma business o collegamento ordine-ricevimento.

Stock restituisce nomi/tipi nella matrice: semantica fisico/impegnato/disponibile non provata; nessuna somma dedotta da etichette. Identità riga idPos osservata non prova namespace/stabilità né provenance acquisto→ricevimento. Nessuna correlazione tra documenti esistenti, nessuna mutazione cliente reale. Null/number sono osservazioni diverse, non versioni di schema alternative garantite.

## Gate outbound: NOT_ESTABLISHED

UI autenticata realmente aperta, navigazione read-only Impostazioni → Fatturazione Elettronica e Mail Aziendale. Nessun Save/Modifica/Attiva/Invia premuto. La pagina elettronica espone elementi di attivazione/configurazione; la pagina mail presenta etichette SMTP/invio documenti/account. Non sono stati trovati controlli visibili che attestino un divieto globale di invio automatico. Nessun indirizzo o valore personale conservato; email esistenti non lette tramite `/emails`.

API `/settings` non ha rivelato categorie SdI/email/webhook/export/automazione; API Archivium per una BU mostra registrazione null e tre flag accordo false. **Assenza di una chiave o registrazione non equivale a blocco invio** e non copre altri plugin, hook o export. SdI disabilitato resta **affermazione owner**, corroborazione parziale del solo stato Archivium, non garanzia indipendente di assenza di ogni percorso fiscale.

**Fatto di sicurezza mancante preciso:** una impostazione osservabile autorevole e comprensiva, oppure una garanzia documentata per la specifica creazione API, che escluda email/webhook/export e consegna a sistemi finanziari all'inserimento di ordine/ricevimento/fattura. API e UI esaminate non lo stabiliscono. Non si cambia configurazione globale, non si usa un destinatario reale e non si crea un documento per scoprire se parte un invio.

## Scenari condizionati: bloccati prima della prima scrittura

Ledger privato predisposto con prefisso `E360-SB-R05A2-20261027`: **zero scritture e zero oggetti** creati/modificati. Nessun tentativo economico ambiguo, replay, numerazione, cleanup o cancellazione. La matrice enumera quattro scenari bloccati:

1. Ordine fornitore sintetico3 → ricevimento collegato2: sicurezza outbound non stabilita; quantità/provenienza/residuo/destinazione/stock before-after non provati.
2. Righe duplicate SKU: stesso blocco, non ampliare con documenti esistenti.
3. **D79 bozza di fattura vendita persistente:** non provata, né smentita. Non invocato POST invoice, non sostituito con offerta/ordine/proforma, nessuna osservazione di numerazione definitiva o effetti stock. Grant API non prova bozza.
4. Risposta persa/recovery/dedupe: nessun lookup univoco di oggetto proprio dimostrato, dunque nessuna simulazione o reinvio. GET con ID già noto non recupera l'ID perso; nessuna idempotency header inventata.

Non serve riapprovare D82 o parzialità. Per il prossimo incremento basta acquisire il fatto safety mancante entro lo stesso sandbox, quindi predisporre ledger prima di ciascuna scrittura e provare lookup recuperabile prima di perdere una risposta. Qualsiasi nuovo oggetto deve essere proprio, inconfondibile e senza recapiti reali; storia fiscale/stock non reversibile per presunzione. Nessun contatto provider effettuato; la bozza R05.a.1 resta NON inviata.

## Offline, CI e rollback

`python3 -I scripts/test-r05a2-evidence.py` è un **guard documentale eseguibile**, non parser di risposte provider né adapter. Controlla le forme effettivamente osservate (plain user versus envelope, documentsHeaders versus document, idPos e quantity null/number), provenienza/cap/classi e blocchi; muta copie della matrice e invoca realmente la CLI per rifiutare promozioni false, campo raw body e ledger non vuoto. Nessuna fixture positiva provider o raw risposta esistente viene generata. Non esiste un positive parser business verificabile senza catture proprie minimizzate: non lo si fabbrica.

Test-first documentale: `03-dossier-RED.log`, cinque assertion mancanti sulla matrice prima dei documenti; non RED runtime. Impact `01-impact-RED.log`: selezione offline assente e wiring mancante prima della modifica; errori aggiuntivi su executable unmapped distinti. `02-impact-GREEN.log`: tre test selettore passati. Successivi risultati effettivi nei log/PR, non anticipati.

La selezione finita aggiunge `affected-r05a2-offline`; registro/piano e relativi guard richiedono anche `affected-r06-offline`. Solo docs/offline: nessun dispatch runtime/Docker, build applicativa, nuova dipendenza o deploy. Runtime saltato non è pass. R05.a.1 conserva prove statiche storiche; D83 non riscrive D1–D82. Rollback solo PR tracciata di documenti/test/wiring; nessun rollback di documenti ERP necessario perché non creati. Bootstrap/Tailscale/volumi/backups/branch R00 non toccati.
