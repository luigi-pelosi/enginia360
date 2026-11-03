# MVP03.b.2a focused backend checkpoint — not delivered

Current status: final corrective validation, not the source-only stage below.
See the [executed-assertion ledger](mvp03b2a-final-validation.md). Historical sections
retain their original chronology and limitations; exact-head remote acceptance
and parent delivery review are still required. WholeMVP03.b remainsfalse.

## Current source continuation — whole #164 implementation, UNVERIFIED

The owner now requires whole-point implementation before **any** validation,
CI or distribution. No new tests, builds, migration execution, audit, typecheck,
smoke, CI, commit, push or PR was run during this continuation. All new source
below is **UNVERIFIED**; old stage35 outputs are historical, not evidence for it.

- Explicit owning transactions now cover Counterparties, Workshop, Inventory,
  Billing, Accounting, Catalog, Vehicles and user-derived Integrations read/recovery.
  They propagate the exact verified tuple and hold the existing777036 and current
  membership/binding rows through commit. No authorization-adapter-only claim.
- Workshop/Inventory RepeatableRead acquires the same boundary before BEGIN,
  hands it to the transaction and releases the session lock in finally; cancellation
  cleanup clears a doubtful pool. SQL-only old snapshots use the private MVCC
  witness and fail closed with40001, not enabled-by-sparse-row absence.
- Unpublished0040 adds restrictive application business RLS, finite guarded
  user-derived SD wrappers (including purchasing, receiving and pricing), private
  original bodies/ACLs, and the independent current selector eligibility fields.
  Existing root/D77/role/company/common-edit/delegated-admin origins remain fenced.
- Accepted Workshop administrative outbox has narrowly persisted-envelope SD read/
  record ports; Inventory purchase/receipt pending/read/record SD ports and technical
  Integrations dispatchers remain accepted-work execution. Missing identity never
  selects those paths from a user operation. Delivery read and manual reconciliation
  are new user-derived operations and use the owning current-access boundary.
- Next Italian access controls use returned exact target/access revision, separate
  delegation labels and self-disable warning; reuse current SSR/private forwarding,
  cookie/JWT/CSRF/no-store and in-page frozen uncertain retries. POST and GET paths
  are deliberately separate; no-JS retains state text while commands are hidden.
- Final-source additions include BusinessMembershipFenceTests (actual Inventory
  reservation/Billing confirmation/Accounting journal race orders), Workshop and
  Counterparties owning races/direct SQL/services, membership SQL origins and
  direct business policies, real OIDC/JWT/SSR/CSRF and identical-retry browser
  acceptance, plus explicit finite mixed/unknown CI selection and a bounded final
  runner. Each singleton-owner class is a separate runtime invocation.
- Positive legacy fixture contexts carry their exact seeded tuple; original
  reset/isolation/cardinality/rollback/refusal assertions are preserved. Published
  migrations0001–0039 were not edited; final runner will verify bytes against base.

The final source manifest/commands and remaining risk are recorded in
`/root/.hermes/evidence/enginia360-mvp03b2a/SOURCE-LATEST.md`.
Source implementation is ready for the parent's final validation phase, **not**
verified/delivered/merge-ready. #164/#142 stay open; wholeMVP03.b runtimeDelivered
remainsfalse; D98 onboarding remains a separate future point. No deployment.

## Historical pre-cadence continuation — stage35, Counterparties owning fence verified

The stage22 account below is retained history. Its Counterparties-specific TODOs
are superseded by [the owning-boundary/classification report](mvp03b2a-counterparty-owning-boundary.md),
not by an all-origin completion claim. Same HEAD/branch; no commit, PR, dispatch,
merge, issue or Project write.

Actual Counterparties user transactions now propagate the exact current verified
principal tuple and hold777036/current binding+membership through effect commit.
Destination/common/supplier/list/detail and the two user-derived service ports
use the explicit owner boundary. App direct business RLS is restrictive (no
missing-identity bypass); four public user SD wrappers acquire777036 before
master-authority and retain private unchanged historical bodies. Offline
owner-only supplier projection is distinct and unchanged; no accepted outbox work
was cancelled or reclassified as a user command.

Demonstrated new behavioral RED25: adapter committed → pause → disable HTTP
committed → resumed destination created persisted row2 instead of1 at pools1/4.
GREEN26 denies with unchanged count1. Reverse order physically observes disable
waiting on the destination effect, then effect commits before disable at both
pools. RED27 reproduces four other actual ingresses at each pool; RED29
reproduces the reversed physical SD lock order for four entries at each pool.
Do not call stage23/24's owning-context connection failures behavioral RED.

