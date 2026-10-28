# R00.a — fixture-free runtime migration foundation

## Contract and ownership

Bounded delivery under D74–D76, tracked by **#50**, a subissue of **R00 #40**. This foundation is not completion of the R00 browser/session contract. GitHub #50 records the actual delivery head, PR and remote CI readbacks; this document records the executable contract and local evidence, not a cached live CI status.

Only the new runtime path provisions this schema. Historical B02–B14 SQL, fixture runners, `postgres.Dockerfile`, `compose.yaml`, bootstrap/nginx/Tailscale and retained storage are unchanged. No changes to `Program.cs`, default health endpoints, application authentication, UI dependencies or domain commands. No identity binding is introduced in R00.a.

### Explicit schema source order

Every target below is under `database/runtime/migrations/`; `database/runtime/manifest.json` allowlists its exact path, contiguous ID and SHA-256 of its bytes. Sources are Enginia360's existing schema, not SmartData. Source revision: `72b43007dbecb33db7bac35edc3963098014243b`.

| New file | Source files under `database/` |
| --- | --- |
| `0001_organization_access.sql` | DDL/indexes/RLS from `001_b02_organization_access.sql`; technical grants from `002_grant_app_role.sh` |
| `0002_company_permissions.sql` | `b03/003_company_permissions.sql` |
| `0003_counterparties.sql` | `b03/004_counterparties.sql`, `b03/005_grants.sql` |
| `0004_destinations.sql` | `b03/006_destinations.sql`, `b03/007_publication.sql`, `b03/008_common_edit.sql` |
| `0005_workshop.sql` | `b04/010_workshop.sql` |
| `0006_catalog_lines.sql` | `b05/020_catalog.sql`, `b05/021_commercial_lines.sql` |
| `0007_inventory.sql` | `b06/030_inventory.sql` |
| `0008_picking.sql` | `b07/040_picking.sql` |
| `0009_installation.sql` | `b08/050_installation.sql` |
| `0010_carcass.sql` | `b09/060_carcass.sql` |
| `0011_administration.sql` | `b10/070_administration.sql`, with infrastructure-owned role creation removed |
| `0012_continuity.sql` | `b11/080_continuity.sql` |
| `0013_billing.sql` | `b12/090_billing.sql` |
| `0014_accounting.sql` | `b13/100_accounting.sql` |

The new copies remove outer transaction wrappers. All root B02 business INSERTs are removed, including those after its RLS policies. No 9xx fixture/test/rollback file is selected. The resulting **46 business tables are all empty** after initialization, including tenants, memberships, permissions, capability activations, document policies/types, stock, invoice profiles and chart accounts. That is successful startup, not a request to invent an administrator or fiscal setup.

Existing slice structures/constraints remain structures/constraints: e.g. the commercial-line kind uniqueness and technical 22% tax case are not broadened into a general fiscal implementation. Billing and Accounting remain present; no reference chart or new fiscal policy is invented. R01 owns authorized business setup, after its precise granting/revocation policy is resolved. Authority D26/D65/D76 remains a setup gate before dependent business writes, not a reason to block this empty foundation.

### Technical file ownership

- `scripts/apply-runtime-migrations.py`: manifest validation and the only owner of migration transactions/history/serialization. Python stdlib plus `psql`, no new ORM/driver dependency.
- `database/runtime/bootstrap-roles.sh`, `scripts/validate-runtime-config.py`: infrastructure-only role bootstrap, separate from domain setup and from the web process.
- `postgres.runtime.Dockerfile`: new PostgreSQL init path, never COPYs historical SQL.
- `migrator.runtime.Dockerfile`: one-shot migration/test executable and the new allowlisted baseline only.
- `compose.r00a-test.yaml`, `scripts/run-r00a-tests.{sh,py}`: unique ephemeral DB/migrator lifecycle, hardening and cleanup. No caller-supplied project or database target is accepted by the lifecycle runner.
- `scripts/test-r00-migrations.py`: offline contracts and opt-in real PostgreSQL cases; `scripts/test-r00a-ci.py`: CI-selection/mutation and cleanup-target guards; `scripts/test-r00a-lifecycle.py`: actual Docker failure/TERM cleanup probes.
- `runtime-pool-test.Dockerfile`, `tests/Enginia360.Api.Tests/RuntimeMigrationPoolTests.cs`: real Npgsql pools, using existing locked dependencies, no application behavior change.
- `.github/workflows/ci.yml`: dedicated `runtime-migrations` job in addition to every existing verification step. Runtime suite is bounded to 600 seconds and lifecycle probes to 180 seconds independently.

