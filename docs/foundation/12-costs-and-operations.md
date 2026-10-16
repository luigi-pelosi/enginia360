# Dossier di fondazione — 12. Costi e responsabilità operative (D02)

**Stato:** In verifica dopo D57; quadro economico iniziale con costi non comunicati espliciti e gate OPE01–OPE05 confermati. Non preventivo definitivo, approvazione del dossier o autorizzazione ad acquisti, servizi o deployment.
**Fonti:** `PROJECT_CHARTER.md` §5, §8, §12 e §15; [bootstrap](../bootstrap.md); [minacce](06-initial-threat-model.md); issue D02 #4.
**Rilevazione:** 16 ottobre 2026. Listino identity gestita verificato in §4; IVA/cambio, costo contrattuale della VPS e costi delle altre risorse ancora non quantificati. Localizzazione attuale dichiarata dal proprietario in D54, non verificata indipendentemente.

## Vincoli economici e hosting: stato corrente

**D54 — Localizzazione attuale e destinazione del pilota non vincolata:** il proprietario dichiara che la VPS attuale è in Germania e precisa che pilota/versione finale potrebbero non essere sulla stessa VPS né nella stessa localizzazione. La Germania è informazione fornita dal proprietario, non verifica contrattuale indipendente. La VPS attuale resta il riferimento di demo e dimensionamento iniziale, non una destinazione irrevocabile del pilota. Resta il requisito del charter di hosting UE per il target effettivo; nessuna nuova macchina, migrazione, provider, regione o spesa è autorizzata da questa precisazione.

**D47 — Baseline iniziale, precisata da D54 per pilota/versione finale:** il proprietario aveva confermato che il budget comprende già il VPS attuale, che non sono previsti acquisti di altre macchine e che i carichi della demo e del pilota saranno eseguiti su questa VPS. Nessun preventivo di un secondo host o di alta disponibilità multi-host entra nella baseline. Il costo esistente non è un nuovo acquisto né viene dichiarato nullo. Nessun importo mensile numerico è stato comunicato.

Il vincolo non approva provider identity, nuovi servizi a pagamento, una policy di backup o disponibilità contrattuale; gli obiettivi iniziali RPO/RTO sono successivamente dichiarati in D49, non già verificati. D48 chiarisce che il proprietario metterà a disposizione risorse esterne per i backup; destinazione e caratteristiche sono ancora da specificare e verificare. Non si presume un acquisto né che una copia sul disco applicativo protegga dalla perdita del nodo. Localizzazione attuale in Germania dichiarata dal proprietario (D54); verifica contrattuale e idoneità del target effettivamente scelto per il pilota restano gate del charter, senza dedurre una deroga.

**D48 — Risorse esterne per i backup fornite dal proprietario:** Luigi Pelosi dichiara che metterà a disposizione risorse esterne alla VPS per i backup. D47 resta il riferimento iniziale, precisato da D54 che non vincola il pilota alla VPS attuale; le risorse esterne sono destinate ai backup, non a nuovi nodi applicativi o alta disponibilità. È un impegno di messa a disposizione, non una destinazione già configurata o verificata.

Restano da definire capacità e accessibilità, indipendenza rispetto ai guasti della VPS, localizzazione e protezione dei dati, cifratura/gestione chiavi, retention, frequenza, monitoraggio e prova di ripristino. Nessun costo esterno è dichiarato nullo o autorizzato implicitamente. Nessuna credenziale è richiesta in chat o salvata nel repository.

## 1. Baseline verificata e limiti

Il Compose Enginia360 esistente ha servizi API e web in esecuzione e healthy al controllo iniziale. L'API non pubblica una porta host; il web pubblica HTTP sulla porta 80. Il bootstrap è una superficie tecnica senza dati di dominio, identità o database, come delimitato dall'ADR.

La risorsa VPS esistente va indicata come costo già sostenuto: non è un nuovo acquisto e non è gratuita perché già disponibile. La localizzazione in Germania è dichiarata dal proprietario (D54). Non sono noti prezzo fatturato, contratto, IVA, disponibilità esclusiva delle risorse o riscontri indipendenti della localizzazione. Non dedurre tali dati dall'IP. Le risorse osservate non sono un benchmark o prova di capacità per 100 utenti.

La CI della PR #2 sul precedente incremento documentale D46 risulta passata al controllo iniziale. Ciò non verifica infrastruttura del pilota, ripristino o prima slice di dominio.

