# R00.b — verified external identity boundary (stage 1 of the browser session foundation)

## Status

Bounded delivery under D74–D76, tracked by **#53**, a subissue of **R00 #40**. This is **not** the complete R00.b browser/session contract and does not close #40, #53 or UI01.b #5. It delivers the identity half of the contract frozen in the R00 implementation handoff: an append-only verified-issuer/opaque-subject binding and a product authentication boundary that refuses the legacy credential surface by default. The real-browser OIDC code/PKCE flow, cookie/ticket session, antiforgery, TLS ephemeral identity stack and logout/revocation acceptance remain **open work**, listed under “Not delivered” below.

Baseline: merged main `23240a1769fedeebf579b0bcbd81fe4098e0f1ea`. Protected bootstrap Compose/nginx, Tailscale 443 → localhost:9119, the two original bootstrap containers and 25 retained volumes are untouched; no persistent environment, public exposure, real identity/data, ERP call or purchase occurred.

## Delivered contract

### Append-only binding migration

`database/runtime/migrations/0015_external_identity_binding.sql` is appended to `database/runtime/manifest.json`. The **published 14 R00.a entries and their exact bytes are unchanged**, asserted by an executable digest check over the manifest prefix (`91cd082a…50b2`), so the R00.a ledger prefix still validates and a second apply remains a no-op.

| Column | Rule |
| --- | --- |
| `InternalIdentityId uuid` | primary key, non-nil; the only identifier the application and domain modules ever see |
| `Issuer text COLLATE "C"` | 9–2048 bytes, `^https://[^\s?#]+$`, byte-exact comparison |
| `Subject varchar(255) COLLATE "C"` | 1–255 printable ASCII, case-sensitive, opaque — never assumed to be a GUID |
| `UNIQUE (Issuer, Subject)` | one internal identity per verified external identity |

Row-level security is enabled and **forced**; the single policy is `SELECT` only and requires both `app.identity_issuer` and `app.external_subject` to match byte-exactly. `PUBLIC` is revoked; the application role has `SELECT` only — no `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE`, no ownership, no ledger write. The table ships **empty** and creates no tenant, membership, grant, capability or default administrator. Nothing in this delivery can create a binding: R01 owns that command once its granting/revocation policy is resolved.

### Authentication boundary

`src/Enginia360.Api/BrowserAuthentication/ExternalIdentityResolver.cs` is the only lookup path. It runs **after** the official handler has verified signature, issuer, audience, lifetime and not-before (`ClockSkew` zero, unchanged), re-checks the token issuer against the configured `ValidIssuer`, requires exactly one `sub`, validates issuer/subject shape in code, sets both identity settings transaction-locally and resolves the binding through RLS. The resulting principal carries exactly one `ClaimTypes.NameIdentifier` — the internal UUID — plus namespaced technical `enginia360:verified-issuer` / `enginia360:external-subject` claims. `MapInboundClaims` is disabled in the product profile so no external `sub` can masquerade as the internal name identifier.

Consequences, all executed:

- No binding → `401`, no insert, no session, no context.
- Binding without membership → authenticated with **empty** contexts; existing commands keep returning 403/404.
- Binding removed between requests → the next request is `401` (re-checked per request, never cached).
- Identity store unavailable → controlled `503`, no `Location` redirect and no token echoed; an API caller is never sent to an HTML login.
- `email`, `role` and `tenant` claims, and an external value that happens to be a UUID, establish nothing.
- Same subject under a different issuer is a different identity; lowercasing the subject is a different identity.

### Default surface closure

`DevelopmentTestLogin:Enabled` alone no longer publishes `POST /api/v1/development/login` or the database-session diagnostic. Both now require the explicit, disjoint `Authentication:Profile=SyntheticLegacy` **and** `BrowserSessions:Enabled` false. `ASPNETCORE_ENVIRONMENT` is not a guard. The historical synthetic acceptance stack sets that profile explicitly in `compose.b02-test.yaml` (inherited by the B03–B14 overlays), which keeps the legacy bearer/GUID-subject scenarios running unchanged while the product profile refuses them. The default build still publishes no `/auth/*` or OIDC callback surface.