Final local evidence (all zero skipped):

| Stage | Outcome |
| --- | --- |
| `34-counterparty-final-green.log` |22 owning/read/SQL/service/SD-lock-order tests, pools1/4, plus common edit/replay/supplier positives and binding replacement regressions |
| `34-membership-backend.log` |2 original current backend theories |
| `34-existing-api.log` |20 existing identity/context/browser-boundary tests |
| `34-direct-boundaries.log` |24 affected module/architecture/authentication-boundary tests |
| `35-membership-sql.log` / `35-original-roles.log` |16 access SQL +15 original role SQL tests |
| `33-original-authority.log` / `33-original-supplier.log` |4 authority +11 supplier regressions with explicit seeded fixture tuple; original assertions retained |
| `34-build.log` |locked restore/build,0 warnings/0 errors |

Stage32 preserved failed old subject-only fixture prerequisites; fixes supply
only each fixture's exact seeded issuer/subject and add missing-tuple refusal
assertions. No production fallback was added. New tests which passed first are
regressions, not retrospective RED. Original stage01–22 chronology gaps remain.

Remaining: actual Workshop/Inventory/Billing/Accounting/Catalog/Vehicle owning
transactions and their direct SQL/SD paths, explicit bounded accepted-work
ports before further RLS, RepeatableRead/current-access race proof, remaining
matrix edges, Next Italian controls and cookie/JWT/SSR/CSRF/no-store/frozen retry,
impact guards and exact-head remote CI/artifacts. No owner policy re-question.
Do not ship0040 or claim #164 complete.

## Historical stage22 checkpoint

Refs #164 / #142. Same `feat/mvp-membership-activation` worktree, base
`2bad821b46b29d5ebb0556461f0eb3b3a61df280`. This is a working local backend
stage, not completion of #164 and not merge-ready. No PR, dispatch or deployment.

## Implemented and exercised

- Unpublished 0040: exact authenticated owner/user-delegate access-state command,
  private immutable audit/replay ledger, independent monotonic revision, closed
  input shape, current actor/target binding checks before replay, minimized
  refusal audit, atomic state/history and commit rollback. No membership,
  binding or grant creation/deletion, mandate renewal or cancellation semantics.
- `POST /api/v1/platform/tenant-roles/{tenantId}/membership-access`, authenticated
  server actor, existing bounded JSON validation, no-store, controlled
  400/403/409/503 and commit-before-success. Existing role workspace includes
  separate `accessEnabled` / `accessRevision` selectors.
- Ordinary, organization-delegate, user-delegate and D77-admin target cases;
  disable/self-disable allowed; delegate enable cannot restore a current
  administrator; owner restores without granting new authority. A D77 operative
  recipient is not an administrative target. Global owner remains independent
  of absent/disabled ordinary membership, without a helper-level business bypass.
- Root/company/common-edit/D77 grant-table restrictive policies, current role
  expansion and both administrative delegate helpers now check access. This is
  **not** every SQL ingress or every business-table policy.
- Replaced prototype lock 777040 with the existing transaction lock 777036;
  no second lock ordering or production interceptor. Exact membership/binding
  rows are held through the calling transaction. SQL physical tests cover
  duplicate UUID, competing revisions, access read/disable in both orders and
  target binding replacement.
- All five company adapters propagate the verified issuer/subject/internal-ID
  tuple. Only the existing explicit browser-disabled `SyntheticLegacy` profile
  retains legacy identity setup; no generic unverified fallback was added.
  Real Counterparties company-list HTTP goes enabled → denied/empty → enabled
  with the same signed bearer at pools 1 and 4.
- Real `OrganizationContextService.CreateNote` owning-effect ordering is proven:
  disable-first blocks the actual HTTP mutation then refuses it; effect-first
  blocks inside a fixture-only BEFORE INSERT trigger while holding the module
  authorization/transaction boundary, then commits the note before disable.
  Pool4 proves the second physical SQL waiter; pool1 proves completion without
  nested-pool deadlock. Persisted notes are counted after commit. This proof is
  **only OrganizationAccess**, not the five adapters' downstream module effects.

## Executed evidence

Durable root: `/root/.hermes/evidence/enginia360-mvp03b2a/`.
Original `01`–`06` evidence and `source/` snapshots are preserved.

