# B05 — Verifica tecnica e handoff

## Stato corrente — accettazione manuale e consegna B05

19 ottobre 2026: il proprietario, dopo la prova privata, risponde **«Ok funziona tutto. Procediamo»**. Accettazione manuale positiva di B05 e autorizzazione a commit/push/PR, CI reale, squash merge e chiusura della sola issue #11; nessuna nuova conferma necessaria. Review indipendenti: candidato core di 44 file PASS (`deleg_8f6e4016`); quattro artefatti manuali PASS (`deleg_04cd4dde`), con unico blocco documentale sulle precedenti righe 5/56 ora riconciliate con ambiente attivo e guide. La correzione è solo documentale: il reviewer non richiede nuovi test applicativi o nuova review indipendente per essa. Contenuto applicativo invariato rispetto agli hash approvati.

**Stato della consegna al congelamento:** In verifica; accettazione e review acquisite, CI remota e merge da eseguire e verificare sullo SHA esatto. Il risultato remoto finale è registrato nella PR e nella issue #11. B06–B14 restano aperti/blocked/Backlog e non autorizzati.

**Ambito accettato e limiti:** percorso sintetico privato italiano UI/API/PostgreSQL, una prestazione e un ricambio, q6/prezzo6/sconto2 [0,100], netto riga HALF_UP6 → base per gruppo → imposta gruppo HALF_UP6 → totale somma; snapshot, retry, isolamento e autorizzazioni. Non fiscalità generale, stock, costi/margini, ERP/SdI, produzione o nuova disponibilità/RPO/RTO. Nessuna modifica/rimozione di righe, lista storico o ripristino GUI dopo refresh/login; Rileggi riguarda solo la commessa corrente. Nessun nuovo deploy/restart, SQL o scrittura sui progetti persistenti/manuali/bootstrap/Tailscale durante la consegna. Le precedenti evidenze di provisioning restano storiche, non azioni ripetute.

Manifest finale: 48 percorsi autorizzati elencati sotto, inclusi i quattro artefatti manuali; hash SHA-256 per file in scratch `b05-delivery-manifest.json`, esclusi runtime, segreti, backup e generati. Report non auto-hashato nel proprio testo. Le sezioni D67 e precedenti sotto conservano evidenze e stati storici, superati da questa registrazione dove incompatibili.

### Verifica finale del candidato accettato

Tutti exit 0, in comandi tool separati bounded a 600 s; log scratch `b05-delivery-{api,ui,b02,b03,b04,b05}.log`:

- Docker SDK `10.0.402-alpine3.24`: restore locked e `dotnet test tests/Enginia360.Api.Tests -c Release --no-restore`, **41 passati/0 saltati**; publish Release e audit NuGet API/test con transitivi senza package vulnerabili.
- Docker Node `24.22.0-alpine3.24`: `npm ci --no-audit --no-fund && npm test`, **16 passati/3 runtime saltati**; `npm run build` e ciascuno dei quattro flag VITE_B02/B03/B04/B05_TEST_UI=true, tutti typecheck/build PASS; `npm audit --audit-level=high`, **0 vulnerabilità**.
- `sh scripts/run-b02-tests.sh`, `sh scripts/run-b03-tests.sh`, `sh scripts/run-b04-tests.sh`, `sh scripts/run-b05-tests.sh`: tutti PASS; ciascun DOM runtime B03/B04/B05 **1 passato/0 saltati** nelle suite isolate, oltre HTTP/SQL/autorizzazioni/RLS/audit/hardening/rollback.
- `python3 scripts/test-ci-runtime.py` **3/3**; `python3 scripts/test-b04-ci.py` e `python3 scripts/test-b05-ci.py` PASS.
- Compose principale `config --quiet`, build/start/health e `sh scripts/smoke.sh` PASS in progetto univoco effimero con credenziali casuali e sola porta web su loopback dinamico; cleanup solo di quel progetto. Nessun comando Compose sui progetti persistenti; nessuna modifica a Tailscale.

## Stato D67 al precedente handoff — storico

