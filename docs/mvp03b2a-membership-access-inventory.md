# MVP03.b.2a — Access-ingress inventory (historical discovery)

Refs #164 / #142. Historical discovery, not an all-origin enforcement claim.
Current production/catalog/consumer assertions and limits are mapped in the
[final validation ledger](mvp03b2a-final-validation.md); the prototype descriptions
below are retained history, not the current implementation status.

**Current source continuation, UNVERIFIED:** [focused backend checkpoint](mvp03b2a-backend-progress.md).
The text below preserves the first tracer's historical inventory and warnings;
its “currently”, missing-command and777040 statements describe that earlier
checkpoint, not the current backend stage. The continuation has the executed
state command/API/fences,777036 ordering proof and precise remaining consumers.

## Actual database inventory

The SQL-only ephemeral TLS runner applied the real manifest (all 39 published
migrations plus the unpublished 0040 prototype) and read `pg_proc`,
`pg_get_functiondef`, `pg_policies`, table privileges and FORCE RLS flags.
Raw catalog: `/root/.hermes/evidence/enginia360-mvp03b2a/actual-runtime-catalog.json`.
At this checkpoint it contains 89 tables (including the migration ledger),
90 function overloads, and 38 app-executable SECURITY DEFINER entrypoints.
These are catalog facts, not executed authorization acceptance. The catalog also
records any-column SELECT/INSERT/UPDATE privileges: destinations, stock, several
Workshop tables and integration dispatch tables have column UPDATE even though
table-level UPDATE is false. Exact column-name ACL inventory remains necessary
before changing those consumers. The earlier regex inventory is superseded:
it misclassified some same-line declarations and missed overloaded functions.

## Independent ingress and owning effects

| Origin / consumer | Actual source / SQL | Required remaining proof |
| --- | --- | --- |
| Root context grants | `OrganizationAccessModule.cs`: ListContexts, CreateNote, GetNote; `membership_scopes`, effective view, `context_notes` | Disabled/root direct SQL + cookie/JWT/SSR and effect commit; not only new roles |
| D77 operative and administrative mandates | `LimitedGrantAdministration.cs`; `grant_administration`, `command_operative_grant`, `delegation_mandates`, `delegated_scopes` | Recipient and mandate-admin access state; expiry/revocation/replay; no renewal on enable |
| Configurable roles | `TenantRoleAdministration.cs`; `current_tenant_role_scopes`, `tenant_role_objects`, role audit | Disabled actor / assignment recipient and current exact binding; state command must not reactivate administration |
| Organization delegation | 0038 `lock_organization_delegate`, workspace/read/command; `organization_delegations` | Disable current delegate, preserve owner global bootstrap, both delegation origins separate |
| User delegation | 0039 `lock_user_administrator`, workspace/read/command | Disabled delegate denied before replay; organization-only remains denied |
| Counterparty/company/common-edit | `CounterpartyAccessAdapter.cs`; CounterpartiesModule, CommonEndpoints, DestinationEndpoints, SupplierEndpoints; 0017/0027/0035 functions | Real read/write and direct SQL/security-definer paths, common-edit-only/site-only/warehouse-only scope negatives |
| Workshop | `WorkshopAccessAdapter.cs`; WorkshopModule, EditorEndpoints, CommercialEndpoints, ActualTimeEndpoints, InstallationEndpoints, AdministrativeEndpoints | Authorization adapter commits before owning effects; current guard/binding must span owning transaction, including direct service ports |
| Catalog and Vehicles | CatalogModule / PurchasePriceEndpoints, VehiclesModule; 0029/0030 catalog functions | Tenant-only internal service calls need authenticated transaction context; price reads/writes and quote consumers are real affected security consumers |
| Inventory | `InventoryAccessAdapter.cs`; InventoryModule, Picking/Release/NewPartReturn/CarcassReturn/PurchaseIntent/ReceiptIntent endpoints; 0023/0024/0028–0034 SQL | Owning quantity/effect transaction, source joins, direct functions and app SQL; no selector narrowing away these actual consumers |
| Billing and Accounting | `BillingAccessAdapter.cs`, `AccountingAccessAdapter.cs`; BillingModule / ConfirmedInvoices, AccountingModule | Current membership guard at owning invoice/journal transaction, not earlier company authorization |
| Accepted-work background ports | Integrations dispatchers/recovery; Workshop administrative outbox; Inventory pending/read/record purchase and receipt dispatch functions | Classify technical processing separately; preserve accepted work without exposing a generic missing-identity business bypass |
| Identity / browser / SSR | ExternalIdentityResolver; BrowserSessionModule; Next authenticated pages and backend forwarding | Existing resolver validates binding, not access state; use current open sessions and JWT, CSRF and no-store/cache isolation |
| Explicit historical profile | `Authentication:Profile=SyntheticLegacy` and browser sessions disabled | Preserve existing legacy fixtures/assertions; no global fallback or weakening of verified production context |

The five authorization adapters currently set only `app.identity_subject`, not
issuer and opaque subject. The unpublished prototype requires the exact tuple
at grant SQL ingress; **normal enabled-member company flows are therefore not
verified compatible and must be fixed/tested before this migration can ship**.
The adapter transaction also commits before the owning module's effect: a lock
there alone cannot serialize suspension with effect commit.

## Prototype coverage, deliberately incomplete

0040 currently has private sparse state (absence = existing enabled/revision0),
current exact-binding helper, restrictive root/company/common-edit policies, and
separate selector fields. Real new SQL tests showed old binding replacement
still exposed root/company grants before the patch and now denies those paths.
The original 15 role SQL tests passed unchanged afterward.

Still unfenced: ordinary business-table RLS, D77, current role scope expansion,
both administrative delegation paths, service effect transactions and SSR.
There is no state mutation command, audit table, HTTP command, usable UI or
runtime acceptance. A next presence test deliberately remains RED because the
state command is absent; that test proves absence only, not future semantics.

## Lock design that still needs implementation and physical proof

The prototype helper takes transaction-shared advisory lock 777040 and holds
exact membership/binding rows FOR SHARE. Existing administration paths use
777036. A potential state mutation order is 777036 then exclusive777040; existing
OrganizationContextService already takes 777036 before root queries. Do not add
a generic interceptor taking777040 before777036 on those paths: that reverses
the mutation lock order. Owning business consumers need an explicit compatible
transaction boundary, current actor propagation and independent physical races
in both orders, with pool1 and pool4. This paragraph is a design warning, **not
serialization evidence**. No such interceptor or state command exists yet.
