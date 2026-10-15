# Bootstrap verification record

Executed on the deployment host on 2026-10-14 UTC. No remote CI execution or host reboot is claimed.

## Test-first evidence

Each behavior was introduced after executing its failing test, then rerunning green:

| Increment | Observed RED | Observed GREEN |
| --- | --- | --- |
| Status metadata | xUnit status request returned 404 | 1 passed |
| Process health | Both health requests returned 404 | 3 passed |
| OpenAPI contract | OpenAPI request returned 404 | 4 passed |
| Safe correlation tokens | Missing response header for six cases | 10 passed |
| Italian landing and status fetch | Vitest could not find API disponibile | 1 passed |
| Failure visibility | Vitest could not find API non disponibile | 2 passed |
| Invalid response rejection | Incorrectly reported available for another product | 4 passed |

Tests use xUnit WebApplicationFactory/TestServer for actual ASP.NET request execution and Vitest/Testing Library/jsdom for React behavior. The UI network boundary is stubbed in unit tests; deployed HTTP smoke checks independently exercise nginx → API.

## Final exercised commands and results

```text
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore --nologo'
Passed! - Failed: 0, Passed: 10, Skipped: 0, Total: 10

docker compose up -d --build --wait --wait-timeout 120
UI Docker build: Test Files 1 passed; Tests 4 passed
TypeScript check and Vite production build succeeded.
Both containers healthy.

sh scripts/smoke.sh
HTTP bootstrap smoke checks passed.

sh scripts/smoke.sh http://169.58.93.135
HTTP bootstrap smoke checks passed.

npm audit --json # in web/
0 vulnerabilities at verification time.

git diff --check
exit 0
```

Runtime inspection verified API uid 1654, nginx uid 101, read-only filesystems, ALL capabilities dropped, no-new-privileges, restart unless-stopped, log limits 10m × 3, memory/CPU/PID bounds, no API host binding and only frontend 80 → 8080. These are point-in-time checks, not an availability SLA.

## API replacement regression — 2026-10-14 UTC

- Inspected the pinned `nginx:1.30.6-alpine3.24` image and running binary: `nginx/1.30.6`. The [official upstream documentation](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#resolve) confirms open-source `resolve` support since 1.27.3 and its shared-memory/resolver requirements.
- Added a shared upstream zone, `server api:8080 resolve`, and Docker embedded DNS `127.0.0.11 valid=5s ipv6=off`. Existing regex locations, URI forwarding (no URI suffix), HTTP version, Host/Connection headers and proxy timeouts remain unchanged. No frontend behavior/timeouts added.
- New `python3 scripts/test-api-replacement.py` uses built image IDs, a unique isolated Compose project, separate networks and a random loopback port. It removes the actual API, occupies the released IP with a constrained holder, and starts a fresh API. It verifies changed container/IP, HTTP recovery within 30 seconds, correlation header forwarding, all smoke routes, and identical web ID/start time/restart count. Finally it removes the holder/stack and asserts no test containers/networks remain. Build both Compose images before running it; it does not build or alter the public stack.

Actual execution:

```text
# RED, before editing nginx.conf
python3 scripts/test-api-replacement.py
API replaced: 172.21.0.2 -> 172.21.0.4
AssertionError: Proxy did not recover within 30s after IP change:
curl: (22) The requested URL returned error: 502
Exit 1; cleanup verified.

# GREEN
docker compose build web
Vitest: 1 test file passed, 4 tests passed.
tsc --noEmit and Vite build succeeded.
python3 scripts/test-api-replacement.py
API replaced: 172.20.0.2 -> 172.20.0.4
HTTP bootstrap smoke checks passed.
PASS: API IP changed; unchanged web recovered and preserved correlation header/routes.
Exit 0; cleanup verified.

# Repeat with bounded smoke curl connect/total timeouts
python3 scripts/test-api-replacement.py
API replaced: 172.21.0.2 -> 172.21.0.4
HTTP bootstrap smoke checks passed.
PASS: API IP changed; unchanged web recovered and preserved correlation header/routes.
Exit 0; cleanup verified.

docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore --nologo'
Failed: 0, Passed: 10, Skipped: 0, Total: 10

docker compose up -d --no-build --wait --wait-timeout 120
Both deployed services healthy; corrected web image deployed on public port 80.
docker compose exec -T web nginx -t
syntax is ok; configuration file test is successful.
sh scripts/smoke.sh
HTTP bootstrap smoke checks passed.
sh scripts/smoke.sh http://169.58.93.135
HTTP bootstrap smoke checks passed.
git diff --check
Exit 0.
docker ps -a --filter name=enginia360-dns-test
docker network ls --filter name=enginia360-dns-test
No matching containers/networks.
```

The terminal wrapper rejected foreground Compose `up -d` as a presumed long-running server; execution as a tracked background command succeeded, verified through healthy services, nginx config and both smoke suites. No daemon settings changed. Replacement can still briefly interrupt backend requests while the API starts and DNS refreshes; this is not zero-downtime or HA. Existing image/Compose rollback instructions apply; reverting the DNS fix reintroduces the stale-address defect and requires restarting web after backend replacement.

## Issues resolved and remaining verification

- Initial older OpenAPI package transitively selected vulnerable Microsoft.OpenApi 2.0.0; warnings-as-errors blocked restore. Updated ASP.NET packages to exact 10.0.13; subsequent restores passed without suppressing audits.
- Initial nginx image tag did not exist; selected a published official stable tag and pinned all image digests.
- Quoted the Compose tmpfs mount because commas in unquoted YAML flow sequences split it into invalid mount paths.
- Redirected all nginx temporary paths to /tmp so read-only nonroot runtime starts correctly.
- TypeScript required explicit Vite client CSS module declarations; typecheck then passed.
- Parent verification installed missing Chromium OS libraries and exercised the rendered application through localhost at desktop and 390 × 844 mobile viewport sizes. API availability was displayed and the mobile document width matched the viewport (no horizontal overflow). Public-IP browser navigation was blocked by the browser client; localhost rendering was used instead.
- Independent HTTP checks through check-host.net returned HTTP 200 for `/api/v1/system/status` from Kazakhstan, Ukraine and London (request `5105340ak7`). Public-IP host smoke checks also passed.
- Parent reran all 10 backend integration tests successfully after a locked restore in a fresh SDK container. A first no-restore-only attempt could not locate the ephemeral previous container's NuGet cache; restore resolved it.
- Both Compose services were restarted and the public-IP smoke suite passed afterward. Docker service is enabled at host startup; no real host reboot was performed.
- No TLS, full image vulnerability scan, load test, failure-injection suite, real reboot test, remote CI run, business/tenant authorization or domain acceptance is claimed.
