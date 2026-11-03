# MVP03.a execution checkpoint

Candidate implementation complete locally; remote acceptance pending. Sole writer: `feat/mvp-organization-delegation`, baseline `095abca4656bffa626e259f7f4aa8237d6afdf26`. Parent alone merges or changes issues/Project. Refs #158; Refs #142.

## Delivered candidate paths

- Append-only 0038: exact existing binding/membership delegation, finite owner selector, immutable atomic command/audit, optimistic revisions, serialized revocation and scoped workspace discovery; original 0001–0037 bytes conserved. No app DML privilege or RLS bypass.
- Existing API controller: bounded JSON parser reused for grant/revoke; owner-only selector, scoped administrative discovery and existing finite structure commands. Delegation and owner authority remain distinct.
- Existing Italian Next workspace: selector grant/revoke, delegate own hierarchy, six company/site/warehouse create/rename paths; no global tenant controls for delegates. Actual OIDC SSR, noJS reads and live-page-only exact frozen retry. No durable forced-reload recovery claimed.
- Existing fail-closed impact map extended for 0038 and finite mixed frontend/organization candidate; unrelated producer consumers and unknown-path refusals retained. Inventory: 38 migrations / 85 CREATE definitions / 9 schemas, all UNDECIDED.

## Original evidence chronology

All paths below are under `/root/.hermes/cache/scratch/mvp03a-evidence/`; logs retain real exits. Missing-route/function RED establishes that path's absence, not every later negative/concurrency assertion independently.

| Behavior | Original RED | Executed GREEN |
| --- | --- | --- |
| Finite 0038 impact mapping | `02-impact-red.log` | `03-impact-green.log` |
| Existing membership selector SQL | `04-selector-red.log` | `05-selector-green.log` |
| Grant/revoke/revision/replay command SQL | `06-grant-red.log` | `07-grant-green.log` |
| Delegate own-tenant read | `08-delegate-red.log` | read assertions pass in `09-delegate-command-red.log` |
| Delegate finite mutation/replay | `09-delegate-command-red.log` | `10-delegate-green.log` |
| Delegation UUID cannot become structure UUID | `11-collision-red.log` | SQL suite in `12-sql-green-http-selector-red.log` |
| Real OIDC HTTP selector | `12-sql-green-http-selector-red.log` | selector passes in `13-http-selector-green-grant-red.log` |
| Real OIDC HTTP grant/revoke route | `13-http-selector-green-grant-red.log` | `14-http-grant-green.log` |
| Scoped workspace discovery SQL | `15-workspace-red.log` | SQL passes in `16-workspace-green-http-red.log` |
| Scoped discovery HTTP | `16-workspace-green-http-red.log` | `25-api-green-pool4.log`, `27-api-green-pool1.log` |
| Owner/delegate rendered UI controls | `17-ui-red.log` | `18-ui-green.log` (locked tests/build/typecheck/audit) |
| Real Next delegated SSR | `19-next-delegate-red.log` | `20-next-green-pool4.log`, expanded `26-next-green-pool1.log` |
| Finite mixed-slice scope, not old ERP runtime | `28-bounded-slice-red.log` | `30-impact-offline-green.log` |

Passing-first supplementary SQL security/concurrency/rollback/binding-loss/exhaustion tests are regressions, not retrospective RED. Full 35-test SQL suite completed in `21-api-green-pool4.log` (later bearer-fixture failure does not make that whole execution pass), and again in successful `27-api-green-pool1.log`. Actual API OIDC + independently signed Keycloak bearer, concurrent replay, post-edit historical snapshots, revocation with live session/token, no-business-context, context-pool isolation and SQL audit readback pass in `25-api-green-pool4.log` and `27-api-green-pool1.log`.

Next pool1 expanded proof retains delegated noJS HTML, mobile screenshot and six persisted delegate commands in `next-pool1/`; original pool4 proof in `next-pool4/`. Owner grant lost accepted response → CSRF refusal → accepted replay with failed reread → exact-byte successful retry is real HTTP, with one SQL grant history row despite four attempts. Existing owner create/rename/frozen retry/layout/logout checks remain executed. `30-impact-offline-green.log` executes the workflow's 24 actual impact guard commands.

## Disclosed incidents, not behavioral RED or success

- Original executor launch timed out with no-consent/no-retry; no executor ran. Owner later answered exactly «Autorizzo» for normal gated resumption. Contract preserves both facts.
- `01-impact-red.log`: initial test key-access error, corrected before actual assertion RED.
- A five-minute orchestration cell timed out during log12, while the bounded runner continued and completed all34 SQL assertions before the intended HTTP404; completion and owned cleanup were reread. No duplicate runner launched.
- Bearer proof initially lacked fixture Authority metadata and a subject-bearing client scope. Logs21–24 are failed fixture/investigation executions, not product RED. Final ephemeral fixture uses explicit metadata, API audience and basic subject scope; actual signature validation remains intact. Password-grant client exists only in the private synthetic realm, not the product/browser client.
- Log22 cleanup failed closed on a two-config label mismatch. The exact five owned ephemeral containers and their one project network were inspected and removed by identity; no project volumes existed. Subsequent runner uses one explicit generated configuration, preserving the cleanup guard, and successful cleanup readbacks. Protected services untouched.
- A local SDK test probe log31 exited during restore without a diagnostic beyond workload verification. It is not test/build/audit acceptance. API production image builds succeeded in actual runtime runners; remote affected API tests/audits still required.
- Generic web extraction backend could not fetch pages; primary-source search and GitHub advisory APIs used instead. No dependency upgrade or blanket vulnerability clearance inferred.

## Remaining delivery

Commit/push and PR, exact-head automatic affected jobs, exact-head targeted dispatch `full_architecture=false`, download and inspect every selected artifact and executed step, fresh head/tree and clean-worktree readback. No operational readiness claim, deployment, real identity/data, secrets committed, provider/ERP writes, persistent environment or protected service/storage changes. #142 remains open for distinct user administration/assignability policy.
