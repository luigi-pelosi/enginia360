# Dossier di fondazione — 01. Glossario e confini di dominio

## Stato corrente consolidato — D70–D72

B01–B07 consegnati; B07 main `fcc62ca8aefbca4e7bf66e413f063d97f85bf9df` (PR #28, CI main 39337260806 success). D70 autorizza B08–B14 in sequenza autonoma, un solo WIP. B08 In corso: D72 conferma installazione parziale esplicita q6 entro il prelevato non installato; il residuo resta prelevato non installato. Officina possiede il fatto tecnico, Inventory il consumo idempotente; nessuna transazione globale. B09–B14 restano Backlog per dipendenze/gate pertinenti, non per mancata autorizzazione. Nessuna nuova policy fiscale o di reso dedotta.

Accettazione automatica isolata effimera, nessun nuovo ambiente manuale persistente, nessuna review LLM o approvazione manuale di routine. Bootstrap 443, segreti, volumi e backup conservati invariati. Le descrizioni successive di stato/autorizzazione precedente sono **storiche e superate da questo riepilogo e D70–D72**; i requisiti di dominio restano validi. Prove/CI/completamento non sono dedotti dall'autorizzazione.


**Stato corrente D69 — 19 ottobre 2026:** B05 completata (PR #26, baseline `605a7d5937b645681eb95cf644e228613b1d4ce8`). Il proprietario approva l’opzione A: prenotazioni parziali esplicite, mai troncamento automatico. B06 privata/sintetica implementata e verificata localmente, candidata alla review indipendente e alla successiva preparazione manuale del parent; non Completata. G02/B06 dispone delle prove tecniche nel [report B06](../b06-verification.md), senza chiudere G02/B07–B09. B07–B14 restano blocked/Backlog e non autorizzati. Nessun commit/push/merge o deployment persistente B06.

### Stati precedenti — storici, superati dove incompatibili con D69

**Consegna B05 — 19 ottobre 2026:** accettazione manuale positiva del proprietario «Ok funziona tutto. Procediamo»; review core e quattro artefatti manuali acquisite, discrepanza documentale risolta. Autorizzata la sola consegna Git/PR/CI/merge/chiusura B05, non nuovi deploy o B06. Stato al congelamento: In verifica; esito finale remoto nella PR e issue #11. Limiti e perimetro nel report B05. Le indicazioni precedenti di accettazione/review pendenti sono storiche e superate da questa registrazione. B06–B14 restano bloccati/Backlog e non autorizzati.

**Stato corrente:** dossier approvato in D58; B01–B04 completati. B04 integrata con PR #25, merge `0f9cc50fcf685d2e8ffab2686947124fb3189293`, issue #10 chiusa e Project Completato, verificati sul remoto. D64 autorizza soltanto B05 sintetica e privata; D65 risolve il gate catalogo con visibilità anagrafica nel tenant, senza ampliare permessi gestionali o dati societari. B06–B14 restano Backlog/bloccati e non autorizzati. Le dichiarazioni pre-consegna nelle decisioni precedenti sono storiche.
**Ambito:** linguaggio del post-vendita e responsabilità dei contesti; autorizzazioni implementative circoscritte nel registro. D60/D61 restano la fonte storica dello scope B03 e del permesso di pubblicazione; il loro stato pre-consegna non descrive più la baseline corrente.
**Fonte normativa di progetto:** `PROJECT_CHARTER.md`, sezioni 3, 4, 7–12 e 15.
**Validatori richiesti:** proprietario del prodotto e referenti operativi; commercialista per significati e regole amministrative.

**Lettura consolidata del blocco documenti:** [Sintesi del modello commerciale](01a-commercial-document-model.md). D1–D2 sono storia superata; D3–D11 contengono i chiarimenti acquisiti. La sintesi distingue tali decisioni dalle conseguenze progettuali ancora proposte.

## 1. Criteri di lettura e accettazione

- **CH:** requisito o distinzione presente nel charter; non implica validazione operativa o fiscale.
- **OL:** comportamento osservato nel legacy, ancora da validare; non diventa automaticamente un requisito.
- **PR:** proposta di modellazione o terminologia, da approvare.
- **DA:** domanda aperta; nessuna decisione implicita.
- **DP:** decisione concettuale confermata dal proprietario; non equivale ad approvazione dell'intero dossier né a validazione fiscale. D3 prevale sulle interpretazioni storiche D1–D2.

Questa fase è accettabile quando il proprietario valida i termini centrali, chiarisce le ambiguità prioritarie e accetta o corregge la mappa delle responsabilità. L'approvazione di questa fase non approva l'intero dossier. Ogni risposta deve essere registrata distinguendo chi decide e su quale perimetro.

## 2. Filo conduttore

Dal charter §4: appuntamento → accettazione → preventivo/autorizzazione → commessa e lavorazioni → ricambi/acquisti → chiusura tecnica → fatturazione/incasso → contabilità e riconsegna.

Questo è un percorso narrativo, non una macchina a stati già approvata: ingresso senza appuntamento, ordine effettivo delle fasi, riaperture, pagamenti e riconsegna richiedono validazione. Il primo rilascio e la prima vertical slice (§11) hanno estensioni diverse: non tutti i passaggi del primo rilascio vanno implementati nella slice.

## 3. Glossario iniziale

I termini inglesi sono proposte per il linguaggio tecnico, non nomi di classi o contratti già decisi.

| Termine operativo | Termine tecnico proposto | Significato e distinzione | Stato / fonte |
| --- | --- | --- | --- |
| Tenant | Tenant | Cliente/gruppo contrattuale (es. Beta Group) con più società interne, anagrafiche comuni ed estensioni societarie riservate. Confine di isolamento dagli altri clienti. | CH §8; DP D22 |
| Società | Legal entity | Soggetto giuridico/contabile; livello esclusivo dei customizing. Relazione 1:N con le sedi. | CH §8; DP D14–D15 |
| Sede | Site | Unità operativa appartenente a una sola società, con relazione 1:N verso i magazzini. Distinta dal magazzino nonostante l'ambiguità legacy. | CH §8; DP D15; OL E4 |
| Magazzino | Warehouse | Unità di gestione delle scorte appartenente a una sola sede; società determinata tramite la sede. | CH §8; DP D15 |
| Soggetto / anagrafica | Party | Persona o organizzazione che può assumere ruoli commerciali differenti. Non impone un unico modello condiviso tra tutti i contesti. | PR |
| Cliente | Customer | Ruolo commerciale del soggetto che riceve servizi; non sinonimo automatico di intestatario, pagante o destinatario fattura. | PR; CH §10.1 |
| Intestatario del veicolo | Registered keeper | Soggetto indicato come intestatario. Non equipararlo automaticamente al proprietario giuridico. Terminologia e fonte del dato da validare. | PR; CH §10.1 |
| Proprietario del veicolo | Vehicle owner | Soggetto titolare della proprietà; possibile ruolo distinto dall'intestatario. Non si inventano regole legali o documentali. | PR; DA |
| Utilizzatore / conducente | Vehicle user / Driver | Ruoli potenzialmente distinti; non presumere che coincidano con richiedente o pagante. | CH §10.1; DA |
| Richiedente | Service requester | Soggetto che richiede l'intervento; poteri di autorizzazione da verificare separatamente. | CH §10.1; PR |
| Pagante / soggetto a carico | Payer / Charge allocation party | Default: un soggetto a carico per riga; righe diverse possono avere soggetti differenti. La singola riga è ripartibile se il customizing del tipo documento lo consente. Pagante effettivo e destinatario fattura non sono automaticamente coincidenti con il soggetto a carico. | DP D12–D13; CH §10.1; PR sui ruoli |
| Destinatario della fattura | Invoice recipient | Ruolo amministrativo da distinguere dal pagante; significato preciso e dati richiesti da validare con amministrazione/commercialista. | CH §10.1; DA |
| Veicolo | Vehicle | Bene oggetto dell'intervento, con identità e relazioni temporali; targa e telaio non sono decisi come identificativo interno. | CH §2, §10.1; PR |
| Appuntamento | Appointment | Impegno pianificato per un intervento. Non coincide con accettazione, lavorazione eseguita o commessa. | CH §4; OL E1 |
| Accettazione | Vehicle reception | Presa in carico operativa del veicolo e rilevazione delle informazioni d'ingresso. Non implica da sola autorizzazione alla spesa. | CH §4; PR; OL E3 |
| Preventivo | Quotation | Documento commerciale con significato di offerta al cliente. Preventivo officina e preventivo ricambi hanno customizing e sviluppi configurabili diversi. | DP D3 |
| Autorizzazione | Customer authorization | Evidenza dell'approvazione di un perimetro di intervento da parte di un soggetto abilitato. Non è il permesso applicativo RBAC. | CH §4; PR |
| Commessa officina | Workshop order | Documento commerciale che è già un ordine cliente effettivo, specializzato per il processo officina e le relative lavorazioni. Non richiede un secondo ordine cliente per acquisire tale significato. Nome inglese proposto. | DP D3 |
| Documento commerciale | Commercial document | Concetto comune a documenti con significati, customizing, personalizzazioni, workflow e collegamenti differenti. Non decide da solo struttura tecnica o ownership dei moduli. | DP D3 |
| Ordine cliente | Sales order | Significato commerciale assunto anche dalla commessa officina; non necessariamente un documento ulteriore separato. | DP D3 |
| Tipo documento configurato | Document type | Profilo come Preventivo officina, Commessa officina o Preventivo ricambi; distingue la configurazione specifica dal significato commerciale del documento. Termine tecnico proposto. | DP D3; PR terminologica |
| Sviluppo documentale | Document flow | Percorso configurato verso documenti commerciali successivi collegati. Non coincide con un semplice cambio di stato del documento sorgente; meccanismo tecnico ancora da definire. | DP D3; PR terminologica |
| Lavorazione | Job / Task | Unità operativa da pianificare ed eseguire nella commessa. Il legame di prestazioni e ricambi con essa dipende dal customizing del tipo documento; struttura precisa e termine `report` ancora da validare. | DP D8 per il legame configurabile; PR; OL E1 |
| Prestazione | Service line | Elemento di servizio valorizzato economicamente. Relazione con lavorazioni, ore e addebiti da validare. | CH §11; PR |
| Consuntivazione | Actual work recording | Registrazione di attività, tempi e risorse effettivamente impiegati. Ore lavorate e ore fatturate non sono assunte uguali. | CH §4; PR |
| Ricambio / articolo | Part / Item | Articolo impiegabile nell'intervento. Identità di catalogo distinta dalla sua quantità presente in magazzino. | CH §7.1 e §11; PR |
| Giacenza fisica | On-hand quantity | Quantità fisica contabilizzata dal magazzino; distinta dalla prenotazione. | CH §10.2 e §11 |
| Prenotazione ricambio | Stock reservation | Impegno quantitativo per una necessità operativa; incide sulla disponibilità, non sulla giacenza fisica. Scadenza e rilascio ancora aperti. | CH §11 |
| Disponibilità | Available quantity | Per B06: fisico meno impegni attivi nello stesso tenant/società/sede/magazzino/articolo; quantità richiesta esplicita coperta e limitata al residuo di riga. Arrivi previsti, rilascio e altre policy restano fuori scope. | CH §10.2; DP D34/D69 |
| Consumo confermato | Confirmed consumption | Utilizzo definitivo che genera una sola movimentazione anche a richiesta ripetuta; non equivale automaticamente alla fatturazione del ricambio. | CH §11; PR |
| Reso / rettifica / annullamento | Return / Adjustment / Cancellation | Concetti distinti: restituzione fisica, correzione di un fatto registrato, revoca di un impegno. Causali ed effetti da validare. | CH §4, §9–10; PR |
| Chiusura tecnica | Technical completion | Completamento operativo delle lavorazioni; non implica fattura emessa, incasso avvenuto o veicolo riconsegnato. | CH §4; PR |
| Risultato economico della commessa | Work-order financial outcome | Nella prima slice: riepilogo commerciale con imponibile al netto degli sconti, imposte e totale a carico. Determinazione dei costi e marginalità rinviate; non è un margine né un utile. | CH §11; DP D32 |
| Fattura / incasso / registrazione contabile | Invoice / Payment receipt / Journal entry | Fatti distinti, con responsabilità e transizioni proprie; le regole fiscali e contabili restano da validare. | CH §4 e §11 |
| Sistema autorevole | System of record | Unica autorità dichiarata per un insieme di dati o una transizione nel profilo configurato; non equivale a qualsiasi copia locale. | CH §7.3 |

## 4. Mappa candidata dei bounded context

**Tutta la scomposizione seguente è PR**, coerente con la mappa candidata del charter §7.1. Definisce responsabilità semantiche, non tredici applicazioni/database da creare. L'ownership indicata vale quando Enginia360 è autorevole: nel profilo ERP esterno va ridefinita esplicitamente nella fase 3, senza doppia scrittura autorevole.

| Contesto candidato | Responsabilità e dati propri proposti | Non deve possedere |
| --- | --- | --- |
| Organizzazioni e accessi | Tenant, società, sedi, membership, ruoli, scope e concessioni delle capability; provider d'identità da decidere. | Regole di commessa o regole fiscali. |
| Anagrafiche commerciali | Identità e contatti di clienti/fornitori, relazioni commerciali. | Ruolo assunto su una specifica commessa o saldi contabili. |
| Veicoli | Identità del veicolo e relazioni con soggetti, con validità temporale da definire. | Pagante della commessa o avanzamento delle lavorazioni. |
| Pianificazione | Appuntamenti e impegni di capacità. Granularità delle risorse da validare. | Consumi definitivi, fatture o consuntivi tecnici. |
| Officina | Presa in carico, commessa, lavorazioni, consuntivi, chiusura tecnica e ruoli dei soggetti nell'intervento. Preventivo/autorizzazione qui collocati in via provvisoria. | Giacenze definitive, emissione fiscale, libro contabile. |
| Catalogo e condizioni | Articoli, prestazioni e condizioni commerciali applicabili. | Quantità a stock; riscrittura dei valori già concordati su una commessa. |
| Magazzino | Prenotazioni, movimenti, giacenze e disponibilità secondo regole approvate. | Esecuzione tecnica delle lavorazioni o condizioni fiscali della fattura. |
| Acquisti | Richieste e ordini ai fornitori, avanzamento dell'approvvigionamento. Coordinamento ricevimento con magazzino da definire. | Aggiornamento diretto delle giacenze di un altro modulo. |
| Fatturazione | Bozze, emissione e rettifiche dei documenti di addebito; copie storiche dei dati necessari. | Chiusura tecnica della commessa e registrazione contabile interna ad altro contesto. |
| Contabilità e tesoreria | Scritture, scadenze e incassi secondo regole validate. Confine interno tra contabilità e tesoreria ancora aperto. | Inventare l'esito operativo o modificare retroattivamente la fattura. |
| Documenti commerciali e sviluppi (confine da definire) | Concetti comuni di tipo, customizing, creazione diretta, sviluppi parziali/raggruppati e rettifiche guidate secondo D3–D11. Ownership concreta e collaborazione con Officina/Fatturazione da definire nella sintesi: non è un modulo tecnico approvato. | Assorbire tutte le regole di officina, magazzino e fiscalità in un motore universale. |
| Allegati e contenuti documentali | File, versioni, integrità e accesso ai contenuti; nome distinto dai documenti commerciali. | Decidere se una fattura o commessa sia valida: il significato resta nel dominio proprietario. |
| Reportistica | Proiezioni e letture autorizzate; controllo di gestione separabile per capability. | Duplicare l'autorità sui fatti o introdurre dipendenze obbligatorie nel flusso operativo. |
| Connettori | Traduzione dei contratti esterni, mappature e stato di sincronizzazione/riconciliazione. | Regole proprietarie del gestionale dentro il dominio; seconda autorità sui dati replicati. |

### Confini da verificare subito

- **Appuntamento ≠ commessa:** la creazione diretta è configurabile secondo D10–D11; nessun appuntamento o preventivo è universalmente obbligatorio. Le cardinalità specifiche restano da definire.
- **Sede ≠ magazzino:** il legacy riusa `warehouse` per la sede dell'agenda (E4). Non trasferire questa sovrapposizione nel modello nuovo.
- **Intestatario ≠ pagante ≠ destinatario fattura:** mantenere ruoli distinti, anche quando riferiscono lo stesso soggetto.
- **Prenotazione ≠ consumo ≠ fatturazione:** sono fatti separati; la transizione di uno non autorizza implicitamente gli altri.
- **Chiusura tecnica ≠ chiusura amministrativa ≠ riconsegna:** ordine e vincoli dipendono dalle regole da raccogliere.
- **Famiglia comune ≠ regole identiche:** commessa, preventivo, DDT e fattura appartengono al linguaggio dei documenti commerciali, ma mantengono significati e vincoli specifici. La struttura tecnica non deriva automaticamente dal nome `document` legacy.

## 5. Evidenze legacy consultate

Repository **`luigi-pelosi/smartdata`**, revisione **`c5d2ec85496bc2f5f6f3a41e7913b9e82ac2b18b`**. Consultazione in sola lettura, senza esecuzione del legacy né verifica con operatori. Gli intervalli di riga si riferiscono a questa revisione. Nessun codice/schema è copiato nel nuovo prodotto.

| ID | Percorso e intervallo | Osservazione circoscritta | Stato |
| --- | --- | --- | --- |
| E1 | `docs/manuale_agenda_appuntamenti_officina.md`, righe 35–57, 77–85, 148–160 | Il manuale descrive cliente obbligatorio, veicolo facoltativo, mantenimento del pagante e conversione dell'appuntamento in ODL con report dalle descrizioni. È documentazione del legacy, non prova runtime. | OL, da validare |
| E2 | `system/model/workshop/appointment.php`, righe 832–851, metodo `buildAppointmentQuery` | La query espone separatamente il cliente dell'appuntamento e quello associato al veicolo. Non dimostra da sola tutti i vincoli della GUI o il significato giuridico dell'associazione. | OL, da validare |
| E3 | `system/model/workshop/document.php`, righe 18–47, metodo `addDocument` | Il modello registra separatamente cliente, veicolo, società, warehouse, date previste/effettive di ingresso e uscita. Le cardinalità corrette e le regole di accettazione non si deducono dal solo schema. | OL, da validare |
| E4 | `docs/manuale_agenda_appuntamenti_officina.md`, righe 22–30, 39–48, 258–264 | Nell'agenda `Magazzino` è descritto come sede abilitata; il magazzino di riferimento preseleziona la sede. Segnale di ambiguità terminologica da non ereditare. | OL, da validare |
| E5 | `system/model/warehouse/movement.php`, righe 3–10 e 12–25 | Sono distinti tipi tecnici adjustment/transfer. Non prova una semantica di prenotazione o una formula di disponibilità: tali distinzioni derivano dal charter, non da queste righe. | OL, da validare |

## 6. Domande prioritarie per la discussione

**Q1 — Natura della commessa: chiarita in D3.** La commessa officina è già un ordine cliente, all'interno della famiglia dei documenti commerciali. Non introdurre un secondo ordine cliente obbligatorio né presumere una gerarchia commessa/ODL.

**Q2 — Lavorazione: parzialmente chiarita in D8.** L'associazione di prestazioni e ricambi alle lavorazioni è configurabile per tipo documento. Modalità precise, struttura delle attività e mantenimento del termine `report` restano da validare; non riproporre una scelta globale fissa.

**Q3 — Origine della commessa: chiarita in D10–D11.** Creazione diretta o provenienza obbligatoria dipendono dal customizing del workflow. L'obbligatorietà del veicolo è un requisito distinto ancora aperto, non deducibile dalla libertà di creazione.

Acquisiti i principi su documenti, workflow e rettifiche in D3–D11. Restano aperti: ruoli e più paganti; differenza proprietario/intestatario; risorse da pianificare; disponibilità/stock negativo; condizioni per riconsegna e dettagli dei residui. La sintesi collegata elenca le specifiche progettuali ancora da definire.

## 7. Registro delle decisioni

### D1 — Distinzione tra processo operativo e documento commerciale

**Voce storica superata da D3: non usare come definizione corrente.**

**Fonte:** Luigi Pelosi, proprietario del prodotto, nella discussione della fase 1. **Stato:** orientamento espresso dal proprietario; formulazione e conseguenze proposte ancora in discussione, non approvazione della fase o del dossier.

Il proprietario propone di intendere la commessa come processo di lavorazione/flusso operativo, anche nell'analogia con un processo industriale; il documento come entità del ciclo commerciale, ad esempio ordine cliente. Indica la fattura di vendita come esito commerciale della commessa conclusa.

La precedente proposta di sinonimia automatica commessa/ODL viene ritirata. Ordine cliente e ordine di lavoro non sono equiparati. Proposta conseguente: la commessa resta una risorsa operativa distinta, collegata ai documenti, non un documento che cambia tipo diventando fattura. La mappa dei contesti rimane preliminare e deve essere riallineata dopo aver chiarito chi possiede ordine cliente e preventivo.

Non sono ancora decisi: rapporto uno-a-uno o molti-a-molti tra commesse e documenti; fatturazione parziale/riepilogativa; obbligo dell'ordine cliente; gestione garanzia o lavori interni; stati di chiusura; termine tecnico definitivo della commessa. Non è approvata un'entità universale `Document` né un motore di workflow generico. Regole fiscali e contabili restano soggette a validazione specialistica.

### D2 — Famiglia comune di documenti commerciali e customizing per processo

**Voce storica precisata e superata da D3: l'ambiguità sull'ordine cliente è risolta.**

**Fonte:** successivo chiarimento di Luigi Pelosi, proprietario del prodotto. **Stato:** indirizzo concettuale espresso; dettaglio del modello ancora da validare. Questo chiarimento corregge l'interpretazione proposta in D1, non approva l'intero dossier.

Il proprietario chiarisce che anche la commessa di lavorazione è un documento commerciale. Il suo customizing differisce da quello di un documento di vendita ricambi; entrambi i percorsi conducono a un ordine cliente. Non è quindi approvata la separazione rigida tra commessa operativa e famiglia dei documenti commerciali proposta in D1. La dimensione operativa della commessa resta da rappresentare, ma non ne esclude la natura commerciale.

Proposta da discutere: famiglia comune `Commercial document`, con tipi/profili distinti e regole specifiche. L'eventuale nucleo condiviso non trasferisce le regole di officina, magazzino o fatturazione in un modulo universale. Customizing non equivale a fork per cliente, feature flag commerciale o possibilità di aggirare autorizzazioni e invarianti. Nessuna decisione su ereditarietà, tabelle, motore generico o cardinalità è presa.

**Ambiguità prioritaria:** «conduce a un ordine cliente» indica che la commessa è già un ordine cliente specializzato, oppure che è un documento precedente dal quale viene generato un ordine cliente distinto? Non si presume una conversione di identità né un rapporto uno-a-uno.

L'ambiguità sopra riportata è stata risolta da D3. D1 e D2 sono conservate come storia della discussione, non come definizioni attuali in contrasto con D3.

### D3 — Commessa come ordine cliente e sviluppi di documenti commerciali

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, chiarimento esplicito nella fase 1. **Stato:** DP sul significato concettuale; dossier complessivo ancora in bozza, regole fiscali non validate.

- La commessa officina è già un ordine cliente effettivo e un documento commerciale. Mantiene la specificità del processo operativo officina.
- I documenti commerciali possono avere customizing, personalizzazioni e workflow diversi ed essere collegati tra loro.
- Esempio configurabile officina: `Preventivo officina` (offerta al cliente) → `Commessa officina` (ordine cliente) → `Fattura vendita`, a conclusione della lavorazione.
- Esempio configurabile ricambi: `Preventivo ricambi` (offerta al cliente) → `Documento di trasporto (DDT)` → eventuale `Fattura differita`.
- Gli esempi non impongono percorsi universali né un ordine cliente separato nel percorso ricambi. Sono requisiti concettuali per la composizione futura, non ampliamento automatico della prima vertical slice.

**Conseguenza proposta per il modello:** distinguere il significato commerciale (offerta, ordine, trasporto, fattura), il tipo configurato (es. Preventivo officina), il suo ciclo di vita e gli sviluppi ammessi verso altri tipi. I nomi sono ancora proposti. Sviluppo documentale e semplice transizione di stato sono concetti distinti; creazione, trasferimento dei dati e preservazione della storia richiedono regole esplicite.

La famiglia comune non decide ereditarietà, schema dati o motore di workflow. La mappa dei contesti resta preliminare, in particolare per ownership di customizing, offerte e collegamenti; restano i vincoli del charter su moduli e autorità dei dati. Non si attribuiscono effetti di magazzino o contabili al solo nome del documento. Le condizioni fiscali per DDT e fatturazione differita saranno validate separatamente, senza dedurle dall'esempio di workflow.

**Domanda risolta in D4:** sono richiesti sviluppi parziali e raggruppamenti.

### D4 — Sviluppi parziali e raggruppamenti documentali

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risposta affermativa alla domanda su entrambe le modalità. **Stato:** DP sul requisito; non approvazione del dossier o delle specifiche fiscali.

- È possibile sviluppare soltanto alcune righe o parte delle quantità di un documento sorgente.
- È possibile raggruppare più documenti sorgente in un documento destinazione, come più DDT in una fattura differita, subordinatamente ai criteri di compatibilità ancora da definire.
- Non si deve vincolare il modello concettuale a relazioni uno-a-uno tra documenti.

**Proposte conseguenti, non ancora approvate nel dettaglio:** tracciare provenienza e quantità sviluppate a livello di riga; distinguere quantità sviluppata e residua per specifico passaggio documentale, senza confonderle con giacenza, consegna o consumo; preservare le provenienze multiple anche quando la destinazione accorpa righe. Una quantità può attraversare passaggi successivi (es. ordine → DDT → fattura): non è un unico contatore globale. Retry e concorrenza non devono creare sviluppi duplicati o superamenti non consentiti. Identità, unità di misura, storni, arrotondamenti e criteri di raggruppamento restano da definire.

**Domanda risolta in D5:** workflow configurabili entro vincoli inderogabili del sistema.

### D5 — Workflow configurabili e rettifiche compensative

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul requisito concettuale; dossier complessivo e regole fiscali restano da approvare/validare.

- Approvata la proposta di configurare, per ciascun tipo documento, destinazioni ammesse, condizioni e dati da riportare, entro vincoli del sistema non aggirabili dal customizing.
- Dove previsto da una configurazione corretta, i documenti completati, anche dopo un successivo sviluppo documentale, devono poter essere rettificati mediante altri documenti e/o movimenti di segno opposto.
- La reversibilità non è quindi esclusa dalla presenza di sviluppi successivi; condizioni ed effetti sui documenti collegati richiedono regole esplicite.

**Interpretazione progettuale proposta, coerente con charter §9:** rettifica compensativa tracciata, non cancellazione dello storico o ritorno indistinto a bozza. Collegare la rettifica all'origine e identificare gli effetti che compensa; non invertire automaticamente ogni effetto del documento. Correzione commerciale, reso fisico e rettifica contabile sono dimensioni distinte. Non si assume che qualsiasi tipo possa rettificare qualsiasi altro tipo, né che una rettifica economica produca automaticamente un movimento fisico. I tipi fiscali e i vincoli di emissione restano da validare con lo specialista.

**Questioni ancora aperte:** compensazione totale/parziale; limiti sulle quantità/importi già compensati; riallocazione dei residui; gestione dei collegamenti e degli sviluppi successivi; autorizzazioni e motivazioni; idempotenza e gestione delle compensazioni tra moduli. Il ripristino di una capacità di sviluppo non equivale automaticamente al ripristino di stock disponibile.

**Domanda risolta in D6:** rettifiche parziali ammesse.

### D6 — Storno parziale riferito alla riga di origine

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, che conferma la rettifica parziale ed esemplifica lo storno di una sola riga ricambio del documento originario. **Stato:** DP sul requisito; non approvazione dell'intero dossier né validazione fiscale.

- È possibile rettificare una singola riga senza stornare l'intero documento, mediante documenti e/o movimenti compensativi secondo D5.
- Il requisito di parzialità riguarda righe e quantità/importi applicabili; regole specifiche per ogni tipo restano da dettagliare.
- Il riferimento al documento originario identifica ciò che viene rettificato; non autorizza a cancellare o riscrivere silenziosamente la riga confermata.

**Proposta conseguente:** rappresentare un collegamento esplicito dalla riga di rettifica alla riga originaria e conservare storico, quota rettificata e residuo rettificabile, con controlli per evitare doppie compensazioni non consentite. Le altre righe mantengono validità salvo vincoli espliciti del processo. Eventuali ricalcoli di totali, sconti o altri valori dipendenti devono essere disciplinati, non ignorati. Effetti commerciali, fisici e contabili restano distinti.

**Domanda risolta in D7:** approvato il percorso guidato.

### D7 — Percorso guidato di rettifica degli sviluppi collegati

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, approva il percorso guidato proposto. **Stato:** DP sul comportamento richiesto; non approvazione dell'intero dossier né validazione fiscale.

Quando una riga ha già prodotto sviluppi successivi, il sistema deve mostrare documenti ed effetti coinvolti, proporre le compensazioni ammesse dal customizing e richiedere conferma. Non deve propagare storni indiscriminatamente. Restano la parzialità e la tracciabilità verso le righe originarie previste in D6, nonché la distinzione tra effetti commerciali, fisici e contabili di D5.

**Dettagli progettuali ancora proposti:** verificare autorizzazioni e residui al momento della conferma; rendere visibili eventuali blocchi e passi non completati; prevenire duplicazioni nei retry; registrare attore, motivazione ed esito. Non è promessa una transazione unica tra moduli o sistemi esterni: gestione di errori e recupero sarà definita nelle sezioni di affidabilità e integrazione.

Questo conclude il gruppo di chiarimenti su significato, customizing, sviluppi e rettifiche dei documenti commerciali, non l'intera fase 1. La struttura delle lavorazioni (Q2) è chiarita parzialmente in D8.

### D8 — Associazione delle righe alle lavorazioni configurabile per tipo documento

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul livello e sull'oggetto della configurazione; modalità dettagliate ancora proposte.

L'associazione di ricambi e prestazioni alle lavorazioni, anziché la loro gestione come righe della commessa senza legame obbligatorio, deve dipendere da un parametro nel customizing del tipo documento, in questo caso officina. Non è una regola globale fissa né una condizione codificata per singolo cliente.

**Modalità candidate da validare:** associazione obbligatoria, facoltativa oppure non utilizzata. La distinzione in tre modalità è una proposta dell'agente, non ancora confermata dal proprietario. Il requisito non definisce cardinalità, annidamenti o eventuali legami multipli.

**Vincoli progettuali proposti, coerenti con il charter:** validazione coerente lato server e GUI; conservazione delle provenienze negli sviluppi e nelle rettifiche; nessun doppio conteggio di righe o importi tra raggruppamenti e totali. La configurazione deve essere tipizzata, validata, versionata e sottoposta ad audit come richiesto dal charter §7.2; il comportamento sui documenti già esistenti resta da decidere, senza reinterpretazione silenziosa dello storico confermato.

**Domanda chiarita in D9:** non retroattività come default generale; applicazione retroattiva solo su richiesta esplicita. L'unità temporale indicata dal proprietario è la prossima operazione, non necessariamente soltanto la creazione di un nuovo documento.

### D9 — Decorrenza delle modifiche e retroattività esplicita

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP come principio generale di prodotto, espresso nel contesto del customizing. Non approva ogni possibile modifica retroattiva né il dossier completo.

- In generale e per default i cambiamenti non sono retroattivi.
- Valgono dalle prossime operazioni, salvo richiesta esplicita dell'utente di applicarli retroattivamente.
- La richiesta di retroattività deve essere distinta dalla modifica ordinaria: non è un effetto implicito del salvataggio di una configurazione.

**Correzione della proposta precedente:** non è ancora approvato che l'intero documento mantenga per sempre un'unica configurazione fissata alla nascita. Occorre distinguere dati/effetti già registrati, configurazione del documento e regole applicabili alle operazioni future, anche su documenti aperti. La decorrenza precisa per categoria di configurazione sarà definita senza reinterpretare automaticamente le operazioni passate.

**Salvaguardie progettuali proposte:** applicazione retroattiva autorizzata e delimitata a un insieme esplicito di oggetti/operazioni, con anteprima di impatti, validazione, conferma e audit delle versioni coinvolte. Una richiesta esplicita non supera vincoli di dominio, permessi o regole fiscali; per fatti confermati che richiedono rettifica si preserva lo storico tramite compensazioni secondo D5–D7, non mediante riscritture silenziose. Recupero degli errori e modalità di esecuzione restano da definire.

L'origine della commessa (Q3) viene chiarita in D10. Restano da discutere le modalità precise di associazione delle righe e gli altri termini della fase 1.

### D10 — Predecessori facoltativi e creazione diretta configurabile

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, con diagramma allegato alla discussione. **Stato:** DP sul requisito di creazione diretta e sulla notazione tratteggiata; nessuna approvazione complessiva del dossier.

- Il workflow nel customizing del tipo documento può consentire la creazione della commessa senza documenti precedenti, anche quando sono configurati sviluppi verso di essa.
- Un collegamento ammesso non rende automaticamente obbligatorio il documento sorgente: occorre distinguere possibilità di sviluppo e obbligo di provenienza.
- Nel diagramma, `Preventivo officina DAF`, `Preventivo officina SCANIA` e `Preventivo officina` confluiscono mediante un percorso tratteggiato in `Commessa (ordine cliente)`; segue una freccia continua verso `Fattura immediata`.
- Il proprietario specifica che il tratteggio rappresenta la non obbligatorietà del flusso: la commessa può essere creata direttamente. Il diagramma non dimostra che i tre preventivi siano richiesti insieme o che debbano essere raggruppati.

**Conseguenza proposta per il modello:** separare gli sviluppi consentiti tra tipi dalla regola di creazione del tipo destinazione (diretta ammessa oppure provenienza richiesta). Se in futuro più predecessori sono obbligatori, occorrerà definire esplicitamente alternative e requisiti congiunti; nessuna semantica AND/OR è dedotta da questo esempio. La creazione diretta non aggira permessi, dati obbligatori o invarianti del tipo documento.

**Limiti dell'interpretazione:** la freccia continua verso fattura non è interpretata come emissione automatica, immediatezza temporale o prova che fatturare sia l'unico esito ammesso: obbligatorietà, condizioni e avvio manuale/automatico restano da precisare. `Fattura immediata` è l'etichetta del tipo rappresentato, non una regola fiscale qui validata. Le etichette DAF e SCANIA esemplificano tipi configurati: non autorizzano dipendenze di codice da marchi o fork per cliente.

**Chiarimento successivo in D11:** non dedurre obblighi universali dal tipo fattura o dal percorso illustrato; il workflow del tipo documento governa i vincoli configurabili.

### D11 — Creazione indipendente e vincoli di workflow per tipo documento

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sull'estensione della configurabilità del workflow; nessuna approvazione complessiva del dossier.

Il proprietario chiarisce che i vincoli e i collegamenti di workflow sono configurabili nel customizing del tipo documento. Anche una fattura officina può essere creata senza derivare da preventivo, commessa o altro documento precedente, quando la configurazione lo consente. Non è ammessa come regola generale codificata «fattura officina richiede sempre commessa» né «ogni documento deve attraversare tutti i passi di un percorso».

Questo amplia D10 dalla commessa agli altri tipi documento: gli esempi di flusso mostrano configurazioni possibili, non sequenze universali obbligatorie. Non occorre richiedere conferma separata della creazione diretta per ciascun tipo.

**Ambito della configurabilità:** provenienze, destinazioni, obbligatorietà e condizioni del workflow. Le modalità concrete, incluso l'eventuale avvio automatico, saranno descritte nel modello di customizing senza presumere automatismi non specificati. «Svincolata da tutto» indica assenza di predecessori documentali obbligatori, non assenza di dati necessari, autorizzazioni, tenant context o vincoli fiscali/contabili. Rimangono i limiti di sicurezza e validità già concordati in D5.

**Questione rinviata alla progettazione degli effetti:** per un documento creato direttamente, stabilire quali effetti operativi sono previsti e quali fatti sono soltanto riferiti; non dedurre un consumo di magazzino o una lavorazione eseguita dalla sola creazione della fattura. Il punto non richiede di irrigidire il workflow.

### D12 — Quote della commessa a carico di più soggetti

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul requisito commerciale; nessuna approvazione complessiva del dossier o delle modalità fiscali.

Una singola commessa può avere quote a carico di più soggetti. Esempio confermato: copertura parziale della garanzia di casa madre, con manodopera a carico del cliente e restante parte coperta da garanzia. L'esempio non stabilisce che la manodopera sia sempre esclusa dalla garanzia né che la casa madre coincida sempre con il soggetto destinatario dei documenti di addebito.

**Conseguenze progettuali proposte:** rappresentare l'attribuzione economica alle quote di righe/prestazioni/ricambi senza duplicare l'intervento operativo o i consumi fisici. Distinguere soggetto a carico, fonte della copertura, destinatario fattura e soggetto che effettua il pagamento; non dedurre l'identità di questi ruoli. Gli sviluppi commerciali devono conservare l'attribuzione delle quote e prevenire doppi addebiti. Modalità di documentazione e regolamento della garanzia restano da validare, senza presumere fatture separate o una specifica procedura di rimborso.

**Domanda risolta in D13:** soggetto a carico unico per riga per default; ripartizione parziale ammessa dal customizing del tipo documento.

### D13 — Default di riga e ripartizione configurabile come regola generale

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul requisito e sul principio generale di configurabilità; non approvazione del dossier completo.

- Di default ogni riga ha il proprio soggetto a carico. Righe diverse dello stesso documento possono avere soggetti differenti.
- La singola riga può essere ripartita parzialmente tra più soggetti se il customizing del tipo documento lo permette.
- È una regola generale, non una particolarità della garanzia o dell'officina: i comportamenti variabili devono essere espressi nella configurazione del tipo pertinente, senza eccezioni hardcoded per cliente, marchio o caso commerciale.
- Il principio opera entro i vincoli inderogabili già acquisiti: configurare non equivale ad aggirare sicurezza, isolamento, integrità o validità fiscale/contabile.

**Conseguenze progettuali proposte:** configurazione esplicita con default sicuro, validazione coerente lato server e GUI e conservazione delle attribuzioni negli sviluppi/rettifiche. Quote coerenti con la base ripartibile, senza doppi addebiti; gestione di arrotondamenti ed eventuali residui da definire. La ripartizione economica non duplica la quantità fisica consumata. Non si fissano ancora ripartizione percentuale/per importo/per quantità, algoritmi o campi tecnici.

La proposta di congelare ogni documento alla configurazione di nascita rimane non approvata: la decorrenza segue D9. Non occorre richiedere di nuovo se la ripartizione sia configurabile per ogni specifica categoria di documento.

### D14 — Customizing esclusivamente societario

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul perimetro organizzativo dei customizing; nessuna approvazione complessiva del dossier.

I customizing funzionano soltanto a livello societario (`Legal entity`). Nel perimetro qui discusso, tipi documento, regole e workflow configurati appartengono alla società. Non sono previsti customizing di tenant o di sede né una gerarchia di ereditarietà/override tenant → società → sede. La precedente proposta di configurazione comune al tenant con differenze locali non è adottata.

**Conseguenze progettuali proposte:** risolvere la configurazione nel contesto della società autorizzata, all'interno del tenant; le sedi di quella società usano il medesimo customizing, senza override locali. Società distinte possono avere customizing indipendenti anche nello stesso tenant. Non si deduce da questo che tutte le altre categorie di impostazioni, entitlement, feature flag o permessi abbiano necessariamente lo stesso scope: sono meccanismi distinti secondo il charter §7.2.

Decorrenza e retroattività seguono D9. Eventuali modelli iniziali o copia esplicita tra società sono questioni separate, non ereditarietà implicita e non funzionalità già approvate. Struttura società/sede/magazzino e ownership dei documenti saranno dettagliate nella fase organizzativa.

### D15 — Gerarchia società, sede e magazzino

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, definisce esplicitamente `società–sede 1:N` e `sede–magazzino 1:N`. **Stato:** DP sulle relazioni organizzative; nessuna approvazione complessiva del dossier.

- Una società può avere più sedi; ciascuna sede appartiene a una sola società.
- Una sede può avere più magazzini; ciascun magazzino appartiene a una sola sede.
- La società di appartenenza del magazzino è determinata tramite la sua sede; non viene introdotta una seconda appartenenza societaria indipendente.
- Non è prevista una relazione di appartenenza molti-a-molti tra sedi e magazzini. Eventuali servizi logistici o trasferimenti tra sedi sono processi distinti, non ulteriori appartenenze.

La cardinalità minima necessaria per creare o attivare una società/sede non si deduce dalla sola notazione 1:N; non si impone qui la creazione immediata di sedi o magazzini fittizi. La relazione tenant/società e le regole di accesso restano da dettagliare. Il customizing continua a essere esclusivamente societario secondo D14.

**Domanda sul contesto operativo chiarita in D16:** sede unica in testata e magazzini delle righe appartenenti a tale sede.

### D16 — Sede del documento e magazzini di riga

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto. **Stato:** DP sul vincolo organizzativo del documento; nessuna approvazione complessiva del dossier.

- La sede è scelta in testata ed è unica per il documento; non può variare tra le righe.
- Il magazzino può variare tra le righe, ma deve appartenere alla sede scelta in testata.
- La società di riferimento della sede è univoca secondo D15; nessuna riga può introdurre una diversa sede/società tramite il magazzino.

**Conseguenze progettuali proposte:** validare lato server l'appartenenza del magazzino alla sede e i relativi permessi, coerentemente con la selezione offerta dalla GUI. Se si cambia la sede di una bozza con righe esistenti, i magazzini vanno rivalidati senza riassegnazioni silenziose o perdita di provenienze. Le condizioni per cambiare la sede non sono ancora approvate. Non si deduce l'obbligo di assegnare un magazzino a ogni tipo di riga (es. note o prestazioni).

L'ammissibilità dei raggruppamenti tra sedi della stessa società è chiarita in D17. Resta da progettare il trattamento della provenienza: non si possono copiare come magazzini operativi di destinazione magazzini estranei alla sede di testata.

### D17 — Raggruppamenti nella stessa sede per default

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma la proposta precisa: «di default raggruppiamo solo documenti della stessa sede, lasciando l'eventuale raggruppamento tra sedi della stessa società a un'abilitazione esplicita nel customizing». **Stato:** DP su default e opzione; non approvazione complessiva del dossier.

- Default: raggruppamento di documenti della stessa sede.
- Raggruppamento tra sedi diverse della stessa società soltanto se esplicitamente abilitato nel customizing societario del tipo documento.
- L'abilitazione non introduce override di sede, non autorizza raggruppamenti tra società differenti e non elimina ulteriori controlli di compatibilità e autorizzazione.
- Resta valida D16: sede unica in testata del documento destinazione; eventuali magazzini operativi di riga appartengono a quella sede.

**Dettagli progettuali ancora aperti:** scelta della sede destinazione, conservazione della provenienza originale delle righe, distinzione tra riferimento storico al magazzino sorgente e magazzino operativo della destinazione. Il raggruppamento non implica un trasferimento fisico né duplicazione dei movimenti già effettuati. Questi dettagli non sono approvati dalla sola conferma del default.

### D18 — Condivisione delle controparti nel perimetro del cliente

**Fonte:** Luigi Pelosi, proprietario del prodotto, descrive Beta Group con due tenant separati corrispondenti a società diverse, che devono condividere la base delle anagrafiche delle controparti. **Stato:** DP sul requisito di condivisione selettiva e isolamento dagli altri clienti; terminologia e soluzione architetturale PR da approvare.

- Società/ambienti separati dello stesso cliente devono poter condividere le anagrafiche delle controparti.
- Non devono condividerle con tenant di clienti estranei.
- La condivisione richiesta riguarda le anagrafiche: non autorizza condivisione automatica di documenti, saldi, condizioni commerciali, permessi o customizing.

**Disallineamento terminologico da risolvere:** il charter §8 usa tenant per il cliente contrattuale e prevede società al suo interno; il proprietario usa qui tenant per gli ambienti societari separati. Non trattare le due definizioni come già equivalenti né cambiare il charter silenziosamente.

**Proposta raccomandata, non ancora approvata:** mantenere il tenant come perimetro del cliente (Beta Group), con società/ambienti societari isolati al suo interno e un'anagrafica comune di controparte. Distinguere i dati identificativi condivisi dalle estensioni/relazioni commerciali possedute da ciascuna società. Stessa controparte può essere cliente, fornitore o entrambi con relazioni societarie distinte. Accesso al nucleo comune esplicito per ruolo, non automatico per ogni utente del tenant; modifiche tracciate e nessuna riscrittura dei dati storici dei documenti. L'elenco dei campi condivisi e delle regole di modifica resta da decidere.

**Alternativa se i tenant societari devono rimanere confini di sicurezza autonomi:** introdurre un perimetro cliente/gruppo superiore e un servizio/contesto anagrafico condiviso mediante concessioni esplicite ai tenant partecipanti. Nessun accesso indiscriminato tra tenant, nessun matching su nome o partita IVA come autorizzazione. Membership, amministrazione della condivisione e separazione futura richiedono regole dedicate. Questa alternativa richiede una revisione esplicita delle definizioni e dei criteri di isolamento del charter, non una deroga implicita alle query tenant-scoped.

**Chiarimento successivo in D19:** le società possono essere gestite sotto un'unica amministrazione Beta Group. Rimane una proposta da consolidare la terminologia tecnica tenant/gruppo; non è deciso il livello fisico dei database.

### D19 — Amministrazione unitaria e destinazioni aggiuntive della controparte

**Fonte:** Luigi Pelosi, proprietario del prodotto, conferma che le società possono essere gestite sotto un'unica amministrazione Beta Group e chiede come consentire a B di aggiungere destinazioni rispetto all'anagrafica generale censita da A. **Stato:** DP sulla possibilità di amministrazione unitaria; modello delle destinazioni PR da approvare.

**Proposta:** identità della controparte comune al perimetro del cliente/gruppo, con destinazioni condivise e destinazioni societarie aggiuntive. B può aggiungere destinazioni riservate al proprio ambito senza duplicare la controparte o alterare automaticamente le destinazioni comuni. Gli utenti autorizzati di B vedono le destinazioni comuni applicabili più quelle locali a B; A non vede quelle di B per il solo fatto di condividere la controparte. Eventuali amministratori di gruppo accedono secondo permessi espliciti.

Creazione dell'identità da parte di A non implica proprietà esclusiva di A sull'anagrafica condivisa. Ogni destinazione deve avere un ambito e un riferimento stabile; distinguere destinazione commerciale/consegna della controparte dalle sedi organizzative di Beta Group definite in D15.

**Estensioni ancora proposte:** pubblicazione/promozione esplicita di una destinazione locale al livello comune, con autorizzazione, controllo duplicati e audit; preferenze o abilitazioni societarie riferite a una destinazione comune senza riscriverne i dati. Niente copie locali silenziose dello stesso indirizzo per simulare override. Una destinazione può essere disattivata per nuovi utilizzi senza perdere i riferimenti storici; i dati riportati su documenti confermati non si aggiornano implicitamente al variare dell'anagrafica.

**Default confermato in D20:** nuove destinazioni societarie; condivisione nel gruppo soltanto esplicita e autorizzata. Preferenze locali, gestione duplicati e disattivazione restano dettagli proposti, non approvati implicitamente.

### D20 — Destinazioni societarie per default, condivisione esplicita

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Esatto» alla proposta di rendere le nuove destinazioni societarie per default e comuni soltanto per scelta esplicita. **Stato:** DP sul default e sull'azione di condivisione; non approvazione dell'intero dossier.

- Una nuova destinazione è riservata alla società che la censisce, nel perimetro della controparte condivisa.
- Diventa comune al gruppo solo mediante scelta esplicita autorizzata, non per il semplice salvataggio.
- L'accesso resta soggetto a permessi; nessuna condivisione con clienti/gruppi estranei.

La conferma non definisce automaticamente l'intera matrice di campi comuni/locali, i permessi di modifica dei dati identificativi condivisi, le copie/duplicati o la revoca della condivisione. Questi aspetti restano da discutere. La condivisione dei dati non modifica lo scope societario dei customizing.

**Domanda risolta in D21:** modifica dell'anagrafica consentita soltanto a chi possiede il permesso specifico.

### D21 — Permesso specifico di modifica dell'anagrafica

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto: «solo chi ha permesso specifico può editare l'anagrafica». **Stato:** DP sul requisito di autorizzazione, nel contesto dell'anagrafica comune; non approvazione dell'intero dossier.

La modifica dell'anagrafica richiede un permesso specifico. La possibilità di consultare o utilizzare una controparte, o di operare in una società del gruppo, non conferisce implicitamente il diritto di modificarne i dati comuni. Il permesso non è dedotto dal solo nome del ruolo o dall'appartenenza all'amministrazione del gruppo.

**Conseguenze progettuali proposte, coerenti con il charter:** verifica lato server dell'azione e del perimetro della controparte, con isolamento dagli altri clienti; modifiche tracciate e indicazione dell'impatto sui dati condivisi. La conferma non definisce nome tecnico del permesso, ruoli assegnatari o facoltà di concederlo. Permessi di creazione, disattivazione, modifica delle estensioni societarie e pubblicazione delle destinazioni restano da dettagliare senza presumere che siano equivalenti al permesso di modifica dell'anagrafica comune.

Questo conclude il chiarimento sulla modifica dell'anagrafica comune; la matrice completa dei permessi sarà trattata nella sezione accessi. La successiva D22 risolve il confine tenant/gruppo: le alternative di D18–D19 restano storia della discussione.

### D22 — Tenant come cliente/gruppo con società interne

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma espressamente «tenant = Beta Group», con più società interne, anagrafiche comuni ed estensioni societarie riservate. **Stato:** DP sul modello organizzativo logico; non approvazione del dossier completo o della topologia fisica.

- Il tenant identifica il cliente/gruppo contrattuale, non ciascuna società separatamente.
- Il tenant può comprendere più società, gestibili sotto un'unica amministrazione. Le società non diventano tenant separati nel modello scelto.
- Le controparti comuni appartengono al perimetro del tenant; estensioni e destinazioni societarie riservate seguono D19–D20.
- Tra tenant di clienti differenti non esiste condivisione automatica di anagrafiche o accesso ai dati.
- Restano validi customizing esclusivamente societario, gerarchia società–sede–magazzino e permessi specifici di modifica dell'anagrafica.

L'alternativa di tenant societari con un ulteriore livello gruppo descritta in D18 non è adottata. Non occorre modificare la definizione del charter §8, con cui la decisione è coerente. Non sono decisi database fisici separati/condivisi, provider di identità, cardinalità minime di attivazione o accesso automatico a tutte le società per ogni membro del tenant.

### D23 — Accessi multisocietari con autorizzazioni esplicite

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma la proposta di un utente abilitabile a più società dello stesso tenant, soltanto su autorizzazione esplicita, con ruoli/permessi diversi per società e limitazioni per sede/magazzino. **Stato:** DP sul modello di accesso; non approvazione complessiva del dossier.

- L'utente può operare in più società del proprio tenant, ma soltanto in quelle autorizzate.
- Ruoli e permessi possono differire tra società.
- L'ambito autorizzato può essere limitato a sedi e magazzini.
- La sola appartenenza al tenant non concede accesso automatico a tutte le società o a tutti i loro dati.
- Il diritto di modifica dell'anagrafica comune resta soggetto al permesso specifico di D21 e al relativo perimetro.

**Dettagli ancora da progettare:** catalogo e assegnazione dei ruoli, autorità di concessione/revoca, combinazione di scope, gestione delle sessioni e revoca efficace. La conferma non decide provider identity, ruoli predefiniti, accessi tra tenant o facoltà amministrative illimitate. La verifica lato server su azione e risorsa rimane un requisito del charter.

### D24 — Composizione delle capability differenziata per società

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma che due società dello stesso tenant possono utilizzare moduli diversi, incluso l'esempio di contabilità Enginia360 per A e contabilità esterna per B. **Stato:** DP sulla differenziazione societaria; non approvazione del catalogo commerciale o dei profili proposti.

- La composizione delle capability può variare tra società dello stesso tenant.
- L'abilitazione o l'uso di un modulo da parte di una società non ne comporta automaticamente l'attivazione nelle altre.
- Contabilità interna ed esterna possono coesistere nel tenant, riferite a società distinte.

**Conseguenze progettuali proposte, coerenti con charter §7.2–7.3:** risolvere capability attive e sistema autorevole nel contesto societario autorizzato; UI, endpoint, job e integrazioni coerenti con tale composizione. Distinguere entitlement contrattuale del tenant, attivazione societaria, customizing e autorizzazione dell'utente. Non sono decisi prezzi, licenze per società, catalogo vendibile, deleghe di attivazione o assegnazione automatica di un profilo. Anagrafiche condivise ed estensioni societarie non devono introdurre una doppia autorità implicita quando un ERP esterno è coinvolto: ownership e sincronizzazione saranno definite nella matrice dedicata.

La conferma non risolve quali integrazioni siano effettivamente usate dai piloti né il sistema autorevole di ogni dato. I tre profili illustrativi restano proposte da discutere.

### D25 — Autorità dei dati configurabile per capability

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma la scelta per capability tra Enginia360 e gestionale esterno, anche oltre la sola contabilità. **Stato:** DP sul principio; non approvazione di un'integrazione concreta o del dossier completo.

- Per una società il gestionale esterno può essere autorevole soltanto sulla contabilità oppure anche su emissione fatture, catalogo e anagrafiche, lasciando a Enginia360 le capability operative concordate.
- Per ciascun insieme di dati e processo deve esistere un unico sistema autorevole dichiarato; eventuali copie nell'altro sistema sono sincronizzate e non diventano una seconda autorità.
- La scelta non è necessariamente uniforme per tutte le società del tenant e non richiede fork di codice per cliente.

**Limiti ancora da progettare:** confini precisi dei dati e delle transizioni, mappature identificative, verso/frequenza delle sincronizzazioni, comportamento in indisponibilità, conflitti e riconciliazione secondo charter §7.3. Non è confermata una specifica granularità per campo, né l'abilitazione tecnica di ogni combinazione immaginabile.

**Chiarito in D26:** autorità unica del nucleo comune a livello tenant distinta dall'autorità sui dati societari. Contratti e protocolli di sincronizzazione restano da progettare.

### D26 — Autorità del nucleo comune distinta dalle relazioni societarie

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, approva il modello dopo l'esempio Beta Group/Trasporti Rossi. **Stato:** DP sul principio di separazione delle autorità; non approvazione del dossier completo o scelta di un ERP concreto.

- L'identità della controparte è condivisa nel tenant, con un unico sistema autorevole designato per il nucleo comune: Enginia360 oppure un sistema esterno.
- Le relazioni e i dati societari possono avere autorità distinta per società e insieme di dati, senza duplicare l'identità condivisa.
- Un ERP autorevole sui dati di B non può per questo sovrascrivere il nucleo comune o i dati locali di A.
- Gli altri sistemi ricevono copie sincronizzate, con mappature dei propri identificativi; un aggiornamento nel sistema non autorevole non diventa implicitamente un aggiornamento comune.

L'esempio usa Enginia360 come autorità comune, A con contabilità interna e B con fatturazione/contabilità esterne; questi sono valori illustrativi, non una configurazione definitiva per tutti i clienti. Denominazione, identificativi fiscali e sede legale sono esempi di dati comuni; codici e condizioni commerciali sono esempi di dati societari. La matrice precisa dei campi non è approvata implicitamente.

**Proposta di gestione delle difformità illustrata nell'esempio:** segnalazione della differenza ed eventuale richiesta di modifica al sistema autorevole, senza sovrascrittura automatica. Approvazioni, workflow e contratto tecnico delle richieste sono ancora da definire. I documenti confermati conservano i dati storici; nessuna propagazione retroattiva silenziosa.

### D27 — Continuità con coda e chiusure subordinate a conferma

**Fonte:** Luigi Pelosi accetta la coda persistente e conferma il default discusso nella sezione 7 della matrice capability. **Stato:** DP sul comportamento, non implementazione.

Registrare richieste persistenti con esiti visibili e ripresa controllata; distinguere registrazione locale e conferma esterna. Per default bloccare le chiusure definitive che richiedono conferma esterna. Deroghe soltanto abilitate dal customizing societario, soggette a permesso specifico e tracciate; non simulano conferme né aggirano invarianti inderogabili. Operatività fisica e stock negativo non sono implicitamente autorizzati.

### D28 — Perimetro iniziale della vertical slice

**Fonte e conferma:** Luigi Pelosi approva la proposta del percorso minimo commessa/prestazione/ricambio/prenotazione/consumo, con destinazione interna (fattura/scrittura) oppure esterna (connettore simulato con coda e recupero). **Stato:** DP sul perimetro di discovery della slice; non autorizzazione a implementare prima dell'approvazione del dossier.

Nello scenario minimo si usa un solo soggetto a carico. Ripartizioni e garanzia sono rinviate a incrementi successivi, senza eliminare i requisiti confermati in D12–D13 o rendere incompatibile il modello futuro. Restano i criteri trasversali del charter: isolamento tenant, distinzione intestatario/pagante, autorizzazioni, idempotenza, arrotondamenti espliciti e diagnosi degli errori. Le regole fiscali/contabili richiedono validazione specialistica; nessuna emissione fiscale reale è approvata.

### D29 — Prelievo, preparazione, installazione e rientro della carcassa

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, richiede momenti distinti e descrive come esempio il prelievo dei componenti dedicati a una lavorazione, il deposito in un'area di preparazione e il successivo ritiro da parte del meccanico per l'installazione. **Stato:** DP sulla distinzione dei fatti e sul rientro del particolare sostituito; organizzazione fisica e regole specifiche ancora da definire.

- Il prelievo non coincide con il consumo/installazione. La proposta precedente di considerarli lo stesso fatto viene ritirata.
- Un componente prelevato può restare in un'area dedicata, assegnato alla lavorazione, prima di essere ritirato dal tecnico e installato. L'esempio non rende obbligatoria questa area per ogni flusso.
- Ritiro da parte del tecnico e installazione non sono automaticamente lo stesso fatto o lo stesso istante.
- La carcassa è il particolare sostituito inutilizzabile che rientra: non è il componente nuovo non utilizzato e non può essere trattata come suo reso disponibile.

**Proposta conseguente:** tracciare separatamente prenotazione, prelievo/collocazione in preparazione, eventuale consegna al tecnico, installazione/consumo, reso del nuovo inutilizzato e rientro della carcassa. Collegare i fatti alla commessa/lavorazione e alle righe pertinenti, con effetti idempotenti propri. Non presumere che ogni ricambio richieda carcassa o serializzazione.

La picking list è proposta come lista/documento di prelievo, distinta dall'area fisica di preparazione. Il termine usato dal proprietario per l'esempio non decide se l'area sia ubicazione interna, magazzino distinto o altro modello logistico. Un passaggio interno non deve ridurre automaticamente la quantità fisica totale nel perimetro che ancora contiene il componente; momento e perimetro dei movimenti/valorizzazioni restano da progettare.

**Questioni aperte:** destinazione e identificazione della carcassa, obbligo e tempi di rientro, vincoli sulle chiusure, disponibilità del componente in preparazione, gestione parzialità e mancato utilizzo. Il rientro della carcassa non implica automaticamente reso al fornitore, rimborso, rifiuto o obbligo legale specifico. L'impatto sul perimetro della slice va aggiornato e validato senza trasformare l'esempio in un magazzino completo.

### D30 — Politica di restituzione carcassa nel customizing del tipo documento

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, precisa che chi prepara il customizing del tipo documento decide la politica di restituzione della carcassa. **Stato:** DP sulla responsabilità configurativa; non approvazione di un default specifico o dell'intero dossier.

La politica di restituzione è definita nel customizing societario del tipo documento, non da una regola universale fissa. Il chiarimento risolve dove si decidono obbligatorietà, tempi e conseguenze sul workflow/chiusura; i valori concreti restano da definire per il tipo configurato. Non imporre per default un blocco o una restituzione successiva alla chiusura non approvati dal proprietario.

**Parametri candidati, ancora da dettagliare:** applicabilità della restituzione, obbligo, momento richiesto, vincoli di completamento/sviluppo, gestione delle mancate restituzioni ed eventuali eccezioni autorizzate. Non sono un catalogo già approvato. Restano invarianti la distinzione tra carcassa e nuovo inutilizzato, la registrazione veritiera dei fatti e la tracciabilità. Configurazione, versionamento e non retroattività seguono D9 e D14.

Non richiedere una politica globale di restituzione ignorando la configurabilità già confermata; riportare il punto nel catalogo del customizing e proseguire con i confini del percorso minimo.

### D31 — Base architetturale del primo incremento

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, conferma la proposta «monolite modulare, contratti espliciti e PostgreSQL inizialmente unico». **Stato:** DP sulla base architetturale, non approvazione del dossier completo o autorizzazione a implementare.

Moduli con responsabilità e dati propri, comunicazione mediante API applicative esplicite, nessun accesso diretto alle tabelle altrui. PostgreSQL inizialmente unico non annulla isolamento tenant/società o ownership dei moduli. La struttura dettagliata della solution, il catalogo definitivo dei moduli, i test di architettura e i meccanismi specifici rimangono proposte nel documento 05; non sono già esercitati. Nessuna adozione implicita di microservizi, broker obbligatorio o entità documento universale.

Nessuna modifica al charter, al runtime o al flag di approvazione del dossier.

### D32 — Riepilogo commerciale nella prima slice; marginalità rinviata

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto: «Procedi con il riepilogo commerciale, la determinazione della marginalità la vediamo in un secondo momento». **Stato:** DP sul significato del risultato economico minimo, non approvazione del dossier completo o autorizzazione a implementare.

Per la prima slice il risultato è il riepilogo commerciale: imponibile delle righe al netto degli sconti, imposte e totale a carico del soggetto previsto nello scenario. Non rappresenta margine, utile o costo del venduto. Determinazione dei costi di ricambi/manodopera, valorizzazioni per marginalità e calcolo del margine sono rinviati a un incremento successivo; non si introduce neppure una marginalità provvisoria in questo perimetro.

D01-Q01 è risolta; il criterio relativo al significato del risultato di B05 è soddisfatto. Restano da concordare i parametri e gli arrotondamenti dello scenario tecnico e da sottoporre allo specialista le regole per uso reale. Nessun obbligo di implementare l'intero ciclo passivo per ottenere il riepilogo commerciale. Le altre domande di D01, i gate implementativi e la validazione fiscale restano aperti.

### D33 — Area di preparazione facoltativa nel customizing societario

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto: «Ok va bene ma non è un vincolo utilizzare l’area di preparazione. Meglio permettere al gestore di sistema di deciderlo nel customizing societario». **Stato:** DP sul comportamento configurabile, non approvazione complessiva del dossier o autorizzazione implementativa.

Il gestore di sistema autorizzato decide nel customizing della società se utilizzare l'area di preparazione. Nessuna obbligatorietà globale, ereditarietà tenant o override di sede è introdotto. L'esempio con area rappresentata da un'ubicazione dello stesso magazzino è accettato, non imposto a tutte le società.

Con area abilitata si traccia il passaggio nell'ubicazione di preparazione, mantenendo il componente in giacenza e assegnato alla commessa. Senza area il prelievo non richiede un transito fittizio in tale ubicazione: prelievo e installazione/consumo restano fatti distinti e riconciliabili, anche se ravvicinati. La sola preparazione interna non riduce il valore aggregato del magazzino; criteri di valorizzazione e rilevazione contabile restano separati e non sono approvati implicitamente.

Il customizing rispetta sede di testata, permessi, audit, assenza di doppi scarichi e non retroattività predefinita. La copertura della prenotazione nel caso minimo è chiarita in D34. La tracciabilità minima della carcassa è chiarita in D35. Restano ulteriori parametri del caso dimostrativo; D01 non è conclusa.

### D34 — Prenotazione solo con disponibilità sufficiente nella prima slice

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Va bene. Andiamo avanti» alla proposta di consentire il ricambio nella commessa anche se manca, ma prenotarlo soltanto quando la disponibilità è sufficiente. **Stato:** DP limitata alla configurazione dimostrativa, senza autorizzazione implementativa o approvazione complessiva del dossier.

**D34 — Prenotazione coperta da disponibilità nel caso minimo:** il ricambio può essere inserito nella commessa anche quando non è disponibile, ma la prenotazione riesce soltanto se la disponibilità impegnabile è sufficiente. Il rifiuto è motivato e non blocca automaticamente tutta la commessa. Dopo il ricevimento e la disponibilità del materiale si può riprovare. Richieste strutturate in attesa di approvvigionamento rinviate. Decisione limitata allo scenario dimostrativo: non approva una politica universale di stock negativo o ulteriori blocchi di workflow.

Il controllo deve essere coerente anche con prenotazioni concorrenti e retry: nessuna quantità impegnata oltre la disponibilità ammessa nello scenario. Il rifiuto di prenotazione non è un ordine di acquisto né una prenotazione futura già coperta. Le politiche per prelievi/consumi in assenza di stock non sono dedotte da questa conferma.

### D35 — Identificazione minima della carcassa nella prima slice

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Perfetto» alla proposta di tracciabilità minima della carcassa. **Stato:** DP sul caso iniziale, non approvazione complessiva del dossier o autorizzazione implementativa.

**D35 — Tracciabilità minima della carcassa confermata:** registrare commessa e lavorazione di provenienza, collegamento alla riga del ricambio installato, descrizione e quantità del particolare rientrato, data e operatore di ricezione. Per il primo scenario non si introducono un catalogo separato delle carcasse o una matricola obbligatoria. Il rientro non aumenta la disponibilità dei ricambi nuovi; politica di restituzione e conseguenze di workflow restano nel customizing societario del tipo documento (D30).

La conferma non stabilisce valorizzazione, rimborso fornitore, smaltimento o ulteriori obblighi legali. La destinazione fisica del caso iniziale è chiarita in D38. La configurazione dimostrativa dei vincoli di restituzione è chiarita in D39, senza imporre una politica universale.

### D36 — Campi anagrafici minimi comuni e societari

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Perfetto» alla proposta di una controparte aziendale minima con dati comuni e una destinazione societaria riservata. **Stato:** DP limitata al primo scenario, non approvazione del dossier completo o autorizzazione implementativa.

**D36 — Controparte aziendale minima:** per il primo scenario, dati comuni al tenant = ragione sociale, identificativo fiscale e indirizzo della sede legale; dati societari = una destinazione operativa aggiuntiva riservata alla società che la registra, salvo condivisione esplicita autorizzata. Dati esclusivamente sintetici; nessuna definizione di obbligatorietà fiscale o catalogo anagrafico completo.

Le società A e B usano la medesima identità senza accesso automatico alle destinazioni locali altrui. Restano validi isolamento fra tenant, permesso specifico di modifica (D21), autorizzazioni contestuali (D23) e autorità unica sul nucleo comune (D26). La conferma non sceglie formato/validazione degli identificativi fiscali, deduplicazione, ruoli nominali o permessi di pubblicazione/revoca nel dettaglio. Nessun dato identificativo reale è richiesto o pubblicato.

### D37 — Chiusura tecnica durante indisponibilità del gestionale esterno

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Confermo» alla proposta di separare chiusura tecnica e amministrativa nel caso iniziale. **Stato:** DP sullo scenario esterno simulato; non autorizzazione implementativa, approvazione complessiva del dossier o prova di compatibilità con un ERP reale.

**D37 — Chiusura tecnica e amministrativa separate nel primo scenario esterno:** a lavorazioni concluse e requisiti locali configurati soddisfatti, la chiusura tecnica è consentita anche se il gestionale esterno è indisponibile. La richiesta amministrativa è conservata nella coda persistente; stato visibile «completata tecnicamente — in attesa di conferma amministrativa». La chiusura amministrativa resta bloccata fino alla conferma dell'esito di business richiesto, non al solo invio riuscito. Un rifiuto rimane visibile e richiede riconciliazione, preservando i fatti tecnici già avvenuti. Nessuna autorizzazione implicita a incasso, riconsegna del veicolo o deroghe ai vincoli configurati.

Sono preservati D27 per deroghe configurate/autorizzate/tracciate e D30 per vincoli della carcassa. Esiti incerti non sono conferme; nessuna cancellazione dei fatti locali per nascondere un rifiuto esterno. Gli ulteriori comportamenti fisici durante un disservizio restano decisioni separate.

### D38 — Ubicazione dimostrativa per la carcassa ricevuta

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Va bene» alla proposta di ubicazione dedicata ai particolari sostituiti. **Stato:** DP limitata al primo scenario; non approvazione complessiva del dossier o autorizzazione implementativa.

**D38 — Destinazione dimostrativa della carcassa:** collocare il particolare sostituito ricevuto in un'ubicazione dedicata, separata dai ricambi nuovi e senza disponibilità vendibile. Nessuna valorizzazione monetaria o gestione dello smaltimento è introdotta in questa fase. È una configurazione del primo scenario, non un vincolo universale; restano validi sede/magazzino autorizzati e customizing societario.

O01 del documento 09 è risolta. La conferma non introduce un catalogo separato delle carcasse, una matricola obbligatoria, recuperi di valore o obblighi di smaltimento. I vincoli dimostrativi di restituzione/chiusura sono chiariti in D39 (O02 risolta).

### D39 — Parametri del tipo documento dimostrativo

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Si» alla proposta dei tre parametri dimostrativi: associazione alla stessa lavorazione, area di preparazione abilitata e carcassa richiesta prima della chiusura tecnica. **Stato:** DP sullo scenario di prova; nessuna approvazione complessiva del dossier o autorizzazione implementativa.

**D39 — Configurazione societaria dimostrativa confermata:** prestazione e ricambio sono collegati alla stessa lavorazione; area di preparazione abilitata per esercitare la separazione fra prelievo e installazione; rientro della carcassa richiesto per il ricambio dell'esempio prima della chiusura tecnica. Sono valori del tipo documento dello scenario di prova, non obblighi universali: restano governati dal customizing societario. La chiusura tecnica di D37 richiede quindi anche tale rientro nel caso dimostrativo. Restano separati permessi, invarianti e regola di non retroattività.

O02 del documento 09 è risolta per questi parametri. La conferma non rende obbligatorie area o carcassa in ogni società/tipo e non approva deroghe, valorizzazioni o regole fiscali. La semantica del contratto simulato O03 è chiarita in D40; dettagli tecnici da progettare in B10–B11. Validazioni specialistiche ancora aperte.

### D40 — Ricezione distinta dall’elaborazione amministrativa completata

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, risponde «Confermo» alla proposta di distinguere acquisizione della richiesta, elaborazione completata e rifiuto/esito incerto. **Stato:** DP sul comportamento del simulatore; nessuna autorizzazione implementativa o approvazione complessiva del dossier.

**D40 — Esito del simulatore amministrativo:** «richiesta ricevuta» indica sola acquisizione e lascia la commessa in attesa. «Elaborazione completata» restituisce una conferma di business e un riferimento esterno stabile, soddisfacendo il requisito esterno per la chiusura amministrativa. Rifiuto o esito incerto mantengono la chiusura bloccata e richiedono riconciliazione. La conferma simulata non rappresenta fattura fiscalmente emessa, incasso o registrazione contabile reale. Restano validi gli altri prerequisiti di chiusura e le autorizzazioni.

O03 è risolta sul piano del comportamento di business e dei riferimenti richiesti. Schema del payload, protocollo di risposta, correlazione/idempotenza e verifica degli esiti restano da progettare e testare negli incrementi B10–B11; non sono contratti già implementati.

### D41 — Caso 001 e politica di arrotondamento di riferimento

**Fonte:** Luigi Pelosi fornisce «Caso di test 001 — Vendita nazionale con prestazione e ricambio» con input, esiti attesi e regole di precisione/arrotondamento. **Stato:** specifica funzionale del proprietario e riscontro aritmetico indipendente; non attestazione di validazione specialistica, approvazione del dossier o autorizzazione implementativa.

**D41 — Caso funzionale 001 fornito dal proprietario:** riepilogo commerciale atteso 164.50 EUR di imponibile, 36.19 EUR di IVA e 200.69 EUR di totale. Prezzi netti fino a 6 decimali, quantità fino a 3, sconti prima dell'IVA, imponibili di riga a 2 decimali; imposta sul raggruppamento di righe con stesso trattamento/aliquota, a 2 decimali con ROUND_HALF_UP. La verifica decimale indipendente è passata; non è un test del motore applicativo o di SdI. Specifica e fixture nel [caso 001](10-test-case-001.md); validazione del referente sul caso successivamente attestata dal proprietario in D42.

Il caso fiscale usa un filtro olio e non sostituisce implicitamente il componente dimostrativo con carcassa di D35–D39. TD01 e mapping DettaglioLinee/DatiRiepilogo sono riferimenti per la futura fatturazione, non emissione XML implementata. F01 è ricevuta come caso funzionale; F02 è ricevuta per politica di base e confronto aggregato/per-riga. La provenienza della validazione del caso è aggiornata in D42. Restano ulteriori casi limite, completamento F03 e piano/scrittura F04.

### D42 — Conferma della validazione del caso 001

**Fonte e ambito:** Luigi Pelosi risponde «Si» alla domanda se il caso e le regole di arrotondamento siano già stati validati dal referente disponibile.

**D42 — Validazione del caso 001 riferita dal proprietario:** Luigi Pelosi conferma che il caso e le regole di arrotondamento sono già stati validati dal referente disponibile. L'attestazione riguarda il caso 001 e la sua politica di calcolo; non è una validazione generale del motore fiscale, di altri trattamenti IVA, della fatturazione elettronica o delle scritture contabili. Il ruolo professionale esatto del referente e un verbale separato non sono stati comunicati; nessun contatto diretto dell'agente è dichiarato.

Il riscontro aritmetico indipendente e la validazione riferita sono evidenze distinte. D01 resta aperta per i punti residui; nessuna approvazione complessiva del dossier, autorizzazione implementativa o abilitazione di emissione fiscale.

### D43 — Piano e scrittura contabile dimostrativi ricevuti

**Fonte:** allegato `F04 - scrittura contabile di riferimento.docx` fornito dal proprietario in risposta alla richiesta F04. **Stato:** riferimento fornito e riscontro aritmetico indipendente; non attestazione aggiuntiva della validazione specialistica.

**D43 — F04 ricevuta:** allegato del proprietario con piano dimostrativo e scrittura della fattura `FV-001/2026`, commessa 001, pagamento differito. Dare 120100 = 200.69 EUR; Avere 700100 = 74.25, 700200 = 90.25, 220100 = 36.19 EUR. Quadratura e coerenza con il caso fiscale 001 verificate con Decimal; validazione del referente specifica di F04 successivamente attestata dal proprietario in D44. Nessun incasso, costo del venduto, valorizzazione o margine introdotto. Dettagli e cautele nel [riferimento F04](11-f04-reference-journal-entry.md).

Classificazioni e richiami normativi restano attribuiti alla fonte, con le cautele espresse nel documento. Il piano dimostrativo non diventa un piano universale; i riferimenti illustrativi non fissano numerazioni o contratti persistenti del prodotto. Il perimetro tecnico F03 è successivamente confermato in D45; i gate implementativi rimangono aperti.

### D44 — Conferma della validazione del piano e della scrittura F04

**Fonte e ambito:** Luigi Pelosi risponde «Confermo» alla domanda se anche il piano dimostrativo e la scrittura F04 siano stati validati dal referente.

**D44 — Validazione F04 riferita dal proprietario:** Luigi Pelosi conferma che anche il piano dei conti dimostrativo e la scrittura F04 del caso 001 sono stati validati dal referente disponibile. L'attestazione è circoscritta a questo riferimento, con le ipotesi e le cautele dell'allegato. Non approva un piano universale, ulteriori scritture, conformità generale o un modulo contabile già implementato. Nessun contatto diretto dell'agente è dichiarato.

F04 è acquisita e validata per il caso 001 secondo attestazione del proprietario. Il perimetro tecnico F03 è successivamente confermato in D45; gli ulteriori casi limite F02 restano da completare o rinviare con gate espliciti. D01 e B00 non vengono chiusi. Nessuna autorizzazione implementativa o approvazione complessiva del dossier.

### D45 — Dati e tracciabilità della fattura tecnica del primo scenario

**Fonte e ambito:** Luigi Pelosi risponde «Confermo» alla proposta F03 di dati, collegamenti e conservazione dello storico della fattura tecnica. **Stato:** decisione di prodotto confermata dal proprietario per il primo scenario, non ulteriore validazione specialistica di emissione reale.

**D45 — Perimetro F03 confermato dal proprietario:** la fattura tecnica del primo scenario conserva società emittente e destinatario con i dati anagrafici utilizzati alla conferma; data, valuta, tipo e riferimento del documento; righe, sconti e riepiloghi fiscali; collegamenti alla commessa, alle righe di provenienza e alla registrazione contabile. Modifiche anagrafiche successive non riscrivono i dati storici della fattura confermata. È un documento tecnico di prova, non una fattura fiscalmente emessa o l'elenco completo dei requisiti della fatturazione reale.

La conservazione dei dati storici non introduce un congelamento universale del customizing e non elimina i percorsi di rettifica tracciata già concordati. I collegamenti sono requisiti di tracciabilità, non transazioni globali: la registrazione può essere successiva e deve rendere visibili attese/errori intermodulo. F03 è risolta per il perimetro tecnico dichiarato. Progettazione di ID, contratti, idempotenza e test restano in B12–B13; ulteriori casi limite F02 e dettagli di stock restano gate da delimitare. Nessuna chiusura automatica di D01 o B00.

### D46 — Dettagli residui e gate della revisione finale D01

**Fonte e ambito:** Luigi Pelosi risponde «Confermo» alla proposta di delimitare casi limite fiscali, dettagli di magazzino e contratti/idempotenza come prerequisiti dei rispettivi incrementi. **Stato:** decisione di pianificazione confermata; non autorizzazione implementativa o approvazione del dossier complessivo.

**D46 — Delimitazione dei dettagli residui confermata:** gli ulteriori casi limite di precisione/arrotondamento devono essere definiti e validati prima di completare B05; dettagli esecutivi dei movimenti e della concorrenza di magazzino devono essere definiti e verificati nei rispettivi incrementi B06–B09; contratti tecnici, idempotenza e recupero degli errori restano progettazione e test degli incrementi pertinenti. Sono gate obbligatori, non requisiti eliminati o già soddisfatti. La conferma permette la revisione finale di D01, non chiude automaticamente D01/B00 e non autorizza implementazione o approvazione complessiva del dossier.

La matrice G01–G03 nel documento 09 riporta incrementi, prove e referenti per ruolo. Le validazioni riferite D42/D44 e il perimetro D45 restano circoscritti ai casi descritti. Nessuna superficie di dominio è aggiunta al bootstrap HTTP pubblico.

### D47 — Demo e pilota sul VPS esistente senza nuove macchine

**Fonte e ambito:** Luigi Pelosi dichiara che il budget comprende il VPS attuale, non prevede altre macchine per demo/pilota e che tutto sarà eseguito su questa VPS. **Stato:** vincolo infrastrutturale/economico confermato, non autorizzazione a modificare il deployment.

**D47 — Unica VPS esistente per demo e pilota:** il proprietario conferma che il budget comprende già il VPS attuale, che non sono previsti acquisti di altre macchine e che i carichi della demo e del pilota saranno eseguiti su questa VPS. Nessun preventivo di un secondo host o di alta disponibilità multi-host entra nella baseline. Il costo esistente non è un nuovo acquisto né viene dichiarato nullo. Nessun importo mensile numerico è stato comunicato.

Il vincolo non certifica capacità, recupero, giurisdizione UE o compatibilità dei carichi futuri; non autorizza esposizione di dati/credenziali sull’HTTP tecnico pubblico. Separazione logica, risorse, backup fuori nodo e RPO/RTO restano da verificare in D02 e negli incrementi autorizzati. Nessuna deroga al charter, nuova macchina o servizio a pagamento è approvato implicitamente.

### D48 — Messa a disposizione di risorse esterne per i backup

**Fonte e ambito:** Luigi Pelosi dichiara «Metterò a disposizione altre risorse esterne a questa VPS per i backup». **Stato:** impegno del proprietario sulla disponibilità futura della destinazione, non prova di provisioning o recupero.

**D48 — Risorse esterne per i backup fornite dal proprietario:** Luigi Pelosi dichiara che metterà a disposizione risorse esterne alla VPS per i backup. D47 resta invariata per l'esecuzione dei carichi demo/pilota sulla VPS esistente; le risorse esterne sono destinate ai backup, non a nuovi nodi applicativi o alta disponibilità. È un impegno di messa a disposizione, non una destinazione già configurata o verificata.

Non sono scelti protocollo, provider, cifratura, gestione delle chiavi, capacità, frequenza o retention; gli obiettivi iniziali RPO/RTO sono successivamente dichiarati in D49, mentre copertura operativa e verifica restano aperte. Messa a disposizione della risorsa e responsabilità di eseguire/controllare backup e ripristino sono distinte. Queste caratteristiche restano gate D02 e delle verifiche prima del pilota; nessun cambiamento al runtime o acquisto è effettuato.

### D49 — Obiettivi iniziali RPO/RTO ed evoluzione infrastrutturale futura

**Fonte e ambito:** Luigi Pelosi indica recupero fino al giorno precedente e ripristino massimo in 1 ora «solo inizialmente»; dichiara una futura evoluzione con ridondanza/replicazione/load balancing, eventualmente AWS, quando il progetto sarà completo. **Stato:** obiettivi iniziali confermati e intenzione futura registrata; non prova di recupero o scelta architetturale cloud definitiva.

**D49 — Obiettivi iniziali di recupero:** il proprietario indica RPO «fino al giorno precedente» e RTO massimo di 1 ora, limitatamente alla fase iniziale. Sono obiettivi da progettare e dimostrare con prove, non garanzie già conseguite o SLA. Per l'RPO vanno precisati orario del punto di recupero giornaliero, completamento del trasferimento esterno e gestione di backup falliti; non si assume automaticamente un limite mobile di 24 ore. Per l'RTO vanno definiti inizio/fine della misurazione, copertura operativa e scenario di guasto.

**Evoluzione futura dichiarata, non baseline attuale:** a progetto completo il proprietario intende valutare ridondanza dei dati, replicazione continua e load balancing, eventualmente su AWS. Non sono approvati provider cloud definitivo, migrazione, servizi, budget o date. D47/D48 restano la baseline iniziale: carichi sulla VPS esistente e risorse esterne per backup messe a disposizione dal proprietario.

Non sono introdotti SLA, failover o replicazione nell’attuale bootstrap. Indisponibilità/perdita completa dell’host, responsabilità di intervento e disponibilità del provider devono essere considerate prima di dichiarare raggiunto l’RTO. Policy, tempi misurati e capacità restano gate D02 e del pilota.

### D50 — Referente operativo per allarmi e ripristino iniziali

**Fonte e ambito:** alla domanda su chi riceverà gli allarmi e gestirà gli interventi di ripristino, Luigi Pelosi risponde «No, sarò io». **Stato:** responsabilità personale confermata per la fase iniziale; non impegno di copertura continua o prova di recupero.

**D50 — Presidio iniziale di allarmi e ripristino:** Luigi Pelosi conferma di occuparsi personalmente della ricezione degli allarmi e della gestione degli interventi di ripristino nella fase iniziale. La conferma non implica reperibilità continuativa, un sostituto, un servizio esternalizzato o tempi già dimostrati. Giorni/fasce sono successivamente definiti in D51; il canale iniziale e-mail è successivamente scelto in D52, mentre configurazione e procedura restano da definire; l'obiettivo RTO di D49 non viene ridefinito come tempo dalla sola presa in carico.

Non si attribuiscono automaticamente al proprietario, con questa sola risposta, tutte le attività di manutenzione, identity o controllo periodico dei backup. Nessun recapito o credenziale è raccolto nel repository. A questo punto della discovery D02 rimaneva In corso; il successivo passaggio In verifica è registrato in D57. Le modifiche sono documentali e non configurano sistemi di notifica o recupero.

### D51 — Presidio iniziale dal lunedì al sabato, 09:00–18:00

**Fonte e ambito:** Luigi Pelosi risponde «Tutti i giorni dalle 09-18 (Lun-Sab)» alla domanda sui giorni e sulle fasce di presidio del pilota. **Stato:** finestra di presidio confermata, non copertura continuativa o SLA.

**D51 — Fascia iniziale di presidio:** Luigi Pelosi indica «09-18 (Lun-Sab)»: presidio dal lunedì al sabato, 09:00–18:00. La specifica Lun–Sab delimita «tutti i giorni»; domenica e altre fasce non hanno presidio dichiarato. Non è una finestra di spegnimento del servizio. Il canale iniziale è successivamente scelto in D52. Fuso orario, festività e trattamento degli incidenti a cavallo della fine fascia restano da precisare prima della configurazione operativa. Non si sospende o riavvia implicitamente il conteggio RTO fuori fascia e non si dichiara garantito il ripristino entro un'ora dove manca presidio.

RPO/RTO iniziali di D49 restano obiettivi da verificare, con la limitazione operativa del presidio esplicita. Nessun monitor, job, calendario o disponibilità pubblica viene modificato. D02 rimane aperta; a questo punto della discovery la documentazione era aggiornata solo localmente. La pubblicazione dell'incremento D49–D57 è tracciata separatamente dalla decisione.

### D52 — E-mail iniziale, Telegram e WhatsApp rinviati

**Fonte e ambito:** Luigi Pelosi dichiara «Per ora solo e-mail; in seguito prevederemo anche Telegram/WhatsApp». **Stato:** canale iniziale confermato e direzione futura registrata, non autorizzazione a installare o configurare integrazioni.

**D52 — Canale iniziale degli allarmi:** il proprietario sceglie la sola e-mail per la fase iniziale; Telegram e WhatsApp sono evoluzioni future, non integrazioni attuali approvate o da implementare subito. D53 conferma successivamente un SMTP già disponibile; la scelta del canale non autorizza acquisti e non dimostra la consegna degli allarmi. Destinatario e parametri di invio saranno configurati fuori dal repository; nessuna credenziale è richiesta in chat.

Responsabile e presidio D50/D51 restano invariati. Monitoraggio, invio e ricezione effettiva dovranno essere verificati nell’incarico operativo pertinente. Non si introducono ora bot, interfacce o servizi per canali futuri, né si cambiano RPO/RTO o copertura. A questo punto della discovery D02 restava In corso; il successivo passaggio In verifica è registrato in D57.

### D53 — Servizio SMTP esistente disponibile per gli allarmi

**Fonte e ambito:** Luigi Pelosi risponde «Si ce l’ho un SMTP disponibile» alla domanda sulla disponibilità di un servizio di invio e-mail. **Stato:** risorsa dichiarata disponibile, non prova tecnica o autorizzazione a usare credenziali/inviare messaggi.

**D53 — SMTP già disponibile:** il proprietario conferma di disporre di un servizio SMTP utilizzabile come risorsa candidata per gli allarmi e-mail iniziali. Non sono ancora specificati provider, limiti di invio, costo contrattuale, modalità di autenticazione o configurazione. La disponibilità dichiarata non è una prova di accesso dalla VPS, protezione del collegamento o consegna effettiva; nessun nuovo servizio di invio è acquistato o attivato.

Resta il canale iniziale e-mail di D52; nessuna implementazione Telegram/WhatsApp o selezione di un nuovo provider. Parametri e segreti non vengono raccolti nel repository o in chat. Configurazione e prova end-to-end degli allarmi saranno esercitate nell’incarico autorizzato pertinente. D02 rimane aperta; modifiche documentali locali, senza commit o deployment.

### D54 — VPS attuale in Germania, target pilota/finale ancora aperto

**Fonte e ambito:** Luigi Pelosi dichiara «Attualmente è in Germania ma non è detto che la versione finale/pilota sia sulla stessa VPS ospitata lì in Germania». **Stato:** localizzazione attuale riferita e precisazione della baseline, non migrazione o nuovo provider approvati.

**D54 — Localizzazione attuale e destinazione del pilota non vincolata:** il proprietario dichiara che la VPS attuale è in Germania e precisa che pilota/versione finale potrebbero non essere sulla stessa VPS né nella stessa localizzazione. La Germania è informazione fornita dal proprietario, non verifica contrattuale indipendente. La VPS attuale resta il riferimento di demo e dimensionamento iniziale, non una destinazione irrevocabile del pilota. Resta il requisito del charter di hosting UE per il target effettivo; nessuna nuova macchina, migrazione, provider, regione o spesa è autorizzata da questa precisazione.

D54 prevale sulla lettura di D47/D48 come obbligo di eseguire qualunque pilota o versione finale sull’host odierno. Il divieto di presumere nuovi acquisti resta: un eventuale cambio richiede scope e costi separatamente approvati. Le verifiche di recupero, accesso protetto, giurisdizione e capacità del pilota dovranno riguardare il target effettivo e le destinazioni dei dati pertinenti. AWS resta soltanto eventualità futura di D49.

### D55 — Keycloak candidato confermato per la prova identity B01

**Fonte e ambito:** Luigi Pelosi risponde «Confermo» alla proposta di Keycloak come candidato da verificare nella prova tecnica, dopo il confronto documentale con Auth0 nel documento 12. **Stato:** candidatura approvata per la valutazione, non scelta di produzione o autorizzazione implementativa.

**D55 — Candidatura Keycloak alla prova B01 confermata:** il proprietario approva Keycloak community self-hosted come candidato da verificare nella prova tecnica. Non è adozione definitiva, autorizzazione a installare/configurare identity o approvazione del dossier complessivo. B01 resta subordinata a B00 e a uno scope implementativo esplicito; nessuna autenticazione viene aggiunta al bootstrap HTTP pubblico.

L’esito di B01 dovrà dimostrare risorse sostenibili, MFA/federazione, verifica token/sessione, revoca e recupero, trasporto protetto e backup/ripristino pertinenti. Versione/digest, configurazioni, modello di amministrazione e responsabilità della manutenzione restano da definire negli scope pertinenti. Il gestito rimane alternativa documentale; rivalutarlo se la prova fallisce richiede decisione e spesa separate. D02 resta aperta; nessun servizio è attivato.

### D56 — Disponibilità ad acquistare un dominio per il progetto

**Fonte e ambito:** Luigi Pelosi dichiara «Non ho ancora un dominio/sottodominio ma non è un problema acquistarlo». **Stato:** assenza della risorsa e disponibilità di spesa dichiarate; non incarico di acquisto.

**D56 — Dominio non disponibile, acquisto valutabile:** il proprietario dichiara di non avere ancora un dominio/sottodominio per il progetto e che acquistarlo non è un problema. È disponibilità a sostenere questa voce di costo, non un ordine di acquisto o una scelta di nome, registrar, estensione, importo o rinnovo. Nessun dominio è stato ricercato per disponibilità, prenotato o registrato dall'agente.

La voce dominio/DNS entra nel confronto economico con registrazione e rinnovo distinti, prezzo e condizioni da verificare sulla proposta effettiva. Nome, provider e controllo DNS restano aperti prima dell’accesso pubblico autenticato tramite dominio; eventuale prova locale protetta non è subordinata all’acquisto. Nessuna modifica al canale HTTP attuale, configurazione identity, DNS o acquisto eseguita. D02 rimane In corso a questo punto della discovery; passaggio alla revisione successivamente confermato in D57.

### D57 — Revisione D02 e gate economico-operativi confermati

**Fonte e ambito:** Luigi Pelosi risponde «Confermo» alla proposta di delimitare i residui per portare D02 In verifica, senza preventivo definitivo o autorizzazione implementativa. **Stato:** delimitazione della discovery approvata, non completamento del lavoro applicativo.

**D57 — Delimitazione D02 confermata per la revisione:** il proprietario approva il passaggio di D02 a «In verifica», mantenendo come gate gli elementi residui: dominio/nome/costi e rinnovi prima dell'acquisto; prove identity, risorse e protezioni prima di completare B01, con prerequisito B00 e scope implementativo esplicito; backup e ripristino misurato, allarmi verificati, responsabilità residue assegnate, costi e idoneità del target effettivo prima del pilota. La matrice OPE01–OPE05 dettaglia referenti ed evidenze. Non è un preventivo definitivo, un acquisto, approvazione complessiva del dossier o autorizzazione a implementare.

D01 e D02 restano issue aperte In verifica; B00 non viene completata o sbloccata automaticamente. Nessun dato di costo sconosciuto è considerato zero, nessun RTO è garantito senza prova e nessuna disponibilità promessa equivale a configurazione operativa. La documentazione è aggiornata localmente, senza commit o pubblicazione delle modifiche correnti.

### D58 — Dossier approvato e B01 autorizzata con scope limitato

**Fonte e conferma:** Luigi Pelosi, proprietario del prodotto, seleziona «Approvo dossier e B00; autorizzo solo B01» dopo la revisione complessiva. **Stato:** approvazione del dossier e gate B00; autorizzazione implementativa circoscritta a B01.

**D58 — Scope autorizzato:** avviare una prova tecnica isolata, reversibile e documentata di Keycloak community self-hosted con soli dati e identità sintetici. La prova deve verificare almeno autenticazione, rifiuto anonimo, token/sessione, revoca pertinente, risorse, trasporto protetto nell'ambiente di prova e istruzioni ripetibili. Può introdurre esclusivamente codice, configurazione, test e container necessari a B01, con versioni/digest bloccati e senza segreti nel repository.

**Esclusioni vincolanti:** nessun dominio o acquisto; nessun utente, cliente o dato reale; nessuna adozione definitiva del provider; nessuna esposizione del login o modifica del servizio HTTP pubblico esistente; nessuna implementazione B02–B14 o modulo di dominio. OPE02 e il threat model governano la prova; gli altri gate G01–G03/OPE01/OPE03–OPE05 restano assegnati alle rispettive scadenze. Ogni ampliamento richiede nuova autorizzazione esplicita.

### D59 — Keycloak baseline iniziale e B02 autorizzata

**Fonte e conferma:** Luigi Pelosi risponde «Confermo» alla proposta esplicita di unire B01, adottare Keycloak come baseline identity iniziale e autorizzare esclusivamente B02. **Stato:** decisione tecnica circoscritta e nuova autorizzazione implementativa; non adozione di produzione né autorizzazione degli incrementi successivi.

**D59 — Decisione:** la prova B01 è accettata come base tecnica iniziale per l'identity; Keycloak community self-hosted diventa la baseline da integrare negli ambienti sintetici autorizzati. Auth0 resta alternativa documentata se i gate operativi o i requisiti futuri rendono insostenibile il self-hosting. B01 può essere completata dopo merge e verifica della PR #21.

**Scope B02 autorizzato:** realizzare il minimo percorso persistito e protetto con due tenant sintetici, più società/sedi/magazzini e scope differenti; autenticare identità sintetiche tramite la baseline Keycloak; validare nel backend il tenant context e i riferimenti organizzativi autorizzati; verificare che manipolazione degli identificativi, capability disabilitate e riuso delle connessioni non amplino l'accesso. PostgreSQL deve restare privato, con migrazioni e ripetibilità verificate; UI/API devono essere il minimo necessario al percorso B02.

**Esclusioni vincolanti:** nessun dato o utente reale, dominio/acquisto o esposizione pubblica del login; nessuna dichiarazione di readiness per produzione; nessuna implementazione B03–B14, controparte, commessa o regola fiscale. B02 non decide cataloghi commerciali, ruoli universali o provisioning reale dei tenant. Ogni ampliamento richiede nuova autorizzazione esplicita.

### D60 — B03 autorizzata, senza estensione agli incrementi successivi

**Fonte e conferma:** Luigi Pelosi risponde «Procediamo» alla comunicazione «Il prossimo incremento è B03 — Controparte comune e destinazioni. È ancora bloccato in backlog: non è stato avviato e richiede la tua autorizzazione circoscritta». La risposta autorizza B03 soltanto, non B04 o l'intera slice. La delega operativa richiede di fermarsi su decisioni di dominio ad alto impatto non risolte dal dossier.

**Scope autorizzato:** minimo percorso reale UI/API/PostgreSQL per la controparte D36, comune a due società del medesimo tenant, con ragione sociale, identificativo fiscale e sede legale; destinazione operativa locale riservata alla società che la registra e pubblicazione comune solo esplicita e autorizzata. Permesso specifico per modificare il nucleo comune; isolamento tenant e scope della risorsa verificati lato server; audit tecnico senza payload sensibili. Preservare sicurezza e prove B02, con test-first e ambiente Compose isolato.

**Esclusioni vincolanti:** soltanto identità e dati sintetici, nessun utente/cliente/dato reale, provisioning reale o UI amministrativa di provisioning; nessuna nuova policy di business o validazione fiscale degli identificativi; niente acquisti, dominio, accesso pubblico o readiness di produzione; nessuna modifica dell'ambiente manuale persistente B02, bootstrap originario o Tailscale. B04–B14 restano bloccati e richiedono autorizzazione distinta. Nessun commit, push o merge prima della review indipendente del parent.

**Gate storico:** il permesso/scope di pubblicazione era da chiarire prima del codice. Risolto dalla conferma esplicita D61; nessuna estensione dello scope D60.

### D61 — Pubblicazione con permesso distinto sulla società proprietaria

**Fonte e conferma:** Luigi Pelosi conferma esplicitamente la proposta «un permesso specifico di pubblicazione, assegnato sulla società proprietaria della destinazione, distinto dal permesso di modificare l’anagrafica comune. Un’autorizzazione limitata a sede o magazzino non basterebbe».

**Decisione:** pubblicare richiede il permesso specifico riferito alla società proprietaria della destinazione. Il solo edit comune, un grant su altra società o un'autorizzazione limitata a sede/magazzino non bastano. La pubblicazione esplicita rende visibile la destinazione alle altre società autorizzate dello stesso tenant, mai ad altri tenant. D36 resta il contratto minimo dei campi comuni; D21 governa separatamente la modifica comune. Non sono approvati ruoli universali, autorità di concessione, revoca, deduplicazione o validazione fiscale.

**Stato storico alla registrazione D61:** gate di dominio B03 risolto; implementazione locale entro D60, con prove tecniche nel report `../b03-verification.md`; review indipendente e CI remota allora ancora da eseguire. B03 è successivamente integrata con PR #24; prevale lo stato corrente in apertura.

### D62 — B04 autorizzata, con gate di dominio veicoli ancora aperto

**Fonte e conferma:** Luigi Pelosi risponde «Procedi» alla proposta esplicita del prossimo incremento B04 — Commessa diretta nel tipo societario, ancora bloccato e non avviato. La delega autorizza solo B04; non risolve implicitamente decisioni di dominio aperte.

**Scope positivo e finito:** minimo percorso reale UI italiana/API/PostgreSQL per creare direttamente una commessa già ordine cliente, di tipo configurato esclusivamente nella società e con una sola sede di testata; selezione del veicolo con intestatario distinto dal singolo soggetto a carico, senza sovrascrivere il pagante; integrazione dei contratti B03 e delle autorizzazioni esistenti, versione della configurazione pertinente tracciata, isolamento e rifiuto dei riferimenti non autorizzati, persistenza/migrazione/rollback e audit tecnico minimizzato. Test-first per comportamento e runner CI di accettazione, verifica isolata e review indipendente prima della consegna.

**Esclusioni vincolanti:** soli dati/identità sintetici; nessun provisioning o editor amministrativo, workflow universale, congelamento universale del documento, catalogo generale dei tipi, ripartizioni/garanzia, righe, ricambi, prezzi, fiscalità o B05–B14. Nessun dato reale, acquisto, accesso pubblico, commit/push/merge o deployment persistente prima della review indipendente e della preparazione manuale del parent. Ambienti manuali B02/B03, bootstrap e Tailscale immutati.

**Gate prima del codice:** il documento 03 §4 dichiara non deciso il perimetro condiviso dei veicoli e vieta di estendere automaticamente le regole delle controparti; il documento 05 assegna Vehicles con scope di condivisione da definire. B04 richiede lettura/selezione del veicolo e rifiuto dei riferimenti estranei: adottare tenant-sharing o riservatezza societaria senza conferma fisserebbe una policy di accesso non approvata. Issue #10 non contiene risposte (discussione vuota alla verifica). Domanda al proprietario: nel solo scenario B04, il veicolo è comune alle società autorizzate dello stesso tenant oppure riservato alla società che lo registra? Raccomandazione prudente: riservato alla società, senza anticipare il catalogo generale. Nessuna alternativa è approvata dalla presente registrazione.

**Stato storico D62:** B04 autorizzata ma allora bloccata sul gate veicoli; avvio esclusivamente documentale su `feat/b04-direct-workshop-order`, baseline `584784812dc8086c3c313e32d2b91adfdfe98bc0`. Gate successivamente risolto in D63. B05–B14 restano non autorizzati e bloccati.

### D63 — Gestione veicoli secondo le controparti; selezione commessa nel tenant

**Fonte e conferma:** risposta diretta del proprietario Luigi Pelosi al gate D62, riportata verbatim: «La lettura, add, edit e remove seguono le stesse regole delle controparti mentre la selezione del veicolo per una commessa di lavorazione può essere effettuata a livello di tenant».

**Decisione:** separare due usi, senza trasformare la selezione in un permesso anagrafico generale:

- **Gestione anagrafica (read/add/edit/remove):** stesse regole approvate delle corrispondenti operazioni sulle controparti (D18/D20/D21/D23/D26/D61): contesto tenant verificato, accessi societari espliciti per la consultazione, modifica comune con permesso specifico distinto dall'uso, dati societari riservati e pubblicazione esplicita ove pertinente. Nessun accesso tra tenant. La frase non approva nuove semantiche di cancellazione o una gestione CRUD completa.
- **Selezione per commessa:** ammessa nell'intero tenant verificato, anche per un veicolo registrato tramite un'altra società alla quale l'operatore non ha accesso gestionale. La proiezione minima dedicata alla selezione, autorizzata nel contesto commessa/società/sede/capability, non concede accesso alla gestione del veicolo, ai dati riservati dell'altra società o alla gestione dell'intestatario. Il backend ricontrolla il riferimento alla creazione; il client non sceglie il tenant.
- **Intestatario e soggetto a carico:** restano riferimenti distinti; selezionare un veicolo non sovrascrive il soggetto a carico scelto. Nessuna equivalenza legale tra intestatario e proprietario viene introdotta.

**Limite implementativo:** B03 non ha implementato add/remove dell'identità comune della controparte; D63 non autorizza a inventarne la policy o a completarli incidentalmente. Per B04 sono sufficienti fixture sintetiche e un selettore minimo del veicolo; nessun editor amministrativo o CRUD completo veicoli/controparti. Policy di gestione futura non necessaria al selettore resta rinviata, non impedimento fittizio a B04.

**Stato corrente:** gate D62 risolto; soltanto B04 è sbloccata per il percorso finito D62 con test-first e review indipendente. B05–B14 restano Backlog/bloccati e non autorizzati. Nessun commit/push/deployment persistente; B02/B03 manuali e Tailscale invariati. La decisione non costituisce prova applicativa né completamento B04.

### D64 — B05 autorizzata; gate catalogo prima del codice

**Nota di lettura corrente:** il gate catalogo e la raccomandazione societaria sotto sono storici, risolti da D65. Scope ed esclusioni D64 restano validi.

**Fonte e ambito:** Luigi Pelosi risponde «procedi» dopo la chiusura di B04; la delega del parent identifica esclusivamente il prossimo incremento B05. Registrazione del 19 ottobre 2026, non approvazione implicita delle decisioni ancora aperte.

**Scope positivo e finito:** aggiungere una prestazione e un ricambio alla commessa persistita mediante minimo percorso privato UI italiana/API/PostgreSQL, contratti e ownership espliciti. Quantità, prezzi unitari, sconti e arrotondamenti con decimal/value object; backend autorevole sui calcoli, senza fiducia nei totali client. Riepilogo commerciale, imponibile netto, imposte e totale attribuiti al soggetto a carico, default uno per riga; associazione alla stessa lavorazione secondo configurazione societaria dimostrativa D39, senza duplicare importi nei raggruppamenti operativi. Storico non riscritto da cambi anagrafici/listini/configurazioni. Caso 001: 164.50 / 36.19 / 200.69, precisioni 6/3, righe a due decimali e IVA aggregata ROUND_HALF_UP secondo D41/D42, senza generalizzazione fiscale. Test-first verticali; isolamento tenant/società/sede, capability/permessi, input e riferimenti obsoleti, concorrenza/retry, trasporto decimale invariante e limiti anti-overflow; migrazioni/rollback/audit/RLS/pooling, DOM/HTTP e selezione CI, regressioni isolate B02–B04.

**Esclusioni:** costi e marginalità anche provvisori (D32), prenotazioni/movimenti e B06–B14; ripartizioni/garanzia, ERP reale, fiscalità reale/SdI, catalogo amministrativo completo, provisioning, dati o identità reali, acquisti o accesso pubblico. Nessun commit/push/merge o deployment manuale persistente prima della review del parent e della preparazione manuale. Conservare ambienti B02/B03/B04, storage esplicito e backup, bootstrap e Tailscale 443/8443/8444/8445; nessun accesso ai segreti.

**Gate prima del codice:** documento 03 §3/limiti dichiara ancora non deciso il nucleo condiviso del catalogo. D63 riguarda soltanto i veicoli e non può essere estesa ad articoli/prestazioni. Catalog non esiste nella baseline; Workshop.Contracts espone soltanto testata/tipo, non righe o prezzi. Issue #11 e discussione (vuota) non risolvono il confine. Un selettore o riferimento di catalogo tenant-wide oppure societario fisserebbe una nuova policy di accesso. Domanda unica al proprietario tramite parent: **per B05, prestazioni e ricambi selezionabili sono comuni nel tenant oppure riservati alla società della commessa?** Raccomandazione prudente: riservati alla società per questa prova finita, senza decidere il catalogo generale; proposta non ancora approvata.

**Altri limiti da non inventare:** il soggetto unico e l'associazione dimostrativa sono già confermati in D28/D39; non richiedono una nuova scelta universale. Non sono invece approvate derivazioni automatiche di prezzo/pagante dal catalogo o regole generali di modifica dei listini. G01/D46 resta gate prima del completamento: ulteriori casi limite con limiti applicativi ed esiti attesi/validazione pertinente, inclusa precisione degli sconti non specificata dal solo caso 001.

**Stato:** avvio documentale su `feat/b05-service-part-values`, baseline `0f9cc50fcf685d2e8ffab2686947124fb3189293`; implementazione ferma al gate catalogo. Issue #11 aperta/blocked, Project Backlog finché mancano requisiti sufficienti; autorizzazione non significa Pronto. Nessuna prova RED/GREEN applicativa o CI B05 eseguita; nessuna implementazione iniziata. B06–B14 restano non autorizzati/bloccati/Backlog.

### D65 — Visibilità delle anagrafiche a livello tenant

**Nota corrente:** precisioni B05 ulteriormente definite da D66; la frase storica sotto sugli sconti non più approvati è superata da D66.

**Fonte e conferma:** risposta diretta di Luigi Pelosi al gate catalogo D64, verbatim: «Il catalogo, l’anagrafica dell’articolo fisico e delle prestazioni, è visibile a livello di tenant. Come regola generale, tutto ciò che è anagrafico è sempre a livello di tenant.»

**Decisione corrente:** la visibilità dell'identità anagrafica comune è tenant-wide, inclusi articoli fisici e prestazioni. Non occorre richiedere nuovamente questa policy per ogni anagrafica. Il tenant verificato resta il confine di isolamento: nessuna condivisione fra tenant. Per B05 il Catalogo possiede l'identità e la proiezione minima usata dalla commessa attraverso contratti pubblici; un articolo registrato da un'altra società del medesimo tenant è selezionabile senza concedere accesso a quella società.

**Distinzioni vincolanti:** visibilità/uso non concedono automaticamente add/edit/remove, amministrazione o facoltà di concedere permessi. D21/D23 e i controlli server sull'azione/risorsa restano validi. Identità comune e sue estensioni sono distinte: condizioni e prezzi societari, documenti, stock/disponibilità, customizing societario versionato D9/D14 e destinazioni riservate D20/D36 non diventano comuni. Pubblicazione esplicita con permesso specifico sulla società proprietaria resta D61. D63 conserva la distinzione selezione veicolo/gestione e non riceve nuovi grant impliciti.

**Perimetro B05:** gate catalogo risolto; proseguire soltanto con il percorso finito D64. Il caso 001 fornisce valori espliciti sintetici, non un listino o una derivazione automatica prezzo/pagante dal master. Precisione generale degli sconti e politiche fiscali ulteriori non sono approvate. G01/D46 richiede evidenze e limiti dichiarati prima del completamento, non riapertura della visibilità già decisa. B06–B14 restano bloccati/Backlog e non autorizzati. Nessun commit/push/merge o deployment persistente prima della review/preparazione manuale.

### D66 — Estensione B05 a valori variabili; precisioni approvate

**Nota corrente:** il solo gate sugli stadi sotto è storico e risolto da D67. Non richiedere altre conferme della medesima sequenza.

**Fonte:** Luigi Pelosi richiede «Estendiamola» e precisa, verbatim:

> Quantità fino a 6 decimali
> Prezzo unitario fino a 6 decimali
> Sconto %: 2 decimali 0-100
> Importi monetari: fino a 6 decimali
> Imposta: calcolata sull’imponibile aggregato per raggruppamento fiscale

**Decisione corrente:** estensione autorizzata solo per B05 privata/sintetica; superata la restrizione ai valori esatti del caso 001 e la precedente scala quantità 3/sconto intero. Le precisioni sopra non vanno riconfermate. La precisione monetaria del calcolo aziendale è distinta da visualizzazione o regolamento in valuta: nessuna riduzione automatica a due decimali di imposta/totale è autorizzata da D66. ROUND_HALF_UP è documentato in D41/D42 per gli stadi del caso 001, non prova sufficiente degli stadi della nuova politica a sei decimali.

**Unico gate matematico residuo G01/D46:** a quale stadio ridurre a sei decimali i risultati intermedi? Esempio verificato con Python Decimal: due righe (prestazione e ricambio), ciascuna quantità `1`, prezzo `0.000001`, sconto `50.00`, hanno netto esatto `0.0000005`. Arrotondando HALF_UP ciascuna riga a sei decimali prima della somma, base `0.000002`; mantenendo gli intermedi fino all’aggregazione, base `0.000001`. Chiedere se adottare la prima sequenza (netto riga HALF_UP a 6 → somma per gruppo → imposta HALF_UP a 6 → totale somma), oppure conservare gli intermedi fino al gruppo. La prima è una proposta, non una scelta approvata. Nessuna scelta implicita di arrotondamento fiscale a due decimali.

**Stato storico D66:** registrazione documentale del 19 ottobre 2026; estensione runtime allora ferma prima della scelta degli stadi. Nessun RED/GREEN nuovo in quel passaggio. Stato corrente ed evidenze: D67 e report B05.

### D67 — Sequenza numerica B05 confermata; implementazione a valori variabili

**Fonte e ambito:** le ripetute risposte «Confermo» di Luigi Pelosi si riferiscono alla prima sequenza esatta proposta in D66; l'istruzione successiva «Riprendi ultima attività» e la richiesta esplicita di implementare non riaprono tale scelta. Registrazione del 19 ottobre 2026. Nessuna approvazione estesa a politiche adiacenti.

**Decisione:** quantità/prezzo unitario fino a 6 decimali; sconto fino a 2 decimali, estremi 0 e 100 inclusi. Calcolare il netto di **ciascuna riga**, arrotondarlo ROUND_HALF_UP a **6 decimali**, sommare i netti arrotondati nel raggruppamento fiscale, calcolare l'imposta del gruppo e arrotondarla ROUND_HALF_UP a **6 decimali**; totale somma delle basi e imposte. Trasporto e visualizzazione monetaria conservano 6 decimali, senza riduzione implicita a 2. Due righe da netto esatto `0.0000005` danno quindi base `0.000002`.

**G01/D46:** chiusa la scelta delle politiche numeriche di questa estensione finita, non certificazione fiscale/legale generale. Evidenza eseguibile e limiti tecnici nel report B05: HTTP→SQL→GET, casi limite, DOM con fetch reale, retry/concorrenza e regressioni. D42 mantiene il solo ambito del caso 001 storico; altri trattamenti IVA, emissione reale e B12 richiedono le rispettive validazioni.

**Confini tecnici:** ancora una prestazione e un ricambio, IVA sintetica 22%, stessa lavorazione e pagante approvati, prezzi espliciti non derivati dal catalogo. Quantità positiva; prezzo zero e sconto 100 ammessi. Bound di rappresentazione/anti-overflow `numeric(12,6)` per quantità/prezzo (massimo `999999.999999`), non massimo commerciale o nuova regola di dominio; netto `numeric(18,6)`, sconto `numeric(5,2)`. Lessico invariante senza segno, esponente o separatore locale; valori equivalenti come `10.0` normalizzati.

**Stato:** B05 In corso, implementazione locale non committata. Review indipendente del candidato e accettazione manuale restano il prossimo gate. Nessun commit/push/merge/deployment persistente; B06–B14 restano bloccati/Backlog e non autorizzati. Esclusioni D64 invariate.

### D68 — Autorizzazione B06 circoscritta; parzialità da decidere prima del codice

**Nota storica:** il gate di parzialità e lo stato documentale sotto sono superati da D69; scope ed esclusioni restano validi.

**Fonte:** il nuovo «Procedi» del proprietario segue la consegna B05; la delega autorizza esclusivamente B06 e impone di non inventare policy di prenotazione. Registrazione del 19 ottobre 2026, baseline main pulita e identica a origin/main `605a7d5937b645681eb95cf644e228613b1d4ce8`. Prossimo ID effettivo verificato dopo D67.

**Scope positivo:** prenotare il ricambio da una riga commessa persistita, nel magazzino autorizzato appartenente alla sede di testata e alla società verificata. Inventory possiederà disponibilità/impegni; Workshop conserva testata/righe e Catalog l'identità comune tenant-wide. Contratti pubblici/adattatori, senza accesso diretto alle tabelle di altri moduli; identità verificata, permessi/capability esatti, RLS, audit e storico autorizzato. Quantità decimal/stringhe invarianti fino a sei decimali e limiti tecnici coerenti con D67; nessuna nuova policy monetaria. Giacenza fisica invariata; disponibilità impegnabile ridotta; insufficienza motivata senza blocco della commessa, retry/concorrenza senza doppi impegni o sovraprenotazione. Test del retry dopo disponibilità mediante sola fixture tecnica sintetica, non acquisti/ricevimento completo.

**Gate effettivo:** D34 decide la copertura della quantità prenotata, non se la riga possa essere prenotata in parte. La gestione delle parzialità è ancora aperta in D29; issue #12 non ha commenti e non risolve la scelta. Con una riga di 3 pezzi e soltanto 2 disponibili, consentire la prenotazione esplicita di 2 pezzi con 1 residuo oppure accettare soltanto l'intera quantità residua della riga cambia contratto, UI, bounds cumulativi e concorrenza. Nessuna delle alternative è adottata. Non confondere questa scelta con un riempimento parziale automatico della richiesta: l'insufficienza della quantità richiesta resta rifiutata secondo D34. Domanda unica al proprietario tramite parent nel report B06.

**Già risolto:** scelta del magazzino limitata alla sede di testata (D16), permessi/società distinti dalla visibilità anagrafica tenant-wide (D23/D65), customizing esclusivamente societario (D14), quantità sei decimali (D67), nessun blocco automatico dell'ordine e nessuna politica universale di stock negativo (D34). Non riaprire questi temi; D33 non autorizza picking in B06.

**Esclusioni e stato:** B07–B14, picking/preparazione, installazione/consumo, resi/carcassa, costi/valorizzazioni/margini, fiscalità/SdI/contabilità/amministrazione, acquisti completi, stock/dati/identità reali, provisioning o accesso pubblico. Nessun commit/push/merge o deployment manuale persistente prima di review del parent e preparazione manuale. Ambienti B02–B05, 18 container persistenti, storage/backup originali e Tailscale 443/8443–8446 non modificati né segreti letti. Solo documentazione locale; nessun codice, migrazione, RED/GREEN o CI B06. Issue #12 aperta/blocked, Project Backlog; B07–B14 aperti/blocked/Backlog e non autorizzati. Accettazione finita e piano prove nel [report B06](../b06-verification.md).

### D69 — Prenotazione parziale esplicita autorizzata

**Fonte e ambito:** Luigi Pelosi sceglie esplicitamente l’opzione A e autorizza la ripresa dell’implementazione B06. La successiva istruzione di riprendere e finire conferma il reset delle sole fixture sintetiche effimere B06, previa verifica dell’identità del progetto, senza autorizzare modifiche agli ambienti persistenti. Registrazione del 19 ottobre 2026; nessun nuovo requisito adiacente approvato.

**Decisione:** su riga di 3 pezzi con 2 disponibili l’operatore può richiedere esplicitamente 2, lasciando 1 da prenotare. Ogni comando richiede quantità positiva q6 non superiore al residuo cumulativo della riga né alla disponibilità del magazzino autorizzato della sede di testata. La richiesta di 3 con disponibilità 2 viene rifiutata integralmente: mai troncamento automatico né blocco dell’ordine. I parziali su magazzini diversi condividono il medesimo limite di riga. Fisico invariato; disponibilità = fisico − impegni attivi.

**Scope ed esclusioni:** esclusivamente B06 privata/sintetica D68. Il retry dopo disponibilità usa una fixture tecnica isolata, non una policy acquisti/ricevimento. Nessun picking, consumo, rilascio/annullamento, costo, fiscalità o B07–B14. Review indipendente, preparazione e accettazione manuale del parent restano prima della consegna; nessun commit/push/merge/deploy persistente autorizzato.

**Evidenza corrente:** modulo Inventory e porta pubblica Workshop, UI italiana con fetch reale, test HTTP/SQL/RLS/audit, migrazioni ripetute/rollback/reapply e concorrenza controllata disponibili localmente. Il precedente test di stock passato senza RED non è evidenza test-first: la nuova barriera SQL ha riprodotto otto successi concorrenti sulla disponibilità di due, prima del lock di riga; cinque interleaving passano dopo il fix. Dettagli, comandi, limiti e regressioni nel [report B06](../b06-verification.md). G02/B06 tecnicamente esercitato, non completamento del backlog o validazione di B07–B09.

### D70 — Consegna autonoma sequenziale B07–B14 autorizzata

**Fonte:** istruzione esplicita corrente di Luigi Pelosi, 19 ottobre 2026, dopo B06 PR #27 incorporata in main `d03b661624b67a9bb41c8ee2d48fde17019246e1`. Autorizzati B07–B14 nell'ordine del backlog, un solo WIP: test/audit → commit → PR → CI remota verde sullo SHA esatto → merge → CI main → chiusura issue/board. Nessuna nuova approvazione del proprietario, review LLM o accettazione manuale di routine per ogni incremento.

**Confini:** esclusivamente dati/identità sintetici e accettazione effimera isolata; nessun nuovo ambiente manuale persistente, deploy pubblico, acquisto, ERP/SdI reale, incasso o conformità fiscale generale. Bootstrap HTTP e Tailscale 443, segreti, backup e volumi conservati non si modificano. Le precedenti frasi di mancata autorizzazione B07–B14 e gate manuali sono storiche e superate, non i gate di dipendenza, sicurezza, dominio o specialistici. Questi si verificano nel rispettivo incremento; una reale scelta non confermata richiede una sola domanda concreta. OPE03 prova restore sintetica in B14; responsabilità/target operativi OPE03–OPE05 restano prima di servizio/pilota, non nuovi blocchi d'avvio.

### D71 — Prelievo parziale esplicito confermato

**Fonte:** «Confermo» riferito alla proposta esatta: su 2 pezzi prenotati è possibile prelevarne esplicitamente 1, lasciando l'altro prenotato da prelevare. Registrazione del 19 ottobre 2026 dopo verifica dell'ultimo ID effettivo D69.

**Decisione:** quantità positiva q6, non superiore al residuo non prelevato della specifica prenotazione nel magazzino autorizzato della sede di testata. Nessun troncamento o aumento implicito; provenienza, lista di prelievo, assegnazione commessa/lavorazione e collocazione persistite. Il prelievo interno lascia fisico e impegno invariati: il materiale prelevato non torna disponibile. Area facoltativa societaria D33; disabilitata significa nessun transito fittizio, non consumo. G02/B07 è risolto quanto alla parzialità; prove di concorrenza, retry, autorizzazione e stock restano richieste. Nessuna decisione sulla parzialità di installazione/consumo B08, rilascio/annullamento o reso nuovo.

### D72 — Installazione parziale esplicita confermata

**Fonte:** «Confermo» del proprietario Luigi Pelosi riferito alla proposta esatta: su 2 pezzi prelevati è possibile installarne esplicitamente 1, consumando 1 e riducendo il fisico di 1; l'altro resta prelevato e non installato. L'istruzione corrente autorizza ripresa e consegna sequenziale D70; verificato D71 come ultimo ID prima della registrazione.

**Decisione:** quantità finita positiva con massimo sei decimali, entro il residuo prelevato non installato della provenienza selezionata; nessuna riduzione, arrotondamento o completamento automatico. Il prelievo o eventuale consegna non costituiscono installazione. La giacenza fisica diminuisce soltanto per il consumo effettivo; contestualmente Inventory estingue la corrispondente quota dell'impegno attivo, senza liberare disponibilità fittizia né riscaricare la preparazione. Le quantità originariamente prenotate/prelevate restano fatti storici; disponibilità = fisico − (prenotato − consumato), non fisico − prenotato originario.

**Semantica tecnica esecutiva, non ulteriore policy di dominio:** Workshop registra il fatto tecnico in una transazione locale con limite cumulativo/idempotenza; solo dopo il commit Inventory applica il consumo in una propria transazione, usando la stessa identità stabile, blocco stock condiviso con prenotazioni e snapshot/provenienze verificati tramite contratti pubblici. Un fallimento dopo il primo commit mantiene installazione e quota impegnata, mostra consumo Pending e si recupera ripetendo lo stesso comando senza duplicare l'installazione o lo scarico. Nessuna atomicità globale o worker/esito automatico promesso. Timestamp server normalizzato alla precisione PostgreSQL e identità operatore verificata, non valori fidati del client.

**Confini:** B08 sintetica/effimera; customizing societario, sede di testata, azioni/scope/capability, RLS e storia autorizzata restano vincolanti. Collegamenti a commessa/lavorazione/riga/prelievo/prenotazione/catalogo e tipo/versione sorgente preservati; la versione sorgente non congela universalmente il customizing delle operazioni future. Il rientro carcassa e le sue quantità/condizioni si verificano in B09; non sono dedotti da D72. Nessun rilascio, annullamento, reso nuovo, costo/valorizzazione, politica fiscale futura o nuova autenticazione. Prove eseguibili e CI restano necessarie prima di chiamare B08 consegnata.
