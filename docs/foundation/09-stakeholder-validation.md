# Dossier di fondazione — 09. Validazioni dei referenti (D01)

**Stato:** caso 001 e relativa politica di arrotondamento validati dal referente secondo attestazione del proprietario (D42); ulteriori risposte ancora da acquisire. D01 resta in corso.
**Fonti:** `PROJECT_CHARTER.md` §11–12 e §15; [slice](04-first-vertical-slice.md); [decisioni D32–D37](01-glossary-and-domain-boundaries.md); issue GitHub #3.

## 1. Disponibilità e responsabilità

Luigi Pelosi, proprietario del prodotto, conferma che il commercialista o referente amministrativo è disponibile. Non è stato specificato quale dei due ruoli ricopra il referente; non sono richiesti nominativi o dati di contatto nel repository.

La disponibilità non costituisce risposta, presa in carico del referente o validazione fiscale/contabile. Il proprietario coordina la raccolta delle risposte; gli aspetti che richiedono competenza fiscale devono essere validati dal commercialista, eventualmente tramite il referente amministrativo. Nessun contatto esterno è stato effettuato dall'agente.

## 2. Domande da sottoporre al referente disponibile

Per ogni risposta registrare ruolo del validatore, versione del caso, risultato atteso ed eventuali limiti. Utilizzare esclusivamente esempi sintetici o anonimizzati.

| ID | Domanda / risultato richiesto | Validatore richiesto | Prima di | Stato |
| --- | --- | --- | --- | --- |
| F01 | Quale caso di vendita domestica usare come riferimento per una prestazione e un ricambio? Fornire trattamento IVA atteso, imponibile, imposte e totale di un esempio sintetico, distinguendo regola validata e parametro tecnico di prova. | Commercialista, tramite referente disponibile se necessario | Validazione dei parametri B05; uso reale | Caso 001 ricevuto; validazione del referente confermata dal proprietario (D42) |
| F02 | Quali precisioni e arrotondamenti adottare per quantità, prezzi, sconti, righe, imponibile e imposte? Fornire casi limite con esiti attesi e criterio di gestione degli scarti. | Referente amministrativo con validazione del commercialista per gli aspetti fiscali | B05 e B12 | Politica del caso 001 e confronto per-riga validati secondo il proprietario (D42); ulteriori casi limite da completare |
| F03 | Quali dati e riferimenti conservare nella fattura tecnica collegata alla commessa? Quali differenze devono restare esplicite rispetto a una fattura realmente emessa? | Referente amministrativo/commercialista secondo competenza | B12; prima di uso fiscale reale | Perimetro della fattura tecnica e storico confermati dal proprietario (D45); non validazione dei requisiti completi di emissione reale |
| F04 | Quale piano dei conti dimostrativo e quale scrittura attesa usare per il caso F01, con riferimenti fattura/commessa? Specificare conti, importi attesi e quadratura; l'agente non sceglie il piano. | Commercialista | B13 | Piano e scrittura ricevuti (D43), quadratura verificata; validazione del referente attestata dal proprietario (D44) |

Costi del venduto, criteri di valorizzazione per marginalità, ciclo passivo completo e margine sono rinviati da D32. Queste domande non riaprono tale perimetro. Nessuna aliquota, conto, scrittura o conformità è approvata dal presente documento.

La prova tecnica e la validazione specialistica sono esiti distinti. Parametri sintetici eventualmente concordati per una prova non diventano regole per uso reale.

**D41 — Caso funzionale 001 fornito dal proprietario:** riepilogo commerciale atteso 164.50 EUR di imponibile, 36.19 EUR di IVA e 200.69 EUR di totale. Prezzi netti fino a 6 decimali, quantità fino a 3, sconti prima dell'IVA, imponibili di riga a 2 decimali; imposta sul raggruppamento di righe con stesso trattamento/aliquota, a 2 decimali con ROUND_HALF_UP. La verifica decimale indipendente è passata; non è un test del motore applicativo o di SdI. Specifica e fixture nel [caso 001](10-test-case-001.md); validazione del referente sul caso e sulle regole di arrotondamento successivamente confermata dal proprietario in D42.

F01–F02 sono risposte funzionali trasmesse dal proprietario; D42 attesta, tramite il proprietario, la validazione del referente per il caso 001 e le relative regole di arrotondamento. F03 ha mapping righe/riepiloghi e perimetro tecnico confermati dal proprietario in D45; F04 è stata fornita nell’allegato e verificata aritmeticamente (D43); la validazione del referente specifica di F04 è attestata dal proprietario in D44. La conferma non si estende a F03 o a casi ulteriori.

**D42 — Validazione del caso 001 riferita dal proprietario:** Luigi Pelosi conferma che il caso e le regole di arrotondamento sono già stati validati dal referente disponibile. L'attestazione riguarda il caso 001 e la sua politica di calcolo; non è una validazione generale del motore fiscale, di altri trattamenti IVA, della fatturazione elettronica o delle scritture contabili. Il ruolo professionale esatto del referente e un verbale separato non sono stati comunicati; nessun contatto diretto dell'agente è dichiarato.

**D43 — F04 ricevuta:** allegato del proprietario con piano dimostrativo e scrittura della fattura `FV-001/2026`, commessa 001, pagamento differito. Dare 120100 = 200.69 EUR; Avere 700100 = 74.25, 700200 = 90.25, 220100 = 36.19 EUR. Quadratura e coerenza con il caso fiscale 001 verificate con Decimal; validazione del referente specifica di F04 successivamente attestata dal proprietario in D44. Nessun incasso, costo del venduto, valorizzazione o margine introdotto. Dettagli e cautele nel [riferimento F04](11-f04-reference-journal-entry.md).

**D44 — Validazione F04 riferita dal proprietario:** Luigi Pelosi conferma che anche il piano dei conti dimostrativo e la scrittura F04 del caso 001 sono stati validati dal referente disponibile. L'attestazione è circoscritta a questo riferimento, con le ipotesi e le cautele dell'allegato. Non approva un piano universale, ulteriori scritture, conformità generale o un modulo contabile già implementato. Nessun contatto diretto dell'agente è dichiarato.

**D45 — Perimetro F03 confermato dal proprietario:** la fattura tecnica del primo scenario conserva società emittente e destinatario con i dati anagrafici utilizzati alla conferma; data, valuta, tipo e riferimento del documento; righe, sconti e riepiloghi fiscali; collegamenti alla commessa, alle righe di provenienza e alla registrazione contabile. Modifiche anagrafiche successive non riscrivono i dati storici della fattura confermata. È un documento tecnico di prova, non una fattura fiscalmente emessa o l'elenco completo dei requisiti della fatturazione reale.

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
- [x] Validazione del referente sul caso 001 e sulle regole F01/F02 attestata dal proprietario (D42).
- [x] Piano e scrittura F04 ricevuti e validazione del referente attestata dal proprietario (D44).
- [x] Perimetro tecnico F03 e conservazione dei dati storici confermati dal proprietario (D45).
- [ ] Ulteriori casi limite F02 completati, oppure rinvio esplicito con gate confermato dal proprietario.
- [ ] Risposte necessarie acquisite, oppure rinvii espliciti con gate sugli incrementi interessati.

Il documento non chiude D01, non approva il dossier completo e non autorizza implementazione, contatti esterni o deployment.
