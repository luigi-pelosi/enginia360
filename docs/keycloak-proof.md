# B01 Keycloak community proof

## Scope and outcome

This is an opt-in, isolated and reversible technical proof for decision D58. It uses only generated synthetic identities and ephemeral storage. D59 subsequently accepts Keycloak as the initial identity baseline and authorizes its use in the synthetic B02 environment; this proof still does not establish production adoption, implement Enginia360 authorization or tenant context, enable MFA/federation, add a domain, or change the public bootstrap in `compose.yaml`.

The proof builds a health-enabled image from Keycloak Community 26.8.1, the current release shown by the official download page when implemented. Both Dockerfile stages pin the multi-platform OCI digest `sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244`; runtime starts the pre-built image with `--optimized` so its read-only root filesystem is retained. The browserless test runner is also version-and-digest pinned. Authentication endpoints use a one-run self-signed TLS certificate whose trust is explicitly mounted into the runner. No host port is published; the management health endpoint on port 9000 and HTTPS endpoint on 8443 remain inside an internal Docker network.

## Run

Prerequisites: Docker with Compose, OpenSSL, and enough capacity for the 1 GiB memory limit. From the repository root:

```sh
sh scripts/run-keycloak-proof.sh
```

The runner generates the administrator, confidential client and synthetic-user credentials in a private temporary directory/process environment, never prints them, starts the separate Compose project, and verifies real Keycloak behavior:

1. an anonymous user-info request is rejected with HTTP 401;
2. the synthetic password grant authenticates (this grant exists only to make the isolated browserless proof deterministic; it is not a product-flow recommendation);
3. user-info, token introspection and the server-side user session agree;
4. OIDC logout revokes the session and subsequent introspection and user-info reject the access token;
5. the container security settings and a point-in-time CPU/memory/PID sample are printed.

Cleanup is automatic on success, failure, or interruption: the Compose project and ephemeral data are removed, followed by generated credentials and certificate material. Confirm manually if the host terminates the process ungracefully:

```sh
KEYCLOAK_CERT_DIR=/nonexistent \
KEYCLOAK_ADMIN_USERNAME=unused KEYCLOAK_ADMIN_PASSWORD=unused \
docker compose -p <project-name-printed-by-docker-compose> -f compose.keycloak-proof.yaml down --volumes --remove-orphans
```

Each run uses a unique Compose project name to prevent concurrent proofs from replacing or deleting one another. If the host terminates the process before cleanup, obtain that name from `docker ps -a --filter label=com.docker.compose.project --format '{{.Label "com.docker.compose.project"}}'` and use only the matching `enginia360-keycloak-proof-*` project after checking its containers.

## Security and operational limits

- The certificate is self-signed and valid for one day. This proves encrypted transport and explicit trust in the isolated network, not public PKI, DNS, certificate renewal, or production TLS hardening.
- Keycloak uses ephemeral local storage. No backup/restore, external PostgreSQL, migration, clustering, high availability, SMTP, account recovery, brute-force policy, audit export, monitoring, load test, or availability objective is proven.
- The direct access grant handles generated test credentials only. A product login flow, MFA enrollment/recovery, and connection to an external OIDC/SAML/LDAP identity provider remain to be evaluated before adoption.
- The 1 GiB limit is a proof constraint, not production sizing. `docker stats --no-stream` is a single idle measurement and must not be interpreted as capacity planning.
- Admin and client secret values exist in runtime process/container metadata while the proof runs. They are random, synthetic, short-lived, not committed or printed by the runner, and are destroyed during cleanup. Keycloak may log generated synthetic usernames and security events, but not the generated passwords/client secret. A future persistent deployment requires a real secret manager.
- Image tags and digests must be intentionally updated together after checking official releases, upgrade notes and vulnerabilities. No full image vulnerability scan or support commitment is claimed here.

## Verification record

Test-first RED, before the proof runtime existed:

```text
KEYCLOAK_URL=https://127.0.0.1:9443 ... python3 scripts/test-keycloak-proof.py
FAIL: <urlopen error [Errno 111] Connection refused>
Exit 1
```

GREEN after the minimal isolated runtime and subsequent test-setup corrections:

```text
sh scripts/run-keycloak-proof.sh
PASS: HTTPS authentication, anonymous rejection, session validation, and logout revocation verified.
Keycloak security: user=1000:1000 readonly=true capdrop=["ALL"] no-new-privileges=["no-new-privileges:true"] ports={}
Keycloak resources: memory=559.4MiB / 1GiB cpu=8.04% pids=50
PASS: isolated Keycloak proof completed; cleanup follows.
Exit 0
```

The measurement is a point-in-time idle sample from this host. Cleanup explicitly checks both project-labeled containers and networks. Existing public-bootstrap smoke tests and all 10 API integration tests passed unchanged; npm audit reported zero known package vulnerabilities. Docker Scout was unavailable, so no full Keycloak image CVE scan is claimed. Remote CI was not changed or claimed because this proof has not yet demonstrated reliable execution on GitHub-hosted capacity.

## Rollback

There is no public-runtime migration to reverse. Stop/remove the isolated project with the cleanup command above and delete these proof files. `compose.yaml`, port 80, API and web behavior remain unchanged. If the operational burden or remaining MFA/federation/recovery/backup findings are unacceptable, retain Auth0 or another managed provider as the documented alternative; B01 does not decide adoption.
