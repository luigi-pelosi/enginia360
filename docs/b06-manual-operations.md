# B06 persistent private manual operations

## Status and scope

**Current delivery update:** the owner reported “Funziona. Procediamo” after private B06 manual acceptance and authorized B06-only commit/push/PR/remote CI/merge. The parent reported independent PASS for the exact core/lifecycle candidate and separately for all five manual artifacts. Pending statements below describe preparation-time history, not a new approval requirement. Acceptance is the owner's report, not an agent-run authenticated browser journey. UI recovery/label, synthetic identity, retained storage and production limitations remain unchanged; no B07 authorization. Actual remote delivery results belong to the linked PR/issue #12. No persistent service, SQL, storage, backup or Tailscale changes are needed for Git finalization.

19 October 2026: owner-authorized private manual preparation **deployed and left running**, after the parent-reported final independent core PASS. This does not mark B06 complete. Independent review of these new manual artifacts/configuration and owner manual acceptance remain pending. No commit/push/merge, remote CI, B07 behavior or management/replenishment endpoint introduced.

URL: `https://vmi3659251.tailfcced0.ts.net:8447/`. Project `enginia360-b06-manual`; its own frontend/backend networks (backend internal), own named storage, no shared old database. Background Tailscale Serve HTTPS 8447 proxies only `127.0.0.1:18086`; no Funnel. Existing 443 and 8443–8446 handlers preserved exactly. Only web publishes a loopback host port; identity/API/database publish none. All four services are healthy, restart unless-stopped, nonroot/read-only/drop ALL/no-new-privileges, bounded CPU/RAM/PIDs/logs.

Compose layers: B02/B03/B04/B05/B06 test layers followed **last** by `compose.b06-manual.yaml`. This manual overlay is the sole exception authorizing use of those technical base layers on this fresh persistent project. It replaces B06 PostgreSQL tmpfs with the proper named parent volume and retains only socket/tmp tmpfs. Do not use the test layers alone on retained data.

New independent owner/application database secrets: `/root/.config/enginia360-b06-manual/runtime.env` (0600; parent directory 0700), never in Git or the user guide. Pool size 8. No old credential file was read; older data baselines used in-container environment references without printing values. No Compose environment rendering, secrets output or backups staged.

PGDATA explicitly `/var/lib/postgresql/18/docker`, sole data volume `enginia360-b06-manual_postgres_b06_storage` at `/var/lib/postgresql`, no anonymous child volume. Actual inspect, SHOW data_directory, realpath, ownership and mountinfo recorded in private evidence. Initial named-volume ownership comes from the image's precreated PostgreSQL directory, no privileged/root helper or migration from an old volume. Root/image dirs and data observed as UID/GID 70:70; initialized data mode 0700. Keycloak synthetic H2/session data remains tmpfs and reimports fixture accounts; this is not production IAM.

## Executed checks and exact limits

- Fresh database only: applied B03/B04/B05/B06 baselines and synthetic fixtures once. No acceptance runner, TRUNCATE, rollback, old-row stock UPDATE or permission revocation. No acceptance reset/trigger controller installed; zero user Inventory triggers verified.
- `python3 scripts/test-b06-manual.py URL WH_PARTIAL WH_RACE WH_EXTRA`: PASS, real HTTPS identity/API/nginx/Postgres. Only fresh API scenarios written. Three private newly INSERTed warehouse/stock/scope fixtures with initial physical 2/2/3 isolate probes from owner warehouses. Explicit 2 of 3 yields remaining 1, physical unchanged/available down; request 3 with available 2 rejected with exact unchanged state; identical command retry 200 and changed payload conflict. q6 invalid/positive microquantity, stale catalog and wrong header/warehouse scopes denied. Beta/outsider/no-read history and command denied. Four new orders/lines compete for a new stock pool: one 201, three 409, committed total 1.5 against physical 2. No controlled trigger or timing hook; this is bounded concurrency, not the earlier isolated barrier proof.
- Additional explicit partials 0.000001, 1.999999, 1 against initial fresh stock 3 succeeded, each idempotent; cumulative 3 and further command rejected. No replenishment or modification of prior physical stock, including probe stock.
- `python3 scripts/test-b06-manual.py URL --permissions WH_READ WH_CREATE`: PASS. Two more freshly INSERTed warehouses with only read or only create grant. Read-only allows GET, denies POST; create-only permits microquantity POST/retry but not GET/history. Readable other warehouse excludes unauthorized reservation details while preserving global line residual. No existing permission or owner row modified.
- `python3 scripts/test-b02-manual-edge.py URL`: PASS case-insensitive diagnostic path and descendant denial. Actual API image environment Production and DOTNET_EnableDiagnostics=0 verified. Synthetic login is deliberately enabled; diagnostic database-session is blocked by the private edge, not claimed removed from API routes. No backend host port.
- Real Chromium rendered HTTPS login; saved screenshot. Vault list had no saved login; no password typed, no authenticated browser journey claimed. Existing core React/JSDOM/HTTP and UI/unit/build results are inherited, not rerun on this persistent project (which would consume owner stock). Known UI heading still says B05/case001; Italian guide explains it without changing reviewed production code. Warehouse 100102 retains historical label “Alfa Nord Magazzino senza scope”, despite current B06 exact grants.
- Two deliberate **B06 PostgreSQL-only** recreations (second after the additional permission fixtures), authenticated readback of exact original order/line/commercial snapshot/reservation, unchanged all-data dump and stock hashes. Other B06 three container IDs unchanged. No assertion of continuously measured downtime or backup/restore.
- Final preservation: **23 preexisting container IDs/start/restart/image/health records unchanged**, including the original 18 persistent/bootstrap containers and five other containers observed at baseline. Four older persistent database normalized data-only pg_dump hashes unchanged (omit only random restrict/unrestrict lines). Prior Tailscale handlers exactly unchanged and Funnel false. Legacy `enginia360-b06-acceptance_postgres_data` retained untouched, never mounted or deleted.

