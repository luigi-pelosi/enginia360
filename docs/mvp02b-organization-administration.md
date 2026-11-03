# MVP-02.b — persistent organization administration (#154; parent #141)

Delivered via PR #155; main `1913c7393362d30193e79ebd7cc1f1a5f521f218`. Parent #141 subsequently completed via PR #157. The 3 November 2026 finite backend contract below remains historical scope: this increment alone did not complete that parent.

## Authority and isolation

Reuse `VerifiedActorContext` from the real authenticated exact internal-ID/issuer/
subject binding, and the current singleton platform authority. No customer
membership is required or created. No role/email/correlation/payload claim grants
power. Every read, mutation **and replay** rechecks current active authority and
extant exact binding server-side. Acquire the same transaction advisory lock
777036 used by owner grant/revoke; hold the binding row SHARE lock through commit.
Revocation and writes linearize in that order, never on a cached eligibility read.

Use finite SECURITY DEFINER operations owned by the existing non-superuser,
NOBYPASSRLS database owner, pinned search_path and no untrusted dynamic SQL. App
gets EXECUTE only, no organization DML or audit read/write. FORCE RLS remains on
all affected tables. The only global policy is tenant **metadata SELECT**, scoped
to the function owner and an extant matching active platform authority; no global
business policy, role membership or bypass. Target function-local tenant context
is verified against that directory and restored on function exit. Existing
ordinary context semantics and customer membership cardinality remain unchanged.

## HTTP and finite data contract

- `GET /api/v1/platform/tenants`: metadata directory including empty tenants;
  `{state:"ok",tenants:[{id,name,revision}]}`, sorted by ID.
- `GET /api/v1/platform/tenants/{tenantId}`: verified target tenant and flat
  `companies`, `sites`, `warehouses` arrays including incomplete chains, carrying
  IDs, immutable parents, names and revision. No business data or users.
- `POST /api/v1/platform/tenants`: create tenant only (target null).
- `POST /api/v1/platform/tenants/{tenantId}/commands`: create child or rename.

Closed JSON command keys: `commandId`, `operation` (create/rename), `kind`
(tenant/company/site/warehouse), `tenantId`, `resourceId`, `parentId`, `name`,
`expectedRevision`. UUID strings canonical lowercase and nonempty; null IDs only
where required below. Route and body target must agree. Create uses null resource
ID, revision0 and existing same-target immediate parent (tenant/company/site);
tenant creation uses null target and parent. Rename uses existing target resource,
its unchanged immediate parent (null for tenant), and revision1..2147483646.
No client-generated new resource ID: generate UUID **after** current authority,
target, parent, input and command checks. Names trim ASCII whitespace, reject
empty/control characters, and accept at most100 Unicode characters (the existing
varchar100 bound). No new uniqueness or fiscal/company fields. Revision starts1,
increments on accepted rename (including same-name rename); exhausted revision
conflicts instead of overflowing. No deletion, reparent, suspension or merge.

Exact command UUID + actor tuple + target + normalized request replay returns
`{state:"replayed",snapshot:...}` with original immutable result, even after later
rename. Changed payload/actor/target conflicts without disclosing another result.
Snapshot includes resourceId, tenantId, parentId, kind, name, revision; it is a
historical result, not a claim of current state. GET rereads current metadata.
Audit stores actor internal ID, command ID, minimized normalized request (no
issuer/subject/token), result and time, atomically with mutation. Immutable audit
including TRUNCATE; failed audit rolls back resource and command. Rejected
commands produce no partial resource/audit. No implicit membership, capability,
business permission, delegation, user provisioning or UI.

Anonymous/unbound401; bound nonadmin403; invalid400; unknown/mismatched target or
parent404 without foreign details; stale revision/reused command409; database
failure503 fail-closed. All platform HTTP responses no-store; real browser CSRF
middleware protects commands. Signed bearer uses existing cryptographic handler,
not synthetic authentication. Maximum body16KiB and duplicate keys rejected.

## Verification and delivery gates

