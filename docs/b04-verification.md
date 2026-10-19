# B04 — local implementation and acceptance evidence

Current status (19 October 2026): implemented and exercised locally on `feat/b04-direct-workshop-order`, based on `584784812dc8086c3c313e32d2b91adfdfe98bc0`. The owner's «Ok funziona. Procediamo», received after the B04 private manual pass and authorized B02/B03 storage recovery, is positive manual acceptance and authorization to deliver **B04 only**, without another owner confirmation. Core B04 and manual-artifact independent reviews were reported PASS in the parent handoff; final storage/configuration and updated-document review and actual remote CI remain delivery gates. Issue #10 stays open, with Project #3 In verifica during delivery preparation. No B05 authorization, commit, push or merge is implied by a local test result. Earlier implementation-pass statements below are chronology; the later manual provisioning and storage-recovery sections supersede their historical no-deployment/no-maintenance claims.

## Finite implemented boundary / module manifests

| Owner | Provided behavior and data | Dependencies / public boundary |
| --- | --- | --- |
| Workshop | Direct work order, already a customer order; one header company/site, one payer, selected vehicle and distinct holder reference; `workshop.orders` and company-only `workshop.document_types` version history. | Workshop.Contracts access port; Vehicles.Contracts selection port; Counterparties.Contracts payer-validation port. No implementation-to-implementation dependency. No published events. |
| Vehicles | Only a minimal, synthetic, tenant-scoped workshop selection projection; `vehicles.vehicles`. No vehicle CRUD/management HTTP routes. | Vehicles.Contracts returns only ID/label for selection; holder ID is resolved internally for the created order. No ORM in contracts. No published events. |
| Counterparties | Existing B03 data/permissions unchanged in production; new `IWorkshopCounterparties` validates an existing payer through the owner module and existing `counterparties.read` permission. | Workshop never queries Counterparties tables. No new counterparty CRUD. |
| OrganizationAccess / API host | Verifies JWT subject, persisted membership, exact company/site/action scope and workshop capability. Company/site grant is allowed, warehouse-limited grant is not sufficient for this header action. | Host adapter owns organization queries; no organization ORM crosses into Workshop. D59 one-subject/one-tenant invariant retained. |

Configuration is company-scoped, typed and versioned. Missing configuration, a disabled direct-creation type or an older submitted version after a newer version exists prevents **new creation** (409). Missing/disabled workshop activation prevents new use (403). Existing authorized GETs remain available after capability disablement and configuration evolution. The order stores the relevant configuration version through a module-local composite foreign key. This is not universal document freezing, a workflow engine or an editor/provisioning API.

The client never chooses the tenant or holder. Extra `tenantId`/`vehicleHolderId` properties do not change verified server values. D63 selection works from A for a vehicle registered through B while the same identity cannot read B’s counterparty management endpoint. Vehicle list exposes only ID/label, not another company’s private data or the holder’s anagraphic fields. Payer selection is independent and not overwritten by vehicle selection.

Creation has a client-generated stable command/resource ID. Identical retries return the same resource; different content with the same ID conflicts. `INSERT ... ON CONFLICT DO NOTHING` and a tenant-scoped reread handle simultaneous retries and cross-tenant ID collisions without leaking the other row or returning a database 500. The runtime runner verifies concurrency both with pool size 1 and pool size 8.

Excluded: B05+, rows, prices, parts, fiscal logic, quotations/appointments as required predecessors, warranty/splits, universal workflow/freeze, vehicle/party administration, real identities/data and all manual deployment.

## RED → GREEN evidence

The following were run serially as tracer bullets, with production changes after the corresponding failure. Supplemental authorization, RLS, architecture and recovery assertions were then added to reinforce the path; their immediate passes are not claimed as independent RED evidence.

For exact HTTP probe commands below, this is the common command prefix used during development (the ephemeral project has since been removed):

