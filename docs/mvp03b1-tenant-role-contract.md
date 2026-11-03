# MVP03.b.1 — finite executable tenant role contract

Refs #161; Refs #142. Candidate contract, not delivery evidence. D97 policy gate remains byte-identical; `userAdministrationPolicy.runtimeDelivered` remains false until all MVP03.b (including the separate invitation/enabling increment) is verified. No new policy decision or business role is introduced.

## Inspected authority and consumers

`ExternalIdentityResolver` verifies the external issuer/subject binding after OIDC or JWT validation and returns only internal identity and verified tuple claims. Cookie validation resolves that tuple again on every request; sessions store no role grant. `VerifiedActorContext` is the existing exact tuple contract. 0036/0037 serialize platform revocation and organization operations at advisory key777036; 0038 adds distinct organization delegation. Membership is unique per internal identity and does not grant administration.

`OrganizationContextService.AuthorizedScopes` is the only consumer of `effective_membership_scopes`: ListContexts, CreateNote, GetNote. SyntheticLegacy alone explicitly uses its historical table. Counterparty/Workshop/Inventory/Billing/Accounting adapters and Catalog pricing consume `company_permissions` and owning-module functions instead; those are NOT supported role actions here and remain unchanged. No label maps to a company permission or administrative authority.

The finite initial executable catalog is exactly:

| Action | Scope | Actual consumers |
| --- | --- | --- |
| `organization-context.read` | exact warehouse tuple: tenant/company/site/warehouse | GET `/api/v1/organization/contexts`, GET `/api/v1/organization/context-notes/{id}` |
| `organization-context.write` | exact warehouse tuple: tenant/company/site/warehouse | POST `/api/v1/organization/context-notes`; company capability activation remains required |

No wildcard, null/broader scope, tenant-only/company-only/site-only or nonexistent/cross-tenant hierarchy is accepted. This is the implemented catalog, not a permanent role ceiling. Further executable actions require their affected consumer proof before exposure. No speculative domain roles, code/formulas, SUPER ADMIN, delegation/administration actions or global tenant access. D97 does not require a delegate to hold the operative actions it configures.

## Finite commands and state

New append-only0039 owns user-administration delegations, tenant permission definitions, tenant role compositions and assignments to existing exact trusted memberships. Existing root grants and D77 mandates remain separate authorities, not rewritten, silently migrated or shadowed. Effective rights are a union of independent current origins: revoking a role origin does not revoke an independently granted legacy origin. Acceptance uses targets with no legacy grants. No writer can mutate another origin.

SUPER ADMIN alone grants/revokes user administration to a selected existing binding/membership in one tenant; organization-only membership is insufficient. Delegates can create/edit permissions, compose/edit roles and assign/revoke them to existing bound memberships in their own tenant. Assignment grants operative actions only, never delegation. A role named SUPER ADMIN is only a label. Invitations, new identities, new memberships and enabling are excluded from this increment and remain in parent#142.

Reads derive the delegate tenant from its current membership; owner selects an explicit existing tenant. Commands carry exact IDs selected from the authorized read and optimistic expected revision (create0, edit current1..2147483646), reject unknown fields/invalid types, and generate new resource IDs server-side. Commands have nonzero lowercase UUID correlation/idempotency keys. Same UUID and exact typed payload under the same current actor/binding/target returns its immutable historical snapshot; any different payload conflicts. Current authority and exact target membership/binding are required even for replay. Reread supplies current state after historical replay.

All authority checks, permission/role/assignment edits and effective-right consumption share the platform revocation lock, with binding and membership rows held through commit. Revocation-first refuses a competing mutation/replay; mutation-first commits its audit/effect before revocation, then future requests refuse it. Business-context reads/writes reevaluate current effective scopes inside their transaction, including already-open HTTP sessions. No claim/session/UI cache is authority.

## Persistence, audit and input

Only finite EXECUTE privileges on new entry points; no app table DML, elevated role, global business policy or RLS bypass. New tables have ENABLE/FORCE RLS and non-superuser/NOBYPASS definer with pinned search_path. All38 published migration files remain unchanged. Prior target GUC is restored in the same transaction.

Each successful mutation atomically records verified internal actor/binding digest, authority source and revision, target tenant/resource, command correlation, minimized before/after revision snapshot, applied outcome and database timestamp. No external tuple, token/email/note content is stored in administrative audit. Append-only audit denies update/delete/truncate even to its owner. Failure at audit insert or deferred commit rolls back the entire effect. Refusal records exclude attacker-supplied foreign target/payload; no customer existence oracle. Exact successful replay adds no mutation audit.

HTTP parser is bounded streaming JSON (16KiB/depth8), rejects duplicate keys at every object, escaped NUL/unpaired surrogates and unsupported shapes before database conversion. SQL validates independently. Labels are1..100 Unicode scalars, no controls; arrays are bounded, distinct same-tenant permission IDs. Labels do not grant authority.

## Dependency/security review — 3 November 2026

No product package, lock, import dependency or image version changed. New UI imports only the existing React/Next, shadcn Button/Card and private backend helpers. Pinned Node24.22.0/Next16.4.4/React19.3.1, SDK10.0.402/ASP.NET10.0.13 and existing PostgreSQL/Keycloak/Chromium images remain in use. The actual frontend image build executes locked npm ci, low-threshold audit, tests, production build and typecheck; API dependency audit remains an affected exact-head CI gate, not inferred from compilation. A temporary nonroot/read-only formatter probe used prettier3.6.2 with zero audit findings, writing no product dependencies/locks.

Official primary sources reread: `https://nextjs.org/blog/upcoming-nextjs-security-release-november-2026`, `https://nextjs.org/blog/nextjs-security-update-october-14-2026` and the `vercel/next.js` published advisory API. The latest published advisory returned by the API is the October14 set, patched in16.4.1; the November3 announcement still describes seven medium vulnerabilities without complete affected/fixed version details. This unresolved disclosure remains a reassessment gate before operational exposure, not a claim of security clearance. New authenticated SSR is force-dynamic/no-store; no Cache Components, `use cache`, Server Actions, next/image or next/og is introduced, and the existing Alpine runtime and sharp0.35.5 lock remain. No blanket clearance follows from npm audit.

## Next SSR and verification contract

Reuse fixed private HTTPS backend transport and incoming cookie only. Dynamic authenticated Italian SSR, private/no-store and no shared identity cache. Server-returned tenant/member/hierarchy/permission/role IDs drive labelled selectors; no routine manual UUID entry. Browser mutations fetch CSRF immediately before sending. Freeze target/route/UUID/serialized bytes through lost response, CSRF refusal and accepted replay whose authoritative reread fails; block SPA navigation and form changes while uncertain. Recovery is live-page only; forced reload/browser closure/new login do not restore pending commands and are not claimed durable recovery.

Required actual evidence: PostgreSQL pools1/4 and physical blocking barriers in both orderings; atomic audit insert/deferred rollback for every mutation kind; immutable audit and exact counts; signed bearer and real TLS OIDC sessions with negative/positive actual context API consumption; role and permission edits, assignment revocation and open-session immediate changes; malformed inputs, revision/idempotency conflicts, foreign scopes and ordinary/organization-only denial; authenticated Next/noJS/cache/CSRF/layout/frozen retry with SQL readback. Passing-first unchanged-code additions are regressions, not original RED. CI finite selection precedes new runtime paths, retains mixed producer consumers and fails closed on unknown executable paths. Exact-head PR checks and dispatched full_architecture=false acceptance, downloaded artifact inspection, parent-only merge/issue/Project readback. No protected service, persistent environment, deployment, real identity/data or ERP/provider change.
