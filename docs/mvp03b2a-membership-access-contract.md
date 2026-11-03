# MVP03.b.2a — Existing-member tenant access

Refs #164 / #142. Base: `2bad821b46b29d5ebb0556461f0eb3b3a61df280`.
Status: whole-point source implementation complete; **final validation in progress / not delivered**.
[Current executed-assertion ledger](mvp03b2a-final-validation.md) supersedes earlier source-only checkpoints. No pending-principal,
invitation, first binding, new membership, provider configuration or deployment.
D97/D98 historical policy/runtime flags remain unchanged.

## State and authority are separate

Membership access is an enabled/disabled state and a monotonic independent
revision, not `active` on an organization delegation or user-administration
delegation. Existing memberships start enabled at access revision zero without
rewriting membership rows, bindings or any grant. A state transition increments
only access revision. Disabling preserves all grant rows, expiry/revocation,
binding, membership and business/audit history. Enabling never creates, edits,
renews or restores a delegation/grant; only still-current operative grants may
become usable again. Revoked/expired grants remain ineffective.

The global platform authority is neither a membership nor a business-data
permission. Its verified bootstrap/revocation path remains available independently
of tenant membership access, including when the owner's ordinary membership is
disabled or absent. Global authority permits explicit tenant-bound administration,
not ordinary business reads/writes without an enabled authorized membership.

## Actor / target / action matrix

Every actor is the current exact authenticated internal identity + issuer + opaque
subject. Every target is an existing exact membership + tenant + internal identity
+ current binding digest, not email, label or a browser-asserted tenant.

| Current actor | Target | Read selector / disable | Enable |
| --- | --- | --- | --- |
| Verified current global owner, with or without enabled membership | Existing membership in the explicitly selected tenant, including own ordinary membership | Allowed | Allowed, without changing any authority row |
| Enabled exact current user-administration delegate | Other existing ordinary membership in the actor's own tenant | Allowed | Allowed if this does not reactivate an administrative mandate/delegation |
| Enabled exact current user-administration delegate | Existing privileged membership in own tenant | Allowed to read/disable; privileged status is not a blanket target ban | Allowed when administrative authority is already inactive/expired/revoked or binding-mismatched; otherwise refused, requiring explicit owner action rather than implicit administrator restoration |
| Enabled exact current user-administration delegate | Own membership | Allowed to read and disable; UI warns this removes own tenant administration access | No self-enable/self-grant; once disabled the actor has no delegate authority |
| Organization-only delegate, operative D77 grant recipient, role/grant-only or ordinary member | Any membership | Refused | Refused |
| Disabled/revoked/binding-mismatched former user delegate | Any membership, including replay of an earlier command | Refused | Refused |
| User delegate | Another tenant, nonexistent membership, mismatched hierarchy or replaced target binding | Same minimized forbidden response | Same minimized forbidden response |
| Anonymous/unassigned federated subject | Any membership | No application authority | No application authority |

For the enable restriction, administrative authority means a current exact-bound
organization delegation (0038), user delegation (0039), or unrevoked/unexpired
D77 `delegation_mandates.AdminMembershipId` mandate. An ordinary D77 delegated
operative scope or role assignment is not administrative nomination. An active
global owner remains globally authoritative independently: an ordinary membership
state command must never grant, revoke or impersonate that authority. The matrix
is the minimum technical reading preventing implicit subdelegation, not a new
owner-only ceiling on ordinary user administration or a ban on privileged targets.

## Finite transport and persistence

Use authenticated no-store workspace selectors; owners choose a tenant from the
existing server directory, delegates discover only their own tenant. Routine UI
uses returned member selectors, not manually entered UUIDs. Existing metadata has
no approved human display-name directory: display a stable, distinguishable
internal member label without disclosing issuer/subject/email. Show **Accesso al
tenant: abilitato/disabilitato** separately from **Delega gestione utenti** and
**Delega struttura**; delegation status is not the access state.

The state command carries exactly `commandId`, `membershipId`,
`internalIdentityId`, `bindingHash`, `expectedRevision`, `enabled`; target tenant
is the explicit route parameter. Actor comes only from verified server context.
Canonical lowercase nonzero UUIDs, 64 lowercase hex binding hash, JSON boolean,
and integer revision 0..2147483646 are required; unknown/duplicate keys, unsafe
Unicode/NUL, oversized/chunked excess bodies and numeric exponent/overflow are
controlled 400. Stale state or same UUID/different payload is 409. Missing or
foreign targets reveal no existence. Current actor, delegation, target binding
and enable restrictions are evaluated **before replay lookup**. Identical replay
returns its historical snapshot, never reapplies state; authoritative reread may
show a later disable/revision. A historical enable cannot undo that later disable.

