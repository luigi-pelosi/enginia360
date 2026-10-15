# Dossier di fondazione — 04. Prima vertical slice

**Stato:** perimetro minimo confermato in D28; flusso e contratti seguenti sono proposte per revisione. Nessuna autorizzazione a implementare prima dell'approvazione del dossier.
**Fonti:** `PROJECT_CHARTER.md` §11–14; [decisioni D3–D28](01-glossary-and-domain-boundaries.md); [capability e data ownership](03-capabilities-and-data-ownership.md).

## 1. Obiettivo e confini

Dimostrare un unico percorso operativo dalla commessa al risultato economico, con due destinazioni alternative. Stessa logica officina nei due casi, nessun ramo per nome/identificativo cliente.

**Significato confermato in D32:** il risultato della prima slice è il riepilogo commerciale: imponibile al netto degli sconti, imposte e totale a carico. Determinazione dei costi e marginalità, anche provvisoria, sono rinviate; il riepilogo non è un margine né un utile. Parametri e arrotondamenti di prova restano da concordare, senza implicita validazione fiscale.

**Incluso:** contesto tenant/società/sede autorizzato, cliente e veicolo con intestatario distinto dal pagante, creazione diretta della commessa consentita dal tipo, una prestazione e un ricambio, un solo soggetto a carico, prenotazione, prelievo, installazione/consumo e rientro della carcassa in una configurazione esplicita di esempio, valorizzazione esplicita, destinazione interna o connettore simulato con coda/recupero.

**Rinviato:** ripartizioni e garanzia, calendario completo, acquisti completi, workflow editor visuale, raggruppamenti e storni completi, ERP reali, trasmissione SdI e conservazione, contabilità ordinaria completa, GUI definitiva. Il rinvio non elimina tali requisiti di prodotto o autorizza un modello incompatibile.

**Composizione minima proposta:** Enginia360 autorevole su anagrafiche necessarie allo scenario, catalogo e magazzino nei due percorsi; cambia soltanto la destinazione amministrativa. Il magazzino esterno del profilo P1 è una variante ulteriore, non una dipendenza implicita della prima slice. La coda è provata verso la destinazione amministrativa simulata; ciò non dimostra già il protocollo di prenotazione stock di un ERP reale.

**D36 — Controparte aziendale minima:** per il primo scenario, dati comuni al tenant = ragione sociale, identificativo fiscale e indirizzo della sede legale; dati societari = una destinazione operativa aggiuntiva riservata alla società che la registra, salvo condivisione esplicita autorizzata. Dati esclusivamente sintetici; nessuna definizione di obbligatorietà fiscale o catalogo anagrafico completo.

## 2. Percorso proposto: comandi, fatti e ownership

Nomi esemplificativi in inglese, non contratti API già approvati. I fatti non impongono pubblicazione asincrona o un broker: gli eventi distribuiti si introducono solo dove necessari. Confini e ownership tecniche dei concetti commerciali comuni restano da consolidare nella solution.

| Passo | Comando/caso d'uso proposto | Fatto/esito proposto | Proprietario logico |
| --- | --- | --- | --- |
| Contesto | SelectOperatingContext | Contesto autorizzato verificato; non un evento di dominio obbligatorio | Organizzazioni/accessi |
| Riferimenti | RegisterOrSelectCounterparty / RegisterOrSelectVehicle | Riferimenti distinti a intestatario e soggetto a carico | Anagrafiche / Veicoli |
| Apertura | CreateWorkshopOrder | WorkshopOrderCreated | Officina, con significato ordine cliente e tipo societario configurato |
| Contenuto | AddServiceLine / AddPartLine | Righe operative/commerciali registrate | Officina; referenze a catalogo e condizioni |
| Prenotazione | ReservePart | PartReserved oppure rifiuto motivato | Magazzino |
| Prelievo e preparazione | PickPartForWorkshopOrder | PartPicked, distinto dal consumo; collocazione/assegnazione tracciata | Magazzino |
| Consegna al tecnico, se distinta nel flusso | HandOverPickedPart | Presa in carico operativa, non prova automatica di installazione | Responsabilità di consegna da dettagliare tra Magazzino/Officina |
| Installazione e consumo | RecordPartInstallation / ConfirmPartConsumption | Installazione registrata e consumo coerente, senza duplicare lo scarico per retry | Officina per il fatto tecnico; Magazzino per gli effetti di stock |
| Rientro carcassa, dove previsto | ReceiveReplacedComponent | Particolare sostituito ricevuto, distinto dal nuovo e dal suo reso inutilizzato | Confine Officina/Magazzino da dettagliare |
| Risultato | CalculateWorkshopOrderOutcome | Valori della commessa determinati con regole/versioni esplicite | Officina, senza duplicare il motore fiscale/contabile |
| Percorso interno | CreateDraftInvoice / ConfirmInvoice | Fattura tecnica confermata e riferita alla commessa | Fatturazione |
| Contabilità interna | PostInvoiceJournalEntry | Registrazione quadrata, con riferimenti alla fattura e alla commessa | Contabilità |
| Percorso esterno | RequestExternalAdministrativeProcessing | Richiesta persistente con identificativo stabile | Modulo proprietario del caso d'uso, con outbox nella propria transazione |
| Invio/esito | DispatchPendingRequest / RecordExternalOutcome | Conferma, attesa, rifiuto o esito incerto, riconciliabili | Connettore per trasporto/mappatura; dominio per conseguenze del risultato |

