# Caso di test 001 — Vendita nazionale con prestazione e ricambio

**Stato:** specifica funzionale fornita dal proprietario; calcoli verificati indipendentemente con aritmetica decimale. Non è un test eseguito sul motore fiscale Enginia360, che non è stato implementato in questa fase.
**Provenienza:** messaggio di Luigi Pelosi nella discovery D01; il proprietario conferma successivamente che il caso e le regole di arrotondamento sono stati validati dal referente disponibile (D42). Attestazione riferita dal proprietario, non contatto diretto dell’agente; ruolo professionale esatto non specificato.
**Dati strutturati:** [fixture 001](test-cases/001-domestic-service-and-part.json). I valori decimali sono stringhe per evitare conversioni implicite in floating-point durante la lettura.

## 1. Scenario e confini

Officina meccanica italiana in regime IVA ordinario; riparazione di un veicolo per cliente residente in Italia. Documento di riferimento TD01, valuta EUR, prezzi al netto dell'IVA. Caso di vendita nazionale imponibile con aliquota del 22% sia per prestazione sia per ricambio, come specificato dal proprietario.

Esclusi acconti, reverse charge, split payment e regimi speciali. Non si deduce da questo caso che ogni intervento o cliente segua lo stesso trattamento. Il caso fiscale non cambia il componente dimostrativo con carcassa di D35–D39: un filtro olio non viene assunto come articolo soggetto a rientro carcassa per il solo fatto di comparire qui.

## 2. Input ed esiti attesi

| Voce | Quantità | Prezzo unitario netto | Sconto | Imponibile atteso |
| --- | --- | --- | --- | --- |
| Manodopera meccanica | 1,50 ore | 55,00 EUR | 10% | 74,25 EUR |
| Ricambio — filtro olio | 1 pezzo | 95,00 EUR | 5% | 90,25 EUR |

| Risultato | Valore atteso |
| --- | --- |
| Imponibile | 164,50 EUR |
| IVA, raggruppamento al 22% | 36,19 EUR |
| Totale documento | 200,69 EUR |

## 3. Politica di calcolo del caso

1. Prezzi unitari con precisione interna fino a 6 decimali; quantità fino a 3 decimali.
2. Aritmetica decimale, senza floating-point binario per quantità/prezzi/importi.
3. Sconto percentuale applicato prima dell'IVA.
4. Imponibile di riga arrotondato a 2 decimali con ROUND_HALF_UP.
5. Base del raggruppamento ottenuta sommando gli imponibili di riga arrotondati con lo stesso trattamento e aliquota.
6. Imposta calcolata sulla base aggregata e arrotondata a 2 decimali con ROUND_HALF_UP.
7. Totale documento del caso = imponibile più imposta; non si introducono altri componenti.

**Regressione da impedire:** l'IVA arrotondata separatamente sulle righe sarebbe 16,34 + 19,86 = 36,20 EUR. Non usarne la somma come imposta del raggruppamento: il valore atteso è 36,19 EUR. Le regole per eventuali visualizzazioni/ripartizioni dell'IVA sulle righe non sono definite da questa scelta.

## 4. Verifica effettivamente eseguita

Calcolo di riferimento indipendente con Python `decimal.Decimal`, precisione di contesto 28 e `ROUND_HALF_UP`; input costruiti da stringhe. Verificati tramite assertion gli imponibili 74.25/90.25, i totali 164.50/36.19/200.69 e il confronto 36.20 ottenuto dal metodo per-riga. Esito PASS.

È una verifica aritmetica del caso fornito, non una prova del software di produzione, dell'integrazione UI/API o dell'accettazione SdI. Non certifica tutti i valori ammessi dalle precisioni dichiarate: occorreranno limiti di importo/quantità, overflow e ulteriori casi limite.

## 5. Contratti e limiti delle fonti

Dati operativi delle righe e riepiloghi fiscali restano distinti. Il mapping futuro indicato dal proprietario associa le righe a DettaglioLinee e i riepiloghi a DatiRiepilogo. Lo schema ufficiale consultato conferma blocchi distinti e campi ImponibileImporto/Imposta di tipo Amount2DecimalType:

- Pagina ufficiale del formato: `https://www.fatturapa.gov.it/en/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa`
- Schema consultato: `https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.4/Schema_VFPR12_v1.2.3.xsd`

Questo riscontro strutturale non dimostra conformità dell'intero tracciato o correttezza di ogni raggruppamento fiscale. Le chiavi complete per futuri casi con trattamenti/esigibilità diversi restano da specificare.

Il proprietario cita art. 21 DPR 633/1972 per l'arrotondamento al centesimo. Il tentativo di consultazione Normattiva non ha restituito un testo dell'articolo verificabile nella pagina scaricata: non è dichiarata una verifica normativa completa. In particolare precisioni 6/3 e ROUND_HALF_UP restano la politica esplicita del caso fornito, non vengono attribuiti automaticamente alla norma.

Generazione XML, validazione XSD completa, invio SdI, conservazione ed emissione fiscale restano fuori dal primo perimetro. TD01 è il tipo del caso di riferimento, non una funzionalità attiva.

## 6. Risposte acquisite e punti aperti

- F01: esempio funzionale ricevuto; validazione del referente sul caso confermata dal proprietario in D42.
- F02: politica di base e differenza fra IVA aggregata/per-riga validate dal referente secondo attestazione del proprietario (D42); ulteriori casi limite non coperti dal caso 001 da raccogliere.
- F03: indicazione di mapping righe/riepiloghi ricevuta; elenco completo dei dati della fattura tecnica e distinzione dall'emissione reale ancora da completare.
- F04: piano e scrittura ricevuti e verificati aritmeticamente; [riferimento F04](11-f04-reference-journal-entry.md), D43. Validazione specifica del referente ancora da attestare.

D01 e il gate B00 restano aperti. Nessuna autorizzazione implementativa o approvazione complessiva del dossier è dedotta dal caso.
