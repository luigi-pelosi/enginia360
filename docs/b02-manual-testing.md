# Private B02 manual testing

The persistent synthetic environment uses Compose project `enginia360-b02-manual` with `compose.b02-test.yaml` and `compose.b02-manual.yaml`. It is separate from the existing bootstrap project, volumes and networks.

Access: https://vmi3659251.tailfcced0.ts.net:8443/ through Tailscale Serve, tailnet only. Existing HTTPS port 443 continues to proxy port 9119. Funnel is not enabled. Only the manual web container binds host loopback, `127.0.0.1:18082`; API, Keycloak and PostgreSQL have no host bindings. The database-session diagnostic route returns 404 at the manual nginx edge.

Runtime credentials are outside the repository at `/root/.config/enginia360-b02-manual/runtime.env` with restrictive permissions. Never commit, print or distribute that file. Login identities are disposable synthetic fixtures, not real accounts. Do not enter real data.

## Verification

The manual HTTPS integration script passed login, authorized context listing, note creation/retrieval, cross-tenant and same-tenant scope denials, forged-header denial, input validation, disabled capability, invalid JWT signature and diagnostic-route rejection. Four containers were healthy. Existing bootstrap status remained unchanged.

### Owner acceptance and UI boundary (2026-10-17)

The owner positively accepted the manual B02 test as working and instructed delivery to continue under the existing plan. This accepts only the synthetic B02 path; it does not authorize an organizational administration increment, B03, real provisioning or production use.

The note shown after creation is transient browser state. Reload clears that display because this minimal UI has no notes list, history browser or stored-note selection. This is not evidence of database deletion: persisted note retrieval was verified through the backend. The owner accepted this explicit UI limitation. Do not promise that refreshing restores the displayed note, and do not expand B02 with an administration UI or listing feature without separate authorization.

### Diagnostic casing regression (2026-10-17)

- Added `python3 scripts/test-b02-manual-edge.py [base-url]`: 12 HTTP cases cover lowercase, mixed case, full uppercase and uppercase diagnostic segment, each bare, trailing slash and nested. Assertions require nginx HTML 404 with no backend correlation header, not merely an arbitrary backend 404/401.
- RED against the existing manual deployment: six failed subcases (four backend 401 and two backend non-HTML 404). Lowercase and fully uppercase paths already returned nginx 404; fully uppercase paths previously fell through the case-sensitive generic proxy to static handling.
- Repository fix: one case-insensitive anchored regex denial before the generic proxy regex. nginx selects the first matching regex; the denial covers backend case-insensitive routing and descendants without matching sibling names.
- GREEN verified against a disposable nginx using the exact running manual image, the patched bind-mounted file and the manual frontend/backend networks: `nginx -t` passed and all 12 HTTP cases passed. The disposable container was removed.
- **Deployment blocked, not green:** `docker exec enginia360-b02-manual-web-1 nginx -t` and `docker exec enginia360-b02-manual-web-1 nginx -s reload` succeeded, but exact file readback proved the running read-only single-file bind mount still references the old inode (mounted 1313026 versus repository 1313042). Reload therefore loaded the old config; both loopback and HTTPS regressions still fail six subcases. Do not claim this boundary fixed in the live manual deployment yet. A separately authorized recreation of **only the manual web container**, without dependencies/build/volume removal, is needed to refresh the mount; no service recreation was performed in this change.
- HTTPS login, authorized contexts, synthetic note creation and exact persisted retrieval still passed. All four manual and both existing bootstrap containers remained healthy; all original container IDs, start timestamps and restart counts were unchanged. Existing `/`, `/api/v1/system/status`, `/health/live`, `/health/ready`, `/openapi/v1.json` response statuses and bodies on ports 80 and 9119 matched pre-reload snapshots (9119 status remains its existing 401). Tailscale mappings remain 443 → 9119 and 8443 → 18082.
- `python3 scripts/test-ci-runtime.py`: one test passed. `git diff --check`: passed. No commit, push, remote CI or merge; independent parent review remains required.

