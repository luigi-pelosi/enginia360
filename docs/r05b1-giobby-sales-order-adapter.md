# R05.b.1 — bounded Giobby sales-order anti-corruption adapter

Refs #104, child of #45; related #44. **Technical candidate only, not live compatibility, owner selection of the exact D85 type, R04/R05 completion or operational readiness.** Uses R05.a.6's evidence-based order recommendation, which the owner can overrule. D76/D82, the External company profile and tenant-wide master authority remain unchanged. No stock/purchasing writer, proforma, invoice creation/conversion, automatic numbering of invoices, sandbox/account traffic, deployment or persistent environment in this increment. An order **reserves**, not discharges stock in the observed sandbox; release/cancellation remains untested.

## Evidence and supported surface

- Official public Swagger: `https://app.giobby.com/GiobbyApi00554/swagger/swagger.json`, fetched read-only for this increment; SHA-256 `0c43f06fa1481fa39d5e0a63f61c5843ded5b82335e68bcb840dc974e13574a3`. `DocumentApi` / `DocumentRowApi` declare input fields; sales-order POST/GET still have no supported response schemas. No proprietary SDK or provider fields enter Workshop's domain.
- Preserved owned minimized responses: `tests/fixtures/r05a6-owned-captures.json` (create acknowledgement, detail and list), plus historical R05.a.2 field/type observation for plain `/loggeduser` (`idCompany` integer, `cid` string). Original captures/decoders/evidence remain byte-identical. Unit HTTP handler replays the owned captures; changed references/negative variants are explicitly synthetic test transformations, not new provider observations.
- The Compose TLS fake uses those response projections with synthetic payload-derived values. Its plain identity response is **synthetic shape coverage** of R05.a.2's observation, not a retained raw identity capture. Neither fixture proves provider guarantees, future schema compatibility, fiscal validity, reservation semantics beyond the prior observation, or exactly-once delivery.

Only `GET loggeduser`, `POST sales/orders?simulation=false`, `GET sales/orders?offset=0&limit=5&freeText=…&docStatus=CREATED`, and `GET sales/{id}/orders` can be generated. No invoice, transformation, stock or purchasing endpoint is implemented. No PUT/DELETE/cancellation.

## Host-only setup and immutable destination

`ExternalAdministration:Protocol=GiobbyV1`, protocol version 1, selects this adapter explicitly; an unknown protocol/version selects an unavailable connector, never the simulator. The same frozen options instance supplies the actual connector, request binding, dispatcher comparison and `AdministrativeRuntime` service consumed by Program/Workshop/UI. Missing configuration holds dependent uses without hiding authorized history.

The non-secret `ExternalAdministration:Giobby` snapshot requires:

| Setting | Meaning / refusal boundary |
|---|---|
| `BaseUrl`, `AllowedHosts` | Preverified company API base; HTTPS only, port 443 or 8443, trailing slash, no userinfo/query/fragment; exact host allowlist. No runtime discovery/redirect retargeting. |
| `CompanyAlias`, `CompanyId`, `Cid` | Explicit non-secret external company identity, compared to authenticated plain `/loggeduser` before each Submit/Status. Never inferred from a display name or unverified token claims. |
| `TenantId`, `LegalEntityId`, `SiteId` | One exact internal owner tuple for this bounded host configuration. Other tenants/companies/sites are held before any HTTP. Multi-company routing/provisioning is not implemented. |
| `Customers:{payer UUID}:Id`, `ContactId`, `LookupName` | Explicit previously verified external customer/contact identity for that internal payer, plus preconfigured customer-name **lookup hint**. No global external customer ID for arbitrary work orders. Names never establish authoritative identity. |
| `Materials:{catalog UUID}`, `Storage`, `BusinessUnit`, `Numerator` | Previously verified material IDs, exact site's external warehouse, BU and sales-order numerator. No fabricated default IDs. Service/material classification and warehouse suitability require setup evidence before live use. |
| `Taxes:{six-decimal rate}` | Previously verified external tax code. Decimal key normalization makes `22` and `22.000000` the same rate, not an implicit tax-code mapping. Other fiscal treatments are not validated. |
| `TokenFile` | Absolute host-mounted secret path. Bounded token read into RAM; never request data, DB, repository, CI secret, HTTP URL or log. Operator-managed acquisition/refresh is outside this increment. |

At request creation, existing Workshop request + outbox + immutable binding are committed atomically under the existing exact action/grant fence. The fingerprint covers protocol/version, normalized base, sales-order type 3, company identity alias/ID/CID, internal scope and non-secret mapping snapshot. It excludes token bytes/path, so same-company token rotation is possible; a wrong-company token is refused by authenticated identity read. No runtime config reload, backfill, redirect, reassignment, or simulator fallback. Changing mappings or company/base after queueing causes a binding mismatch even for Status; restoring the original setup and explicitly reconciling only permits lookup. A request queued with incomplete mappings stays held; configuration correction cannot silently retarget its immutable descriptor. There is no automatic repair or policy to replace such requests in this increment.

Migration **0026 only widens the existing binding Kind constraint to SimulatorV1/GiobbyV1**. Migrations 0001–0025 are unchanged. All RLS, immutable/provenance triggers and permissions remain. R06 inventory has 26 migrations and the same 66 CREATE definitions/9 schemas; CREATE inventory deliberately does not reconstruct ALTER. Eligibility remains UNDECIDED.

## Field mapping

