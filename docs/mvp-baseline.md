# Primo MVP — baseline funzionale consolidata

Stato: requisiti confermati consolidati; sviluppo autonomo autorizzato da D96. Per consegne verificate e punto corrente usare il riepilogo delimitato MVP09 sotto; gli scenari di requisito non sono da soli prove di completamento.
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
- Può delegare anche invito o abilitazione degli utenti, assegnazione e creazione/modifica di ruoli e permessi (D97). Questa facoltà è distinta dalla delega organizzativa.
- L'anagrafazione da sola non concede privilegi. La delega non concede accesso agli altri tenant, ruolo SUPER ADMIN o subdelega implicita.
- Creazione e modifica sono approvate in generale, non soltanto assegnazione di ruoli predefiniti dal proprietario; nessuna nomina amministrativa o promozione globale automatica. Il matching tecnico iniziale è consegnato con MVP03.b.1 per organization-context.read/write; i domini futuri aggiungeranno consumer eseguibili provati senza riaprire la decisione.

<!-- d97-current:start -->
D97: creare e modificare ruoli e permessi con audit immutabile e tracciabile obbligatorio, solo nel proprio tenant; gestione utenti distinta dalla delega organizzativa; nessun SUPER ADMIN, nessun potere cross-tenant o control-plane, nessuna subdelega o nomina implicita; non solo ruoli definiti dal proprietario; nessun runtime consegnato qui. [Decisione e contratto finito MVP03.b](mvp03b-user-administration.md), con interpretazione tecnica minima correggibile sulle azioni/scope eseguibili supportati, non un nuovo tetto ai ruoli.
<!-- d97-current:end -->

<!-- d98-current:start -->
D98: prima associazione binding + membership di un soggetto federato autenticato approvabile dal delegato alla gestione utenti solo nel proprio tenant; autenticazione e audit obbligatori; nessun ruolo o potere amministrativo automatico; nessun tetto owner-only; runtime D98 non consegnato. [Contratto finito MVP03.b.2](mvp03b2-user-onboarding.md).
<!-- d98-current:end -->

<!-- d99-current:start -->
D99: «Configurabile per società, con blocco predefinito». Nel nuovo inventario documentale MVP la società può consentire stock negativo soltanto mediante configurazione esplicita autorizzata, versionata e con audit immutabile; default blocca quantità insufficienti. Nessun grant amministrativo implicito, writer autonomo o switch dei profili ERP storici. La regola vale anche sulla gamba uscente dei trasferimenti (interpretazione tecnica minima correggibile); D34 sulle prenotazioni officina resta storico e non aveva risolto questa domanda.
<!-- d99-current:end -->

<!-- d100-current:start -->
D100: «La quantità viene prenotata alla conferma della bozza». La destinazione Draft salva allocazioni proposte, senza impegnare capacità sorgente né stock. L'impegno della capacità documentale avviene soltanto atomicamente con la conferma della destinazione, rileggendo tutti i residui riga/passaggio. Bozze concorrenti possono contendere: una conferma perdente riceve 409, resta Draft, senza riduzione silenziosa o effetto parziale. Non è una prenotazione fisica. Ogni precedente proposta di prenotazione al salvataggio è SUPERATA/non scelta.
<!-- d100-current:end -->

<!-- d101-current:start -->
D101: «Usare soltanto sorgenti confermate, anche di tipi diversi se tutti abilitati verso la destinazione». Ogni sorgente deve essere Confirmed immutabile e ogni percorso societario sorgente→destinazione deve essere correntemente abilitato. Tipi sorgente differenti sono ammessi, mai tenant/società differenti. D14/D17 restano: customizing solo societario, stessa sede per default, cross-site della stessa società solo esplicitamente abilitato per ciascun percorso coinvolto.
<!-- d101-current:end -->



<!-- mvp09-current:start -->
**Stato corrente: MVP00–08 completati; MVP-09/#148 IN CORSO, SOURCE_COMPLETE_UNVERIFIED; MVP-10/#149 Backlog.** [Contratto finito MVP09](mvp09-integrated-acceptance-contract.md). Implementazione e acceptance preparata non sono runtime verificato. Un solo punto intero; nessuna validazione durante la fase source-only. D96 autorizza ora una sola campagna finale eccezionale `full_architecture=true` dopo completamento funzionale e sorgente, mai CI automatica ordinaria; routine PR-only/dispatch mirato `full_architecture=false`, skip non è pass.

