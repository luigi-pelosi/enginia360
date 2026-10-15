# Dossier di fondazione — 06. Modello iniziale delle minacce

**Stato:** bozza di analisi e controlli proposti; nessun audit di sicurezza eseguito. Non approvazione del dossier né autorizzazione a esporre il dominio sul bootstrap pubblico.
**Fonti:** `PROJECT_CHARTER.md` §7–9, §11 e §14; [organizzazione/accessi](02-organization-and-access.md), [ownership](03-capabilities-and-data-ownership.md), [architettura](05-solution-and-module-boundaries.md). I controlli sono proposte di progetto e criteri di verifica, non garanzie di sicurezza già ottenute.

## 1. Beni e confini di fiducia

**Da proteggere:** identità/sessioni, dati comuni delle controparti, estensioni societarie, documenti/righe e allegati, stock e fatti tecnici, scritture/risultati economici, customizing, credenziali dei connettori, coda e audit.

**Confini:** browser/API; utente/tenant; dati comuni/dati societari; società/sedi/magazzini autorizzati; modulo/modulo; processo/database; host/connettore/ERP esterno; operatore/supporto; ambiente di prova/ambiente reale. Un utente autenticato, un messaggio di coda o un modulo interno non sono autorizzati a qualsiasi azione per il solo fatto di trovarsi entro il sistema.

## 2. Rischi e controlli da verificare

Le priorità sono un ordinamento progettuale qualitativo, non punteggi quantitativi di rischio o una certificazione.

| ID | Minaccia/scenario | Controlli proposti | Verifica richiesta |
| --- | --- | --- | --- |
| T01 — Critica | Cambio di tenant/società nel payload o nell'URL per leggere/modificare dati estranei. | Contesto verificato lato server, verifica su azione e risorsa, filtri e RLS dove appropriato; nessun accesso automatico a tutte le società. | Due tenant e più società: tentativi di lettura/scrittura/ricerca con ID validi ma non autorizzati rifiutati. |
| T02 — Critica | Dati societari o destinazioni locali esposti tramite anagrafica comune, esportazioni o cache. | Scope esplicito delle risorse, chiavi cache con perimetro corretto, proiezioni minimizzate e controlli in export/ricerche. | Stessa controparte comune, estensioni di A/B: accesso alle sole quote autorizzate; nessuna fuga tramite liste o conteggi. |
| T03 — Critica | Contesto residuo su connessione/job riutilizzato; messaggio eseguito nel tenant sbagliato. | Impostazione/ripulitura del contesto, envelope verificato e scope esplicito del worker; operazioni privilegiate limitate. | Richieste/job alternati tra tenant, errori e riavvii, con controlli sui dati risultanti. |
| T04 — Alta | Modifica indebita di anagrafica comune, ruoli o customizing. | Permessi specifici, autorità di concessione definita, versioni validate, audit e anteprima per retroattività. | Utente con sola lettura non modifica; un amministratore non può concedere ciò che non è autorizzato a gestire. Regole delle deleghe da definire. |
| T05 — Alta | Sviluppo/storno ripetuto o concorrente produce doppio consumo, doppio addebito o quantità eccedenti. | ID operazione stabili, controllo concorrenza e residui, compensazioni collegate alle origini, vincoli del modulo. | Doppio invio e azioni concorrenti; un solo effetto ammesso, residui coerenti e storico preservato. |
| T06 — Alta | Timeout esterno interpretato come fallimento certo e reinvio che duplica l'effetto. | Stato esito incerto, deduplicazione del destinatario o interrogazione/riconciliazione prima del reinvio; niente falsa conferma. | Simulatore accetta e interrompe la risposta: recupero senza doppio effetto. |
| T07 — Alta | Risposta/import esterno altera dati non autorevoli o contiene riferimenti fuori perimetro. | Anti-corruption layer, validazione del contratto e delle mappature, autorità unica, scope tenant/società verificato. | Dati malformati, identità esterna di un'altra società e modifiche al nucleo comune da fonte non autorevole. |
| T08 — Alta | Documento/allegato esposto mediante URL diretto o identificativo indovinabile. | Verifica accesso alla risorsa anche sul download; gestione sicura dei nomi/percorsi, versioni e integrità; niente cartella pubblica di documenti aziendali. | Accesso diretto senza permesso, file di altra società/tenant e riferimenti alterati. Upload/scansione file da progettare prima di attivare allegati. |
| T09 — Alta | Furto di sessioni/credenziali, abuso di account elevati o supporto permanente. | Federation e MFA come requisiti del charter, trasporto protetto per accessi reali, sessioni/revoche e supporto temporaneo tracciato. | Prova del provider ancora da scegliere, autenticazione/revoca e scadenza dei privilegi. Nessun esito già dimostrato dal bootstrap. |
| T10 — Alta | Perdite di richieste o stato non recuperabile dopo crash, crescita illimitata della coda o dati persi. | Outbox persistente nei confini transazionali, retry limitati, escalation e monitoraggio; backup e prova di ripristino. | Restart durante elaborazione, richieste scadute/rifiutate, ripristino da backup e riconciliazione. RPO/RTO ancora da concordare. |
| T11 — Alta | Segreti o dati personali esposti in log, errori, payload di coda o repository. | Segreti fuori repository, log minimizzati, errori senza dettagli sensibili, accesso e retention di coda/audit espliciti. | Controllo di log e fallimenti del simulatore; nessun token o payload personale superfluo. |
| T12 — Alta | Regole fiscali/contabili aggirate dal customizing o storico riscritto. | Invarianti del modulo non aggirabili, versione dei dati rilevanti, compensazioni tracciate e validazione specialistica. | Configurazioni incompatibili rifiutate; scritture quadrate e riferimenti preservati. Non equivale a conformità fiscale. |

