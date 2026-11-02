# Primo MVP — baseline funzionale consolidata

Stato: requisiti confermati consolidati; sviluppo autonomo autorizzato da D96; scenari di accettazione da eseguire, non prove di completamento.
Data: 2 novembre 2026.
Fonte: revisione della [carta di progetto](../PROJECT_CHARTER.md), paragrafi 4.1, 6 e 8.1, con Luigi Pelosi.

## 1. Obiettivo e confine

Il primo MVP comprende sette domini necessari al completamento. Non coincide con il precedente pilota officina/Giobby né con l'intero ciclo post-vendita della baseline originaria. Le integrazioni esterne non sono un criterio di completamento. D96 autorizza sviluppo autonomo, riallineamento GitHub/istruzioni e pulizia motivata; non autorizza riscrittura indiscriminata, deployment, dati reali, acquisti o nuovi ambienti persistenti. La pubblicazione del software deve distinguere release verificata e readiness operativa effettiva.

| Dominio | Requisito confermato |
| --- | --- |
| Identità e accessi | Identity federation, RBAC e autorizzazioni. |
| Organizzazione | Gestione tenant, società, sedi e magazzini. |
| Controparti | Anagrafiche e relativi ruoli. |
| Cataloghi | Articoli e servizi. |
| Inventari | Gestione continuativa delle quantità nei magazzini. |
| Tipologie di documento | Configurabili separatamente per ogni società. |
| Documenti | Testate e righe; sviluppo parziale e raggruppamento con provenienza e residui. |

Restano i confini già confermati delle identità anagrafiche condivise nel tenant e dei dati societari separati. Visibilità condivisa non equivale a permesso di modifica.

## 2. Amministrazione confermata

- Luigi Pelosi è SUPER ADMIN: crea e amministra tutti i tenant e le loro strutture organizzative.
- Può delegare la gestione organizzativa di un singolo tenant a un soggetto già anagrafato in quel tenant.
- Può delegare anche invito o abilitazione degli utenti e assegnazione di ruoli e permessi. Questa facoltà è distinta dalla delega organizzativa.
- L'anagrafazione da sola non concede privilegi. La delega non concede accesso agli altri tenant, ruolo SUPER ADMIN o subdelega implicita.
- Il perimetro dei ruoli assegnabili e l'eventuale abilitazione di ulteriori amministratori restano da precisare prima dell'implementazione interessata.

## 3. Documenti e quantità: modello confermato

Ogni variazione di quantità è tracciata e deriva dalla conferma di un documento. Non sono previste movimentazioni autonome senza documento. Un documento non confermato non produce tali variazioni.

La tipologia seleziona un comportamento supportato: carico, scarico, trasferimento tra magazzini oppure nessun effetto sulle quantità. La configurazione è societaria, senza codice o formule personalizzate. I nomi e i codici delle tipologie non sono fissati da questi esempi.

Lo sviluppo documentale permette di selezionare righe o quantità di una sorgente e creare documenti successivi, mantenendo origine e residuo. Il raggruppamento permette di selezionare da più sorgenti per una sola destinazione, conservando tutte le provenienze. Non è una copia senza collegamento.

I residui si riferiscono al passaggio documentale interessato, non a un unico contatore consumato per tutta la catena. I criteri di compatibilità del raggruppamento vanno esplicitati prima di implementarlo; non sono ammesse combinazioni arbitrarie per il solo fatto che le sorgenti condividono una destinazione.

## 4. Scelte tecniche confermate

- Frontend Next.js con SSR, React, TypeScript e shadcn/ui.
- Backend ASP.NET Core su .NET 10; persistenza PostgreSQL.
- Regole di dominio e autorizzazioni rimangono nel backend; il rendering server non implica accesso diretto del frontend al database.
- Vite/Ant Design non sono la destinazione del nuovo frontend; non si dichiara una migrazione già eseguita.
- Sessioni, rendering e cache devono preservare isolamento e autorizzazioni. Versioni e dipendenze saranno selezionate e verificate nel relativo incremento tecnico.

## 5. Scenari di accettazione proposti

