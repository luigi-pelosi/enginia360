# UI01.b — verification and limits

Bounded runtime editor, subissue #60 / parent #5. Contract: [ui01b-runtime-contract.md](ui01b-runtime-contract.md). No claim of complete UI01 live editor or pilot readiness. Remote SHA/run IDs and final tree/readback are recorded on the delivery PR/issue, only after actual execution.

## Executable RED → GREEN

Each new behavior was exercised before its production change using the pinned Node image already used by this repository. Scratch logs retain the failures and subsequent results; initial host Node startup failure is not RED evidence.

- Transport read: missing workshopApi import → same-origin/no-store read succeeds without bearer/tenant headers.
- Write/CSRF: resolved first response instead of rejecting409 → obtains fresh token and preserves exact JSON; empty-body error typed.
- Known-ID document: missing runtime component → actual supplied UUID/order/summary, independent of create scopes; unsupported controls disabled.
- Create: missing server selector option → server document version7, distinct payer/vehicle selection and readback.
- Add: missing AddLine import → explicit line-policy9/catalog8, invariant payload and identical uncertain replay; no totals sent.
- Session binding: missing add/session retry controls → authenticated add binding and401 clear; missing native login → antiforgery form; missing own-context state → true/false/null presentation.
- Session race: late authenticated result restored creation after newer anonymous result → request generation rejects superseded authority.
- Malformed CSRF: POST sent with missing token → invalid projection stops before POST.
- Definitive create409: pending draft disabled configuration reload indefinitely → pending cleared/configuration invalidated. The first concurrent fixture attempt timed out before its assertion; a separate valid RED explicitly observed `disabled=true` instead of false, then GREEN. No timeout was increased.
- Accepted-write/readback: missing accepted/unverified state and duplicate-create controls remained → explicit unverified status, no amounts or new-create action, read retry without another POST.
- Operational gap: absent distinct panels → six explicitly unconnected stages/disabled commands, not invented zero/Pending states.
- Stored header: missing configuration/company display → immutable stored company/site/document/version/customer flag/payer/vehicle/holder and collapsible header.
- Wiring/impact: absent build/CSP/job/mappings → separate build and per-response nonce, new exact-head editor dispatch and direct Workshop/Commercial/auth contracts selected.

This is not a claim that every assertion had an independent business-level RED; schema/error-table regressions also verify existing implemented behavior.

## Local commands and observed results

Image identities remain pinned in manifests/workflow. From repository root:

- Node24.22.0 pinned container: `npm ci --no-audit --no-fund`; `npm test -- src/ui01/runtime --maxWorkers=1`; `npm run build`; `npm run build:ui01`; `npm run build:ui01-runtime`; `npm audit --audit-level=high`. Latest runtime test/build log at `/root/.hermes/cache/scratch/UI01b-candidate-runtime-build.log`: **25 unit tests passed**, all three builds/typecheck passed, audit **0 vulnerabilities**. Ant bundler `use client` warnings are retained, not suppressed. Subsequent header-only change has a separate RED and is included in the delivery candidate verification.
- Earlier affected UI/prototype run `/root/.hermes/cache/scratch/UI01b-ui-final-serial.log`: **45 passed** at that earlier stage. Later unchanged synthetic 100-row JSDOM acceptance exceeded its existing5s timeout, including an isolated rerun. This is a real local failed regression run, not a pass, not browser acceptance, and not fixed by changing/skipping its test/deadline. CI keeps the test and unchanged timeout. New CreateOrder test now flushes its asynchronous fixture with React act instead of racing its1s option poll; failure/sabotage evidence remains separate.
- SDK10.0.402 pinned locked restore, filtered API test, publish and both transitive audits (`UI01b-api-final.log`): **73 passed,3 runtime-only skipped,76 total** offline. Filter: WorkshopBoundaryTests, CommercialCalculationTests, CounterpartyArchitectureTests plus existing AUTH_FILTER. Skips are not runtime passes; real editor/API/SQL below and migration/session dispatch remain required.
- `python3 scripts/test-ui01b-impact.py`:3; `test-ui01b-wiring.py`:2; `test-ci-impact.py`:10; r00a-ci:4; migration-tls:1; r00b-lifecycle default:3 offline; ci-runtime:7; C00 guard PASS; productization mutation tests:16. Default lifecycle test is not a new actual Docker TERM proof.
- `git diff --check`: clean; canonical `sh scripts/smoke.sh http://127.0.0.1`: PASS on protected unchanged bootstrap, without restart/build/deployment. This does not claim that the old running bootstrap image contains this candidate.

## Actual authenticated Chromium/API/PostgreSQL

`timeout 600 python3 scripts/run-ui01b-tests.py`, durable local `/root/.hermes/cache/scratch/UI01b-runtime-candidate.log`: **10 named browser checks,0 skipped**, plus SQL and cleanup assertions. Ephemeral CA-trusted TLS, real Keycloak confidential code/S256 (PAR when supported), real API/16 migrations/PostgreSQL. No ignoreHTTPSErrors, mock successful API, bearer, development login, real user or persistent deployment.