## 2. Tre scenari distinti

| Scenario | Scopo e dati | Base da confrontare | Limiti |
| --- | --- | --- | --- |
| Locale/sviluppo | Build e test con dati sintetici, ambienti ripetibili | Risorse già disponibili e relativi consumi; servizi di sviluppo necessari | Non è un servizio pilota; nessuna promessa di continuità |
| Demo | Dimostrazione della slice con dati sintetici, accesso protetto quando sono attive identità e funzioni di dominio | Stessa VPS esistente; separazione logica da progettare e capacità da misurare, senza nuove macchine | Non estendere implicitamente il bootstrap HTTP anonimo a credenziali o dominio |
| Pilota | Uso da parte di clienti concordati con dati reali solo dopo gate separati | Destinazione effettiva da confermare (D54), non necessariamente questa VPS; requisito UE, capacità, recupero, persistenza, identità, canale protetto e costi da verificare prima del pilota | Non produzione approvata dal solo nome; capacità e recupero da provare, nessuno SLA dedotto da un host |

## 3. Voci obbligatorie e opzionali da quotare

Obbligatorio indica una capacità necessaria nello scenario, non un abbonamento da acquistare automaticamente. Una soluzione self-hosted consuma comunque risorse e lavoro operativo.

| Voce | Locale | Demo di dominio | Pilota con dati reali | Come stimare |
| --- | --- | --- | --- | --- |
| Compute e storage applicativo/database | Risorse di sviluppo | Necessari | Necessari | VPS già compreso nel budget, nessun nuovo host; costo contrattuale, quote disponibili, volumi e traffico da verificare |
| Identity/federazione/MFA | Ambiente di prova quando introdotto | Accesso protetto necessario | Necessari secondo charter | Confrontare self-hosted e gestito dopo requisiti e prova B01, non scegliere dal solo prezzo iniziale |
| Backup separato dal nodo applicativo | Fixture riproducibili, conservazione del lavoro | Necessario se la demo mantiene stato da recuperare | Necessario; risorse esterne saranno messe a disposizione dal proprietario (D48) | Destinazione/caratteristiche, dimensione, frequenza, retention, cifratura e prova di ripristino da verificare; nessuna configurazione già eseguita |
| Monitoraggio e notifica | Test e diagnostica | Health/errori pertinenti | Necessari con reperibilità definita | Risorse self-hosted oppure servizio; copertura esterna distinta dai soli health check locali |
| Canale protetto | Necessario dove transitano credenziali/dati | Necessario per identità e dominio | Necessario | Modalità e costo da scegliere; nessuna modifica automatica all'HTTP tecnico esistente |
| Dominio/DNS | Non presunto necessario | Nessun dominio attuale; acquisto valutabile dal proprietario (D56) | Nome/provider/controllo DNS da confermare per il target effettivo | Registrazione e rinnovo da quotare separatamente; disponibilità di spesa, non ordine di acquisto |
| E-mail operativa di identity/allarmi | Da valutare con il provider | E-mail unico canale allarmi iniziale (D52); invio da configurare | E-mail unico canale allarmi iniziale (D52); flussi identity da definire separatamente | SMTP disponibile secondo il proprietario (D53); verificare limiti, volumi, costo contrattuale e consegna. Nessuna approvazione automatica di recupero account o nuovi servizi |
| Storage allegati | Fuori slice iniziale | Fuori slice iniziale | Solo se autorizzato nel pilota | Non includere una piattaforma documentale prematura |
| HA/multi-host | Non richiesti | Fuori baseline D47 | Fuori baseline D47 | Nessuna nuova macchina prevista e nessuna promessa di alta disponibilità dal singolo VPS |
| Operatività e manutenzione | Tempo da esplicitare | Tempo da esplicitare | Responsabile e copertura da approvare | Patch, vulnerabilità, backup, ripristino e incidenti; distinguere esborso e lavoro |

## 4. Confronto documentale identity — rilevazione 16 ottobre 2026

**Stato:** confronto su fonti primarie eseguito; raccomandazione per una prova, non provider adottato. B01 resta subordinata al gate B00 e a un incarico implementativo esplicito. D47/D54 non vincolano il prodotto all'host odierno.