```sh
P='docker run --rm --network enginia360-b04-dev_backend -v /root/enginia360:/source:ro -w /source python:3.14.0-alpine3.22 python3 scripts/test-b04.py http://web:8080'
# A table entry “$P direct_order” expands to this complete invocation.
```

All commands were run from `/root/enginia360`. The repository mount was originally spelled `-v "$PWD:/source:ro"`, with that working directory. The final runner pins the same probe image by digest.

| Tracer / command | Observed RED | Observed GREEN |
| --- | --- | --- |
| `python3 scripts/test-b04-ci.py` | `AssertionError: CI must invoke isolated B04 acceptance runner` (exit 1) | `PASS B04 CI selects HTTP/DOM/RLS/audit/rollback acceptance` (exit 0) |
| `$P direct_order` | `('tenant-wide vehicle selector expected 200', 404, None)` (exit 1) | `PASS direct_order: tenant-wide minimal selector, persisted direct customer order, distinct payer/holder, config version, reread/retry/conflict` |
| `$P invalid_command_id` | Expected controlled 400, got **201**: EF generated a new GUID from an empty ID. | `PASS invalid_command_id: empty command identifier rejected before persistence` (400) |
| `$P context_and_types` | `('workshop contexts expected 200', 404, None)` | `PASS context_and_types: server-authorized contexts and latest company type version` |
| DOM command below | `Unable to find a label with the text of: Utente sintetico` (bootstrap rendered instead of B04) | `1 passed (1)` using real private HTTP. A separate fixture-name mismatch (`Alfa Nord` vs existing `Alfa Sede Nord`) was corrected, not counted as feature RED. |
| `$P superseded_configuration` after loading `/b04/910_superseded_configuration.sql` | Expected 409, got **201** with configurationVersion 1 after version 2 disabled creation. | `PASS superseded_configuration: stale version cannot bypass current direct-creation policy` |
| Audit command below | `AssertionError: Workshop audit events must exist` | Minimized success/denial events present. The JSON logger’s actual `State` shape was corrected in the checker (no extra `Message` field), not counted as feature RED. |
| `$P command_id_collision` | Expected 409 for a valid beta command colliding with alpha’s ID, got **500**. | `PASS command_id_collision: cross-tenant identifier collision controlled, no disclosure` |
| `docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 npm test -- --run src/B04.test.tsx` | **1 failed, 2 passed**; missing empty-authorized-context explanation. | **3 passed**. |
| `python3 scripts/test-b04-ci.py` after strengthening the guard | `AssertionError: B04 runner must execute B04_POOL_SIZE=8` | Pass; runner recreates only its isolated API with pool size 8, verifies the effective configuration, executes the concurrency probe, then restores size 1. |
| Audit command after requiring a committed resource ID | `AssertionError: Successful creation audit must identify the committed resource` | Final isolated runner audit: **12 events**, success/denial, nonempty committed resource ID for creation, fixed minimized field set. |

Exact DOM invocation used for RED and GREEN:

```sh
docker run --rm --network enginia360-b04-dev_backend \
  -e VITE_B04_HTTP_BASE=http://web:8080 \
  -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 \
  npm test -- --run src/B04.runtime.test.tsx
```

Exact development audit pipeline used for RED and GREEN:

```sh
docker compose --env-file "$TMPDIR/b04-dev.env" -p enginia360-b04-dev \
  -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml \
  logs --no-log-prefix api | python3 scripts/test-b04-audit.py
```

The isolated runner builds the application before applying B03 and B04 migrations. It never points at a manual project. A build-time regression initially exposed existing UI tests inheriting the new B04 build flag; their test setup now explicitly selects B02/B03 rather than allowing inherited B04 to replace their UI. A supplemental WebApplicationFactory fixture also needed `UseSetting` rather than late app configuration to enable conditional module registration; the real Compose path was already passing. Neither setup failure is presented as behavior RED.

## Final executable verification

