# Engineering standards

Read all of PROJECT_CHARTER.md before editing. This repository is Enginia360, not SmartData. Do not modify or depend on SmartData. See docs/bootstrap.md for the limited bootstrap authorization and foundation decisions D58, D70–D73. The synthetic/ephemeral B01–B14 slice is complete; the only current post-slice authorization is C00 documentation reconciliation and safe technical cleanup. UI01 being Ready does not authorize implementation, a pilot, production use or deployment. No new persistent manual environment or public deployment is authorized.

- Implement only the authorized behavior, with a failing executable test before production code (RED → GREEN → REFACTOR). Report exact commands and outcomes.
- Use English identifiers, immutable contracts, nullable reference types and warnings as errors. Italian is the initial UI language. No speculative abstractions or domain modules.
- Keep tenant, identity, fiscal and accounting decisions pending human approval. Never add business data, fake demonstrations or authentication without explicit scope.
- Never commit secrets, personal data, generated build files or local configuration. Validate all untrusted input. Correlation tokens are technical identifiers, never authentication or trusted identity.
- Lock dependencies and explicitly pin image versions. Update locks intentionally and run security audits; do not disable audit warnings to force builds through.
- Run API integration tests, UI tests/typecheck/build, Compose health checks and HTTP smoke tests. CI is not verified until executed on the remote platform.
- Containers must run nonroot, read-only, with dropped capabilities, no privilege escalation, bounded resources/logs and no public backend/database ports.
- Document limitations and rollback for every deployment change. Do not claim availability guarantees from a single-host bootstrap. Never create an interface or service solely for hypothetical future requirements.
