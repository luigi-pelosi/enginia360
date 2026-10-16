# Sintesi del modello — Documenti commerciali

**Stato:** sintesi per revisione; non approvazione del dossier completo.
**Ambito:** consolidamento delle decisioni concettuali D3–D11, senza codice, schema dati o contratti API.
**Fonti:** [glossario e registro delle decisioni](01-glossary-and-domain-boundaries.md), chiarimenti di Luigi Pelosi (proprietario del prodotto); `PROJECT_CHARTER.md` §7–11. Non sono introdotte nuove evidenze legacy.

## 1. Decisioni acquisite

| Tema | Requisito confermato | Fonte |
| --- | --- | --- |
| Natura della commessa | La commessa officina è un documento commerciale ed è già un ordine cliente effettivo. | D3 |
| Specializzazione | Tipi diversi hanno customizing, personalizzazioni e workflow differenti e possono essere collegati. | D3, D5 |
| Sviluppi | Sono ammessi sviluppi parziali e raggruppamenti di più documenti sorgente in una destinazione. | D4 |
| Creazione diretta | Anche una fattura officina può nascere senza documenti precedenti, se consentito dal customizing. Nessun percorso è universalmente obbligatorio. | D10–D11 |
| Righe e lavorazioni | L'associazione di ricambi/prestazioni alle lavorazioni dipende dal customizing del tipo documento officina. | D8 |
| Rettifiche | Sono ammesse compensazioni con documenti/movimenti di segno opposto, anche dopo sviluppi successivi e su una sola riga. | D5–D6 |
| Guida alle rettifiche | Mostrare documenti ed effetti coinvolti, proporre compensazioni consentite e richiedere conferma; niente cascata indiscriminata. | D7 |
| Decorrenza | Cambiamenti non retroattivi per default, efficaci dalle prossime operazioni. Applicazione retroattiva solo su richiesta esplicita. | D9 |

Gli esempi `Preventivo officina → Commessa officina → Fattura vendita` e `Preventivo ricambi → DDT → eventuale Fattura differita` illustrano configurazioni possibili, non un catalogo chiuso o un obbligo di attraversare ogni passaggio. Non sono una validazione fiscale.

## 2. Vocabolario del modello

Le distinzioni seguenti consolidano il linguaggio; la loro rappresentazione tecnica è ancora proposta.

- **Significato commerciale:** ciò che un documento rappresenta, ad esempio offerta, ordine cliente, trasporto o fattura.
- **Tipo documento configurato:** il profilo operativo concreto, ad esempio Preventivo officina, Preventivo ricambi o Commessa officina.
- **Documento:** una specifica istanza del tipo configurato, con dati e storia propri.
- **Riga:** elemento del documento su cui possono essere riferiti sviluppi e rettifiche; natura e struttura dettagliata ancora da definire.
- **Stato:** fase del ciclo di vita del documento. Non è sinonimo di documento successivo.
- **Regola di sviluppo:** configurazione che disciplina un passaggio ammesso tra tipi, con condizioni e dati da riportare.
- **Collegamento di sviluppo:** relazione effettivamente prodotta tra documenti e, come proposta progettuale, tra righe e quote sviluppate.
- **Rettifica compensativa:** documento/movimento che compensa effetti individuati senza cancellare silenziosamente la storia originaria.

**Non sono sinonimi:** tipo documento e stato; regola di sviluppo e collegamento effettivo; documento commerciale e file/allegato; rettifica economica e reso fisico.

## 3. Ripartizione delle responsabilità proposta

Questa è una proposta di confini logici, non una divisione già approvata in progetti, servizi o database. Un modello concettuale comune non autorizza duplicazioni di ownership o una classe universale con tutte le regole.

| Livello | Responsabilità proposta | Limite |
| --- | --- | --- |
| Concetti commerciali comuni | Identità/riferimenti dei documenti e delle righe, tipo e significato, provenienza e collegamenti, storia degli sviluppi e delle compensazioni. | L'elenco non fissa campi obbligatori uguali per ogni tipo né un unico aggregato tecnico. |
| Customizing del tipo | Regole di struttura e associazione delle righe; workflow ammessi, provenienze/destinazioni, obbligatorietà, condizioni e dati trasferibili. | Nessun fork per cliente o codice specifico per marchio; non aggira permessi, capability abilitate o invarianti. |
| Officina | Lavorazioni, assegnazioni, tempi/consuntivi e chiusura tecnica; specificità della commessa come ordine cliente officina. | Non possiede direttamente le giacenze o le scritture contabili. |
| Magazzino | Disponibilità, prenotazioni, movimenti fisici, consumi e resi. | Non deduce un effetto fisico dal solo nome del documento commerciale. |
| Fatturazione | Regole di emissione e rettifica dei documenti di addebito, riferimenti e valori storici necessari. | Configurazione del flusso non equivale a validità fiscale; verifica specialistica richiesta. |
| Contabilità e tesoreria | Scritture, scadenze e incassi secondo regole validate. | Non modifica retroattivamente i fatti di proprietà di altri domini. |
| Integrazione | Traduzione dei contratti, mappature, invio/esito e riconciliazione quando il sistema autorevole è esterno. | Non diventa una seconda autorità sui dati replicati. |