## Engine behavior

The manifest is authoritative, not a directory glob. Reject empty/malformed manifests, noncontiguous or duplicate IDs, paths not exactly `migrations/<id>.sql`, symlinks, checksum changes, transaction wrappers and psql metacommands. Quoted function bodies/literals are distinguished from top-level transaction commands. Migration SQL is reviewed executable repository code, **not an untrusted-SQL sandbox**.

A single `psql -X` connection does all of the following:

1. Acquire the session advisory lock for `hashtextextended('enginia360.runtime_migrations.v1',0)` in the target database. Wait is bounded by `lock_timeout=10s`; each statement is bounded to 30s and the controller to 120s.
2. Verify the database-owner migrator is non-superuser/NOBYPASSRLS/NOCREATEROLE/NOCREATEDB; verify the application role is a distinct LOGIN/NOINHERIT/nonprivileged role with **no role memberships**; verify the outbox exception is still NOLOGIN, BYPASSRLS and otherwise nonprivileged.
3. If no ledger exists, refuse every nonempty user schema/public relation/function/type or non-default extension, rather than adopting legacy data. Create the technical ledger only on an empty database.
4. After acquiring the lock, re-read the complete ledger `runtime_migrations.applied(id,checksum,applied_at)`. It must be exactly a checksum-matching manifest prefix: unknown future rows, gaps and damaged checksums fail before new units.
5. For each missing unit, execute **BEGIN → DDL/RLS/grants → ledger INSERT → COMMIT** on that same connection. Failure rolls back both the current unit and its ledger row; later units do not run. Earlier committed units remain the resume point.

Second apply does not rewrite timestamps or execute a unit. Concurrent runners both succeed, apply once and inspect history after the lock; an in-unit PostgreSQL probe confirms the applying backend holds that advisory lock. SIGINT/SIGTERM cancels and closes psql. Linux parent-death protection kills the psql child even if the controller receives SIGKILL: quiet DDL must not consume buffered COMMIT after its parent dies. Backend disconnect detection can wait for the bounded current statement; no instant cluster-wide cancellation guarantee is claimed. The runtime controller therefore requires Linux, as do the pinned container images.

The application has SELECT-only access to the technical ledger, no ledger writes or schema ownership. The infrastructure superuser remains an operational privilege, never a web credential. Failed migrations give a generic secret-free diagnostic; the operator inspects the manifest, role configuration and last committed ledger row on the isolated target. Do not dump credential-bearing environment/configuration into logs to diagnose a refusal.

## Roles, secrets and isolation

The new infrastructure entrypoint creates database owner and app roles from required runtime environment, never hardcoded credentials. Names must be distinct, valid non-reserved identifiers; database name is validated; owner/app/infrastructure passwords must be distinct 48–128-character lowercase hex values. The runner generates fresh random values and writes a mode-0600 file inside a mode-0700 scratch directory, removed on every ordinary exit and handled signal. Migration child environment is minimized; passwords are never CLI arguments or output. Secret-bearing infrastructure SQL disables statement/error-statement logging in that bootstrap session.

`enginia360_outbox_reader` is created only by infrastructure. The migration owner can SET that role solely as a trusted infrastructure/migration principal; the application has no membership and cannot impersonate it. The role owns only the two fixed-search-path, envelope-only SECURITY DEFINER discovery functions, with PUBLIC execution revoked. Column-only reads on outbox/outcomes are preserved; no request-payload read grant is added. Schema CREATE needed for ownership transfer is granted transiently inside the relevant migration transaction and then revoked.