19 ottobre 2026, branch `feat/b05-service-part-values`, baseline `0f9cc50fcf685d2e8ffab2686947124fb3189293`. **B05 In corso, non completata.** Le ripetute conferme del proprietario approvano gli stadi D67; G01/D46 risolto esclusivamente per queste politiche numeriche, non certificazione fiscale/legale generale. Il candidato applicativo ha superato la review indipendente locale; l'ambiente manuale privato B05 è attivo e i quattro artefatti manuali hanno superato la review mirata. Restano accettazione manuale del proprietario e CI remota. Nessun commit/push/merge. Vedere `docs/b05-manual-operations.md` e `docs/b05-manual-scenarios.it.md` per accesso, verifiche e limiti dell'ambiente persistente.

### Artefatto attuale

- Rimossa l'uguaglianza ai valori fixture: quantità positiva e prezzo non negativo fino a 6 decimali; sconto fino a 2 decimali, 0–100 inclusi. `10.0`, `10.00` e altre rappresentazioni valide normalizzate in stringhe invarianti. Negativi (incluso `-0`), quantità zero, scale eccedenti, esponenti, virgole, whitespace e valori numerici JSON invece di stringhe rifiutati.
- Netto **di ogni riga** ROUND_HALF_UP6 prima della somma; base per gruppo fiscale (pagante/aliquota nel documento corrente), imposta del gruppo ROUND_HALF_UP6; totale somma basi+imposte. Nessun arrotondamento implicito a 2, denaro serializzato/display a 6 fissi. IVA sintetica 22%, una prestazione/un ricambio, pagante/testata/lavorazione e customizing approvati invariati.
- Schema ed EF: quantità/prezzo `numeric(12,6)`, sconto `numeric(5,2)`, netto `numeric(18,6)`. Sei cifre intere per quantità/prezzo è un **bound tecnico ereditato dalla grammatica/storage anti-overflow, non un massimo commerciale**. Massimo `999999.999999`; moltiplicazione fino a 24 cifre significative e fattore sconto fino a 4, entro `decimal`; al massimo due righe, basi/imposte/totale restano rappresentabili. Non è supporto di quantità/prezzi arbitrariamente grandi. Migrazione ripetibile amplia quantità/sconto/netto esistenti senza ricalcolare snapshot; rollback B05 distruttivo solo nell'ambiente sintetico.
- UI con input per quantità, prezzo, sconto separati per prestazione/ricambio; nessuna conversione floating-point dei valori inviati. Recupero catalogo/riepilogo e retry esistenti mantenuti. Storici letti dai valori salvati, non dal catalogo corrente; nessun listino o ricalcolo automatico.
- Caso 001 originale/JSON preservato: base `164.500000`, imposta `36.190000`, totale `200.690000`. La sola prestazione ora rende `74.250000 / 16.335000 / 90.585000`, distinto dalla politica storica a due decimali.

### RED → GREEN realmente osservato in questa estensione

Tutti i log sotto sono in `/root/.hermes/cache/scratch/` e non nel repository; ogni comando tool è bounded a massimo 600 secondi.

| Tracer | RED | GREEN |
| --- | --- | --- |
| Valori variabili HTTP→SQL→GET, due righe half-micro | `sh scripts/run-b05-tests.sh`, `b05-variable-red.log`, exit 1: riga quantità `1.000000`, prezzo `0.000001`, sconto `50.00` attesa 201, ottenuto 400 | Stesso runner, `b05-variable-green.log`, exit 0: netto per riga `0.000001`, base `0.000002`, imposta `0.000000`, totale `0.000002`, retry `1.0` restituisce lo stesso snapshot |
| Input modificabili UI | Docker Node digest-pinned, `npm test -- --run src/B05.test.tsx`, `b05-ui-variable-red.log`, exit 1: label `Quantità prestazione` assente; 1 fallito/1 passato | Suite UI completa `b05-variable-ui.log`, exit 0: 16 passati, 3 runtime saltati; test verifica payload `2.123456 / 10.000001 / 10.25` |
| DOM/HTTP reale con recupero | La prima esecuzione post-backend è fallita solo perché aspettava ancora `74.25` nel display, che era già `74.250000`; non viene presentata come RED di un algoritmo errato | Runner B05 finale esegue 1/1 DOM con vero login/fetch/POST/GET, modifica entrambi gli input a half-micro e rilettura persistita dopo recupero catalogo |

