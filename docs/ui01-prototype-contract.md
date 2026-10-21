# UI01.a — frozen prototype contract

Authorized implementation after verified P00; refs #5. UI01.b remains dependent on R00.

## Boundary

Opt-in `npm run build:ui01` / `npm run dev:ui01` uses a separate HTML/React entry and separate `dist-ui01` output. Default App/main/bootstrap and every Bxx flag remain unchanged. No network calls, authentication, tenant context, localStorage, stock mutation, CRUD or backend endpoint. Reload discards drafts. UI state is not business authority. No public deployment or persistent environment.

## Readonly input and local output

`EditorDocument`: stable id, reference, document/customer/payer/vehicle context, readonly repeated `EditorWorkGroup[]`, supplied `EditorSummary`, separately supplied operational projections. `EditorLine` discriminates Service/Part/Note with stable id. Commercial values are invariant decimal **strings**, not JS Number money. Note has description only. Local catalog items support Service/Part selection without allocating backend identities. `onDraftChange(EditorDocument)` emits an immutable local draft only; no saved or confirmed claim. Vehicle/keeper and payer selections are independent.

One explicit active row draft; Modify focuses description; Escape/Cancel discards transient input and returns focus to row Modify; Apply validates and immutably replaces that same row id in its original group, announces local-only outcome and restores focus. Enter in text inputs submits; Tab follows native controls; no global keyboard interception. Description required, max 500 chars. Commercial quantity and price accept nonnegative invariant strings with at most six fractional digits and at most 12 integer digits; malformed/overprecision/exponent/comma values rejected without truncation/rounding. These are prototype input constraints, not fiscal/discount/stock policy. No discount engine added.

Supplied summary amount strings and revision are read-only. Any transient or applied local change visibly invalidates it; cancelling the only transient change restores freshness, applied edits remain stale. No client tax arithmetic or fake refresh response. Summary/actions remain visible while central document scrolls. External Received is explicitly NOT business Confirmed; reserved, picked, prepared, installed/consumed and carcass are distinct facts, never inferred from one another.

## Acceptance tracer bullets

1. Render supplied context/groups/summary and distinct stages; no fetch.
2. Explicit edit/cancel with focus restoration and no mutation.
3. Apply q6 text preserving stable identity; stale supplied summary.
4. Validation associated/announced and first invalid input focused; Escape and Enter.
5. Local catalog search/select within active row, no silent draft discard.
6. Vehicle/payer independent and context collapse.
7. Synthetic 100-row, empty/loading/error states and reachable last row.
8. Actual browser desktop 1920x1080/laptop 1366x768 and keyboard/scroll checks.
9. Full UI regressions/typecheck/default/prototype/Bxx builds/audit; applicable API/container proofs separately bounded; exact-head and merged-main CI.

## Design and dependency decision

Ant Design core only, compact light ConfigProvider theme, semantic native table composition with Ant inputs/buttons/selects; no second grid/design system/templates. Registry `npm view antd version license peerDependencies --json` on 2026-10-21 returned **6.6.7**, MIT, React/react-dom >=18.0.0; existing React 19.3.1 satisfies this declared peer range. Official docs show 6.6.7 and React 16/17 dropped in v6. Pin exactly 6.6.7 and intentionally regenerate lock; verify runtime/build and audit, not just declared compatibility.

Primary sources checked before installation:
- https://ant.design/docs/react/introduce/ (version/environment)
- https://ant.design/docs/react/customize-theme/ (ConfigProvider compact algorithm)
- https://raw.githubusercontent.com/ant-design/ant-design/6.6.7/LICENSE (MIT terms)
- npm registry via actual `npm view` (browser retrieval of registry URL failed; CLI succeeded)

Legacy screenshot inspected locally only for structure: narrow contextual left column, repeated dense work sections, local toolbars, persistent bottom summary. No customer/document/vehicle values copied. Fidelity is compositional, not pixel-identical or proof of legacy behavior. Contract published before production implementation.

## Rollback and remaining gates

Remove separate prototype entry, ui01 sources, build script/CI step and pinned dependency in a reviewed PR. No migration/data rollback. UI01.b must map authorized existing reads/commands after R00; B05 is add-only single Service/Part, not a general multi-group edit API. Unsupported operations remain gaps. No R00 implementation here.