La selezione del contesto non si fida di un identificativo inviato dal client: controllare appartenenza e autorizzazione server-side. Magazzino appartenente alla sede della testata. La conferma di fattura e la scrittura contabile sono transazioni dei rispettivi moduli; il processo deve rendere visibili eventuali esiti parziali, non promettere atomicità globale.

**D34 — Prenotazione coperta da disponibilità nel caso minimo:** il ricambio può essere inserito nella commessa anche quando non è disponibile, ma la prenotazione riesce soltanto se la disponibilità impegnabile è sufficiente. Il rifiuto è motivato e non blocca automaticamente tutta la commessa. Dopo il ricevimento e la disponibilità del materiale si può riprovare. Richieste strutturate in attesa di approvvigionamento rinviate. Decisione limitata allo scenario dimostrativo: non approva una politica universale di stock negativo o ulteriori blocchi di workflow.

## 3. Destinazioni alternative e continuità

### Interna

Commessa → risultato → fattura bozza/confermata → scrittura quadrata. È un percorso tecnico con regole dichiarate e testate, non fatturazione fiscale o validazione del commercialista. Piano dei conti, casi IVA e arrotondamenti devono essere espliciti e validati prima di uso reale, non inventati dall'agente.

### Esterna simulata

Commessa → risultato → richiesta persistente → tentativo invio → esito visibile.

Scenari da provare: destinatario disponibile, indisponibile con recupero, rifiuto di business e timeout con esito incerto. Idempotenza dell'operazione e deduplicazione/verifica esito evitano duplicazioni; nessuna promessa exactly-once dalla sola coda. Restart del worker non deve perdere le richieste già salvate.

Default confermato in D27: operazioni accodabili; chiusure definitive subordinate a conferma esterna bloccate in assenza di tale conferma. La chiusura tecnica locale è distinta da quella amministrativa come confermato in D37. Deroghe solo se configurate, autorizzate e tracciate entro invarianti inderogabili.

**D37 — Chiusura tecnica e amministrativa separate nel primo scenario esterno:** a lavorazioni concluse e requisiti locali configurati soddisfatti, la chiusura tecnica è consentita anche se il gestionale esterno è indisponibile. La richiesta amministrativa è conservata nella coda persistente; stato visibile «completata tecnicamente — in attesa di conferma amministrativa». La chiusura amministrativa resta bloccata fino alla conferma dell'esito di business richiesto, non al solo invio riuscito. Un rifiuto rimane visibile e richiede riconciliazione, preservando i fatti tecnici già avvenuti. Nessuna autorizzazione implicita a incasso, riconsegna del veicolo o deroghe ai vincoli configurati.

## 4. Criteri di accettazione proposti

- Scenario ripetibile con istruzioni locali, dati esclusivamente di test e nessuna esposizione di dati aziendali sul bootstrap pubblico.
- Almeno due tenant di test: lettura, scrittura, ricerca e lavorazione della coda non devono oltrepassarne il perimetro.
- Accesso a società/sede/magazzino non concessi rifiutato lato server; appartenenza al tenant non equivale ad accesso universale.
- Intestatario del veicolo diverso dal soggetto a carico, preservati entrambi selezionando il veicolo.
- Una prestazione e un ricambio nella commessa, con un solo soggetto a carico nello scenario minimo.
- Prenotazione incide sulla disponibilità, non sulla giacenza fisica; prelievo/preparazione e installazione sono fatti distinti. La collocazione interna non equivale automaticamente a consumo; gli effetti di stock per perimetro saranno esplicitati e non duplicati da retry o dal passaggio al consumo.
- Carcassa rientrata distinta dal componente nuovo inutilizzato: non ripristina automaticamente disponibilità del nuovo. Il rientro è incluso nel caso minimo confermato; regole ed effetti della configurazione dimostrativa restano da specificare prima dell'implementazione.
- Importi monetari decimal/value object e regole esplicite/riproducibili di imponibile, IVA e arrotondamento; parametri tecnici dimostrativi non presentati come fiscalmente validati.
- Percorso interno mantiene i riferimenti commessa/fattura/scrittura e verifica quadratura/idempotenza.
- Percorso esterno conserva la richiesta durante indisponibilità e riavvio; ritenta solo quando appropriato, mostra tentativi/errori ed evita doppi effetti su esiti incerti.
- Stato locale, esito esterno e stato amministrativo distinguibili; blocchi/deroghe coerenti con D27.
- Capability disabilitata impedisce nuovi utilizzi tramite endpoint, menu e job pertinenti senza eliminare storico autorizzato. Controllo di gestione non necessario al flusso.
- Errori diagnosticabili tramite correlation ID e audit pertinente senza dati sensibili non necessari.