| Exact local invocation | Result / raw evidence |
| --- | --- |
| `timeout 300 python3 /root/.hermes/evidence/enginia360-mvp03b2a/stage-runner.py` (stage18 source) | 16 real PostgreSQL tests passed; `18-sql-matrix-green.log` / `18-runner.log` |
| `timeout 300 python3 /root/.hermes/evidence/enginia360-mvp03b2a/role-regression-runner.py` | unchanged original 15 RoleTests passed; `19-original-role-regressions.log` |
| `timeout 420 python3 /root/.hermes/evidence/enginia360-mvp03b2a/api-runner.py` (stage22 source) | 2 signed-bearer SQL/API theories, pools1/4, zero skipped; `22-backend-final-green.log`; existing API identity/context/browser-boundary regressions20 passed in a separate invocation, `22-existing-api-regressions.log` |
| Hardened network-none `dotnet test ... --filter FullyQualifiedName~WorkshopBoundaryTests\|FullyQualifiedName~BillingBoundaryTests\|FullyQualifiedName~AccountingBoundaryTests\|FullyQualifiedName~CounterpartyArchitectureTests\|FullyQualifiedName~InventoryArchitectureTests` | 19 unit/boundary tests passed, zero skipped; exact argv in continuation ledger, `21-direct-consumer-unit.log` |

The API build used the pinned existing SDK and locked restore; no packages added.
SQL and HTTP both force audit insert and deferred-commit failure with fixture-only
triggers, then reread physical state/history. HTTP returns503, no access change
or replay row. Audit UPDATE/DELETE/TRUNCATE are refused. These are executed tests,
not descriptions of a future journey.

## Chronology and incidents (not waived)

- `07-state-behavior-red.log`: actual disable/enable state assertions failed before
  command implementation. Baseline has no ingress, so the state probes catch only
  undefined_function and then assert unchanged physical state. Replay/rollback
  tests at that stage stopped at the missing command: **not distinct behavioral
  RED for conflict, revoked replay or audit rollback**. Passing tests now do not
  retroactively repair that original test-first evidence gap; no merge waiver.
- `09-origin-fences-red.log`: actual disabled user-delegate read and configurable
  role scope bypass assertions failed, then passed with the new fences.
- `12-api-red.log`: both pool theories observed404 before adding the route.
  `14-company-compat-red.log`: both observed an empty company list for a valid
  enabled member before tuple propagation. Matrix/race/effect additions that
  passed first are labeled regressions, not original RED.
- Stage11 had one duplicate synthetic subject fixture failure; corrected before
  the valid two-pool API RED. Stage16 combined two test classes that each own the
  singleton global-authority slot and collided; unchanged original tests and the
  new class pass in separate invocations. No assertions were relaxed.
- Several inherited whole-host cleanup equality assertions failed because an
  unrelated `smartmobile-php85` container started/stopped concurrently. Exact
  task-owned projects were removed; later runs check the protected Enginia360
  baseline separately, not whole-host equality. Protected web/API IDs and start
  times remain unchanged. No actions were taken on the unrelated containers.

## Exact remaining work

Do not ship0040 yet. No all-origin or complete #164 acceptance claim:

1. Complete direct business RLS/security-definer/service coverage using the
   retained actual catalog, especially Counterparties/Supplier, Catalog/Vehicles,
   Workshop, Inventory, Billing/Accounting. D77 command/direct-service consumers
   still need independent full acceptance; SQL grant policies alone are not that.
2. Propagate verified actor and apply an actual module-owned transaction guard to
   those downstream effects; current adapter transactions commit beforehand.
   Exercise both physical orderings and binding deletion/replacement through
   their effect commits. Existing accepted outbox execution must be classified
   and retained, not implicitly cancelled or given an unverified fallback.
3. All five adapters' enabled-runtime direct consumers and explicit historical
   profile need complete affected regression runs. Current positive real HTTP
   company proof covers Counterparties, not all five domains.
4. More finite matrix edges remain: active/expired binding-mismatched authority
   combinations, foreign UUID collision and target hierarchy, maximum revision,
   current actor revocation/binding races at the API boundary.
5. Italian Next selectors/labels, real open-cookie/SSR/JWT journey, frozen retry,
   CSRF, cache isolation, no-JS/layout and artifact evidence remain unimplemented.
6. Impact mapping/guards, remaining builds/audits, exact-head PR and targeted
   `full_architecture=false` remote CI/artifacts remain unexecuted.

Next bounded execution: add a failing real Counterparties business effect test
for disable-first after adapter authorization, then guard that module's owning
transaction with verified tuple +777036 and exact binding lifetime. Classify its
internal/background ports explicitly before extending restrictive business RLS.
No domain question is required. Parent retains merge/issues/Project ownership.
