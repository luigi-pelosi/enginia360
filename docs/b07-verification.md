# B07 — Explicit partial picking verification

## Scope and current status

D70 authorizes sequential B07–B14 autonomous delivery, one WIP, synthetic ephemeral acceptance only. D71 confirms explicitly picking 1 of 2 reserved leaves 1 reserved to pick. Baseline: B06 merged PR #27, `d03b661624b67a9bb41c8ee2d48fde17019246e1`.

B07 is locally implemented and verified; remote PR/CI/merge must be read from the actual delivery before claiming completion. No new persistent manual environment, public deployment, real users/data, purchases or secret access. Existing bootstrap HTTP/Tailscale 443, retained volumes and backups are outside this increment.

## Finite behavior and ownership

- Inventory owns immutable pick facts, reservation provenance and company-only preparation policy. Workshop reservations already supply immutable, authorized header-site/company/warehouse/part references; no direct cross-module table access is introduced.
- `POST /api/v1/inventory/orders/{orderId}/lines/{lineId}/reservations/{reservationId}/picks` requires a nonempty command UUID and explicit positive invariant quantity string (up to six decimals, technical maximum `999999.999999`). Unknown fields, caller-supplied placement/tenant/warehouse and invalid references are rejected.
- A command is bounded by the unpicked quantity of its exact reservation. No autotrim/increase or whole-order block. Command identity lock → reservation lock → fresh cumulative read → local insert/commit. Identical retries return the original snapshot; different quantity/reservation or another tenant's globally colliding pick ID returns controlled conflict.
- Physical stock and total reservation commitment are unchanged. A picked part remains assigned and unavailable. No installation, handover, consumption, release, unused-new return, carcassa, costing or valuation is fabricated.
- The finite company setting has version and `PreparationEnabled`; physical warehouse locations are not site-level customizing overrides. When enabled, origin and preparation placement within the same warehouse are snapshotted. When disabled, placement is null, with no fictional transit. Missing configuration fails closed. Settings are synthetic SQL fixtures, not an authorized production administration editor or a generic logistics system.
- Each explicit command creates one single-line picking-list record identified independently from its physical location. The fact retains reservation/order/job/line/warehouse/article/version, quantity, configuration version, origin/placement, operator and UTC microsecond timestamp. No multi-line list lifecycle is claimed. Existing bounded job ID equals order ID.
- Exact `inventory.picks.read`/`inventory.picks.create` permissions require company + header site + reservation warehouse, independently from reservation grants and Workshop read. New writes require both capabilities; disabled capabilities preserve authorized historical reads. Forced PostgreSQL tenant RLS and immutable application grants supplement action/resource checks.
- Inventory releases its lookup connection before access adapters run: shared pool size one remains functional. Pick timestamps are normalized to PostgreSQL microseconds before returning the initial result, preserving byte-equivalent retry/GET snapshots.

## Test-first evidence

All logs below are local scratch artifacts, not tracked output or fabricated fixtures.

| Evidence | Exact command | Observed outcome |
| --- | --- | --- |
| First HTTP RED | `sh scripts/run-b07-tests.sh` | `b07-red-partial.log`: real authenticated pick 1/2 expected 201, missing route returned 404 before picking production code |
| Persisted snapshot RED | same runner | `b07-concurrent-first.log`: initial response timestamp differed from PostgreSQL GET precision; fixed by microsecond normalization |
| Pool/concurrency RED | same runner | `b07-pool1-red.log`: eight requests could starve the shared pool and hit a non-JSON gateway response; fixed by closing Inventory lookup transaction before access adapters |
| HTTP GREEN | same runner | `b07-concurrent-green.log`: persisted partial, concurrent bound and pool-one round trip passed |
| UI RED | same runner selecting `src/B07.runtime.test.tsx` | `b07-dom-red.log`: real DOM/HTTP reservation succeeded but picking heading/action absent before UI code |
| Lost response recovery RED | same runner | `b07-full-green.log`: committed-response-loss error failed the actionable Italian recovery assertion; network errors are now normalized without changing pending command ID |
| Controlled race RED | same runner with reservation lock temporarily removed | `b07-controlled-race-red.log`: SQL insert barrier admitted eight competing production inserts, accepting eight quantities of 1.5 against reservation 2; sabotage restored immediately, never committed |
| CI selection RED | `python3 scripts/test-b07-ci.py` | missing isolated runner invocation failed before workflow update |

