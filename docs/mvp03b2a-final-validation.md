# MVP03.b.2a — Final validation ledger

Refs #164 / #142. This ledger supersedes **current-status** wording in the
historical discovery/checkpoint documents, not their retained failures or RED
chronology. Whole-point implementation is complete; final corrective validation
is in progress. Remote exact-head acceptance and parent review remain mandatory.
No merge, issue/Project completion, deployment or operational readiness is claimed.
Whole MVP03.b `runtimeDelivered=false`; D98 first-binding/onboarding remains future.

## Criterion → actual executed assertions

Local durable evidence root: `/root/.hermes/evidence/enginia360-mvp03b2a/`.
Each `final-*.status.json` records the actual argv, HEAD, dirty-source SHA256,
START, exit and END; its matching log retains real stdout/stderr. A matching
commit ID alone is not evidence of matching dirty source. Current production
0040 SHA256 is `cfd47c810509e6180d1e4b279bd9a2599564c878987a5696e9d631a60d75be6a`.

| Criterion | Executed assertion / retained evidence |
| --- | --- |
| Separate existing-member state/revision; no new identity/membership/grant | SQL `test_disable_changes_existing_access_without_deleting_grants`, `test_enable_changes_disabled_access_with_independent_revision`, selector test; signed-bearer `MembershipAccessTests`; actual OIDC user/delegate/owner journey |
| Exact actor/target matrix, privilege/self restrictions, owner bootstrap independence | SQL privileged-target, user-delegation/self-disable, D77 admin-vs-operative recipient, owner-ordinary-membership, target/binding/private-DML tests; organization-only/current disabled delegation refusal |
| Root/D77/role/company/common-edit grant origins | SQL disabled role/effective view, direct root/company binding replacement, D77 recipient and disabled mandate administrator before replay; `final-d77-regression-attempt3` executes the latter separately, preserving historical command count and scope count |
| Actual enable → access → disable → denied → re-enable | `MembershipAccessTests` signed bearer at pools1/4; `membership-browser-results.json` and browser source assertions use existing real OIDC cookies and a signed IdP JWT, then reread current root access with the same credentials; state does not delete session or grants |
| Owning transactions, not only authorization adapters | `CounterpartyMembershipFenceTests`22, `WorkshopMembershipFenceTests`34, `BusinessMembershipFenceTests`18 and `MembershipAccessTests`2:76 executed,0 skipped per whole runner; persisted effects checked before status; actual Inventory reservation, Billing confirmation, Accounting journal and Counterparties destination effects |
| Physical race orders, binding lifetime, pooled connections | Disable-first/effect-first/binding-first, Counterparties SD lock order, Workshop editor/technical/rebinding, root notes, direct SQL; exact physical waiter assertions and unfinished tasks; pools1/4 included. Workshop RepeatableRead snapshot disable/rebind/cancellation, handoff and stale SQL snapshot40001 are independent cases |
| Direct SQL/RLS, invoker view, SD and service ingress | SQL direct catalog/vehicle/stock and effective scope tests; Counterparties raw read/write/missing identity/recipient service/four SD entry races; Workshop raw read/write/source/missing tuple and reservation/Billing/allocation service cases. Actual catalog supplements verify exact59 restrictive policies, app roles/predicates/FORCE RLS and exact41 app-executable SD signatures, not merely source text |
| Replay/current authority/conflicts | SQL access replay/conflict/stale/current revoked actor; disabled delegate cannot replay; D77 disabled admin cannot replay operative grant; API repeated UUID and conflict, malformed input; browser disabled delegate403 before replay, historical state snapshot does not reapply; mutation tests reread unchanged history/effects |
| Atomic immutable minimized audit | SQL update/delete/truncate refusal, explicit minimized denial rows, insert and deferred-commit rollback; HTTP503 for both fault points with unchanged physical state and absent replay row; browser SQL readback exactly4 applied command UUIDs and minimized immutable rows |
| Accepted work vs new user operation | Workshop `accepted-work` cases at both pools read and record the persisted envelope after suspension, while new user ingresses refuse; exact ten accepted-work SD entries separately classified, private original/ACL supplement, existing purchase/receipt/administrative dispatch regression suites retained. No missing-identity flag or cancellation path is added |
| Cookie/JWT/SSR/CSRF/no-store/uncertainty | Real Keycloak/OIDC and signed-bearer browser assertions; no-JS disabled-state HTML and sanitized headers; separate delegation labels; self-disable warning; three byte-identical in-page retry bodies after lost accepted response and failed reread; navigation/new command frozen; disabled delegate reload removes role commands |
| Layout/hardening | Actual390/1024/1440 screenshots and document overflow assertions; retained Compose nonroot/read-only/cap-drop/no-new-privileges/resources/internal network/no published backend/DB port metadata; isolated ephemeral fixture, not protected deployment |
| Migration/dependency/history preservation | `final-integrity-verified.json`:39 published files byte-identical to base,40 valid manifest hashes,87 old inventory entries unchanged (90 total),20 tracked lockfiles byte-identical; no down migration, history/grant deletion or dependency change |
| Build/audit and direct enabled regressions | Release API publish,276 selected fast API passes (24 runtime skips explicitly not acceptance),196 legacy UI and14 Next tests/typecheck/build, fresh audits; foundation/purchasing/receipt SQL partitions and selected direct-consumer runtime checks. Exact command results remain in named status/log records |
| Selection / remote delivery | `final-current-offline` passes all29 impact/guard command chains; `final-actual-combined-selection.json` retains the real combined dirty-path selection, mixed producers and unknown executable path fail closed. Exact-head PR/dispatch selected job/step results and downloaded artifacts are a separate final gate, not inferred from local passes |

