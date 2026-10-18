# B03 — controparte comune e destinazioni: verifica locale

**Stato corrente — 18 ottobre 2026:** implementazione locale su `feat/b03-counterparties`, baseline B02 `6a80eecb35c287fb3e68ad782bba926f09f47fea`. Il proprietario comunica «Ho fatto la prova privata: funziona tutto. Possiamo procedere»: accettazione privata positiva e autorizzazione alla consegna finale del solo B03, soggetta a review indipendente e CI remota positiva. Ambiente manuale B03 separato già predisposto come documentato in `b03-manual-operations.md`; nessun commit/push/PR/merge eseguito. Review indipendente delle ultime aggiunte manuali e CI remota pendenti. D60/D61 restano il confine funzionale. B04–B14 restano aperti, `blocked`, Backlog e non autorizzati. Le sezioni precedenti di verifica sono evidenze storiche: prevalgono questo stato e il riesame finale sotto.

## Contratto finito e ownership

- La controparte sintetica esistente ha una sola identità per tenant e i tre campi D36: `legalName`, `fiscalIdentifier`, `registeredOffice`. A/B leggono e ricercano la stessa riga; nessuna creazione anagrafica generale, deduplicazione o regola fiscale implicita.
- Organizations conserva membership, riferimenti societari e concessioni. Il suo adapter nell'host implementa la porta `ICounterpartyAccess`; Counterparties non legge né scrive le tabelle Organizations. Il nuovo assembly Counterparties dipende soltanto dal proprio Contracts e dai framework; entità e DbContext sono interni, con dominio separato dalla persistenza. Nessun modulo futuro vuoto.
- Permessi tecnici della prova: `counterparties.read` sulla società per la consultazione; `counterparties.destination.write` sulla proprietaria per aggiungere l'indirizzo operativo; `counterparties.destination.publish` sulla proprietaria per pubblicare. Il permesso specifico di edit comune è rappresentato separatamente in `organization_access.common_edit_permissions`, riferito alla membership/tenant, e richiede anche consultazione autorizzata nel contesto selezionato. Questi identificatori e le assegnazioni sintetiche non costituiscono un catalogo di ruoli, provisioning o autorità di concessione per clienti reali.
- I grant societari con `SiteId` o `WarehouseId` valorizzati non soddisfano la concessione societaria. Le prove isolano anche, separatamente, edit comune senza grant di pubblicazione, grant limitato a sede, grant limitato a magazzino e società non proprietaria.
- Una destinazione è sempre creata privata. Il backend deriva tenant/proprietaria dal contesto verificato; payload con `published`, tenant o proprietaria manipolati non possono pubblicare o cambiare titolarità. Solo POST esplicita di pubblicazione aggiorna la stessa destinazione, rendendola leggibile alle società autorizzate del medesimo tenant. Mai cross-tenant.
- Nessun aggiornamento/cancellazione dell'indirizzo operativo, revoca di pubblicazione, disattivazione o workflow ERP è introdotto. L'unica modifica della destinazione in questa slice è la pubblicazione. Le policy di tali eventuali operazioni future restano da autorizzare.
- Le query applicative verificano azione e risorsa; RLS impone un secondo confine su tenant e, per le destinazioni, proprietaria/visibilità. `SET LOCAL` tramite `set_config(..., true)` vive in transazioni esplicite; nessun tenant accettato come identità dal client. Il ruolo runtime non è superuser/BYPASSRLS e non può scrivere le concessioni.
- Audit operativo tecnico nei log JSON: EventId 303, template dell'azione, esito HTTP, UUID risorsa/identità e correlation ID tecnico. Nessun payload, nome, identificativo fiscale, indirizzo, password o token. Non è un giornale di compliance durevole/atomico: è soggetto alla rotazione e alla disponibilità dei log del processo. Le richieste respinte dall'autenticazione prima dell'endpoint restano coperte dalla pipeline di autenticazione, non dal filtro B03.

## Superficie minima

API autenticata, mappata soltanto con `Counterparties:Enabled=true`:

