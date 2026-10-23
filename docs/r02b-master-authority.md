# R02.b — single shared-master authority and bounded common edit

Subissue #64 of R02 #42. D21/D26/D61/D65/D76/D77; no change to delegable actions. The only supported domain is `counterparties`. This contract implements configuration and one existing edit, not ERP synchronization or general master CRUD. Concrete pilot source/profile values are **not selected** by this implementation.

## One actual authority, explicit company references

Migration `0017_master_authority_profile.sql` appends to the published manifest; all sixteen previous entries/checksums remain unchanged. `organization_access.master_authority_history` stores domain, tenant, strictly increasing version, direction, **owner-supplied technical SourceId and ProfileId**, explicit company references, actor membership, offline-verification evidence reference, command UUID and database effective timestamp. Every company reference in a decision refers to the **same actual source/profile/version**, not merely the same direction enum. Separate company extensions, prices, stock, accounting and integration credentials are untouched.

An owner operation replaces the entire explicit reference set atomically with a new version. It cannot establish competing company writers within one version. Adding/removing a company reference or changing a source is an explicit new tenant-wide owner decision with an exact expected version, never a company override, automatic switch or mutation of an old decision. Concurrent operations based on the same version conflict. A company omitted from the current explicit set has no usable profile: no inheritance/default source is fabricated. This bounded operation does not provide independent company configuration or change the authority of company-owned data.

History is append-only: UPDATE/DELETE/TRUNCATE fail, including for the ordinary database owner. No authority scheduling/backdating interface is supplied; immediate database timestamps are a technical supported-operation boundary, **not a new universal business policy**. Future scheduling or historical reconciliation needs a separate bounded contract.

## Owner/trusted-operator setup, not tenant-admin power

`python3 scripts/owner-master-authority.py <explicit-input.json>` is an offline owner/trusted-operator tool. It requires normal PG environment configuration with `PGSSLMODE=verify-full`, a trusted root certificate and the existing nonprivileged database-owner connection. It neither reads credentials from files nor accepts credentials in input. A web/app role has **no EXECUTE** on the setup function and no INSERT/UPDATE/DELETE/TRUNCATE on authority or edit history. No `master-authority.configure` permission, delegate allowlist extension, endpoint, default-first-user or provisioning is introduced.

The exact input fields are:

- `commandId`, `tenantId`, `actorMembershipId`, `verificationReference`, `sourceId`, `profileId`: explicit, canonical nonzero UUID technical references;
- `domain`: exactly `counterparties`;
- `direction`: exactly `Enginia360ToExternal` or `ExternalToEnginia360`, never bidirectional;
- `expectedVersion`: exact nonnegative current version, zero only for absent history;
- `companyIds`: nonempty explicit unique company UUID list (technical input bound 1000), each validated in that tenant.

The actor must already have a trusted external identity binding and membership in that tenant. `verificationReference` locates the owner's independently retained identity/source verification evidence; supplying a UUID is **not identity verification**. The database credential establishes the trusted operator boundary. Verify identity, source ownership and exact company impact offline **before** applying real setup. The tool does not perform or claim that human verification. The accepted decision records actor and evidence reference immutably; identical replay is idempotent, conflicting/stale input is refused. The tool reads back the exact committed history fields before reporting success, without printing secrets or personal data. No real binding or customer setup was performed during acceptance.

## Runtime reads and one dependent write

- `GET /api/v1/counterparties/authority?legalEntityId=…`: requires the existing exact company-level `counterparties.read` grant; returns missing/local/external, concrete source/profile/version when present and separate `canEdit`. Membership, site-only grants and organization-context administration are not sufficient.
- `GET /api/v1/counterparties/{id}/edit-state?legalEntityId=…`: reads the authorized common identity, committed revision and authority under the same serialization boundary as edits. No company extensions or reserved destinations are projected.
- Existing `PUT /api/v1/counterparties/{id}`: still requires tenant-wide `counterparties.common.edit` **and** exact company `counterparties.read`. Runtime additionally requires explicit `commandId`, `authorityVersion`, `expectedRevision`, with the existing legalName/fiscalIdentifier/registeredOffice contract. No create/remove/deactivate/dedup/publication/vehicle/catalog edit is added.

