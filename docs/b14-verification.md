# B14 — Verifica finale e recupero operativo

**Consegna verificata:** PR #35, CI exact-head 39513412208 success, squash merge/main `fa972837684e67b9e5094025acdd54848a46c62a`; issue #20 chiusa/Completato e CI main 39518931794 success. B01–B14 sono quindi conclusi nel solo perimetro sintetico/effimero. Nessun nuovo ambiente persistente, deployment pubblico, policy fiscale, RPO/RTO contrattuale o readiness di produzione.

## Accettazione eseguita

| Superficie | Prova effettiva |
| --- | --- |
| Due destinazioni, stessa logica Workshop | Creazione, prestazione/ricambio, prenotazione, prelievo, installazione, carcassa, chiusura tecnica; interna → fattura confermata/scrittura F04; esterna → richiesta/outbox/simulatore/conferma/chiusura amministrativa. Nessuna richiesta esterna interna né fattura esterna duplicata. |
| HTTP e DOM | Due DOM con fetch e login reali su nginx/API/Keycloak/PostgreSQL; scrittura quadrata e chiusura esterna leggibili. Nessuna simulazione delle risposte HTTP nei test runtime. |
| Autorizzazione e isolamento | Anonimo 401, risorsa di altro tenant 404, comando ID vuoto 400; RLS forzata/no-context/cross-tenant/insert-only e reset contesto con ruolo applicativo prima **e dopo** restore. Scope esatti, capability, race/retry e audit rieseguiti nei runner B12/B13. |
| Coda e recupero | Runner B11 separato: destinatario indisponibile, backoff limitato, esito incerto/status-first, kill/recreate API, lease/fencing, fairness, riconciliazione autorizzata/idempotente e RLS su veri fatti di riconciliazione. |
| Diagnosi e privacy | Eventi 404/312/313 e 314, correlazione, TraceId/SpanId W3C nei log reali. Istogramma `enginia360.http.duration` via MeterListener nel test API. Validatore rifiuta credenziali effimere, token e importi/conti nell'audit; quattro test di mutazione del validatore. Nessun exporter/collector persistente o endpoint diagnostico pubblico aggiunto. |
| Hardening | Readback Docker dei cinque servizi: nonroot, read-only, ALL cap drop, no-new-privileges, memoria/CPU/PID/log limitati, zero porte pubblicate. Storage e backend isolati. |
| Recupero dati | `pg_dump -Fc`, distruzione vera del container/tmpfs, nuovo ID/cluster senza schema contabile, `pg_restore --exit-on-error`, riavvio e readback HTTP autenticato + contenuto canonico di tutte le 46 tabelle applicative identico. ACL/ownership e RLS preservate. |
| Migrazione/rollback | Rollback B13 rifiutato con evidenze vive; sola pulizia della fixture ripristinata, rollback e riapplicazione B13 riusciti. Nessuna cancellazione su dati conservati. Ordine inverso e limiti in [istruzioni operative](b14-operations.md). |
| CI e regressioni | Workflow seleziona integralmente B02–B14, lifecycle race, API/UI/build/audit, hardening e smoke. La selezione non equivale all'esecuzione remota: run/head/esiti finali nella PR/issue. |

## RED → GREEN e cause risolte

- `dotnet test ... --filter FullyQualifiedName~OperationalDiagnosticsTests`: RED reale `Assert.NotEmpty`, nessuna misura emessa (`b14-metric-red2.log`); aggiunto istogramma tecnico e scope W3C, suite completa GREEN **69/69** (`b14-dotnet-green.log`). Il primo tentativo senza restore era un errore di preparazione NuGet, non RED.
- `python3 scripts/test-b14-diagnostics-unit.py`: RED **2/4** (payload contabile e traccia assente accettati), poi GREEN **4/4**; input unitari dichiarati mutazioni, non evidenze runtime.
- `python3 scripts/test-b14-restore-contract.py`: RED `--env-file` assente, GREEN dopo riuso degli overlay esatti, etichette e prova d'integrità/provenienza.
- Runner congiunto ereditato: errore reale B12 `alpha invoice visibility incorrect` in `b14-full-attempt3.log`: il tracer produce una fattura, la suite B12 ne produce tre. B13 analogamente assumeva una sola scrittura. Cambiati **soltanto test SQL**: atteso calcolato con filtro tenant come owner in tabella TEMP, SELECT concesso sul solo TEMP, confronto nel ruolo applicativo con visibilità positiva; somma F04 moltiplicata per le scritture attese. Tutti gli assert su policy/RLS/permessi/immutabilità/cross-tenant restano. Nessuna policy, grant persistente o schema di produzione indebolito. B12 e B13 originali rieseguiti GREEN con gli stessi test.
- Errori fixture/runner distinti da RED di dominio: TEMP inizialmente non leggibile al ruolo applicativo; B11 RLS richiede riconciliazioni realmente eseguite e pertanto resta nel runner B11 separato, non si fabbrica una riga nello stack congiunto; Docker tmpfs va verificato in HostConfig.Tmpfs; nuovo cluster esegue init B02 e richiede restore clean/if-exists. `pg_dump` non conserva ruoli globali: ricreato esclusivamente il ruolo NOLOGIN tecnico B10, senza leggere password, e mantenuta ownership dal dump. Non si usa `--no-owner` sulla funzione SECURITY DEFINER.
- Eliminata pipeline `docker run | tee` che occultava l'exit del probe in shell POSIX: risultato scritto direttamente e stampato soltanto dopo successo.