**Limite test-first:** il RED HTTP dimostra rifiuto dei valori variabili, non isola ogni errore di rounding precedente. I nove casi aritmetici, i nuovi negativi e l'allineamento EF/schema sono copertura finale aggiunta dopo il primo GREEN; non si inventa un RED distinto per ciascuno. Il test riflessivo resta solo controllo supplementare della primitiva, non prova pubblica principale. Le lacune RED storiche sono conservate nella cronologia sotto.

### Comandi effettivamente rieseguiti ed esiti

Directory `/root/enginia360`; output rediretto nei log nominati. Docker SDK `mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24`, Node `node:24.22.0-alpine3.24` (il runner DOM usa il digest fissato nel relativo script).

```sh
# b05-variable-api.log — exit 0, 41 passati, 0 falliti/saltati
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore'
# b05-variable-ui.log — exit 0, 16 passati/3 saltati, tutti i cinque typecheck/build verdi, audit 0 vulnerabilità
docker run --rm -v "$PWD:/source" -w /source/web node:24.22.0-alpine3.24 sh -c 'npm test && npm run build && VITE_B02_TEST_UI=true npm run build && VITE_B03_TEST_UI=true npm run build && VITE_B04_TEST_UI=true npm run build && VITE_B05_TEST_UI=true npm run build && npm audit --audit-level=high'
# b05-variable-nuget.log — exit 0, nessun package vulnerabile API/test con transitivi
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive'
# Ciascuno invocato con comando e timeout propri, nessun timeout aggregato
sh scripts/run-b02-tests.sh # b05-regression-b02.log, exit 0
sh scripts/run-b03-tests.sh # b05-regression-b03.log, exit 0, runtime DOM 1/1
sh scripts/run-b04-tests.sh # b05-regression-b04.log, exit 0, runtime DOM 1/1
sh scripts/run-b05-tests.sh # b05-variable-final.log, exit 0, runtime DOM 1/1
python3 scripts/test-ci-runtime.py # 3/3
python3 scripts/test-b04-ci.py # PASS
python3 scripts/test-b05-ci.py # PASS
```

Runner B05: public HTTP/persist/read half-micro; nove casi con aspettative letterali indipendenti (sotto/sopra mezzo micro, tax-half-micro, sei decimali, sconto frazionario, massimo storage, prezzo zero, sconto 100 e `10.0`); per ciascuno retry e conflitto di payload. Caso aggregazione due basi `0.000002`: base `0.000004`, imposta `0.000001`, totale `0.000005` (somma imposte arrotondate per riga errata sarebbe zero). Caso 001 separato. Negativi verificano settima cifra quantità/prezzo, terza sconto, bound `1000000`, `-0`, zero quantità e input enormi, senza scritture parziali. Restano esercitati auth/tenant/company/site/capability, totali client non fidati, collisione cross-tenant, RLS/pool1, concorrenza pool8, storico dopo master/config change, audit, repeat migration, rollback/reapply, quattro container healthy/hardened senza porte pubblicate. I tre runtime UI saltati nella suite ordinaria sono eseguiti dai rispettivi runner isolati; non è una sessione browser visuale manuale.

Issue #11 aggiornata e riletta: aperta, label blocked rimossa; Project 3 **In corso**. Readback programmatico di tutti e nove B06–B14: issue aperte/blocked e Project Backlog; nessuna autorizzazione downstream. Log JSON `b05-project-after.json`. Cleanup dei runner verificato tramite readback Docker, nessun container effimero numerico residuo; nessuna operazione sui progetti manuali/retained/bootstrap o Tailscale. Nessuna verifica integrale dei contenuti dei database persistenti dichiarata.

### Manifest e limiti correnti

