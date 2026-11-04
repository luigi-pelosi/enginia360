# Enginia360 - Carta di progetto per agenti di sviluppo

Stato: revisione MVP attiva; baseline originaria conservata dove esplicitamente storica
Data: 14 ottobre 2026; revisione MVP 2 novembre 2026 (D96)
Proprietario del prodotto: Luigi Pelosi

## 1. Scopo del documento

Questo documento e' il punto di ingresso per qualunque agente che lavori a Enginia360.

L'agente deve usarlo per comprendere:

- quale prodotto stiamo costruendo;
- quali decisioni sono gia' state prese;
- come consultare SmartData come sistema legacy di riferimento;
- quali principi architetturali sono vincolanti;
- quale risultato produrre per primo;
- quali aspetti richiedono ancora validazione umana.

Questo documento non autorizza a implementare indiscriminatamente l'intero DMS. Ogni intervento deve avere un obiettivo circoscritto, criteri di accettazione verificabili e un confine di dominio esplicito.

## 2. Visione del prodotto

Enginia360 deve diventare un Dealer Management System autorevole per aziende che svolgono attivita' di prevendita e post-vendita su veicoli di qualsiasi tipo: auto, van, truck e categorie future.

Il prodotto deve essere:

- modulare e costruito attorno a business capability esplicite;
- API-first e predisposto all'interoperabilita' tra domini;
- multi-tenant, sicuro e configurabile per cliente;
- adatto a piu' societa', sedi e magazzini dello stesso cliente;
- dotato di identity federation, RBAC e autorizzazioni contestuali;
- osservabile, mantenibile e aggiornabile nel tempo;
- semplice da usare per operatori con ruoli e competenze differenti.

Il primo mercato e' italiano. I primi utilizzatori saranno clienti gia' conosciuti, coinvolti come piloti.

## 3. Strategia greenfield e ruolo del sistema esistente

Enginia360 e' un progetto greenfield. Non deve essere realizzato modernizzando gradualmente il codice PHP esistente e non deve ereditarne automaticamente struttura, database o convenzioni tecniche.

Il repository esistente e' una fonte di conoscenza sui processi. Deve essere consultato per:

- individuare domini e terminologia utilizzati realmente;
- ricostruire regole e casi limite consolidati;
- comprendere integrazioni, documenti e flussi operativi;
- preparare domande concrete per operatori e commercialista;
- progettare migrazione e riconciliazione dei dati.

Il comportamento trovato nel codice legacy non costituisce automaticamente un requisito corretto. Ogni regola importante deve essere classificata come:

1. confermata da un referente di dominio;
2. osservata nel legacy ma ancora da validare;
3. nuova decisione di prodotto;
4. comportamento da eliminare.

Riferimenti iniziali nel repository legacy:

- agenda officina: `docs/manuale_agenda_appuntamenti_officina.md`;
- officina: `system/model/workshop/`;
- magazzino: `system/model/warehouse/`;
- clienti e veicoli: `system/model/customer/` e `system/model/catalog/vehicle*.php`;
- utenti e autorizzazioni: `system/model/user/` e `system/library/cart/user.php`;
- conti e scadenze: `system/model/account/`;
- integrazioni: controller e librerie SAP HANA, Giobby, DAF e fornitori.

### 3.1 Repository e relazione tra i progetti

I due prodotti hanno identita' e repository distinti:

- prodotto nuovo: `Enginia360`;
- repository di sviluppo: `https://github.com/luigi-pelosi/enginia360.git`;
- prodotto legacy di riferimento: `SmartData`;
- repository legacy: `https://github.com/luigi-pelosi/smartdata.git`;
- checkout locale di riferimento, quando disponibile: `C:\Users\pelos\Desktop\smartdata`.

SmartData non e' un modulo, una dipendenza runtime, un package o una precedente versione di Enginia360 da aggiornare. E' una reference esterna per la conoscenza di dominio e per la futura migrazione dei dati.

Un agente che lavora nel repository Enginia360 puo' leggere SmartData per raccogliere evidenze, ma non deve:

- aggiungere riferimenti di build o dipendenze dal codice legacy;
- copiare classi, query, schema o convenzioni senza una nuova progettazione;
- modificare il repository SmartData salvo incarico esplicito e separato;
- descrivere Enginia360 come nuova versione tecnica di SmartData;
- usare il nome SmartData per namespace, assembly, API, database, eventi o interfaccia del nuovo prodotto.

Quando cita una regola osservata nel legacy, l'agente deve indicare repository e percorso di origine e marcarla come non confermata finche' non viene validata da un referente.