In runtime, the module-owned SQL function rechecks membership and exact grants, locks permission rows against concurrent deletion and takes the same tenant authority transaction lock as the owner setup operation. Authority validation, expected revision, idempotency history and local UPDATE commit atomically. Direct app UPDATE on the common table is revoked. Foreign-tenant command collisions produce a controlled conflict without exposing the foreign row. The previous synthetic legacy Bxx profile keeps its historical schema and behavior only when `Authentication:Profile=SyntheticLegacy` and browser sessions are disabled; runtime never falls back to it.

Absent or omitted profile, stale authority version, external authority and revision/payload conflicts return explicit 409 states, insufficient grants 403, unknown/inaccessible counterparty 404, malformed command/input 400. Database unavailability remains 503 through the existing runtime boundary. Immutable edit history records the exact actor, company, authority version, revision and necessary before/after business snapshot. Payload values are not technical logs. Idempotent replay adds neither a revision nor another history row. No authority refusal changes reads/searches/selection or silently switches a profile to local.

## Italian opt-in runtime surface

Only UI01.b gains `MasterAuthority`: current company source/profile/direction, missing/external/insufficient permission, error and explicit reread. A selected payer or saved order's payer can open the **actual bounded common edit**, not a fake document editor. It changes shared identity, never the independently selected payer/vehicle relationship, saved order/header/lines or authoritative q6 totals. Company/selection changes and session expiry invalidate outstanding panel responses. No browser storage, tenant claim, optimistic saved state or inferred source/version is used.

Every PUT obtains fresh CSRF. Transport/server uncertainty freezes the exact UUID/payload and offers only identical retry. Success requires server reread; failed readback is explicitly unverified and offers a read-only retry. Definitive refusal clears the stale edit state and requires reread. Existing default bootstrap, synthetic UI01.a, read-only order reopening, CSP and static Ant styles remain separate and unchanged.

## Executed evidence and delivery

Behavior-level RED before implementation is recorded in the delivery evidence: missing owner setup; an actual ungated runtime PUT returning 200 instead of refusal; missing authority UI; unsupported PUT/error state; absent common-edit UI; inconsistent authority read during a controlled concurrent owner transaction; missing persisted domain; and an RLS-hidden foreign command unique violation. The matching GREEN paths are exercised by the targeted runners, not a full architecture gate.

`run-r00a-tests.py` executes the migration/security/history suite, R02.b SQL tests and real pooled Npgsql identity/authority tests. The SQL tests include separate physical concurrent identical retries, controlled owner-change and exact permission-deletion barriers, append-only history, rollback, malformed/conflicting input, app privilege boundaries and foreign identity/tenant isolation. Migration first boot, idempotent restart, checksum drift, failure rollback and restore remain covered.

`run-ui01b-tests.py` uses trusted ephemeral TLS, real Keycloak OIDC/Chromium, nginx/API and PostgreSQL: missing/external refusal with unchanged reads, owner tool over verify-full TLS, actual local UI PUT, deliberately dropped accepted response and exact retry, API reread, SQL source/profile/actor/revision/history readback, paused-database 503 and explicit recovery, logout and preserved search/payer-holder/q6/order behavior. No mock-only browser acceptance or real ERP call is claimed. Exact commands, counts and remote CI handles belong in the PR/issue after execution.

Routine CI remains changed-file/direct-dependency scoped and PR-only automatically; affected migration/browser/editor jobs require targeted dispatch at the exact head. A skipped runtime job is not a pass. Full historical architecture is not a routine automatic or manual delivery gate. Parent #42 and UI01 #5 retain their remaining criteria.

## Limits and rollback

No real source mapping/ERP identifier import, credentials, Giobby HTTP, sync, queue, commercial data, tenant provisioning, real identity, persistent environment, public deployment or purchase. Synthetic explicit sources are acceptance-only. Internal accounting capability is not changed or disabled. R03/R04 operational and editor gaps and R05 provider/mapping/acknowledgement contracts remain separate; R06 and OPE01–OPE05 are not certified by this increment.

No protected deployment was changed. For a future rollback, preserve the applied migration and immutable histories; revert the UI/API through a reviewed PR or apply a forward correction. An older runtime without the gated function must remain unable to UPDATE under the restricted app role: do **not** restore broad privileges or delete history to make it work. Correct an authority only through a new explicit verified owner decision, never by editing history or automatic fallback. Bootstrap/Tailscale 443 → localhost:9119, retained volumes/backups/configurations and the old R00 worktree remain off-limits.