## Durability evidence

Durable private evidence: `/root/.config/enginia360-b06-manual/evidence/`. Contains build/migration logs, preexisting read-only baselines, fresh fixture INSERT SQL/IDs, probes, original durability reference, storage topology/ownership, Serve readback, verification JSON, browser screenshot and exact one-time verification helper copies. No credentials in those artifacts; runtime env is separate and must never be attached.

SHA-256 after final PostgreSQL recreate:

- Reservation/state canonical sorted compact JSON: `0ea2002ffb69e449d91157c77c92c80b864c39d33ff69aedb98ec7d1251d6442`.
- All B06 data-only normalized dump: `383e5a9c1c974e360db48874dd3db62c275b96558f05cd31bc0041fef260a1e3`.
- Sorted stock row JSONL: `a8ddffe5da59e96f8084b64b3e583ccb23f1c4d23f79e55355f4a0dada407434`.

Final stock: eight rows, physical total 17 (canonical three rows total 6 plus five new probe rows total 11), unchanged by reservations and recreations. Canonical A/B/Beta rows have no reservations: **owner Alfa A and B each remain physical/available 2**. The probe rows are named B06 probe and should not be used for the guided owner acceptance. Later owner writes legitimately change these evidence hashes; do not reset to reproduce them.

## Operator commands, stop/resume and rollback

From repository root:

```sh
b06() { docker compose --env-file /root/.config/enginia360-b06-manual/runtime.env -p enginia360-b06-manual -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b06-manual.yaml "$@"; }
b06 ps
```

Data-preserving stop: `tailscale serve --https=8447 off`, then `b06 stop`. Resume: `b06 up -d --wait --wait-timeout 240`, then `tailscale serve --bg --https=8447 http://127.0.0.1:18086`. Never reset Serve or change the older handlers. Never run acceptance runners, rollback SQL, volume prune, `down --volumes`, TRUNCATE or stock resets on this project. Retain the runtime file securely for resume.

The smoke probe is not a self-provisioning fixture manager: main mode requires three newly provisioned, unused synthetic scoped warehouses (physical 2/2/3); it fails closed on occupied stock. Permissions mode requires two newly provisioned exact read-only/create-only warehouses. Do not rerun it with old probe IDs or ordinary owner stock. Private fresh-fixture SQL evidence shows exactly what was INSERTed, not an authorized general replenishment procedure. No scheduled controller remains running.

Rollback after any new accepted write requires compatible image/schema review and reconciliation, not blind restoration of a stale database. Stop this project only, retain volume/evidence, review rollback separately. No backup/restore drill, host-failure guarantee, production IAM, image CVE scan, remote CI or fiscal/accounting approval claimed. Single host/tailnet ACL/network/power and volatile identity sessions remain limitations. Italian guide documents explicit partial/insufficiency/retry/read/refresh limits. Downloadable PDF outside Git; source guide in repository. Independent manual-artifact review and owner acceptance precede Git delivery.
