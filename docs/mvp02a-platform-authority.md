# MVP-02.a — explicit platform authority (#152, parent #141)

Finite implementation contract, 3 November 2026. D96; technical foundation only.

## Trust and scope

The existing cryptographically validated issuer/subject binding resolves the internal identity independently of membership. A new backend-derived actor context retains that exact tuple; no external email, role, internal-ID claim or correlation token is authority. Ordinary organization-context semantics and membership uniqueness are unchanged.

One platform-owner authority slot is persisted, initially absent, never seeded. This is the owner's offline bootstrap/recovery path, not nomination/delegation of additional administrators. An owner with the existing nonprivileged database-owner connection explicitly grants or revokes the slot. Grant requires the existing exact internal ID/issuer/subject binding, locked through commit. Revoke uses the retained exact tuple even after binding deletion. No FK cascade can erase the authority or audit. A new verified binding does not inherit old authority.

## Owner command

`scripts/owner-platform-authority.py INPUT.json` accepts exactly `commandId`, `operation` (`grant`/`revoke`), `internalIdentityId`, `issuer`, `subject`, `verificationReference`, `expectedRevision`. UUIDs are canonical lowercase, nonempty; issuer and subject use the existing resolver's finite HTTPS/printable limits; revision is an integer 0..2147483646. The verification reference is a minimized UUID pointing to an out-of-band owner identity check, not verification itself or authentication. The operator must actually verify the subject offline before grant. No real identity or credential is packaged.

The SQL command is callable only by the non-superuser/non-BYPASSRLS database owner, with no app EXECUTE or table writes. A singleton transaction advisory lock serializes commands. Exact JSON request replay returns the original immutable snapshot (even after later state changes); changed payload with the same command ID conflicts. New commands require the current revision and exact retained tuple for revoke; a grant cannot replace an active different identity. Every accepted command increments revision, atomically writes state and immutable minimized request/snapshot audit. Refusals write neither. Exhausted revision conflicts. CLI requires verify-full TLS, closed input and committed exact audit readback; it prints the original snapshot, not a claim that replay restored current state. Readback is not a second write.

## Narrow HTTP read

`GET /api/v1/platform/administration-eligibility`: anonymous/unbound -> 401; bound without current matching active authority -> 403; current owner -> 200 `{ "canAdministerPlatform": true }`. It requires no customer membership. Current state and exact binding are reread per request in one transaction, with transaction-local actor settings. Authority is not frozen in cookie/token. Store failure is fail-closed (503, never eligibility). Response is no-store even in bearer profile. Existing browser CSRF middleware applies; no write/grant route is added. Reads linearize at their database snapshot; a request begun after completed revoke must deny. No cross-tenant business read or implicit operational access.

## Persistence and boundaries

Append migration 0036 only; published migrations/checksums remain unchanged. FORCE RLS on state/audit: app may SELECT only its current exact identity's active state with an extant matching binding. Audit is owner-only and immutable including TRUNCATE. No SECURITY DEFINER is needed for commands, no new role privileges or business policies. Owner RLS policy is explicitly role-scoped; existing owner binding read policy uses exact transaction-local tuple.

Excluded: organization CRUD/catalog, tenant target navigation, membership rewrite, invitations, delegation, UI, provider/ERP calls, operational onboarding or deployment. MVP-02.b/c and #141 remain open.

## Verification and rollback

Behavioral RED/GREEN is retained per vertical behavior. Real isolated PostgreSQL covers owner/app/nonprivileged roles, no defaults/membership, replay/conflict, boundaries, atomic audit rollback/immutability, binding loss and concurrent commands. Real CA-trusted OIDC Chromium/HTTP covers anonymous/claims/nonadmin, membership-free owner, active-session revoke, no-store/CSRF, failure and alternating identities at pools 1/4. Existing affected auth/RLS/migration/browser regressions remain selected, not the full historical ERP stack. CI mapping fails closed for unknown executable paths; PR-only checks and exact-head dispatch `full_architecture=false` are required. Evidence records actual commands/exits, original RED/GREEN and remote job/step outcomes.

Rollback: revoke through the finite owner procedure; roll back application image if needed. Do not delete published migration/audit or rewrite retained data. This increment creates no persistent environment and changes no protected service/storage/access.

## Executed local evidence checkpoint

Original logs are retained in `/root/.hermes/cache/scratch/mvp02a-evidence/`. They are not reconstructed RED output. Remote exact-head evidence is recorded in the PR after execution.

- `python3 -I scripts/test-mvp02a-impact.py`: RED unmapped finite paths, then GREEN; separate CI invocation RED before workflow wiring, then GREEN.
- `python3 -I scripts/run-mvp02a-tests.py --sql-only`: schema RED (`persistent platform authority missing`), owner-command RED (`owner command missing`), then GREEN. Lifecycle RED observes duplicate-key instead of exact replay, missing revoke after binding loss, and invalid input accepting a write; full original rerun retained before production fix. Schema/function absence is not claimed as separate proof of every later denial.
- `python3 -I scripts/test-mvp02a-authority.py OwnerInputTests -v`: missing finite CLI RED, GREEN. Duplicate JSON reader RED (`ValueError not raised`), then strict reader GREEN.
- `python3 -I scripts/run-mvp02a-tests.py`: real HTTP RED 404 vs expected401; deny-only route then real owner-grant positive eligibility RED403 vs200. GREEN real CA-trusted Chromium/SQL/owner CLI at pool4; `MVP02A_POOL_SIZE=1` same acceptance PASS. The later concurrency/RLS/atomicity/maximum-revision and signed bearer additions are regressions on unchanged production code, not retroactive RED claims.
- Pinned SDK10.0.402 locked restore, Release test/publish, app+test NuGet vulnerability audit: exit0. Fast auth selection60 passed/4 runtime theories skipped; those theories are not acceptance until actual PostgreSQL execution. `R00_MIGRATION_SUITE=foundation sh scripts/run-r00a-tests.sh`: exit0, real pool tests17 passed/0 skipped including signed bearer platform eligibility at pools1/4, and all selected SQL suites executed. No audit vulnerabilities reported.
- `python3 -I scripts/run-r00b-tests.py`: existing actual TLS OIDC/Chromium recovery acceptance and guarded cleanup PASS. All22 impact guard commands, MVP baseline/backlog and inventory guards passed.
- Direct readiness regression exposed an existing D96 archive-header displacement beyond the old1000-character guard (also present at base HEAD), not an authority runtime failure. Restored the same OPE OPEN/runbook links in the archive header; no old test expectation or gate was changed.
- No protected running container/volume changed in the successful runtime readback. No operational identity, external provider, tenant CRUD, frontend administration or deployment was performed.

