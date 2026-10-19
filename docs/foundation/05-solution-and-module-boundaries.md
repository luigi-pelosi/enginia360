# Dossier di fondazione — 05. Solution e confini dei moduli

**Stato:** base architetturale confermata dal proprietario Luigi Pelosi: monolite modulare, contratti espliciti e PostgreSQL inizialmente unico, con dati posseduti per modulo. Il layout dettagliato, il catalogo dei moduli e le modalità tecniche restano proposte da rifinire; non è approvazione del dossier completo né autorizzazione a implementare. Nulla è ancora implementato oltre il bootstrap.
**Ambito:** struttura della solution, ownership e dipendenze del monolite modulare per la prima slice. Il modello completo delle minacce, il backlog e i costi sono sezioni successive.
**Fonti:** `PROJECT_CHARTER.md` §6–9, §11–14; [modello commerciale](01a-commercial-document-model.md), [organizzazione](02-organization-and-access.md), [ownership](03-capabilities-and-data-ownership.md), [slice](04-first-vertical-slice.md). Nessuna libreria o provider ulteriore selezionato.

## 1. Punto di partenza e obiettivo

Il repository contiene oggi un host `src/Enginia360.Api`, test di bootstrap e frontend `web/`; non contiene ancora moduli di dominio. Conservare il bootstrap e introdurre incrementi verticali soltanto dopo l'approvazione del dossier.

Proposta iniziale: un host ASP.NET Core .NET 10, moduli in assembly dedicati, PostgreSQL, React/TypeScript e un worker ospitato nello stesso processo per le attività persistenti. I container frontend e API restano distinti; in seguito si aggiunge la persistenza necessaria alla slice. Un eventuale worker separato è una scelta operativa successiva, non un requisito per chiamare il sistema modulare.

Niente microservizi, message broker obbligatorio, motore BPM generico, event sourcing, generic repository o interfaccia per ogni classe. L'outbox è un meccanismo di consegna affidabile, non l'adozione di event sourcing.

## 2. Ownership logica proposta

La famiglia comune dei documenti commerciali rimane valida. Non si crea però una mega-entità che possiede tutte le regole: un tipo concreto ha un proprietario definito. Il patrimonio comune riguarda tipi, significati, configurazioni e contratti di sviluppo, non accesso universale alle tabelle.

| Modulo candidato | Dati e regole posseduti | Fuori dal suo confine |
| --- | --- | --- |
| Organizations | Tenant, società, sedi, magazzini come unità organizzative; membership, scope e assegnazioni di accesso/capability. | Credenziali di un provider identity non ancora scelto; movimenti e stock. |
| Counterparties | Identità comune tenant-scoped, estensioni societarie, destinazioni e visibilità, mappature/autorità dichiarate pertinenti. | Saldi contabili e documenti delle società; aggiornamenti concorrenti senza autorità. |
| Vehicles | Identità del veicolo e relazioni ai soggetti; D63: gestione secondo le regole approvate delle controparti, selezione commessa mediante proiezione minima nel tenant verificato. | Soggetto a carico della specifica commessa; selezione non conferisce gestione o accesso ai dati societari riservati. B04 non introduce CRUD completo né nuove semantiche add/remove. |
| Catalog | Identità articoli/prestazioni, condizioni e regole di valorizzazione commerciale di propria competenza. | Giacenze e riscrittura dei valori storici già fissati in altri documenti. |
| CommercialFlow | Tipi/significati configurati, versioni del customizing documentale societario, regole di sviluppo, collegamenti effettivi di provenienza e avanzamento delle operazioni di sviluppo/rettifica. | Non possiede stock, tempi, importi fiscali o una copia autorevole dello stato di ogni documento specializzato. |
| Workshop | Istanze dei documenti officina (preventivo e commessa), righe pertinenti, lavorazioni, assegnazioni/tempi, installazione tecnica e chiusura tecnica. | Emettere fatture, registrare stock direttamente o duplicare i collegamenti autorevoli di CommercialFlow. |
| Inventory | Prenotazioni, prelievi, collocazione/preparazione, consegne logistiche, effetti di consumo, resi del nuovo e ricevimento della carcassa. | Dichiarare tecnicamente installato un componente o creare una scrittura contabile. |
| Billing | Istanze delle fatture e rettifiche del proprio dominio, dati storici e validazioni fiscali di competenza. | Duplicare commesse, imporre sempre un predecessore o registrare direttamente scritture contabili. |
| Accounting | Scritture, quadratura, riferimenti e idempotenza delle registrazioni del caso minimo. | Contabilità completa del primo rilascio non inclusa nella sola slice; nessuna modifica delle fatture. |
| Integrations | Contratti/adattatori esterni, traduzione, mappature tecniche, stato di invio e riconciliazione tecnica. | Seconda autorità sui dati comuni, regole proprietarie introdotte nel dominio o conferma economica dedotta dal solo HTTP 200. |

