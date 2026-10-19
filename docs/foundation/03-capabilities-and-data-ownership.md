# Dossier di fondazione — 03. Capability e data ownership

**Stato:** proposta per revisione, non approvata. I principi D24–D26 sono confermati; le assegnazioni dei profili e le dipendenze sotto sono proposte da validare.
**Ambito:** tre scenari societari di riferimento, responsabilità sui dati e prerequisiti funzionali. Nessun catalogo commerciale, prezzo, schema database, contratto API o implementazione.
**Fonti:** `PROJECT_CHARTER.md` §7.1–7.3, §8–9, §11–12; [decisioni D3–D26](01-glossary-and-domain-boundaries.md); [organizzazione e accessi](02-organization-and-access.md). Nessuna nuova regola dedotta dal legacy.

## 1. Principi acquisiti

- Le società di uno stesso tenant possono usare capability e sistemi autorevoli differenti (D24–D25).
- Il nucleo anagrafico comune ha una sola autorità designata per il tenant, Enginia360 o un sistema esterno; i dati societari possono avere autorità proprie (D26).
- Le copie sincronizzate non sono una seconda autorità. Ownership di un dato e possibilità di inoltrare un comando al sistema autorevole non sono sinonimi.
- Customizing societario, entitlement, feature flag e permessi restano distinti. Le capability di un'altra società non conferiscono accesso o attivazione impliciti.
- Gli sviluppi documentali sono configurabili; gli scenari sotto non impongono una sequenza universale né un predecessore obbligatorio per le fatture.

## 2. Scenari proposti

| Profilo | Obiettivo operativo | Enginia360 | Sistema esterno |
| --- | --- | --- | --- |
| P1 — Officina integrata | Usare Enginia360 per l'operatività, mantenendo l'ERP amministrativo e logistico. | Appuntamenti, accettazione, commesse, lavorazioni, assegnazioni e consuntivi. | Catalogo/prezzi, magazzino autorevole, fatturazione, contabilità e tesoreria. |
| P2 — Post-vendita con contabilità esterna | Gestire operatività, ricambi e fatturazione in Enginia360; contabilizzare altrove. | Officina, catalogo/prezzi, magazzino, acquisti e fatturazione. | Contabilità e tesoreria. |
| P3 — Post-vendita con contabilità interna | Gestire il ciclo operativo e amministrativo in Enginia360. | Officina, catalogo/prezzi, magazzino, acquisti, fatturazione, contabilità e tesoreria. | Eventuali servizi/connettori specialistici da scegliere separatamente. |

Sono composizioni esemplificative, non pacchetti indivisibili. La contabilità interna non implica attivazione del controllo di gestione. Provider SdI/conservazione e conformità fiscale restano decisioni aperte; il percorso tecnico della prima slice non equivale al servizio fiscale completo.

## 3. Matrice del sistema autorevole proposto

**E:** Enginia360 autorevole. **X:** sistema esterno autorevole. **T:** scelta unica per il nucleo comune a livello tenant, indipendente dal profilo della società. Queste sigle identificano l'autorità, non il luogo fisico di ogni copia dei dati.

| Dato o processo | Perimetro | P1 | P2 | P3 |
| --- | --- | --- | --- | --- |
| Identità comune della controparte | Tenant | T | T | T |
| Relazione cliente/fornitore, codici e condizioni societarie | Società | X | E | E |
| Destinazioni comuni della controparte | Tenant | T, con dettaglio delle responsabilità da definire | Come P1 | Come P1 |
| Destinazioni riservate | Società | X, salvo composizione specifica diversa | E | E |
| Identità veicolo e relazioni anagrafiche | D63: gestione come controparti; selezione commessa nel tenant verificato, senza permessi gestionali impliciti | X | E | E |
| Appuntamenti e pianificazione officina | Società/sede | E | E | E |
| Accettazione, commessa/ordine cliente officina | Società/sede | E | E | E |
| Lavorazioni, assegnazioni e tempi effettivi | Società/sede | E | E | E |
| Catalogo articoli/prestazioni e condizioni applicabili | Società; eventuale nucleo condiviso ancora aperto | X | E | E |
| Prenotazioni di stock e disponibilità impegnabile | Società/sede/magazzino | X | E | E |
| Movimenti confermati, consumi e giacenze | Società/sede/magazzino | X | E | E |
| Ordini di acquisto e ricevimento logistico | Società/sede/magazzino | X | E | E |
| Emissione e rettifica delle fatture | Società | X | E | E |
| Scritture e saldi contabili | Società | X | X | E |
| Scadenze, incassi e riconciliazione finanziaria | Società | X | X | E |
| Esiti e stato dei connettori Enginia360 | Società e autorità comune quando pertinente | E | E | E, se connettore presente |

**Limiti della matrice:**

