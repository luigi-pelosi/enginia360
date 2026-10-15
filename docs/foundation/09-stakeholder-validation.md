# Dossier di fondazione — 09. Validazioni dei referenti (D01)

**Stato:** domande preparate; risposte specialistiche non ancora acquisite. D01 resta in corso.
**Fonti:** `PROJECT_CHARTER.md` §11–12 e §15; [slice](04-first-vertical-slice.md); [decisioni D32–D37](01-glossary-and-domain-boundaries.md); issue GitHub #3.

## 1. Disponibilità e responsabilità

Luigi Pelosi, proprietario del prodotto, conferma che il commercialista o referente amministrativo è disponibile. Non è stato specificato quale dei due ruoli ricopra il referente; non sono richiesti nominativi o dati di contatto nel repository.

La disponibilità non costituisce risposta, presa in carico del referente o validazione fiscale/contabile. Il proprietario coordina la raccolta delle risposte; gli aspetti che richiedono competenza fiscale devono essere validati dal commercialista, eventualmente tramite il referente amministrativo. Nessun contatto esterno è stato effettuato dall'agente.

## 2. Domande da sottoporre al referente disponibile

Per ogni risposta registrare ruolo del validatore, versione del caso, risultato atteso ed eventuali limiti. Utilizzare esclusivamente esempi sintetici o anonimizzati.

| ID | Domanda / risultato richiesto | Validatore richiesto | Prima di | Stato |
| --- | --- | --- | --- | --- |
| F01 | Quale caso di vendita domestica usare come riferimento per una prestazione e un ricambio? Fornire trattamento IVA atteso, imponibile, imposte e totale di un esempio sintetico, distinguendo regola validata e parametro tecnico di prova. | Commercialista, tramite referente disponibile se necessario | Validazione dei parametri B05; uso reale | Da sottoporre |
| F02 | Quali precisioni e arrotondamenti adottare per quantità, prezzi, sconti, righe, imponibile e imposte? Fornire casi limite con esiti attesi e criterio di gestione degli scarti. | Referente amministrativo con validazione del commercialista per gli aspetti fiscali | B05 e B12 | Da sottoporre |
| F03 | Quali dati e riferimenti conservare nella fattura tecnica collegata alla commessa? Quali differenze devono restare esplicite rispetto a una fattura realmente emessa? | Referente amministrativo/commercialista secondo competenza | B12; prima di uso fiscale reale | Da sottoporre |
| F04 | Quale piano dei conti dimostrativo e quale scrittura attesa usare per il caso F01, con riferimenti fattura/commessa? Specificare conti, importi attesi e quadratura; l'agente non sceglie il piano. | Commercialista | B13 | Da sottoporre |

Costi del venduto, criteri di valorizzazione per marginalità, ciclo passivo completo e margine sono rinviati da D32. Queste domande non riaprono tale perimetro. Nessuna aliquota, conto, scrittura o conformità è approvata dal presente documento.

La prova tecnica e la validazione specialistica sono esiti distinti. Parametri sintetici eventualmente concordati per una prova non diventano regole per uso reale.

## 3. Decisioni di prodotto già acquisite

| Tema | Esito | Riferimento |
| --- | --- | --- |
| Risultato economico minimo | Riepilogo commerciale; costi e marginalità rinviati | D32 |
| Area di preparazione | Facoltativa nel customizing societario | D33 |
| Disponibilità per prenotazione | Prenotare solo quantità coperte nel caso iniziale; nessun blocco automatico della commessa | D34 |
| Carcassa | Tracciabilità minima senza catalogo separato o matricola obbligatoria nel caso iniziale | D35 |
| Controparte | Ragione sociale, identificativo fiscale, sede legale comuni; destinazione aggiuntiva societaria riservata | D36 |
| Chiusure durante indisponibilità esterna | Tecnica consentita con requisiti locali soddisfatti; amministrativa in attesa della conferma di business | D37 |

## 4. Stato dei parametri dimostrativi

| ID | Decisione richiesta / risposta attesa | Referente | Incrementi interessati | Stato |
| --- | --- | --- | --- | --- |
| O01 | Ubicazione dedicata ai particolari sostituiti, separata dal nuovo e non vendibile; nessuna valorizzazione o gestione dello smaltimento introdotta | Proprietario, conferma D38 | B09 | Risolta per il primo scenario |
| O02 | Prestazione e ricambio nella stessa lavorazione; area abilitata; carcassa del ricambio dimostrativo richiesta prima della chiusura tecnica. Valori di esempio, non regole universali | Proprietario, conferma D39 | B04–B09 | Risolta per questi parametri del primo scenario |
| O03 | Acquisizione non conclusiva; conferma di elaborazione con riferimento esterno stabile soddisfa il requisito esterno di chiusura. Rifiuto/esito incerto bloccano e richiedono riconciliazione. Nessun effetto fiscale reale | Proprietario, conferma D40 | B10–B11 | Semantica confermata; dettagli tecnici da progettare e verificare |

I referenti operativi non sono stati identificati come disponibili dalla sola conferma sul referente amministrativo/commercialista. Nessun termine di consegna o assegnazione nominale è inventato.

## 5. Gate di chiusura D01

- [x] Registro delle domande con referente per ruolo, risultato richiesto e incremento interessato.
- [x] Separazione fra decisioni di prodotto e validazioni specialistiche.
- [x] Destinazione dimostrativa O01 concordata e riportata nella slice/backlog (D38).
- [x] Parametri del tipo dimostrativo O02 concordati e riportati nella slice/backlog (D39).
- [x] Semantica di business O03 e riferimento esterno concordati e riportati nella slice/backlog (D40). Schema/protocollo e idempotenza restano progettazione/verifica di B10–B11.
- [ ] Trasmissione delle domande F01–F04 al referente confermata dal proprietario.
- [ ] Risposte necessarie acquisite, oppure rinvii espliciti con gate sugli incrementi interessati.

Il documento non chiude D01, non approva il dossier completo e non autorizza implementazione, contatti esterni o deployment.