Manifesto dei percorsi alla fine del documento include tutto il working tree B05 ereditato, non solo questo passaggio. Per-file SHA-256 del candidato preparato in scratch per il parent; nessun file runtime/generated incluso. Scope di questo passaggio: `CommercialEndpoints.cs`, `WorkshopDbContext.cs`, `021_commercial_lines.sql`, `CommercialCalculationTests.cs`, `test-b05.py`, `run-b05-tests.sh`, tre file B05 TSX e documenti D67/backlog/validazioni/caso/report. Dipendenze invariate; NuGet/npm audit non è un audit CVE delle immagini.

Limiti: policy ancora denominata `Case001` nel contratto/customizing per compatibilità del profilo sintetico (non vincola più i valori); nessuna selezione IVA generale o documento reale; niente modifica/rimozione di righe salvate, lista storico o ripristino automatico della commessa dopo refresh/nuovo login; Rileggi opera sulla commessa corrente. Nessun backup/restore nuovo, ERP/SdI, stock/costi/margini o CI remota. Il deployment B05 manuale è disponibile soltanto nella tailnet; la rilettura dopo ricreazione PostgreSQL è documentata nelle operazioni manuali e non costituisce prova di backup/ripristino. Review applicativa e review dei quattro artefatti manuali passate; accettazione manuale del proprietario ancora pendente.

## Cronologia precedente — evidenze e limiti storici, non stato corrente

Le sezioni seguenti documentano le sessioni precedenti limitate al caso 001 e il recupero UI. Le loro scale a due decimali, gate allora aperti e stati GitHub sono storici, superati dallo stato D67 sopra.

## Stato e perimetro

19 ottobre 2026, recupero locale su `feat/b05-service-part-values`, baseline
`0f9cc50fcf685d2e8ffab2686947124fb3189293`. Evidenze tecniche locali recuperate e
B05 rieseguita dopo l'introduzione di `RoundMoney`; **non è una dichiarazione di
completamento prodotto o di approvazione G01/D46**. Review indipendente del parent
ancora necessaria. Nessun commit, push, merge, deployment persistente o modifica
agli ambienti manuali effettuato da questo recupero. B06–B14 restano bloccati.

D64/D65 autorizzano soltanto catalogo anagrafico tenant-wide e percorso sintetico
privato della commessa: una prestazione e un ricambio del caso 001, stessa
lavorazione e soggetto unico a carico. Catalog possiede identità/proiezione via
contratti; Workshop possiede righe, snapshot e riepilogo. Nessuna query Workshop
sulle tabelle Catalog. Visibilità non conferisce mutazioni o accesso gestionale ad
altre società; prezzi, stock e customizing non diventano dati comuni.

Il backend accetta soltanto gli esatti valori del caso 001 (incluse rappresentazioni
decimali equivalenti entro scala 3/6; sconti interi 10/5). Non è un motore fiscale
generale: nessun nuovo profilo, prezzo derivato, stock, costo/margine, fattura,
SdI, ERP o dato reale. Stringhe invarianti, grammatica limitata e valori fissi
impediscono overflow nel dominio ammesso. ROUND_HALF_UP per valori non negativi
usa `decimal.Round(..., 2, MidpointRounding.AwayFromZero)`: imponibili 74.25 e
90.25, base 164.50, IVA aggregata 36.19 (non somma IVA per riga 36.20), totale
200.69 EUR. Storico salvato indipendente dal master/configurazione successivi.

## Evidenze RED → GREEN recuperate

Fonti append-only locali (non tutti i payload dei tool sono integrali):

- `/root/.hermes/cache/delegation/live/deleg_5a5c5cfa/task-0.log`
- `/root/.hermes/cache/delegation/live/deleg_3a2d2253/task-0.log`

Orari del transcript in CEST; Vitest stampa anche orari UTC nel container.