- La scelta T non è ripetuta per società: due ERP societari non diventano master concorrenti dell'identità comune.
- P1 può mostrare dati esterni e inoltrare richieste di prenotazione/consumo, senza dichiararli confermati prima dell'esito del proprietario. Una richiesta pendente non è una prenotazione autorevole.
- Una fattura emessa esternamente può essere rappresentata in Enginia360 tramite riferimento/copia controllata, senza una seconda emissione interna.
- La commessa resta ordine cliente operativo in Enginia360 anche se l'ERP richiede una propria rappresentazione commerciale: eventuale replica è mappata, non una seconda autorità sullo stesso processo operativo. Il contratto deve distinguere i fatti di ciascun sistema.
- Per P2, incassi/scadenze esterni possono essere visibili tramite proiezioni; eventuale raccolta pagamenti in Enginia360 richiede una composizione ulteriore da definire, non è approvata qui.
- D63 risolve il perimetro veicoli: lettura/add/edit/remove seguono le regole approvate delle corrispondenti operazioni sulle controparti, senza inventare add/remove dell'identità comune non implementati in B03. La selezione per commessa è invece ammessa nell'intero tenant verificato mediante una proiezione minima dedicata: non concede accesso gestionale al veicolo, all'intestatario o ai dati riservati delle altre società. Per B04 bastano fixture sintetiche e selettore, non CRUD completo. Il perimetro condiviso del catalogo resta non deciso.
- La destinazione societaria resta locale per default; una promozione al nucleo comune deve essere governata dal proprietario di quest'ultimo, non una scrittura concorrente da ERP diversi.
- Le prove pilota possono portare ad altre composizioni valide. L'elenco non certifica che i relativi ERP espongano tutti i contratti necessari.

## 4. Dipendenze e prerequisiti funzionali proposti

Le dipendenze sotto sono prerequisiti di comportamento, non riferimenti tra assembly o permesso di accedere direttamente ai dati di un altro modulo. Una fonte esterna o una proiezione controllata può soddisfare il fabbisogno previsto dal contratto.

| Capability | Prerequisito minimo proposto | Fonte interna/esterna |
| --- | --- | --- |
| Officina | Contesto tenant/società/sede autorizzato; riferimenti a controparti, veicoli dove richiesti e offerta di articoli/prestazioni. | Fonti autorevoli dichiarate; nessun obbligo generale di contabilità interna. |
| Prenotazione/consumo ricambi | Articolo identificato, magazzino autorizzato della sede, regole e autorità di stock definite. | Magazzino E oppure contratto X. |
| Acquisti | Relazione fornitore, articoli, condizioni e contratto con il ricevimento/magazzino. | Interno oppure esterno come composizione esplicita. |
| Fatturazione | Società emittente, dati destinatario, righe valorizzate e regole validate. | Non richiede sempre una commessa precedente: il customizing può consentire creazione diretta. |
| Contabilità interna | Regole validate, piano dei conti, fatti/documenti da registrare e riferimenti riconciliabili. | Fonte dei fatti dichiarata; nessuna doppia registrazione a fronte di retry. |
| Tesoreria | Scadenze, pagamenti e loro riconciliazione, con un unico proprietario dichiarato. | Le dipendenze precise saranno progettate senza imporre la contabilità Enginia360 a chi usa una fonte esterna. |
| Connettore | Contratto versionato, mappature, autorità definite, credenziali protette e politiche di errore/riconciliazione. | Necessario solo quando un processo attraversa il confine esterno. |

Nessuna capability deve dipendere obbligatoriamente dal controllo di gestione. Il disegno tecnico delle dipendenze deve essere aciclico, come richiesto dal charter; questa tabella non ne costituisce già la verifica architetturale.

## 5. Entitlement, attivazione, customizing e permessi

| Meccanismo | Domanda a cui risponde | Stato |
| --- | --- | --- |
| Entitlement | Il cliente ha diritto a utilizzare la capability? | Distinzione del charter; catalogo commerciale e assegnazione ancora aperti. |
| Attivazione societaria | Quale società usa quella capability e con quale sistema autorevole? | Differenziazione societaria confermata; procedura di attivazione proposta da dettagliare. |
| Customizing | Come opera quel tipo documento/processo nella società? | Scope esclusivamente societario confermato; vincoli del sistema non aggirabili. |
| Feature flag | La funzione è tecnicamente rilasciata al perimetro previsto? | Non sostituisce entitlement o autorizzazione. |
| Permesso e scope | Questo utente può compiere questa azione su questa risorsa? | Accessi societari espliciti; limiti sede/magazzino e permesso anagrafico confermati. |
| Extension point | Come tradurre e collegare un sistema esterno tramite un contratto supportato? | Principio del charter; provider e contratti pilota ancora aperti. |

**Criteri proposti per un'attivazione:** validare entitlement, dipendenze, fonte autorevole, configurazioni, permessi e migrazioni; verificare un connettore se richiesto; impedire attivazioni incoerenti. La disattivazione non cancella storico autorizzato e deve disciplinare richieste pendenti e sviluppi ancora aperti. Nessuna licenza commerciale per società viene inventata qui.