Rollback for this config-only change: restore the previous diagnostic denial and refresh only manual nginx after validating the exact mounted file with `nginx -t`. A reload alone cannot repair a stale file bind mount. Never restart the whole stack or remove data volumes to update nginx.

### Live deployment verification superseding the stale-mount blocker (2026-10-17)

The manual web container alone was recreated with `up -d --no-deps --no-build --force-recreate web` using the manual project and both Compose files. No dependencies or volumes were recreated. The mounted configuration now matches the repository. Both loopback and Tailscale HTTPS regression runs passed all 12 cases; an independent reviewer repeated these checks and confirmed the live correction. Page, system status, health and OpenAPI requests remained successful, and unauthorized context access remained 401. All six containers were healthy. The earlier deployment-blocked entry above is historical and is superseded by this verification.

## Operations

```sh
docker compose --env-file /root/.config/enginia360-b02-manual/runtime.env -p enginia360-b02-manual -f compose.b02-test.yaml -f compose.b02-manual.yaml ps
```

Rollback, preserving data:

```sh
tailscale serve --https=8443 off
docker compose --env-file /root/.config/enginia360-b02-manual/runtime.env -p enginia360-b02-manual -f compose.b02-test.yaml -f compose.b02-manual.yaml stop
```

Do not reset all Tailscale Serve configuration: port 443 is unrelated. Do not remove volumes without explicit permission. PostgreSQL data persists in this project's volume; Keycloak development H2 storage is temporary and synthetic fixtures are reimported on restart. This single-host environment has the one-time backup/restore proof recorded below, but no automated backup schedule or availability guarantee. No production identity approval, public release, merge or remote CI verification is implied.

## Storage remediation and recovery proof (19 October 2026)

Owner-authorized B02/B03 storage-only maintenance. No application/schema changes, business writes, builds, commit, push or merge. B04 and bootstrap remained unchanged. The final check at **09:19:16 UTC** found all **14 running services healthy**; ten unrelated container IDs, start times, images and restart counts matched the baseline. B02 containers did not change during B03 work. Tailscale Serve configuration remained exactly equal, including 443 → 9119 and private manual ports 8443/8444/8445. Loopback and trusted HTTPS checks passed; port 443's existing protected system-status response remained 401.

### Actual source and final layout

Do not infer the active volume from `docker inspect` destination strings alone. This image has `/var/lib/postgresql/data -> .`; the old child mount resolves onto the parent. Explicit read-only helper mounts proved the actual clusters were in these **named** sources, not in the initially suspected anonymous parents:

| Project | Verified original cluster volume | New active volume |
| --- | --- | --- |
| B02 | `enginia360-b02-manual_postgres_data` | `enginia360-b02-manual_postgres_storage_v4` |
| B03 | `enginia360-b03-manual_postgres_data` | `enginia360-b03-manual_postgres_storage_v5` |

Both final manual overlays explicitly set `PGDATA=/var/lib/postgresql/18/docker` and mount the new external volume at `/var/lib/postgresql`, without the old child mount. `!override` replaces inherited volume lists; use Compose supporting this tag (executed version: v5.6.0). B03 retains its read-only `/b03` SQL directory. Final PostgreSQL mounts contain exactly that named volume and, for B03 only, the SQL bind. Cluster directories remain uid/gid 70:70, mode 0700; `PG_VERSION` remains 18.

All original volumes remain. The original anonymous IDs are also retained, although they are **not the cluster sources**:

- B02: `96126a1e737c8370a7b23d82cba191aefe45bda1c8dd55da481ac0d65ff2b239`.
- B03: `9bb370d287a4485ffd189619f9240e3a263582da16bb459804fb0114c1e205c1`.

