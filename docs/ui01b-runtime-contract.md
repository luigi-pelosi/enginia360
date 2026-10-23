# UI01.b — bounded runtime editor contract

Subissue #60 of UI01 #5; baseline f2d64cba0dd9ea2d962c4ec679ed5be01ec458a1. D74–D77, existing D67 snapshots/rounding unchanged. The bounded R02.b authority/common-edit addition is specified separately in [its contract](r02b-master-authority.md). No ERP call, production identity, provisioning or fiscal engine.

## Opt-in only

`npm run build:ui01-runtime` produces `web/dist-ui01-runtime/` from `ui01-runtime.html`, separate from default bootstrap and synthetic UI01.a/Bxx builds. `compose.ui01b-test.yaml` extends the existing guarded R00 TLS services, enabling only Counterparties and Workshop in this isolated profile. No published ports, retained volumes or persistent manual environment. Native access/admin remains at `/`; editor at `/ui01-runtime.html`. Login returns to the existing fixed `/`, never a client-supplied redirect; reopen the editor URL afterward. The existing R01 limited grant panel is preserved.

## Existing contracts connected

- Same-origin R00 `/auth/session`, `/auth/csrf`, native antiforgery `/auth/login`; logout/admin remain in existing shell. No bearer, client tenant identity, storage, synthetic login or client grants. Every write obtains fresh CSRF, exclusively in memory.
- Own exact R01 `/api/v1/organization/contexts` with true/false/null capability state. `canWrite` concerns only organization-context.write; it is not Workshop authorization.
- Workshop `/contexts`, `/document-types`, `/vehicles`, `/catalog`; company-authorized Counterparties search. Creation uses server document ID/current version/direct-creation flag. Selected vehicle never changes selected payer; holder is resolved/stored by server, not invented by the selector.
- Existing POST `/orders`, GET `/orders/{uuid}` and `/commercial-summary`, POST `/orders/{uuid}/lines`. Fragment `#order=UUID` is only an untrusted locator; reload/new page reacquires session and rereads the server, including read-only identities with no creation contexts.
- Saved header, IDs, lines and q6 summary are immutable. No local optimistic totals, arithmetic or saved row edits. Input strings remain invariant quantity6/unit-price6/discount2 and server numeric bounds. Prices are explicit inputs, not supplied by catalog.
- The server's `Case001` projection supports one Service and one Part in the working group whose ID equals the order ID. UI states this supported limit and disables duplicate kind selection. Revision comes from each validated server summary, not a hardcoded revision <=2 rule.
- The line-policy version is not publicly projected. An explicitly labelled positive setup version is required, initially empty; never derive it from document/catalog versions or assume 1. Server validates it. Acceptance deliberately uses document7, line-policy9 and catalog8.

## Errors and uncertainty

Empty-body HTTP errors are handled without unconditional JSON parsing. 401 clears document/options/action state; native session retry is explicit, never automatic write replay. 403/404 are generic scope/resource denials; 409 requires reread/configuration refresh; csrf_invalid is visible and writes obtain a fresh token on explicit retry. No server HTML is rendered.

Each explicit command allocates one UUID and exact payload in component memory. Transport/server uncertainty locks that draft and offers only identical replay. Definitive 4xx creation rejection releases pending state and clears document configuration until refreshed. An accepted write is not a confirmed summary: failed readback displays 'Scrittura accettata; riepilogo non verificato', removes unverified amounts, and offers a read-only retry. An accepted create exposes the known ID in the URL before readback. Session/read generations discard superseded responses; document reads atomically replace validated order/summary rather than patching totals locally.

Response parsing rejects mismatched order/payer/group IDs, unknown policy/kind/currency, numeric amounts in place of strings, invalid IDs/versions, duplicated line identities/kinds and inconsistent revision/line count. This does not replace server authorization.

## Unsupported controls and parent criteria

Persisted row edit/remove, Note, multiple groups, order list/search, payer/vehicle change after creation are explicitly disabled. These require bounded R03 contracts, not fictitious PUT/PATCH endpoints or local prototype persistence. Logistics/administrative panels remain separately labelled 'Non collegato in UI01.b', not inferred zero/Pending/Confirmed states; commands disabled. Actual operational projections/commands remain R03/R04. Parent #5 must remain open: persisted editing, long repeated-group runtime documents and live operational states are not supplied by this increment. UI01.a remains a separate synthetic local editor.

## Styling and CSP

Pinned existing Ant Design 6.6.7; no dependencies/lock changes. Its installed `antd/dist/antd.css` and supported `theme.zeroRuntime` supply static styles; ConfigProvider `csp.nonce` covers remaining dynamic style mechanisms. The opt-in TLS edge substitutes a fresh nginx `$request_id` (16 random bytes) into the document meta and `style-src 'self' 'nonce-…'` per response, with no-store. Script/connect remain same-origin, no unsafe-inline/wildcard or untrusted client nonce. Native controls avoid style-attribute-requiring overlays; real Ant Button is exercised under that policy. Existing bootstrap/R00 nginx policy is untouched. This profile is a bounded acceptance entry, not an approved production deployment.

Official primary references checked: `https://ant.design/docs/react/compatible-style/` (zeroRuntime/static antd.css), `https://ant.design/components/config-provider` (csp nonce), `https://nginx.org/en/docs/http/ngx_http_core_module.html#var_request_id` (16 random bytes). Installed pinned package sources and actual strict-CSP Chromium acceptance verify the concrete integration rather than relying only on documentation.

## Rollback

A reviewed revert removes the separate entry, runtime sources/build script, opt-in Compose/nginx and targeted CI mapping/job. No application schema, migration, backend contract, saved snapshot or protected deployment was changed; no data rollback or authority switch is needed. Do not delete retained data or alter the existing Tailscale handler.