## 6. Contratti tra profili e prima vertical slice

La slice del charter mantiene officina uguale nei profili interno/esterno. Cambia la destinazione del risultato, non il nome del cliente né un ramo permanente del codice:

- percorso interno: risultato della commessa → bozza/conferma fattura → scrittura quadrata secondo regole tecniche esplicite, ancora da validare fiscalmente;
- percorso esterno: risultato → richiesta idempotente al connettore simulato → esito/errore e riconciliazione visibili.

Sono confini di caso d'uso, non un workflow universale imposto a tutti i tipi documento. La simulazione del connettore dimostra comportamento tecnico, non compatibilità con ERP reali.

## 7. Punto di validazione successivo

**Default confermato dal proprietario Luigi Pelosi:** registrare le operazioni in attesa nella coda persistente, ma bloccare le chiusure definitive che richiedono conferma esterna. Eventuali deroghe sono abilitate nel customizing societario, soggette a permesso specifico e tracciate. La conferma riguarda questo default e le condizioni delle deroghe; non approva l'intero dossier o tutti i profili della matrice.

Una deroga non può simulare una conferma esterna, eliminare un esito incerto o aggirare vincoli inderogabili di integrità, sicurezza o validità fiscale. D37 chiarisce chiusura tecnica consentita al soddisfacimento dei requisiti locali e chiusura amministrativa bloccata fino alla conferma di business nel primo scenario esterno. Restano da definire separatamente ulteriori operazioni fisiche durante il disservizio, altre politiche di stock e le ulteriori chiusure/deroghe ammissibili.

**D37 — Chiusura tecnica e amministrativa separate nel primo scenario esterno:** a lavorazioni concluse e requisiti locali configurati soddisfatti, la chiusura tecnica è consentita anche se il gestionale esterno è indisponibile. La richiesta amministrativa è conservata nella coda persistente; stato visibile «completata tecnicamente — in attesa di conferma amministrativa». La chiusura amministrativa resta bloccata fino alla conferma dell'esito di business richiesto, non al solo invio riuscito. Un rifiuto rimane visibile e richiede riconciliazione, preservando i fatti tecnici già avvenuti. Nessuna autorizzazione implicita a incasso, riconsegna del veicolo o deroghe ai vincoli configurati. Nessun prelievo fisico è autorizzato implicitamente dall'accodamento.

### Indirizzo accettato — coda persistente durante indisponibilità

Il proprietario accetta la proposta di una coda persistente per le operazioni verso il sistema esterno indisponibile, con stati visibili, invio al ripristino, tentativi controllati e gestione degli esiti senza simulare una conferma autorevole. L'assenso non autorizza operatività degradata illimitata né approva l'intero dossier. PostgreSQL con worker .NET è la soluzione iniziale proposta nella discussione, non ancora implementata o verificata sul caso reale. Il dettaglio degli algoritmi e delle politiche operative resta da definire.

**Proposta tecnica:** registrare in PostgreSQL richieste persistenti con identificativo idempotente, tenant/società, provenienza, dati/versione e stato. Salvare atomicamente il fatto locale e la richiesta di integrazione quando appartengono alla stessa transazione del modulo (outbox); un worker .NET ne cura invio, tentativi con attesa e recupero. Non richiede per il bootstrap di dominio un broker separato; implementazione da verificare. Stati proposti: in attesa, in invio, confermata, errore temporaneo, rifiutata/da riconciliare, esito incerto. UI e audit espongono tentativi ed esiti senza simulare conferme esterne.

**Garanzie da progettare:** ordine per flusso/risorsa interessata, dipendenze tra operazioni, retry limitati con escalation, identificazione duplicati nel destinatario o verifica/riconciliazione prima di reinviare in caso di esito incerto. Timeout non dimostra mancata esecuzione esterna: nessuna promessa exactly-once derivante dalla sola coda. L'autorità esterna può rifiutare per insufficienza stock, dati o autorizzazioni; il rifiuto non è un guasto temporaneo da ritentare all'infinito.

Distinguere sempre richiesta pendente da conferma autorevole. Se il fatto fisico è già avvenuto (ricambio realmente utilizzato), conservarne la rilevazione operativa distinta dall'esito di registrazione nell'ERP. L'accodamento non autorizza automaticamente prelievi fisici, superamento disponibilità, chiusure definitive o emissioni fiscali senza i prerequisiti: politiche di continuità e responsabilità da approvare. Il disservizio riguarda l'ERP, non il funzionamento offline del client rispetto a Enginia360.

**Criterio di avanzamento:** validare i profili come scenari, correggere le assegnazioni di autorità e chiarire il comportamento d'indisponibilità prima di dettagliare comandi/eventi della slice. Documento locale di lavoro; nessuna modifica a runtime o flag di approvazione del dossier.