Prior whole-runner local evidence at0040 SHA9e662a9d: `final-pool4-attempt2/` and
`final-pool1-attempt3/`:17 SQL cases and76 runtime API cases per runner,0 skipped;
28 retained artifact digests each, plus actual SQL/catalog/ACL/SSR/browser data.
The later accepted-work compatibility correction changes only the bounded
Workshop accepted-envelope read/record body and its targeted assertion. Both
whole pools and the affected binding/closure/sales consumers must pass again on
SHA cfd47c81; old hashes are not substituted for that gate. Final exact-head
job/step/artifact results and candidate tree are recorded in the delivery PR.
The later D77 regression is an additional passing-first regression, not retroactive
RED. Final remote runners execute the current SQL inventory including that case.

## Final corrective incidents and preserved intent

- The remaining binding acceptance found an actual compatibility regression:
  an unbound historical persisted request/outbox was hidden by the new binding
  INNER JOIN, leaving dispatch Queued/source_unavailable instead of the existing
  NeedsReconciliation hold. The read now LEFT JOINs the **exact** binding and
  exposes null binding only for persisted request+outbox work. Recording requires
  a real exact binding object and still refuses unbound/foreign outcomes. No
  backfill, dispatch, new request or missing-identity user bypass is permitted.
  The old historical-hold/zero-HTTP/no-backfill assertions remain unchanged;
  accepted-work security now explicitly checks null-binding historical read plus
  refused outcome recording, and both whole pools are rerun. Failed
  `final-admin-bindings` is retained as a nonpass.
- Earlier grant-table restrictions unintentionally affected the trusted offline
  owner. Corrected only unpublished0040 to target the exact application role;
  separate user-derived definer guards and original owner-only ACL remain.
  Foundation7, purchasing2 and prior whole runners use SHA9e662a9d; their
  unaffected grant/identity policies are unchanged by the accepted-work fix.
- Historical positive SQL fixtures now supply their exact synthetic verified
  binding tuple. Missing-tuple refusal is separately asserted; original downstream
  trigger/rollback/security/replay assertions are retained. No runtime auth fallback.
- Own-time's old barrier counted only backends directly waiting on the resource.
  With existing777036 serialization, backend2 correctly waits behind backend1.
  The fixture now pins backend1, proves its direct resource wait, then proves
  exactly two active application backend identities with backend2's recursive
  `pg_blocking_pids` path through that same backend1 to the exact holder. Both HTTP
  requests must still be unfinished before release. Required2 is not reduced;
  all original duration/revision/conflict/double-effect assertions remain. The
  sibling closure/binding barriers use the same fixture helper, not production code.
  The second dispatch exposed the same direct-only count in the receipt-browser
  budget race (separate from already-passed receipt SQL). It now starts request1,
  pins its direct source wait, starts request2 and proves the exact transitive
  two-backend chain plus both unfinished HTTP requests. Original201/409, uncertain
  capacity,3-provider-POST/single effects and both grant-revocation orders remain;
  the original15-second receipt wait and10-second other waits are preserved.
  The failed receipt-browser log is retained; final complete receipt pool4/pool1
  and lifecycle steps are mandatory, not replaced by SQL-only evidence.
