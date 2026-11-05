# MVP09 — prepared final acceptance, NOT executed

Status: SOURCE_COMPLETE_UNVERIFIED / all commands below UNEXECUTED for MVP09. Parent owns final validation, corrective rechecks, commit/PR/merge and issue/Project readback. This source-only worker must not execute these commands or open a PR.

## Phase order

1. Freeze the whole source point and durable source checkpoint, including all tracked/untracked hashes against `b00fdbafd3f91f6526caf18e75b79476ab02660f`.
2. Parent executes final offline contract/impact guards, selected API/frontend tests/build/audits, foundation/security/migration consumers and isolated runtime acceptance. Correct failures and recheck affected consumers without fabricating RED or losing NONPASS logs. Serialize Docker --rm helpers on any host taking pre-existing runtime snapshots.
3. Commit/push only the verified source, then PR-only exact-head impact checks and targeted dispatch with `full_architecture=false`. Derive required jobs from the actual whole-point changed paths, never dirty overlay alone. Skip is not pass.
4. Only after whole-point functional/source completion, parent executes ONE explicitly authorized exceptional final campaign on the exact candidate SHA with `full_architecture=true`. Read actual required jobs/steps/artifacts, hashes and checkout trees. Any skipped required matrix consumer or missing runtime artifact is NONPASS, not acceptance.
5. Parent guarded merge, tree equivalence/readback and #148/Project transition only after all five criteria have executed evidence. No automatic main CI is assumed. MVP10/#149 stays separate.

## Prepared commands (run only in final phase)

From the exclusive worktree, with a private durable evidence directory and configured scratch:

```sh
python3 -I scripts/test-mvp09-contract.py
python3 -I scripts/test-mvp09-impact.py
python3 -I scripts/test-mvp08-contract.py
python3 -I scripts/test-mvp08-impact.py
python3 -I scripts/test-mvp07-contract.py
python3 -I scripts/test-mvp06-contract.py
MVP09_POOL_SIZE=4 timeout 1500 python3 -I scripts/run-mvp09-tests.py --evidence-dir /root/.hermes/evidence/enginia360-mvp09/final/pool4
MVP09_POOL_SIZE=1 timeout 1500 python3 -I scripts/run-mvp09-tests.py --evidence-dir /root/.hermes/evidence/enginia360-mvp09/final/pool1
```

The routine selector remains `python3 scripts/select-ci-impact.py --base BASE40 --head HEAD40`; use the whole base-to-candidate path union with staged/unstaged/untracked overlay for local preparation, never execute only the examples above and call that the entire selected gate. Existing frontend runner `run-mvp01-tests.py --build-only` executes real component tests/typecheck/locked build/audit; its runtime command and canonical MVP08 runner must also run because their shared source changed. Actual impact selection decides all other direct consumers. Pin/lock files are unchanged; host Node18 is not substituted for pinned Node24.22.0.

After the parent has pushed the exact validated candidate, the existing workflow accepts:

```sh
# GitHub workflow dispatch accepts a branch/tag name, not a raw commit SHA.
# Fail closed on the exact pushed head before dispatch; never move this branch
# during acceptance. Read the resulting run's head_sha and checkout tree too.
test "$(gh api repos/luigi-pelosi/enginia360/git/ref/heads/feat/mvp-integrated-acceptance --jq .object.sha)" = "$EXACT_CANDIDATE_SHA" &&
  gh workflow run ci.yml --ref feat/mvp-integrated-acceptance -f comparison_base=b00fdbafd3f91f6526caf18e75b79476ab02660f -f full_architecture=false
# Only the PARENT at the explicitly named final exceptional acceptance phase:
test "$(gh api repos/luigi-pelosi/enginia360/git/ref/heads/feat/mvp-integrated-acceptance --jq .object.sha)" = "$EXACT_CANDIDATE_SHA" &&
  gh workflow run ci.yml --ref feat/mvp-integrated-acceptance -f comparison_base=b00fdbafd3f91f6526caf18e75b79476ab02660f -f full_architecture=true
```

`EXACT_CANDIDATE_SHA` is a parent-resolved 40-character actual pushed commit assigned to the shell variable, not a literal value or permission to dispatch now. Raw-SHA dispatch was actually refused with HTTP422 during final validation; no runtime campaign started from that refused request. The guarded existing branch ref and subsequent exact run-head/checkout-tree readback preserve exact-head acceptance without new flags or tags. Default remains false; automatic trigger remains pull_request only.

## Actual exceptional mode and additive scope

