# F04 — Scrittura contabile di riferimento del caso 001

**Stato:** documento di riferimento ricevuto dal proprietario; quadratura e coerenza con il caso 001 verificate aritmeticamente. La validazione specialistica specifica di F04 non è ancora esplicitamente attestata: D42 riguarda il caso fiscale e le regole di arrotondamento, non questa nuova scrittura.
**Fonte:** allegato `F04 - scrittura contabile di riferimento.docx`, sezioni 1–3. Nessun dato identificativo reale riprodotto e nessun metadato personale del file pubblicato. SHA-256: `8333a3f49f5e7b2f2921f5069092a43985806ccb68504f96a5880c94a40a8615`.
**Collegamenti:** [caso fiscale 001](10-test-case-001.md); [fixture contabile](test-cases/001-sales-journal-entry.json); [domande e gate](09-stakeholder-validation.md).

## 1. Ipotesi dichiarate dalla fonte

Fattura TD01 di riferimento `FV-001/2026`, commessa 001, cliente nazionale, pagamento differito, operazione completata nello stesso esercizio, regime IVA ordinario. Valuta EUR, coerente con il caso 001.

I riferimenti sono illustrativi: non definiscono formato degli ID, numerazione delle fatture o sequenze di registrazione del prodotto. La presenza di un riferimento fattura e di una commessa non specifica ancora il contratto persistente di tracciabilità fra gli oggetti applicativi.

## 2. Piano dei conti e scrittura forniti

| Conto | Descrizione del piano dimostrativo | Dare EUR | Avere EUR |
| --- | --- | --- | --- |
| 120100 | Crediti verso clienti | 200,69 | — |
| 700100 | Ricavi prestazioni officina | — | 74,25 |
| 700200 | Ricavi vendita ricambi | — | 90,25 |
| 220100 | Erario c/IVA a debito | — | 36,19 |
| **Totale** | | **200,69** | **200,69** |
| **Differenza Dare/Avere** | | **0,00** | |

Classificazioni riportate nella fonte, non scelte dall'agente: 120100 = Stato patrimoniale C.II.1; 700100 e 700200 = Conto economico A.1; 220100 = Stato patrimoniale D.12 nel modello semplificato. La fonte precisa che nel bilancio effettivo occorrono compensazioni e posizione IVA netta: non si trasforma la classificazione dimostrativa in una regola generale di esposizione.

La fonte separa ricavi di prestazioni e ricambi come scelta gestionale, non come obbligo di utilizzare questi sottoconti. Richiama OIC 34 per la valutazione del trattamento unitario quando economicamente inscindibili e art. 2425-bis del Codice civile/OIC 12 per ricavi al netto degli sconti e distinzione dall'IVA. Sono indicazioni attribuite al documento ricevuto, non una verifica normativa indipendente o una regola universale di riconoscimento dei ricavi approvata dall'agente.

## 3. Verifiche aritmetiche e limiti

Verifica con `decimal.Decimal` costruiti da stringhe:

- credito cliente uguale al totale documento del caso 001;
- ricavi di prestazione e ricambio uguali agli imponibili delle rispettive righe, già al netto degli sconti;
- IVA a debito uguale all'imposta aggregata del caso 001;
- totale Dare = totale Avere = 200.69; differenza = 0.00.

Non si aggiungono sconti una seconda volta né si usa l'IVA arrotondata per-riga di 36.20. Il controllo esercita esclusivamente i dati di riferimento, non un modulo contabile Enginia360.

Pagamento differito non significa incasso già avvenuto: nessuna scrittura di banca/cassa è presente nel caso. Nessun costo del venduto, movimento di valorizzazione o margine è introdotto; valgono le esclusioni D32.

## 4. Gate ancora aperti

- Attestare la validazione del referente anche per il piano e la scrittura F04; non estendere automaticamente D42.
- Completare F03: dati della fattura tecnica e riferimenti da preservare verso commessa e registrazione, distinti dalla fatturazione reale.
- Progettare e verificare nei rispettivi incrementi autorizzati autorizzazioni, idempotenza della registrazione, riferimenti immutati e recupero degli errori intermodulo. La sola quadratura non dimostra questi comportamenti.

Nessuna approvazione complessiva del dossier o autorizzazione a implementare è dedotta dall'allegato. B13 resta backlog dipendente da B12; D01 non è chiusa.