- Return's former read/write fixture created its own lock cycle. The replacement
  proves the reader→holder/writer→reader physical chain, coherent before/after
  quantities and unchanged original successful-write/status checks. It does not
  falsely claim the serialized writes occurred between the source queries.
- Release layout required completion of the two real lazy reads and render frames
  before the original strict clipping/keyboard/footer measurements. No CSS change,
  geometry relaxation or timeout increase.
- D77 supplemental fixture initially omitted the original server-resolved tenant
  context required by FORCE RLS; after supplying actor+tenant, the positive grant,
  disable/refusal-before-replay and owner re-enable/historical replay all pass.
  The setup failure and original own-time failure remain preserved nonpasses.
- First remote dispatch retained two setup/fixture failures, not runtime passes:
  the new membership job's shallow checkout lacked the exact published baseline
  object for the byte comparison (after18 SQL/76 API tests had passed); that
  job now fetches history, with a dedicated guard. Restore's real post-restore
  RLS probe supplied tenant/own-actor but omitted the new mandatory exact
  verified tuple. It now derives each exact existing synthetic binding, adds
  a separate tenant-without-identity denial, and retains original tenant/own-time
  cardinalities, single-backend context reset and ledger/escalation refusals.
  No production access rule or timeout changed. The final head requires fresh
  PR and full selected dispatch success; old-head success is not substituted.
- The second PR run exceeded the existing3-minute R06 offline job budget:
  its44 authority tests reported OK after178.747s, but that canceled job is not
  a pass. Profiling the real validator found remaining full-document promotion
  regex scans and matching unrelated ID candidate starts against every claim.
  The finite candidate index now includes those exact promotion patterns and
  buckets the unchanged claim candidates by their proven initial letters. Every
  original regex/flags/full context and all44 original test bodies are preserved;
  added differential Unicode/positive/negative/unknown-pattern and scan/bucket
  regressions pass. No deadline is increased. Local180-second full-suite attempts
  remain nonpasses. A later exact-head PR passed47 tests in145.871s, but its
  corresponding dispatch again exceeded the3-minute job budget: that canceled
  job is not accepted. Further actual-validator profiling identified remaining
  D90–D92 scope-wide searches and regex-union candidate scans. Finite literal
  finders now feed the unchanged regexes/flags against untouched full contexts;
  new positive/negative/Unicode scope comparisons cover all26 such patterns.
  All47 prior test bodies and every original forbidden-regex tuple remain
  unchanged. The default full49-test command executes four finite disjoint,
  exhaustive process-isolated documentary partitions (including an inventory
  regression), retaining every real CLI mutation and original180-second outer
  deadline. That complete local command passed; final remote acceptance still
  requires every partition/count and all selected job steps within the unchanged
 3-minute job budget. No check or deadline is waived.
- A final-head dispatch closure pool4 browser snapshot-visibility wait timed out
  while the same production/fixture passed the complete bounded local browser
  consumer. This intermittent remote failure is retained, not assigned an
  invented root cause. A targeted instrumented complete pool4 run also passed;
  failed synthetic DOM/state diagnostics now reach the durable job log as well
  as screenshots. No closure assertion, refresh behavior or deadline changed;
  complete pool4/pool1 and lifecycle must pass on the final exact head.
- A local binding run reached its unchanged330-second browser deadline after
  historical hold and both A/B recovery paths passed; it remains a nonpass,
  not a new behavioral failure claim. The final dispatched binding job must
  actually execute complete pool4/pool1, proof-gap and lifecycle steps.
- Owner Docker restart3 November2026 16:11UTC is the accepted protected baseline,
  not investigated as an incident. Protected IDs/start/mount/ports and Tailscale
 443→localhost:9119 remain separately verified. Unrelated resources are not cleaned.

## Limits and rollback

777036 is deliberately coarse: these proofs establish ordering, not throughput or
production-scale performance. Frozen retries are only for the still-open page,
not durable recovery after navigation/restart. Synthetic private fixtures are not
real-user onboarding, fiscal validation, provider adoption or operational exercise.
Application rollback must preserve access/audit history and may not restore access
by deleting state. Do not revert published migrations or silently change old ERP
stock/document authority. No secrets, retained volume cleanup, public exposure,
purchases or protected deployment is authorized here.

The parent owns guarded merge, tested-candidate/main tree comparison and tracking
readbacks. #164/#142 remain OPEN during this worker's delivery.