| Prova | RED osservato | GREEN osservato |
| --- | --- | --- |
| Selezione CI | 12:21:19, `python3 scripts/test-b05-ci.py`: assertion `CI must invoke isolated B05 acceptance runner` | Rieseguita nel recupero: `PASS B05 CI selects HTTP/DOM/RLS/audit/rollback acceptance` |
| Persistenza prestazione | 12:26:54, `scripts/test-b05.py http://web:8080 service`: atteso 201, ottenuto 404 | 12:30:07 transcript; poi runner completo 13:03:54 e riesecuzione post-rounding |
| Seconda riga/ricambio | 12:30:31, `scripts/test-b05.py http://web:8080 pair`: Part attesa 201, ottenuto 400 | Runner completo: imponibili e IVA aggregata esatti, rilettura persistita |
| DOM/HTTP | 12:32:10 e 12:33:34, un test runtime fallito; dettaglio messaggio abbreviato nel transcript, non ricostruito | 12:34:09, un test passato; nuovamente passato nel runner post-rounding |
| Primitive rounding attuale | 13:04:40, sei casi falliti per `Assert.NotNull`, metodo `RoundMoney` ancora assente | 13:05:59, suite API 41/41; runner B05 post-rounding conferma percorso reale |

**Limite della prova rounding RED:** il test riflessivo dimostra assenza della
primitiva richiesta, non una regressione aritmetica osservata del precedente
endpoint (che già usava arrotondamenti inline). I sei input sono 0.004999, 0.005,
0.005001, 16.335, 19.855, 36.19, attesi 0.00/0.01/0.01/16.34/19.86/36.19.
Non diventano profili HTTP autorizzati. Il precedente `b05-rounding-red.log`
contiene cinque fallimenti di un diverso test poi sostituito: non viene contato
come GREEN dell'attuale contratto. Non è recuperabile da questi transcript una
prova RED comportamentale distinta per ogni singolo controllo negativo introdotto;
non se ne inventa una. L'accettazione finale ne verifica lo stato corrente.

## Comandi ed esiti

Directory di esecuzione `/root/enginia360`; `TMPDIR` è la scratch Hermes.
I comandi dei runner sono quelli eseguiti. Nei precedenti transcript alcune
invocazioni Docker composte risultano abbreviate: le righe seguenti distinguono
il comando ripetibile dall'evidenza realmente conservata, senza fingere una
ricostruzione byte-per-byte delle parti omesse.

| Comando / evidenza | Esito osservato e tempo |
| --- | --- |
| `sh scripts/run-b02-tests.sh` → `b05-resume-b02.log` | PASS finale, fine 13:08:36; 2 righe PASS; integrazione login/context/note, isolamento, baseline ripetuta, hardening |
| `sh scripts/run-b03-tests.sh` → `b05-resume-b03.log` | PASS finale, fine 13:10:56; 18 righe PASS; 7 probe HTTP, B02, RLS, rollback/reapply, audit 128 eventi |
| `sh scripts/run-b04-tests.sh` → `b05-resume-b04.log` | PASS finale, fine 13:14:08; 36 righe PASS; HTTP/DOM, permessi esatti, storico, concorrenza pool 8, RLS, rollback, audit e regressioni B02/B03 |
| `sh scripts/run-b05-tests.sh` → `b05-resume-acceptance.log` | PASS prima del nuovo helper, fine 13:03:54; non sostituisce la riesecuzione sotto |
| `sh scripts/run-b05-tests.sh` → `b05-recovery-post-rounding.log` | EXIT 0, 13:14:19–13:17:27 CEST (188 s); 34 righe PASS; runtime DOM 1/1, 3.01 s totali Vitest |
| `python3 scripts/test-b05-ci.py` | PASS locale nel recupero; selezione CI statica, non esecuzione remota |
| `git diff --check` | Corretto il solo blank EOF del glossario; controllo finale documentato nell'handoff |

I tre runner B02/B03/B04 erano stati avviati alle 13:06:23 in un unico comando
interrotto dal timeout aggregato a 420 s alle 13:13:23. **I log individuali hanno
comunque raggiunto tutti il rispettivo PASS finale**, B04 alle 13:14:08, e le
risorse si sono poi ripulite. Nessuna suite di queste tre era rimasta da rieseguire.
Non si attribuisce un exit code individuale non conservato. Nel recupero è stata
eseguita solo B05 separatamente, con timeout tool 600 s, registrando START/EXIT/END.