| Opzione | Licenza/canone rilevato | Funzioni e limiti rilevanti | Responsabilità e adeguatezza da provare |
| --- | --- | --- | --- |
| Keycloak community self-hosted | Licenza Apache-2.0, senza canone obbligatorio community per utente; risorse, gestione e supporto eventuale non sono gratuiti | Documentazione ufficiale: OIDC/SAML, identity brokering/federazione e secondo fattore; necessario ambiente protetto e database persistente | A nostro carico deploy, patch, backup/configurazioni, chiavi, monitoraggio e recupero. Responsabile manutenzione identity ancora da assegnare; D50 non assegna automaticamente tutte queste attività |
| Auth0 Free | 0 USD/mese nel listino | Fino a 25.000 MAU, 5 Organizations e 1 Enterprise Connection; Pro MFA non incluso nella matrice confrontata | Non dichiarato sufficiente per il charter solo perché gratuito: verificare MFA/federazione e modello organizzativo. Organizations del provider non equivalgono automaticamente ai tenant/società Enginia360 |
| Auth0 B2B Essentials, Monthly, selettore 500 MAU | 150 USD/mese | Fino a 500 MAU, Organizations pubblicizzate come illimitate, soggette a limiti di sistema, 3 connessioni enterprise e Pro MFA; add-on separati | Trasferisce al fornitore la gestione del servizio identity, non autorizzazione applicativa, isolamento tenant o tutti gli oneri operativi. Regione, contratto e funzioni effettive da validare prima dell'adozione |
| Auth0 B2B Professional, Monthly, selettore 500 MAU | 800 USD/mese | Fino a 500 MAU; aggiunge fra l'altro Enterprise MFA e funzionalità di sicurezza ulteriori | Non motivato come baseline iniziale dai requisiti fin qui raccolti; non attivato |

**Base del confronto economico:** pagina pubblica Auth0 verificata con B2B e Monthly selezionati, soglia del selettore 500 MAU; metadato priceCurrency USD. La pagina B2C mostra prezzi differenti e non è stata usata per le righe B2B. L'IVA/tassazione e i costi di cambio per il cliente non sono determinati dal listino consultato: importi non presentati come preventivo EUR IVA inclusa. Add-on, rinnovi futuri e condizioni contrattuali richiedono conferma prima di spesa.

Per confronto di periodicità, 12 pagamenti al prezzo mensile invariato corrispondono a 1.800 USD per Essentials e 9.600 USD per Professional, calcolati con Decimal. Non sono prezzi dell'opzione Yearly, non includono add-on e non fissano il prezzo di rinnovo. I 100 utenti contemporanei del charter non sono una stima di MAU: i volumi mensili del pilota sono ancora da rilevare.

### Capacità e prova self-hosted

La guida ufficiale container raccomanda un limite di memoria di 2 GB per piccoli deployment production-ready. È un riferimento di pianificazione, non un limite applicato né una misura del consumo di Enginia360: occorre misurare il carico con PostgreSQL, API, web, job e build concorrenti sul nodo disponibile. Non si deduce che la VPS sia già dimensionata per il pilota.

Le guide ufficiali richiedono canali protetti, persistenza e configurazione production; l'esempio start-dev non va pubblicato come configurazione del pilota. L'HTTP tecnico anonimo esistente non viene trasformato in un login pubblico. Il supporto documentato a protocolli/MFA non prova revoca, isolamento o conformità dei nostri flussi: verificarli in B01.

### Candidatura per la prova confermata — D55

Il proprietario conferma **Keycloak self-hosted come candidato per la prova B01** (D55), coerentemente con l’infrastruttura iniziale già disponibile e senza introdurre un canone identity gestito. Condizioni di accettazione: risorse misurate, trasporto protetto, OIDC e federation/MFA pertinenti al charter, revoca e recupero accessi, backup/ripristino, manutenzione sostenibile. Se la prova fallisce o il costo operativo è eccessivo, rivalutare il gestito con scope e spesa separatamente approvati.

La conferma riguarda la candidatura, non l’adozione definitiva; B00 e l’autorizzazione allo scope della prova restano prerequisiti. D55 non installa Keycloak, non sceglie una versione/digest da distribuire e non approva nuove identità o dati di dominio. Auth0 resta alternativa documentale, non contratto o dipendenza attivata. Il tentativo di consultare alcune pagine Auth0 sulle policy di hosting è stato bloccato; non è dichiarata una verifica completa di residenza/trasferimento dati. Va ripresa sul target e sul contratto effettivi prima del pilota.

