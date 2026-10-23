# R03.a.2 — safe material structural corrections and direct consumers

23 October 2026. Scoped subissue #68 of #43; #43 and #5 remain open. P1/P2 are already approved. No appointment/time/delivery/new-part return/release workflow, real data, ERP calls, purchases, deployment or persistent environment is introduced.

## Contract and ownership

Before technical closure, `EditCommercialLine` accepts explicit `quantity`, `groupId`, and the **paired** `catalogItemId`/`catalogVersion`. Group must be active in this same order. The public Catalog lookup must return that current version and the existing row kind; the operator cannot turn a Part into a Service. Catalog identity/version/label are replaced together; price is never inferred. Payer, tax, order, row ID, creation sequence and configuration provenance stay immutable. `RemoveLine` permanently tombstones a Part; original history is not deleted or revived.

A structural Part change is permitted only without active logistics effects. Existing committed reservation, picking and consumption facts are active. Failed/rejected reservation has no persisted commitment and does **not** seal the line. The published runtime has no reservation release, new-part return or compensation command/state: R03.a.2 invents none. A D73 replaced-component/carcass receipt is not a release or compensation of the new part, so it does not make an installed/reserved line structurally editable. A future approved fully compensated/released state must evolve the Inventory owning contract and tests, not be guessed from quantities or carcass coverage. Commercial-only price/discount/description corrections remain possible with active effects, until technical closure.

Append-only migration `0020_material_structure_fence` preserves the exact nineteen prior manifest entries and SQL checksums. SQL contracts are **public owning-module interfaces**, not permission to query the other module's private tables:

- `inventory.line_has_commitments(tenant uuid, line uuid) → boolean`: Inventory owns its query of reservations/picks/consumptions. VOLATILE, SECURITY INVOKER, fixed `search_path = pg_catalog, inventory`; explicit tenant predicate plus forced RLS; revoked PUBLIC execution, app EXECUTE only.
- `workshop.reservation_line(tenant uuid, ord uuid, line uuid) → (OrderId, LineId, LegalEntityId, SiteId, CatalogItemId, CatalogVersion, Kind, Quantity, WorkingGroupId)`: Workshop owns the snapshot query; only active, not-technically-closed material sources. Same invoker/RLS/PUBLIC/grant discipline; fixed `pg_catalog, workshop` search path.
- Canonical lock key is lowercase UUID D-format `inventory:line:{tenant}:{line}`, hashed by `hashtextextended(key,0)`. Workshop: order advisory lock → line advisory lock → **fresh** commitment function → projection/version/history/revision/receipt in one local transaction. Inventory Reserve: command lock → line lock → **fresh Workshop public SQL snapshot on Inventory's existing transaction/connection**, then residual/stock locking and reservation. Preliminary Workshop lookup is authorization context only; quantity/catalog/group are not used from that stale snapshot. No held pooled connection opens another module connection; pool1 completes.
- The Workshop trigger independently takes the same serialization fence and rejects active structural changes even through raw application-role SQL. No GUC/raw-app bypass or identity trust is added. Column grants are limited to the changed projection fields; history/receipts stay insert-only, forced RLS and no app DELETE/TRUNCATE. Other identity columns stay trigger-immutable.

`409 active_material_commitments` is a controlled refusal with no partial version/history/receipt/revision. Existing stale revision/policy, exact grants, CSRF, closure, replay and collision semantics remain. Exact replay returns the original immutable receipt, even after a later edit/removal/closure, but only after current membership/action authorization.

## UI

Real supported quantity, explicit working-group/catalog selection and removal controls are exposed after server proofs; draggable rows, header/payer/vehicle, logistics panels and new workflow remain unsupported. Capability/read-only/closure state still gates writes. Server checks remain authoritative for active commitments. An uncertain command freezes edit controls and retains the exact serialized command for retry; accepted response loss is exercised through actual Chromium fetch, not mocked API success. Authoritative reread supplies the saved revision and q6 summary. The catalog selector retains its existing `orders.create` authorization requirement; editing quantity/group does not require or imply catalog-search authority.

## Test-first evidence and truthful history

All logs are durable scratch artifacts under `r03a2-logs` for this execution; no historical merged code is rewritten.