Tutti i log `b05-*.log` citati risiedono in `/root/.hermes/cache/scratch/` e sono
locali/effimeri, non allegati al repository. Non contengono risultati CI remoti.

### API, publish e audit già completati dopo RoundMoney

Evidenza preservata: `b05-resume-api.log`, termine 13:05:59, comando Docker SDK
`mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24`. Restore locked, test Release:
**41 passati, 0 falliti, 0 saltati**, durata test 2 s; publish Release completato;
audit NuGet API/test con transitivi: nessun package vulnerabile nelle fonti
consultate. Tempo complessivo tool 47.6 s. Non rieseguiti nel recupero, che non ha
modificato codice applicativo.

Comandi ripetibili delle operazioni documentate:

```sh
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore'
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive'
```

### UI già completata

Evidenza preservata: `b05-resume-ui.log`, termine 13:06:22, tempo tool 22.4 s.
`npm ci`, `npm test`, build normale e quattro build flag B02/B03/B04/B05
(`tsc --noEmit && vite build`), `npm audit --audit-level=high`: **14 test passati,
3 saltati in 6 file (3 passati, 3 saltati)**; zero vulnerabilità. I tre test runtime
saltano senza base HTTP; i runner isolati eseguono i runtime pertinenti, B05 1/1
verificato nel recupero. Non è una prova visuale browser o una sessione manuale.

Comando ripetibile della suite UI conservata:

```sh
docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f sh -c 'npm ci && npm test && npm run build && VITE_B02_TEST_UI=true npm run build && VITE_B03_TEST_UI=true npm run build && VITE_B04_TEST_UI=true npm run build && VITE_B05_TEST_UI=true npm run build && npm audit --audit-level=high'
```

### Copertura finale B05 osservata

- Proiezione tenant: anagrafiche registrate da B selezionabili da A senza accesso
  gestionale a B; tenant estraneo escluso.
- Persistenza, rilettura, retry e snapshot di etichetta/versioni/valori; stesso
  working group e pagante dalla testata, non dal client.
- Input negativi: ID vuoto/estraneo, campi extra e totali client, riferimenti e
  versioni obsoleti, stringhe/scalette, valori fuori profilo e anti-overflow.
- Scope indipendenti create-only, altra società, sede errata, warehouse-only;
  add non implica read. Capability disabilitata blocca anche retry di scrittura,
  non lettura storica autorizzata.
- Collisione UUID cross-tenant controllata; dieci letture alternate su pool 1;
  pool 8 effettivamente configurato, otto retry identici producono un inserimento;
  revisione concorrente in conflitto e refresh esplicito successivo.
- RLS forzata, ruolo non bypass, nessun contesto/contesto estraneo, reset a fine
  transazione, privilegi SELECT/INSERT strettamente necessari.
- Audit tecnico con ID riga committato e deny/conflict, niente payload commerciale
  o segreti; quattro container healthy/nonroot/read-only/hardened e zero porte
  pubblicate, verificati tramite inspect.
- Migrazioni ripetute, rollback ripetuto e reapply; dati B02/B03 e testata B04
  preservati nel database sintetico; pair finale ricalcolata e persistita.

## Migrazioni, rollback e pulizia

`compose.b05-test.yaml` è solo overlay effimero, mai su un progetto persistente.
Il runner usa le basi B02/B03/B04 e monta `/b05` read-only. Ordine B05:
`020_catalog.sql`, `021_commercial_lines.sql`, `900_catalog_fixtures.sql`,
`901_commercial_fixtures.sql`. Fixture esclusivamente sintetiche.
`950_rls_test.sql` verifica runtime SQL; `990_rollback.sql` elimina righe/policy,
indice aggiunto e schema catalogo: **distruttivo per i soli dati B05**. Perdita
righe B05 prevista; non è un rollback sicuro di dati reali. Reapply ricrea schema
e fixture; nessuna disponibilità o recuperabilità di produzione dimostrata.