Acquisti, pianificazione completa, tesoreria completa, gestione allegati e reportistica non vengono creati come progetti vuoti ora. Il tipo di magazzino/area di preparazione e l'identificazione della carcassa restano dettagli di dominio aperti. Il confine organizzativo possiede il riferimento del magazzino; Inventory ne possiede lo stock: non sono due proprietari dello stesso fatto.

### Documento comune e documento specializzato

Esempio proposto: la commessa è un ordine cliente commerciale il cui stato e contenuto sono posseduti da Workshop; la fattura è un documento commerciale posseduto da Billing. CommercialFlow possiede la configurazione che consente lo sviluppo e il suo collegamento/progresso, non riscrive direttamente nessuna delle due entità.

Il comune riferimento a un documento comprende identificativo, tipo e contesto autorizzato secondo contratti minimi. Uno stato mostrato nella vista del flusso è una lettura/proiezione dello stato posseduto dal modulo competente, non una seconda macchina a stati autorevole. Errori o ritardi della proiezione devono essere distinguibili.

CommercialFlow contiene configurazioni tipizzate dichiarate dalle capability. Una configurazione della carcassa è di tipo officina/magazzino: il modulo competente ne definisce schema, vincoli e comportamento; il catalogo comune ne conserva la versione societaria e non esegue codice arbitrario caricato da un utente. Non si approva un linguaggio di regole universale.

## 3. Struttura della solution proposta

```text
Enginia360.sln
Directory.Build.props
global.json
src/
  Enginia360.Api/                   # composition root, HTTP, avvio worker
  BuildingBlocks/
    Enginia360.BuildingBlocks/      # sole primitive tecniche realmente comuni
  Modules/
    Organizations/
    Counterparties/
    Vehicles/
    Catalog/
    CommercialFlow/
    Workshop/
    Inventory/
    Billing/
    Accounting/
    Integrations/
  Processes/
    Enginia360.AfterSales/          # coordinamento della slice interna/esterna
tests/
  Enginia360.Api.Tests/             # preservare verifiche bootstrap
  Modules/                         # test dei moduli effettivamente introdotti
  Enginia360.Architecture.Tests/
  Enginia360.AcceptanceTests/
web/
docs/foundation/
```

Questo è un layout target, non una richiesta di creare subito tutte le cartelle o progetti. Il nome `BuildingBlocks` non autorizza un contenitore di regole comuni di officina/fiscalità.

Per ogni modulo necessario all'incremento, proporre inizialmente:

```text
Enginia360.<Module>.Contracts/      # soli contratti pubblici minimi
Enginia360.<Module>/
  Domain/
  Application/
  Infrastructure/
```

Un assembly d'implementazione per modulo, separazione interna in namespace/cartelle e contratti dedicati: evita quattro progetti automatici per ogni contesto. Il dominio rimane indipendente dal codice di infrastruttura e dai contratti esterni. Entità e dettagli interni non sono pubblici; soltanto le API necessarie e il punto di registrazione sono esposti. Test di architettura verificano le separazioni interne; un'ulteriore separazione fisica dei layer verrà introdotta soltanto se giustificata. Nessun tool per questi test è scelto qui.

## 4. Regole di dipendenza

Le frecce indicano dipendenze di compilazione ammesse, non flussi HTTP:

```text
Api -> AfterSales + punti di registrazione dei moduli
AfterSales -> Contracts dei moduli coinvolti + proprie porte applicative
Implementazione di ciascun modulo -> propri Contracts + BuildingBlocks
Contracts -> BCL e primitive minime concordate
```