## 4. Perimetro del primo prodotto

### 4.1 Perimetro corrente del primo MVP — revisione del 2 novembre 2026

Sintesi dei requisiti confermati, scenari di accettazione proposti e dettagli rinviati ai singoli incrementi: [baseline funzionale MVP](docs/mvp-baseline.md). Non costituisce un'autorizzazione all'implementazione.

Il proprietario ha ridefinito il primo MVP nei seguenti sette domini, tutti necessari al suo completamento:

1. Identity federation, RBAC e autorizzazioni.
2. Gestione dei tenant, organizzazioni e unita' aziendali (societa', sedi e magazzini).
3. Anagrafiche controparti e relativi ruoli.
4. Cataloghi articoli e servizi.
5. Inventari: gestione continuativa delle quantita' nei magazzini, non il solo conteggio fisico periodico.
6. Tipologie di documento.
7. Documenti (testate e righe).

Le integrazioni verso sistemi esterni non sono una priorita' o un criterio di completamento di questo MVP. I primi quattro domini da soli non costituiscono l'MVP completo. Per Inventari il proprietario ha confermato la gestione continuativa delle quantita' nei magazzini, secondo il modello documentale seguente:

- Ogni variazione di quantita' e' tracciata e deriva dalla conferma di un documento; non sono previste movimentazioni autonome prive di documento nell'MVP.
- La tipologia del documento stabilisce l'effetto di magazzino: carico (aumento della giacenza), scarico (diminuzione), trasferimento (scarico del magazzino di origine e carico di quello di destinazione) oppure nessun effetto sulle quantita'. Questi sono comportamenti confermati, non nomi o codici definitivi delle tipologie.
- La sola compilazione o il salvataggio di un documento non confermato non produce tali variazioni.
- Ogni societa' ha le proprie tipologie di documento configurabili, nel contesto del tenant autorizzato. Non si tratta di un insieme fisso imposto a tutte le societa' ne' di una configurazione unica tenant-wide. La configurazione seleziona comportamenti supportati dall'applicazione, senza introdurre codice o formule personalizzate.
- Nell'MVP e' incluso lo sviluppo di un documento a partire da un altro, riportando righe o quantita' selezionate e mantenendo origine e residuo. Non e' una semplice copia priva di collegamento: la provenienza deve identificare le righe e le quantita' sorgenti utilizzate.
- Nell'MVP e' incluso anche il raggruppamento di righe o quantita' selezionate da piu' documenti sorgenti in un unico documento di destinazione, mantenendo tutte le provenienze e il residuo di ciascuna riga sorgente per il passaggio documentale interessato. L'inclusione del raggruppamento non autorizza combinazioni arbitrarie di documenti: restano da delimitare i criteri di compatibilita' applicabili, nel rispetto dei confini organizzativi e delle autorizzazioni.

Le tipologie concrete, le regole ulteriori del ciclo di vita e le specifiche causali richiedono ancora delimitazione. Il modello confermato non approva implicitamente effetti fiscali o contabili, workflow specifici o un motore documentale generico. Conteggio fisico periodico e relative rettifiche non sono requisiti confermati da questa precisazione.

Il modello amministrativo confermato e' descritto al paragrafo 8.1. L'autorizzazione autonoma corrente e' D96 al paragrafo 4.2; il [piano di consegna MVP](docs/mvp-delivery-plan.md) e il [backlog MVP](docs/mvp-backlog.json) sostituiscono la sequenza operativa precedente. Nessuna vecchia dipendenza ERP costituisce un criterio aggiuntivo di completamento del nuovo MVP.

### 4.2 D96 — Autorizzazione autonoma e riallineamento al nuovo MVP

Il 2 novembre 2026 il proprietario conferma: «Procedi in totale autonomia; rimodula il progetto github secondo l'MVP, fai pulizia di tutto il non necessario, procedi con il riallineamento delle istruzioni degli agenti e pubblica l'MVP quando pronto per l'utilizzo.»

L'autorizzazione riguarda la sequenza dei sette domini del paragrafo 4.1: gestione del progetto GitHub, sviluppo, pulizia motivata delle parti non necessarie, test, commit convenzionali, PR, CI exact-head per impatto, merge verificati e pubblicazione del software quando realmente pronto. Non occorrono riconferme ordinarie a ogni incremento. Le decisioni di dominio veramente mancanti restano da risolvere prima del comportamento dipendente, senza bloccare il lavoro indipendente.