Il recupero ha verificato la scomparsa dei progetti effimeri B02
`2139058-2139060`, B03 `2146788`, B04 `2156083`, B05 `2171163`.
Il progetto residuo `enginia360-b05-dev` apparteneva alle precedenti prove
sintetiche: rimosso esclusivamente con
`sh /root/.hermes/cache/scratch/b05-dev.sh down --volumes --remove-orphans`.
Readback Docker: nessun container/network/volume con prefisso effimero
`enginia360-b0[2345]-<numero>` o `enginia360-b05-dev`; nessuna prune globale.
Snapshot prima/dopo: 14 container manuali correnti B02/B03/B04 e bootstrap con
identici ID, Created, StartedAt, RestartCount e mount.
Evidenza locale: `b05-recovery-preservation-before.json`. Non è una verifica
integrale dei contenuti dei database; backup/retained resources non toccati.

## Limiti e prossimi gate

- Parent review indipendente, accettazione manuale e G01/D46 restano pendenti:
  la domanda concreta sul confine finito corrente è in documento 09 §7. Non è
  richiesto scegliere ulteriori profili fiscali per questo perimetro.
- Nessuna CI GitHub eseguita su queste modifiche; la sola selezione YAML non
  dimostra CI verde. Nessun push/PR/issue/project update durante il recupero.
- Nessun deployment manuale B05, accesso pubblico, verifica ERP/SdI/fiscale reale,
  backup/restore nuovo, garanzia RPO/RTO o disponibilità dichiarata.
- HTTP/nginx/API/OIDC/PostgreSQL esercitati dal runner isolato; lo smoke del
  bootstrap e la sua immagine corrente non provano questo codice non distribuito.
- SDK e Node di CI sono tag versionati, non tutti digest-pinned; non si sostiene
  un audit immagini completo o una verifica CVE futura.
- Nessun refactor di produzione eseguito nel recupero: conservate le prove verdi;
  sola documentazione e rimozione blank EOF. La review valuterà anche leggibilità
  e limiti del test riflessivo, senza scambiarlo per prova fiscale completa.

## Correzione della review B05 — 19 ottobre 2026

Il difetto riprodotto era: catalogo iniziale 503, rilettura del solo riepilogo
riuscita, pulsanti di aggiunta abilitati senza articoli, click senza POST né alert.
`web/src/B05.test.tsx` monta il componente commerciale reale tramite il suo
contenitore B05 (solo B04 è sostituito con il contesto sintetico; fetch è il
confine stub). I due casi coprono recupero positivo e catalogo ancora 503.

RED eseguito prima del codice: comando
`docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 npm test -- --run src/B05.test.tsx`,
exit 1, **2 falliti**, attese 2 letture catalogo ma osservata 1; DOM del riepilogo
riletto con pulsanti abilitati. Log scratch `b05-review-red.log`.
Stesso comando GREEN: exit 0, **2 passati**, `b05-review-green.log`.
Il recupero ora ricarica catalogo e riepilogo, senza ciclo di retry automatico;
svuota gli articoli prima del tentativo, conserva le aggiunte disabilitate se
fallisce e mostra errore con azione Rileggi/riseleziona. Il guard di aggiunta
mancante mostra errore, non un silent no-op. Successo verificato con POST e
riepilogo autorevole aggiornato; fallimento persistente con zero POST e alert.

Il runtime `B05.runtime.test.tsx` conserva login/contesto/commessa e richieste
HTTP reali: inietta soltanto il primo 503 catalogo, verifica blocco iniziale,
poi Rileggi usa la vera GET catalogo e prosegue con le due vere POST e i totali
persistiti. Non simula il recupero o le risposte del backend.

Verifiche successive effettivamente eseguite, tutte exit 0:

- Comando Docker UI completo riportato sopra: **16 passati, 3 runtime saltati**,
  typecheck/build normale + B02/B03/B04/B05, npm audit **0 vulnerabilità**.
  Log `b05-review-full-ui.log`.