- Vietati riferimenti diretti da implementazione A a implementazione B.
- Per il primo incremento i contratti non dipendono da altri contratti di modulo; eventuali riferimenti pubblici indispensabili richiedono una decisione esplicita e un grafo aciclico.
- Nei contratti solo identificativi/DTO immutabili e API applicative; niente entità interne, `IQueryable`, contesti ORM o connessioni database condivise.
- AfterSales coordina le chiamate e conserva lo stato del processo quando occorre recupero, non possiede fatture, commesse o stock. Non viene referenziato dai domini.
- Le implementazioni dei moduli non dipendono da AfterSales per eseguire le proprie operazioni. Il coordinatore invoca le loro API e interpreta gli esiti.
- Le implementazioni della porta di destinazione interna/esterna appartengono al livello applicativo di coordinamento e vengono composte dall'host. La scelta segue capability e autorità societarie, non il nome del cliente.
- Schema e validazione delle estensioni di customizing si registrano nell'host tramite contratti: CommercialFlow non referenzia Workshop/Billing per conoscerne l'implementazione.
- Ogni accesso pubblico verifica i prerequisiti pertinenti; il solo fatto di essere chiamato internamente dal coordinatore non rende autorizzata un'operazione.

Il grafo va verificato dai test prima di dichiararlo aciclico. I nomi e il numero di progetti sono proposte, non standard obbligatori del linguaggio.

## 5. Dati, transazioni e processi recuperabili

Proposta: un'istanza/database PostgreSQL iniziale, ownership per modulo e separazione in schemi; non database per società o microservizio dedotti dalla gerarchia. È una scelta ancora da approvare.

- Ogni modulo applica le proprie migrazioni, possiede le tabelle e il contesto di persistenza; non crea query/join applicativi sulle tabelle degli altri moduli per eluderne i contratti.
- Tenant context sempre verificato. Dati comuni tenant-scoped e dati societari hanno scope differenti; la condivisione non elimina i controlli. RLS dove appropriato secondo il charter, da progettare/testare senza presumere che ogni tabella abbia gli stessi filtri.
- Transazioni locali al modulo. Registrazione del fatto e relativa outbox atomica quando condividono il proprietario e la transazione.
- Ogni passo coordinato ha un identificativo di operazione stabile; moduli destinatari prevengono effetti duplicati. Stato del coordinamento, collegamenti CommercialFlow e fatti dei moduli hanno responsabilità distinte, non tre copie dello stesso esito autorevole.
- Integrazione esterna mediante coda persistente e worker .NET; non promessa di transazione distribuita o exactly-once. Esiti incerti richiedono verifica/riconciliazione.
- Gli effetti di installazione e consumo avvengono nei rispettivi moduli: eventuale successo tecnico seguito da errore di stock è uno stato visibile da recuperare, non una conferma globale inventata.

Per flussi puramente interni, preferire contratti sincroni espliciti finché bastano. Eventi/outbox solo per lavoro persistente o confini distribuiti reali; non distribuire ogni interazione del monolite per uniformità.

## 6. Frontend, sicurezza e osservabilità

- Un'app React/TypeScript, organizzata per funzionalità introdotte; nessun frontend distinto per tenant o società.
- Contesto operativo visibile e capability/permessi coerenti, con enforcement backend. Non usare menu nascosti come unica autorizzazione.
- Provider federation/MFA ancora da scegliere tramite prova e confronto richiesti dal charter. Nessuna autenticazione casalinga o credenziale reale aggiunta al bootstrap HTTP pubblico.
- Scenario di dominio inizialmente in ambiente di test protetto; prima di esporre dati o credenziali, progettare autenticazione, trasporto sicuro e accessi. L'autorizzazione al bootstrap HTTP non è autorizzazione a pubblicare il DMS in chiaro.
- Log strutturati e correlation ID del bootstrap da estendere; OpenTelemetry previsto dal charter, ma pipeline/collector/destinazione non sono già implementati.
- Coda con stato, tentativi e azioni di recupero autorizzate; audit di customizing, concessioni di accesso e rettifiche. Dati personali minimizzati.

## 7. Verifica prevista e decisione richiesta

Prima di dichiarare la struttura implementata: test delle dipendenze/visibilità, regole di dominio, API e isolamento tra tenant/società/sedi, processi intermodulo con fallimenti e retry, persistenza coda al restart e contratti del simulatore esterno. Le verifiche del bootstrap non soddisfano questi criteri di dominio.

**Decisione da discutere ora:** monolite modulare con assembly dedicati, contratti espliciti e coordinamento applicativo; PostgreSQL inizialmente unico con dati posseduti per modulo. Niente scaffolding massivo prima dei casi d'uso. Catalogo definitivo dei moduli e confini tecnici sono revisionabili prima dell'approvazione completa.

**Successivi elaborati del dossier:** threat model iniziale, backlog verticale con criteri e dipendenze, domande agli operatori/commercialista e costi locale/demo/pilota. Questa proposta non li dichiara completati.