### Fonti primarie consultate

Rilevazione 16 ottobre 2026; i listini e le guide possono cambiare. Copie di lavoro delle pagine lette conservate in scratch, non come dipendenze del prodotto.

- Keycloak, funzionalità: `https://www.keycloak.org/`
- Licenza del progetto: `https://raw.githubusercontent.com/keycloak/keycloak/main/LICENSE.txt`
- Configurazione produzione: `https://www.keycloak.org/server/configuration-production`
- Container e memoria: `https://www.keycloak.org/server/containers`
- Auth0, prezzi e matrice funzionale: `https://auth0.com/pricing` (selettori B2B, Monthly, 500 MAU verificati nel browser)

### Dominio e accesso protetto — disponibilità di spesa D56

**D56 — Dominio non disponibile, acquisto valutabile:** il proprietario dichiara di non avere ancora un dominio/sottodominio per il progetto e che acquistarlo non è un problema. È disponibilità a sostenere questa voce di costo, non un ordine di acquisto o una scelta di nome, registrar, estensione, importo o rinnovo. Nessun dominio è stato ricercato per disponibilità, prenotato o registrato dall'agente.

Per il preventivo considerare registrazione e rinnovi separatamente, valuta/IVA, eventuali servizi DNS inclusi e costi accessori, su listino primario del registrar effettivamente proposto. Senza nome/estensione/provider non viene inventato un prezzo, né un totale con costo zero. Il vincolo sulle nuove macchine non viene esteso a vietare il dominio.

Scelta del nome, costo iniziale/rinnovo e controllo DNS sono gate prima dell’uso di un dominio per accessi autenticati pubblici; servono inoltre canale protetto e verifica della configurazione identity. Un dominio non rende da solo sicuro il bootstrap HTTP. Questa voce non impone un dominio acquistato per una prova locale isolata e non autorizza TLS, DNS o redirect sull’ambiente attuale.

### Dominio e certificati: riferimento di costo verificato

Rilevazione 16 ottobre 2026, solo listini pubblici; nessuna verifica di disponibilità del nome, accesso a checkout o scelta di registrar effettuati.

| Voce di riferimento | Prezzo/cadenza | Cosa include e limiti |
| --- | --- | --- |
| Aruba, prodotto Dominio, gruppo .it | 11,99 EUR + IVA/anno a listino ordinario, promozioni escluse | Registrazione dominio, gestione DNS e redirect dichiarati nel listino. Per un nome specifico verificare condizioni, disponibilità e rinnovo prima dell'ordine |
| Aruba, prodotto Dominio, gruppo .com | 14,99 EUR + IVA/anno a listino ordinario, promozioni escluse | Stesse cautele; non è un preventivo di un dominio premium o una scelta di acquisto |
| Certificato Let's Encrypt ottenuto direttamente | Nessuna tariffa della CA per emissione/rinnovo | Configurazione, rinnovo automatico, protezione delle chiavi e monitoraggio restano lavoro operativo; eventuali intermediari possono applicare costi |

Il sito Aruba presenta anche promozioni per il primo anno, ma non sono usate per abbassare artificialmente il costo ricorrente. Il riferimento resta il listino ordinario, da riconfermare per il nome e il prodotto scelti; non si presume un prezzo futuro invariabile. Nessuna nuova casella e-mail o piano hosting viene aggiunto: il proprietario ha già dichiarato un SMTP e una VPS disponibili. L'IVA del dominio non viene desunta dal 22% del caso fiscale 001: il documento conserva gli importi del listino come «+ IVA» e non attribuisce un regime al cliente.

Il certificato è una componente del canale protetto, non una prova che DNS, login e reverse proxy siano sicuri. La configurazione richiederà scope separato e prove; nessuna emissione o rinnovo è stato eseguito. Le prove locali isolate non richiedono l'acquisto preventivo del dominio.

Fonti primarie lette:

- Listino ordinario Aruba, prodotto Dominio: `https://www.aruba.it/listino-domini.aspx`
- Descrizione del servizio e promozioni non usate per il ricorrente: `https://hosting.aruba.it/domini/registrazione-dominio/`
- FAQ ufficiale Let's Encrypt, costi e intermediari: `https://letsencrypt.org/docs/faq/`