- `GET /api/v1/counterparties/companies`: società consultabili tramite i permessi B03, senza ereditare la capability B02 delle note.
- `GET /api/v1/counterparties?legalEntityId=<uuid>&search=<testo opzionale>`: ricerca comune parametrizzata, ricerca massima 200 caratteri.
- `GET /api/v1/counterparties/{id}?legalEntityId=<uuid>`: lettura diretta autorizzata.
- `PUT /api/v1/counterparties/{id}`: edit comune specifico; campi normalizzati e limiti tecnici 200/100/500, non validazione fiscale.
- `POST /api/v1/counterparties/{id}/destinations`: aggiunta privata, indirizzo massimo 500 caratteri.
- `GET /api/v1/counterparties/{id}/destinations?legalEntityId=<uuid>` e `GET /api/v1/counterparties/destinations/{id}?legalEntityId=<uuid>`: lettura con visibilità e autorizzazione di risorsa.
- `POST /api/v1/counterparties/destinations/{id}/publication`: permesso distinto sulla proprietaria, non edit comune/sede/magazzino.

La UI italiana privata è compilata soltanto con `VITE_B03_TEST_UI=true`. Consente login sintetico, società autorizzata, campi comuni, destinazioni private e pubblicazione esplicita; presenta gli errori reali del backend senza affidare la sicurezza ai pulsanti. Valida i contratti ricevuti e scarta risposte obsolete dopo cambio di contesto. Token solo in memoria; nessun login B03 sul bootstrap di default. Il percorso manuale persistente B02 e le sue fixture/istruzioni non sono modificati.

## RED → GREEN osservati

Comando HTTP usato per ciascun comportamento, contro Compose isolata già avviata:

```sh
docker run --rm --network enginia360-b03-work_backend -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22 python3 scripts/test-b03.py http://web:8080 <comportamento>
```

| Comportamento | RED eseguibile prima del codice | GREEN osservato |
| --- | --- | --- |
| `shared_identity` | lista attesa 200, ottenuto 404 | A/B stessa identità D36 e lettura diretta |
| `private_destination` | creazione attesa 201, ottenuto 404 | creazione e rilettura B; A/cross-tenant esclusi anche per ID |
| `publication` | fallisce l'asserzione di rifiuto 403: azione ancora assente | rifiuto senza grant societario; pubblicazione autorizzata stessa identità; visibilità A solo dopo l'azione |
| `common_edit` | fallisce l'asserzione di rifiuto specifico: PUT non implementata | publisher non modifica; editor modifica; nessun diritto implicito di pubblicazione |
| `company_choices` | società B03 attese 200, ottenuto 404 | membership con permesso B03 ma senza contesti B02 vede soltanto B |
| `search_identity` | ricerca impossibile restituisce righe invece di lista vuota | filtro parametrizzato e limite input verificati |
| audit | `python3 scripts/test-b03-audit.py` sui log fallisce: EventId 303 assente | eventi di successo/rifiuto con soli metadati tecnici |

Il primo tentativo della fixture Python fallì per import del file con trattino; corretto **prima** del RED valido `shared_identity` (404). Non viene contato come RED di comportamento.

UI: `docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 npm test -- --run src/B03.test.tsx` è stata eseguita a ogni incremento. RED successivi: heading B03 assente; pulsante Destinazioni assente; azione Condividi nel tenant assente; azione Modifica campi comuni assente; URL società ancora B02 invece di B03; contratto malformato non segnalato; errore di richiesta obsoleta mostrato dopo cambio società. Ogni comportamento è stato reso GREEN prima del successivo. Un errore nella coda delle risposte del mock è stato corretto nella fixture, non trattato come RED applicativo.

Le prove supplementari di architettura, regressione B02 e isolamento negativo estendono queste evidenze; non sono presentate come RED iniziali di funzioni già esistenti.

## Comandi ripetibili e risultati reali

Non serve .NET installato sull'host; gli SDK sono eseguiti nei container. I tag/digest completi dell'SDK e Node sono quelli già bloccati nei Dockerfile. Le nuove esecuzioni ripetibili nel runner usano digest anche per Python/Node.

