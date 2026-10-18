#!/bin/sh
set -eu
project="enginia360-b03-$$"
env_file="${TMPDIR:?use a scratch directory}/${project}.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml "$@"; }
cleanup(){ compose down --volumes --remove-orphans >/dev/null 2>&1 || true; rm -f "$env_file"; }
trap cleanup EXIT INT TERM
umask 077
password="$(openssl rand -hex 24)"
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$password" "$password" >"$env_file"
compose up -d --build --wait --wait-timeout 240
migrate(){ compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'; }
probe(){ docker run --rm --network "${project}_backend" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 "$@"; }
migrate
migrate
for behavior in shared_identity private_destination publication common_edit company_choices search_identity isolation_and_pool; do probe scripts/test-b03.py http://web:8080 "$behavior"; done
# Test each insufficient publication scope independently, retaining real membership/common-edit.
for keep_scope in common site warehouse; do
 compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /b03/902_permission_fixtures.sql' >/dev/null
 compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v keep_scope="$1"' sh "$keep_scope" <<'SQL'
DELETE FROM organization_access.company_permissions
WHERE "MembershipId"='dddddddd-dddd-dddd-dddd-ddddddddddd1' AND "Permission"='counterparties.destination.publish'
AND (:'keep_scope'='common' OR (:'keep_scope'='site' AND "SiteId" IS NULL) OR (:'keep_scope'='warehouse' AND "WarehouseId" IS NULL));
SQL
 probe scripts/test-b03.py http://web:8080 publication
 printf 'PASS independent publication denial fixture: %s\n' "$keep_scope"
done
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /b03/902_permission_fixtures.sql' >/dev/null
probe scripts/test-b02.py http://web:8080
docker run --rm --network "${project}_backend" -e VITE_B03_HTTP_BASE=http://web:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B03.runtime.test.tsx
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f /b03/950_rls_test.sql'
compose logs --no-log-prefix api | python3 scripts/test-b03-audit.py
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
print("PASS 4 healthy hardened containers; no published ports")'
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /b03/990_rollback.sql'
remaining="$(compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM organization_access.tenants"')"
test "$remaining" = 2
migrate
probe scripts/test-b03.py http://web:8080 shared_identity
printf 'PASS B03: 7 HTTP behavior probes, B02 HTTP regression, RLS, repeat migration, destructive rollback/reapply, hardening, technical audit.\n'
