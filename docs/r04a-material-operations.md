# R04.a.1 — MaterialOperations runtime panel

Sub-issue #70 of #44; #44 and R04.b/R04.c remain open. Scope is only already-approved D69/D71/D72/D73 commands in the opt-in cookie/OIDC runtime workspace. No receiving, replenishment, supplier order, new-part return, release, cancellation, handover, ERP call, real data, purchase, deployment or persistent environment is introduced.

## Contract

- The panel selects a saved Part line and an authorized warehouse of the header company/site. Reads keep warehouse physical/available/active commitment/consumed separate from the cumulative line reserved/residual across warehouses. Quantities are invariant q6 strings; aggregate parsing is not capped as a single command input.
- Reserve is explicit, never truncated. Pick is for one reservation, install for one pick, carcass for the whole outstanding line residual with exact covered installation IDs. Picking records origin/optional placement but does not decrement stock; installation `Pending` is an accepted technical fact and recovery replays the original installation ID and quantity.
- Owner read projections add advisory `CanReserve/CanPick/CanInstall/CanRecoverConsumption/CanReceiveCarcass` flags. They are computed after the read transaction is released, with the same exact authorization ports and capability as commands; commands always revalidate. They do not create permissions or delegation.
- Uncertain transport freezes the original URL/UUID/body until identical retry. A successful POST followed by a failed GET is shown as unverified, never as an optimistic reread. An optional logistics error does not clear the saved commercial summary.

## D76 company stock authority

Migration `0021_company_stock_profile` is append-only and fixture-free. `company_stock_profiles` is company scoped, forced-RLS, immutable and separate from the tenant-wide counterparties master authority. Setup is offline through `scripts/owner-stock-profile.py`, using a verified existing binding/membership, an explicit evidence reference and the nonprivileged database owner connection; the reference is not proof that verification occurred. The tool supports only initial setup (`expectedVersion=0`). Local setup is refused after existing uncaptured material facts (`original_stock_profile_missing`), preventing retroactive authority and local fallback.

Missing or external profiles block only dependent local stock writes (`stock_profile_missing/external`; install/recovery is refused through the owning projection). Reads and history remain available. There is no ERP stock client, synchronization, switching workflow or pilot value.

## Evidence

`python3 scripts/run-r04a-tests.py` runs trusted-TLS Chromium → OIDC → nginx/API → PostgreSQL on a random ephemeral Compose project, no host ports or persistent volumes, default pool 4. `R04A_POOL_SIZE=1` runs the same public-contract sequence on one connection; the two-waiter barriers are pool-4-only and use `pg_blocking_pids` rather than sleeps. `python3 scripts/test-r04a-lifecycle.py` sends TERM while Chromium and a separate SQL stock lock are alive. The runner also verifies Decimal stock equations, installation coverage, group provenance, owner-only profile privileges, migration replay and synthetic backup/restore in private tmpfs.

CI remains pull-request-only automatically. `affected-r04a` runs only through exact-head dispatch with `full_architecture=false`; a skipped job is not a pass. The previous R03.a.2 runtime job is still required when the selector maps shared Workshop/Inventory paths.

## Limits and rollback

This is synthetic technical acceptance, not pilot readiness. Setup is manual, initial only and has no UI. The owner setup tool does not prove identity verification. Existing local-history companies need a separate approved migration policy before stock writes can resume. Rollback requires restoring the verified backup or a forward fix; do not drop migration history or physical stock history. Protected bootstrap, Tailscale 443 → 9119, 25 retained volumes/backups/configuration and the old R00 worktree are untouched.