La gestione autonoma dei tenant e le deleghe del paragrafo 8.1 sostituiscono i limiti precedenti di D77 soltanto per il nuovo MVP. Il nuovo inventario documentale opera senza dipendere da Giobby: D82 e i vincoli ERP restano riferiti ai profili storici e non vietano il nuovo percorso locale, senza cambio automatico dell'autorita' degli ambienti o dei dati esistenti.

Pulizia non significa cancellazione indiscriminata: preservare storia Git, evidenze, migrazioni pubblicate, segreti, volumi, backup, configurazioni e servizi protetti. Rimuovere codice obsoleto soltanto con analisi degli utilizzi, sostituzione ove necessaria e verifiche dei consumer interessati. Il piano officina/ERP viene conservato come archivio storico, non come roadmap corrente.

«Pubblica ... quando pronto per l'utilizzo» autorizza la consegna verificata del software, non una dichiarazione anticipata di readiness. Lettura conservativa dell'agente: non implica acquisti, accesso pubblico, dati reali, nuovo ambiente persistente o sostituzione di servizi protetti. Restano invariati Tailscale 443 → localhost:9119, gli ambienti conservati e i gate operativi non provati; destinazione e accesso di un futuro rilascio operativo richiedono un contratto esplicito prima dell'azione dipendente. Sviluppo e acceptance isolati proseguono autonomamente.

### 4.3 Baseline originaria del primo rilascio — riferimento storico, non perimetro corrente dell'MVP

Il testo seguente conserva l'obiettivo originario del 14 ottobre 2026; non impone il completamento del ciclo post-vendita o della contabilita' per il primo MVP ridefinito al paragrafo 4.1.

Il primo rilascio deve coprire un ciclo post-vendita completo:

1. pianificazione dell'appuntamento;
2. accettazione del veicolo;
3. preventivo e autorizzazione del cliente;
4. apertura e gestione della commessa o ordine di lavoro;
5. pianificazione e consuntivazione delle lavorazioni;
6. richiesta, prenotazione, prelievo e reso dei ricambi;
7. acquisti e ricevimento merce necessari alla commessa;
8. chiusura tecnica della lavorazione;
9. fatturazione e incasso;
10. registrazione contabile e riconsegna del veicolo.

Il primo rilascio rende disponibile anche la contabilità ordinaria italiana: ciclo attivo e passivo, partita doppia, IVA, clienti e fornitori, banche, cespiti, assestamenti e chiusure. Il modulo contabile non e' obbligatorio per ogni tenant: un cliente puo' mantenere il proprio gestionale come sistema autorevole e usare Enginia360 soltanto per le capability operative concordate.

Sono esclusi dal primo rilascio:

- paghe;
- dichiarativi fiscali;
- consolidamento di gruppo;
- vendita veicoli nuovi e usati;
- applicazioni native mobili;
- funzionamento offline completo.

Queste esclusioni non devono impedire future estensioni, ma non devono generare codice prematuro.

## 5. Scala e vincoli organizzativi

La prima scala operativa di riferimento e':

- fino a 10 aziende clienti;
- circa 100 utenti contemporanei complessivi;
- clienti con una o piu' societa', sedi e magazzini;
- hosting SaaS nell'Unione europea.

Il progetto e' finanziato e guidato personalmente dal proprietario, che e' attualmente l'unico sviluppatore umano e conosce soprattutto PHP. La disponibilita' settimanale puo' variare. Non devono essere promesse date basate soltanto su stime teoriche.

Gli agenti devono privilegiare:

- incrementi verticali piccoli e dimostrabili;
- costi iniziali contenuti;
- dipendenze open source solide e mantenute;
- automazione ripetibile;
- semplicità operativa;
- documentazione sufficiente per permettere al proprietario di comprendere e mantenere il sistema.

L'agente non deve introdurre un servizio gestito a pagamento senza presentare costo, alternativa self-hosted, responsabilita' operative trasferite e motivazione concreta.

## 6. Direzione tecnologica

La baseline proposta per il nuovo prodotto e':

- C# e .NET 10 LTS;
- ASP.NET Core per API e processi applicativi;
- PostgreSQL per la persistenza relazionale;
- Next.js con React e TypeScript per la GUI web, con rendering lato server (SSR);
- shadcn/ui come base dei componenti dell'interfaccia;
- REST con OpenAPI per le API sincrone;
- eventi asincroni solo quando esiste un caso d'uso reale;
- OpenTelemetry per log, metriche e tracce;
- container Linux per ambienti locali e distribuzione.

.NET, ASP.NET Core e il compilatore C# non richiedono royalty per l'uso commerciale. Il prodotto non deve dipendere da Windows Server, SQL Server, Visual Studio a pagamento o Azure.