```sh
python3 scripts/test-ci-runtime.py
python3 scripts/test-b04-ci.py
sh -n scripts/run-b04-tests.sh
sh scripts/run-b04-tests.sh
sh scripts/run-b02-tests.sh
sh scripts/run-b03-tests.sh
```

Actual results:

- CI runtime prerequisites: **3 tests passed**; B04 selection guard passed.
- B04 runner: **19 B04 HTTP probe invocations** (11 named functions): direct_order 4, invalid_command_id 1, context_and_types 1, isolation_and_references 1, concurrent_retry 2, command_id_collision 1, prepare_history 1, denied_scope 4, denied_read 1, superseded_configuration 1, historical_read 2. These are scenario probes containing multiple assertions, not 19 xUnit tests.
- Real B04 JSDOM/HTTP test: **1 passed, 0 skipped** in the isolated runner. It authenticates through the synthetic Keycloak-backed login and uses real fetch through nginx/API/PostgreSQL. It is not a full-browser-session claim.
- B04 SQL: forced RLS on all three tables; app role is non-superuser/non-bypass; no-context denial; tenant-scoped reads; cross-tenant INSERT denied; transaction-local context resets; configuration/vehicle/update privileges absent as intended.
- Same-tenant authorization tested independently: missing membership, valid membership with missing workshop action, wrong company/site, read-only, different-site-only, warehouse-only, and create without read. The exact header site grant is sufficient. Reads by guessed IDs are denied even with valid same-tenant membership lacking the exact read action.
- Pool isolation: ten alternating real alpha/beta order/vehicle queries over one physical database PID. Separate 8-way identical simultaneous creation tested with pool size 8; exactly one 201 and seven 200, one persisted resource. A further development-only 5 repetitions at pool size 8 also passed; CI includes the pool-size-8 scenario itself.
- Repeat migration, double destructive rollback, B02/B03 data survival checks, B03 fixture restoration, and B04 reapply/direct creation all passed.
- Final bounded audit checker: **12 events** after the runner’s deliberate API recreations. These are the retained final-container events, not a claim of complete durable audit retention across replacement.
- Four healthy hardened containers, nonroot/read-only, capabilities dropped, no privilege escalation, bounded CPU/memory/PIDs/logs, **no published ports**.
- B04 runner also executes the B02 HTTP regression and all seven B03 HTTP behaviors before narrowing its synthetic permissions; B03 shared identity is rechecked after B04 rollback.
- Separate full B02 runner passed: integration, repeat baseline, identity uniqueness/coherence rejection and hardening.
- Separate full B03 runner passed: seven HTTP behaviors, three independent insufficient-publication scopes, B02 regression, **1 real DOM/HTTP test passed**, SQL RLS, bounded audit (**128 events** in that run), hardening, rollback/reapply.

Exact SDK test command:

```sh
docker run --rm -v "$PWD:/source" -w /source \
  mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c \
  'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore'
```

Final output: **Failed 0, Passed 34, Skipped 0, Total 34**. Includes enabled-route authentication and module/contract boundary checks. Release API publish in the actual Compose build also passed.

Exact UI/build/audit command:

```sh
docker run --rm -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24 sh -c \
  'npm ci --no-audit --no-fund && npm test && npm run build && VITE_B02_TEST_UI=true npm run build && VITE_B03_TEST_UI=true npm run build && VITE_B04_TEST_UI=true npm run build && npm audit --audit-level=high'
```

Output: **14 passed, 2 skipped (16)** in ordinary UI tests. The two skipped tests are B03/B04 runtime tests requiring their HTTP-base variables; each was explicitly run and passed in its isolated runner. All four UI variants built/typechecked. `npm audit`: **0 vulnerabilities**. After source-only formatting, ordinary tests and default/B04 builds were rerun and passed; B04 Docker build reran UI tests/typecheck/build as well.

NuGet audit commands (same SDK container/workdir):