Extend fail-closed CI selection and tests before new executable paths. Original
behavior-level RED then GREEN, actual isolated PostgreSQL and CA-trusted OIDC /
signed-bearer HTTP; pool1 and4 plus independent physical barriers. Exercise empty
and incomplete structures, all create/rename kinds, wrong parent/target, replay
and edit-after-replay, current binding/revoke ordering, invalid names/revisions,
ordinary note-only denial, audit rollback/immutability, no business grants,
app DML denial, FORCE RLS/NOBYPASS and store fail-closed. Preserve all36 published
migration bytes/checksums; append0037 and explicit manifest/inventory entries.
Locked SDK build/tests/publish/audit and exact-head affected PR/runtime checks
(full_architecture=false); skips are not acceptance. No deployment/provider calls,
real identities or data, host ports, persistent environments or protected-service
changes. Parent alone merges and changes issues/Project. PR uses Refs #154/#141.

Rollback: revoke authority using existing owner command and roll back app image;
retain migration, organization IDs, command results and audit. No destructive
schema rollback or data rewrite. MVP-02.c supplies authenticated Next UI later.

## Execution ledger

Original commands/logs and progressive checkpoint live in isolated scratch
`/root/.hermes/cache/scratch/mvp02b-evidence/`; delivery requires their actual
execution, not this contract's intended tests. Executed local synthetic acceptance (not operational release):

- Original RED→GREEN: impact mapping; directory/empty tenant; tenant create/replay;
  company, site and warehouse create; optimistic rename all4 kinds; actual OIDC
  HTTP directory/command routes; anonymous bearer no-store; CI invocation. Real
  HTTP follow-up RED found JSON NUL503 vs400 and unpaired surrogate500 vs400; both
  fixed in bounded scalar/Unicode parsing, then full pool4 rerun passed.
- Later security/boundary/concurrency/atomicity additions already passing unchanged
  production are **regressions**, not retroactive RED: physical create/replay/update
  barriers, revoke-first/mutation-first, binding deletion, immutable audit,
  deferred-commit rollback for create+rename, actual denied app DML, names/max
  revision, no business grants and pool identity/target isolation.
- Latest `python3 -I scripts/run-mvp02b-tests.py`:27 actual SQL tests PASS plus real
  TLS OIDC HTTP pool4,10 immutable command/audit rows read back. Earlier pool1 full
  acceptance:25 SQL tests+HTTP PASS; exact-head CI reruns latest27 at pools1/4.
- `R00_MIGRATION_SUITE=foundation sh scripts/run-r00a-tests.sh`: PASS, actual .NET20
  passed/0 skipped including real signed-bearer organization commands pools1/4,
  fixture-free SQL/RLS/context regressions and restart/reapply. SDK workload warning
  retained; tests actually executed successfully.
- Pinned SDK10.0.402 locked restore, Release selected tests/publish, app+test NuGet
  audits: exit0,61 passed/5 runtime theories skipped in the fast selection (not
  acceptance until real PostgreSQL execution); no vulnerable packages reported.
- All25 offline command groups from impact workflow plus MVP/inventory/readiness
  guards PASS. Original36 migration bytes/checksums and prior82 inventory records
  verified unchanged. Nonroot organization fixture/repeated owner-input regression
  PASS, final mounts0444. Runtime nonroot/read-only/capdrop/internal/no-host-port
  hardening and protected-container/volume readback PASS.

Incidents retained, not acceptance: first runner attempt referenced wrong script
(valid RED separately retained); initial development function SET custom-GUC was
refused by PostgreSQL, replaced by tested explicit local save/restore; one build
caught xUnit2031 in a new test (fixed, analyzer not suppressed). Combined outer
execution timeout interrupted first pool1 after completed pool4; cleanup was read
back and pool1 rerun alone successfully. No interrupted run counts as passing,
no old test/budget relaxed. Final narrow Unicode corrective checks are rerun remotely.

Exact-head remote PR/dispatch jobs, steps and artifacts are recorded in the PR
only after actual execution. Parent alone merges and updates issue/Project.

### Original execution captures (SHA-256)