Questa baseline puo' essere contestata soltanto con una decisione architetturale documentata che mostri un impedimento reale o un'alternativa nettamente migliore rispetto ai vincoli del progetto.

**Scelta frontend del proprietario — 2 novembre 2026:** il nuovo MVP adotta Next.js con SSR e shadcn/ui. Questa scelta sostituisce Vite/Ant Design come destinazione frontend del nuovo MVP, senza dichiarare gia' migrato il codice esistente. ASP.NET Core rimane il backend applicativo: il rendering server del frontend non trasferisce implicitamente a Next.js le regole di dominio o l'accesso diretto ai dati. L'interattivita' lato client resta ammessa dove necessaria. Rendering e cache devono preservare sessione, autorizzazioni e isolamento tenant/societa', senza condividere contenuti riservati fra utenti o contesti. Versioni, dipendenze e modalita' di esecuzione saranno fissate e verificate nell'incremento tecnico dedicato; questa registrazione non installa pacchetti e non autorizza deployment o riscrittura indiscriminata.

### 6.1 Regole C# iniziali

- Abilitare nullable reference types.
- Trattare i warning del codice applicativo come errori nella pipeline.
- Usare `decimal` o value object dedicati per valori monetari; non usare `float` o `double`.
- Non rappresentare identificativi, denaro, quantita' e stati con stringhe o numeri generici quando un tipo dedicato elimina ambiguita'.
- Preferire oggetti immutabili per valori e contratti.
- Separare modello di dominio, casi d'uso e infrastruttura.
- Non introdurre un'interfaccia per ogni classe: usarla quando esiste una sostituibilita' o un confine effettivo.
- Non adottare librerie esterne se il framework o una piccola implementazione chiara coprono il requisito.

## 7. Strategia architetturale

La destinazione e' un sistema composto da capability indipendenti. Il primo passo e' un monolite modulare predisposto all'estrazione, non una flotta immediata di microservizi.

Motivazione: con un solo sviluppatore, distribuire fin dall'inizio ogni dominio separatamente introdurrebbe costi di rete, compatibilita', sicurezza, diagnostica, code e deployment prima di aver validato le regole aziendali.

Ogni modulo deve comunque avere:

- responsabilita' di dominio esplicita;
- namespace e progetto dedicati;
- modello interno non accessibile direttamente dagli altri moduli;
- API applicative o contratti pubblici definiti;
- ownership dei propri dati;
- test delle regole critiche;
- dipendenze direzionate e verificabili.

Un modulo potra' diventare un microservizio quando almeno una delle seguenti condizioni sara' dimostrata:

- necessita di scalare indipendentemente;
- ciclo di rilascio realmente indipendente;
- confine di sicurezza o isolamento specifico;
- integrazione esterna con disponibilita' diversa;
- ownership stabile dei dati e dei contratti;
- beneficio operativo superiore al costo della distribuzione.

### 7.1 Domini candidati

- organizzazioni, tenant e accessi;
- clienti, fornitori e contatti;
- veicoli;
- pianificazione;
- officina;
- catalogo, prezzi e condizioni;
- magazzino;
- acquisti;
- fatturazione;
- contabilita' e tesoreria;
- documenti;
- reportistica;
- connettori esterni.

Questa lista e' una mappa iniziale, non autorizza a creare subito tredici applicazioni o tredici database.

### 7.2 Composizione delle capability per tenant

Enginia360 deve essere un prodotto componibile. Ogni tenant deve poter acquistare, abilitare e configurare soltanto le capability necessarie senza creare una variante del codice.

Profili esemplificativi, non esaustivi:

- solo operativita' officina e commesse, con anagrafiche e contabilita' mantenute nel gestionale del cliente;
- officina, magazzino e fatturazione, con contabilita' esterna;
- post-vendita e contabilita' Enginia360, senza controllo di gestione;
- piattaforma completa, comprendente reporting e controllo di gestione;
- singole capability esposte in modalita' headless tramite API.

La composizione deve avvenire attraverso quattro meccanismi distinti:

1. `entitlement`: stabilisce quali moduli o capability sono concessi al tenant;
2. `feature flag`: governa il rilascio tecnico controllato di una funzione;
3. `configuration`: definisce il comportamento ammesso per quel tenant, societa' o sede;
4. `extension point`: integra sistemi esterni attraverso contratti supportati.

Questi meccanismi non sono intercambiabili. Una feature flag non deve diventare il listino commerciale, una configurazione non deve aggirare un'autorizzazione e un'integrazione non deve richiedere modifiche al core per ogni cliente.

