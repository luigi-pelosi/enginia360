# ADR-0001 — Infrastructure bootstrap, not product approval

- Status: accepted for this explicitly requested technical bootstrap only.
- Foundation dossier: **NOT APPROVED**. This document is not that dossier.
- Charter: PROJECT_CHARTER.md remains unchanged and authoritative for the future product.

## Context and boundary

The owner explicitly requested a publicly reachable always-on Docker foundation before domain implementation. This is a narrow infrastructure task, not implicit approval of charter §12 or completion of its §11 vertical slice. The entire charter was read. No domain investigation of SmartData was necessary for a stateless technical status page; SmartData was neither modified nor made a dependency. No observed legacy rule is asserted as validated.

## Decision

One ASP.NET Core .NET 10 API and one static React/TypeScript UI behind nginx, composed on a single Linux host. Only nginx publishes host port 80. API port 8080 is confined to the internal Docker network. No business modules, tenant/user operations, identity provider, demonstration records or business CRUD. No PostgreSQL container: there is no persisted application state to justify database credentials, migrations, backup burden or an exposed database. PostgreSQL remains the charter direction for future approved persistence.

Status returns explicit bootstrap metadata, not an uptime estimate, fabricated infrastructure inventory, domain readiness or externally verified service availability. Both health endpoints describe only a running HTTP process; readiness currently has no database or third-party dependencies. The UI validates the actual status response and distinguishes loading, available and unavailable. OpenAPI is the generated JSON contract, not an interactive Swagger UI.

Incoming X-Correlation-ID is accepted only as a single 1–64-character ASCII alphanumeric, hyphen or underscore token; anything else is replaced by a random 32-hex token. It is echoed on API responses and included in structured application log scopes. Values remain untrusted, may collide and confer no access. nginx does not forge identities or accept forwarded identity context. Application completion logs contain only method, status and correlation ID; nginx access logs are disabled to avoid retaining client addresses and arbitrary query strings. Framework request logging is reduced. Container log rotation is bounded. There is no audit trail, metrics backend, distributed tracing collector or full OpenTelemetry integration; these are deferred, not claimed as implemented.

## Security and operational limits

This is a public, unauthenticated technical demonstration over **HTTP without TLS**. Never send credentials, personal data or business data. TLS/domain, provider choice, tenant isolation and authorization tests, threat model, fiscal validation, backup policies, external monitoring, rate limiting and production hardening require subsequent explicit work. Docker daemon privilege remains a host responsibility. Restart policy recovers exited containers, not merely unhealthy ones; a live but unhealthy process requires operator intervention. Single host/network/power failure remains an outage. No uptime, RPO or RTO commitment is made. No provider or hosting jurisdiction is inferred from the host IP.

Dependencies are exact-version pinned with npm/NuGet lockfiles; container references are pinned by tag and digest. Updating base images requires intentional digest refresh, vulnerability review and rerunning verification. No image vulnerability scanner or remote CI result is claimed by this bootstrap.

## Acceptance

API status, process health and OpenAPI are executable integration-tested; correlation inputs include safe, malformed, empty, multi-value and oversized tokens. React tests cover a real-client fetch contract using a network boundary stub, malformed responses and failure visibility. Docker build executes UI tests and typecheck. HTTP smoke checks exercise nginx → API on deployment. These tests are not proof of the charter’s tenant isolation, accounting or first vertical slice: none exists yet.
