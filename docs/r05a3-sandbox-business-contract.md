# R05.a.3 — Prove business reali nel sandbox Giobby

**Esito: OBSERVED_BUSINESS_WITH_PRECISE_BLOCKERS.** Refs #94 / #45 / #44. Il 27 ottobre 2026 sono stati persistiti **6 aggregati business propri e 2 contatti impliciti = 8 oggetti verificati**, non dati dimostrativi inventati come risposte provider. Ordine3 → ricevimento collegato2 realmente eseguito **via trasformazione UI**, con readback API e distinzione delle due righe dello stesso SKU. Vera bozza D79 e recovery di una creazione riuscita restano **non provati**. Nessun adapter/proiezione/runtime/setup Enginia360; R04/R05/readiness non completati.

## D84: gate outbound risolto dall'owner, non verifica tecnica universale

Il registro completo D1–D83 è stato controllato prima di assegnare il successivo D84. Fonte diretta owner, **27 ottobre 2026**, citazione esatta:

> Confermo che la sandbox è scollegata da altri sistemi automatici, webhook ed esportazioni.

Evidenza **owner-assertion** accettata per il sandbox già autorizzato D83; SdI disabilitato resta separata affermazione owner. Il gate prima NOT_ESTABLISHED è ora **RESOLVED_BY_OWNER_ASSERTION**, senza pretendere una prova indipendente di assenza universale di egress. Nessuna nuova domanda di permesso per le scritture sintetiche o per 3/2. Non autorizza produzione, invio esterno, modifica globale di email/numeratori/integrazioni, acquisti reali, provider contact, deployment, migrazione o nuovo ambiente persistente. D82 resta stesso ERP autorevole per stock/acquisti: nessun writer/fallback locale.

R05.a.2 e la sua matrice zero-write rimangono **snapshot storici invariati**; D1–D83 cronologici non riscritti. Gli hash di controllo sono nella [matrice corrente](r05a3-evidence.json).

## Accesso, intent ledger e minimizzazione

Bootstrap protetto nuovo via vault; token endpoint api-server corretto, TLS verificato e redirect negati. HTTP200, issuer/client verificati in RAM, discovery dinamica nuova e `/loggeduser` legato al CID autorizzato. JWT company string e user company integer confrontati per valore testuale; il primo assertion mismatch di tipo non era un fallimento password. Hash originali auth/discovery non conservati: nessun hash inventato o token serializzato. Due successivi bootstrap autentici sono avvenuti prima delle rispettive operazioni, senza retry cieco di scritture.

Directory privata0700, ledger/catture0600 predisposti **prima della prima POST**. Prefisso univoco `E360-SB-R05A3-20261027T102351Z`; soltanto controparti/prodotto/documenti nuovi propri. Nessuna email/PEC, indirizzo, identità fiscale o coordinata pagamento reale; non sono stati nemmeno necessari destinatari example.invalid. Unità/IVA/magazzino/numeratore preesistenti solo riferimenti read-only. Nessun oggetto preesistente modificato. Rate limit client300ms e timeout30s; una pagina, reference limit1, lookup propri limit5/offset0; nessun export/scansione account.

33 richieste API business osservate, incluse 6 GET di riferimento necessarie e 6 tentativi POST. Due intent UI: prodotto distinto e ricevimento; quest'ultimo ha avuto un rifiuto di validazione prima del salvataggio. **8 intent totali**, dei quali6 verificati,1 errore prodotto senza replay e1 percorso UNCERTAIN. Le catture originali necessarie e gli ID remoti rimangono privati; nessuna credenziale a CI. La matrice espone UTC, endpoint templati, HTTP/business status e hash source/shape distinti. Source-shape completo resta privato; gli hash non costituiscono firma/versione provider. Le fixture sono proiezioni allowlist di sole risposte proprie con alias coerenti, non risposte fabbricate: numeri di documento anonimizzati ma non svuotati, identità int e righe/numeri/null/status conservati.

## 3 ordinati / 2 ricevuti, stesso SKU e magazzino

1. Fornitore e cliente creati con contatti nuovi; readback esatto e filtro `name` documentato. La richiesta visibilityType ONLY_FOR_ME viene restituita ALL: osservazione sandbox, non promessa privacy.
2. POST prodotto documentata: HTTP500/error2401003, dettaglio dell'ID richiesto404. Causa non risolta; **nessun replay** dedotto dal404. Prodotto **distinto** creato nel legittimo form UI, readback API positivo e stockEnabled true; nessuna giacenza iniziale creata.
3. `POST /purchases/orders?simulation=false`: due righe stesso prodotto con quantità1 e2 (totale3), idPos1 e2. Readback CREATED/Creato, numero assegnato. docStatus in input ignorato con warning. La stessa correlazione nelle note/reference permette successivamente lista freeText limit5 con un solo ordine proprio.
4. Il modello ufficiale `GenerateGoodReceiptIssueApi` della trasformazione `/purchases/{id}/orderstogoodsreceipt` pubblica solo header: **nessuna selezione riga/quantità**. Non invocato per creare3 e poi fingere ricevimento2. Nessun purchase-source field inventato.
5. Dal link dell'ordine proprio osservato si apre `GoodsReceiptIssue.xhtml?DOCS_ID_IMPORT={ownedOrder}&ftrID=g_receipt_n&IDDOCTYPE_IMP=2`. Si rimuove soltanto la riga importata **non ancora persistita** qty1, conservando la seconda qty2 e il riferimento origine. Il primo save rifiuta numero documento oltre20 caratteri; corretto al numero sintetico corto, prefisso completo nelle note, poi un solo ricevimento persistito. Nessuna cancellazione di storico stock/fiscale.
6. API dettaglio ricevimento: riga nota idPos1/idPosType5/idMaterial null; riga materiale idPos3/qty2 al magazzino scelto. Ordine riletto **GOOD_PARTIAL_RECEIVED**: riga originale1 resta CREATED, riga originale2 diventa GOOD_RECEIVED. Questo, il percorso reale di import e il residuo ordinato1 distinguono la provenienza anche con SKU duplicato; non è un ricevimento scollegato.