MVP-08/#147 COMPLETATO: PR #172, merge `b00fdbafd3f91f6526caf18e75b79476ab02660f`, candidate `4169bb7ac66a841b69527bf61bd55846c6943fa2`, tree equivalente `487afd38009d71fc51185681a9ae5521a2c86d37`. Readback indipendente del parent: PR CI `42060851414` 5 job/62 step; dispatch `42060851802` 18 job/166 step; 12 ZIP fresh exact-head/SHA256, 32 TRX non vuoti, 420 eseguiti/passati, zero runtime skip. Equivalenza tree, NON nuova CI main. Ledger finale `/root/.hermes/evidence/enginia360-mvp08/final/merge-ready.json`, SHA256 `6b6bce96aa38a315848c1e6e90469503b4f18230f8f1e81656512aaf20a592a8`; readback `/root/.hermes/evidence/enginia360-mvp08-parent/merge-readback.json` e `tracking-readback.json` (#147 chiusa/Completato, #148 aperta/In corso, #149 aperta/Backlog, #37 aperta). Tutte le 46 migrazioni ora pubblicate sono immutabili. SHA256 dei readback esterni: merge `2e85e11ee4e15d9c27ad4b01c09816db0a8571a843a7b70d8ea2aaed0318afa6`, tracking `ba1c09cca4ee595bdd9e3823cb276bb94ccd1ffb0134dfe2ba667ba5190ca63d`.

D97/D98 runtimefalse nei blocchi decisionali indica soltanto i gate documentali storici, non la consegna funzionale successiva. Nessun deployment/readiness operativo; provider reale, target/accesso, recupero/RPO/RTO, privacy e manutenzione restano gate di MVP10. Cronologia e incidenti NONPASS conservati in [archivio dei checkpoint](archive/mvp08-checkpoints.md).
<!-- mvp09-current:end -->

<details><summary>Prove storiche dei predecessori (non stato corrente)</summary>

MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 COMPLETATO: PR #170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidate `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`. Il coordinatore ha riletto PR CI `41881635998` (5 job/60 step), dispatch `41881398306` (16 job/148 step), 10 ZIP exact-head/SHA256 e 24 TRX con328 test eseguiti/passati, zero skip/fail. Issue #145 chiusa e Project Completato; equivalenza tree, non nuova CI main. MVP-07/#146 COMPLETATO: PR #171, main `7d505db049880ef6fc4a2307dcd4575165c08923`, candidate `09cc3b1acddfab31879b940339fcb5af31053991`, tree equivalente `5a58e881d71e5d4b12fdb42ea1829d49790b7e0e`. Il coordinatore ha riletto PR CI `41945630168` (5 job/61 step), dispatch `41945650853` (17 job/157 step), 11 ZIP exact-head/SHA256 e 28 TRX, 380 eseguiti/passati, zero skip; issue #146 chiusa, Project Completato. Equivalenza tree, non nuova CI main. Evidenze `/root/.hermes/evidence/enginia360-mvp07-parent/merge-readback.json`.

</details>


MVP03.b.2a/#164 (PR #165) precede il primo ingresso federato #166, consegnato separatamente con PR #167: [contratto e prove storiche](mvp03b2b-federated-onboarding.md).

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
- Documenti: MVP07 fissa testata/righe e Draft → Confirmed quantitativo non fiscale nel proprio contratto; numerazione commerciale/fiscale, economia e correzioni non sono inventate né prerequisiti impliciti di questo punto.
- Inventari: quantità insufficienti risolte da D99; quantità iniziali documentate, magazzini ammessi e servizi fissati nel contratto MVP07, senza reset dei dati legacy.
- Sviluppo/raggruppamento: D100/D101 risolvono impegno alla conferma e sole sorgenti confermate anche di tipi diversi. Il [contratto MVP08](mvp08-document-development-contract.md) fissa percorsi societari stabili, compatibilità canonica/snapshot/contesto, capacità per stadio, concorrenza e correzioni del piano Draft. Nessun reset/compensazione automatica dei Confirmed o riapertura dei residui inventata.

Conteggi fisici periodici, valorizzazione del magazzino, workflow officina e adempimenti fiscali non diventano requisiti dell'MVP per implicazione.

## 7. Valutazione dell'esistente e passaggio successivo

La [valutazione dell'esistente](mvp-existing-code-assessment.md) e' stata completata sui sette domini: evidenze di codice, gap, raccomandazioni di riuso o ricostruzione e verifiche effettivamente eseguite sono separate dalle prove mancanti. D96 autorizza la prosecuzione autonoma con ricostruzione funzionale mirata e riuso selettivo, non una cancellazione totale ne' un semplice cambio grafico. Le prove storiche non dimostrano automaticamente il nuovo modello; non ripetere indiscriminatamente tutte le vecchie suite.

L'ordine di lavoro proposto è: accesso e amministrazione organizzativa end-to-end; controparti/cataloghi; tipologie e documenti con effetti inventariali; sviluppo e raggruppamento. Ogni punto segue la cadenza corrente: intera implementazione prima della validazione finale per impatto; RED → GREEN precedente resta storico ove incompatibile.

Il [piano di consegna MVP](mvp-delivery-plan.md), [backlog corrente](mvp-backlog.json) e il blocco D96 in AGENTS.md guidano ora il lavoro; il piano precedente e' archivio storico. Ogni scelta concreta di riuso o rimozione deve essere motivata da utilizzi e verifiche. Baseline, storia Git e ambienti protetti vanno preservati.