- `python3 scripts/run-r03a2-tests.py`: quantity tracer RED `409 material_structure_edit_not_supported != 200` (01), GREEN (03).
- Same command: tombstone removal RED `409 != 200` (04), GREEN (05).
- Explicit group/catalog payload RED `400 != 200` (06), GREEN (07); the final acceptance also changes to a different real current Part/version/label.
- Deterministic separate-connection PostgreSQL barrier, pool4, edit wins: RED Reserve `201` using stale quantity5 after edit2, expected `409 exceeds_remaining` (08); GREEN after fresh in-transaction owning-public snapshot (09). Reverse serialization observes both exact lock waiters; Reserve wins, structural edit/removal refuses with active effects. Failed reserve leaves the line editable.
- Real UI Part quantity control RED missing (`0 != 1`,12); quantity/removal GREEN (14). Explicit group/catalog controls RED absent (16); subsequent fixture corrections fixed implicit-label matching and paginated catalog search rather than changing production assertions or timeouts. Final actual UI traverses both controls.
- Real accepted-but-lost response: edit-input freezing RED `false != true` (22), GREEN after disabled controls (24); retry body is byte-identical, SQL has exactly one history row and receipt.
- Authoritative reread discarded-draft guard: unit RED retained old quantity3 after server revision5→6 (39), then minimal effect clears the old edit without silently rebasing it; uncertain frozen commands remain retryable.
- `python3 scripts/test-r03a2-impact.py`: missing r03a2 selection/job RED (25), then required targeted dispatch mapping and both pool sizes are wired.

Existing working behavior may pass immediately and is reported as regression, not manufactured RED: real picking/install/consumption/carcass for two working-group IDs distinct from OrderId; technical closure, internal Billing draft/confirmation and Accounting journal; external administrative request snapshot; exact grants/revocation/CSRF/cross-tenant/hidden-command collision rollback, replay, q6 and history. The initial direct-consumer assertion used `state` instead of the actual Billing `status` property; this was a test error, **not** a production defect or TDD RED. An intermittent fixture acknowledgement exposed non-atomic file publication; test controller request/ack publication now uses atomic rename. Original R03.a.1 tests added after production remain historical TDD nonconformance; this increment does not retroactively certify them.

## Actual affected acceptance

`python3 scripts/run-r03a2-tests.py` runs real CA-trusted TLS OIDC Chromium → nginx/API → PostgreSQL, default pool4, no mocked responses. `R03A2_POOL_SIZE=1 python3 scripts/run-r03a2-tests.py` separately runs the same sequential public-contract and downstream paths with the shared one-connection pool; only the simultaneous two-waiter barrier is pool4-specific. Reports distinguish these paths. Exact PostgreSQL lock IDs and distinct waiting backend PIDs, not scheduler sleeps, establish both serializations.

The new workspace has repeated Service/Part rows, Notes, edited revisions and two non-order working groups. Reservation → pick → installation/consumption → carcass quantities and group IDs are checked through real endpoints and SQL. Current persisted revision, not row count, reaches closure/Billing; Notes are excluded; BigInt/Decimal-independent q6 values match snapshots. Billing confirm and journal replay are idempotent; journal debit equals credit, difference zero; source/invoice/journal/versions/history/grants are read back. External snapshot creation remains distinct from business acceptance; no live Giobby transport or fabricated acknowledgement is claimed.

Affected-only regression includes migration upgrade/backfill/rollback/RLS/permissions/pooling, R00 session, UI01 runtime and original R03.a workspace. CI stays PR-only automatically. `affected-r03a2` is explicit exact-head dispatch, `full_architecture=false`, with pool4, pool1 and actual TERM while Chromium and a separate held SQL lock are alive. Skipped required jobs never count as success. Remote job IDs and merge/tree identity are delivery evidence in #68/PR, not prewritten predictions.

## Rollback and boundaries

No protected deployment changes. Use only guarded random ephemeral Compose projects, no host ports/persistent volumes. Cleanup runs on success, failure and TERM; protected bootstrap containers, retained 25 volumes/backups/configuration, old R00 worktree and Tailscale 443→9119 are untouched. Reverting to an older binary would remove the structural fence coordination and is **not** a safe live rollback. Forward-fix or restore the exact verified backup on an authorized target; do not drop migration history or physical business history. No production target/go-live is authorized.