## Executed verification

Behavioral RED was observed before each production change, on real infrastructure — not fixture or setup failures:

| Behavior | RED | GREEN |
| --- | --- | --- |
| Verified binding store exists, empty, forced RLS, exact lookup, app read-only | `to_regclass('organization_access.external_identity_bindings') IS NOT NULL` returned `f` on a healthy migrated database | `scripts/test-r00b-bindings.py`, 1 real PostgreSQL test |
| Only the exact verified issuer+subject resolves; UUID/email/role/tenant claims do not; removal invalidates | unbound internal-UUID token returned `200` (the pre-change pipeline trusted raw `sub`) | `ExternalIdentityAuthenticationTests`, real JWT handler + real RLS pool, sizes 1 and 12 |
| Store outage is controlled | `500` | `503`, no redirect, no token in body |
| Legacy credential surface is not a default | development login returned `400` (i.e. routed) | `404` for login and database-session; 2 tests |
| Acceptance actually selected | `scripts/test-r00b-bindings.py` absent from the runner constants and the identity suite absent from the test image filter | both asserted by `scripts/test-r00a-ci.py` |

Commands and results actually executed from the isolated worktree:

```sh
python3 scripts/test-r00a-ci.py                                             # 4 passed
python3 scripts/test-r00-migrations.py ManifestTests BaselineTests ConfigurationTests   # 4 passed
timeout 600 sh scripts/run-r00a-tests.sh                                    # 22 Python + 1 binding + 5 .NET, 0 skipped
timeout 180 python3 scripts/test-r00a-lifecycle.py                          # real failure/TERM cleanup
dotnet test tests/Enginia360.Api.Tests                                      # 72 passed, 2 opt-in runtime theories skipped
dotnet list … package --vulnerable --include-transitive                     # no vulnerable packages, API and tests
```

The canonical runner now applies the 15-unit manifest twice, runs both PostgreSQL suites and the pool/identity .NET suite with zero skips, restarts the same ephemeral project, reapplies the manifest, checks logs for generated secrets and cleans up only exact project/configuration-labelled resources. Pre-existing container, network and volume inventories are asserted unchanged.

## Not delivered (remaining R00.b work)

These remain unproven and are therefore not claimed anywhere:

1. Backend OIDC confidential client, authorization code + PKCE S256 via the official middleware, with meaningful state/correlation/nonce/signature/issuer/audience/lifetime negative tests.
2. Same-origin `__Host` Secure/HttpOnly cookie, bounded absolute-expiry revocable server-side tickets, no tokens in JS, antiforgery on login/logout and every cookie-authorized command, bearer-present-never-cookie selection.
3. Logout: local revocation before redirect, copied-cookie replay rejection, restart recovery, and — only if claimed at all — an actually signed Keycloak backchannel notification with replay protection and documented delivery-loss residue.
4. Explicit CA-trusted TLS for browser, IdP, backchannel and database with strict forwarded-proto/Host trust and no plaintext credential path; new isolated ephemeral Compose/nginx profile.
5. Real Chromium acceptance against a real Keycloak confidential client with direct grant disabled: login, session, authorized write and read-back, negative OIDC/CSRF/cross-tenant/scope cases, pooling, error and recovery paths; plus a minimal runtime access shell proving the flow.

## Rollback

Revert this delivery's commit. The binding migration is additive and empty: dropping it removes no business fact. Never point the ephemeral runner at retained B02 volumes and never stamp a ledger onto a presumed-compatible nonempty schema. No business policy, provisioning API or authority decision is introduced; D74–D76, the single tenant-wide shared-master authority and internal Billing/Accounting remain unchanged.
