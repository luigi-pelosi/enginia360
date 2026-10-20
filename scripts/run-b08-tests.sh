#!/bin/sh
set -eu
export B04_POOL_SIZE=8
project="enginia360-b08-$$"
state="${TMPDIR:?use a scratch directory}/${project}"
mkdir -m 700 "$state"
env_file="$state/runtime.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b07-test.yaml -f compose.b08-test.yaml "$@"; }
cleanup(){
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$env_file" "$state/b06-history.json" "$state/b06-retry.json" "$state/b08-history.json"
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
probe(){ docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b08.py http://web:8080 "$1"; }
reset(){ printf 'TRUNCATE inventory.reservations;\n' | sql; }
migrate(){ file /b06/030_inventory.sql; file /b06/900_synthetic_fixtures.sql; }
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql /b05/020*.sql /b05/021*.sql /b05/900*.sql /b05/901*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
migrate
migrate
file /b07/040_picking.sql
file /b07/040_picking.sql
file /b07/900_synthetic_fixtures.sql

file /b08/050_installation.sql
file /b09/060_carcass.sql
file /b10/070_administration.sql
file /b08/900_synthetic_fixtures.sql
reset(){ printf 'TRUNCATE inventory.consumptions, workshop.installations, inventory.picks, inventory.reservations; UPDATE inventory.stock SET "Physical"=2;\n' | sql; }
ui(){ docker run --rm --network "${project}_backend" -e VITE_B08_HTTP_BASE=http://web:8080 -e VITE_B08_STOCK_FAULT="${B08_UI_STOCK_FAULT:-false}" -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B08.runtime.test.tsx; }
if [ "${B08_BEHAVIOR:-all}" = ui ]; then ui; exit; fi
if [ "${B08_BEHAVIOR:-all}" != all ]; then
 if [ "$B08_BEHAVIOR" = race ]; then python3 scripts/test-b08-installation-race.py "$project"; else probe "$B08_BEHAVIOR"; fi
 exit
fi
file /b08/050_installation.sql
probe smoke
for behavior in partial invalid references idempotency concurrent; do reset; probe "$behavior"; done
for iteration in 1 2 3; do python3 scripts/test-b08-installation-race.py "$project"; done
reset
ui
reset
sql <<'SQL'
CREATE SEQUENCE inventory.test_stock_fault_sequence;
GRANT USAGE, SELECT ON SEQUENCE inventory.test_stock_fault_sequence TO :"app_user";
CREATE FUNCTION inventory.test_once_stock_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
 IF nextval('inventory.test_stock_fault_sequence')=1 THEN RAISE EXCEPTION 'Synthetic once-only stock fault'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER test_once_stock_fault BEFORE UPDATE ON inventory.stock FOR EACH ROW EXECUTE FUNCTION inventory.test_once_stock_fault();
SQL
B08_UI_STOCK_FAULT=true ui
sql <<'SQL'
DROP TRIGGER test_once_stock_fault ON inventory.stock;
DROP FUNCTION inventory.test_once_stock_fault();
DROP SEQUENCE inventory.test_stock_fault_sequence;
SQL
for scope in common-edit site-only warehouse-only wrong-action workshop-missing; do
 reset
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" LIKE 'inventory.consumptions.%';
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',
CASE WHEN '$scope'='common-edit' THEN 'counterparties.edit' WHEN '$scope'='wrong-action' THEN 'inventory.stock.edit' ELSE permission END,
CASE WHEN '$scope' IN ('site-only','wrong-action','workshop-missing') THEN '11111111-1111-1111-1111-111111110101'::uuid ELSE NULL END,
CASE WHEN '$scope' IN ('warehouse-only','wrong-action','workshop-missing') THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
FROM (VALUES ('inventory.consumptions.read'),('inventory.consumptions.create')) p(permission);
DELETE FROM organization_access.company_permissions WHERE '$scope'='workshop-missing' AND "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" LIKE 'workshop.installations.%';
SQL
 probe denied_scope
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" IN ('inventory.consumptions.read','inventory.consumptions.create','inventory.stock.edit','counterparties.edit');
SQL
 file /b08/900_synthetic_fixtures.sql
 printf 'PASS B08 independent insufficient grant: %s\n' "$scope"
done
for action in workshop.installations inventory.consumptions; do
 for permission in create read; do
  reset
  sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='$action.$permission';
SQL
  if [ "$permission" = create ]; then probe read_only; else probe create_only; fi
  file /b08/900_synthetic_fixtures.sql
 done
done
reset
# Fault AFTER consumption INSERT but BEFORE physical update: both Inventory effects must roll back.
sql <<'SQL'
CREATE FUNCTION inventory.test_stock_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic stock update fault'; END $$;
CREATE TRIGGER test_stock_failure BEFORE UPDATE ON inventory.stock FOR EACH ROW EXECUTE FUNCTION inventory.test_stock_failure();
SQL
probe fault
sql <<'SQL'
DO $$ BEGIN ASSERT (SELECT count(*) FROM workshop.installations)=1; ASSERT (SELECT count(*) FROM inventory.consumptions)=0; END $$;
DROP TRIGGER test_stock_failure ON inventory.stock;
DROP FUNCTION inventory.test_stock_failure();
SQL
compose restart api
compose up -d --no-deps --wait --wait-timeout 120 api
probe recover
for capability in inventory workshop; do
 sql <<SQL
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='$capability';
UPDATE inventory.picking_policies SET "Version"=2,"PreparationEnabled"=false;
UPDATE inventory.picking_locations SET "OriginLocation"='Changed',"PreparationLocation"=NULL;
SQL
 probe history
done
file /b08/950_rls_test.sql
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
probe history
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
SQL
reset
probe partial
reset
probe idempotency
file /b08/950_rls_test.sql
# Same hardening assertions as B07; four healthy containers, no host bindings.
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
print("PASS B08 four healthy hardened containers, no published ports")'
file /b09/990_rollback.sql
file /b08/990_rollback.sql
file /b08/990_rollback.sql
# Earlier B06 SELECT FOR UPDATE requires its pre-existing column privilege after rollback.
sql <<'SQL'
BEGIN;
SET LOCAL ROLE :"app_user";
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
SELECT "Physical" FROM inventory.stock FOR UPDATE;
ROLLBACK;
SQL
sql <<'SQL'
DO $$ BEGIN
 ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
 ASSERT EXISTS (SELECT 1 FROM inventory.picks);
 ASSERT EXISTS (SELECT 1 FROM workshop.orders);
 ASSERT to_regclass('inventory.consumptions') IS NULL;
 ASSERT to_regclass('workshop.installations') IS NULL;
 ASSERT (SELECT "Physical" FROM inventory.stock LIMIT 1)=2;
END $$;
SQL
file /b08/050_installation.sql
file /b09/060_carcass.sql
file /b10/070_administration.sql
reset
probe partial
compose logs --no-log-prefix api | python3 scripts/test-b08-audit.py
printf 'PASS B08 isolated acceptance complete; cleanup verified by EXIT trap.\n'