```sh
sh scripts/run-b03-tests.sh
sh scripts/run-b02-tests.sh

docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests --no-restore --verbosity minimal'
docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 sh -c 'npm test && npm run build && npm audit --audit-level=low'
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive && dotnet list src/Modules/Counterparties/Enginia360.Counterparties package --vulnerable --include-transitive'
git diff --check
```

Risultati finali:

- Suite API/architettura: **26 superati, 0 falliti**, restore locked-mode e Release publish riusciti. Nessun warning applicativo tollerato.
- Suite UI ordinaria: **11 superati**, con **1 test runtime intenzionalmente saltato** senza ambiente HTTP. Typecheck e build riusciti.
- Il runner B03 esegue poi quel test runtime separatamente con `VITE_B03_HTTP_BASE=http://web:8080`: **1 superato**, DOM React/JSDOM collegato via fetch reale a nginx → API → Keycloak/PostgreSQL, senza risposte di rete simulate. Esercita destinazione privata B/invisibile A, pubblicazione e rilettura A, edit comune da altra identità, rifiuti di pubblicazione/creazione e visualizzazione degli errori. L'URL della UI privata è stato aperto anche tramite lo strumento browser (sola navigazione; login e flusso autenticato nel browser non verificati); nessuna credenziale è stata inserita tramite il browser/vault vuoto.
- B03 HTTP: **7 probe nominali**, più ripetizione di `publication` su **3 fixture indipendenti** insufficienti, più `shared_identity` dopo rollback/reapply. Pool: **10 alternanze** di identità/tenant con un unico PID PostgreSQL, mantenendo letture B03 corrette dopo successo e rifiuto.
- Test SQL col ruolo runtime: SELECT/INSERT/UPDATE cross-tenant negati, riservatezza societaria e pubblicazione same-tenant, INSERT già pubblico negato, transazione senza contesto senza righe e GUC ripulite, ruolo senza bypass RLS.
- Migrazioni applicate due volte; rollback distruttivo B03 eseguito; due tenant B02 conservati; reapply e lettura B03 nuovamente riusciti.
- Compose B03: **4 container healthy**, nonroot, filesystem read-only, capability rimosse, no-new-privileges, CPU/memoria/PID/log limitati, **nessuna porta host pubblicata**. Risorse rimosse dal runner con trap.
- Audit sul run completo: **128 eventi tecnici** verificati con successi e rifiuti, campi fissi e assenza dei payload sintetici sensibili. Questo è il conteggio del run verificato, non una promessa sul numero di eventi di esecuzioni future.
- Runner B02 completo: PASS HTTP, ripetizione baseline, rifiuto identità cross-tenant e riferimenti incoerenti, privilegi e hardening; environment manuale persistente non coinvolto.
- npm audit: **0 vulnerabilità**. Audit NuGet API/test/modulo: nessun package vulnerabile secondo le sorgenti consultate. Nessun nuovo package esterno introdotto: i lock cambiano per il grafo dei nuovi progetti.
- Nessuna CI remota o scansione di vulnerabilità delle immagini dichiarata eseguita.

Log locali dettagliati: `$TMPDIR/b03-final-integration.log`, `$TMPDIR/b03-b02-regression.log`; RED UI in `$TMPDIR/b03-ui-*-red.log`. Sono evidenze temporanee fuori repository, non artefatti da committare.

## Riesame circoscritto del gap CI (17 ottobre 2026)

**Esito: BLOCK per portabilità CI; runtime locale PASS.** Il parent ha aggiunto alla workflow `sh scripts/run-b03-tests.sh`, aumentato il timeout complessivo da 15 a 25 minuti e aggiunto `test_ci_executes_b03_runtime_acceptance` in `scripts/test-ci-runtime.py`. Il RED iniziale del nuovo test (1 fallito, 1 superato) è evidenza fornita dal parent, non rieseguita in questo riesame. Sull'albero attuale `python3 scripts/test-ci-runtime.py` termina con **2 test superati**, exit 0; verifica presenza del comando e configurazione Compose, non avvio effettivo della workflow GitHub.