Both DB and migrator run UID/GID 70, read-only root, dropped capabilities, no privilege escalation, bounded memory/CPU/PIDs/logs, and no published ports. PostgreSQL 18 PGDATA is explicitly `/var/lib/postgresql/18/docker`, inside tmpfs mounted at the correct **parent `/var/lib/postgresql`**; inspection verifies no inherited anonymous volume. The internal network and tmpfs mean this is deliberately disposable. Stopping PostgreSQL discards this test store; restart reinitializes and reapplies the same manifest. It is not a persistent deployment or an availability claim.

The base PostgreSQL and SDK images retain the repository's exact tag+digest pins. Python is installed as exact Alpine package `python3=3.12.16-r0` (bumped from `3.12.15-r0`, which Alpine v3.22 withdrew from its repository; the only pin site is guarded offline by `scripts/test-r00a-ci.py`). Rollback: revert the pin commit, but the old revision is no longer installable, so rollback means pinning the then-current Alpine revision instead; package availability was actually checked before building. No application dependency/lockfile changed. NuGet/npm audits below are not an image-CVE or production security certification.

## Repeatable verification

From the repository root, with Docker available and `TMPDIR` pointing to private scratch:

```sh
python3 scripts/test-r00a-ci.py
python3 scripts/test-r00-migrations.py ManifestTests BaselineTests ConfigurationTests
timeout 600 sh scripts/run-r00a-tests.sh
timeout 180 python3 scripts/test-r00a-lifecycle.py
```

The canonical runner starts healthy PostgreSQL, completes the real one-shot migrator twice, executes the opt-in PostgreSQL suite and Npgsql pool tests, stops/restarts the same ephemeral project, reapplies the manifest, checks logs for generated secrets and tears down only exact project/configuration-labelled resources. Default offline invocation reports PostgreSQL tests skipped; the CI runner **sets `R00_MIGRATION_TESTS=1`**. The dedicated pool invocation supplies its runtime-only connections and executes both pool sizes, with zero skips. CI selection tests inspect executable Python constants, not shell comments, and mutate missing runner/guard/opt-in selection.

### RED → GREEN evidence

Commands used for the initial PostgreSQL tracer cycles were `timeout 180 sh /root/.hermes/cache/scratch/r00a-cycle.sh <test-name>` against the same new Compose files. The durable canonical runner above supersedes that local harness; no manual environment is required.

| Behavioral assertion | Observed RED before the corresponding implementation | GREEN evidence |
| --- | --- | --- |
| Ordered explicit verified manifest | expected unit bytes versus empty result; malformed/checksum/duplicate/gap/path cases accepted | offline manifest tests |
| Fixture-free complete baseline | 0 versus 14 units | 14 units, all 46 tables empty, forced RLS |
| Real first boot | `migration ledger absent` on healthy PostgreSQL, not connection refused | first/second-boot ledger/timestamp checks |
| Unit atomicity/resume | failed unit leaked DDL | failed unit and row absent, next unit absent, resume commits exactly once |
| Serialized runners and untracked refusal | runner return codes `[0,1]`; legacy schema silently adopted, including a user `pgx_legacy` namespace incorrectly matched by a SQL LIKE wildcard | two successes/one application; untracked DB unchanged; literal system-prefix filtering and bounded held-lock refusal |
| Checksum/history validation | manifest drift silently adopted | manifest/ledger drift rejected; three independent future/gap/damaged-ledger tests also deliberately fail when the prefix guard is disabled in a scratch mutant |
| App role and outbox exception | BYPASS app accepted; app membership in infrastructure accepted; interactive BYPASS outbox accepted | unsafe roles refused before ledger creation, app SET ROLE/CREATE ROLE/ledger writes rejected |
| Cancellation | terminated runner left its connection alive | TERM cancels/closes and rolls back |
| Uncatchable kill | quiet DO-block DDL committed after parent SIGKILL | parent-death guard prevents commit, prior unit retained |
| Runtime configuration | reserved name, duplicate secret, weak infrastructure secret and invalid DB name accepted | required validated runtime inputs, generic error messages |
| CI/lifecycle selection | runtime runner absent; failure-cleanup probes absent | dedicated CI job plus real failure/TERM cleanup |