L'ownership concreta di tipi, regole comuni e istanze è ancora da progettare: non si decide qui un nuovo modulo generico centrale. Il dominio che possiede un fatto ne verifica gli invarianti anche quando l'operazione nasce da uno sviluppo documentale. La configurazione è tipizzata, validata, versionata e sottoposta ad audit secondo il charter.

## 4. Sviluppi parziali e raggruppamenti

**Requisito confermato:** supportare più sviluppi parziali e il raggruppamento di sorgenti, senza imporre relazioni uno-a-uno tra documenti.

**Conseguenze progettuali proposte:**

- Tracciare la provenienza a livello di riga e quantità/importo pertinente, anche se una riga destinazione raccoglie più origini.
- Misurare sviluppato e residuo per specifico passaggio: da consegnare, da fatturare e da rettificare non sono un unico contatore globale.
- Impedire duplicazioni nei retry e sviluppi concorrenti eccedenti quanto consentito.
- Verificare compatibilità delle sorgenti prima di raggrupparle; i criteri non sono ancora decisi.

Unità di misura, arrotondamenti, trasferimento/ricalcolo di prezzi e sconti, nonché riapertura dei residui dopo rettifica, restano aperti.

## 5. Rettifiche e storico

**Requisito confermato:** rettifica anche parziale, riferita alla riga originaria, mediante documenti/movimenti compensativi ammessi; percorso guidato quando esistono sviluppi successivi.

**Comportamento progettuale proposto del percorso:** selezione della quota da rettificare → analisi degli effetti collegati → proposta delle compensazioni ammesse → verifica di permessi e residui → conferma → esecuzione ed esito visibile.

La GUI unitaria non implica una transazione unica tra moduli o sistemi esterni. Audit, idempotenza, blocchi, errori parziali e recupero saranno definiti nella sezione di affidabilità. Le righe non rettificate restano valide salvo regole esplicite; totali e valori dipendenti possono richiedere ricalcolo controllato. Una compensazione commerciale non ripristina automaticamente stock fisico.

## 6. Configurazione nel tempo

Il default acquisito è efficacia dalle prossime operazioni e nessuna riscrittura retroattiva implicita. Non è approvato un congelamento indiscriminato di tutta la configurazione per l'intera vita del documento.

**Proposta:** registrare la versione di configurazione rilevante per ogni operazione; definire la decorrenza per categoria di regola. Una richiesta retroattiva delimita il perimetro, mostra gli impatti e richiede autorizzazione/conferma. Vincoli di dominio e storico confermato restano protetti, con compensazioni dove necessarie. Modalità esecutive ancora da definire.

## 7. Questioni rinviate, senza riaprire le decisioni acquisite

- Catalogo concreto delle regole configurabili. **Scope acquisito in D14: soltanto società**, senza ereditarietà di tenant o override di sede; non confondere customizing con entitlement, feature flag o permessi.
- Ownership applicativa e struttura tecnica, senza anticipare schema o motore universale.
- Dati obbligatori, ruoli dei soggetti, vincoli e autorizzazioni delle operazioni.
- Criteri ulteriori di compatibilità per raggruppare documenti e righe. **D17 acquisita:** stessa sede per default; sedi diverse della stessa società solo con abilitazione nel customizing societario. **D15–D16:** società → sedi 1:N, sede → magazzini 1:N; sede unica in testata e magazzini operativi delle righe appartenenti a quella sede. Scelta della sede destinazione e trattamento dei riferimenti storici restano da progettare.
- Effetti di ogni passaggio e momento della loro esecuzione, evitando duplicazioni tra predecessore e successore.
- Prezzi/sconti, unità di misura, arrotondamenti e gestione dei residui.
- Eventuali automatismi, integrazioni e recupero degli errori.
- Regole fiscali e contabili da validare con lo specialista.

## 8. Soggetti a carico e ripartizione — chiarimenti acquisiti

D12–D13 confermano che una commessa può avere quote a carico di più soggetti: per esempio manodopera al cliente e ricambi coperti dalla garanzia di casa madre.

- **Default:** un soggetto a carico per ciascuna riga; righe differenti possono avere soggetti differenti.
- **Opzione configurabile:** ripartizione parziale della singola riga tra più soggetti, se consentita dal customizing del tipo documento.
- **Principio generale:** le varianti di comportamento sono governate dal customizing pertinente, non da eccezioni hardcoded per officina, garanzia, marchio o cliente. Restano invarianti sicurezza, integrità e vincoli di dominio.

La ripartizione economica non duplica l'intervento o il consumo fisico. Metodi di ripartizione, arrotondamenti, destinatari dei documenti successivi e gestione della copertura rifiutata restano da definire. Soggetto a carico, intestatario del veicolo, richiedente, pagante effettivo e destinatario fattura non sono sinonimi automatici.

**Prossimo ambito da discutere:** modello organizzativo tenant/società/sede/magazzino e livello al quale applicare il customizing. Il dettaglio degli algoritmi di ripartizione è rinviato ai relativi casi d'uso.

La sintesi non approva l'intera fase 1 o il dossier, non modifica il charter e non autorizza codice applicativo o cambiamenti del runtime.
