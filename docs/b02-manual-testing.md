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

Do not reset all Tailscale Serve configuration: port 443 is unrelated. Do not remove volumes without explicit permission. PostgreSQL data persists in this project's volume; Keycloak development H2 storage is temporary and synthetic fixtures are reimported on restart. This single-host environment has no verified backup/restore or availability guarantee. No production identity approval, public release, merge or remote CI verification is implied.