`sh scripts/run-b03-tests.sh` termina con **exit 0**; log `$TMPDIR/b03-ci-gap-integration.log`. Confermati 7 probe HTTP nominali, 3 fixture indipendenti di pubblicazione insufficiente, regressione HTTP B02, **1 test DOM/runtime superato** (4,51 secondi di suite), SQL/RLS col ruolo runtime, doppia migrazione, rollback/reapply, **128 eventi audit** tecnici e **4 container healthy/hardened senza porte pubblicate**. Il test DOM usa fetch reale (solo risoluzione URL adattata), non risposte simulate. Il runner usa credenziali DB casuali in scratch con umask 077, non stampa credenziali e applica trap di cleanup. Dopo il run non rimangono container/reti/volumi del progetto B03 né file `enginia360-b03-*.env`; i container persistenti B02 restano presenti e non sono stati riavviati.

**Blocker riprodotto:** il runner richiede `TMPDIR` alla riga 4, ma la workflow attuale non lo inizializza esplicitamente. Rimuovendo soltanto `TMPDIR` dall'ambiente del processo e avviando lo stesso runner, l'esecuzione termina immediatamente con **exit 2**, `TMPDIR: use a scratch directory`, prima di creare risorse. Il successo locale dipende quindi da una variabile fornita da Hermes e non dimostra la portabilità CI. Occorre inizializzare esplicitamente uno scratch nella workflow (ad esempio da `RUNNER_TEMP`) e aggiungere una regressione prima della chiusura del gap; in questo incarico di verifica non sono state apportate correzioni al codice/CI. I 25 minuti sono un limite complessivo ragionevole ma non misurato su runner GitHub a cache fredda; la CI remota resta non eseguita. Nessun commit/push, mutazione GitHub o deployment persistente.

## Migrazione e rollback operativo

`compose.b03-test.yaml` è un **override** di `compose.b02-test.yaml`, solo per un nuovo Project Docker isolato. Non avviarlo con il nome dell'ambiente manuale persistente. Non aggiunge porte host, non cambia Tailscale, ingress o bootstrap pubblico.

Il runner crea credenziali DB casuali in un file scratch 0600, avvia un Project univoco, monta `database/b03` read-only ed esegue esplicitamente:

1. `003_company_permissions.sql`: concessioni Organizations, RLS e FK membership/società coerenti.
2. `004_counterparties.sql`: schema e nucleo comune tenant-scoped.
3. `005_grants.sql`: privilegi runtime limitati.
4. `006_destinations.sql`: destinazioni private di default, FK al nucleo comune, RLS SELECT/INSERT.
5. `007_publication.sql`: UPDATE soltanto della colonna Published e policy proprietaria.
6. `008_common_edit.sql`: permesso specifico separato, RLS e UPDATE soltanto dei tre campi comuni.
7. `900`–`903`: **fixture sintetiche esplicite**, non provisioning o migrazioni di dati reali.

Le transazioni DDL e i comandi idempotenti sono stati rieseguiti realmente. Come la baseline B02, non sono un migration engine di produzione: `IF NOT EXISTS` non riconcilia uno schema arbitrariamente alterato. Per un cambiamento futuro serve una nuova migrazione revisionata; non modificare retroattivamente questi file per forzare la convergenza di dati esistenti.

`950_rls_test.sql` inserisce esclusivamente righe sintetiche ed esegue i test col runtime role. `990_rollback.sql` elimina schema Counterparties e le sole due nuove tabelle di concessione Organizations. **Perde destinazioni, edit comuni e concessioni B03**; usare solo nella prova sacrificabile, esportando prima ciò che occorre. Non elimina tabelle, note, membership o tenant B02. Il runner verifica i due tenant rimasti e ricrea B03 dalle fixture. Per tornare al solo comportamento B02, rimuovere l'override/flag B03 e usare gli artefatti B02: non è un comando di downgrade su un ambiente persistente autorizzato.

Nessuna modifica dell'ambiente manuale B02, del bootstrap originario, della rete Tailscale o di una configurazione reale è necessaria o stata eseguita. La build del database continua a copiare la baseline B02; i file B03 in sottodirectory non vengono eseguiti automaticamente dall'entrypoint PostgreSQL e sono applicati solo dal runner esplicito.