Verified create with current server document7, catalogue8 and independently supplied line-policy9; payer different from vehicle holder throughout persisted readback; Service/Part q6 writes with non-default quantity/price/discount; saved summary revision2 and stable order/group/line IDs; reload and new-page known UUID; empty-create-context read-only identity. Negative checks cover anonymous, absent/corrupt CSRF, stale revision/duplicate kind, other tenant and exact missing add action, local logout clearing an already-open editor.

Two explicitly negative transport faults, not synthetic business responses: let the real Service POST commit then drop its response; identical UUID/payload replay200 creates no duplicate. Let the real Part POST commit then abort summary reads; UI marks accepted/unverified; explicit real read recovery succeeds without new command. Positive business responses are always real server responses. No HAR/trace/credential/OAuth log is captured.

Privileged test-only readback: exactly **1 order,2 lines** after all negative/replay attempts; persisted quantity/price/discount/net snapshots equal HTTP projection. Python Decimal computes D67 half-up at six places and compares net/tax/total with SQL and server summary. Payer/holder equality with stored IDs independently checked. This is authorized Case001 technical evidence, not fiscal certification or a generic tax engine.

Hardening checks: nonroot/read-only/dropALL/no-new-privileges, bounded CPU/memory/PIDs, no published ports or mounted persistent volume, internal network. Cleanup checks exact random project/config labels, removes only its ephemeral resources, and compares original running-container and volume inventories unchanged. Bootstrap web/API, Tailscale443→localhost9119, retained volumes/backups/configurations not changed.

Early browser fixture failures are retained: PAR cannot be checked as a plain query-only authorization request; native option attachment is not option visibility; native select accessible labels now explicit after a real browser failed to locate the wrapped select. No application policy or timeout was loosened. Final real run passed after those corrections.

## Layout/CSP/evidence

Measured real viewports **1920×1080** and **1366×768**; footer bottom equals actual viewport height. Synthetic screenshots and SQL projection at `/root/.hermes/cache/scratch/ui01b-evidence/`. No credential/login screenshot. Actual Ant Button runs with static CSS/zeroRuntime and nonce-aware ConfigProvider under strict opt-in CSP:0 app CSP console violations; separate HTTP responses have distinct32-hex nonces matching their own headers/document. No unsafe-inline or wildcard policy.

## Delivery selection and remaining parent criteria

First exact head `e159a518f59bf6696e9009a7b2172352c485d7bf`: PR run39841945773 succeeded, including all **47 affected UI/prototype tests** (unchanged5s timeout), API/publish/audits. Targeted dispatch39841945252 exposed a real hosted nonroot fixture failure before startup: R00 writes browser.json as0444; UI01.b then tried extending it while local root had masked the missing write permission. A new real uid1001/read-only/no-network container test reproduced PermissionError (RED). The fixture owner now temporarily chmods only that ephemeral file0600, extends it, and reseals0444 before any browser mount; the same test GREEN. No application, host permissions, acceptance timeout or final mount policy changed. Final repaired-head runs must be verified separately; the first head's successes are not acceptance for a different head.

Second head `114673ed1c7d6807d481404ac06d5ddb31fad5a5`: PR39842795446 success; dispatch39842810618 passed API/UI/migrations/R00 browser but the editor failed the read-only identity's known-order status assertion. Its independently denied create-only catalog selector overwrote the already successful saved-order read status; local timing had masked it. A new deterministic component test observed missing revision status (RED). Optional catalog/organization panel errors now remain visible in their own panels, preserving independent saved-order read status;401 still clears the whole session. Local GREEN: **26 runtime unit tests**, runtime build/typecheck and audit0; final real browser rerun `UI01b-final-runtime-fixed.log` passed all10 named checks/SQL/cleanup. Browser acceptance also exercises actual Tab focus/Enter submission and scrolls the central pane to assert the add button stays reachable above the sticky footer on both measured viewports. No assertion or timeout was relaxed.

Automatic PR-only checks; targeted exact-head dispatch runs affected API/UI, fixture-free migration/binding/RLS dependencies, R00 browser regression and new editor browser job. Full architecture stays exceptional/defaultfalse, no main-push automation, runtime skip is not acceptance. Candidate exact head and post-squash tree must be read back before closing #60; identical tree is not a fresh main CI execution.

Parent #5 remains open: persisted edits/removal/Notes/multiple groups, long live documents, order list/search and real logistics/administrative panels are not implemented here. Those controls are disabled and R03/R04 gaps explicit. No R02, Giobby adapter, SAP, data authority switch, accounting change, real pilot setup or go-live. Billing/Accounting code/contracts/tests preserved. Revert only opt-in artifacts/mappings through a reviewed PR; no schema/data rollback or protected deployment action.
