export const domains = [
    {
        id: "identity",
        label: "Identità e accessi",
        description: "Federazione, ruoli e autorizzazioni.",
        milestone: "MVP-02 / MVP-03",
    },
    {
        id: "organization",
        label: "Organizzazione",
        description: "Tenant, società, sedi e magazzini.",
        milestone: "MVP-02 / MVP-03",
    },
    {
        id: "counterparties",
        label: "Controparti",
        description: "Anagrafiche condivise e relativi ruoli.",
        milestone: "MVP-04",
    },
    {
        id: "catalog",
        label: "Cataloghi",
        description: "Articoli e servizi indipendenti dall’officina.",
        milestone: "MVP-05",
    },
    {
        id: "inventory",
        label: "Inventari",
        description: "Quantità tracciate tramite documenti confermati.",
        milestone: "MVP-07",
    },
    {
        id: "document-types",
        label: "Tipologie documentali",
        description: "Configurazione separata per società.",
        milestone: "MVP-06",
    },
    {
        id: "documents",
        label: "Documenti",
        description: "Testate, righe, sviluppo e provenienza quantitativa.",
        milestone: "MVP-07 / MVP-08",
    },
] as const;