- Docker SDK `10.0.402-alpine3.24`: restore locked, test Release **41/41**,
  publish Release, audit NuGet API/test transitivi senza package vulnerabili.
  Log `b05-review-api.log`. Comando uguale ai due esempi sopra, con
  `dotnet publish src/Enginia360.Api -c Release --no-restore -o /out` tra test e audit.
- `sh scripts/run-b05-tests.sh`: PASS prima e dopo l'aggiunta della fault
  injection runtime; log `b05-review-acceptance.log` e
  `b05-review-acceptance-recovery.log`. Nell'ultima esecuzione runtime DOM/HTTP
  **1/1**, 16 unit UI passati durante build, quattro container healthy/hardened
  senza porte pubblicate; permessi, RLS/pool/concorrenza, audit e rollback/reapply
  superati. Risorse effimere ripulite; readback Docker senza container del runner.
- `python3 scripts/test-b05-ci.py`: PASS selezione statica locale;
  `git diff --check`: PASS. Nessuna CI remota o nuova prova fiscale/legale.

Backlog e stato del caso 001 riconciliati con l'implementazione locale; domanda
residua G01/D46 con grammatica/scale/valori effettivi in documento 09 §7.
Nessuna approvazione dedotta dai test; D42 e D65 non riaperti. Nessun commit,
push, deployment manuale/persistente o mutazione GitHub.

## Manifest esatto delle modifiche locali

Include modifiche ereditate dalle due sessioni precedenti e questo documento;
non include bin/obj/dist/node_modules ignorati né log/credenziali scratch.

```text
.github/workflows/ci.yml
compose.b05-test.yaml
compose.b05-manual.yaml
docs/b05-manual-operations.md
docs/b05-manual-scenarios.it.md
scripts/test-b05-manual.py
database/b05/020_catalog.sql
database/b05/021_commercial_lines.sql
database/b05/900_catalog_fixtures.sql
database/b05/901_commercial_fixtures.sql
database/b05/950_rls_test.sql
database/b05/990_rollback.sql
docs/b05-verification.md
docs/foundation/01-glossary-and-domain-boundaries.md
docs/foundation/02-organization-and-access.md
docs/foundation/03-capabilities-and-data-ownership.md
docs/foundation/05-solution-and-module-boundaries.md
docs/foundation/07-vertical-slice-backlog.md
docs/foundation/09-stakeholder-validation.md
docs/foundation/10-test-case-001.md
scripts/run-b05-tests.sh
scripts/test-b05-audit.py
scripts/test-b05-ci.py
scripts/test-b05.py
src/Enginia360.Api/Enginia360.Api.csproj
src/Enginia360.Api/Program.cs
src/Enginia360.Api/packages.lock.json
src/Modules/Catalog/Enginia360.Catalog.Contracts/Contracts.cs
src/Modules/Catalog/Enginia360.Catalog.Contracts/Enginia360.Catalog.Contracts.csproj
src/Modules/Catalog/Enginia360.Catalog.Contracts/packages.lock.json
src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs
src/Modules/Catalog/Enginia360.Catalog/Enginia360.Catalog.csproj
src/Modules/Catalog/Enginia360.Catalog/packages.lock.json
src/Modules/Workshop/Enginia360.Workshop.Contracts/Contracts.cs
src/Modules/Workshop/Enginia360.Workshop/CommercialEndpoints.cs
src/Modules/Workshop/Enginia360.Workshop/Enginia360.Workshop.csproj
src/Modules/Workshop/Enginia360.Workshop/TechnicalAuditFilter.cs
src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs
src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs
src/Modules/Workshop/Enginia360.Workshop/packages.lock.json
tests/Enginia360.Api.Tests/CommercialCalculationTests.cs
tests/Enginia360.Api.Tests/packages.lock.json
web/Dockerfile
web/src/App.tsx
web/src/B04TestApp.tsx
web/src/B05.runtime.test.tsx
web/src/B05.test.tsx
web/src/B05TestApp.tsx
```