```sh
dotnet list src/Enginia360.Api package --vulnerable --include-transitive
dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive
```

Both returned **no vulnerable packages given the current sources**. No new external runtime dependency was added; new project lockfiles and host/test project-reference locks were intentionally regenerated, then locked restore verified. Formatting used pinned Prettier 3.6.2 as a transient tool, not a project dependency. `git diff --check` and a changed-file scan for shell injection, eval and unsafe deserialization passed.

Local raw logs are under `$TMPDIR`: `b04-acceptance-final.log`, `b04-api-final.log`, `b04-ui-final.log`, `b04-ui-postformat.log`, `b04-b02-regression.log`, `b04-b03-regression.log`. They are local scratch evidence, not committed build artifacts or remote CI evidence.

## Migration, rollback, UI recovery and limits

- Run only `sh scripts/run-b04-tests.sh` for this acceptance proof. It creates unique ephemeral credentials/project, mounts B03/B04 SQL read-only, applies exact-baseline migrations twice and removes its containers/networks/volume/env file on exit. Manual projects are not used.
- `010_workshop.sql` owns only Vehicles/Workshop schema data; no foreign-module query is introduced in Workshop. Cross-module references are validated via owner contracts before creating the local order. There is deliberately no global cross-module transaction. B04 exposes no reference deletion/editor; introducing such mutation later requires an explicit consistency design, not an invented B04 CRUD policy.
- SQL is a repeatable proof baseline, not a production schema-convergence/versioning framework. IF NOT EXISTS does not repair an arbitrary drifted database. Configuration defaults to direct creation disabled; only explicit synthetic company fixtures enable it.
- `990_rollback.sql` is **destructive and only for the isolated synthetic proof**: drops Workshop/Vehicles schemas, removes workshop grants/capability fixtures and the extra synthetic holder; reapply B03 synthetic fixtures to restore grants intentionally narrowed by the D63 test. The runner proves double rollback and reapply while retaining the two B02 tenants and the two B03 common identities.
- UI retries use the same command ID while fields remain unchanged, including after POST succeeds but GET fails. Selecting another context clears dependent state. Error text explains retry/reselection. Payer is never set by the vehicle handler.
- UI rereads the saved order after POST; it does **not** implement a history/list/reopen-by-ID control or restore the selection after refresh/new login. Data remains persisted in an environment that is retained, but this acceptance runner intentionally destroys its volume. A changed/disabled configuration can reject a new POST/retry; authorized direct GET of the original ID remains available.
- Audit is bounded operational logging, not a durable/compliance journal. Creation records the committed technical resource ID and identity/action/outcome, never token, payer/holder details, names or addresses. Configuration is synthetic SQL fixture data; no production configuration-administration audit surface is claimed.
- No production authentication/provider adoption, availability guarantee, external ERP, real-browser login or remote CI result is claimed. Manual provisioning and human acceptance were subsequently completed within the separate private follow-up below. Final storage/document review, reviewed commit/PR and actual remote CI remain separate delivery gates. B05–B14 remain unauthorized and blocked.

## Private manual follow-up

A separate persistent B04-only environment was provisioned for human acceptance; see `docs/b04-manual-operations.md` for actual evidence, the PostgreSQL 18 named-volume correction and limitations. The earlier implementation-only statements describe the isolated implementation pass, not the subsequent authorized manual provisioning. B02/B03 services and data were unchanged during that provisioning, then separately received owner-authorized storage-only maintenance on 19 October 2026. The owner's «Ok funziona. Procediamo» is positive B04 manual acceptance and delivery authorization. Core and manual independent PASS verdicts are inherited from the parent handoff, not fabricated as new reviews by the delivery-preparation agent. The four B02/B03 storage changes and the latest documentation require final independent review before any commit/push/merge.

Additional manual-pass manifest:

```text
compose.b04-manual.yaml
scripts/test-b04-manual.py
docs/b04-manual-operations.md
docs/b04-manual-scenarios.it.md
```

