# Private persistent B03 manual acceptance

## Scope and access

Owner-authorized synthetic B03 only. On 18 October 2026 the owner reported «Ho fatto la prova privata: funziona tutto. Possiamo procedere»: positive private manual acceptance and authorization for B03 final delivery (commit/push/PR/remote CI/merge), subject to independent review and green remote checks. No commit/push/merge has yet occurred. B04+, real accounts/data, purchases and public exposure remain unauthorized. URL: https://vmi3659251.tailfcced0.ts.net:8444/ (tailnet only). Existing 443 → 9119 and B02 8443 → 18082 remain unchanged; Funnel is not enabled. Original port-80 bootstrap remains unchanged. Default frontend build is still bootstrap; the new project's build explicitly enables the private B03 UI.

Fixed project `enginia360-b03-manual`, own `postgres_data` volume and frontend/backend networks. Only web binds `127.0.0.1:18083:8080`; no API/database/Keycloak host ports. Backend network internal. Four services use `unless-stopped`, nonroot users, read-only roots, all capabilities dropped, no-new-privileges, CPU/memory/PID/log limits and pinned base-image digests. Keycloak's local proof image is rebuilt from its pinned Dockerfile. PostgreSQL persists in its own named volume; Keycloak proof H2 is tmpfs and reimports synthetic realm on restart, not production identity persistence.

Runtime file: `/root/.config/enginia360-b03-manual/runtime.env`, directory 0700/file 0600, fresh independently generated owner/app passwords. No B02 environment file was read or reused. Do not print Compose resolved configuration or inspect environment values: these contain database secrets.

Compose layers, in order: `compose.b02-test.yaml`, `compose.b03-test.yaml`, `compose.b03-manual.yaml`. New minimal manual overlay reuses `web/nginx.b02-manual.conf` read-only, including anchored case-insensitive diagnostic denial before proxy routing. No B02 file or container was changed. All case/slash/descendant database-session diagnostic probes return nginx HTML 404 without backend correlation header. Pool diagnostics remain inaccessible through the private edge.

## Operations

Run from `/root/enginia360`:

```sh
docker compose --env-file /root/.config/enginia360-b03-manual/runtime.env -p enginia360-b03-manual -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b03-manual.yaml ps
python3 scripts/test-b02-manual-edge.py https://vmi3659251.tailfcced0.ts.net:8444
python3 scripts/test-b03-manual.py https://vmi3659251.tailfcced0.ts.net:8444
```

Initial deployment built the images, started all four healthy services, then explicitly applied `/b03/00*.sql` and `/b03/90*.sql` using owner SQL access in PostgreSQL. These are synthetic baseline fixtures, not a production migration engine. Never run `scripts/run-b03-tests.sh`, `950_rls_test.sql` or `990_rollback.sql` against this persistent project: the isolated runner contains destructive rollback/fixture changes. The HTTPS manual security probe performs reads and rejected mutations only. Nominal probes additionally create synthetic destinations and edit the common synthetic identity; they intentionally leave records for acceptance rather than deleting them.

Data-preserving rollback:

```sh
tailscale serve --https=8444 off
docker compose --env-file /root/.config/enginia360-b03-manual/runtime.env -p enginia360-b03-manual -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b03-manual.yaml stop
```

Never `tailscale serve reset`, remove volumes, or stop/recreate B02/bootstrap. To resume use the same project/env/layers with `up -d --wait`, then `tailscale serve --bg --https=8444 http://127.0.0.1:18083`. Review image/source changes before rebuilding. Single-file config bind mounts can retain an old inode after edits: verify mounted content; refreshing it requires recreation of B03 web only, not data services.

## Real verification (2026-10-18 session)

- Narrow CI prerequisite review: `env -i PATH="$PATH" HOME="$HOME" TMPDIR="$TMPDIR/b03-ci-runner-fresh" python3 scripts/test-ci-runtime.py`: **3 passed**. Same minimal environment and fresh explicit TMPDIR ran `sh scripts/run-b03-tests.sh`: **exit 0**, including seven behaviors, independent common/site/warehouse insufficient-publication fixtures, B02 regression, real-fetch DOM runtime, RLS, repeated migration, isolated destructive rollback/reapply and hardening/audit. Fresh directory empty after cleanup. Log `$TMPDIR/b03-manual-prerequisite.log`. This closes the local runner-scratch portability blocker; actual GitHub CI remains unexecuted.
- Persistent HTTPS: six nominal B03 probes passed: shared identity, private destination, explicit publication, common edit, company choices and search. Added `scripts/test-b03-manual.py` passed ten alternating tenant reads plus cross-tenant/direct-ID exclusion, absent membership, spoofed headers, invalid JWT, invalid/missing/oversized fields and manipulated owner/company IDs. No pool diagnostic calls or destructive SQL on persistent B03.
- Both loopback and HTTPS edge regression passed all 12 casing/slash/descendant cases. Live `nginx -t` passed. Four live containers healthy with all hardening/restart/network/binding assertions passing.
- Existing six B02/bootstrap container IDs, start timestamps, restart counts, image IDs and health unchanged. Existing Tailscale handlers read back identical. Original bootstrap, B02 and B03 status endpoints returned 200. B02 data was never written by this task; repeated read-only B02 data dumps were stable. **Limitation:** initial data snapshot retained only an unnormalized pg_dump hash, whose random restrict token prevents a meaningful pre/post byte comparison; exact full-data equality against the initial snapshot is not claimed. Existing data volume/services were not recreated.
- Real Chromium screenshot verified rendered B03 login page over private HTTPS. No password typed via browser; authenticated browser workflow not performed. Full authenticated behavior is verified by real HTTPS probes and the separate real-fetch React/JSDOM runtime, not falsely described as browser end-to-end acceptance.
- `git diff --check` passed. No commit, push, merge or remote CI invocation.

## Guide and remaining gates

Italian guide `docs/b03-manual-scenarios.it.md`; downloadable copy `/root/.hermes/cache/scratch/b03-manual-scenarios.it.md`. Only disposable fixture login credentials, never DB secrets. Fixture editor's historical B02 username says 'senza-lettura' but B03 grants read B/common edit and insufficient site/warehouse publication scope; the guide makes this distinction explicit.

Human manual acceptance and final-delivery authorization were received on 18 October 2026. Next gate: independent review of `compose.b03-manual.yaml`, `scripts/test-b03-manual.py`, `docs/b03-manual-operations.md`, `docs/b03-manual-scenarios.it.md`, current CI changes and final evidence report; then reviewed commit/push/PR and actual remote CI. The delivery-preparation agent did not author or independently approve the manual provisioning; no fresh review verdict for these newest files was available, so it deliberately left all work uncommitted. No production IAM/fiscal validation, backup/restore proof, image vulnerability scan, durable compliance audit, availability/RPO/RTO guarantees or further increments are implied. Service restart policies do not heal a live unhealthy process. Tailscale access still depends on existing tailnet policy and host availability.