Questi scenari rendono verificabili i requisiti; non sono prove già eseguite o approvazioni di nuove regole di dominio. Usare soltanto dati sintetici in ambienti isolati. Per ogni percorso servono interfaccia, API e persistenza effettive, oltre ai rifiuti di sicurezza pertinenti.

| ID | Percorso da dimostrare | Risultato osservabile |
| --- | --- | --- |
| MVP-A01 | Accesso federato e amministrazione globale | Il SUPER ADMIN crea un tenant e ne gestisce società, sedi e magazzini. Un utente senza tali poteri non può farlo. |
| MVP-A02 | Delega nel tenant | Un soggetto già anagrafato riceve la delega organizzativa e gestisce quel tenant, non un altro. La gestione utenti richiede la distinta facoltà prevista. |
| MVP-A03 | Controparti e cataloghi | Gestione autorizzata e rilettura persistita di una controparte con ruolo, di un articolo e di un servizio; campi e operazioni esatte da fissare nel contratto dell'incremento. |
| MVP-A04 | Configurazione societaria | Due società configurano le rispettive tipologie senza modificarsi reciprocamente. |
| MVP-A05 | Documento e inventario | Compilazione senza variazione stock; conferma con l'effetto configurato; collegamento consultabile tra documento, righe e movimenti. Verificare carico, scarico, trasferimento e nessun effetto. |
| MVP-A06 | Sviluppo parziale | Selezione di righe o quantità, creazione della destinazione e rilettura di provenienza e residuo del passaggio. |
| MVP-A07 | Raggruppamento | Una destinazione riceve quantità da più sorgenti compatibili, mantenendo provenienza e residuo per ciascuna sorgente. |

Verifiche trasversali: isolamento tenant/società, azione e scope lato server, audit minimizzato, retry senza effetti duplicati e concorrenza. La completezza tecnica non equivale a validazione fiscale o readiness operativa.

## 6. Dettagli da chiudere nei contratti degli incrementi

Non estendere la discovery a tutti i casi futuri. Prima dell'incremento interessato fissare il comportamento minimo e le prove necessarie:

- Identità: provider e percorso federato concreto, binding iniziale, limiti delle deleghe, revoca e gestione utenti.
- Anagrafiche/cataloghi: dati minimi, ruoli supportati, operazioni e autorizzazioni, disattivazione e duplicati.
- Documenti: dati minimi di testata/riga, numerazione, stati e correzioni, dati economici eventualmente necessari; nessun effetto fiscale o contabile presunto.
- Inventari: quantità iniziali documentate, regole sulle quantità insufficienti, magazzini ammessi e comportamento dei servizi.
- Sviluppo/raggruppamento: percorsi ammessi, compatibilità, momento di impegno del residuo, concorrenza e correzioni. Non riaprire il principio già approvato della configurazione societaria.

Conteggi fisici periodici, valorizzazione del magazzino, workflow officina e adempimenti fiscali non diventano requisiti dell'MVP per implicazione.

## 7. Valutazione dell'esistente e passaggio successivo

La [valutazione dell'esistente](mvp-existing-code-assessment.md) e' stata completata sui sette domini: evidenze di codice, gap, raccomandazioni di riuso o ricostruzione e verifiche effettivamente eseguite sono separate dalle prove mancanti. D96 autorizza la prosecuzione autonoma con ricostruzione funzionale mirata e riuso selettivo, non una cancellazione totale ne' un semplice cambio grafico. Le prove storiche non dimostrano automaticamente il nuovo modello; non ripetere indiscriminatamente tutte le vecchie suite.

L'ordine di lavoro proposto è: accesso e amministrazione organizzativa end-to-end; controparti/cataloghi; tipologie e documenti con effetti inventariali; sviluppo e raggruppamento. Ogni incremento mantiene RED → GREEN e verifiche per impatto.

Il [piano di consegna MVP](mvp-delivery-plan.md), [backlog corrente](mvp-backlog.json) e il blocco D96 in AGENTS.md guidano ora il lavoro; il piano precedente e' archivio storico. Ogni scelta concreta di riuso o rimozione deve essere motivata da utilizzi e verifiche. Baseline, storia Git e ambienti protetti vanno preservati.