Requisiti obbligatori:

- nessun fork o branch permanente per cliente;
- nessuna condizione applicativa basata sul nome o sull'identificativo di uno specifico cliente;
- dipendenze tra moduli esplicite e acicliche;
- interfaccia utente, menu, permessi, job ed endpoint coerenti con le capability abilitate;
- disabilitare un modulo impedisce nuovi utilizzi senza cancellare o rendere illeggibile lo storico autorizzato;
- le configurazioni sono tipizzate, validate, versionate e sottoposte ad audit;
- i valori di default sono sicuri e documentati;
- l'attivazione di una capability verifica prerequisiti, migrazioni e permessi;
- ogni modulo dichiara capability fornite, dipendenze richieste, eventi pubblicati e dati posseduti.

Il codice condiviso deve contenere soltanto primitive tecniche o concetti realmente comuni. Le regole di officina, magazzino, fatturazione, contabilita' e controllo di gestione restano nei rispettivi domini.

### 7.3 Integrazione con gestionali esterni

Per ogni insieme di dati e processo deve esistere un solo sistema autorevole dichiarato. L'ownership puo' variare per tenant e per capability, ma non puo' essere ambigua durante l'esecuzione.

Esempio per un tenant che usa Enginia360 soltanto come interfaccia operativa:

- il gestionale esterno possiede anagrafiche, articoli, condizioni commerciali, documenti fiscali e contabilita';
- Enginia360 possiede appuntamenti, commesse operative, assegnazioni, avanzamenti, tempi e raccolta delle informazioni di lavorazione;
- dati necessari all'operativita' vengono replicati in viste locali controllate;
- gli esiti della commessa vengono consegnati al gestionale tramite un connettore;
- errori, conflitti e ritardi di sincronizzazione sono visibili agli operatori e riconciliabili.

Ogni connettore deve usare un anti-corruption layer che traduca il contratto esterno nel linguaggio del dominio Enginia360. Il dominio non deve contenere campi, stati o regole specifiche di SAP, Giobby o di un altro gestionale.

Per ciascuna integrazione devono essere definiti:

- sistema autorevole per ogni entita' e transizione;
- direzione e frequenza della sincronizzazione;
- identificativi interni ed esterni e relativa mappatura;
- idempotenza, retry, ordinamento e gestione dei duplicati;
- comportamento durante l'indisponibilita' del sistema esterno;
- politica per conflitti, cancellazioni e dati non piu' disponibili;
- stato di sincronizzazione visibile e strumenti di riconciliazione;
- versione del contratto, compatibilita' e deprecazione;
- proprieta' e minimizzazione dei dati scambiati.

Il core applicativo non deve chiamare direttamente SDK o API proprietarie. Deve dipendere da porte di dominio implementate dai connettori.

## 8. Multi-tenancy e autorizzazione

Il modello organizzativo minimo deve distinguere:

- tenant: cliente contrattuale della piattaforma;
- legal entity: societa' o soggetto contabile;
- site: sede operativa;
- warehouse: magazzino;
- user: identita' della persona;
- membership: appartenenza dell'utente al tenant;
- role e permission: cosa puo' fare l'utente;
- scope: su quali societa', sedi, magazzini e risorse puo' agire.

Requisiti obbligatori:

- il tenant context non deve essere accettato ciecamente dal payload del client;
- ogni comando e query deve operare in un tenant context verificato;
- cache, file, job, eventi, log ed esportazioni devono preservare l'isolamento;
- le query applicative devono essere protette anche da Row-Level Security PostgreSQL dove appropriato;
- connessioni riutilizzate e job in background devono impostare e cancellare correttamente il contesto;
- l'autorizzazione deve essere verificata lato server sulla specifica azione e risorsa;
- le operazioni amministrative e di assistenza devono essere temporanee e sottoposte ad audit.

La federazione OIDC/SAML e l'MFA sono requisiti del prodotto. La scelta tra Keycloak self-hosted, servizio gestito o altro provider va presa dopo una prova tecnica e un confronto dei costi.

### 8.1 Amministrazione della piattaforma e deleghe nel tenant — revisione MVP

Decisione confermata dal proprietario il 2 novembre 2026 durante la revisione della carta.

