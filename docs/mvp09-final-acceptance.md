# MVP09 — verified finite final acceptance and historical procedure

## Current verified outcome — PR173 (6 November 2026)

MVP09/#148 COMPLETED. Parent independently verified candidate `e36697723d9d8ae96022cd0779bcc83958fc7f9f`, merged main `9326d19abc97d1eb249d0a1abecdc1ffd4cd3289`, same TREE `8e2230c67865f1199a47a2d75c58cef0fa9caf52` (not new main CI). Ordinary CI42191323014 and dispatch42191747586 passed. Criterion4 completed via scoped FINAL42194906237: `mvp_final=true`, `full_architecture=false`, 23 groups +1 API,24 required jobs/166 steps,104 commands,23 artifact ZIPs/947 source hashes;36 runtime TRX/460 passed/zero runtime skip. All five criteria have parent readback proof; [sanitized provenance](mvp10-functional-baseline.json). No operational readiness/deployment. MVP10/#149 active SOURCE_COMPLETE_UNVERIFIED; artifact publication PENDING, readiness OPEN.

The following is an **archived source-phase contract/procedure**, preserved as written. Its UNEXECUTED/SOURCE_COMPLETE_UNVERIFIED and “MVP10 Backlog” statements are historical, NOT current delivery state. Old42116253372 remains FAILED and interrupted B04 remains NONPASS; no full legacy campaign pass is claimed. Do not rerun this historical procedure as an automatic MVP10 prerequisite.

<details><summary>Historical MVP09 source preparation (superseded by verified outcome above)</summary>


Status: SOURCE_COMPLETE_UNVERIFIED / all commands below UNEXECUTED for the corrected source point. Earlier executions are historical only, as disclosed below. Parent owns final validation, corrective rechecks, commit/PR/merge and issue/Project readback. This source-only worker must not execute these commands or open a PR.

## Phase order

1. Freeze the whole source point and durable source checkpoint, including all tracked/untracked hashes against `b00fdbafd3f91f6526caf18e75b79476ab02660f`.
2. Parent executes final offline contract/impact guards, selected API/frontend tests/build/audits, foundation/security/migration consumers and isolated runtime acceptance. Correct failures and recheck affected consumers without fabricating RED or losing NONPASS logs. Serialize Docker --rm helpers on any host taking pre-existing runtime snapshots.
3. Commit/push only the verified source, then PR-only exact-head impact checks and targeted dispatch with `full_architecture=false`. Derive required jobs from the actual whole-point changed paths, never dirty overlay alone. Skip is not pass.
4. Only after whole-point functional/source completion, parent executes ONE explicitly authorized exceptional FINAL MVP campaign on the exact candidate SHA with `mvp_final=true`, `full_architecture=false`. This is the seven-domain architecture and evidenced direct dependencies, not an acceptance claim for all retained repository history. Read actual required jobs/steps/artifacts, hashes and checkout trees. Any skipped required matrix consumer or missing runtime artifact is NONPASS, not acceptance.
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
  gh workflow run ci.yml --ref feat/mvp-integrated-acceptance -f comparison_base=b00fdbafd3f91f6526caf18e75b79476ab02660f -f full_architecture=false -f mvp_final=false
# Only the PARENT at the explicitly named final exceptional acceptance phase:
test "$(gh api repos/luigi-pelosi/enginia360/git/ref/heads/feat/mvp-integrated-acceptance --jq .object.sha)" = "$EXACT_CANDIDATE_SHA" &&
  gh workflow run ci.yml --ref feat/mvp-integrated-acceptance -f comparison_base=b00fdbafd3f91f6526caf18e75b79476ab02660f -f full_architecture=false -f mvp_final=true