## 3. Distinzioni da preservare

- Schema PostgreSQL per modulo è una proposta di separazione dei dati, non prova sufficiente di isolamento. Verificare privilegi effettivi e possibilità di bypass RLS; non testare soltanto il percorso felice con utente privilegiato.
- Scope societario del customizing non abilita una società a cambiare dati comuni o permessi di tutto il tenant.
- Registrazione locale, invio di trasporto e accettazione esterna sono fatti diversi. Le deroghe di continuità non creano conferme esterne fittizie.
- Rientro carcassa, reso del nuovo e installazione hanno identità/effetti distinti, anche se il customizing rende facoltativo un passaggio.
- Non riprodurre nel nuovo sistema una vista pubblica del legacy solo perché esiste. Ogni esposizione di dati operativi richiede un caso d'uso e controlli propri.

## 4. Limiti e porte d'ingresso della slice

Il bootstrap attuale è una superficie HTTP pubblica di stato tecnico. Questa autorizzazione non si estende a credenziali, documenti o dati personali. Prima di aprire funzionalità di dominio a utenti reali occorrono ambiente protetto, autenticazione, autorizzazione, trasporto adeguato, segreti e policy operative verificate. Nessun cambio di TLS, firewall, provider o deployment è eseguito da questo documento.

Per la slice proposta: dati sintetici di test, simulatore esterno deterministico, controlli negativi di isolamento e idempotenza prima della dimostrazione completa. Nessun accesso a ERP reali, emissione fiscale o dati pilota senza incarico e prerequisiti separati.

## 5. Decisioni e verifiche ancora necessarie

- Provider definitivo federation/MFA dopo prova comparabile; ruoli, deleghe e supporto temporaneo.
- Politiche delle sessioni/revoche e protezione dei canali HTTP/API del futuro ambiente di dominio.
- Retention e accesso a log/audit/outbox/documenti; regole di trattamento dei dati da validare con competenze pertinenti.
- Backup, ripristino, obiettivi RPO/RTO e disponibilità, senza promettere SLA dal singolo VPS.
- Contratti reali dei connettori e gestione dei segreti; test della fiducia sulle risposte esterne.
- Verifiche tecniche e validazione fiscale/contabile prima di uso reale.

La proposta può alimentare il backlog con test verificabili. Nessun controllo è dichiarato implementato per il solo fatto di essere elencato; l'approvazione della base architetturale non implica approvazione di ogni dettaglio qui proposto.
