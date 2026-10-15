# Dossier di fondazione — 02. Organizzazione, anagrafiche e accessi

**Stato:** sintesi delle decisioni acquisite, dossier complessivo ancora in bozza. Nessuna autorizzazione a implementare. La [matrice delle capability e della data ownership](03-capabilities-and-data-ownership.md) è proposta per revisione, non ancora approvata.

**Fonti:** chiarimenti del proprietario Luigi Pelosi registrati in [D14–D23](01-glossary-and-domain-boundaries.md); charter §7–8. Le alternative storiche sui tenant societari non sono il modello scelto.

## Modello organizzativo confermato

```text
Tenant = cliente/gruppo contrattuale (es. Beta Group)
└── Società
    └── Sedi       società–sede 1:N
        └── Magazzini  sede–magazzino 1:N
```

- Un tenant può comprendere più società sotto un'amministrazione comune (D22).
- Ogni sede appartiene a una sola società; ogni magazzino a una sola sede (D15).
- Il customizing opera esclusivamente a livello societario, senza ereditarietà dal tenant o override di sede (D14).
- La cardinalità minima per attivare una società/sede non è decisa dalla notazione 1:N. Nessuna scelta di database fisici o provider identity è approvata.

## Contesto organizzativo dei documenti

- Sede unica in testata; i magazzini possono variare tra righe ma appartengono alla sede scelta (D16).
- Raggruppamento nella stessa sede per default; tra sedi della stessa società soltanto se abilitato nel customizing societario (D17).
- Non confondere provenienza storica delle righe e magazzino operativo del documento destinazione. Scelta della sede destinazione e trattamento dei riferimenti sorgente restano da progettare.

## Controparti comuni ed estensioni societarie

- Le società dello stesso tenant condividono l'anagrafica comune delle controparti, con estensioni societarie riservate (D18, D22).
- Una nuova destinazione è societaria per default; diventa comune al gruppo solo tramite scelta esplicita autorizzata (D20).
- La creazione della controparte da parte di A non ne determina una proprietà esclusiva di A.
- La condivisione dell'identità non concede implicitamente accesso a documenti, saldi, condizioni commerciali o customizing delle altre società.
- Non esiste condivisione automatica tra tenant di clienti estranei.

L'elenco preciso dei campi comuni/locali, deduplicazione, revoca della condivisione e conservazione dei dati storici sono da dettagliare. Il mantenimento dei dati storici dei documenti è un vincolo del charter, non un aggiornamento retroattivo implicito.

## Accessi confermati

- Un utente può operare in più società dello stesso tenant solo su autorizzazione esplicita (D23).
- Ruoli e permessi possono essere diversi per società, con scope limitati per sede e magazzino (D23).
- Appartenenza al tenant non equivale ad accesso a tutte le società (D23).
- Modifica dell'anagrafica subordinata a un permesso specifico; consultazione e utilizzo non conferiscono modifica (D21).

Le autorizzazioni devono essere verificate lato server sull'azione e sulla risorsa nel contesto corretto, secondo il charter. Non si decide qui chi possa concedere/revocare ruoli o come combinare scope e permessi; la conferma non autorizza ruoli amministrativi illimitati o accessi tra tenant.

## Prossimo blocco: composizione delle capability

Separare l'abilitazione di una capability per il cliente, il customizing societario e i permessi dell'utente. Il charter richiede almeno tre profili e distingue entitlement, feature flag, configuration ed extension point.

**Profili iniziali proposti per la matrice, ancora da validare:**

1. Officina operativa con anagrafiche/ERP esterni autorevoli.
2. Officina, magazzino e fatturazione Enginia360 con contabilità esterna.
3. Post-vendita con contabilità Enginia360.

**Confermato in D24:** società dello stesso tenant possono adottare composizioni differenti, ad esempio contabilità Enginia360 per A ed esterna per B. L'attivazione in una società non implica attivazione nelle altre. I tre profili sopra restano esempi proposti, non pacchetti commerciali approvati.

**Distinzioni da mantenere:** entitlement del cliente, attivazione societaria, customizing e permessi utente non sono intercambiabili. Modello commerciale, catalogo delle dipendenze e autorità di attivazione restano da definire.

**Confermato in D25:** il gestionale esterno può essere autorevole solo per la contabilità oppure anche per emissione fatture, catalogo e anagrafiche; la selezione dipende dalle capability e dagli insiemi di dati, con una sola autorità per ogni fatto. La conferma non approva specifici profili, connettori o combinazioni tecnicamente non ancora validate.

**Confermato in D26:** il nucleo anagrafico condiviso ha un solo sistema autorevole designato per il tenant, Enginia360 oppure un sistema esterno. I dati societari hanno autorità distinta per società/insieme di dati; gli ERP locali non possono sovrascrivere implicitamente il nucleo comune o i dati di altre società. Copie sincronizzate e mappature preservano l'identità comune. L'esempio concreto è illustrativo, non impone Enginia360 come autorità per tutti i tenant. Matrice dei campi, gestione difformità e protocolli di sincronizzazione restano da progettare.
