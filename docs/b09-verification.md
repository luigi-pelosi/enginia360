# B09 — Full-residual carcass return and technical-closure gate

## Scope, decision and ownership

D73 records the owner's explicit decision «Ogni rientro copre tutto il residuo con unico comando»: with 2 installed parts whose carcass is required, one command returns all remaining 2. Partial returns (1 of 2) are not adopted. D70 authorizes sequential synthetic/ephemeral delivery only; no persistent/manual environment or public deployment. Baseline B08 PR #29/main `67bec45f116c85658098ce62232aafccd365ce10`.

- **Configuration (D30/D39/D14/D9).** `workshop.carcass_policies` is company document-type customizing, versioned per catalog item. Each new installation snapshots the latest policy version and `CarcassReturnRequired`; later versions apply only to later installations. No policy means no requirement and no gate (D30 forbids a default block). The synthetic fixture configures a dedicated *Componente sintetico con carcassa*; case 001's oil filter stays unconfigured and proves the absence of a universal rule.
- **Receipt (D35/D38).** Inventory owns immutable `inventory.carcass_returns`: order/working group/line, catalog item, receiving warehouse of the header site, dedicated location and its configuration version (`inventory.carcass_locations`, refused if missing or equal to a new-part origin/preparation location), description, quantity, server UTC time and verified operator. `inventory.carcass_return_installations` links each covered installation exactly once (primary key on installation). Carcasses never touch `inventory.stock`: physical quantity, availability and commitments are unchanged.
- **Gate.** Workshop `GET /api/v1/workshop/orders/{id}/technical-closure-gate` returns `Blocked` while any snapshotted required installation is uncovered, otherwise `Clear`, with per-line required/returned/outstanding. It is read-only: B09 records no closure state or transition and does not implement the other D37 local requirements. A later closure command must enforce this gate.

## Contract

`POST /api/v1/inventory/orders/{orderId}/lines/{lineId}/carcass-returns` accepts only nonempty `id`, `warehouseId`, explicit positive invariant `quantity` (≤6 decimals, ≤`999999.999999`) and `description` (1–200 characters, no surrounding whitespace or control characters). Unknown or server-owned fields fail with 400.

1. Workshop's tenant-verified projection lists the immutable required installations of the order line, read before any Inventory transaction (works with pool size one).
2. Inventory transaction: command-ID lock → identical retry returns the original (changed line/warehouse/quantity/description → 409) → line lock → fresh covered set → outstanding = required installations not yet linked.
3. Residual zero → 409 `nothing_outstanding`. Quantity different from the exact residual → 409 `must_cover_outstanding` with the current `outstanding`; never trimmed, rounded or completed.
4. Return and all links insert in one transaction; another tenant's colliding ID → 409 without disclosure.

A late installation committed after step 1 is not covered and remains outstanding; if it was visible, a request for the old residual is refused whole. `GET …/carcass-returns?warehouseId=` shows line totals and the returns received in that authorized warehouse.

Authorization: `workshop.orders.read` plus warehouse-scoped `inventory.carcass-returns.create`/`.read`, combined with verified tenant, company, header site and capabilities. Writes need active `workshop` and `inventory` capabilities; historical reads and the gate stay available when disabled. Forced tenant RLS, non-bypass app role and insert-only grants. Audit: route outcome/resource (event 606/404) and committed return (609) with technical IDs only, no descriptions.

## Actual test-first evidence

Scratch logs under `/root/.hermes/cache/scratch` are execution evidence, not tracked output.