- Il proprietario del software, Luigi Pelosi, opera come SUPER ADMIN: puo' creare e amministrare i tenant di tutti i clienti e gestire le rispettive strutture organizzative (societa', sedi e magazzini).
- Il SUPER ADMIN puo' delegare la gestione della struttura organizzativa di uno specifico tenant a un soggetto gia' anagrafato in quel tenant.
- Il SUPER ADMIN puo' delegare anche l'invito o l'abilitazione degli utenti nel tenant, l'assegnazione e, con D97, la creazione e modifica dei relativi ruoli e permessi. Questa facolta' e' distinta dalla gestione della struttura organizzativa e non deriva automaticamente da essa.
- La delega vale soltanto per il tenant indicato, non per gli altri clienti. L'anagrafazione e' un prerequisito e non attribuisce da sola poteri amministrativi.
- L'autorita' globale del SUPER ADMIN e la delega organizzativa tenant-scoped sono distinte. Anche le operazioni globali devono individuare e verificare il tenant destinatario e restare sottoposte ad autorizzazione e audit; non implicano un bypass dell'isolamento.
- Queste decisioni superano i precedenti limiti di D77 dove impedivano le deleghe confermate per struttura organizzativa, invito o abilitazione degli utenti, assegnazione e creazione/modifica di ruoli e permessi nel tenant. Non approvano implicitamente subdelega, nomina di amministratori, attribuzione del ruolo SUPER ADMIN o accesso ad altri tenant. La creazione/modifica e' approvata in generale da D97, non limitata ai ruoli predefiniti dal proprietario; il matching tecnico azione/scope e' lavoro dell'incremento dipendente.

<!-- d97-current:start -->
D97: creare e modificare ruoli e permessi con audit immutabile e tracciabile obbligatorio, solo nel proprio tenant; gestione utenti distinta dalla delega organizzativa; nessun SUPER ADMIN, nessun potere cross-tenant o control-plane, nessuna subdelega o nomina implicita; non solo ruoli definiti dal proprietario; nessun runtime consegnato qui. [Decisione e contratto finito MVP03.b](docs/mvp03b-user-administration.md), inclusa l'interpretazione tecnica minima correggibile sulle azioni/scope eseguibili supportati, non un nuovo tetto ai ruoli.
<!-- d97-current:end -->

<!-- d98-current:start -->
D98: prima associazione binding + membership di un soggetto federato autenticato approvabile dal delegato alla gestione utenti solo nel proprio tenant; autenticazione e audit obbligatori; nessun ruolo o potere amministrativo automatico; nessun tetto owner-only; runtime D98 non consegnato. [Contratto finito MVP03.b.2](docs/mvp03b2-user-onboarding.md).
<!-- d98-current:end -->

MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 IN VALIDAZIONE FINALE, CONSEGNA NON VERIFICATA; contratto `docs/mvp05-catalog-contract.md`. Nessun deployment/readiness operativo. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva.


Stato corrente: MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 IN VALIDAZIONE FINALE, CONSEGNA NON VERIFICATA; contratto `docs/mvp05-catalog-contract.md`. Nessun deployment/readiness operativo. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva.

MVP03.b.2a/#164 (PR #165) precede il primo ingresso federato #166, consegnato separatamente con PR #167: [contratto e prove storiche](docs/mvp03b2b-federated-onboarding.md).

## 9. Regole di affidabilita' e sicurezza

- Ogni operazione critica deve essere idempotente dove puo' essere ripetuta.
- Le transazioni restano locali al modulo che possiede i dati.
- La pubblicazione affidabile di eventi deve usare un outbox quando attraversa un confine distribuito.
- I consumer devono gestire duplicati e retry senza produrre doppi effetti economici o di magazzino.
- Gli stati intermedi e gli errori devono essere visibili e recuperabili.
- Correzioni fiscali e contabili devono generare operazioni tracciate; non si riscrive silenziosamente lo storico confermato.
- Allegati e documenti definitivi richiedono controllo accessi, integrita', versionamento e retention.
- Segreti e credenziali non devono essere salvati nel repository o nei log.
- Log e audit non devono contenere dati personali non necessari.
- Dipendenze e immagini devono essere mantenute, scansionate e aggiornate regolarmente.

## 10. Conoscenza di dominio gia' emersa

I seguenti comportamenti sono rilevanti, ma devono essere confermati dai referenti:

### 10.1 Cliente pagante e intestatario del veicolo

Il cliente che paga una lavorazione puo' essere diverso dall'intestatario del veicolo. Il sistema non deve sovrascrivere automaticamente il pagante quando viene selezionato un veicolo intestato a un altro soggetto.

Il modello futuro deve poter rappresentare almeno:

- proprietario o intestatario del veicolo;
- utilizzatore o conducente;
- richiedente della lavorazione;
- soggetto pagante;
- destinatario della fattura.