Questi criteri derivano dal charter e dai chiarimenti, non sono dichiarazioni di test già eseguiti. Test, autorizzazione a implementare, piano di migrazione/rollback e approvazione specialistica restano fasi successive.

## 5. Prelievo e installazione distinti — chiarimento D29

**Confermato dal proprietario:** prelievo e installazione sono momenti distinti. I componenti destinati a una lavorazione possono essere preparati in un'area dedicata e ritirati dal tecnico successivamente. La proposta precedente di assimilare prelievo e consumo è ritirata. Il ritiro dal punto di preparazione non dimostra automaticamente l'installazione.

**Flusso concettuale aggiornato:** prenotazione → prelievo/preparazione → eventuale consegna al tecnico → installazione/consumo. Distinti da questo flusso: reso del nuovo non utilizzato e rientro della carcassa (particolare sostituito inutilizzabile). **D30 conferma che la politica di restituzione è decisa da chi prepara il customizing societario del tipo documento**, compresi i vincoli di workflow/chiusura applicabili. Non è scelta una politica globale di blocco; il catalogo dei parametri concreti resta da dettagliare.

**D33 — area facoltativa:** il gestore di sistema autorizzato decide nel customizing societario se usare l'area di preparazione. È accettato l'esempio di un'ubicazione nello stesso magazzino, senza renderlo un vincolo universale. Con area abilitata, il trasferimento interno mantiene il componente in giacenza e assegnato alla commessa; senza area, nessun transito fittizio è richiesto. Prelievo e installazione/consumo restano distinti in entrambi i percorsi, senza doppi scarichi.

Area fisica e picking list non sono sinonimi: la lista può guidare/documentare il prelievo senza imporre un'area. Il customizing non modifica implicitamente i criteri di valorizzazione o le regole contabili; valgono sede unica di testata, permessi, audit e non retroattività predefinita.

**D35 — Tracciabilità minima della carcassa confermata:** registrare commessa e lavorazione di provenienza, collegamento alla riga del ricambio installato, descrizione e quantità del particolare rientrato, data e operatore di ricezione. Per il primo scenario non si introducono un catalogo separato delle carcasse o una matricola obbligatoria. Il rientro non aumenta la disponibilità dei ricambi nuovi; politica di restituzione e conseguenze di workflow restano nel customizing societario del tipo documento (D30).

**D39 — Configurazione societaria dimostrativa confermata:** prestazione e ricambio sono collegati alla stessa lavorazione; area di preparazione abilitata per esercitare la separazione fra prelievo e installazione; rientro della carcassa richiesto per il ricambio dell'esempio prima della chiusura tecnica. Sono valori del tipo documento dello scenario di prova, non obblighi universali: restano governati dal customizing societario. La chiusura tecnica di D37 richiede quindi anche tale rientro nel caso dimostrativo. Restano separati permessi, invarianti e regola di non retroattività.

### Perimetro dimostrativo confermato

Luigi Pelosi conferma di includere nel primo scenario un componente con prelievo, installazione e rientro della carcassa, usando una configurazione esplicita di esempio. La gestione completa delle varianti è rinviata agli incrementi successivi. La conferma riguarda il perimetro, non una politica specifica di obbligatorietà o blocco né l'approvazione dell'intero dossier.

Il criterio di accettazione del caso minimo comprende quindi fatti distinti e riferimenti coerenti: componente prelevato, installazione registrata, particolare sostituito rientrato senza incremento improprio della disponibilità del nuovo. La tracciabilità minima della carcassa è confermata in D35. La destinazione fisica del rientro è chiarita in D38: ubicazione dedicata ai particolari sostituiti, separata dal nuovo e non vendibile, senza introdurre valorizzazione o smaltimento. I parametri di associazione alla lavorazione, area e vincolo di rientro sono confermati in D39; ulteriori dettagli esecutivi di stock restano da progettare e verificare negli incrementi pertinenti. L’area facoltativa e l’esempio di ubicazione interna sono chiariti in D33. Nessuna implementazione autorizzata da questa sola conferma.
