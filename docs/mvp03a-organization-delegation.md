# MVP-03.a — tenant-scoped organization delegation

Status: finite implementation candidate for #158 (parent #142), 3 November 2026; local evidence in [execution checkpoint](mvp03a-progress.md), remote acceptance pending. Not delivered or operationally ready. This file was absent at the verified 095abca baseline; this contract transcribes the live #158 and explicit delivery instruction, not a new policy decision.

## Resumed execution authorization

The original executor launch approval timed out with explicit no-consent/no-retry; that executor did not run and produced no code, tests or commits. This remains historical non-consent, not behavioral RED evidence. On 3 November 2026 the owner answered exactly «Autorizzo» to the coordinator's question authorizing resumption of #158 and resubmission through the normal execution-approval gate. That explicit resumed authorization permits a normal gated retry, not a bypass or scope expansion. A renewed no-retry refusal must stop that action.

## Authority and scope

Only the current exact trusted SUPER ADMIN binding may grant or revoke organization-structure administration. The target is an existing trusted exact external-identity binding and membership in one selected tenant. Registration is not authority. No identity, membership, role, scope or invitation is created as a side effect.

An active exact delegate may read that tenant's structure and create/rename its companies, sites and warehouses using the existing finite organization commands, revision and immutable historical replay semantics. No global tenant directory, tenant creation/rename, other-tenant structure, delegation management, user administration, business rights, SUPER ADMIN promotion, self-grant or subdelegation follows. Ordinary membership cardinality and note/operative permissions remain unchanged. User invitation/enabling and finite role assignability are MVP03.b, not this contract; #142 remains open.

## Boundary and persistence

Server verifies signed authenticated internal identity/issuer/subject and current binding, owner or delegation, exact target membership and tenant on every read, mutation and replay. Serialize grant/revoke and dependent operations with the owner-revocation transaction boundary; hold relevant binding/membership rows through commit. No stale bearer/session claim is authority. Replay after revocation is forbidden; an authorized exact replay returns its original immutable snapshot even after later edits. A changed actor, binding, target or payload with the same command UUID conflicts without writes or foreign-state disclosure.

Append-only migration 0038 may add finite tables/functions/policies. Preserve all 37 published migration bytes. Function owner is non-superuser/NOBYPASS with pinned search_path and FORCE RLS; app gets finite EXECUTE, never unrestricted organization/delegation DML or RLS bypass. Audit is immutable, atomic with mutation, minimized (no tokens, names/email/issuer/subject personal directory); freeze exact target binding using a digest or internal reference. Revisions are optimistic with controlled exhaustion. Refuse invalid/duplicate/oversized JSON and malformed Unicode at the real HTTP boundary; CSRF/no-store/session security remain mandatory.

## API and UI

Reuse the current organization API/Next workspace without weakening the global owner workflow. Owner has a minimal authorized selector of existing trusted memberships for the selected tenant, not a global identity directory. UI shows enough opaque/internal synthetic identity information to select without routine manual UUID entry, and current delegation/revision. Grant and revoke are explicit owner actions. Delegate sees only own authorized tenant structure; do not activate a business context or infer a grant from the menu.

Freeze route, UUID and serialized command bytes on uncertain responses for both delegation and structure commands. Repeated retries must survive a later CSRF failure and an accepted replay followed by failed authoritative reread, without new commands or changed target. Block form/target/SPA navigation while uncertain. Existing limitation: pending commands live in the current page only; forced reload/new login is not durable recovery. This remains disclosed, not waived for operational release.

## Required evidence

Behavioral RED before each changed production path, then GREEN on actual PostgreSQL, real signed-bearer/OIDC HTTP and Next browser. Test pools 1 and 4, physical-connection barriers in both revoke/mutation orderings, owner/actor/target binding loss, membership boundary, grant/revoke retry/conflict and atomic insert/deferred-commit rollback, immutable/minimized audit, command collisions, historical replay after edit and refusal after revoke. Verify no new membership/business privilege and direct DML denial. Preserve original raw RED/GREEN captures and hashes.

Extend fail-closed finite CI mapping tests before new executable paths; retain directly affected authentication, identity, organization, frontend and security consumers. Run locked tests/typecheck/build/audits and current official dependency/security review without hiding warnings. PR-only selected checks plus exact-head dispatch full_architecture=false; every selected job and actual test step succeeds, artifact contents read back. A skip is not acceptance. No default historical ERP/full-architecture campaign and no assertion/budget weakening.

## Dependency review — 3 November 2026

No dependencies or lock entries changed. Existing pins are Next16.4.4, React19.3.1, sharp0.35.5, SDK10.0.402 and ASP.NET10.0.13. The frontend's locked Docker verification executes npm audit at low threshold, tests, production build and typecheck. API dependency audit is an exact-head affected CI gate, not inferred from compilation.

Primary references reread: `https://nextjs.org/blog/security`, `https://nextjs.org/blog/upcoming-nextjs-security-release-november-2026`, `https://nextjs.org/blog/nextjs-security-update-october-14-2026`, official `vercel/next.js` security-advisory API, and `https://github.com/dotnet/announcements/issues/451`. At lookup the November3 Next announcement described seven medium issues but did not supply the full advisories or patched versions. This remains an explicit reassessment gate before operational exposure; npm audit is not proof against undisclosed issues. October14 Next advice names fixes in16.4.1 for cache/typed-array, SVG image optimization and Server Actions paths. This candidate adds no `use cache`, Server Actions, next/image or next/og use; authenticated SSR remains dynamic/no-store, cacheComponents is not enabled, production standalone runs on pinned Alpine and sharp0.35.5. This is a bounded applicability review, not security clearance. The Microsoft advisory451 affects Windows WPF packages; this candidate runs ASP.NET on Linux and does not reference WindowsDesktop. Recheck new advisories at release time.

## Delivery and safety

One implementation writer in the owned feat/mvp-organization-delegation worktree based on 095abca4656bffa626e259f7f4aa8237d6afdf26. Conventional commits, push, merge-ready PR with Refs #158 and Refs #142, no closing keywords. Parent alone merges and changes issue/Project state. Preserve progress checkpoints, clean committed worktree and exact head/tree/run/artifact evidence. No deployment, public exposure, real data, secrets, new persistent environment, provider/ERP changes, protected services/storage or Tailscale443->9119 modifications. Synthetic IdP is a real isolated authentication fixture, not an auth stub; runtime nonroot/read-only/internal/no host ports. Restore owned fixture files to 0444 after bounded writes.