I ruoli effettivamente necessari e la loro validita' temporale devono essere validati.

### 10.2 Movimenti provvisori e definitivi

Una prenotazione o un movimento operativo non ancora confermato puo' essere utile alla pianificazione senza modificare la giacenza ufficiale o i totali economici definitivi.

Il nuovo modello deve distinguere almeno:

- disponibilita' fisica;
- quantita' prenotata o impegnata;
- movimento previsto;
- movimento confermato;
- rettifica e annullamento.

Non copiare i flag del database legacy. Ricostruire il significato aziendale e validarlo con officina, magazzino e amministrazione.

### 10.3 Stato e audit

Appuntamenti, commesse, documenti, movimentazioni e registrazioni devono avere transizioni esplicite. Per i processi confermati o collegati ad altri documenti, preferire annullamenti e rettifiche tracciate alla cancellazione fisica.

## 11. Prima vertical slice

**Baseline storica:** il percorso sotto descrive la prima slice originaria, non l'accettazione del nuovo MVP. Per il perimetro corrente e gli scenari proposti fare riferimento al paragrafo 4.1 e alla [baseline MVP](docs/mvp-baseline.md).

Il primo risultato implementativo deve dimostrare un percorso minimo dal post-vendita alla destinazione amministrativa configurata:

1. creare o selezionare tenant, societa' e sede;
2. creare cliente e veicolo mantenendo distinti intestatario e pagante;
3. aprire una commessa;
4. aggiungere una prestazione e un ricambio;
5. calcolare imponibile, IVA e totale con regole esplicite;
6. prenotare il ricambio senza alterare la giacenza fisica;
7. confermare il consumo e produrre il movimento definitivo;
8. produrre il risultato economico della commessa;
9. nel profilo con contabilita' Enginia360, creare e confermare una fattura bozza e produrre una registrazione contabile quadrata;
10. nel profilo con gestionale esterno, pubblicare una richiesta idempotente verso un connettore simulato e registrare esito, errore e riconciliazione.

Questa slice non comprende ancora trasmissione SdI, conservazione fiscale, calendario completo, acquisti completi o GUI definitiva.

### 11.1 Criteri di accettazione

- Due tenant non possono leggere o modificare reciprocamente dati, documenti o risultati di ricerca.
- L'intestatario del veicolo puo' differire dal pagante senza perdere nessuna delle due informazioni.
- Una prenotazione ricambio incide sulla disponibilita' ma non sulla giacenza fisica.
- La conferma del consumo genera una sola movimentazione anche se la richiesta viene ripetuta.
- Tutti gli importi usano regole di arrotondamento esplicite e riproducibili.
- Lo stesso modulo officina funziona sia con contabilita' Enginia360 sia con il connettore esterno, senza condizioni riferite a uno specifico cliente.
- Nel profilo interno, la registrazione contabile e' quadrata e mantiene il riferimento alla fattura e alla commessa.
- Nel profilo esterno, un'indisponibilita' del gestionale non perde la richiesta e rende visibile lo stato da recuperare.
- Un tenant privo del controllo di gestione non vede menu, endpoint o job relativi, ma conserva gli eventi necessari a una futura attivazione secondo la retention prevista.
- Un'operazione non autorizzata viene rifiutata dal backend e registrata in modo appropriato.
- Gli errori applicativi sono diagnosticabili tramite correlation ID senza esporre informazioni sensibili.
- L'intero scenario e' eseguibile localmente con istruzioni ripetibili.

I risultati fiscali e contabili devono essere considerati tecnicamente implementati ma non validati finche' non sono approvati dal commercialista.

## 12. Primo incarico consigliato per l'agente

**Incarico iniziale storico:** la revisione MVP non richiede di ripetere integralmente il dossier di fondazione descritto sotto. Il prossimo passo proposto e' la valutazione mirata dell'esistente rispetto ai sette domini, come descritto nella [baseline MVP](docs/mvp-baseline.md).

Prima di scrivere l'intero prodotto, l'agente deve produrre un dossier di fondazione contenente:

1. glossario iniziale dei termini del post-vendita;
2. mappa dei bounded context e delle loro responsabilita';
3. modello organizzativo tenant/societa'/sede/magazzino;
4. flusso della prima vertical slice con comandi, eventi e proprietario dei dati;
5. matrice delle capability, dipendenze, entitlement e configurazioni per almeno tre profili cliente;
6. matrice di data ownership per profilo interno ed ERP esterno;
7. proposta di struttura della solution .NET e delle dipendenze consentite;
8. modello iniziale delle minacce per tenant isolation, documenti, connettori e contabilita';
9. backlog ordinato della vertical slice;
10. elenco delle domande da sottoporre a operatori e commercialista;
11. preventivo dei costi ricorrenti per ambiente locale, demo e pilota, separando obbligatori e opzionali.

