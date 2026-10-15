# Dossier di fondazione — 01. Glossario e confini di dominio

**Stato:** bozza per discussione; non approvata.
**Ambito:** linguaggio del post-vendita e responsabilità dei contesti. Nessuna autorizzazione a implementare moduli.
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
| Disponibilità | Available quantity | Quantità utilizzabile secondo regole esplicite. Formula, unità di misura e trattamento degli arrivi previsti non ancora approvati. | CH §10.2; DA |
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