Stopped/never-started holders `enginia360-b02-retained-pre-v3` and `enginia360-b03-retained-pre-v3` reference the original named and anonymous volumes read-only. Additional B03 holder `enginia360-b03-retained-pre-v5` is retained. Unverified/failed-attempt volumes, including B02 `postgres_storage_v2`, B02 `postgres_storage_v3`, and B03 `postgres_storage_v4` (with their project prefixes), were not reused or deleted. Never run volume deletion, pruning, or `down -v` as cleanup.

### Protected backups and evidence

Root directory: `/root/.local/share/enginia360-storage-remediation/20261019` (0700; evidence/archive files 0600). Archives and restore proofs are outside Git:

| Project | Archive relative to root | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| B02 | `b02/base.tar` | 49550336 | `b69ad31821b2104178e06b454a6bafaa263b13497e99ed82f0a6af56dec2428c` |
| B03 | `b03/base.tar` | 49788416 | `2ce139eca0517cfc2ed491b1304e94488b77d4dbd2e7d99a6ff3b85bb5e83e9c` |

Both archives passed `pg_verifybackup`. B02's earlier actual isolated restore (`enginia360-b02-restore-proof`, retained stopped) matched the current post-rollback baseline before migration; the archive was independently re-extracted and reverified in `enginia360-b02-backup-verification-v4`. B03 was backed up consistently and actually started/restored in isolated container/volume `enginia360-b03-restore-proof-v3`, then stopped and retained. All table counts, canonical sorted-row SHA-256 values and normalized schema hashes matched the respective live baseline (8 B02 tables, 12 B03 tables). Schema normalization removes only pg_dump's random restrict/unrestrict lines.

The same comparisons passed after copying, after deliberate PostgreSQL container replacement, and in final verification. B02 still has 9 context notes with SHA-256 `631d5836c41fc49475ded42c83fae78fad7978f7790e76a2263084db743db2dc`; schema SHA-256 is `00057d2f422b9f92c2113468e8676aeed539cf9f244fe62d7ca7fef5679e32a2`. B03 schema SHA-256 is `b01164cb3a80c51757f63c77a1e85fe89291d544a3ff7a6226477aec66b30d70`.

`continuation/` contains original overlays, full container IDs, source inventory, byte/mode/ownership and control-file comparisons, event timestamps, migration results, before/after/final table references and authenticated response hashes. `final-result.json`, `final-containers.json`, `b02-migration.json`, `b03-migration.json` and `*-reference-final.json` are the summary evidence. Executed helpers are archived under `continuation/helpers/`; do not rerun the migration helper blindly (it intentionally requires fresh volumes and preserves attempt-specific names).

### Exact execution and operational constraints

The migration used one project at a time. Only its API writer was stopped, then PostgreSQL was stopped cleanly with `stop -t 60 postgres`. A network-isolated helper mounted the verified source `readonly` and a fresh target read-write, copied the entire volume with `cp -a /source/. /target/`, and checked PG_VERSION, stopped control state, absent postmaster PID, all cluster bytes, numeric ownership/modes, symlink target and matching allocated size. No Docker host Mountpoint was used. Successful copy sizes were 64784 KiB for B02 and 65012 KiB for B03 (whole volume). Only PostgreSQL was recreated; existing API containers were restarted, not rebuilt or replaced.

Executed commands from `/root/enginia360` included:

```sh
python /root/.hermes/cache/scratch/storage-migrate-v3.py b02
python /root/.hermes/cache/scratch/storage-b03-backup-restore-v3.py
python /root/.hermes/cache/scratch/storage-migrate-v3.py b03
python /root/.hermes/cache/scratch/storage-final-verify.py
```

Scratch paths are session execution locations, not permanent recovery dependencies; archived copies and exact evidence remain in the protected root. Both projects passed `storage-live-check.py`, authenticated original-record GET/hash comparison, anonymous 401/cross-tenant 404 checks, and all 12 diagnostic-edge cases over both loopback and HTTPS. No accepted application mutation was sent. The original B02 note and B03 counterparty were read again after deliberate PostgreSQL recreation. B04's full data/schema reference remained identical. Application/UI suites and remote CI were not rerun for this storage-only operation.

