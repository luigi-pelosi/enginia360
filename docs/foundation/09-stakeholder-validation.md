# Dossier di fondazione — 09. Validazioni dei referenti (D01)

## Stato corrente consolidato — D70/D71

B01–B06 consegnati; B06 main `d03b661624b67a9bb41c8ee2d48fde17019246e1` (PR #27). B07–B14 autorizzati in sequenza autonoma, un solo WIP. B07 In corso: prelievo parziale esplicito q6 sul residuo della prenotazione, senza consumo, fisico/impegno invariati; area interna facoltativa societaria, picking list distinta. B08–B14 restano Backlog per dipendenze, non per mancata autorizzazione. G02/G03 e vincoli specialistici ancora pertinenti restano obbligatori al rispettivo incremento, non già soddisfatti. La parzialità del consumo non è decisa da D71.

Accettazione automatica isolata effimera, nessun nuovo ambiente manuale persistente, nessuna review LLM o approvazione manuale di routine. Bootstrap 443, segreti, volumi e backup conservati invariati. Le descrizioni successive di stato/autorizzazione precedente sono **storiche e superate da questo riepilogo e D70/D71**; i requisiti di dominio restano validi. Prove/CI/completamento non sono dedotti dall'autorizzazione.


**Aggiornamento consegna B06:** accettazione privata positiva del proprietario «Funziona. Procediamo» e autorizzazione alla consegna Git/PR/CI/merge della sola B06. Review indipendenti core/lifecycle e artefatti manuali PASS sul candidato esatto; prove finali rieseguite nel [report B06](../b06-verification.md). G02/B06 soddisfatto per prenotazioni parziali esplicite q6 D69, insufficienza senza autotrim, concorrenza/retry e fisico invariato. G02/B07–B09 resta aperto; B07–B14 non autorizzati/blocked/Backlog. I paragrafi precedenti alla consegna restano storici; CI remota e chiusura sono da verificare sui riferimenti effettivi della PR/issue #12, non assunte dalla prova locale.

**Stato corrente D69 — 19 ottobre 2026:** il proprietario approva esplicitamente l’opzione A: prenotazioni parziali richieste dall’operatore, mai troncamento automatico. B06 privata/sintetica è implementata e verificata localmente; candidata alla review indipendente, non Completata. G02/B06 dispone delle prove tecniche nel [report B06](../b06-verification.md); G02/B07–B09 resta aperto. B07–B14 restano blocked/Backlog e non autorizzati. Nessun commit/push/merge o deployment persistente prima della parent review.

**Stato:** caso 001 e relativa politica di arrotondamento validati dal referente secondo attestazione del proprietario (D42); ulteriori risposte ancora da acquisire. D01 è pronta per la revisione finale, con dettagli residui assegnati agli incrementi in D46.
**Fonti:** `PROJECT_CHARTER.md` §11–12 e §15; [slice](04-first-vertical-slice.md); [decisioni D32–D37](01-glossary-and-domain-boundaries.md); issue GitHub #3.

## 1. Disponibilità e responsabilità

Luigi Pelosi, proprietario del prodotto, conferma che il commercialista o referente amministrativo è disponibile. Non è stato specificato quale dei due ruoli ricopra il referente; non sono richiesti nominativi o dati di contatto nel repository.

La disponibilità non costituisce risposta, presa in carico del referente o validazione fiscale/contabile. Il proprietario coordina la raccolta delle risposte; gli aspetti che richiedono competenza fiscale devono essere validati dal commercialista, eventualmente tramite il referente amministrativo. Nessun contatto esterno è stato effettuato dall'agente.

## 2. Domande da sottoporre al referente disponibile

Per ogni risposta registrare ruolo del validatore, versione del caso, risultato atteso ed eventuali limiti. Utilizzare esclusivamente esempi sintetici o anonimizzati.

| ID | Domanda / risultato richiesto | Validatore richiesto | Prima di | Stato |
| --- | --- | --- | --- | --- |
| F01 | Quale caso di vendita domestica usare come riferimento per una prestazione e un ricambio? Fornire trattamento IVA atteso, imponibile, imposte e totale di un esempio sintetico, distinguendo regola validata e parametro tecnico di prova. | Commercialista, tramite referente disponibile se necessario | Validazione dei parametri B05; uso reale | Caso 001 ricevuto; validazione del referente confermata dal proprietario (D42) |
| F02 | Quali precisioni e arrotondamenti adottare per quantità, prezzi, sconti, righe, imponibile e imposte? Fornire casi limite con esiti attesi e criterio di gestione degli scarti. | Referente amministrativo con validazione del commercialista per gli aspetti fiscali | B05 e B12 | Politica del caso 001 e confronto per-riga validati secondo il proprietario (D42); ulteriori casi limite assegnati a G01/B05 con gate D46 |
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
- [x] Ulteriori casi limite F02 assegnati al gate G01/B05, confermato dal proprietario in D46; non sono dichiarati già verificati.
- [x] Risposte del caso minimo acquisite e dettagli residui delimitati con gate approvati D46.
- [ ] Revisione finale della documentazione e verifiche della PR concluse; nessun completamento automatico di D01.

Il documento non chiude D01, non approva il dossier completo e non autorizza implementazione, contatti esterni o deployment.

## 6. Dettagli residui assegnati agli incrementi — D46

**D46 — Delimitazione dei dettagli residui confermata:** gli ulteriori casi limite di precisione/arrotondamento devono essere definiti e validati prima di completare B05; dettagli esecutivi dei movimenti e della concorrenza di magazzino devono essere definiti e verificati nei rispettivi incrementi B06–B09; contratti tecnici, idempotenza e recupero degli errori restano progettazione e test degli incrementi pertinenti. Sono gate obbligatori, non requisiti eliminati o già soddisfatti. La conferma permette la revisione finale di D01, non chiude automaticamente D01/B00 e non autorizza implementazione o approvazione complessiva del dossier.

| Gate | Incremento | Evidenza necessaria prima del completamento | Referente |
| --- | --- | --- | --- |
| G01 | B05 | Casi limite con esiti attesi, precisioni e limiti applicativi espliciti, validazione pertinente e test decimali; nessuna generalizzazione dal solo caso 001 | Proprietario/referente amministrativo; commercialista per gli aspetti fiscali |
| G02 | B06–B09, per i rispettivi effetti | Effetti di prenotazione/prelievo/consumo/rientro e concorrenza definiti; test su retry, quantità e assenza di doppi effetti; area facoltativa e nuovo/carcassa distinti | Proprietario con referenti officina/magazzino e prove tecniche |
| G03 | Incrementi pertinenti, in particolare B10–B13 | Contratti versionati, correlazione/idempotenza, esiti incerti ed errori recuperabili progettati e testati; nessuna transazione globale implicita | Responsabile tecnico con review del proprietario |

## G02/B06 — parzialità risolta D69; prove tecniche locali disponibili

**D69 — Prenotazione parziale esplicita:** su riga di 3 filtri con 2 disponibili, l’operatore richiede esplicitamente 2: vengono prenotati 2 e resta 1 da prenotare successivamente quando disponibile. Ogni quantità richiesta deve essere positiva, non superiore al residuo non prenotato della riga né alla disponibilità del magazzino autorizzato della sede di testata. Una richiesta di 3 con disponibilità 2 è rifiutata integralmente, senza effetti e senza bloccare la commessa; non viene ridotta a 2. I successivi comandi, anche su magazzini diversi validi, non possono superare cumulativamente la quantità della riga. La giacenza fisica non cambia; disponibilità = fisico − impegni attivi. D69 risolve soltanto la parzialità della prenotazione, non prelievo, consumo, annullamento o rilascio. La quota G02/B06 è esercitata dal runner isolato: quantità/residuo, stock condiviso con barriera SQL, retry, insufficienza/replenishment tecnico, autorizzazione e storico. Report B06 con log/comandi ed esiti. Review indipendente e accettazione manuale restano necessarie; G02/B07–B09 non è chiuso. Non occorre nuova approvazione della parzialità.

## 7. G01/B05 — politiche numeriche risolte da D67

**Stato corrente:** conferme ripetute del proprietario acquisite senza nuova domanda. Netto di ogni riga HALF_UP a 6 → somma delle righe arrotondate per raggruppamento fiscale → imposta del gruppo HALF_UP a 6 → totale somma basi+imposte, senza riduzione a 2 nel trasporto/display. Quantità/prezzo 6 decimali, sconto 2 e 0–100 inclusi. G01/D46 chiuso per queste scelte numeriche finite; test eseguibili e limiti tecnici nel [report B05](../b05-verification.md). Non è certificazione fiscale/legale generale né completamento B05: review indipendente e accettazione manuale pendenti, B06–B14 bloccati. D42 resta circoscritta al caso storico.

D66 conserva verbatim le precisioni e il confronto tra le alternative; D67 registra la scelta confermata. Il runtime ora accetta valori variabili e le rappresentazioni invarianti equivalenti, senza uguaglianza con fixture. Il test HTTP delle due righe half-micro verifica base `0.000002`; il caso 001 completo resta regressione separata. Nessuna richiesta di ulteriore conferma è necessaria per queste politiche.

**Stato D01:** materiale consolidato per revisione finale; non Completato. Le risposte e le conferme del caso sono acquisite o delimitate con gate approvati. Restano review della documentazione e verifiche della PR; B00 e D02 non sono chiusi da D46.
