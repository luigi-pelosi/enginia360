# Currency optimistic concurrency

Apply `database/migrations/20261120_currency_version.sql` once to databases that already have the currency table, before running the updated API. The migration preserves all rows and starts every existing currency at version 1. New installations get the same definition from `foundation.sql`. Back up and follow the normal migration procedure; this change does not migrate or deploy anything automatically.

Currency list items and create/update responses contain a read-only numeric `version`. Create still uses the existing payload without a version. For a conditional edit use either:

* `PUT /api/data/currencies/{id}` with currency fields and top-level `expectedVersion`, for example `{"name":"Euro","expectedVersion":1}`; or
* `PUT /api/data/currencies/{id}/save` with `{"values":{"name":"Euro"},"expectedVersion":1}`. The token belongs to the outer envelope, not `values`.

The token is a positive integer no larger than 9007199254740991. On success, the response contains the new version. A stale token returns HTTP 409 `{"code":"version_conflict"}`; no mutation or update audit is committed. Missing rows return 404. A version at the maximum returns 409 `version_exhausted` rather than overflowing. Other invalid tokens return 400. Conditional checks, the update, version change and its before/after audit run in the request transaction, under the currency row lock. Every update, including an unconditional legacy update or a direct SQL update, increments the version.

For backwards compatibility, a currency update that omits `expectedVersion` still succeeds without a stale-write check. Other resource payloads and projections are unchanged. This means unmodified legacy clients themselves are not protected from overwriting other edits, although their writes invalidate existing currency tokens.

The editor must retain the version from the authoritative read that formed the draft's original base, persist it with the draft, and submit that exact version on every restored edit. Do not replace it with the version from a later refresh before saving. On 409 keep the draft, fetch the latest currency and offer explicit reconciliation or discard; after reconciliation use the newly observed version. Drafts created before version support lack a trustworthy base token and must not be submitted as conditional updates without explicit user reconciliation. A lost successful response is not idempotency: retrying with the old token can return 409 even when the original write succeeded; reread and reconcile rather than blindly retrying. Deletion is not conditional under this contract.
