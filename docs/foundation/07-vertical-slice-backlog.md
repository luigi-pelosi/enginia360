# Dossier di fondazione — 07. Backlog della prima vertical slice

## Stato corrente consolidato — D70–D73

B01–B08 consegnati; B08 main `67bec45f116c85658098ce62232aafccd365ce10` (PR #29, CI main 39395112487 success). D70 autorizza B08–B14 in sequenza autonoma, un solo WIP. B09 In corso: D73 — ogni rientro carcassa copre esattamente tutto il residuo con un unico comando (su 2 installati, 2); parziali/eccedenti rifiutati integralmente; gate di chiusura tecnica bloccato finché il residuo è maggiore di zero. Inventory possiede il rientro fuori giacenza nell'ubicazione dedicata D38, Officina il requisito fotografato sull'installazione e il gate; nessuna transazione globale. Report [B09](../b09-verification.md). B10–B14 restano Backlog. Nessuna policy fiscale, di costo, smaltimento o proprietà della carcassa dedotta.

Accettazione automatica isolata effimera, nessun nuovo ambiente manuale persistente, nessuna review LLM o approvazione manuale di routine. Bootstrap 443, segreti, volumi e backup conservati invariati. Le descrizioni successive di stato/autorizzazione precedente sono **storiche e superate da questo riepilogo e D70–D73**; i requisiti di dominio restano validi. Prove/CI/completamento non sono dedotti dall'autorizzazione.


**Aggiornamento consegna B06:** il proprietario ha accettato la prova privata («Funziona. Procediamo») e autorizzato commit/push/PR/CI/merge della sola B06. Review indipendenti core/lifecycle e cinque artefatti manuali PASS; riesecuzioni finali nel [report B06](../b06-verification.md). G02/B06 soddisfatto nel solo perimetro D69; completamento remoto subordinato agli esiti reali della PR e issue #12. B07–B14 restano non autorizzati, aperti/blocked/Backlog; nessun avanzamento downstream. Le precedenti indicazioni di review/accettazione pendenti sono storiche.

**Stato corrente D69 — 19 ottobre 2026:** il proprietario approva esplicitamente l’opzione A: prenotazioni parziali richieste dall’operatore, mai troncamento automatico. B06 privata/sintetica è implementata e verificata localmente; candidata alla review indipendente, non Completata. G02/B06 dispone delle prove tecniche nel [report B06](../b06-verification.md); G02/B07–B09 resta aperto. B07–B14 restano blocked/Backlog e non autorizzati. Nessun commit/push/merge o deployment persistente prima della parent review.

### Stati precedenti — storici, superati dove incompatibili con D69

**Consegna B05 — 19 ottobre 2026:** accettazione manuale positiva del proprietario «Ok funziona tutto. Procediamo»; review core e quattro artefatti manuali acquisite, discrepanza documentale risolta. Autorizzata la sola consegna Git/PR/CI/merge/chiusura B05, non nuovi deploy o B06. Stato al congelamento: In verifica; esito finale remoto nella PR e issue #11. Limiti e perimetro nel report B05. Le indicazioni precedenti di accettazione/review pendenti sono storiche e superate da questa registrazione. B06–B14 restano bloccati/Backlog e non autorizzati.

**Aggiornamento D67:** estensione a valori variabili implementata localmente; quantità/prezzo 6, sconto 2 (0–100), netto di ciascuna riga HALF_UP6 → base gruppo → imposta gruppo HALF_UP6 → somma totale. Conferme del proprietario acquisite; G01/D46 risolto per queste politiche numeriche, non certificazione fiscale generale. Stato B05 **In corso**, non completata: review indipendente e accettazione manuale ancora necessarie. Evidenze correnti nel report B05; le descrizioni del precedente runtime limitato al caso 001 sotto sono storiche. B06–B14 restano bloccati/Backlog.

**Stato corrente:** B01–B04 completati; baseline B04 `0f9cc50fcf685d2e8ffab2686947124fb3189293`. D64–D67 autorizzano soltanto B05 sintetica/privata; catalogo e politiche numeriche risolti. B05 **In corso**, locale non committata: report con prove API/UI/HTTP/PostgreSQL, review indipendente e accettazione manuale pendenti. Nessuna CI B05 remota né consegna persistente. B06–B14 restano Backlog/bloccati e non autorizzati.
**Fonti:** `PROJECT_CHARTER.md` §11–14; [slice](04-first-vertical-slice.md), [architettura](05-solution-and-module-boundaries.md), [minacce](06-initial-threat-model.md). Le decisioni acquisite restano nel [registro](01-glossary-and-domain-boundaries.md).

## 1. Metodo proposto

Ogni voce B00–B14 è pubblicata come issue con risultato, perimetro escluso, dipendenze, criteri di accettazione e prove. Gli ID Bxx sono identificativi del dossier, non numeri di issue GitHub. Nessuna stima di durata o data di consegna è promessa.

Flusso Kanban proposto: **Backlog → Pronto → In corso → In verifica → Completato**. Un solo incremento implementativo in corso; analisi e verifiche indipendenti possono procedere senza avviare altre funzionalità. Le dipendenze non trasformano ogni singola voce in un servizio o modulo.

- **Pronto:** requisiti sufficienti, dipendenze completate, decisioni necessarie risolte e autorizzazione nell'ambito approvato.
- **In verifica:** codice e prove disponibili, review/CI o validazione ancora in corso.
- **Completato:** risultato esercitato, criteri superati e limiti dichiarati; non basta compilare o creare una PR.
- **Bloccato:** indicatore trasversale con motivo e decisione richiesta, non una colonna in cui perdere l'ordine del lavoro.

Non trasferire automaticamente tutte le voci in Pronto dopo l'approvazione del backlog. L'approvazione dell'ordine non approva il dossier completo, il provider di identità o le regole fiscali.

## 2. Sequenza e dipendenze

| ID | Risultato dimostrabile | Dipende da | Natura |
| --- | --- | --- | --- |
| B00 | Dossier revisionato e gate di avvio esplicito | — | Decisione/documentazione |
| B01 | Prova identity e ambiente protetto di test | B00 | Abilitatore tecnico con prova concreta |
| B02 | Entrare solo nel contesto organizzativo autorizzato, persistito | B01 | Incremento attraversabile UI/API/database |
| B03 | Usare una controparte comune con destinazioni societarie protette | B02 | Incremento anagrafiche/accessi |
| B04 | Aprire direttamente una commessa nel tipo societario consentito | B03 | Incremento documento commerciale |
| B05 | Aggiungere e valorizzare prestazione e ricambio | B04 | Incremento economico dimostrativo |
| B06 | Prenotare il ricambio senza consumo fisico | B05 | Incremento magazzino |
| B07 | Prelevare e preparare il ricambio senza dichiararlo installato | B06 | Incremento logistico |
| B08 | Registrare installazione e relativo consumo senza doppi effetti | B07 | Incremento officina/magazzino |
| B09 | Ricevere la carcassa secondo la configurazione di esempio | B08 | Incremento di rientro distinto |
| B10 | Consegnare il risultato a un destinatario amministrativo simulato | B09 | Primo percorso esterno completo |
| B11 | Recuperare indisponibilità, timeout incerti e richieste interrotte | B10 | Incremento di continuità e riconciliazione |
| B12 | Produrre e confermare una fattura tecnica interna collegata | B09 | Percorso amministrativo interno |
| B13 | Registrare contabilmente la fattura con scrittura quadrata | B12 | Incremento contabile tecnico |
| B14 | Eseguire e ripristinare lo scenario completo in modo ripetibile | B11, B13 | Chiusura verificabile della slice |

**Ordine confermato da Luigi Pelosi:** percorso esterno simulato prima di quello contabile interno, per dimostrare presto il ciclo operativo e la resilienza senza inventare regole fiscali. B12–B13 possono essere preparati mentre si risolvono le relative validazioni, senza dichiararli Pronto prematuramente. La conferma riguarda la sequenza proposta, non l'approvazione del dossier completo, di ogni dettaglio delle schede o l'autorizzazione all'implementazione.

## 3. Schede degli incrementi

**D39 — Configurazione societaria dimostrativa confermata:** prestazione e ricambio sono collegati alla stessa lavorazione; area di preparazione abilitata per esercitare la separazione fra prelievo e installazione; rientro della carcassa richiesto per il ricambio dell'esempio prima della chiusura tecnica. Sono valori del tipo documento dello scenario di prova, non obblighi universali: restano governati dal customizing societario. La chiusura tecnica di D37 richiede quindi anche tale rientro nel caso dimostrativo. Restano separati permessi, invarianti e regola di non retroattività.

### B00 — Gate di avvio

- **Risultato:** dossier consolidato, approvazioni distinte da proposte, decisioni bloccanti e proprietari registrati; autorizzazione esplicita alla prima implementazione.
- **Accettazione:** sono presenti backlog, domande agli operatori/commercialista, scenari di costo e rischi; le scelte ancora aperte hanno un gate concreto e non sono spacciate per risolte. Allineare AGENTS.md allo scope approvato quando autorizzato, senza reinterpretare i divieti attuali.
- **Prova:** checklist e review del dossier; nessun flag runtime cambiato come sostituto dell'approvazione.
- **Decisione D58:** dossier e B00 approvati dal proprietario; autorizzata esclusivamente B01 nello scope delimitato sotto. L'approvazione non completa né autorizza B02–B14.

### B01 — Identity e ambiente di prova protetto

- **Risultato:** prova comparabile per scegliere il provider di federation/MFA; ambiente ripetibile per dati sintetici, non pubblicato anonimamente sul bootstrap HTTP.
- **Accettazione:** autenticazione, rifiuto accesso anonimo, verifica token/sessione e revoca rilevante dimostrati nella prova; scelta motivata con alternativa e oneri operativi. Nessun provider scelto a priori dal backlog.
- **Candidato confermato D55:** Keycloak community self-hosted per la prova, non adozione definitiva. Confronto documentale con Auth0 nel documento 12; nessuna installazione autorizzata dalla sola candidatura. Restano B00 e scope implementativo esplicito.
- **Scope autorizzato D58:** prova isolata e reversibile con identità/dati sintetici; niente dominio, acquisti, utenti reali, modifica del servizio HTTP pubblico o implementazione di B02–B14. Versioni/digest bloccati, segreti fuori repository, risorse e trasporto protetto verificati nell'ambiente di prova.
- **Prova:** test positivi/negativi e istruzioni ripetibili; vincoli dell'ambiente dichiarati. Non è già il sistema IAM completo.

### B02 — Contesto autorizzato persistito

- **Risultato:** un utente di test sceglie società/sede consentite e accede a una minima risorsa persistita; due tenant di test, più società e scope differenti.
- **Accettazione:** cambi di ID tenant/società/sede/magazzino non ampliano i permessi; contesto visibile e validato nel backend. Capability disabilitata rifiuta l'azione pertinente. Migrazione locale e health della persistenza ripetibili.
- **Prova:** API/UI e test negativi di isolamento, incluso riutilizzo connessioni; prime verifiche di dipendenze/visibilità dei soli moduli introdotti. Minacce T01, T03, T09.
- **Scope autorizzato D59:** due tenant sintetici, più società/sedi/magazzini e scope differenti; Keycloak come baseline iniziale; tenant context e riferimenti autorizzati validati lato backend; PostgreSQL privato con migrazioni ripetibili; UI/API minime. Verificare manipolazione degli ID, capability disabilitata e riuso delle connessioni. Esclusi dati reali, accesso pubblico, provisioning reale e B03–B14.

### B03 — Controparte comune e destinazioni

- **Risultato:** A e B dello stesso tenant usano la stessa identità; B aggiunge una destinazione locale non esposta ad A; pubblicazione comune soltanto esplicita e autorizzata.
- **Accettazione:** altro tenant escluso; edit anagrafica comune negato senza permesso specifico; dati societari restano distinti. Campi del caso minimo confermati in D36: ragione sociale, identificativo fiscale e sede legale comuni; una destinazione operativa societaria riservata salvo condivisione esplicita autorizzata. Non è l’intera anagrafica ERP o una definizione di obblighi fiscali.
- **Prova:** letture/ricerche e modifiche con ruoli differenti; audit dell'azione senza payload sensibili superflui. T01, T02, T04, T11.
- **Autorizzazione D60:** solo B03 sintetica/privata, senza provisioning amministrativo, dati reali, cambi dell'ambiente manuale B02 o B04+. Branch locale `feat/b03-counterparties`; nessun commit/push prima di review indipendente.
- **Gate risolto D61:** permesso specifico di pubblicazione sulla società proprietaria, distinto dall’edit comune; grant limitati a sede/magazzino o ad altra società non bastano. Visibilità soltanto alle società autorizzate dello stesso tenant, mai cross-tenant.

**Accettazione finita B03 (prove locali nel report `../b03-verification.md`; non completata prima della review):**
1. A e B autorizzate nello stesso tenant leggono la stessa identità persistita e i tre campi D36; ricerca e lettura diretta rispettano i permessi di risorsa.
2. B crea una destinazione locale; A non la trova nelle liste/ricerche e non può leggerla o modificarla conoscendone l'ID. Sola appartenenza al tenant o permesso di edit comune non concede automaticamente pubblicazione.
3. Solo l'azione esplicita con autorizzazione specifica di pubblicazione sulla società proprietaria (D61) rende la stessa destinazione comune; tentativi senza scope o con società proprietaria estranea sono rifiutati e non mutano dati.
4. Lettore privo del permesso specifico non modifica i campi comuni; modifiche autorizzate sono visibili ad A/B senza duplicare l'identità. Nessun controllo fiscale o deduplicazione inventato.
5. Altro tenant, ID organizzativi estranei, identità senza membership e riuso di connessioni non ampliano letture o scritture; test applicativi e PostgreSQL RLS negativi distinti.
6. Audit registra solo identificativi tecnici, azione ed esito pertinenti, senza ragione sociale, identificativo fiscale, indirizzi, token o credenziali.
7. Percorso UI italiana/API/PostgreSQL reale, migrazione e rollback documentati, regressioni B02, build/test/audit e Compose isolata esercitati. L'ambiente manuale persistente non cambia; CI remota non dichiarata verificata prima dell'esecuzione remota.

### B04 — Commessa diretta nel tipo societario

- **Autorizzazione D62/D63:** solo B04 sintetica e privata, con gate veicoli risolto; nessun commit/push/merge o deployment persistente prima della review indipendente e preparazione del parent. Ambienti manuali B02/B03 e Tailscale invariati; B05–B14 non autorizzati.
- **Gate risolto D63:** «La lettura, add, edit e remove seguono le stesse regole delle controparti mentre la selezione del veicolo per una commessa di lavorazione può essere effettuata a livello di tenant». Gestione anagrafica e selezione per commessa sono autorizzazioni/usi distinti: proiezione minima di selezione nel tenant verificato, anche tra società, senza ampliare lettura gestionale o accesso ai dati societari riservati. Riferimenti e permessi ricontrollati alla creazione; mai accesso inter-tenant. B03 non ha implementato add/remove dell'identità comune: non introdurre nuove policy di cancellazione o CRUD amministrativo. Fixture sintetiche e selettore minimo bastano al percorso B04.
- **Stato:** implementazione locale B04 e accettazione isolata disponibili; In corso fino alla review indipendente del parent. CI remota e qualunque ambiente manuale B04 non eseguiti. B05–B14 restano Backlog/bloccati.

- **Risultato:** creare una commessa che è già ordine cliente, usando un tipo configurato della società e una sede unica; selezionare un veicolo con intestatario diverso dal soggetto a carico.
- **Accettazione:** nessun preventivo/appuntamento obbligatorio se il tipo consente creazione diretta; singolo soggetto a carico nello scenario. Versione della configurazione rilevante tracciata senza inventare il congelamento universale del documento.
- **Prova:** percorso UI/API persistito, mancata sovrascrittura del pagante alla selezione veicolo, rifiuto riferimenti non autorizzati. T01, T04.
- **Escluso:** editor visuale del workflow, catalogo universale dei tipi e ripartizioni/garanzia.

### B05 — Prestazione, ricambio e valori riproducibili

- **Autorizzazione D64:** solo B05 sintetica e privata; scope positivo/esclusioni nel registro D64. Nessun codice prima del chiarimento sul catalogo; nessun commit/push/merge o deployment persistente prima della review/preparazione del parent. B02/B03/B04 e Tailscale invariati; B06–B14 non autorizzati.
- **Gate catalogo risolto D65:** identità anagrafiche di articoli fisici e prestazioni visibili nel tenant, come regola generale anagrafica. Nessun grant implicito add/edit/remove; prezzi, customizing, stock, estensioni e destinazioni riservate restano separati. D61/D63 invariati; nessuna nuova domanda sulla policy già acquisita.
- **Già acquisito:** soggetto unico D28, default per riga D13 e associazione alla stessa lavorazione D39. Nessuna nuova policy prezzo/pagante da master approvata. G01/D46 risolto da D67 per le politiche numeriche finite; nessuna certificazione fiscale generale o riapertura D42.
- **Stato:** In corso, non Completato; implementazione locale e RED/GREEN applicativo, HTTP/DOM/PostgreSQL e suite tecniche nel report [B05](../b05-verification.md). Review indipendente e accettazione manuale pendenti; issue #11 aperta senza blocked e Project In corso, riletti. Nessuna CI B05 remota o deployment persistente. Baseline `0f9cc50fcf685d2e8ffab2686947124fb3189293`.

- **Risultato:** aggiungere una prestazione e un ricambio; esporre imponibile, imposta e totale di prova con regole esplicite.
- **Accettazione:** default un soggetto a carico per riga, associazione a lavorazione secondo configurazione dimostrativa; nessun doppio conteggio nei raggruppamenti operativi. Decimal/value object e arrotondamenti riproducibili; storico non ricalcolato silenziosamente da cambi anagrafici.
- **Prova:** test su valori limite e arrotondamenti, payload reali UI/API coerenti; caso 001 e relativa politica validati secondo attestazione D42, non validazione fiscale generale. T05, T12.
- **Decisione D32:** risultato minimo = riepilogo commerciale (imponibile al netto degli sconti, imposte e totale a carico). Costi e marginalità, anche provvisoria, rinviati. Questo chiarimento non chiude gli altri prerequisiti di B05 o la validazione fiscale.
- **Caso di riferimento D41:** [001](10-test-case-001.md), imponibile 164.50 / IVA 36.19 / totale 200.69; IVA calcolata sull’imponibile aggregato del raggruppamento, non somma delle imposte arrotondate per riga. Precisioni e ROUND_HALF_UP espliciti nel caso; aritmetica verificata indipendentemente e validazione del referente sul caso attestata dal proprietario in D42. Implementazione locale limitata al caso e prove applicative ora disponibili nel report B05; G01/D46 non soddisfatto dai soli test.

### B06 — Prenotazione

- **Autorizzazione D68/D69:** B06 privata/sintetica In corso; opzione A approvata, gate di parzialità risolto. **D69 — Prenotazione parziale esplicita:** su riga di 3 filtri con 2 disponibili, l’operatore richiede esplicitamente 2: vengono prenotati 2 e resta 1 da prenotare successivamente quando disponibile. Ogni quantità richiesta deve essere positiva, non superiore al residuo non prenotato della riga né alla disponibilità del magazzino autorizzato della sede di testata. Una richiesta di 3 con disponibilità 2 è rifiutata integralmente, senza effetti e senza bloccare la commessa; non viene ridotta a 2. I successivi comandi, anche su magazzini diversi validi, non possono superare cumulativamente la quantità della riga. La giacenza fisica non cambia; disponibilità = fisico − impegni attivi. D69 risolve soltanto la parzialità della prenotazione, non prelievo, consumo, annullamento o rilascio.
- **Risultato:** prenotare il componente per la commessa/lavorazione nel magazzino della sede autorizzata.
- **Accettazione:** disponibilità impegnabile ridotta senza alterazione della quantità fisica; retry non duplica impegno; prenotazioni concorrenti rispettano la disponibilità consentita.
- **Decisione D34:** nello scenario minimo il ricambio può essere inserito anche se indisponibile; prenotazione rifiutata con motivo quando la disponibilità impegnabile è insufficiente. Nessun blocco automatico dell’intera commessa; richieste strutturate in attesa di approvvigionamento rinviate. Nessuna politica universale di stock negativo dedotta.
- **Prova:** test su prenotazioni concorrenti, riferimenti estranei, insufficienza e retry dopo disponibilità del materiale, senza sovraprenotazioni o doppi impegni. T01, T05.

### B07 — Prelievo e preparazione

- **Risultato:** prelevare il componente per la lavorazione; usare l'area di preparazione soltanto se abilitata dal gestore autorizzato nel customizing societario (D33). Collocazione e assegnazione visibili senza dichiarare installazione o consumo.
- **Accettazione:** picking list distinta dall'area fisica; quantità e provenienza riconciliabili; nessun consumo implicito o doppio scarico. Magazzini operativi coerenti con la sede di testata.
- **Prova:** scenario con componente in preparazione e non installato, retry e prelievo concorrente. T01, T05.
- **Decisione D33:** area facoltativa; accettato l'esempio di ubicazione nello stesso magazzino, senza imporlo globalmente. Nessun transito fittizio se disabilitata; prelievo e installazione restano distinti. Ulteriori effetti e politiche di stock da dettagliare; niente magazzino logistico completo per questa sola prova.

### B08 — Installazione e consumo

- **Risultato:** registrare l'installazione tecnica e gli effetti di consumo nel modulo competente; eventuale consegna al tecnico distinta.
- **Accettazione:** il solo ritiro non prova installazione; tentativi ripetuti non duplicano movimenti. Errore tra conferma tecnica ed effetto di stock visibile e recuperabile, senza transazione globale fittizia.
- **Prova:** happy path, retry ed errore intermodulo con recupero; nessun secondo scarico che riconti il movimento di preparazione. T05, T10.

### B09 — Carcassa

- **Risultato:** ricevere il particolare sostituito e riferirlo al componente/intervento pertinenti secondo una politica dimostrativa esplicita del tipo documento.
- **Accettazione:** carcassa e nuovo inutilizzato non confusi; nessun ripristino improprio della disponibilità del nuovo. Vincoli di chiusura derivano dalla configurazione, non da un obbligo universale hardcoded.
- **Identificazione confermata D35:** commessa/lavorazione, riga del ricambio installato, descrizione e quantità della carcassa, data e operatore di ricezione. Nessun catalogo separato o matricola obbligatoria nel caso iniziale.
- **Destinazione D38:** ubicazione dedicata ai particolari sostituiti, separata dai ricambi nuovi e non vendibile nel primo scenario; valorizzazione e smaltimento non introdotti. Non è un vincolo universale.
- **Decisione D73:** ogni rientro copre esattamente tutto il residuo con un unico comando; su 2 installati si rientrano tutti i 2. Parziali, eccedenti o a residuo zero rifiutati integralmente, mai troncati; installazione successiva crea un nuovo residuo. Gate di chiusura tecnica bloccato finché il residuo è maggiore di zero.
- **Prova:** rientro idempotente, dati D35 e destinazione D38 verificati. D39: verificare che la chiusura tecnica del caso dimostrativo sia rifiutata prima del rientro richiesto e consentita dopo il suo completamento, a parità degli altri requisiti. T05, T12.

### B10 — Destinazione esterna simulata

- **Risultato:** inviare il risultato al simulatore e mostrare un esito amministrativo coerente senza fattura interna duplicata.
- **Accettazione:** richiesta salvata durevolmente, identificativo stabile e scope preservato; fatto locale e outbox nella stessa transazione del proprietario quando applicabile. D40: acquisizione della richiesta distinta da elaborazione amministrativa completata; solo conferma di business con riferimento esterno stabile soddisfa il requisito esterno per la chiusura. Rifiuto/esito incerto richiedono riconciliazione e mantengono il blocco. Nessuna emissione fiscale, incasso o scrittura reale impliciti.
- **Prova:** invio/esito e consultazione autorizzata della richiesta, riferimenti alla commessa e contratto del simulatore. T03, T07, T11.

### B11 — Continuità e riconciliazione

- **Risultato:** destinatario indisponibile → richiesta in attesa → ripresa controllata, inclusi riavvio worker e timeout dopo esecuzione esterna.
- **Accettazione:** nessuna perdita o duplicazione non riconciliata; rifiuti di business non ritentati all'infinito; esiti incerti distinti. D37: chiusura tecnica consentita con requisiti locali soddisfatti; richiesta in coda e stato di attesa esplicito; chiusura amministrativa bloccata fino alla conferma di business esterna, non al solo invio. Rifiuto visibile e riconciliabile senza cancellare il lavoro eseguito. Nessun incasso/riconsegna impliciti; deroghe solo configurate, autorizzate e tracciate entro invarianti.
- **Prova:** fault injection deterministica, duplicati, dipendenze/ordine, fallimenti e azioni di recupero autorizzate. Nessuna promessa exactly-once dal solo trasporto. T03, T05, T06, T07, T10.

### B12 — Fattura tecnica interna

- **Risultato:** nell'alternativa interna generare bozza e confermare una fattura tecnica collegata alla commessa; mantenere dati storici e riferimenti.
- **Accettazione:** tipo/workflow consentiti dal customizing, nessuna sequenza universale imposta ad altri tipi; idempotenza e capability/permessi verificati. Nessun invio SdI, nessuna affermazione di emissione fiscale reale.
- **Perimetro F03/D45:** conservare emittente/destinatario con dati anagrafici utilizzati alla conferma, data/valuta/tipo/riferimento, righe/sconti/riepiloghi fiscali e collegamenti commessa/righe origine/registrazione. Nessuna riscrittura dello storico per modifiche anagrafiche successive; documento tecnico di prova, non emissione fiscale.
- **Prova:** valori e riferimenti verificabili, modifica anagrafica successiva senza riscrittura dello storico, chiamata ripetuta e azione non autorizzata. T01, T05, T12.
- **Gate:** casi e parametri di prova espliciti; regole fiscali per uso reale sottoposte al commercialista.

### B13 — Scrittura contabile tecnica

- **Risultato:** produrre una scrittura quadrata riferita a fattura e commessa; mostrare eventuali errori senza cancellare la fattura confermata.
- **Accettazione:** nessuna doppia registrazione a richiesta ripetuta; transazione locale al modulo, errori recuperabili e piano di prova documentato.
- **Prova:** quadratura, retry ed errore intermodulo, riferimenti immutati. T05, T10, T12.
- **Riferimento D43:** [F04](11-f04-reference-journal-entry.md) fornisce piano e scrittura dimostrativi del caso 001; quadratura e corrispondenza ai dati fiscali verificate. Validazione del referente su piano e scrittura attestata dal proprietario in D44, limitata al caso 001. Nessuna scelta fiscale definitiva dell’agente o implementazione contabile implicita.

### B14 — Verifica finale e recupero operativo

- **Risultato:** eseguire entrambi i percorsi dalla stessa logica officina, con istruzioni Docker ripetibili e prove di recupero dei dati.
- **Accettazione:** suite API/UI/database, isolamento, dipendenze, coda e CI eseguite; migrazioni e rollback operativo documentati, backup/ripristino esercitato su dati di test. Log/metriche/tracce e audit consentono diagnosi senza esporre segreti. Storage/backend non pubblici; nessun dominio anonimo aggiunto al bootstrap.
- **Prova:** report con comandi/esiti reali, demo manuale del percorso e review dei casi critici. Validazioni specialistiche mancanti e incompatibilità ERP reali dichiarate, non inventate. T01–T12 dove le superfici sono attivate; upload/allegati non introdotti restano gate futuri.

## 4. Definition of Done comune

- Test-first per comportamento applicativo; casi negativi su autorizzazione e invarianti, non soltanto compilazione.
- UI minima con stato, errore e azione successiva; contratto runtime UI/API esercitato.
- Contratti e ownership rispettati, dipendenze verificate, nessuna query sulle tabelle degli altri moduli.
- Migrazioni, configurazione, log/audit, diagnosi e recupero pertinenti al cambiamento documentati.
- Review, test e CI con esiti reali; distinguere implementato, verificato tecnicamente e validato dal dominio.
- Nessun dato o segreto reale nel repository; nessuna esposizione pubblica non autorizzata.
- PR collegata all'issue una volta adottato il workflow GitHub; prova di merge/chiusura verificata, non dedotta dall'avvio dei comandi.

## 5. Blocchi decisionali da risolvere al momento giusto

I gate economico-operativi OPE01–OPE05 del [documento 12](12-costs-and-operations.md) sono confermati in D57 per portare D02 In verifica; non costituiscono prove già superate o un preventivo definitivo.

Domande ai referenti, disponibilità dichiarata e gate per incremento sono raccolti in [09 — Validazioni dei referenti](09-stakeholder-validation.md). Referente amministrativo/commercialista disponibile secondo il proprietario; caso 001 e F04 validati secondo le attestazioni D42/D44, perimetro tecnico F03 confermato in D45. Dettagli residui assegnati ai gate G01–G03 con D46.

| Gate | Necessario prima di | Chi valida |
| --- | --- | --- |
| Dossier e scope implementativo autorizzati | B01 e codice di dominio | Proprietario |
| Provider identity/ambiente scelti dalla prova | Chiusura B01, poi B02 | Proprietario con evidenze tecniche |
| Campi comuni/locali minimi D36 e permessi di pubblicazione D61: risolto; prove applicative pendenti | B03 | Proprietario/referenti anagrafiche |
| Configurazione societaria dimostrativa e dati obbligatori | B04–B05 | Proprietario/referente officina |
| Risultato economico chiarito in D32; parametri del caso 001 forniti in D41 e validazione del referente attestata dal proprietario in D42; ulteriori casi limite da acquisire | B05 | Proprietario; specialista per significati fiscali |
| Disponibilità, collocazione, consumo e carcassa del caso minimo | B06–B09 | Referenti officina/magazzino |
| Contratto simulato, stati e chiusure da bloccare | B10–B11 | Proprietario con test tecnici |
| Valorizzazioni/piano e regole contabili del caso tecnico | B12–B13 | Proprietario/commercialista secondo competenza |
| Costi, ripristino, ambiente e limiti operativi: OPE01–OPE05 confermati in D57; D02 In verifica, totale non definitivo | Acquisti e accesso tramite dominio secondo OPE01; B01 secondo OPE02; B14/messa in servizio/pilota secondo OPE03–OPE05 | Proprietario con responsabili da assegnare e prove tecniche |

Questo backlog non sostituisce costi, review o approvazione complessiva. Project n. 3 e issue sono pubblicati; la pubblicazione non completa gli incrementi. I gate esecutivi G01–G03 sono approvati in D46 e descritti nel documento 09. Nessuna chiusura automatica di D01/B00.

**D46 — Delimitazione dei dettagli residui confermata:** gli ulteriori casi limite di precisione/arrotondamento devono essere definiti e validati prima di completare B05; dettagli esecutivi dei movimenti e della concorrenza di magazzino devono essere definiti e verificati nei rispettivi incrementi B06–B09; contratti tecnici, idempotenza e recupero degli errori restano progettazione e test degli incrementi pertinenti. Sono gate obbligatori, non requisiti eliminati o già soddisfatti. La conferma permette la revisione finale di D01, non chiude automaticamente D01/B00 e non autorizza implementazione o approvazione complessiva del dossier.