Source inspection of the inherited workflow found `impact` gated by `!inputs.full_architecture`; existing `affected-*` jobs depend on it and therefore do not constitute full-mode evidence. Existing full-mode jobs `runtime-migrations` and `verify` are retained unchanged, including B02–B14 API/UI/security, race-controller lifecycle, fixture-free migrations/recovery, internal technical billing/accounting consumers and hardened Compose/HTTP smoke. Their original budgets are not enlarged.

Added `architecture-current-contracts` is final-dispatch-only with a finite 44-group matrix. Each group invokes `run-mvp09-architecture.py` under an explicit `MVP09_EXCEPTIONAL_FINAL=true` environment, reusing the actual named run commands and literal step environments from the current workflow, under each original job deadline. These include impact guards (not impact selection), new integrated journey, all current MVP auth/organization/RBAC/onboarding/master/document jobs, offline dossiers, browser/editor, Rxx security/lifecycle/restore and staging consumers. Full fast API/UI remain covered by the unchanged `verify` job rather than executing an empty impact filter. No legacy consumer is silently dropped; a new/unmapped affected job fails closed until explicitly mapped. Matrix jobs are on isolated hosted workers; commands inside each worker are serial.

Each step has a real command, start/end, exit, PASS/NONPASS and log. Shell pipefail is explicit even for older tee commands. Empty plans, unknown groups, unsupported executable YAML/expressions and missing expected original artifacts refuse. Timeout/interruption terminates the owned process group and retains NONPASS. It never prunes resources or infers task ownership by prefix. Original explicit MVP artifact directories are copied only after success, never arbitrary temporary fixture/credential files. Parent must inspect the original per-suite evidence, not only the wrapper's exit code.

## Integrated evidence map

- `mvp09-created-context.json`, explicit synthetic registration/bootstrap/authority files: generated tenant/company/site/warehouse, exact trusted binding; fixture setup is not D97 UI or real-user identity verification.
- `mvp09-journey-spec.json` binds the same newly D98-approved membership (initially disabled/roleless), explicit enabling and real D97 scoped permission creation/assignment to supplier, company extension, canonical Article/Service, type IDs, four effect documents, grouped origins and hop IDs.
- `mvp09-http-readbacks.json`, `mvp09-integrated-sql.json`, `mvp09-app-role-rls.json`: real persisted facts, no mocked business response. Independent SQL checks same organizational ownership, master identities, per-effect ledger legs, balance/ledger equality, mixed source types and immediate multi-hop origins. Actual runtime_app functions prove allowed own and forbidden foreign company.
- The reused MVP08 journey remains inside this same database/principal/resource chain. It executes partial grouping, stage residuals, competing drafts, source-only revoke/develop/read and exact accepted replay denial while destination grants remain, plus noJS, actual delayed-chunk hydration and exact lost-ACK/CSRF/GET-failure retries. Its original SQL/API cases also run under the same bounded runner. Canonical standalone MVP08 remains separately selected because the helper changed.
- SSR HTML/headers/screenshots and `mvp09-browser.json` record actual OIDC, pinned browser/Playwright versions, headless mode and protected-resource hardening. A new foreign session reads the exact same SSR supplier URL and must not receive private data.
- Candidate/source manifest, all46 published hashes, before/after protected runtime/volumes and exact owned cleanup are inherited from the existing runner. No container, browser or migration ran during source implementation.

## Historical proof reuse and risks

MVP08 parent proof is historical: PR CI `42060851414` (5 jobs/62 successful steps), dispatch `42060851802` (18/166), 12 fresh ZIPs, 32 nonempty TRX and 420 executed/passed/zero runtime skip, candidate/tree equivalent to merged main. This is NOT a new MVP09 execution. Exact byte-preserved independent edge cases remain historical proof until the explicit final campaign executes current consumers.

Retain NONPASS incidents: old protected HTML `lang=it` failure is not candidate readiness; earlier live noJS geometry cause remains unproven; tall Chromium native capture failure has no proven OOM/root cause. Adjacent full-width CDP tiles plus focused viewport captures preserve bounded evidence, not a universal screenshot/skip-link fix. Passing reruns do not establish causality. Retry remains live-page-only, not persistent after reload.

Operational provider adoption, real identity/revocation, target/access, off-host backup/recovery/RPO/RTO, alerts/maintenance, privacy/retention, fiscal/legal approval and production use remain open in MVP10. No deployment, real data, public exposure, paid service/purchase or new persistent environment is authorized. Protected Tailscale443→localhost9119 and all retained IDs/start/mounts/volumes must remain unchanged.
