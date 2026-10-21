# B04 private persistent manual operations

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

## Boundary

Authorized D62/D63 synthetic acceptance only. URL https://vmi3659251.tailfcced0.ts.net:8445/ (tailnet only, trusted TLS verified). Fixed project `enginia360-b04-manual`; web only `127.0.0.1:18084:8080`. Background Tailscale Serve 8445 proxies that loopback endpoint; no Funnel. Existing 443/8443/8444 handlers unchanged. Default bootstrap UI remains default; B04 test layer explicitly selects private UI.

Runtime `/root/.config/enginia360-b04-manual/runtime.env`: directory 0700/file 0600; independently generated owner/app DB secrets, not reused from older stacks. Never print resolved Compose environment or DB credentials. Guides contain disposable fixture logins only.

Compose order: `compose.b02-test.yaml`, `compose.b03-test.yaml`, `compose.b04-test.yaml`, `compose.b04-manual.yaml`. All four services restart unless-stopped; nonroot, read-only roots, all caps dropped, no-new-privileges, bounded memory/CPU/PIDs/logs. API/Postgres/Keycloak expose no host ports. Project-only frontend/backend networks; backend internal. Inherited nginx manual configuration denies database-session diagnostic path, descendants and case variants before proxy dispatch. All 12 HTTPS edge probes passed; mounted config matched host bytes and nginx -t passed.

## PostgreSQL 18 persistence finding and correction

Live verification found inherited PostgreSQL 18 default PGDATA `/var/lib/postgresql/18/docker` outside inherited named mount `/var/lib/postgresql/data`, initially using an anonymous volume. **B04 overlay explicitly sets `PGDATA=/var/lib/postgresql/data/18/docker`.** Only new B04 API/Postgres were stopped; an offline copy preserved the initial B04 cluster into its named volume, then only B04 Postgres was recreated and API restarted. The first attempted `/var/lib/postgresql/data` setting failed because the copied cluster was nested; corrected to the verified nested location. Final SHOW data_directory confirms named-volume location; initial pre-recreation order `a54c1967-7487-4fcb-9771-00f946604ec8` still returned 200 after recreation. Old anonymous B04 volume retained, not pruned; current image can still allocate an unused anonymous parent volume. No previous persistent environment SQL/service changes were made. **Inherited B02/B03 mounting pattern deserves separate authorized review; it was not changed here.**

## Commands / non-destructive rollback

From `/root/enginia360` define:

```sh
b04() { docker compose --env-file /root/.config/enginia360-b04-manual/runtime.env -p enginia360-b04-manual -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b04-manual.yaml "$@"; }
b04 ps
python3 scripts/test-b04-manual.py https://vmi3659251.tailfcced0.ts.net:8445
python3 scripts/test-b02-manual-edge.py https://vmi3659251.tailfcced0.ts.net:8445
```

Manual probe creates new synthetic B04 orders and rejected invalid commands only; leaves accepted orders. No B02/B03 business mutations. Initial provisioning applied only B03 baseline/fixtures and B04 010/900 into the fresh B04 database. Never run isolated acceptance runners, 910/950/990 SQL, permission-narrowing SQL or destructive rollback on this persistent project.

Data-preserving stop:

```sh
tailscale serve --https=8445 off
b04 stop
```

Resume same env/project/layers with `b04 up -d --wait --wait-timeout 240`, then `tailscale serve --bg --https=8445 http://127.0.0.1:18084`. Do not reset Serve, use down --volumes, delete/prune volumes, or recreate earlier environments. Review source/images before rebuild. Bound config inodes must be verified after edits; recreate only B04 web if necessary. Named-volume persistence is not a tested backup/restore procedure.

## Actual evidence

- HTTPS manual probe passed context/types, direct creation/reread/retry/conflict, zero-ID rejection, eight simultaneous identical requests, cross-tenant command-ID conflict; fresh Alfa/Beta orders, exact company/site authorization, owner/payer distinction, disabled/foreign configuration, malformed/missing references, membership/action denial, anonymous/header spoof denial and ten alternating tenant reads. No diagnostic endpoint used. Concurrency ran with normal pool size 1; pool-8 proof belongs to isolated prior runner, not this persistent claim.
- React JSDOM with real HTTP through B04 nginx/API/Keycloak/Postgres: **1 passed, 0 skipped**. Payer remains selected when vehicle changes; POST then GET confirms saved resource. Real browser rendered private HTTPS login; no password typed and no authenticated browser E2E claim.
- Final runtime verifier: four healthy hardened unless-stopped containers, loopback-only port, isolated networks/named DB storage, secret modes and trusted TLS. Earlier bootstrap/B02/B03 container IDs/start times/restart counts/image IDs/health identical to pre-provision snapshot; B02/B03 normalized data-only pg_dump SHA256 identical (only randomized restrict/unrestrict lines omitted). Existing Serve handlers identical, no Funnel. Bootstrap and B02/B03/B04 health HTTP 200.
- Local evidence `/root/.hermes/cache/scratch/b04-manual-evidence/`: before snapshot, Serve before/after, provision log and verified.txt; scratch verifier/provision programs adjacent. Initial order reread after DB recreation independently passed. `git diff --check` passed.

Italian guide `docs/b04-manual-scenarios.it.md`, downloadable copy `/root/.hermes/cache/scratch/b04-manual-scenarios.it.md`.

## Remaining gates / limitations

The owner has now accepted the B04 manual result with «Ok funziona. Procediamo» after recovery completion (19 October 2026), authorizing delivery of **B04 only** without further owner confirmation. The independent manual-artifact PASS is reported in the parent handoff; its chronology limitation remains: earlier statements here describe provisioning, not an assertion that no later B02/B03 maintenance occurred. B02/B03 subsequently received separate authorized storage-only recovery; its verified named-volume sources, one-time restore proof and final preservation evidence are documented in `docs/b02-manual-testing.md` and `docs/b03-manual-operations.md`. That maintenance did not change B04 data/schema or Tailscale. The current maintenance overlays and updated evidence documents still require final independent review, followed by reviewed commit/push/PR and actual remote CI before closure. No commit/push/merge or B05 has occurred in this preparation pass. Remote CI is not claimed here. Synthetic identity only, single-host availability, no B04 verified backup restore, production IAM, fiscal validation, vulnerability image scan or durable compliance audit. Restart policy does not recover every unhealthy live service. Tailnet access depends on existing ACLs/device access and host availability. See `docs/b04-verification.md` for fresh final isolated verification and the full delivery manifest.