| Probe | Command | Observed RED |
| --- | --- | --- |
| HTTP vertical path | `timeout 580 sh scripts/run-b09-tests.sh` (initial runner, no B09 schema/code) | `b09-red.log`: real order/line/reserve/pick/install succeeded; installation lacked the carcass snapshot (`KeyError: carcassReturnRequired`), no return/gate surface |
| .NET boundary | `dotnet test --filter CarcassBoundaryTests` with B09 routes temporarily unmapped | `b09-dotnet-red.log`: 3 failed (404 instead of 401) |
| Unit UI | `npm test -- --run src/B09.test.tsx` | `b09-ui-unit-red.log`: component missing |
| Real DOM/HTTP | `B09_BEHAVIOR=ui timeout 580 sh scripts/run-b09-tests.sh` | `b09-ui-red2.log`: after real login/order creation, part selector `Articolo ricambio` absent |
| Controlled race | `B09_BEHAVIOR=race …` with the line lock temporarily removed | `b09-race-red.log`: 8 production INSERT sessions reached the SQL gate; 1×201 and 7 uncontrolled 500s (only the DB key prevented double coverage). Mutation restored, never committed |
| CI selection | `python3 scripts/test-b09-ci.py` | `b09-ci-red.log`: no B09 runner step |

## Executed verification

- `timeout 595 sh scripts/run-b09-tests.sh`: PASS (`b09-full1.log`, about 4.5 minutes). Real synthetic Keycloak → nginx → API → PostgreSQL: 1/1.999999/3/2.000001 refused, 2 accepted, linking both installations, gate Blocked → Clear, stock unchanged; late installation reopens exactly 1 and the old retry stays unchanged; five concurrent late-install/return pairs; strict input; unconfigured part; 8 identical concurrent retries; changed replays and cross-tenant ID; 8 independent concurrent commands accept exactly one; foreign tenant/member/no-read/order/line/warehouse/service-line/anonymous denial; second warehouse with its own location; three controlled race interleavings (one session at the gate); real DOM run; missing and shared location; D9 policy/location v2; four insufficient grant shapes; read-only/create-only; injected link failure rolls back return and links, API restart, same command recovers once; disabled capabilities keep history/gate; RLS twice; pool size 1; four hardened healthy containers without published ports; destructive rollback twice, B08 schema usable by the app role, reapply and retest; audit. The EXIT trap verifies no project containers or networks remain.
- `src/B09.runtime.test.tsx` (React/JSDOM with real fetch, not a real browser): 1 passed — explicit part selection, reserve/pick 2, install 1 then 1, residual 1 → 2, request 1 refused with the residual message, lost committed response, same-ID retry, `Rientrato: 2`, residual 0, gate satisfied, physical 0 and available 0 unchanged.
- Regressions `run-b02` … `run-b08-tests.sh`: PASS (`b09-regression-b02.log` … `b09-regression-b08.log`). B06–B08 runners now apply the B09 schema and roll it back before B08's rollback.
- Pinned SDK: 50 passed (`b09-dotnet-final.log`); NuGet audit reports no vulnerable packages. Pinned Node: `npm ci`, 19 passed (7 environment-gated skips), every build mode including private B09, `npm audit --audit-level=high` 0 vulnerabilities (`b09-web-final.log`). Race lifecycle offline: 22 passed. CI gates B04–B09: PASS. No dependency, lock or image-pin changes.
- Original bootstrap: read-only HTTP smoke PASS; container IDs/start times unchanged; 25 retained volumes untouched. Remote CI must be verified on the exact PR head and merged main.

## Migration, rollback and limitations

Apply `database/b09/060_carcass.sql` after B08 using the owner convention and explicit `app_user` (idempotent; run twice). It adds the policy/location/return/link tables with RLS and grants, plus two nullable/default snapshot columns and an index on `workshop.installations`. The B08 application keeps working on the migrated schema; the B09 application requires it.

`database/b09/990_rollback.sql` is a **destructive synthetic-fixture rollback only**: it drops B09 tables and snapshot columns while preserving installations, consumptions and earlier facts. It is not a disposal or compensation of real received carcasses. Operational rollback: stop new returns, keep schema and facts, back up, redeploy the previous approved image; any loss or compensation policy needs separate approval.

Limits: no technical-closure state or transition, no other D37 requirements, no optional returns for parts without the requirement, no valuation, cost, refund, supplier return, disposal, carcass ownership or fiscal effect, no carcass catalog or serial number. Snapshot columns on pre-existing installations default to "no obligation"; only synthetic data exists. Audit is bounded technical logging, not a tamper-proof journal. No ERP, SdI, payment, accounting or RPO/RTO guarantee. B10–B14 are not implemented by this increment.