| Log | SHA-256 |
| --- | --- |
| `01-impact-red.log` | `26cfec58da27aaaed0dca9b2fecc0c3a99ff23bb940b16a54e21821f79230326` |
| `01-impact-green.log` | `921b60a7fd52e978fbb551cacd29df2d6708879400278e1fcc70fceeb0c6f8e0` |
| `02-directory-red-valid.log` | `fe8553215826c5837a41ecf7db39124bccf107f2f1299769ada39daf24d9f5c8` |
| `02-directory-green.log` | `d13ae46d62adce3d484b3d8b10fbc8d1cac215d5238e7564eb3912ea00cd8e88` |
| `03-create-red.log` | `05000c569cc16ff156945398818278241e44706a51cac78837054c7a388256e5` |
| `03-create-green.log` | `796f1e0393a7ed3ad3efe141ff005b81d323959a6bd8e3fddfc91b47c3a1496a` |
| `04-company-red.log` | `14751d9d432b95bbc773eee1b52a1f0828f7259ad7f06756111005f136c55a3e` |
| `04-company-green.log` | `187ee2711164ab35a841061a71f092b6b80e20159a124e7a6dff7d606019f299` |
| `05-site-red.log` | `21ed2c2a78868a3a2146e29b9080447591a2eb552aae6e7cb5c9fa264669b939` |
| `05-site-green.log` | `5a48d029b32695ab90839576d060db01c7f04cd9dff9195de32f67a763800de0` |
| `06-warehouse-red.log` | `e0b62876184036bd98d623123bdd7f51b283c21983dc0e975847b62ba71f5e19` |
| `06-warehouse-green.log` | `7137e0810d15a7df7e4d0c6d302a8d2056c2dd91df2aea87595d89358ac4aa4a` |
| `07-rename-red.log` | `6e113a79cc7913ec0b86e6ea51fcb1359bf628c4624595ee6f0b67fa0d50f0d5` |
| `07-rename-green.log` | `e0e3c68189cdcd73e632cfc8d8d600a67b9e110717be57dea95ff5022da41323` |
| `10-http-directory-red.log` | `d9efa7f7fd945e4f31ff06f26b669ccf74f3a97b62c2801d8a2b4b4fad7d44e0` |
| `10-http-directory-green.log` | `3cc04006aae241b931229dcdd5cf12b49a099a4d95f088eac3b6b71673173a1d` |
| `11-http-command-red.log` | `23deacdc334bb561ee6c0ec20de20b41994c93d29a6c3d8c137e42ec2f4c5c8a` |
| `11-http-command-green.log` | `2a36c1d9321be4cf847a72bc8b9626dbf97b4ef48dd3326f0f3402748e8f433a` |
| `12-bearer-cache-red.log` | `e82becde0c3b6ad5289835a892098112faa81d8d25ef35ba61ed71326ad77a75` |
| `13-composition-impact-red.log` | `a3273cc550a86d8e9eb8782f706712cb681b6ade818f566e1f5bc9bf2f987b0f` |
| `13-composition-impact-green.log` | `921b60a7fd52e978fbb551cacd29df2d6708879400278e1fcc70fceeb0c6f8e0` |
| `14-api-build-test-audit-green.log` | `d091728aa6d0e540eb86eaa21682422d031abaee5bcc8ece355b306f8521f9f1` |
| `16-ci-red.log` | `e1d4f166372ef584073275a2e67c823418918e570595e99f13190887362cbf34` |
| `16-ci-green.log` | `d094b1bd2c8318c96097f80c50da282add5b2972970a77046de8db6c8935f6ca` |
| `18-runtime-pool1-complete.log` | `9f4a7be01864e263b1ffd81b3a39aa8196fe73fa934633867144499b38ef12b5` |
| `19-foundation-signed-bearer.log` | `cb5ab0626e1a0d43f6060839e13f7375b2352959fb721503be56b0aee7b285a3` |
| `20-offline-guards.log` | `9226e31b08390982d6e8e14390e7d40574f2040e048d3a0aed8218ab1386160d` |
| `21-nonroot-fixture.log` | `f4482d4da1bdcc01f7d88907d4d3bbe86774bd0a2e4030d62aaea97efa2be2d4` |
| `22-http-nul-red.log` | `300a185fd2c836b4c590329b2a46c66c58520dd800a2b56311e1790e290c7929` |
| `23-unicode-red.log` | `e8eb816d5341bf764f3c22ac2d0f9f93b6f14b6178b2699b4f23299371b97b9d` |
| `24-final-pool4.log` | `b1844546707a1e28803786e21e7534add1020c2753e335c77a8a1393ce0903ab` |
