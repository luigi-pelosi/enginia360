# Dossier di fondazione — 12. Costi e responsabilità operative (D02)

**Stato:** analisi avviata; scenari e voci da quantificare, non preventivo approvato. Nessun acquisto, servizio o deployment autorizzato da questo documento.
**Fonti:** `PROJECT_CHARTER.md` §5, §8, §12 e §15; [bootstrap](../bootstrap.md); [minacce](06-initial-threat-model.md); issue D02 #4.
**Rilevazione iniziale:** 16 ottobre 2026. Prezzi, IVA, localizzazione del fornitore e costo effettivo del VPS non ancora verificati.

## Vincolo economico e di hosting confermato

**D47 — Unica VPS esistente per demo e pilota:** il proprietario conferma che il budget comprende già il VPS attuale, che non sono previsti acquisti di altre macchine e che i carichi della demo e del pilota saranno eseguiti su questa VPS. Nessun preventivo di un secondo host o di alta disponibilità multi-host entra nella baseline. Il costo esistente non è un nuovo acquisto né viene dichiarato nullo. Nessun importo mensile numerico è stato comunicato.

Il vincolo non approva provider identity, nuovi servizi a pagamento, una policy di backup, RPO/RTO o disponibilità contrattuale. La disponibilità di una destinazione di backup fuori dal nodo resta da chiarire: non si presume un acquisto né che una copia sul disco applicativo protegga dalla perdita del nodo. Giurisdizione e idoneità del VPS per il pilota UE restano da verificare rispetto al charter, senza dedurre una deroga.

## 1. Baseline verificata e limiti

Il Compose Enginia360 esistente ha servizi API e web in esecuzione e healthy al controllo iniziale. L'API non pubblica una porta host; il web pubblica HTTP sulla porta 80. Il bootstrap è una superficie tecnica senza dati di dominio, identità o database, come delimitato dall'ADR.

La risorsa VPS esistente va indicata come costo già sostenuto: non è un nuovo acquisto e non è gratuita perché già disponibile. Non sono noti prezzo fatturato, contratto, IVA, disponibilità esclusiva delle risorse o giurisdizione del servizio. Non dedurre tali dati dall'IP. Le risorse osservate non sono un benchmark o prova di capacità per 100 utenti.

La CI della PR #2 sul precedente incremento documentale D46 risulta passata al controllo iniziale. Ciò non verifica infrastruttura del pilota, ripristino o prima slice di dominio.

## 2. Tre scenari distinti

| Scenario | Scopo e dati | Base da confrontare | Limiti |
| --- | --- | --- | --- |
| Locale/sviluppo | Build e test con dati sintetici, ambienti ripetibili | Risorse già disponibili e relativi consumi; servizi di sviluppo necessari | Non è un servizio pilota; nessuna promessa di continuità |
| Demo | Dimostrazione della slice con dati sintetici, accesso protetto quando sono attive identità e funzioni di dominio | Stessa VPS esistente; separazione logica da progettare e capacità da misurare, senza nuove macchine | Non estendere implicitamente il bootstrap HTTP anonimo a credenziali o dominio |
| Pilota | Uso da parte di clienti concordati con dati reali solo dopo gate separati | Stessa VPS esistente; giurisdizione UE/idoneità da verificare, persistenza, identità, canale protetto, backup e monitoraggio da predisporre negli scope approvati | Non produzione approvata dal solo nome; capacità e recupero da provare, nessuno SLA dedotto da un host |

## 3. Voci obbligatorie e opzionali da quotare

Obbligatorio indica una capacità necessaria nello scenario, non un abbonamento da acquistare automaticamente. Una soluzione self-hosted consuma comunque risorse e lavoro operativo.

