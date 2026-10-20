#!/bin/sh
set -eu
export B04_POOL_SIZE=8
project="enginia360-b07-$$"
state="${TMPDIR:?use a scratch directory}/${project}"
mkdir -m 700 "$state"
env_file="$state/runtime.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b07-test.yaml "$@"; }
cleanup(){
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$env_file" "$state/b06-history.json" "$state/b06-retry.json"
    rmdir "$state" 2>/dev/null || true
    test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
    test -z "$(docker network ls -q --filter "label=com.docker.compose.project=$project")"
}
trap cleanup EXIT INT TERM
umask 077
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" > "$env_file"
compose up -d --build --wait --wait-timeout 240
# Fail closed before any destructive fixture command: project, network, tmpfs, no retained volumes.
compose ps -q postgres | xargs docker inspect | python3 -c 'import json,sys
p=sys.argv[1]; m=json.load(sys.stdin)[0]
assert m["Config"]["Labels"]["com.docker.compose.project"]==p
assert set(m["NetworkSettings"]["Networks"])=={p+"_backend"}
assert "/var/lib/postgresql" in m["HostConfig"]["Tmpfs"]
assert not any(x["Type"]=="volume" for x in m["Mounts"])
print("PASS ephemeral fixture identity, network and tmpfs; no retained volumes")' "$project"
sql(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"'; }
file(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$1"' sh "$1"; }
probe(){ docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b07.py http://web:8080 "$1"; }
reset(){ printf 'TRUNCATE inventory.reservations;\n' | sql; }
migrate(){ file /b06/030_inventory.sql; file /b06/900_synthetic_fixtures.sql; file /b07/040_picking.sql; file /b08/050_installation.sql; file /b09/060_carcass.sql; file /b10/070_administration.sql; }
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql /b05/020*.sql /b05/021*.sql /b05/900*.sql /b05/901*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
migrate
migrate
file /b07/040_picking.sql
file /b07/040_picking.sql
file /b07/900_synthetic_fixtures.sql
reset(){ printf 'TRUNCATE inventory.consumptions, inventory.picks, inventory.reservations;\n' | sql; }
probe smoke
for iteration in 1 2 3; do python3 scripts/test-b07-picking-race.py "$project"; done
for behavior in partial invalid references idempotency concurrent; do reset; probe "$behavior"; done
reset
docker run --rm --network "${project}_backend" -e VITE_B07_HTTP_BASE=http://web:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B07.runtime.test.tsx
for scope in common-edit site-only warehouse-only wrong-action; do
 reset
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" LIKE 'inventory.picks.%';
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',
CASE WHEN '$scope'='common-edit' THEN 'counterparties.edit' WHEN '$scope'='wrong-action' THEN 'inventory.stock.edit' ELSE permission END,
CASE WHEN '$scope' IN ('site-only','wrong-action') THEN '11111111-1111-1111-1111-111111110101'::uuid ELSE NULL END,
CASE WHEN '$scope' IN ('warehouse-only','wrong-action') THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
FROM (VALUES ('inventory.picks.read'),('inventory.picks.create')) p(permission);
SQL
 probe denied_scope
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" IN ('inventory.picks.read','inventory.picks.create','inventory.stock.edit','counterparties.edit');
SQL
 file /b07/900_synthetic_fixtures.sql
 printf 'PASS independent insufficient B07 grant: %s\n' "$scope"
done
reset
sql <<'SQL'
UPDATE inventory.picking_policies SET "PreparationEnabled"=false, "Version"=2 WHERE "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
probe disabled_area
for permission in create read; do
 reset
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='inventory.picks.$permission';
SQL
 if [ "$permission" = create ]; then probe read_only; else probe create_only; fi
 file /b07/900_synthetic_fixtures.sql
done
reset
sql <<'SQL'
UPDATE inventory.picking_policies SET "PreparationEnabled"=true, "Version"=1;
SQL
probe prepare_history
for capability in inventory workshop; do
 sql <<SQL
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='$capability';
SQL
 probe history
done
sql <<'SQL'
UPDATE inventory.picking_policies SET "PreparationEnabled"=false, "Version"=2;
UPDATE inventory.picking_locations SET "OriginLocation"='Changed', "PreparationLocation"=NULL;
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability" IN ('workshop','inventory');
SQL
probe history
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
probe history
file /b07/950_rls_test.sql
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
UPDATE inventory.picking_policies SET "PreparationEnabled"=true, "Version"=1;
UPDATE inventory.picking_locations SET "OriginLocation"='Stock A', "PreparationLocation"='Preparazione A';
SQL
reset
probe partial
file /b07/950_rls_test.sql
compose logs --no-log-prefix api | python3 scripts/test-b07-audit.py
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
print("PASS B07 four healthy hardened containers, no published ports")'
file /b09/990_rollback.sql
file /b08/990_rollback.sql
file /b07/990_rollback.sql
file /b07/990_rollback.sql
sql <<'SQL'
DO $$ BEGIN
 ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
 ASSERT EXISTS (SELECT 1 FROM inventory.reservations);
 ASSERT EXISTS (SELECT 1 FROM workshop.orders);
 ASSERT EXISTS (SELECT 1 FROM workshop.commercial_lines);
 ASSERT to_regclass('inventory.picks') IS NULL;
END $$;
SQL
file /b07/040_picking.sql
file /b08/050_installation.sql
file /b09/060_carcass.sql
file /b10/070_administration.sql
file /b07/900_synthetic_fixtures.sql
reset
probe partial
printf 'PASS B07 isolated acceptance complete; cleanup verified by EXIT trap.\n'