## 5. Responsabilità confermate e ancora da assegnare

**D50 — Presidio iniziale di allarmi e ripristino:** Luigi Pelosi conferma di occuparsi personalmente della ricezione degli allarmi e della gestione degli interventi di ripristino nella fase iniziale. La conferma non implica reperibilità continuativa, un sostituto, un servizio esternalizzato o tempi già dimostrati. Giorni/fasce sono successivamente definiti in D51; il canale iniziale e-mail è successivamente scelto in D52, mentre configurazione e procedura restano da definire; l'obiettivo RTO di D49 non viene ridefinito come tempo dalla sola presa in carico.

**D51 — Fascia iniziale di presidio:** Luigi Pelosi indica «09-18 (Lun-Sab)»: presidio dal lunedì al sabato, 09:00–18:00. La specifica Lun–Sab delimita «tutti i giorni»; domenica e altre fasce non hanno presidio dichiarato. Non è una finestra di spegnimento del servizio. Il canale iniziale è successivamente scelto in D52. Fuso orario, festività e trattamento degli incidenti a cavallo della fine fascia restano da precisare prima della configurazione operativa. Non si sospende o riavvia implicitamente il conteggio RTO fuori fascia e non si dichiara garantito il ripristino entro un'ora dove manca presidio.

**D52 — Canale iniziale degli allarmi:** il proprietario sceglie la sola e-mail per la fase iniziale; Telegram e WhatsApp sono evoluzioni future, non integrazioni attuali approvate o da implementare subito. D53 conferma successivamente un SMTP già disponibile; la scelta del canale non autorizza acquisti e non dimostra la consegna degli allarmi. Destinatario e parametri di invio saranno configurati fuori dal repository; nessuna credenziale è richiesta in chat.

**D53 — SMTP già disponibile:** il proprietario conferma di disporre di un servizio SMTP utilizzabile come risorsa candidata per gli allarmi e-mail iniziali. Non sono ancora specificati provider, limiti di invio, costo contrattuale, modalità di autenticazione o configurazione. La disponibilità dichiarata non è una prova di accesso dalla VPS, protezione del collegamento o consegna effettiva; nessun nuovo servizio di invio è acquistato o attivato.

Destinatario e segreti saranno gestiti tramite configurazione sicura fuori dal repository quando l’incarico operativo sarà autorizzato; non sono richiesti in chat. Verificare limiti, costi eventualmente già inclusi, connettività, invio protetto e ricezione di un messaggio di prova prima di dichiarare operativo l’allarme. Non estendere automaticamente la disponibilità SMTP ai flussi di identity non ancora progettati.

| Attività | Responsabile confermato o da concordare | Prova richiesta |
| --- | --- | --- |
| Approvazione spesa e provider | Proprietario | Budget e scelte esplicite; nessuna attivazione prima dell'autorizzazione |
| Patch host/container e dipendenze | Operatore da identificare | Procedura, verifica vulnerabilità e rollback |
| Messa a disposizione risorse esterne di backup | Proprietario, impegno D48 | Destinazione e caratteristiche concordate; accesso sicuro da verificare |
| Esecuzione e controllo periodico dei backup | Responsabile/procedura da definire; non assegnati implicitamente da D48 o D50 | Esecuzione, verifica copie e segnalazione errori esercitate |
| Gestione degli interventi di ripristino | Luigi Pelosi nella fase iniziale (D50), lunedì–sabato 09:00–18:00 (D51); fuso da precisare | Procedura e ripristino esercitati su ambiente isolato e dati di test, con tempi misurati |
| Gestione identità, recupero account e accessi di emergenza | Referente autorizzato da identificare | Flussi verificati, MFA/federazione e audit pertinenti |
| Ricezione degli allarmi e gestione del ripristino | Luigi Pelosi nella fase iniziale (D50), lunedì–sabato 09:00–18:00 (D51); e-mail (D52), SMTP disponibile (D53), configurazione/fuso da precisare | Notifica effettivamente ricevuta e procedura di intervento provata; nessuna reperibilità continuativa presunta |
| Protezione dati e idoneità per uso reale | Proprietario con competenze pertinenti | Giurisdizione/contratti e misure verificate prima del pilota |

RPO = perdita temporale massima di dati accettata; RTO = tempo obiettivo per il ripristino.

