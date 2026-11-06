# MVP10 — source-supported release procedure

**SOURCE_COMPLETE_UNVERIFIED**. All commands below are FINAL-phase entrypoints, NOT executed by the source worker. Publication PENDING; no archive/binary/image was built here. [Finite contract](mvp10-release-contract.md), [machine-readable readiness](mvp10-readiness.json), [sanitized historical functional proof](mvp10-functional-baseline.json).

## What can be delivered

Three managed assets: `enginia360-source.tar.gz` (explicit committed allowlist), `provenance.json` (source file hashes/modes/sizes, exact tested candidate and merged commit/TREE, actual remote jobs/steps/artifact IDs/digests, minimized local proof hashes), `SHA256SUMS` (archive and provenance). No binaries, container image registry publication, deployment bundle, database, secrets, generated builds or fixture credentials. All backend modules remain in source because the existing API project composes them; repository presence is not an MVP feature or acceptance obligation.

Source inventory is fixed in `mvp10-source-policy.json`; no recursive worktree copy. A conservative static dependency-closure guard requires every committed `src/` and `frontend/` input, Dockerfile COPY source and explicit project/import reference (including project locks); omitted inputs and unsupported new COPY/reference/local-package forms refuse packaging rather than produce an incomplete archive. Per-input omission regressions run without assembling real candidate assets. This proves source completeness, not an extracted-source build; the parent must perform that actual build after merge. It includes API/project/locked module sources, Next source and credential-free component tests needed by its existing Dockerfile, all46 published migrations, role bootstrap/config validator/migrator and selected owner tools and release docs. It omits historical test runners, browser/IdP/DB fixtures and all Compose manifests. Source integration tests require the full pinned Git checkout, not pretending the minimized archive is a complete historical acceptance checkout. In the full repository every synthetic fixture is TEST ONLY, never an operational credential. GitHub also exposes automatic full tag source downloads, distinct from this managed sanitized archive: review that boundary before creating any public tag.

Repository was freshly read as **public**, no tags/releases on 6 November 2026. That is not permission to upload private evidence. Re-read visibility immediately before packaging and publication; explicitly set `--visibility public` only if still approved. Parent reviews all exported metadata and automatic source downloads. Packaging copies hashes and typed metadata, NEVER raw proof files, runtime ZIPs, reports, dumps, screenshots, cookies or credentials. Credential-pattern refusal is a defense, not a guarantee; inspect the final allowlist/content before distribution. Local evidence paths stay in the private review input, never the public provenance.

Version derives from actual `frontend/package.json` (`0.1.0`) as `v0.1.0-mvp.10.rc.<merged-12-sha>`; this is a new bounded prerelease suffix, not production 1.0 or an existing tag convention. Do not modify dependency/package versions just to manufacture a release number. No application license grant is inferred from GitHub visibility; dependencies retain upstream terms, including `frontend/shadcn-LICENSE.txt`.

## Final validation / parent only

This increment changes packaging/docs/guards only, not business/runtime/dependencies/images/migrations. Run release-tool tests (real scratch Git archive, deterministic bytes, corruption/refusal checks, controlled remote API fixtures), selector positive/negative/whole-point/mixed cases and current-status/preservation guards. Mock remote fixtures prove parser behavior, NOT real GitHub provenance: actual packaging separately performs read-only `gh api` calls. Do not repeat MVP09/B04–B14 unless a genuine business dependency changes. Keep current dependency/security checks appropriate to actual sources/locks; previous MVP09 audits are inherited, not fresh MVP10 audits. Existing CI impact job also runs its retained guards; no check is disabled or early docs PR required.

```sh
# Only after source completion; use private durable evidence and scratch outside checkout.
python3 -I scripts/test-mvp10-release.py
python3 -I scripts/test-mvp10-impact.py
python3 -I scripts/test-mvp09-contract.py
python3 -I scripts/test-mvp-baseline.py
python3 -I scripts/test-mvp-impact.py
# Determine WHOLE base-to-candidate changes, not only the dirty overlay after a commit:
python3 scripts/select-ci-impact.py --base 9326d19abc97d1eb249d0a1abecdc1ffd4cd3289 --head "$CANDIDATE"
# Parent runs the selected existing PR guards, corrects failures, commits/pushes,
# reads exact-head remote CI and guarded-merges; no automatic main CI assumed.
```

Current dependency/security checks are not waived. At the parent FINAL gate, reuse the exact pinned images already defined in source, in ephemeral build/audit helpers only (no target environment). The actual existing commands are frontend `npm ci --ignore-scripts --no-fund && npm audit --audit-level=low` and locked SDK `dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet list src/Enginia360.Api package --vulnerable --include-transitive && dotnet list tests/Enginia360.Api.Tests package --vulnerable --include-transitive`. Record their real exit/output and vulnerabilities separately; a new advisory is an applicable security finding, not a reason to execute unrelated B04–B14. The new Python code uses only stdlib, so no new dependency installation/audit framework is needed. No claim of fresh audit execution is made here.

