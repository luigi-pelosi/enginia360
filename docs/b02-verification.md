# B02 verification and operations

B02 is the only authorized increment. It uses synthetic identities/data and a development-only login proxy enabled only in the private test Compose network. The browser never reaches Keycloak directly and identity headers are never trusted. The synthetic UI is also build-time gated: only `compose.b02-test.yaml` sets `VITE_B02_TEST_UI=true`; the default Docker build and main Compose render the safe bootstrap/status page and call only `/api/v1/system/status`.

## Implemented acceptance

- PostgreSQL composite foreign keys enforce tenant → legal entity → site → warehouse coherence for membership scopes and notes; mixed same-tenant and cross-tenant IDs are rejected.
- B02 deliberately permits exactly one tenant membership per identity subject. `IdentitySubject` is globally unique in SQL and EF for this increment; tenant switching and multi-tenant identity membership remain unauthorized and unimplemented.
- EF alternate keys, composite relationships and the membership-scope unique index match the SQL schema, including `Permission`.
- The Italian UI authenticates through `/api/v1/development/login`, lists only server-authorized contexts, shows disabled contexts without allowing selection, and creates then retrieves a persisted note.
- The default production frontend contains no login/password controls; the synthetic B02 controls are enabled only in the isolated test image build.
- Note input is trimmed; empty/whitespace-only or over-200-character messages return 400.
- `GET /api/v1/organization/context-notes/{id}` requires the authenticated identity’s membership plus `organization-context.read` for the note’s exact tenant/legal entity/site/warehouse. The query checks server-owned membership/scope rows; payloads and identity/tenant headers do not authorize reads. Forced tenant RLS remains a separate defense. Cross-tenant, same-tenant out-of-scope, and missing-membership reads return 404.
- JWT validation explicitly reads `Authentication:ValidIssuer`, validates signature/issuer/audience/lifetime with zero clock skew, and has executable negative tests for wrong signature, issuer, audience, expired and not-yet-valid tokens.
- The application DB role is non-superuser. RLS is forced on every B02 table. Each operation uses a transaction-local `app.identity_subject` and `app.tenant_id`; pool size is exactly one. Alternating identities demonstrably reuse one backend PID without leaking identity context.
- The application DB role has read-only access to organization reference/access tables and only `SELECT, INSERT` on `context_notes`.
- Main PostgreSQL and Keycloak use `restart: unless-stopped`. Both Compose files require runtime-injected DB owner/application credentials; the test runner creates a mode-0600 ephemeral env file and removes it.

Disabled visibility semantics: a context with read scope remains visible with `capabilityEnabled=false` so the operator can understand why it cannot be used; note creation is disabled in the UI and rejected with 403 by the API. Historical notes remain readable when the identity retains the exact read scope, even if the capability is disabled.

## Current RED → GREEN evidence (2026-10-16)

### Read authorization regression

Before changing `GetNote`, added a synthetic Alfa membership with no read scope and authenticated it through the real Keycloak/login path. Ran:

```sh
sh scripts/run-b02-tests.sh
```

**Behavioral RED, exit 1:** all four isolated services were healthy; note creation and the authorized GET succeeded. The new denial assertion expected 404 but received **200 with the persisted Alfa note** for subject `dddddddd-0000-0000-0000-000000000001`. Local raw log: `/root/.hermes/cache/scratch/b02-read-red.log` (ephemeral evidence, not a repository artifact).

Minimal fix: filter the note by authenticated subject membership and exact stored read scope in the database query. No capability-enabled filter is added to reads: disabled historical contexts preserve authorized readability. RLS policies and transaction-local session handling remain intact.

**GREEN, exit 0:** reran the same full runner after the fix. Authorized current and disabled historical reads passed; no-read Alfa membership, missing membership, cross-tenant identity, forged identity/tenant headers, and manipulated same-tenant out-of-scope note ID were denied with 404. Existing creation/validation/disabled-write/JWT/pool-isolation checks passed, followed by baseline reapplication, relational/identity uniqueness rejection, privilege and container-hardening assertions. Cleanup trap removed the isolated stack/volume/env file. The post-format final rerun also exited 0 (`/root/.hermes/cache/scratch/b02-read-final.log`); exact-project Docker container, volume and network queries returned no resources, and the ephemeral env file was absent. `git diff --check` exited 0.

### EF metadata alignment

Added `Note_message_check_matches_database_baseline` before changing the model:

```sh
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode >/dev/null && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore --nologo --filter Note_message_check_matches_database_baseline'
```

**RED, exit 1:** `Assert.Contains` found an empty CHECK-constraint collection (not a fixture error). Added the same `length(btrim("Message")) BETWEEN 1 AND 200` CHECK to EF table metadata, without modifying the existing SQL constraint. Full API suite GREEN below includes this test. The disabled database-session route test now uses its real GET method (login remains POST).

### Final verification commands

```sh
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore --nologo && dotnet build src/Enginia360.Api -c Release --no-restore --nologo && dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive'
```