| Log | SHA-256 |
| --- | --- |
| `01-impact-red.log` | `787715222ffc54584eb01f7a83b811c436592b47cbe982b22878cf0e5da0bafa` |
| `01-impact-green.log` | `fd62c457cb71e49847bf4b65dd4a733d005a8d927ab5ef707880fdbaeb9926f5` |
| `02-schema-red.log` | `ff9427ee80b301ef7c3591fbdf0fa3cef8688fe1692e81333d2b68ddad4755e9` |
| `02-schema-green.log` | `e71d42447a379b5455b8348134fbf19d995c3704dba516f184973a953dc551b9` |
| `03-grant-red.log` | `8be573b6dbe6664d856c270bb7aa109cbfddb8e4c43b7b865682b83a36821974` |
| `03-grant-green.log` | `e71d42447a379b5455b8348134fbf19d995c3704dba516f184973a953dc551b9` |
| `04-lifecycle-red-full.log` | `b2bd4dcc4ce91b69e3f759f3466ea7b14c47dc79f056ad1f43f257f71a7663cb` |
| `04-lifecycle-green.log` | `7a07878cb2754ce6d61cf6e594bce97d463646b05d8c2c7807c25e0353015e5f` |
| `05-cli-red.log` | `39f1e8351a4cb112dc03b57730be89c1f5124dc7c6476c4d05e0eb43aebb6786` |
| `05-cli-green.log` | `73329d97be3863bb4ae0f6be03be93304d0502f54b3ee47fe38afef41bf2197f` |
| `06-http-red.log` | `5226620a95a55e7f971b670bec4ed04af94321c72fbc6d7c3c96135703bb4373` |
| `07-eligibility-red.log` | `1c4c0ad9d6acbcbdfb99f52b986c851d0f2b45972ec659b8ce7ed1e4fe5bb1f0` |
| `07-eligibility-green-pool4.log` | `9ab137b56eb2fd9454e1fe67718d5e3e4d91175d740b265448838f022174f449` |
| `08-ci-red.log` | `ce59957dcc3690b8b3f38d9a68f128f6ee113044fa4bf41b77880ce985b3cde5` |
| `08-ci-green.log` | `d889e796ea5a5e14b33532fed985e1271b52cddf8990af591fc504c139988e5b` |
| `09-sql-regressions.log` | `a4bee54bb69af8f0a9b05250b4f10fe3166006e679d5d193313646e143295c7e` |
| `10-api-build-test-audit.log` | `5e03733e40433bda3f9997a799123d1e6c72845d0da43efde7663cefe596e93d` |
| `11-foundation.log` | `618189affaad5acadb125699bdca367ad0b0560a5a9456f7cb52b887b8751a75` |
| `12-authority-pool1.log` | `36fd61c005fd327537f0d0c4471aa4fa0e19b68800b1c2deb49341c8dd303903` |
| `13-existing-browser.log` | `1da6870a180b7cff546e97fb91621bcb3b5761f775731810830115e2ccf36649` |
| `14-json-red.log` | `c503bcc882bb7b1fafe8c1b943ab119d4254ddff46defca039bd8fb06b8e8284` |
| `14-json-green.log` | `88704c029b7c1252c172107bbef1cdd1cebe99e8cd0aa1cddcf0e5ba8e60eac6` |
| `15-final-pool4.log` | `a010ff18fb411b2b4b2eb737d30fa65991c08ea5b4ae36ce329119221cb65640` |
| `16-readiness-header-red.log` | `2171045015516597f3f6ae3a253f7b2326adbeb34142b9d9614bc4d617c14ec9` |

### First remote attempt and bounded recovery

At candidate `4abd505bbcf7c34b4c753746e5abc58d32d1aa74`, PR run `41551567528` was cancelled (not a pass); its legacy R04 documentation suite reported44 passing tests in185.485s inside the3-minute R06 job. Dispatch `41551566944` failed before new SQL/HTTP acceptance because the reused base realm/browser fixture is deliberately0444: root-local execution had masked a nonroot `PermissionError` while extending it. The completed foundation and old-browser steps do not turn that failed run into acceptance. Failure artifact `13193505616` retains the actual partial logs.

A real nonroot-container reproducer then failed on the same0444 extension before the fix. The owned fixture writer now temporarily restores owner-write and always returns0444, including reused owner-command input; the nonroot regression verifies realm/browser and repeated grant/revoke input writes. No app privilege or runtime hardening was relaxed. The finite authority selection now has a dedicated offline inventory/readiness job, not the unrelated44-test historical ERP documentation mutation suite. Mixed real producers still retain the original full consumers; all old test assertions and existing CI budgets remain unchanged. New scope guard RED precedes this mapping change. Fresh exact-head PR/dispatch acceptance is required; the old failures remain disclosed.