**D49 — Obiettivi iniziali di recupero:** il proprietario indica RPO «fino al giorno precedente» e RTO massimo di 1 ora, limitatamente alla fase iniziale. Sono obiettivi da progettare e dimostrare con prove, non garanzie già conseguite o SLA. Per l'RPO vanno precisati orario del punto di recupero giornaliero, completamento del trasferimento esterno e gestione di backup falliti; non si assume automaticamente un limite mobile di 24 ore. Per l'RTO vanno definiti inizio/fine della misurazione, copertura operativa e scenario di guasto.

La prova di recupero deve riguardare il servizio utilizzabile, non soltanto il caricamento del database: rendere espliciti tempi di disponibilità del nodo, recupero delle configurazioni necessarie, trasferimento dei backup, ripristino e verifiche applicative. La perdita completa o indisponibilità prolungata della VPS è uno scenario distinto da un errore del database. Nel vincolo a nodo unico non è dimostrato che il nodo possa tornare disponibile entro l’ora; non promettere il rispetto dell’obiettivo senza verifica delle dipendenze dal provider e dell’operatore. D48 non rende automaticamente le risorse di backup una macchina di failover.

**Evoluzione futura dichiarata, non baseline attuale:** a progetto completo il proprietario intende valutare ridondanza dei dati, replicazione continua e load balancing, eventualmente su AWS. Non sono approvati provider cloud definitivo, migrazione, servizi, budget o date. D47/D48 restano il riferimento iniziale, precisato da D54: VPS esistente per la demo e backup esterni del proprietario; destinazione effettiva di pilota/versione finale ancora da confermare.

## 6. Dati necessari e prossimo gate

1. Budget iniziale D47 comprensivo del VPS attivo e nessun acquisto aggiuntivo approvato; D54 chiarisce che il target di pilota/versione finale può cambiare. Importo mensile non comunicato; un’eventuale alternativa richiederà valutazione e approvazione separata.
2. Costo effettivo del VPS corrente e cosa include, senza richiedere credenziali o documenti con dati personali.
3. Allarmi e gestione del ripristino affidati al proprietario nella fase iniziale (D50); presidio lunedì–sabato 09:00–18:00 confermato (D51), canale iniziale e-mail (D52); SMTP disponibile (D53), parametri/limiti e prova di consegna ancora da verificare; fuso, festività e gestione fuori fascia ancora da precisare. Manutenzione, controllo dei backup e ulteriori responsabilità restano da assegnare senza presumere un servizio esternalizzato o lavoro senza costo.
4. Volumi iniziali pilota e capacità disponibile da verificare; D49 indica recupero fino al giorno precedente e RTO massimo di 1 ora inizialmente. Precisare punti temporali, copertura e scenari, poi provare il recupero prima del pilota con dati reali.
5. Risorse esterne di backup saranno fornite dal proprietario (D48): specificare destinazione e verificarne indipendenza dal nodo, capacità, retention, accesso e ripristino, senza presumere nuove spese o accesso già operativo.

Il confronto del listino identity è riportato in §4. Per le altre voci, confrontare soltanto i listini primari pertinenti al riferimento iniziale D47 e alla precisazione D54, senza presumere acquisti di nuove macchine, con data di rilevazione, valuta, IVA, cadenza, risorse incluse, rinnovi e costi opzionali. Normalizzare con calcoli eseguiti e dichiarare assunzioni/extra. Non riportare un totale finché i dati necessari sono mancanti.

**Stato D02:** In verifica, con delimitazione dei residui confermata dal proprietario in D57 (§7). Confronti identity e dominio/certificati verificati su fonti primarie; totale non quantificato e prove operative non eseguite. D01 resta separata, In verifica; B00 e dossier complessivo non approvati. Il servizio pubblico non è stato modificato.

## 7. Quadro economico consolidato e gate confermati per la revisione D02

Il riferimento iniziale è sostenibile soltanto sotto condizioni da provare; non è un preventivo completo o uno SLA. Nessun costo non comunicato è trattato come zero.