| Internal frozen source / explicit mapping | Declared outbound field |
|---|---|
| Technical candidate constant | `idDocumentType: 3`; never an invoice or proforma |
| Payer-scoped customer and contact IDs | `idCustomer`, integer `idContact`; `idVendor: null` |
| Explicit host BU/order numerator | `idBu`, `idNumerator`; no `docNumber` sent |
| Current submission UTC timestamp in milliseconds | `docDate` string (declared example representation); not an approved fiscal/business-date policy |
| Snapshot currency | `docCurrency` (bounded EUR) |
| Stable request UUID | `reference: E360-{UUID without hyphens}`; correlation only, never authentication/idempotency promise |
| Active snapshot rows in owner order | `rows`, `idPosType: 1`, mapped `idMaterial`, snapshot `description` |
| q6 decimal quantities/prices, explicit discount | numeric `quantity`, `price`, `dsc1`; no floating-point or cent rounding in adapter |
| Verified tax/warehouse mapping | `idVat`, `idStorage` |
| Empty explicit array | `payments: []`; observed Giobby still creates a payment instalment; not payment suppression |

No tax authority, stock writer, local receipt or money calculation policy is introduced. Snapshot net/tax/total remain owner facts. Live business-date, nonzero-discount, multirow, service classification, tax and rounding compatibility are not established by the single owned quantity-one observation.

## Completion and recovery

1. Persisted dispatcher `Uncertain` precedes HTTP, including identity read. Lease must exceed all three bounded HTTP calls; fencing and exact tenant/company server context are preserved.
2. HTTP200 + business200/error0 + positive integer `idDocument` is only an acknowledgement. It triggers exact GET; it does **not** mean Completed or fiscal issuance.
3. Detail must match positive ID, type 3, CREATED, exact technical reference, customer/contact, row count/order/positions, material/warehouse, decimal quantity/price, and totalAmount against snapshot total. Nonzero discount requires matching returned `dsc1`; a supplied `dsc1`/`idVat` must match. The minimized owned capture omits tax-code/discount/net/tax totals: absent zero discount is tolerated, tax-code identity relies on the verified outbound mapping, and net/tax are **not independently returned totals**. Unsupported or mismatched fields remain ambiguous; no invented response fields. Confirmed reference is `GiobbyOrder-{id}`.
4. Status uses the preconfigured customer-name hint plus CREATED, **never freeText=request reference or idContact**. A structurally checked page of at most five headers must be complete (`offset=0`, exact declared cap, totalCount agrees and is below cap). Client filters type 3, customer, exact request reference, CREATED; only one match permits detail readback. Empty, nonunique and truncated are distinct ambiguous codes. No automatic pagination or NotFound guarantee.
5. 5xx, timeout/transport failure, 4xx, redirects, malformed/oversized responses, unknown business errors and empty lookup never produce NotFound or authorize a second POST. Four failed polls reach NeedsReconciliation; explicit reconciliation resumes **GET only**. No documented conclusive Giobby business-refusal contract exists here, so this adapter never emits Rejected from arbitrary HTTP/errorCode alone. Simulator's historically documented rejection/NotFound semantics remain isolated to SimulatorV1.

TLS certificate/hostname validation is standard .NET (ephemeral CA trusted in acceptance), redirects disabled, HTTP logging removed, response cap 65,536 bytes and deadline covers body streaming too. Auth token is frozen in RAM for each identity+business sequence. No discovery URL is automatically followed: a separately verified discovery result must pass the same host-only base allowlist before being configured. Token expiry/auth failure holds; no live grant, login or discovery call was made for this increment.

## Executed verification and limits

- `scripts/test-r05b1-impact.py`: finite positive/negative mapping, PR-only automation and targeted dispatch guard. Unknown executable paths still fail closed; full architecture is not the default.
- `GiobbySalesOrderTests`: owned-capture real adapter/HTTP handling, q6 mapping, missing/foreign mappings before HTTP, ack/readback, mismatch, typed lookup, unknown errors, bounded transport, auth/identity, actual runtime/descriptor and lease bounds. New behavior had separate executable RED/GREEN; added passing historical-path coverage is labelled regression.
- `scripts/run-r05b1-tests.py`: same established R05.b.0 runner/Compose primitives, trusted TLS/OIDC Chromium + real API/Postgres, pool4 and pool1. Includes creation-time A→B Submit/Status blocking, controlled hold/history, exact same-UUID concurrency, CSRF/grant/RLS, real DOM/fetch provider identity, ack-only/500/timeout/empty hold and recovery, no duplicate POST, no prohibited endpoint, actual redirect denial, fixture-only insert/deferred-commit rollback, read-back outcomes and HTTP effects. Fake amounts are synthesized solely for exercising the adapter and are not external evidence.
- `scripts/test-r05b1-lifecycle.py`: actual TERM with Chromium and held SQL dispatch barrier; exact protected-container/volume cleanup assertions unchanged. Existing R05.b.0 lease-race/permission/history suites remain regressions, not independent-worker-process crash proof.
- Exact-head PR/dispatch IDs and selected executed jobs/steps are recorded in the delivery report after execution, not guessed here. Skipped runtime jobs are not passes. Historical fixture/evidence hashes and migrations are checked separately.

No provider account traffic, credential access, invoice conversion, deployment, live reconciliation, external customer provisioning, universal idempotency/exactly-once, or R04/R05/readiness claim. Cancellation/release, real API row/tax/rounding compatibility, token acquisition/refresh, future multi-company routing, live recovery latency and owner final D85 type choice remain outside this bounded proof.

## Rollback

Revert application/host wiring through a tracked PR with outbound dispatch stopped first. Keep 0026 as an inert append-only migration; do not rewrite published migration bytes, delete history or downgrade the Kind constraint over existing Giobby bindings. Old simulator-only code must not run active Giobby delivery. Pending immutable Giobby requests remain held until their original supported configuration is restored; no retarget/replay or destructive cleanup is authorized. No protected bootstrap or retained environment was changed.
