# MVP03.b.2a — Counterparties owning boundary and port classification

Refs #164 / #142. Local stage35, not all-origin completion or remote acceptance.

## Runtime user-derived paths

`CounterpartiesDbContext.BeginUserOperation` is called explicitly inside the
Counterparties-owned physical transaction. It sets tenant/company and the
handler-verified internal ID/issuer/opaque subject; calls
`organization_access.current_membership_access`; and holds777036 plus the exact
binding/membership row locks through effect commit. A refusal disposes the
transaction before propagating to the route's403 mapping. There is no connection
or SaveChanges interceptor, ambient cross-module transaction or second lock.

| Consumer | Actual owner operation | Classification |
| --- | --- | --- |
| Counterparties list/detail | CounterpartiesModule query transactions | New user query; current tuple required |
| Destination create/list/get/publish | DestinationEndpoints.Begin → BeginUserOperation | New user query/command, not accepted work |
| Common authority/edit-state/edit | CommonEndpoints → same owner boundary | New user operation; existing exact company-read/common-edit + authority/revision/replay remain required |
| Supplier-role/ERP identity read | SupplierEndpoints → same owner boundary | New user operation; no implicit supplier/pricing grants |
| IWorkshopCounterparties.CanUsePayer | WorkshopCounterparties, called by Workshop.Create | New user-derived command dependency, not worker |
| IInvoiceCounterparties.Find | WorkshopCounterparties, sole source caller Billing.Confirm | New user-derived command dependency; tenant UUID alone is not authentication |

Only explicit `SyntheticLegacy` with browser sessions disabled retains its
historical application identity setup. Missing identity in the federated profile
is never a worker/owner bypass. This application-profile condition does **not**
create a database RLS bypass.

## Actual SQL boundaries

- `counterparties.counterparties` and `counterparties.destinations`: new
  **restrictive application-role** policies AND existing tenant/company policies.
  Direct app SQL without a current exact tuple or from a disabled membership is
  denied. This does not give direct SQL additional action grants.
- App-executable user SD entries `common_edit_state`, `edit_common`,
  `set_supplier_role`, `purchase_suppliers`: authenticated wrappers acquire777036
  before the old master-authority lock. Original function bodies are renamed
  private and app EXECUTE revoked. Earlier exact grant/authority/replay checks
  are still executed; the wrapper is not a replacement authorization predicate.
- `read_giobby_vendor_identity`: existing exact company-grant path reaches the
  current-access restrictive grant policy; module caller now propagates tuple.
  No new master-authority-before777036 lock is taken by this function.
- Private `purchase_price_supplier`, `purchase_supplier`, `purchasing_supplier`
  are user-derived SQL helpers, not generic workers. Their observed Catalog /
  Inventory callers must still be accepted independently with owner-module
  transaction/lock-order tests. No new app EXECUTE was granted.
- `establish_giobby_vendor_identity` and `project_external_supplier_role` are
  existing offline nonprivileged database-owner-only verified projection ports,
  **not** authenticated user commands and **not** accepted outbox workers. Their
  ACL/session-owner checks and historical authority/evidence contract are left
  unchanged. App-role-only business restrictions do not invent a missing-identity
  branch inside these owner-only ports. Neither a client flag nor a correlation
  token can enter them.

The app-role RLS rules are deliberately not advertised as SD-owner coverage;
SD user entries are fenced separately. Owner-only and private-helper boundaries
must not be confused with an unrestricted session-role fallback.

## Accepted work outside Counterparties: do not blanket-fence

Actual inspected callers, not yet modified or accepted by this stage:

- WorkshopAdministrativeOutbox.Pending/Read/Record consume already committed
  request/binding/outbox envelopes. Read/Record currently use direct Workshop
  table operations under an envelope tenant. They must remain executable after
  the original operator's membership is suspended; capability pauses remain
  their separate existing rule. New Request/Reconcile routes are user-derived.
- WorkshopBillingSources.Find/Allocate and WorkshopReservationLines.Find are
  called to create new user work, not background authority merely because their
  parameters say `verifiedTenantId`.
- Inventory purchase/receipt pending/read/record dispatch SQL and Integrations
  transport/recovery are accepted-work ports. Classify exact producers/callers
  and enforce bounded persisted-envelope semantics before restrictive table RLS.
  Do not let new user commands choose an `accepted-work` session flag.
- Catalog/Vehicle tenant-only projections are new user-command dependencies;
  they are not automatically trusted technical work.

Do **not** copy the Counterparties ReadCommitted pattern blindly into existing
RepeatableRead snapshots. Workshop has RepeatableRead read/effect transactions;
lock waiting after a transaction snapshot is established needs its own physical
state-change test and correct fresh-access behavior. This is a remaining test /
implementation concern, not a claimed observed failure or an owner-policy gate.

## Executed local acceptance

All logs under `/root/.hermes/evidence/enginia360-mvp03b2a/`.

- `25-counterparty-effect-red.log`: real adapter committed, fixture decorator
  paused outside DB, membership disable HTTP committed, resumed destination
  inserted persisted row2 instead of1 at both pools. Actual behavioral RED.
- `26-counterparty-effect-green.log`: same owning operation now refuses, count1;
  reverse order observes physical disable waiter and effect commit before disable.
- `27-counterparty-ingress-red.log`:8 distinct case executions fail across
  pools1/4 (direct business read, direct INSERT, recipient direct service, read
  after committed adapter). `28-counterparty-ingress-green.log`:10 pass.
- `29-counterparty-lockorder-red.log`:8 physical app SD cases held the
  master-authority lock before waiting on777036. `30-...green.log`:18 pass.
- `34-counterparty-final-green.log`:22 pass, zero skipped, including binding
  replacement after adapter, missing-tuple SQL, enabled common edit/replay,
  supplier-role and persisted immutable history. New assertions that passed
  first are regressions, not retroactive RED.
- `34-membership-backend.log`:2; `34-existing-api.log`:20;
  `34-direct-boundaries.log`:24; `35-membership-sql.log`:16;
  `35-original-roles.log`:15, all passed, zero skipped.
- `32-original-{authority,supplier}.log`: failed legacy fixture prerequisites
  (subject-only SQL), preserved. Test fixture prefixes now explicitly use their
  seeded issuer/subject; missing-tuple refusals are added while **all original
  assertions remain**. `33-original-authority.log`:4;
  `33-original-supplier.log`:11 pass, including offline vendor mapping and
  enabled historical ERP authority/replay/maximum-revision/grant/isolation cases.

Stage23/24 were owning-context fixture setup failures (localhost), not RED.
Original stage01–22 chronology gaps remain disclosed; no TDD waiver, PR or
merge-readiness claim. All39 published migration files remain byte-identical;
only unpublished0040 and its manifest hash were extended.