Audit is immutable, minimized and atomic with every access mutation: exact actor
binding digest, selected authority and revision, tenant/member, command UUID,
request, before/after enabled state and revision, timestamp/outcome. No tokens,
issuer, opaque subject, email or user-entered personal data. Audit insert and
deferred-commit failure must roll back both state and command history. Denial
audit omits requested tenant/member/payload and must not expose a foreign target.

The UI freezes the exact command while its outcome is uncertain. Retry uses the
same UUID and byte-identical payload; controlled refusal requires a fresh
selector read before a new command. Describe this as retry on the still-open
page, not durable recovery across navigation/restart unless persistence is
actually implemented and tested. No browser-generated issuer/subject proof.

## Enforcement and final transaction acceptance (source implemented, UNVERIFIED)

Current source status and historical pre-cadence evidence are recorded in the
[focused backend checkpoint](mvp03b2a-backend-progress.md); the requirements below
are requirements for final execution, not a verified assertion about every consumer.

A common current-access fence must dominate root membership scopes, D77 operative
scopes/mandates, configurable role scopes, company/common-edit permissions and
both administrative delegations. SQL/RLS enforcement cannot be another permissive
OR policy. Authenticated open SSR, cookie and bearer requests must re-evaluate
current state, not rely on session claims. The owner has no business bypass.

Authorization adapters currently commit before the owning effect transaction.
A resolver check, adapter check, HTTP-only middleware or holding a lock only in
the adapter cannot prove commit ordering. The owning effect transaction and
state mutation must share a documented database lock boundary and exact binding
row lifetime. Test disable-first and effect-first using independent physical
connections and real lock barriers; verify effect/audit after commit. Account for
existing advisory lock 777036 and cross-module nested calls/pool1 before choosing
a lock order; do not introduce a second lock in reversed order. Bindings must be
held/rechecked through the owning effect commit, including replacement/deletion.

Independently exercise direct SQL table policies, invoker views, security-definer
function entrypoints and direct application services, not just HTTP. Technical
background processing of already accepted outbox work is distinct from a new
user command: disabling must not implicitly cancel it or authorize new user work.
Do not solve worker compatibility by allowing every missing-identity SQL context.
The accepted Workshop read may expose a persisted unbound historical request
with null binding only for the existing controlled reconciliation hold; it must
not dispatch, backfill a binding or record an outcome without an exact binding.
Keep the explicit `SyntheticLegacy` / browser-disabled profile regression and
its original assertions; fixture-only verified identity additions must retain the
original downstream failure/authorization fence.

The changed-consumer inventory and exact runtime database catalog must determine
CI selection. Initial discovery includes OrganizationAccess root/D77/roles,
Counterparties/common edit/supplier, Workshop, Catalog/pricing, Vehicles,
Inventory/picking/returns/purchasing/receiving, Billing and Accounting. Internal
outbox/Integrations ports must be classified, not automatically canceled or
silently exempted. A broad shared security fence makes those direct consumers
relevant even though a full unrelated ERP connector stack is not the default.

## Required proof before delivery

- Actual owner/delegate enable → access → disable → denial → re-enable journey,
  with no new/renewed grants and separate UI labels/selectors.
- Root, D77, role, company/common-edit and delegated administration origins;
  direct SQL/RLS/functions/services, real OIDC cookie and signed JWT, current SSR.
- Both physical race orders, pool1 and pool4, replay after disable/revocation,
  collision/stale/unknown input, hierarchy isolation and binding replacement.
- Audit immutability and rollback at insert and deferred commit for every mutation;
  CSRF, no-store/cache isolation, frozen in-page uncertainty.
- Preserve all 39 published migration byte hashes; 0040 is unused at the base.
  Append-only migration, no destructive down-migration or grant/history deletion.
- Final-phase finite positive/mixed/unknown fail-closed impact selection; local
  focused build/tests/audits and exact-head PR plus full_architecture=false dispatch.
  All selected jobs/steps must execute successfully; downloaded artifact head,
  hashes, actual SQL/SSR/browser/hardening and screenshots must be inspected.

No acceptance item is implied by this contract. #142 and onboarding remain open.
Rollback is application rollback only if compatible; do not roll back by deleting
suspension history or restoring access. A failed acceptance is not a deployment.

## Current validation cadence

The owner’s latest whole-point cadence supersedes historical test-first / RED →
GREEN timing. Preserve historical evidence and its original labels, but do not run
new validation until the whole agreed #164 implementation is finished. Writing
these final tests/runners/CI sources is implementation, not an executed pass.
Source completion does not close #164 or parent#142. The parent owns final local
validation and any subsequent exact-head delivery CI; no automatic deployment.
