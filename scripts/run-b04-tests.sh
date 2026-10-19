#!/bin/sh
set -eu
export B04_POOL_SIZE=1
project="enginia360-b04-$$"
env_file="${TMPDIR:?use a scratch directory}/${project}.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml "$@"; }
cleanup(){ compose down --volumes --remove-orphans >/dev/null 2>&1 || true; rm -f "$env_file"; }
trap cleanup EXIT INT TERM
umask 077
owner_password="$(openssl rand -hex 24)"
app_password="$(openssl rand -hex 24)"
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$owner_password" "$app_password" >"$env_file"
compose up -d --build --wait --wait-timeout 240
sql(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"' ; }
file(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$1"' sh "$1"; }
migrate_b03(){ compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'; }
migrate(){ file /b04/010_workshop.sql; file /b04/900_synthetic_fixtures.sql; }
probe(){ docker run --rm --network "${project}_backend" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 "$@"; }
b04(){ probe scripts/test-b04.py http://web:8080 "$1"; }
migrate_b03
# Exercise B02/B03 before the B04-only fixture intentionally narrows company B access.
probe scripts/test-b02.py http://web:8080
for behavior in shared_identity private_destination publication common_edit company_choices search_identity isolation_and_pool; do probe scripts/test-b03.py http://web:8080 "$behavior"; done
migrate
migrate
for behavior in direct_order invalid_command_id context_and_types isolation_and_references concurrent_retry command_id_collision prepare_history; do b04 "$behavior"; done
docker run --rm --network "${project}_backend" -e VITE_B04_HTTP_BASE=http://web:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B04.runtime.test.tsx
# Separate valid same-tenant action/resource denial from tenant RLS.
for scope in read-only different-site warehouse-only; do
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.orders.create';
INSERT INTO organization_access.company_permissions VALUES (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','workshop.orders.create',
CASE WHEN '$scope'='different-site' THEN '11111111-1111-1111-1111-111111119999'::uuid ELSE NULL END,
CASE WHEN '$scope'='warehouse-only' THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END);
DELETE FROM organization_access.company_permissions WHERE '$scope'='read-only' AND "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.orders.create';
SQL
 b04 denied_scope
 printf 'PASS independent workshop insufficient scope: %s\n' "$scope"
 migrate
 done
# Site-limited grant to this exact header site is sufficient; warehouse-limited is not.
sql <<'SQL'
UPDATE organization_access.company_permissions SET "SiteId"='11111111-1111-1111-1111-111111110101'
WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.orders.create';
SQL
b04 direct_order
sql <<'SQL'
UPDATE organization_access.company_permissions SET "SiteId"=NULL WHERE "Permission"='workshop.orders.create';
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.orders.read';
SQL
b04 denied_read
migrate
# Do not let a one-connection pool accidentally serialize the concurrency proof.
B04_POOL_SIZE=8 compose up -d --no-deps --wait --wait-timeout 120 api
compose ps -q api | xargs docker inspect | python3 -c 'import json,sys
assert any(x.startswith("ConnectionStrings__OrganizationAccess=") and "Maximum Pool Size=8;" in x for x in json.load(sys.stdin)[0]["Config"]["Env"])
print("PASS B04 concurrent retry runtime configured with pool size 8")'
b04 concurrent_retry
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
b04 direct_order
file /b04/910_superseded_configuration.sql
b04 superseded_configuration
b04 historical_read
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='workshop' AND "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
b04 historical_read
b04 denied_scope
file /b04/950_rls_test.sql
compose logs --no-log-prefix api | python3 scripts/test-b04-audit.py
compose ps -q | xargs docker inspect | python3 -c 'import json,sys
items=json.load(sys.stdin); assert len(items)==4
for item in items:
 c=item["HostConfig"]
 assert item["Config"]["User"] not in ("","0","root")
 assert c["ReadonlyRootfs"] and c["CapDrop"]==["ALL"] and "no-new-privileges:true" in c["SecurityOpt"]
 assert c["Memory"]>0 and c["NanoCpus"]>0 and c["PidsLimit"]>0
 assert c["LogConfig"]["Config"]["max-size"] and c["LogConfig"]["Config"]["max-file"]
 assert all(v is None for v in (item["NetworkSettings"]["Ports"] or {}).values())
 assert item["State"]["Health"]["Status"]=="healthy"
print("PASS B04: 4 healthy hardened containers, no published ports")'
file /b04/990_rollback.sql
file /b04/990_rollback.sql
sql <<'SQL'
DO $$ BEGIN
ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
ASSERT (SELECT count(*) FROM counterparties.counterparties)=2;
ASSERT NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname IN ('workshop','vehicles'));
END $$;
SQL
migrate_b03
probe scripts/test-b03.py http://web:8080 shared_identity
migrate
b04 direct_order
printf 'PASS B04 isolated acceptance: HTTP, DOM/HTTP, exact scopes, historical read, configuration, SQL RLS/pool, migration repeat, rollback/reapply, minimized audit, hardening and B02/B03 regression.\n'