## File manifest

The original implementation manifest is recorded below, followed by the separately authorized manual and storage-maintenance additions. The D62/D63 edits to foundation documents 01/03/05 were inherited from the prior documentation pass and preserved. Document 07 additionally receives the implementation status. No generated bin/obj/node_modules/dist files, caches, runtime environment files or protected recovery archives are deliverables.

```text
.github/workflows/ci.yml
compose.b04-test.yaml
database/b04/010_workshop.sql
database/b04/900_synthetic_fixtures.sql
database/b04/910_superseded_configuration.sql
database/b04/950_rls_test.sql
database/b04/990_rollback.sql
docs/b04-verification.md
docs/foundation/01-glossary-and-domain-boundaries.md
docs/foundation/03-capabilities-and-data-ownership.md
docs/foundation/05-solution-and-module-boundaries.md
docs/foundation/07-vertical-slice-backlog.md
scripts/run-b04-tests.sh
scripts/test-b04-audit.py
scripts/test-b04-ci.py
scripts/test-b04.py
src/Enginia360.Api/Enginia360.Api.csproj
src/Enginia360.Api/OrganizationAccess/WorkshopAccessAdapter.cs
src/Enginia360.Api/Program.cs
src/Enginia360.Api/packages.lock.json
src/Modules/Counterparties/Enginia360.Counterparties.Contracts/Contracts.cs
src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs
src/Modules/Counterparties/Enginia360.Counterparties/WorkshopCounterparties.cs
src/Modules/Vehicles/Enginia360.Vehicles.Contracts/Contracts.cs
src/Modules/Vehicles/Enginia360.Vehicles.Contracts/Enginia360.Vehicles.Contracts.csproj
src/Modules/Vehicles/Enginia360.Vehicles.Contracts/packages.lock.json
src/Modules/Vehicles/Enginia360.Vehicles/Enginia360.Vehicles.csproj
src/Modules/Vehicles/Enginia360.Vehicles/VehiclesModule.cs
src/Modules/Vehicles/Enginia360.Vehicles/packages.lock.json
src/Modules/Workshop/Enginia360.Workshop.Contracts/Contracts.cs
src/Modules/Workshop/Enginia360.Workshop.Contracts/Enginia360.Workshop.Contracts.csproj
src/Modules/Workshop/Enginia360.Workshop.Contracts/packages.lock.json
src/Modules/Workshop/Enginia360.Workshop/Enginia360.Workshop.csproj
src/Modules/Workshop/Enginia360.Workshop/TechnicalAuditFilter.cs
src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs
src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs
src/Modules/Workshop/Enginia360.Workshop/packages.lock.json
tests/Enginia360.Api.Tests/WorkshopBoundaryTests.cs
tests/Enginia360.Api.Tests/packages.lock.json
web/Dockerfile
web/src/App.test.tsx
web/src/App.tsx
web/src/B03.test.tsx
web/src/B04.runtime.test.tsx
web/src/B04.test.tsx
web/src/B04TestApp.tsx
```

Separate authorized maintenance manifest (not omitted from delivery):

```text
compose.b02-manual.yaml
compose.b03-manual.yaml
docs/b02-manual-testing.md
docs/b03-manual-operations.md
```

## Final delivery preparation — 19 October 2026

The intended publication is two explicit reviewed commits in one B04 delivery PR: a storage-only maintenance commit containing exactly the four paths immediately above, and a B04 implementation/manual/documentation commit containing the original and manual manifests. No maintenance command is rerun by committing these files. Current overlays must be published because they describe the already verified live storage; excluding them would leave Git unable to reproduce the retained environment. Both commits remain blocked until their current contents are independently reviewed.

