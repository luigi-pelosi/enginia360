# R02.a — authorized shared-master search and selection

Subissue #62 of R02 #42; baseline 025a82b86760f3fab98657e0667143346a177eee. D26/D65 tenant-wide shared identity, D61 reserved/published destinations, D63 vehicle selection versus management, D76 unchanged authority invariant, D77 delegation unchanged. No master write, authority selection, ERP call or R03 behavior.

## Scope

Bounded search and selection over the already-authorized owning-module reads used by the runtime editor:

- `GET /api/v1/counterparties?legalEntityId=&search=&limit=&after=` — common identity (`counterparties.read` on the exact company), unchanged projection.
- `GET /api/v1/workshop/vehicles?legalEntityId=&siteId=&search=&limit=&after=` — minimal `id`/`label` choice across the verified tenant (`workshop.orders.create` on the exact company/site).
- `GET /api/v1/workshop/catalog?legalEntityId=&siteId=&search=&limit=&after=` — minimal `id`/`kind`/`label`/`version`, no company price, stock or term.

Each action/resource grant stays distinct: `counterparties.read` never implies vehicle/catalog reads, membership alone authorizes nothing, and the catalog selector still requires `workshop.orders.create` exactly as before UI01.b. No directory, general master permission, create/edit/deactivate/dedup/publish/import/sync endpoint is added.

## Technical input contract

- `search`: optional, at most 200 UTF-16 characters; otherwise 400. Literal substring over the stored label/legal name, case-sensitive and diacritic-sensitive, with `%`/`_` treated as literal characters by the parameterized provider translation. This is a technical filter, not a business normalization, matching or deduplication policy.
- `limit`: optional 1–50, default 20; any other value is 400.
- `after`: optional UUID cursor; results are strictly ordered by the stored identifier ascending and the cursor is exclusive, so pages are stable and never duplicate or skip a row. A malformed cursor is 400.
- Responses keep the existing array shapes. Totals, counts and paging state are never supplied by or trusted from the client; the UI derives "next page available" only from a full page.

## UI

`web/src/ui01/runtime/MasterSearch.tsx` is one Italian selector used for payer, vehicle and catalog in the opt-in runtime editor. Search runs only on explicit `Cerca …`, Enter, `Pagina successiva …` or `Prima pagina …`; there is no automatic or debounced query. Selecting a vehicle never changes the chosen payer, and the holder stays server-resolved. Every request carries a generation: responses from a superseded company/site, a superseded explicit search, an unmounted component or an expired session are discarded, so a result from one context can never appear in another. Empty, denied (403), unavailable (503/outage) and session-expired states are explicit and recoverable only by an explicit retry. Catalog denial remains an optional-panel error and does not overwrite the saved read-only order state.

## Proof

Executable RED before each change: impact mapping failed closed for the six owning paths; `run-ui01b-tests.py` observed unbounded results, ignored search parameters and an absent database controller; component tests observed the missing searches and the surviving superseded responses. GREEN evidence is the same commands.

Actual runtime acceptance (trusted ephemeral TLS → real Keycloak OIDC Chromium → nginx/API → PostgreSQL): 16 named checks, 0 skipped, including bounded defaults, 51-row keyset traversal in both API and UI without duplicates, literal case/diacritic/wildcard behavior, 400 input caps, same-tenant other-company identities selectable, reserved destination hidden while the published one is visible, cross-tenant/identity tampering ineffective, distinct per-action denials (`counterparties.read`-only identity gets 200/403/403, membership-only gets 403/403/403), actual paused-PostgreSQL 503 with explicit recovery, and the preserved UI01.b create/add/q6/payer-holder/reload/logout checks plus the SQL readback. `test-r00b-lifecycle.py --actual --editor` proves TERM cleanup while PostgreSQL is paused; protected containers and the 25 retained volumes are compared before and after every run.

## Limits and rollback

Synthetic data only; no real identity, ERP call, deployment or persistent environment. Search ranking, dictionary/phonetic matching, deduplication and company extensions/prices/stock remain out of scope. R02.b (an authorized acquisition or modification path, local or ERP projection) still requires the concrete runtime authority profile and its mapping/history contract before any dependent write; it is not implied by this selection. Parent #42 and UI01 #5 remain open. A reviewed revert of this delivery restores the previous bounded reads; no schema, migration, saved document or protected deployment changed, so no data rollback is required.