### Consistent backup and isolated restore procedure

Use a fresh protected directory/archive, exact running image ID and a fresh restore volume/name. Never overwrite existing evidence. The archive command used was:

```sh
umask 077
# Set PG to the selected project's PostgreSQL container; BACKUP to a new protected file.
docker exec "$PG" sh -c 'exec pg_basebackup -U "$POSTGRES_USER" -D - -Ft -X fetch --checkpoint=fast' > "$BACKUP"
```

Restore into a new Docker volume, not a Docker-host path: helper `docker run --rm -i --network none --read-only --cap-drop ALL --cap-add CHOWN --cap-add FOWNER --cap-add DAC_OVERRIDE --security-opt no-new-privileges --mount type=volume,src="$RESTORE_VOLUME",dst=/restore --entrypoint sh "$IMAGE_ID" -ec 'tar -xpf - -C /restore; chown 70:70 /restore; chmod 700 /restore; pg_verifybackup /restore' < "$BACKUP"`. Actual helpers also bounded memory, CPU and PIDs. Start a separate restore container using that volume, uid/gid 70:70, read-only root, dropped capabilities, tmpfs socket/temp directories, `--network none`, and `postgres -D /restore -c listen_addresses=`. Use only SQL user/database identifiers from the selected live database, not its credentials. Compare every table and normalized schema against the baseline, then stop and retain the proof. The complete executed B03 backup/restore helper is archived above.

### Recorded maintenance windows and rollback

These are **stop-request to authenticated successful-read bounds**, not continuous outage measurements. Times are UTC on 19 October 2026:

| Project / attempt | Start | Verified readable | Bound |
| --- | --- | --- | ---: |
| B02 failed copy verifier, original restored | 09:10:45.794 | 09:11:27.921 | 42.127 s |
| B02 successful migration | 09:12:39.155 | 09:13:03.897 | 24.742 s |
| B02 deliberate durability recreation | 09:13:03.897 | 09:13:21.465 | 17.568 s |
| B03 failed edge check, original restored | 09:14:31.153 | 09:15:12.608 | 41.454 s |
| B03 successful migration | 09:16:43.492 | 09:17:13.545 | 30.053 s |
| B03 deliberate durability recreation | 09:17:13.545 | 09:17:36.575 | 23.030 s |

B02's first verifier incorrectly followed the image's `data -> .` symlink; source was untouched and rollback/hash/authenticated-read verification passed. The verifier was tested without following symlinks before using a fresh target. B03's first edge check encountered nginx's cached old API address while Docker DNS converged; rollback and original-data/authenticated-read verification passed. The successful attempt required three consecutive edge-ready responses before authentication, bounded to 30 checks two seconds apart; authorization/hash failures are not retried. Failed-attempt evidence remains separate.

For rollback before accepting any later writes: stop **only the selected API**, cleanly stop its PostgreSQL, restore that project's exact `continuation/b02-manual-original.yaml` or `b03-manual-original.yaml` to its manual overlay, then use its documented project/env/Compose layers with `up -d --no-deps --no-build --force-recreate --wait postgres`. This remounts the retained original `postgres_data` cluster. Verify full table/schema references before `up -d --no-deps --no-build --wait api`; allow bounded DNS convergence and repeat the authenticated original-record GET. Do not alter Tailscale, web, identity service or any other project. Never initialize an empty database as fallback. If new writes have occurred on the migrated volume, the old source is stale: retain both and reconcile/restore under new authorization rather than discarding those writes.

One-time same-host recovery proofs are not scheduled/off-host backups, production identity durability, availability or RPO/RTO guarantees. No volumes were deleted or pruned; no real business records or B04 business behavior were changed.