| Fase | quantity (fisico nel report esercitato) | availableQty | orderedToSuppliersQty | stockForecastQty |
|---|---:|---:|---:|---:|
| Dopo ordine / prima ricevimento | 0 | 0 | 3 | 3 |
| Dopo ricevimento2 | 2 | 2 | 1 | 3 |
| Dopo fattura1 | 1 | 1 | 1 | 2 |

Prima dell'ordine `/stocks/avaibility` restituisce array vuoto: **non convertito in zero**. I valori numerici zero sono osservati nel report successivo all'ordine. `reservedByOrdersQty` è0 nelle tre letture report. Destinazione header del ricevimento `-1`, ma riga stock al magazzino selezionato: non confondere i due campi.

**Limite API preciso:** nella detail le proprietà `saleorderref`, `saleorderposref`, `materialmovementref`, `materialmovementposref` sono realmente **null**, anche dopo la trasformazione UI collegata. Non si ricostruisce un grafo provider inventando valori da descrizione o SKU. Prova quantitativa/UI positiva, ma campo API esplicito di provenienza acquisto/riga e trasformazione parziale direttamente API non stabiliti. Quantità ricevuta2 e residuo1 risultano da riga ricevuta/stato riga ordine/report, non da inesistenti campi receivedQty/residualQty.

## D79: fattura vendita reale persistente, non prova di vera bozza pending

`POST /sales/invoices?simulation=false`, tipo10 ufficiale, contro cliente proprio e prodotto proprio qty1, dopo il carico2. HTTP200/error0 con idDocument; dettaglio esatto e lista freeText ritrovano la fattura. Numero non vuoto assegnato, docStatus **CREATED**, descrizione **Creato**, eidocstatus stringa vuota. Il provider avverte che docStatus passato è ignorato. La UI propria mostra Salva/Stampa/Invia e nessuna etichetta bozza osservata; nessuna azione Invia/Genera/Emetti premuta.

Lo stock del solo prodotto proprio passa2→1. Quindi **la chiamata esercitata persiste una fattura numerata con effetto stock**, non offre evidenza della bozza pending senza quegli effetti desiderata D79. Non è stata sostituita con proforma, offerta o ordine. Né CREATED né numero/non-invio dimostrano, da soli, definitività fiscale: **nessuna conclusione fiscale generale**. Non si conclude che ogni variante API possa soltanto registrare; resta da stabilire un percorso supportato di vera bozza, se esiste.

## Recovery prima del replay: lookup positivo, perdita tentata, errore reale

Prima della perdita, `GET /vendors?name={ownedName}&limit=5&offset=0` trova esattamente il nuovo fornitore proprio: totalCount1, nome esatto e ID confrontato col dettaglio. Analogo lookup cliente1. Questo è lookup indipendente dall'ID server, non GETbyknownID spacciata per recovery.

Una **sola** ulteriore POST fornitore con nome proprio distinto è inviata con risposta scartata al confine client, conservando oracle separato privato. Recovery usa soltanto nome: lista fornitori0; ricerca contatti fullName0. Solo dopo il lookup si esamina l'oracle: **HTTP500/error2121003**, errore interno provider, nessun ID ritornato. Il test non ha quindi prodotto una creazione riuscita con risposta persa da recuperare. **UNCERTAIN hold, zero replay**: lista vuota ed errore500 non autorizzano resubmission e non provano assenza di effetti. Non esteso il test con altre creazioni per mascherare il blocco; gli altri scenari indipendenti sono proseguiti. Nessuna idempotency header inventata o single-effect/replay proof dichiarata.

## Verifiche offline, CI e confini

Sette proiezioni di catture proprie parsabili in `tests/fixtures/r05a3-owned-captures.json`; decoder limitato offline in `scripts/r05a3_captures.py`. Nessuna normalizzazione di null o deduzione di draft/ack. Il test-first di selezione mostra assertion mancanti prima del mapping; executable non mappati sono errori separati. Il decoder parte dal solo json.loads: RED reali **ValueError not raised** per refusal, string/bool/NaN/Infinity quantity, ID riga duplicato e shape non supportata; poi validazione minima GREEN. Conservazione righe/null e sequenza stock sono regressioni di catture, non prove live aggiuntive. Le mutation documentali proteggono owner-assertion, cronologia e divieto di promozioni false. Log `r05a3-logs`, esiti exact-head e run reali nella PR dopo esecuzione.

Selezione finita docs/offline: impact, affected-r05a3-offline, affected-r05a2-offline per il suo bound cronologico e affected-r06-offline per registro/piano. Unknown executable fail-closed e mixed security/runtime preservati. Nessuna dipendenza nuova, install, Docker, dispatch runtime/full architecture, migrazione o build applicativa richiesta dal diff; runtime skip non è pass. Nessun hash bootstrap ricostruito; bootstrap/Tailscale/25 volumi/backups/branch R00 non toccati. RAM API non presente all'ultimo controllo; nessuna sessione/credenziale persistita per il seguito.

Rollback: PR tracciata dei soli documenti/test/wiring. **Non cancellare gli oggetti ERP propri né la storia fiscale/stock** come rollback software; ledger privato mantiene provenienza e hold. Rimangono D79 vera bozza, recovery positivo di lost-success, contratto API di provenienza/partial transform e garanzie provider/integrazione operativa. Nessun completamento parent o go-live implicito.