The deterministic race controller runs only after checking exact ephemeral project identity, private network, PostgreSQL tmpfs and absence of retained volumes. It gates production INSERTs with a fixture-only SQL trigger; with the actual lock restored only one insert reaches the barrier, and competing requests conflict after commit. Offline lifecycle tests exercise startup/SQL/observer/readiness/completion/cleanup faults and bounded child/container cleanup. No test trigger enters migrations or production code.

## Executed verification

- `sh scripts/run-b07-tests.sh`: real Keycloak → nginx HTTP → API → PostgreSQL, explicit partial/bounds/q6, normalized retries, eight identical commands, changed quantity/reservation, foreign-tenant command collision, anonymous/foreign membership and wrong provenance, independent common-edit/site-only/warehouse-only/wrong-action grants, read-only/create-only actions, company preparation enabled/disabled, unchanged physical/available, immutable history under disabled capabilities/configuration edits, pool 8 and pool 1, forced RLS/no-context/cross-tenant insert/reset, minimized actual audit, repeated migration/rollback/reapply and four healthy hardened containers without published ports. Each run removes its own containers/network/tmpfs via EXIT trap.
- `timeout 60 python3 scripts/test-b07-picking-race-lifecycle.py`: 22 passed. Existing B06 lifecycle remains selected by CI.
- `python3 scripts/test-ci-runtime.py && python3 scripts/test-b04-ci.py && python3 scripts/test-b05-ci.py && python3 scripts/test-b06-ci.py && python3 scripts/test-b07-ci.py`: passed, including executable hosted-runner scratch initialization checks.
- Pinned SDK container: `dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore`: 43 passed, zero skipped. NuGet vulnerable/transitive audits on API and test projects: none reported by configured sources.
- Pinned Node container: `npm ci --no-audit --no-fund && npm test`: 17 passed; five environment-gated runtime tests deliberately skipped in ordinary mode. The B07 runner separately executes its runtime test with the real endpoint: one passed, zero skipped. B03–B06 runtime tests execute in their respective isolated regression runners. This is React/JSDOM with real fetch and synthetic backend login, not an authenticated real-browser claim.
- `npm run build` for default, B02, B03, B04, B05, B06 and combined B06+B07 private modes: TypeScript/build passed. `npm audit --audit-level=high`: zero vulnerabilities reported. No dependencies or image pins changed.
- Separate bounded `sh scripts/run-b02-tests.sh`, `run-b03-tests.sh`, `run-b04-tests.sh`, `run-b05-tests.sh`, `run-b06-tests.sh`: all passed. Existing bootstrap is not restarted for local smoke; B07's isolated nginx readiness/system/HTML/compiled bundle smoke is selected, and the existing bootstrap smoke runs on the ephemeral GitHub runner.

## UI and recovery limitations

Italian UI displays explicit quantity, picked and remaining-to-pick, reservation origin and picking-list/location distinction. Invalid/uncovered requests do not mutate stock. The runtime test deliberately injects one initial pick-read failure (action disabled until reread), one lost successful POST response (same command retry, once), and verifies that a subsequent equal-sized explicit pick receives a new ID. These are stated faults, not real outages claimed.

The private proof still requires opening the current order and selecting its warehouse. There is no new order/pick-history search or restoration across refresh/new login; database facts remain durable within a running environment, but proof tmpfs is intentionally destroyed. No persistent manual acceptance or real logistics workflow is provided.

## Migration and rollback

Apply `database/b07/040_picking.sql` twice using the existing owner migration convention and explicit `app_user`; no automatic production provisioning. It adds three Inventory tables/policies/index, leaving B06/Workshop data intact. The application can select/insert pick facts, not edit/delete them or change company configuration. The runner applies migration twice, tests RLS, applies `990_rollback.sql` twice, verifies original reservations/orders/lines/tenants remain, reapplies migration/fixtures and repeats the HTTP partial path.

Destructive rollback is only for disposable synthetic acceptance or after a separately approved export/data-loss decision. Operational rollback is disable Inventory writes and redeploy the previous pinned application image while retaining new tables/facts; do not erase confirmed picks or alter retained volumes. No availability, external backup independence or RPO/RTO claim is made. B14 must still execute real synthetic backup/restore and measure its actual endpoints; OPE03–OPE05 operational gates remain before service/pilot.

## Remaining domain boundary

D71 does not decide partial installation/consumption. B08 must resolve the concrete quantity contract before implementing consumption, without reasking reservation/picking, six decimals, company customizing, shared anagraphic visibility or already validated reference-case policies. B08–B14 are authorized, not delivered or acceptance-complete by B07.
