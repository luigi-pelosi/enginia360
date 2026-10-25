# R05.b.0 — immutable synthetic administrative connector binding

Refs #90, child of #45. This is **not** a Giobby adapter, projection, stock/purchasing writer or readiness claim. Giobby R04.b/R05 stays BLOCKED on the official response contract.

## Contract
- At request creation, Workshop freezes `Kind=SimulatorV1`, `ProtocolVersion=1` and a SHA-256 destination fingerprint in `workshop.administrative_bindings`, in the same owner transaction as the request and outbox row.
- The host composition supplies the descriptor; clients cannot send, and responses/logs never contain, a URL or credential. Request bodies keep unknown-member rejection.
- The dispatcher reads the stored binding through `IWorkshopAdministrativeOutbox.Read` and compares it with the current host descriptor before **any** Submit or Status. Missing, unknown protocol, absent host descriptor or mismatch becomes `NeedsReconciliation` with `destination_binding_mismatch`: no POST/GET, no fallback, no retargeting.
- Terminal Completed/Rejected state is finished without HTTP. Restoring the original descriptor and using the existing explicit reconciliation resumes the same UUID through Status, not a blind resubmit.
- Historical requests created before 0025 have no binding, stay readable and held, and are not backfilled: a trigger only accepts a binding created by the same transaction that inserted the request.
- Fingerprint canonicalization is the absolute URI normalization of .NET (case-insensitive scheme/host). Path, port and scheme differences remain distinct.
- Uses the exact existing `workshop.administrative-requests.create` grant, rechecked on the Workshop connection through `organization_access.administrative_request_authorized`, so revocation serializes before request, binding and outbox commit. No nested pool.

## Limits
Only the existing synthetic protocol is proven. No Giobby IDs, wire fields, endpoints or default profile; no SDK/provider framework. A missing/unverified descriptor does not stop the application or history; it only holds dependent dispatch. The fingerprint is a technical non-secret identifier, not authentication.

## Verification
`scripts/run-r05b0-tests.py` (trusted TLS, OIDC, Chromium, API, PostgreSQL, two isolated simulators A/B, HTTP counters; pool 4 and pool 1), `scripts/test-r05b0-lifecycle.py` (TERM) and `scripts/test-r05b0-impact.py` (dispatch-only `affected-r05b0`). The proof-gap suite `R05B0_SPEC=r05b0-gaps.cjs python3 scripts/run-r05b0-tests.py` (pool 4 and pool 1, same stack) adds: identical-UUID concurrency, same-UUID/foreign-tenant conflicts, invalid and max-bound payloads, CSRF/tenant/role/capability refusals, rollback of request+binding+outbox together (fault triggers exist only in the ephemeral fixture database), and stale-lease/reconcile races on every claim path with simulator B counters at zero. R06 inventory classifies the new table `integration_evidence` and leaves eligibility UNDECIDED.

## Rollback
Revert this PR. The 0025 table is additive and published migrations 0001–0024 are byte identical; if already applied, keep it as an inert ledger until a separately approved cleanup. No data deletion.