Current local result: **22 Python tests passed** (4 offline, 18 PostgreSQL, including a test which confirms all three history mutants fail); **2 actual Npgsql pool cases passed, 0 skipped**. Pool=1 reuses the same backend PID while alternating tenants; pool=12 holds 12 distinct backends concurrently. Commit, rollback and cancelled query all clear tenant context. Synthetic rows occur only in these explicit acceptance phases, not migrations.

Logical `pg_dump`/`pg_restore` to a **distinct disposable database on the same isolated server** preserves the complete ledger, checksum prefix and subsequent no-op apply. This assumes the same already-bootstrapped technical roles; it is not a cross-host/global-role restore proof. Success, controlled migration failure and SIGTERM cleanup probes preserve pre-existing container/network/volume inventories. The original two bootstrap containers and 25 retained volumes remain outside the target.

### Other executed regressions and limits

- API integration: 69 passed, one opt-in pool theory skipped without a supplied runtime DB. The dedicated runtime runner separately executes its two inline pool cases with zero skips. Locked restore/build succeeds in `runtime-pool-test.Dockerfile`.
- UI: 57 passed, 12 explicit HTTP-runtime tests skipped in the ordinary unit invocation; default build/typecheck and `build:ui01` succeed; npm audit reports zero vulnerabilities. The first contended invocation exceeded the existing five-second UI01 100-row deadline; the unchanged suite passed on an uncontended repeat. No timeout was raised and no UI test was removed. Existing Ant Design bundler `use client` warnings remain outside this change.
- NuGet: API and test project vulnerability queries with transitive dependencies report no vulnerable packages. An initial read-only-image invocation attempted implicit restore and failed; `--no-restore` against the already locked/restored build succeeded. No audit warning was suppressed. The SDK prints its existing workload-verification notice under the nonroot test user; no workload update is required by these tests.
- Historical runners executed **independently**, each bounded to 600 seconds: B02 passed real HTTP/JWT/context/RLS/hardening; B13 passed internal Billing/Accounting, real HTTP DOM, immutable journal/RLS/audit/recovery; B14 passed joint internal/external destinations, real HTTP DOM, diagnostics, destroyed-tmpfs backup/restore/readback and guarded rollback. B14 measured backup 0.610s and recovery 38.476s on that synthetic run, not contractual RPO/RTO. The complete unchanged historical CI sequence remains selected remotely.
- CI configuration guards: the complete existing guard command passed. It initially caught the new job's direct `runner.temp` environment expression; the job now exports `$RUNNER_TEMP` through `$GITHUB_ENV`, following the repository's existing tested scratch convention. No old guard was weakened.
- No standalone protected bootstrap Compose start, public smoke target, real identity, ERP call, business data, purchase or go-live occurred. Existing API health behavior is unchanged. New API/UI/identity readiness and browser HTTP smoke belong to R00.b, not a false success claim from this DB-only foundation.

## Rollback and concrete R00.b handoff

Rollback this disposable proof by its generated runner cleanup, then recreate from the manifest. Never point it at retained B02 volumes and never stamp a ledger onto a presumed-compatible nonempty schema. Existing `990_rollback.sql` files are not runtime downgrades. For any later data-bearing migration, define its backup/restore and compatibility procedure explicitly; do not delete immutable business facts as a rollback shortcut.

R00.b starts from these exact paths and adds, test-first:

1. A separately versioned issuer+opaque-sub → internal UUID binding migration, with no default identity or membership and no alteration of published R00.a checksums. The implementation handoff's proposed bridge is not silently included here.
2. Opt-in expected-schema readiness when API integration is added; keep default health compatibility. Wire healthy DB → successful migrator → API → web in a **new isolated** runtime stack, not the protected main Compose.
3. The full real-browser OIDC code/PKCE/session/CSRF/logout/revocation contract, TLS trust and identity/schema/pooling/error/recovery acceptance described in the R00 implementation handoff. No provider-production approval or R01 granting policy is inferred.
4. Update synthetic legacy test plumbing explicitly only when that identity contract changes it; preserve all Billing/Accounting, scope and historical-read cases. UI01.b integration follows the verified runtime contract, not invented CRUD.

R00 #40 remains open for that evidence. D74–D76, the single tenant-wide shared-master authority, separate company extensions/prices/stock and internal Billing/Accounting remain unchanged. No new business policy question is needed to deliver this foundation.