| Voce | Locale | Demo di dominio | Pilota con dati reali | Come stimare |
| --- | --- | --- | --- | --- |
| Compute e storage applicativo/database | Risorse di sviluppo | Necessari | Necessari | VPS già compreso nel budget, nessun nuovo host; costo contrattuale, quote disponibili, volumi e traffico da verificare |
| Identity/federazione/MFA | Ambiente di prova quando introdotto | Accesso protetto necessario | Necessari secondo charter | Confrontare self-hosted e gestito dopo requisiti e prova B01, non scegliere dal solo prezzo iniziale |
| Backup separato dal nodo applicativo | Fixture riproducibili, conservazione del lavoro | Necessario se la demo mantiene stato da recuperare | Necessario | Dimensione, frequenza, retention, cifratura e prova di ripristino |
| Monitoraggio e notifica | Test e diagnostica | Health/errori pertinenti | Necessari con reperibilità definita | Risorse self-hosted oppure servizio; copertura esterna distinta dai soli health check locali |
| Canale protetto | Necessario dove transitano credenziali/dati | Necessario per identità e dominio | Necessario | Modalità e costo da scegliere; nessuna modifica automatica all'HTTP tecnico esistente |
| Dominio/DNS | Non presunto necessario | Da valutare secondo modalità di accesso | Da definire con l'accesso previsto | Registrazione/rinnovo distinti; nessun dominio acquistato |
| E-mail operativa di identity/allarmi | Da valutare con il provider | Secondo flussi adottati | Secondo flussi adottati | Volumi, recupero account e notifiche; non introdurre un servizio se non necessario |
| Storage allegati | Fuori slice iniziale | Fuori slice iniziale | Solo se autorizzato nel pilota | Non includere una piattaforma documentale prematura |
| HA/multi-host | Non richiesti | Fuori baseline D47 | Fuori baseline D47 | Nessuna nuova macchina prevista e nessuna promessa di alta disponibilità dal singolo VPS |
| Operatività e manutenzione | Tempo da esplicitare | Tempo da esplicitare | Responsabile e copertura da approvare | Patch, vulnerabilità, backup, ripristino e incidenti; distinguere esborso e lavoro |

## 4. Confronto identity ancora da svolgere

D47 fissa sulla VPS esistente l’esecuzione dei carichi di demo e pilota. Il charter propone Keycloak self-hosted come candidato, non come provider scelto. Il gestito resta solo un confronto documentale richiesto dal backlog, non un acquisto o una dipendenza operativa approvati. Il confronto con un'alternativa gestita deve documentare federation richiesta, MFA, utenti attivi, amministrazione/recupero, localizzazione e trattamento dati, costi iniziali e di rinnovo, limiti di piano e responsabilità trasferite.

Self-hosted: quotare risorse, aggiornamenti, backup e gestione degli incidenti. Gestito: verificare funzioni nel piano effettivamente confrontato, prezzo e dipendenze esterne; non assumere che il piano iniziale copra i requisiti del charter. Entrambe le opzioni restano da verificare su fonti primarie aggiornate e con prova B01.

## 5. Responsabilità da assegnare, non assunte

| Attività | Responsabile da concordare | Prova richiesta |
| --- | --- | --- |
| Approvazione spesa e provider | Proprietario | Budget e scelte esplicite; nessuna attivazione prima dell'autorizzazione |
| Patch host/container e dipendenze | Operatore da identificare | Procedura, verifica vulnerabilità e rollback |
| Backup e recupero database/configurazioni necessarie | Operatore da identificare | Ripristino esercitato su ambiente separato e dati di test |
| Gestione identità, recupero account e accessi di emergenza | Referente autorizzato da identificare | Flussi verificati, MFA/federazione e audit pertinenti |
| Allarmi e incidenti | Referente e copertura da definire | Notifica ricevuta e procedura di intervento provata |
| Protezione dati e idoneità per uso reale | Proprietario con competenze pertinenti | Giurisdizione/contratti e misure verificate prima del pilota |

RPO = perdita temporale massima di dati accettata; RTO = tempo obiettivo per il ripristino. Nessun valore è proposto come già approvato, nessuno dei due è garantito dal solo acquisto di backup o VPS. Occorre provarli e distinguere disponibilità del servizio da possibilità di recuperare i dati.

## 6. Dati necessari e prossimo gate

1. Vincolo confermato D47: budget comprensivo del VPS attivo e nessun acquisto di altre macchine per demo/pilota. Importo mensile non comunicato; non occorre scegliere una nuova taglia di host.
2. Costo effettivo del VPS corrente e cosa include, senza richiedere credenziali o documenti con dati personali.
3. Budget separato per lavoro operativo se esternalizzato; responsabilità e copertura disponibili.
4. Volumi iniziali pilota, capacità disponibile sulla VPS e obiettivi RPO/RTO compatibili con il nodo unico da concordare e provare.
5. Destinazione di backup esterna già disponibile o inclusa nei servizi esistenti: verificare indipendenza dal nodo, capacità, retention e ripristino, senza presumere nuove spese.

Confrontare eventuali listini primari delle sole voci pertinenti al vincolo D47, senza preventivare nuove macchine, con data di rilevazione, valuta, IVA, cadenza, risorse incluse, rinnovi e costi opzionali. Normalizzare con calcoli eseguiti e dichiarare assunzioni/extra. Non riportare un totale finché i dati necessari sono mancanti.

**Stato D02:** In corso. Nessun criterio economico è soddisfatto dal solo elenco delle voci; preventivo, scelta del provider e responsabilità restano aperti. D01 resta separata, In verifica; B00 e dossier complessivo non approvati. Il servizio pubblico non è stato modificato.