```

`EXACT_CANDIDATE_SHA` is a parent-resolved 40-character actual pushed commit assigned to the shell variable, not a literal value or permission to dispatch now. Raw-SHA dispatch was actually refused with HTTP422 during final validation; no runtime campaign started from that refused request. The guarded existing branch ref and subsequent exact run-head/checkout-tree readback preserve exact-head acceptance without raw-SHA dispatch or new tags; `mvp_final` is the explicit source-defined corrected final-mode input. Default remains false; automatic trigger remains pull_request only.

## Actual exceptional FINAL MVP scope (owner-corrected)

The inherited `full_architecture=true` lane still executes exactly the unchanged historical `runtime-migrations` and `verify` jobs. It is available for a separately requested legacy campaign, NOT required for MVP09 and NOT selected by `mvp_final=true` / `full_architecture=false`. Ordinary PR-only and targeted dispatch defaults remain false. Set only one exceptional mode; both true is not valid MVP acceptance because the required final jobs refuse that combination.

The new finite final lane has 23 explicit adapter consumers plus `architecture-mvp-api` (one fast API composition/test/locked publish/dependency-audit job, original10-minute budget). API tests run without an empty impact filter; this does not run historical B04–B14 fixture workflows. The final matrix does not automatically widen to every retained affected job: all groups are explicitly classified, unknown/lost groups fail closed until a concrete dependency is mapped. Current security/ownership/restoration checks are not skipped. [Actual dependency and owning-transaction trace](mvp09-cleanup-trace.md).

| Finite final consumer | Original budget | Concrete dependency / acceptance |
| --- | --- | --- |
| `impact` | 5 min | Ordinary selector/unknown/mixed and security wiring guards; selection step itself is not acceptance. |
| `affected-integrated-acceptance` | 60 min | Same generated tenant and D98→enable→D97 operator→supplier/catalog/types/four effects→mixed-source partial development→multi-hop; pool4/1. |
| `affected-document-development` | 60 min | Canonical changed shared MVP08 helper, original API/SQL/browser edge cases and pool4/1. |
| `affected-documents` | 60 min | Documents owns confirmation/inventory transaction, race/replay/audit/negative-stock and RLS contract. |
| `affected-document-types` | 60 min | Current company definitions/passages/versions and permissions feed Documents. |
| `affected-catalog-management` | 60 min | Canonical Article/Service identity/revision/authority supplies document snapshots. |
| `affected-counterparty-management` | 60 min | Tenant supplier identity and separate company extension; shared-master authority. |
| `affected-federated-onboarding` | 60 min | D98 verified first binding, disabled membership, no automatic grants and audit. |
| `affected-membership-access` | 60 min | Current-session revocation/suspension and owning-effect fences. |
| `affected-tenant-roles` | 20 min | D97 role/permission creation/edit/assignment; immutable atomic audit and actual authorization. |
| `affected-platform-offline` | 3 min | Direct inventory/readiness preservation; no operational promotion. |
| `affected-platform-authority` | 15 min | Explicit global bootstrap/revocation, authenticated target and foundation RLS/pools. |
| `affected-organization-administration` | 15 min | Actual tenant/company/site/warehouse ownership and separate delegation. |
| `affected-authenticated-organization` | 15 min | Authenticated SSR and separate organization/users authorities. |
| `affected-frontend` | 12 min | Current Next component tests/typecheck/locked build/dependency audit. |
| `affected-frontend-runtime` | 15 min | Current shell SSR/noJS/hydration, private transport and bounded runtime cleanup. |
| `affected-mvp-offline` | 3 min | D96/D97/D98 literal policy/backlog positive and negative guards. |
| `affected-r05a2-offline` | 3 min | Changed exact historical decision-register guard consumer, documentary only. |
| `affected-r05a3-offline` | 3 min | Changed exact historical decision-register guard consumer, documentary only. |
| `affected-r06-offline` | 3 min | Changed shared decision-integrity consumer and conserved OPEN readiness, documentary only. |
| `affected-migrations` | 15 min | Actual single46-migration catalog/ACLs and owning membership dependencies; foundation/purchasing/receipts and TERM. |
| `affected-browser` | 15 min | Shared TLS/OIDC/cookie/CSRF/RLS/pool helper and real TERM cleanup. |
| `affected-r06-restore` | 45 min | Same current migrator/full snapshots/ACLs; exact0045 private singleton and retained-network identity corrections; canonical plus dump/restore/browser TERM. |

The following stay available but are NOT prerequisites without new concrete producer impact: legacy Vite fast UI/editor; R03 workshop workspace/material correction/own time/closure; R04 material reservations/picking/installations/returns and purchasing/price/dispatch connectors; R05 provider/sandbox/connector campaigns other than the two changed documentary consumers; R06 synthetic staging transfer. Their workflow commands, security tests and evidence are retained, not disabled or reported passed. A real later producer edit still selects its ordinary consumers through the unchanged fail-closed/mixed selection rules.

Each selected group invokes `run-mvp09-architecture.py` with explicit `MVP09_EXCEPTIONAL_FINAL=true`, reusing actual named workflow commands and literal environments under the original group deadline. Commands inside each group are serial; hosted matrix workers are isolated. Empty plans/unknown groups/unsupported YAML or expressions/missing expected artifacts refuse. Each step records command, start/end, exit, PASS/NONPASS, log hash and whole-source manifest. Pipefail is enforced; timeout/interruption terminates its process group and preserves NONPASS. No prune or prefix-based ownership. Parent must inspect actual suite artifacts/logs, not only wrapper exit. Original artifact directories are copied only after success, never arbitrary fixture credentials.

Parent-only local preparation for the SAME finite campaign, after the entire corrected source point is frozen (UNEXECUTED here):

```sh
# Set private durable FINAL_EVIDENCE and scratch TMPDIR/RUNNER_TEMP first.
# Explicit finite list; do not replace with all affected jobs or legacy B04–B14.
for consumer in impact affected-integrated-acceptance affected-document-development affected-documents affected-document-types affected-catalog-management affected-counterparty-management affected-federated-onboarding affected-membership-access affected-tenant-roles affected-platform-offline affected-platform-authority affected-organization-administration affected-authenticated-organization affected-frontend affected-frontend-runtime affected-mvp-offline affected-r05a2-offline affected-r05a3-offline affected-r06-offline affected-migrations affected-browser affected-r06-restore; do
  MVP09_EXCEPTIONAL_FINAL=true python3 -I scripts/run-mvp09-architecture.py \
    --job "$consumer" --evidence-dir "$FINAL_EVIDENCE/$consumer" || exit "$?"
