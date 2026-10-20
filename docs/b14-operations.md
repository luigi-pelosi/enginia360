# B14 — Istruzioni operative ripetibili e recupero

Ambito: scenario sintetico effimero della prima vertical slice, eseguito in un progetto Docker Compose isolato. Nessun ambiente persistente, nessuna porta pubblicata, nessun dato reale. Il bootstrap HTTP esistente, il canale Tailscale, i segreti, i backup e i 25 volumi conservati non vengono modificati da queste procedure.

## 1. Prerequisiti

- Docker Engine con plugin Compose e `openssl`, `python3`, `git` sull'host.
- Directory di lavoro scrivibile per gli artefatti temporanei: esportare `TMPDIR` su una directory di scratch dedicata.
- Immagini bloccate per digest nei Dockerfile e nei compose: non sostituire i tag.

## 2. Esecuzione completa dello scenario

```sh
cd /percorso/di/enginia360
export TMPDIR=/percorso/di/scratch
timeout 600 sh scripts/run-b14-tests.sh
```

Il runner, in un unico progetto effimero `enginia360-b14-<pid>`:

1. costruisce e avvia i container irrobustiti (nonroot, read-only, capability rilasciate, nessuna porta pubblicata, limiti di risorse e log) con identity sintetica, PostgreSQL privato, API, web e simulatore amministrativo;
2. applica in ordine le migrazioni `database/b03` → `database/b13` e le sole fixture sintetiche;
3. esegue il tracer congiunto `scripts/test-b14.py`: la stessa superficie Workshop porta un ordine alla destinazione **interna** (fattura tecnica confermata + scrittura contabile quadrata) e un ordine di un'altra società alla destinazione **esterna simulata** (richiesta, conferma di business, chiusura amministrativa), verificando che nessuno dei due percorsi contamini l'altro;
4. esegue i test DOM reali con login e fetch autenticati (`src/B13.runtime.test.tsx`, `src/B14.runtime.test.tsx`);
5. verifica la diagnosticabilità dei log (`scripts/test-b14-diagnostics.py`): eventi di audit Workshop/Billing/Accounting e correlation ID distinti, assenza di credenziali effimere e token;
6. riesegue le suite di isolamento RLS con ruolo applicativo reale di B12 e B13 prima e dopo il ripristino nello stack congiunto; B11 è rieseguito separatamente con i suoi veri fatti di riconciliazione;
7. esegue la prova di recupero `scripts/test-b14-restore.py` (sezione 4);
8. verifica il rollback guardato nell'ordine documentato e la riapplicazione della migrazione sul database ripristinato;
9. al termine (anche in caso di errore) rimuove container, reti e volumi del solo progetto effimero e lo verifica per etichetta.

Suite per singolo incremento, utili in isolamento: `sh scripts/run-b10-tests.sh`, `run-b11-tests.sh`, `run-b12-tests.sh`, `run-b13-tests.sh`.

## 3. Migrazioni e rollback operativo

- Ordine di applicazione: `b03` → `b04` → `b05` → `b06` → `b07` → `b08` → `b09` → `b10` → `b11` → `b12` → `b13`. Ogni directory contiene lo schema (`0xx_*.sql`), le fixture sintetiche (`900_*`), le prove RLS (`950_*`) e il rollback (`990_*`).
- Ordine di rollback: **inverso**, `b13` → `b12` → `b11` → `b10` → …. Ogni `990_rollback.sql` si **rifiuta** se esistono evidenze vive del proprio incremento (scritture contabili, collegamenti, fatture, claim, richieste incerte). Procedura corretta: fermare le scritture e i worker, risolvere o esportare le evidenze con un piano approvato, poi eseguire il rollback.
- Dopo un rollback, la migrazione dello stesso incremento è riapplicabile: il runner lo esercita realmente su database ripristinato.
- Nessun downgrade distruttivo è eseguito su dati conservati: in ambiente reale servono backup e retention approvati prima di qualunque rollback.

## 4. Prova di backup e ripristino (gate OPE03, prova su dati di test)

`scripts/test-b14-restore.py` esegue, nel solo progetto effimero:

1. **letture di riferimento** autenticate (fattura, scrittura contabile, stato amministrativo esterno) e conteggi SQL;
2. **backup reale** `pg_dump -Fc` del database sintetico in un file di scratch con permessi `600`, con durata e dimensione misurate;
3. **distruzione reale** del data store: arresto dei servizi, rimozione del container PostgreSQL e quindi del suo tmpfs `/var/lib/postgresql`, con verifica dell’assenza del vecchio ID e di un nuovo ID al ripristino. Lo script rifiuta qualunque progetto che non inizi con `enginia360-b14-` e confronta l'elenco dei volumi non effimeri prima e dopo, così i volumi conservati non possono essere toccati;
4. **ripristino misurato**: cluster nuovo e vuoto (verificato), `pg_restore --exit-on-error`, riavvio di API e web, nuova lettura autenticata;
5. **confronto**: le risposte HTTP e il contenuto canonico di tutte le tabelle applicative dopo il ripristino devono essere identici a quelli del backup (SHA-256); digest del dump, hash dei sorgenti e revisione Git sono registrati, e le tabelle ripristinate devono conservare la row-level security forzata;
6. scrittura del referto `<progetto>-restore-measurement.json` in scratch (fuori dalla directory eliminata dal runner) e cancellazione del dump.

La procedura eseguibile autorevole è `sh scripts/run-b14-tests.sh`; `test-b14-restore.py` riutilizza **tutti** gli overlay e il file env effimero del runner, non il compose bootstrap. Dopo la creazione del cluster vuoto ricrea esclusivamente il ruolo tecnico `enginia360_outbox_reader` con gli stessi attributi NOLOGIN/BYPASSRLS della migrazione B10 e ripristina ownership/ACL dal dump: non usa `--no-owner`, che perderebbe il proprietario della funzione SECURITY DEFINER. Il ruolo applicativo non riceve BYPASSRLS; le prove RLS con quel ruolo sono rieseguite dopo restore.

**Limiti dichiarati.** La misura è una prova su dati sintetici in un progetto effimero su un solo host: non è un RTO contrattuale, un RPO verificato, una garanzia di disponibilità o una prova di recupero del nodo. Non sono stati configurati destinazione esterna dei backup, cifratura e gestione delle chiavi, checkpoint giornaliero, retention, monitoraggio dei fallimenti o allarmi; questi restano i gate **OPE03** (destinazione, quote, cifratura, retention e ripristino misurato prima del pilota con dati reali), **OPE04** (ruoli residui, estremi temporali e allarmi SMTP con ricezione provata prima della messa in servizio) e **OPE05** (paese/contratti, costi effettivi, capacità e risorse di recupero del target reale prima del pilota) del documento 12. Gli obiettivi iniziali dichiarati in D49 — RPO fino al giorno precedente, RTO massimo 1 ora — restano obiettivi da progettare e non sono dimostrati da questa prova.

## 5. Diagnosi

- Ogni risposta HTTP espone `X-Correlation-ID`; i log applicativi sono JSON con scope di correlazione e eventi di audit tecnici per Counterparties (303), Billing (312), Accounting (313), Workshop (404) e Inventory (606/608/609).
- L'audit registra azione, esito, identificativo tecnico della risorsa e identità; non contiene importi, conti, ragioni sociali, token o credenziali. Il controllo è eseguito dalla suite, non soltanto documentato.
- Le attività W3C ASP.NET espongono TraceId/SpanId nello scope dei log; EventId 314 registra metodo, stato e durata senza URL/payload. Il Meter `Enginia360.Api` espone l’istogramma `enginia360.http.duration` in secondi, con soli tag metodo/stato: un MeterListener eseguito nei test verifica la misura. Non è configurato un collector/exporter OpenTelemetry persistente o un sistema di allarmi: nessuna infrastruttura ipotetica è aggiunta. I test di mutazione del validatore rifiutano credenziali, payload di business nell’audit e assenza di traccia.

## 6. Esclusioni

Nessun deployment pubblico, dominio, invio e-mail/SMTP, acquisto, ERP reale, SdI, incasso, dato personale o credenziale reale è introdotto da queste procedure. Il modulo contabile è limitato alla scrittura tecnica del caso 001; la validazione fiscale e contabile generale resta ai referenti competenti.
