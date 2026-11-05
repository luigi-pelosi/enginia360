# MVP09 — bounded cleanup and consumer/replacement trace

Status: SOURCE_COMPLETE_UNVERIFIED. This is source inspection and prepared final acceptance, not observed runtime success. NO deletion quota.

## Active composition actually read

- `src/Enginia360.Api/Program.cs`: Catalog is composed when Catalog or Workshop is enabled; standalone Catalog management maps under Catalog. DocumentTypes and Documents have separate opt-in composition and public endpoint mapping. Historical Inventory reservation still requires Workshop, and Workshop/Inventory/Billing/Accounting/Integrations still have retained composition and consumers. New document stock lives in Documents; it is not a replacement authorization to delete historical Inventory.
- `frontend/app/layout.tsx` composes `frontend/components/shell.tsx`; domain navigation maps Inventory and Documents to the existing `/documents` workspace. `frontend/components/documents-workspace.tsx` owns current context selectors, document mutations, quantities and provenance. Shell neither resolves identity nor grants access. Every domain remains reachable; no new universal workspace or business writer.
- `frontend/app/organization`, `users`, `onboarding-admin`, `counterparties`, `catalog`, `document-types`, `documents` and their typed `frontend/lib` adapters remain the current UI paths. Private backend transport remains cookie-per-request, no shared credentials/cache.
- `.github/workflows/ci.yml` routine impact consumers include foundation, auth, membership, onboarding, tenant roles, counterparties/catalog, document types and documents plus direct historical consumers. Explicit full architecture previously selected ONLY `runtime-migrations` and `verify`; it did not automatically select the newer `affected-*` jobs because `impact` is skipped. Both existing legacy jobs are preserved byte-for-byte. The final-only adapter now composes the real existing commands of all other finite affected groups, including security/lifecycle/restore consumers; it does not infer full acceptance from the old two jobs.

## Bounded changes and direct final consumers

| Obsolete active dependency/defect | Source cause and replacement | Prepared final consumer |
| --- | --- | --- |
| Repeated stale MVP08 source-only checkpoint paragraphs in active instructions/plan/charter/baseline | Remove duplicate active status dependencies. One delimited `mvp09-current` summary per document points to parent-verified MVP08 delivery and source-only MVP09. Exact prior paragraphs are preserved in `docs/archive/mvp08-checkpoints.md`; predecessor proof remains explicitly historical. D97/D98 gate fields and D100/D101 literal decisions are not rewritten. | `test-mvp09-contract.py` current-summary positive/negative mutations, historical archive and byte-preservation guards; existing MVP06/07/08 current-status guards advanced only. |
| Two simultaneous `aria-current=page` links for `/documents` | Both Inventory and Documents map to the same route and were both treated current. `domainIsCurrent` gives Documents sole current-page semantics while retaining Inventory as a usable alias. No capability/grant change. | Real Shell component SSR test plus actual integrated Chromium assertion of exactly one current main-navigation link. |
| Shell says no active business context while module can have one selected | Old unconditional context note described technical MVP01 baseline. `ContextBoundary` now says context is selected in the open module, without inferring any selected tenant or claiming a grant. Baseline/home wording remains unchanged. | Real component SSR tests and integrated browser module-context assertion; existing shell/hydration/noJS consumers remain selected. |
| Copying old full document browser fixtures into each new point | Export `documentDevelopmentJourney` from its existing owner fixture, preserving its body/assertions and default standalone invocation. MVP09 supplies the newly approved principal and generated organization to the same actual journey. Small runner hooks reuse hardening, SQL/API contracts, quantity readbacks and guarded cleanup. | Literal body-preservation test, canonical MVP08 pool4/1, integrated MVP09 pool4/1 and all mapped shared-producer consumers. |

## Explicitly retained

- B02–B14 and R00–R06 modules, UI fixtures, helpers, permissions, security tests, migrations and evidence: still composed, selected, referenced by historical profiles or directly consumed by runtime/acceptance. Nothing was proven universally unconsumed; therefore no module/endpoint/bulk legacy-UI deletion is justified.
- All 46 published migration SQL files, manifest, inventory entries and immutable historical decision/register blocks. No new migration, data reset, schema rewrite or history rewrite.
- Existing locks, image pins, frontend/backend ownership and retained functional/incident evidence. Newly prepared passing-first guards will be regression evidence, never retrospective RED.
- All retained services/volumes and Tailscale443→localhost9119. Older membership fixture `enginia360-r00b-5b070b47257f` / `d5c8d55bebcf` remains protected, never classified disposable by its prefix. Final runtime captures exact IDs/start/mounts/config labels before cleanup; no cleanup was executed in this source phase.

The active-path cleanup is intentionally documentation/composition-only. Its final direct-consumer checks remain UNEXECUTED; no assertion here grants authority to delete a still-used runtime surface.