Il dossier deve citare il codice legacy soltanto come evidenza del comportamento osservato. Non deve presentare come confermate regole ricavate esclusivamente dal repository.

Dopo l'approvazione del dossier, il primo incremento di codice deve essere uno skeleton eseguibile con un solo percorso completo, non una raccolta di CRUD indipendenti.

## 13. Metodo di lavoro richiesto agli agenti

### Cadenza di validazione — disposizione corrente del proprietario

Il proprietario dispone: «Unit Test, Test di CI, CI pipelines e tutto ciò che concerne la validazione, il testing del codice e la sua distribuzione deve perentoriamente avvenire a fine implementazione dei punti di sviluppo».

Completare l'implementazione del punto di sviluppo concordato prima di eseguire unit test, test di integrazione/sicurezza/runtime, build e audit di validazione, pipeline CI o distribuzione. Non suddividere artificiosamente il punto in micro-passaggi per mantenere verifiche intermedie. Questa disposizione sostituisce la precedente sequenza test-first/RED → GREEN ove incompatibile, senza cancellare prove e decisioni storiche.

La validazione finale resta obbligatoria prima di dichiarare il punto verificato, effettuare il merge o distribuire il software. Eventuali esiti negativi aprono una fase correttiva seguita dalle verifiche finali interessate. Nessuna rinuncia a sicurezza, isolamento o criteri di accettazione; nessuna autorizzazione aggiuntiva al deployment. Lettura del codice, progettazione e raccolta del contesto restano attività di implementazione; non sono campagne di test. I controlli automatici esistenti non vengono disabilitati: la PR di consegna viene aperta nella fase finale, non durante l'implementazione.

Prima di proporre o implementare una modifica, l'agente deve:

1. leggere questo documento;
2. esplorare i riferimenti legacy pertinenti;
3. descrivere il comportamento osservato e il livello di certezza;
4. cercare componenti o decisioni gia' esistenti nel nuovo progetto;
5. definire risultato, confini e criteri di accettazione;
6. scegliere la soluzione minima coerente con l'architettura;
7. implementare e verificare il percorso completo;
8. documentare decisioni, rischi e verifiche mancanti.

L'agente deve evitare:

- duplicazioni tra moduli;
- librerie condivise contenenti logica di dominio di piu' contesti;
- generic repository privi di un'esigenza concreta;
- CRUD come sostituto del modello di dominio;
- eventi usati per nascondere dipendenze sincrone;
- microservizi creati soltanto per uniformita' diagrammatica;
- configurazioni per cliente implementate con fork del codice;
- conclusioni fiscali o legali non validate da uno specialista;
- affermazioni di funzionamento basate soltanto su compilazione o test statici.

## 14. Definition of Done iniziale

Una funzionalita' e' completata quando:

- il comportamento e i casi limite sono documentati;
- ownership e confini dei dati sono rispettati;
- autorizzazione e tenant isolation sono verificate;
- regole critiche e casi di errore hanno test significativi;
- migrazioni e rollback operativo sono definiti;
- log, metriche e audit permettono la diagnosi;
- la GUI espone stato, errori e azione successiva in modo chiaro;
- le dipendenze introdotte sono motivate e con licenza compatibile;
- la documentazione operativa e' aggiornata;
- e' dichiarato cio' che non e' stato verificato in ambiente reale;
- operatori o commercialista hanno validato gli aspetti che richiedono competenza di dominio.

## 15. Decisioni aperte

Le seguenti decisioni non devono essere inventate dall'agente:

- identita' dei clienti pilota e referenti di processo;
- provider definitivo per identity federation;
- provider SdI e conservazione;
- piano dei conti e regole contabili di riferimento;
- regole fiscali e casi IVA supportati al primo rilascio;
- catalogo commerciale iniziale delle capability e relative dipendenze;
- granularita' delle configurazioni tra tenant, societa' e sede;
- sistemi autorevoli e contratti dei gestionali dei clienti pilota;
- strategia dettagliata di migrazione dello storico;
- budget mensile massimo per demo e produzione;
- obiettivi contrattuali di disponibilita', RPO e RTO;
- momento e criteri con cui estrarre ciascun microservizio.

Per queste decisioni l'agente deve preparare alternative comparabili, implicazioni e una raccomandazione, lasciando la decisione al proprietario e agli specialisti competenti.

