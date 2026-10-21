# B05 persistent private manual operations

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

**Consegna B05 — 19 ottobre 2026:** accettazione manuale positiva del proprietario «Ok funziona tutto. Procediamo»; review core e quattro artefatti manuali acquisite, discrepanza documentale risolta. Autorizzata la sola consegna Git/PR/CI/merge/chiusura B05, non nuovi deploy o B06. Stato al congelamento: In verifica; esito finale remoto nella PR e issue #11. Limiti e perimetro nel report B05. Le indicazioni precedenti di accettazione/review pendenti sono storiche e superate da questa registrazione. B06–B14 restano bloccati/Backlog e non autorizzati.

## Scope and manifest

Authorized synthetic D64–D67 manual acceptance only, no B06. Private trusted HTTPS `https://vmi3659251.tailfcced0.ts.net:8446/`, background Tailscale Serve to `127.0.0.1:18085`; no Funnel. Project `enginia360-b05-manual`, isolated frontend/backend networks, backend internal. Four hardened healthy services, all unless-stopped. API/identity/database have no published host ports. Existing 443/8443/8444/8445 handlers preserved.

Compose layers in order: `compose.b02-test.yaml`, `compose.b03-test.yaml`, `compose.b04-test.yaml`, `compose.b05-test.yaml`, **`compose.b05-manual.yaml`**. The last layer explicitly authorizes persistence; do not run the destructive test runner on this project. Newly generated independent database owner/application secrets are in `/root/.config/enginia360-b05-manual/runtime.env`, directory 0700, file 0600, never in Git or the guide. Initial provisioning applied only baseline/fixture migrations on the fresh B05 database; no destructive permission changes or migration rollback.

From first boot PGDATA is `/var/lib/postgresql/18/docker`, inside the sole named parent volume `enginia360-b05-manual_postgres_b05_storage` mounted at `/var/lib/postgresql`; inherited child mount replaced with Compose !override. Inspect, SHOW data_directory, readlink and mountinfo agree. No volume migration needed. Keycloak fixture H2 is tmpfs: fixture identities reimport on restart, sessions are not durable production IAM.

## Verification executed

- `python3 scripts/test-b05-manual.py https://vmi3659251.tailfcced0.ts.net:8446`: trusted HTTPS identity, contexts, tenant catalog, original pair, variable q6/p6/discount2, nine boundary arithmetic cases, line HALF_UP then group VAT, exact six-place summary, immutable payer/group, retry/conflicts, concurrency, membership/action/cross-tenant denials, invalid inputs and no partial writes. Fresh records only, no SQL/config mutations.
- `python3 scripts/test-b04-manual.py ...`: original work-order core, payer/holder, exact context/type/reference/permission isolation and retry, eight simultaneous identical creates; PASS.
- `python3 scripts/test-b02-manual-edge.py ...`: PASS case-insensitive diagnostic denial edge, including descendants. Existing shared nginx file unchanged.
- Deliberately recreated **only B05 PostgreSQL** with --no-deps --force-recreate. Original fresh variable order and summary reread exactly; summary SHA256 `7c475af105aa521a0dc5f34d8a46d61c06487e13f00891069f15754918699e14`. Storage durability is proved, not a backup/restore claim.
- Pinned Node 24 container, host network, `VITE_B05_HTTP_BASE=https://vmi3659251.tailfcced0.ts.net:8446 npm test -- --run src/B05.runtime.test.tsx`: **1 passed, 0 skipped**. Real React JSDOM with trusted HTTPS API/identity/Postgres, variable input, injected initial catalog failure recovery and reread. Host Node could not start Vitest (missing styleText); pinned Node succeeded. This is not full authenticated real-browser E2E.
- Real browser rendered private HTTPS login. No password typed, vault restriction respected; no authenticated browser journey claimed.
- Final verification: four healthy nonroot/read-only/cap-drop/no-new-privileges services with bounded memory/CPU/PIDs/logs. All 14 previous container IDs/start/restart/image/health unchanged; normalized data-only pg_dump hashes of all three older databases unchanged (only random restrict/unrestrict lines omitted). Existing Serve handlers unchanged; Funnel disabled.
- `git diff --check` PASS. Existing reviewed production source and fixtures unchanged: no misleading-label/mock correction included in this operational preparation. The low label issue remains documented by the review; it does not limit variable values.

Durable local evidence (not Git): `/root/.config/enginia360-b05-manual/evidence/` contains baseline, Serve before/after, private build log, probe output, durability references/hash, mount/path and verification summary. This is one-time host-local evidence, not continuous monitoring.

## Stop/resume/rollback

Define from repository root:

```sh
b05() { docker compose --env-file /root/.config/enginia360-b05-manual/runtime.env -p enginia360-b05-manual -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b05-manual.yaml "$@"; }
b05 ps
```

Data-preserving stop: `tailscale serve --https=8446 off` then `b05 stop`. Resume `b05 up -d --wait --wait-timeout 240`, then `tailscale serve --bg --https=8446 http://127.0.0.1:18085`. Do not reset Serve, prune/delete volumes, run down --volumes, run rollback SQL or modify earlier projects. If code/config changes require rollback, stop this project and review compatible image/schema together; never silently discard accepted writes. No tested B05 backup/restore or production recovery guarantee.

New Git artifacts: manual overlay, non-destructive probe, Italian guide and this operations manifest. Prior candidate reviewed hashes remain applicable to untouched production files; these additions require independent manual-artifact/configuration review. Downloadable Italian copy is provided separately. No commit, push, merge, remote CI or owner acceptance claimed. Tailnet ACLs, host availability, single-host limits, image vulnerability scanning, production IAM and fiscal/accounting approval remain outside this proof. GUI refresh/history limitations are explicit in the guide.