The finite release-only selection uses the existing `affected-mvp-offline` job, plus `impact`. Unknown executable paths fail closed. Adding a real runtime producer restores its original security/isolation/runtime consumers; source docs never waive an applicable failure.

### Reviewed private input (create only with actual FINAL values)

`--review` is strict JSON with exactly `schemaVersion: 1`, `runs`, `proofs`:

- Each run: `id` (real numeric GitHub run ID), `role` (`release-validation` for the tested MVP10 candidate; `inherited-functional` for MVP09), `requiredJobs` (exact nonempty job-name list from the actual selected workflow, NOT every job that happens to pass), `artifacts` (list of `{id, path}` pointing to actual downloaded ZIP bytes; empty allowed for current offline jobs without artifacts).
- Each proof: `{name, path}`, sanitized public basename plus private existing regular-file path. Parent includes its exact-head job/step/source/merge readbacks and impact applicability ledger; content is hashed but not exported. Review all labels as metadata too.
- For inherited functional proof use run `42194906237`, head `e36697723d9d8ae96022cd0779bcc83958fc7f9f`, all24 exact successful job names and 23 real ZIP IDs/paths from the preserved parent manifests. The source baseline retains their original hashes and expiry metadata. It is a past execution on its own tree, not a new release-head runtime pass. Parent verifies unchanged business paths before relying on it.
- Never fill a fake sample manifest with invented IDs/digests. Parent assembles this small review input from authoritative remote reads and its actual private ledger. The tool refuses wrong heads, required skipped/missing/ambiguous jobs or steps, mismatched/expired remote artifacts and local digest differences. Source packaging can use retained historical proof hashes after URL expiry only via a separately reviewed, explicit provenance extension, NOT by silently suppressing expiry checks.

```sh
# Final only, after exact candidate CI + guarded merge/readback. Both are FULL 40-char SHAs.
# FINAL_ASSETS must be a NEW private directory OUTSIDE the checkout.
python3 -I scripts/mvp10_release.py build --commit "$MERGED_MAIN" --candidate "$CANDIDATE" \
  --review "$PRIVATE_REVIEW_JSON" --output "$FINAL_ASSETS" \
  --visibility public --public-metadata-reviewed
python3 -I scripts/mvp10_release.py verify --output "$FINAL_ASSETS" --repo "$PWD"
(cd "$FINAL_ASSETS" && sha256sum -c SHA256SUMS)
```

`git archive` reads exact committed blobs; uid/gid/mtime, ordering and gzip header are normalized. Repeating source packaging with the same committed inputs under the same Python/zlib yields the same source bytes; provenance may differ if fresh remote metadata changes. Hash the bytes actually delivered. Git archive is filtered: `tree` denotes the whole committed tree, `files` the exact managed source subset, not a claim that the subset itself has that Git tree ID. Provenance cannot hash itself recursively: `SHA256SUMS` covers provenance, whose assets/files cover the source archive. Offline verification establishes integrity; add `--repo` for exact Git comparison. It does not independently authenticate a publisher or refresh remote jobs.

### Parent publication readback

Only parent, after checking source rights/public boundary, prerelease status, exact tag target, source bundle content, no credentials and all final evidence: create tag on the recorded merged commit and a **prerelease**, upload only the three managed assets. No automatic publication command is executed by CI/tool. Read back exact tag/commit, release `prerelease=true`, visibility, assets/names/sizes; download managed assets into a fresh directory and rerun verification plus compare original SHA256s. A release API success is not enough. Record release/asset IDs, tag and download hashes in the durable private ledger and issue/milestone. Artifact retention URLs may expire; retain this minimized provenance, not a promise of permanent Actions access.

#149 remains OPEN for applicable target/operational proof; proposed finite **software-publication milestone/child** covers criterion1 only. Do not silently close #149 or tick ready-use from a tag. Publication and commissioning are independent. Next single bounded question, only when commissioning begins: exact target/private-access boundary and responsible operator. The [readiness matrix](mvp10-readiness.json) preserves concrete remaining inputs rather than re-asking every settled business policy.

## Install prerequisites and actual build entrypoints (NOT deployment)

- Linux, Git and Python3 standard library for packaging; authenticated `gh` read access for final provenance; no Docker/service/network beyond GitHub metadata is required to package. Full SHA objects and clean checkout required. No install is run by the packaging tool.
- For building locally later: pinned Node 24.22.0 (not host Node18), .NET SDK10.0.402/global.json, ASP.NET10.0.13, Next16.4.4/React19.3.1 with committed npm/NuGet locks. `frontend/Dockerfile` and `src/Enginia360.Api/Dockerfile` contain exact existing SHA256-pinned images. PostgreSQL18.0-alpine3.22 digest is in `postgres.runtime.Dockerfile`; migrate using the committed manifest and existing stdlib engine, not ORM-generated SQL. No new dependencies/images.
- Build commands reuse existing definitions, create images only, and do not start services:

```sh
# In an extracted source archive / pinned checkout, ONLY in authorized final build phase:
docker build -f src/Enginia360.Api/Dockerfile -t enginia360-api:local-source .
docker build -f frontend/Dockerfile --target runtime -t enginia360-next:local-source frontend
# Equivalent frontend commands INSIDE the pinned Node image/workspace:
# npm ci --ignore-scripts --no-fund && npm audit --audit-level=low
# npm test && npm run build && npm run typecheck
# API Dockerfile: dotnet restore src/Enginia360.Api --locked-mode
# dotnet publish src/Enginia360.Api -c Release --no-restore -o /app /p:UseAppHost=false
```

These `local-source` labels are local examples, NOT claimed built release images or production registry refs. `.NET` API/test transitive audits and frontend audit remain part of the applicable parent final lane; use exact pinned images from source. No fake audit pass is attached to this increment.

This is **not a production Compose** distribution. Root `compose.yaml`/README bootstrap commands are historical public-HTTP/Vite setup, NOT new MVP installation; `compose.mvp02c-test.yaml` and runners are isolated synthetic acceptance with ephemeral DB/IdP, never an operational installer. The minimized bundle intentionally omits Compose and historical fixture runners. Existing `migrator.runtime.Dockerfile` is a combined test image with many test-file COPY inputs: it is NOT included or claimed buildable from the minimal bundle. Use `scripts/apply-runtime-migrations.py` with PostgreSQL client/Python3 in a separately authorized target contract, not an invented production image.

Before operational install one must contract the exact PostgreSQL nonprivileged owner/application roles and technical outbox role/TLS CA/secret delivery, manifest/ledger state, API ConnectionStrings/Authentication/BrowserSessions, trusted OIDC/MFA/bootstrap/revocation, Next `ORGANIZATION_BACKEND_ORIGIN`/`ORGANIZATION_PUBLIC_HOST`, private reverse proxy/TLS/CSRF, resource limits, backup/maintenance. Actual names are visible in existing sources; values are not guessed. API exposes only to private backend; Next never reads DB directly. Do not use fixture credentials, a default first-user admin, a live secret in a shell argument, or the old unauthenticated HTTP bootstrap for login. No source command provisions target users/data or enables writers.

## Upgrade / rollback preserving state

No migration added by MVP10. Preserve all46 published SQL files/checksums/manifest, ledger and facts; no change to locks/images. Before a separately authorized target upgrade: record previous/current commit/TREE and image digests/config references, target role/ACL/schema/manifest-prefix readback and a verified recoverable backup of DB plus IdP/keys/config; secrets outside Git. Stop if target/data authority differs or any published prefix/hash fails; no automatic backfill, reset or silent authority switch. Existing migrator refuses untracked nonempty DBs, unsafe roles and nonmatching history and locks the manifest application. It is not a production commissioning permission.

No downgrade SQL. A packaging rollback simply withdraws/corrects the prerelease via parent-controlled tracking while retaining provenance. Application rollback requires a separately authorized maintenance window: stop writes, use the previously verified compatible source/image/config and retained database; prove old code supports the current schema/facts first. If incompatible, forward-fix or separately approved restore with explicit data-loss boundary; do not drop new tables, edit migration ledger, delete confirmed documents or apply older migration scripts. Back up before touching state; no claim that a synthetic same-host restore proves off-host/RPO/RTO. Never prune/remove retained volumes or restart protected containers/Tailscale as part of this release.

## Readiness and limitations

MVP09 is functionally verified for the seven-domain synthetic boundary. D99 company explicit negative-stock opt-in/default block; D100 stable-passage quota and stock only on destination confirmation (Draft reserves neither physical stock nor capacity); D101 every mixed source path currently permits the same-company destination, cross-site explicit/fresh warehouse. D97 admin is not a business grant; D98 starts disabled/roleless. No confirmed cancel/reopen/reset/compensation, fiscal numbering, valuations, tax approval or persistent retry across reload. Historical old HTML/noJS/tall-renderer incidents retain unproven causes and are not operational readiness. Old run42116253372 remains FAILED/interrupted history, not an accepted full legacy campaign.

Operational target/access/provider/bootstrap/revocation, independent backups/keys/RPO/RTO, privacy and monitoring/maintenance remain OPEN. Existing OPE01–OPE05 requirements and D47–D57 answers remain unchanged; MVP10 does not invent new default policies or rewrite the old registry. No public service exposure, purchases, real data/onboarding, new persistent environment or deployment authorized. The release alone is not ready-for-use.