done
# Separate fast API composition job uses this actual locked command:
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24@sha256:230c3fbae0ceedc70bca04eed2bfb5694e8b248cadbb81010f41b7a993601f55 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore && dotnet publish src/Enginia360.Api -c Release --no-restore -o /proof /p:UseAppHost=false && dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive'
```

No legacy `verify` or full-history matrix is part of that completion condition. Local execution is not remote exact-head CI; parent must bind the actual pushed source manifest and read all24 required final jobs/steps/evidence before criterion4 can pass.

## Integrated evidence map

- `mvp09-created-context.json`, explicit synthetic registration/bootstrap/authority files: generated tenant/company/site/warehouse, exact trusted binding; fixture setup is not D97 UI or real-user identity verification.
- `mvp09-journey-spec.json` binds the same newly D98-approved membership (initially disabled/roleless), explicit enabling and real D97 scoped permission creation/assignment to supplier, company extension, canonical Article/Service, type IDs, four effect documents, grouped origins and hop IDs.
- `mvp09-http-readbacks.json`, `mvp09-integrated-sql.json`, `mvp09-app-role-rls.json`: real persisted facts, no mocked business response. Independent SQL checks same organizational ownership, master identities, per-effect ledger legs, balance/ledger equality, mixed source types and immediate multi-hop origins. Actual runtime_app functions prove allowed own and forbidden foreign company.
- The reused MVP08 journey remains inside this same database/principal/resource chain. It executes partial grouping, stage residuals, competing drafts, source-only revoke/develop/read and exact accepted replay denial while destination grants remain, plus noJS, actual delayed-chunk hydration and exact lost-ACK/CSRF/GET-failure retries. Its original SQL/API cases also run under the same bounded runner. Canonical standalone MVP08 remains separately selected because the helper changed.
- SSR HTML/headers/screenshots and `mvp09-browser.json` record actual OIDC, pinned browser/Playwright versions, headless mode and protected-resource hardening. A new foreign session reads the exact same SSR supplier URL and must not receive private data.
- Candidate/source manifest, all46 published hashes, before/after protected runtime/volumes and exact owned cleanup are inherited from the existing runner. No container, browser or migration ran during source implementation.

## Historical proof reuse and risks

Owner correction source: `/root/.hermes/evidence/enginia360-mvp09-parent/owner-scope-correction.json`. Old exceptional `42116253372` is **FAILED**, not new green. Old B04 process `proc_a0c746d7a4a0` exit−15/agent_close is NONPASS_INTERRUPTED_NOT_SUCCESS; no restart is authorized for this correction.

Parent independent ordinary proof references: PR CI `42112432604` (5 jobs/63 steps), targeted dispatch `42112473729` (19 jobs/175 steps), 13 ZIP/36 TRX/460 passed/0 skipped. These are HISTORICAL evidence of the earlier source, not execution or acceptance of the corrected manifest. Retain parent evidence and hashes outside checkout; do not replay those jobs merely to re-create history. New corrected final validation remains UNEXECUTED, and any actual applicable failure must be corrected and rechecked.

MVP08 parent proof is historical: PR CI `42060851414` (5 jobs/62 successful steps), dispatch `42060851802` (18/166), 12 fresh ZIPs, 32 nonempty TRX and 420 executed/passed/zero runtime skip, candidate/tree equivalent to merged main. This is NOT a new MVP09 execution. Exact byte-preserved independent edge cases remain historical proof until the explicit final campaign executes current consumers.

Retain NONPASS incidents: old protected HTML `lang=it` failure is not candidate readiness; earlier live noJS geometry cause remains unproven; tall Chromium native capture failure has no proven OOM/root cause. Adjacent full-width CDP tiles plus focused viewport captures preserve bounded evidence, not a universal screenshot/skip-link fix. Passing reruns do not establish causality. Retry remains live-page-only, not persistent after reload.

Operational provider adoption, real identity/revocation, target/access, off-host backup/recovery/RPO/RTO, alerts/maintenance, privacy/retention, fiscal/legal approval and production use remain open in MVP10. No deployment, real data, public exposure, paid service/purchase or new persistent environment is authorized. Protected Tailscale443→localhost9119 and all retained IDs/start/mounts/volumes must remain unchanged.

</details>
