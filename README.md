# Enginia360 — bootstrap e incrementi runtime bounded

## Stato corrente del codice

B01–B14/C00 e R00/R01.a sono consegnati; R01.b (#58, parent #41) aggiunge amministrazione grant operativi limitata dal mandato owner D77. [Contratto, procedura owner, test e limiti R01.b](docs/r01b-limited-grant-administration.md). Evidenze exact-head/merge sono riportate nella PR/issue, non dedotte da questa pagina. [Piano corrente e gate R02–R06](docs/productization-plan.md).

Il runtime usa binding verificati, cookie OIDC/CSRF, grant espliciti e migrazioni append-only: **non** crea automaticamente tenant/utenti/admin. Il tool owner applica solo mandati espliciti a binding/membership già trusted; provisioning/root binding completo e policy CRUD restano esclusi. Queste modifiche non sono un deployment: il bootstrap protetto continua a eseguire le proprie immagini già presenti, senza dati reali, go-live, nuovi ambienti persistenti o modifica Tailscale/storage.

## Bootstrap storico — istruzioni del perimetro tecnico iniziale

A minimal Italian landing page and live API status. **Not a usable DMS:** the foundation dossier is not approved and the charter vertical slice is not implemented. No business data, identity, tenant operations or database. Read [PROJECT_CHARTER.md](PROJECT_CHARTER.md), [scope/ADR](docs/bootstrap.md) and [engineering standards](AGENTS.md).

## Deploy

Prerequisites: Linux host with Docker Engine and Compose plugin, curl and python3 for verification scripts, internet access for initial image/package downloads, port 80 free. Only technical/public metadata is served; HTTP is unencrypted. Do not enter credentials or personal data. For initial installation use official Docker instructions; this repository does not change the Docker daemon or firewall.

```sh
cd /root/enginia360 # or your checkout
# Run API integration tests using the pinned SDK; no host SDK is required.
docker run --rm -v "$PWD:/source" -w /source mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24 sh -c 'dotnet restore tests/Enginia360.Api.Tests --locked-mode && dotnet test tests/Enginia360.Api.Tests -c Release --no-restore'
# UI tests and production/typecheck build run inside its Docker build.
docker compose up -d --build --wait --wait-timeout 120
sh scripts/smoke.sh
# Isolated deployment regression: build images first; public stack is untouched.
python3 scripts/test-api-replacement.py
```

Open `http://HOST/`. nginx publishes port 80; the API has no host port binding. Docker must be enabled at boot (`systemctl is-enabled docker`). Both services use `restart: unless-stopped`; containers deliberately stopped by an operator remain stopped. Health checks do not automatically restart unhealthy containers. Host reboot behavior must be separately tested during an approved maintenance window.

| Endpoint | Meaning |
| --- | --- |
| `GET /api/v1/system/status` | Honest bootstrap metadata, no domain readiness claim |
| `GET /health/live` | Process serves HTTP |
| `GET /health/ready` | Process ready; no external dependencies exist |
| `GET /openapi/v1.json` | Generated OpenAPI JSON |

All are public. The API returns a validated/generated `X-Correlation-ID`. No auth cookies, secrets or database credentials exist.

## Verify and develop

CI in `.github/workflows/ci.yml` repeats SDK integration tests, Compose build/start and HTTP smoke checks. Remote CI must run after a separately authorized push; adding the workflow does not prove it has run.

With SDK 10.0.402 and Node 24 LTS (container builds use 24.22.0):

```sh
dotnet restore tests/Enginia360.Api.Tests --locked-mode
dotnet test tests/Enginia360.Api.Tests -c Release --no-restore
cd web
npm ci
npm test
npm run build
# optional local UI: npm run dev (API must listen at localhost:8080)
```

The local development command for API is `ASPNETCORE_HTTP_PORTS=8080 dotnet run --project src/Enginia360.Api` from repository root. English code, Italian interface; no external fonts/assets. Dependency locks are committed inputs; generated `bin`, `obj`, `dist` and `node_modules` are ignored. MIT React/Vite and .NET’s open-source ecosystem do not require a managed service subscription. Third-party licenses remain upstream and must be reviewed as dependencies change.

## Operate, update and recover

```sh
docker compose ps
docker compose logs --tail=100 api web
sh scripts/smoke.sh
# After review and explicitly authorized source update:
git pull --ff-only
docker compose build --pull
docker compose up -d --wait --wait-timeout 120
sh scripts/smoke.sh
# Recover an unhealthy process after inspecting its logs:
docker compose restart api web
docker compose up -d --wait --wait-timeout 120
```

Before updating, record `git rev-parse HEAD` and save known-good images (`docker image save enginia360-api enginia360-web -o /safe/path/enginia360-images.tar`). For rollback, restore the previously reviewed checkout without discarding uncommitted work, load the saved images (`docker image load -i /safe/path/enginia360-images.tar`) and run `docker compose up -d --no-build --wait`, then smoke-test. Keep the previous Compose configuration as well. Do not run blind `git reset --hard` or image/volume pruning. This bootstrap has no application volumes, migrations or database to back up; repository and image recovery are still required. Avoid `docker compose down` during routine updates: it intentionally removes the running services and interrupts access.

Runtime controls: nonroot users, read-only filesystems, small tmpfs, all capabilities dropped, no-new-privileges, CPU/memory/PID bounds, health checks, rotated JSON container logs. Startup honors backend health. JSON API logs include correlation scope; nginx access logging is intentionally disabled. See ADR for absent TLS, monitoring, full telemetry, database, HA, identity and domain authorization. This single-host bootstrap is not production readiness or an availability SLA.