## Comandi ed esiti locali

Tutti i runner con limite esterno `timeout 600`, singolarmente; log in `/root/.hermes/cache/scratch/` (non Git):

- `timeout 600 sh scripts/run-b14-tests.sh` → **exit 0**, `b14-final-green.log`: hardening, HTTP negativi/congiunti, due DOM (1+1 PASS), audit/tracce/privacy, RLS pre/post, restore, rollback/reapply, cleanup esatti.
- `timeout 600 sh scripts/run-b11-tests.sh` → **exit 0**, `b14-regression-b11.log`.
- `timeout 600 sh scripts/run-b12-tests.sh` → **exit 0**, `b14-regression-b12.log`.
- `timeout 600 sh scripts/run-b13-tests.sh` → **exit 0**, `b14-regression-b13.log`.
- SDK bloccato `dotnet restore ... --locked-mode && dotnet test ... -c Release --no-restore` → **69 PASS**, audit NuGet API/test transitivi: nessun pacchetto vulnerabile, `b14-dotnet-green.log`.
- Node bloccato `npm ci --no-audit --no-fund && npm test && npm run build && VITE_B13_TEST_UI=true VITE_B10_TEST_UI=true npm run build && npm audit --audit-level=high` → **35 PASS**, 12 runtime test intenzionalmente skipped senza fixture, typecheck e due build PASS, **0 vulnerabilità**, `b14-ui-green.log`. Due runtime B14 sono eseguiti separatamente nel runner, non conteggiati come saltati.
- `python3 scripts/test-ci-runtime.py`, tutti `test-b04-ci.py` → `test-b14-ci.py`, restore contract e quattro mutation test → PASS; `git diff --check` PASS.
- `sh scripts/smoke.sh` → PASS sul bootstrap esistente, senza rebuild o restart. ID/start time/mounts dei due container originali e i **25 volumi conservati** identici al readback precedente; Tailscale 443 → 127.0.0.1:9119 preservato. Non si dichiara un controllo dei contenuti dei DB conservati.

## Referto restore reale

Progetto `enginia360-b14-1001204`, referto scratch `enginia360-b14-1001204-restore-measurement.json`:

- backup **0.361 s**, **162985 byte**; recupero fino a readback applicativo/SQL **28.983 s**;
- dump SHA-256 `edaa2533ccfd3170d67f851e71dd65db2340ed86bef4a315ca7b6db479711ad4`;
- hash stato HTTP + **46 tabelle** prima/dopo uguale: `9818d979d3d9be654c2059ae1300f66c405fa847e0cd1695ea3dc62fb0d7d95a`;
- vecchio container `39a8b64ec605780e45ee4613377295f57b823e0a09ca200f38d5bcb47e90e107`, nuovo `fd4379452bd7c8cb3ede08717447d6b0da66b54071ea758aa698bf8e198ceb26`;
- referto include revisione base e hash esatti dei sorgenti non ancora committati; manifest completo/checkpoint scratch `b14-proof-checkpoint.json`. Dump e credenziali effimeri eliminati; report tecnico conservato senza payload di business.

Non è `pg_restore --list`: il data store è distrutto e ricostruito, il database e l'applicazione sono riletti e confrontati. La misura sintetica è inferiore a un'ora ma **non prova un RTO contrattuale**, RPO giornaliero, perdita del nodo o disponibilità single-host. Non sono backup off-host cifrati, retention o allarmi. OPE03–OPE05 restano gate per dati reali/servizio/pilota, non un nuovo gate manuale B14. ERP reale, upload/allegati, emissione fiscale/SdI, incasso e contabilità generale esclusi. La dimostrazione è automatica DOM/HTTP isolata, non un'approvazione manuale del proprietario o una nuova validazione specialistica.