Recovery evidence was read from `/root/.local/share/enginia360-storage-remediation/20261019/continuation/final-result.json`: 14 healthy running containers, B02/B03/B04 table counts/row hashes/schema equal, ten unrelated containers unchanged, B02 unchanged during B03, Tailscale exactly unchanged, all original/failed-attempt volumes retained. The actual B02/B03 source clusters were in original **named** volumes, as proven by read-only mounts despite the image's `data -> .` symlink. Do not repeat the superseded anonymous-source diagnosis. The final external storage volumes are `enginia360-b02-manual_postgres_storage_v4` and `enginia360-b03-manual_postgres_storage_v5`, mounted at `/var/lib/postgresql`. Recovery proofs are one-time same-host, not scheduled/off-host backups or availability/RPO/RTO guarantees. Detailed checksums, restoration evidence, measured bounds and rollback remain in the B02/B03 manuals; archives and credentials stay outside Git.

Fresh final commands/results from `/root/enginia360`:

- `python3 scripts/test-ci-runtime.py`: 3 passed; `python3 scripts/test-b04-ci.py`: PASS; `sh -n scripts/run-b04-tests.sh` and `git diff --check`: PASS.
- Pinned SDK locked restore and Release API tests: **34 passed, 0 failed, 0 skipped**. Both transitive NuGet audits reported no vulnerable packages given the current sources.
- Pinned Node clean install, ordinary UI tests: **14 passed, 2 skipped**. Default/B02/B03/B04 typecheck/builds passed; npm audit **0 vulnerabilities**. Each otherwise-skipped runtime test was separately executed by the actual isolated runner and passed.
- `sh scripts/run-b02-tests.sh`: PASS full B02 regression and hardening.
- `sh scripts/run-b03-tests.sh`: PASS full seven-behavior HTTP/scoped-publication/RLS/audit/rollback path, including **1 real DOM/HTTP test passed** and 128 bounded audit events.
- `sh scripts/run-b04-tests.sh`: PASS full HTTP/authorization/configuration/forced-RLS/pool-1/pool-8/concurrency/history/rollback/reapply/hardening path, including **1 real DOM/HTTP test passed**, 12 retained final-container minimized audit events, and B02/B03 HTTP regression. No persistent manual project was used.
- Scratch verifier `python3 "$TMPDIR/b04-delivery-config-main.py"`: all seven actual main/test/manual Compose combinations validated with fresh ephemeral secrets, never with private runtime files. Parsed B02/B03 manual mounts exactly matched the new external parent mounts; inherited child mount absent. Main Compose was built/started under a unique isolated project with only its web port overridden to a random loopback port. The unchanged canonical `scripts/smoke.sh` passed and all four containers were healthy. The ephemeral stack/volume/env were removed; a full before/after persistent-container ID/start/image/restart/health snapshot was exactly equal.

Raw final logs: `$TMPDIR/b04-delivery-api.log`, `b04-delivery-ui.log`, `b04-delivery-b02.log`, `b04-delivery-b03.log`, `b04-delivery-runtime.log`, `b04-delivery-config-main.log` and `b04-delivery-main-build.log`. These are local evidence, not remote CI. An initial mistaken invocation of the persistent manual probe without its mandatory base URL failed before making HTTP requests; it is not a failed application scenario. It also prevented the chained runtime runner from starting, so the isolated B04 runner was then explicitly run separately and passed. The generated Python import cache was removed, not staged. No persistent manual acceptance probe was rerun, because it intentionally writes synthetic orders and delivery preparation requires no further persistent mutations.

The inherited independent core/manual PASS gates are not extended silently to later storage changes or these updated documents. Parent final review must cover the exact four maintenance files plus the current `docs/b04-manual-operations.md` and `docs/b04-verification.md`; exact SHA-256 manifest is emitted outside Git for review. Only after that PASS may reviewed source/config/docs be staged, commits pushed, a PR opened and actual CI observed on its exact head before merge/issue closure. Positive manual acceptance does not waive technical gates. B05–B14 remain open, blocked and Backlog; no further increment or private project/runtime/Tailscale/database change is authorized here.