Exit 0: **22 API tests passed**, Release build **0 warnings / 0 errors**, neither API nor test project reported vulnerable packages from current NuGet sources.

```sh
docker run --rm -v "$PWD:/source" -w /source/web node:24.22.0-alpine3.24 sh -c 'npm ci --no-audit --no-fund && npm test && npm run build && VITE_B02_TEST_UI=true npm run build && npm audit --audit-level=high'
```

Exit 0: **5 UI tests passed**, both default and private-B02 TypeScript/Vite builds passed, npm audit **0 vulnerabilities**.

Formatting only: CSharpier 1.3.0 for changed C#, Prettier 3.6.2 for changed TSX, Black 26.10.0 for Python (including runner’s inline hardening check), pgFormatter 5.8 for SQL. No formatter dependency was added to project manifests/locks.

Earlier invalid JWT timestamp boundaries and malformed seed hierarchy failures were **fixture/setup errors, not behavioral RED**. An initial final-check attempt used `--no-restore` in a fresh SDK container without its NuGet cache and failed with missing assembly files; rerunning locked restore in that same container resolved it. No production/public Compose stack was started, and remote CI/image scanning remain unverified.

## Delivery re-verification (2026-10-17)

The owner accepted the private manual path, including the refresh/display limitation described in `docs/b02-manual-testing.md`. This is B02-only acceptance; no administration increment or B03 authorization is inferred.

Current reruns, all exit 0:

- The exact API command above: **22 passed**, Release **0 warnings / 0 errors**, API and test NuGet audits reported no vulnerable packages.
- The exact UI command above: **5 passed**, both TypeScript/Vite build modes succeeded, npm audit **0 vulnerabilities**.
- `sh scripts/run-b02-tests.sh`: all four services healthy, real Keycloak login and persisted-note isolation/validation/JWT/pool tests passed; baseline reapplication, identifier coherence, uniqueness, least-privilege and container hardening passed. Cleanup removed only its unique test project, networks, volume and ephemeral env file.
- Main `compose.yaml` also passed a fresh isolated build/start and `scripts/smoke.sh`, using generated credentials, a unique project and a loopback-only temporary port override. Disabled login and database-session routes returned 404. Its isolated resources were removed; the existing bootstrap/manual projects were not restarted or reconfigured.
- `python3 scripts/test-ci-runtime.py`: **1 passed**. Before the workflow fix, the same test failed because required `B02_DB_*` runtime values were absent, so the existing remote Compose step would not parse. The workflow now generates independently random owner/application passwords in `$GITHUB_ENV`, masks both, and executes the B02 integration, UI/build/audit and NuGet audit gates in addition to the existing bootstrap smoke. The regression executes the actual initialization block and validates main Compose configuration without starting services.
- `git diff --check` passed. Candidate source/config/docs paths contained no generated build output or local runtime file. The static scan found only runtime-generated/environment-derived assignments and synthetic test tokens; no private key or recognizable GitHub/AWS credential. The intentionally disposable Keycloak fixture passwords are not production credentials.
- Private manual status remained available and its database-session diagnostic route returned 404. Existing manual containers remained healthy without restart; neither Tailscale Serve nor existing volumes were changed.

Local evidence logs are ephemeral under `/root/.hermes/cache/scratch/b02-delivery-{api,ui,compose,main}.log`. **Independent review of the latest workflow/manual overlay and remote CI remain delivery gates; no commit, PR, merge or issue closure is implied by these local checks.**

## Runtime configuration

Create a gitignored runtime env file containing all required values (do not commit it):

```text
B02_DB_NAME=...
B02_DB_USER=...
B02_DB_PASSWORD=...
B02_DB_APP_USER=...
B02_DB_APP_PASSWORD=...
```

Then run `docker compose --env-file <runtime-file> up -d --build`. Only main `web` publishes host port 80. API, PostgreSQL and Keycloak remain private. The development login endpoint is not enabled in main Compose.

## Migration, rollback and limitations

`database/001_b02_organization_access.sql` is a repeatable B02 baseline, not a production migration framework. `CREATE TABLE IF NOT EXISTS` does not reconcile arbitrary pre-existing table definitions. The explicit unique index does converge a compatible prior B02 schema to the single-tenant-per-identity rule, but deliberately fails if duplicate identity subjects already exist; such data requires reviewed manual remediation rather than an automatic tenant-selection decision. The two shell initializers create/grant the non-superuser application role from runtime environment values without printing them.

Destructive synthetic-test rollback:

```sh
docker compose -f compose.b02-test.yaml down --volumes --remove-orphans
```

Back up any volume that must be retained before removal. Main rollback is to stop the B02 services and restore the prior reviewed images/configuration; dropping `organization_access` destroys B02 data and must be explicit.

Limitations: exactly one tenant membership per identity subject, no tenant switching or multi-tenant identity semantics, synthetic direct-grant Keycloak users, HTTP-only private service traffic, Keycloak development file storage, single host, no real provisioning, no production login, no production migration framework or automatic convergence for incompatible existing schemas/data, no HA/backup automation, no remote CI evidence, and no B03+ domain behavior.