## File della modifica locale

52 percorsi (inclusi documenti D60, CI/test del parent e ultime aggiunte manuali); conteggio univoco verificato con `git ls-files --modified --others --exclude-standard`. Rimossi due file `scripts/__pycache__/*.pyc` generati dai test; nessun runtime.env, cache, output build, node_modules o configurazione locale nel manifest. Il manifest include i quattro percorsi manuali elencati sotto oltre ai 48 precedenti. Non è ancora un manifest staged: index vuoto.

```text
compose.b03-manual.yaml
docs/b03-manual-operations.md
docs/b03-manual-scenarios.it.md
scripts/test-b03-manual.py
.github/workflows/ci.yml
compose.b03-test.yaml
database/b03/003_company_permissions.sql
database/b03/004_counterparties.sql
database/b03/005_grants.sql
database/b03/006_destinations.sql
database/b03/007_publication.sql
database/b03/008_common_edit.sql
database/b03/900_synthetic_fixtures.sql
database/b03/901_destination_fixture.sql
database/b03/902_permission_fixtures.sql
database/b03/903_common_edit_fixture.sql
database/b03/950_rls_test.sql
database/b03/990_rollback.sql
docs/b03-verification.md
docs/foundation/01-glossary-and-domain-boundaries.md
docs/foundation/02-organization-and-access.md
docs/foundation/07-vertical-slice-backlog.md
scripts/run-b03-tests.sh
scripts/test-b03-audit.py
scripts/test-b03.py
scripts/test-ci-runtime.py
src/Enginia360.Api/Dockerfile
src/Enginia360.Api/Enginia360.Api.csproj
src/Enginia360.Api/OrganizationAccess/CounterpartyAccessAdapter.cs
src/Enginia360.Api/Program.cs
src/Enginia360.Api/packages.lock.json
src/Modules/Counterparties/Enginia360.Counterparties.Contracts/Contracts.cs
src/Modules/Counterparties/Enginia360.Counterparties.Contracts/Enginia360.Counterparties.Contracts.csproj
src/Modules/Counterparties/Enginia360.Counterparties.Contracts/packages.lock.json
src/Modules/Counterparties/Enginia360.Counterparties/CommonEndpoints.cs
src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs
src/Modules/Counterparties/Enginia360.Counterparties/DestinationEndpoints.cs
src/Modules/Counterparties/Enginia360.Counterparties/Domain/Counterparty.cs
src/Modules/Counterparties/Enginia360.Counterparties/Domain/Destination.cs
src/Modules/Counterparties/Enginia360.Counterparties/Enginia360.Counterparties.csproj
src/Modules/Counterparties/Enginia360.Counterparties/Infrastructure/CounterpartiesDbContext.cs
src/Modules/Counterparties/Enginia360.Counterparties/TechnicalAuditFilter.cs
src/Modules/Counterparties/Enginia360.Counterparties/packages.lock.json
tests/Enginia360.Api.Tests/BootstrapTests.cs
tests/Enginia360.Api.Tests/CounterpartyArchitectureTests.cs
tests/Enginia360.Api.Tests/packages.lock.json
web/Dockerfile
web/src/App.test.tsx
web/src/App.tsx
web/src/B03.runtime.test.tsx
web/src/B03.test.tsx
web/src/B03TestApp.tsx
```

## Residui reali

### CI scratch prerequisite correction

The isolated B03 runner passed locally, but a portability check found that GitHub Actions did not explicitly provide its required `TMPDIR`. A new regression in `scripts/test-ci-runtime.py` failed with two passing tests and one failure before the workflow change. Job-level `TMPDIR: ${{ runner.temp }}` now provides runner-owned scratch storage; all three CI configuration regressions pass. This supersedes the missing-scratch blocker; actual remote execution remains unverified until a PR is published.