| Voce | Locale/sviluppo | Demo | Pilota | Stato economico |
| --- | --- | --- | --- | --- |
| Compute principale | Risorse disponibili | VPS già nel budget | VPS attuale solo riferimento; target non vincolato (D54) | Nessun nuovo acquisto approvato; importo VPS non comunicato, target pilota da verificare |
| Backup | Fixture e codice versionati non sostituiscono backup dei dati persistenti | Risorse esterne promesse D48, se c'è stato da conservare | Risorse e recupero da verificare sul target effettivo | Costi/quote non comunicati; non è una risorsa già provata |
| Invio allarmi | Solo se esercitato nello scope autorizzato | E-mail via SMTP già disponibile, da provare | Stessa scelta iniziale, da verificare sul target | Nessun nuovo servizio richiesto; costi/quote dell'esistente non comunicati |
| Identity | Prova isolata dopo i gate | Keycloak candidato D55, non installato | Adozione condizionata all'esito B01 e alle verifiche sul target | Nessun canone community, ma risorse e manutenzione da misurare/assegnare; gestito non attivato |
| Dominio | Non necessario per la prova locale isolata | Acquisto valutabile D56, esempio .it/.com a listino sopra | Riutilizzo o scelta sul target, non dati inventati | Nuova voce annuale eventuale, non ordine approvato; rinnovi da verificare |
| Certificati | Canale adeguato alla prova isolata | Possibile CA senza tariffa, non configurata | Emissione/rinnovo e canale da provare | Nessun abbonamento CA obbligatorio introdotto; lavoro operativo non quantificato |
| Manutenzione/monitoraggio | Da includere nell'impegno | Responsabile allarmi/ripristino D50, ulteriori ruoli aperti | Copertura iniziale D51 e limiti da formalizzare | Non si presume servizio esternalizzato o lavoro a costo zero |

**Totale:** non determinabile in modo attendibile con i dati attuali. Si separano il budget esistente non quantificato, le risorse fornite dal proprietario, gli esempi di listino e il lavoro operativo. Non si sommano listini USD di alternative non adottate agli esempi EUR del dominio. Nessuna promessa di «costo totale zero» o disponibilità garantita.

### Gate residui confermati — D57

**D57 — Delimitazione D02 confermata per la revisione:** il proprietario approva il passaggio di D02 a «In verifica», mantenendo come gate gli elementi residui: dominio/nome/costi e rinnovi prima dell'acquisto; prove identity, risorse e protezioni prima di completare B01, con prerequisito B00 e scope implementativo esplicito; backup e ripristino misurato, allarmi verificati, responsabilità residue assegnate, costi e idoneità del target effettivo prima del pilota. La matrice OPE01–OPE05 dettaglia referenti ed evidenze. Non è un preventivo definitivo, un acquisto, approvazione complessiva del dossier o autorizzazione a implementare.

| ID | Ambito e referente | Scadenza logica / evidenza richiesta |
| --- | --- | --- |
| OPE01 | Dominio e spesa, proprietario | Prima di qualsiasi acquisto: nome/estensione/registrar, prezzo iniziale e rinnovo, IVA/extra e autorizzazione esplicita; controllo DNS prima dell'accesso pubblico tramite dominio |
| OPE02 | Identity, responsabile tecnico e proprietario | B00 e scope prima di implementare B01; risorse, trasporto protetto, protocolli/MFA, revoca, recupero e manutenzione verificati prima di completare B01; nessun login reale sul bootstrap HTTP anonimo |
| OPE03 | Backup, responsabile da assegnare dal proprietario | Destinazione, quote, cifratura/chiavi, checkpoint giornaliero, retention e guasti da definire prima dell'uso dello stato persistente della demo; ripristino end-to-end misurato prima di completare B14 e prima del pilota con dati reali |
| OPE04 | Allarmi/manutenzione, proprietario assegna i ruoli residui | Prima della messa in servizio: fuso/festività/fine fascia, estremi RTO, canali SMTP e ricezione verificata; assegnare controllo backup, patch host/container e amministrazione identity senza estendere implicitamente D50 |
| OPE05 | Target e costi pilota, proprietario | Prima del pilota: paese/contratti del target e destinazioni dati pertinenti, quote/costi effettivi e capacità, risorse di recupero e test; nessuna deroga UE dedotta da D54 |

La delimitazione è confermata in D57: consente la revisione finale di D02, non chiude automaticamente l'issue o le domande economiche e non approva un preventivo inesistente. Le assegnazioni residue e le prove saranno completate ai rispettivi gate, non sono dichiarate già risolte. Review della documentazione e verifiche della PR restano distinte. Nessun gate permette di esporre credenziali/dati senza protezioni o di dichiarare raggiunto l'RTO non provato.
