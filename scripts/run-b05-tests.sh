#!/bin/sh
set -eu
export B04_POOL_SIZE=1
project="enginia360-b05-$$"
env_file="${TMPDIR:?use a scratch directory}/${project}.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml "$@"; }
cleanup(){ compose down --volumes --remove-orphans >/dev/null 2>&1 || true; rm -f "$env_file"; }
trap cleanup EXIT INT TERM
umask 077
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" >"$env_file"
compose up -d --build --wait --wait-timeout 240
sql(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"'; }
file(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$1"' sh "$1"; }
probe(){ docker run --rm --network "${project}_backend" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 "$@"; }
b05(){ probe scripts/test-b05.py http://web:8080 "$1"; }
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
migrate(){ for f in /b05/020_catalog.sql /b05/021_commercial_lines.sql /b05/900_catalog_fixtures.sql /b05/901_commercial_fixtures.sql /b10/070_administration.sql; do file "$f"; done; }
migrate
migrate
probe scripts/test-b04.py http://web:8080 direct_order
probe scripts/test-b04.py http://web:8080 isolation_and_references
for behavior in variable arithmetic catalog service pair negatives collision_and_pool prepare_history; do b05 "$behavior"; done
docker run --rm --network "${project}_backend" -e VITE_B05_HTTP_BASE=http://web:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B05.runtime.test.tsx
# Action and each insufficient resource scope tested independently, with valid membership.
for scope in create-only other-company wrong-site warehouse-only; do
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.lines.add';
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111',
CASE WHEN '$scope'='other-company' THEN '11111111-1111-1111-1111-111111111102'::uuid ELSE '11111111-1111-1111-1111-111111111101'::uuid END,
'workshop.lines.add',
CASE WHEN '$scope'='wrong-site' THEN '11111111-1111-1111-1111-111111119999'::uuid ELSE NULL END,
CASE WHEN '$scope'='warehouse-only' THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
WHERE '$scope'<>'create-only';
SQL
 b05 denied_scope
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.lines.add';
SQL
 file /b05/901_commercial_fixtures.sql
 printf 'PASS independent B05 insufficient scope: %s\n' "$scope"
done
sql <<'SQL'
UPDATE organization_access.company_permissions SET "SiteId"='11111111-1111-1111-1111-111111110101' WHERE "Permission"='workshop.lines.add' AND "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1';
SQL
b05 pair
sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.orders.read';
SQL
b05 denied_read
file /b04/900_synthetic_fixtures.sql
# Independent multi-connection concurrency, not serialized accidentally by a pool of one.
B04_POOL_SIZE=8 compose up -d --no-deps --wait --wait-timeout 120 api
compose ps -q api | xargs docker inspect | python3 -c 'import json,sys; assert any("Maximum Pool Size=8;" in x for x in json.load(sys.stdin)[0]["Config"]["Env"]); print("PASS B05 concurrent runtime pool size 8")'
b05 concurrent
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
b05 pair
sql <<'SQL'
UPDATE catalog.items SET "Version"=2,"Label"='Master cambiato' WHERE "Id"='11111111-7777-0000-0000-000000000001';
SQL
b05 history
b05 replay_history
sql <<'SQL'
UPDATE catalog.items SET "Version"=1,"Label"='Manodopera meccanica' WHERE "Id"='11111111-7777-0000-0000-000000000001';
INSERT INTO workshop.line_policies VALUES ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-5555-0000-0000-000000000001',2,'Disabled',false);
SQL
b05 stale_policy
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='workshop' AND "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
b05 disabled
file /b05/950_rls_test.sql
compose logs --no-log-prefix api | python3 scripts/test-b05-audit.py
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
print("PASS B05: four healthy hardened containers, no published ports")'
file /b05/990_rollback.sql
file /b05/990_rollback.sql
sql <<'SQL'
DO $$ BEGIN
 ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
 ASSERT EXISTS (SELECT 1 FROM workshop.orders);
 ASSERT EXISTS (SELECT 1 FROM counterparties.counterparties);
 ASSERT NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='catalog');
END $$;
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability"='workshop' AND "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
file /b04/900_synthetic_fixtures.sql
probe scripts/test-b04.py http://web:8080 direct_order
migrate
b05 pair
printf 'PASS B05 isolated HTTP/DOM/PostgreSQL acceptance, precision rejection boundaries, snapshot/history, exact scopes, retry/concurrency, RLS/pool, audit, migration repeat and rollback/reapply.\n'