- Review indipendente delle ultime aggiunte manuali ancora richiesta; autorizzazione alla consegna ricevuta, non serve richiederla nuovamente. PR/CI remota non esistono ancora per questa modifica locale.
- L'aggiornamento della frase storica «foundation dossier remains unapproved» in `AGENTS.md` è stato bloccato dal controllo di scrittura del file protetto (approvazione non ricevuta). Il file è rimasto invariato; nessun aggiramento tentato. D58/D60/D61 e questo report rendono esplicito lo stato corrente senza cambiare il charter.
- Nessun blocker di dominio B03 residuo sulla pubblicazione. Restano fuori scope policy di revoca/deduplica, provisioning/ruoli reali, sistemi autorevoli ERP reali, validazioni fiscali, accesso pubblico, audit di compliance e readiness di produzione.

## Preparazione consegna dopo accettazione — 18 ottobre 2026

Accettazione manuale e autorizzazione alla consegna riferite dal proprietario, non inventate dall'agente: «Ho fatto la prova privata: funziona tutto. Possiamo procedere». Nessun dettaglio aggiuntivo sui singoli scenari/browser è stato fornito. Il riesame non ripete login o scritture sui dati persistenti accettati.

Prove rieseguite sul working tree corrente (tutti exit 0):

- `sh scripts/run-b03-tests.sh`: sette probe, tre fixture indipendenti, B02 HTTP, un test DOM/runtime reale, SQL/RLS, doppia migrazione, rollback/reapply, 128 eventi audit e quattro container healthy/hardened senza porte host.
- `sh scripts/run-b02-tests.sh`: suite isolata completa PASS.
- `env -i PATH="$PATH" HOME="$HOME" TMPDIR="$TMPDIR/b03-delivery/fresh" sh -c 'python3 scripts/test-ci-runtime.py && sh scripts/run-b03-tests.sh'`: tre regressioni CI PASS e intero B03 PASS, nessuna dipendenza da variabili developer; directory fresh vuota dopo cleanup.
- Comandi Docker .NET/Node nella sezione ripetibile: restore locked-mode, 26 API/architettura PASS, Release publish, 11 UI PASS/1 runtime saltato nella suite ordinaria (poi eseguito dal runner), typecheck e build default/B02/B03 PASS. npm audit livello low: zero vulnerabilità; NuGet API/test/modulo nessun package vulnerabile secondo le sorgenti consultate.
- `git diff --check`: PASS. Scan statico del manifest: soltanto assegnazioni di password casuali via openssl segnalate dal pattern, nessun segreto hardcoded trovato; le credenziali sintetiche già versionate sono fixture, non account reali. Questo scan non è una certificazione né una scansione immagini.
- Snapshot sicuro Docker prima/dopo: identici ID, immagini, start timestamp e restart count di tutti i dieci container persistenti; runner isolati rimossi. Nessun comando di modifica Tailscale, Compose persistente o SQL persistente; nessun runtime.env letto/stampato/staged. Il riesame non afferma uguaglianza byte-per-byte dei dati né ripete il provisioning già accettato.

Log: `$TMPDIR/b03-delivery/{api,ui,b02,b03,minimal-env}.log`. Manifest e SHA-256 per file in `$TMPDIR/b03-delivery/{manifest,review-sha256}.json`, rigenerati dopo la documentazione finale. Non sono artefatti repository.

**Gate di review fail-closed:** la precedente review PASS non prova l'approvazione delle quattro aggiunte manuali. Al parent viene restituito questo insieme circoscritto per review indipendente: `compose.b03-manual.yaml`, `scripts/test-b03-manual.py`, `docs/b03-manual-operations.md`, `docs/b03-manual-scenarios.it.md`, `.github/workflows/ci.yml`, `scripts/test-ci-runtime.py`, `docs/b03-verification.md`. Nessun errore bloccante individuato nell'ispezione preparatoria: overlay solo loopback/restart/mount della configurazione edge B02 già esistente; script manuale sole letture e mutazioni attese rifiutate; CI richiama il runner e fornisce scratch. Non è un verdetto indipendente e non autorizza a saltarlo. Lasciato tutto uncommitted/unstaged; nessun push/PR/merge/CI remota. Dopo review positiva sull'esatto contenuto, il parent può eseguire la consegna già autorizzata e verificare la CI remota prima del merge dello stesso head. B04–B14 restano bloccati in Backlog.
