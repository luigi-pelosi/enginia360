#!/bin/sh
set -eu
export B04_POOL_SIZE=8
project="enginia360-b09-$$"
state="${TMPDIR:?use a scratch directory}/${project}"
mkdir -m 700 "$state"
env_file="$state/runtime.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b07-test.yaml -f compose.b08-test.yaml -f compose.b09-test.yaml "$@"; }
cleanup(){
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$env_file" "$state/b06-history.json" "$state/b06-retry.json" "$state/b08-history.json" "$state/b09-history.json"
    rmdir "$state" 2>/dev/null || true
    test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
    test -z "$(docker network ls -q --filter "label=com.docker.compose.project=$project")"
}
trap cleanup EXIT INT TERM
umask 077
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" > "$env_file"
compose up -d --build --wait --wait-timeout 240
compose ps -q postgres | xargs docker inspect | python3 -c 'import json,sys
p=sys.argv[1]; m=json.load(sys.stdin)[0]
assert m["Config"]["Labels"]["com.docker.compose.project"]==p
assert set(m["NetworkSettings"]["Networks"])=={p+"_backend"}
assert "/var/lib/postgresql" in m["HostConfig"]["Tmpfs"]
assert not any(x["Type"]=="volume" for x in m["Mounts"])
print("PASS ephemeral fixture identity, network and tmpfs; no retained volumes")' "$project"
sql(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"'; }
file(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$1"' sh "$1"; }
probe(){ docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b09.py http://web:8080 "$1"; }
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql /b05/020*.sql /b05/021*.sql /b05/900*.sql /b05/901*.sql /b06/030*.sql /b06/900*.sql /b07/040*.sql /b07/900*.sql /b08/050*.sql /b08/900*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
file /b09/060_carcass.sql
file /b09/060_carcass.sql
file /b09/900_synthetic_fixtures.sql
reset(){
 printf 'TRUNCATE inventory.carcass_return_installations, inventory.carcass_returns, inventory.consumptions, workshop.installations, inventory.picks, inventory.reservations; UPDATE inventory.stock SET "Physical"=2; DELETE FROM workshop.carcass_policies WHERE "Version">1; DELETE FROM inventory.carcass_locations WHERE "Version">1;\n' | sql
 file /b09/900_synthetic_fixtures.sql >/dev/null
}
ui(){ docker run --rm --network "${project}_backend" -e VITE_B09_HTTP_BASE=http://web:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B09.runtime.test.tsx; }
if [ "${B09_BEHAVIOR:-all}" != all ]; then
 reset
 case "$B09_BEHAVIOR" in ui) ui ;; race) python3 scripts/test-b09-return-race.py "$project" ;; *) probe "$B09_BEHAVIOR" ;; esac
 exit
fi
probe smoke
for behavior in full late invalid unrequired idempotency concurrent references other_warehouse; do reset; probe "$behavior"; done
for iteration in 1 2 3 4 5; do reset; probe late_race; done
for iteration in 1 2 3; do python3 scripts/test-b09-return-race.py "$project"; done
reset
ui
# D38: missing or non-dedicated location is refused, never defaulted.
for mode in missing shared; do
 reset
 sql <<SQL
DELETE FROM inventory.carcass_locations WHERE '$mode'='missing' AND "WarehouseId"='11111111-1111-1111-1111-111111100101';
UPDATE inventory.carcass_locations SET "Location"='Stock A' WHERE '$mode'='shared' AND "WarehouseId"='11111111-1111-1111-1111-111111100101';
SQL
 probe unconfigured_location
 sql <<'SQL'
DELETE FROM inventory.carcass_locations;
SQL
done
# D9: later company customizing applies only to later operations.
reset
probe version_before
sql <<'SQL'
INSERT INTO workshop.carcass_policies SELECT "TenantId","LegalEntityId","DocumentTypeId","CatalogItemId",2,false FROM workshop.carcass_policies WHERE "Version"=1;
INSERT INTO inventory.carcass_locations SELECT "TenantId","LegalEntityId","SiteId","WarehouseId",2,"Location"||'2' FROM inventory.carcass_locations WHERE "Version"=1;
SQL
probe version_after
for scope in common-edit site-only warehouse-only wrong-action; do
 reset
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" LIKE 'inventory.carcass-returns.%';
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',
CASE WHEN '$scope'='common-edit' THEN 'counterparties.edit' WHEN '$scope'='wrong-action' THEN 'inventory.consumptions.create' ELSE permission END,
CASE WHEN '$scope' IN ('site-only','wrong-action') THEN '11111111-1111-1111-1111-111111110101'::uuid ELSE NULL END,
CASE WHEN '$scope' IN ('warehouse-only','wrong-action') THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
FROM (VALUES ('inventory.carcass-returns.read'),('inventory.carcass-returns.create')) p(permission);
SQL
 probe denied_scope
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND ("Permission" LIKE 'inventory.carcass-returns.%' OR "Permission"='counterparties.edit' OR "Permission"='inventory.consumptions.create');
SQL
 file /b08/900_synthetic_fixtures.sql
 file /b09/900_synthetic_fixtures.sql
 printf 'PASS B09 independent insufficient grant: %s\n' "$scope"
done
for permission in create read; do
 reset
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='inventory.carcass-returns.$permission';
SQL
 if [ "$permission" = create ]; then probe read_only; else probe create_only; fi
 file /b09/900_synthetic_fixtures.sql
done
reset
# Fault AFTER the return INSERT, before the installation links: the Inventory transaction must roll back both.
sql <<'SQL'
CREATE FUNCTION inventory.test_carcass_link_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Synthetic carcass link fault'; END $$;
CREATE TRIGGER test_carcass_link_failure BEFORE INSERT ON inventory.carcass_return_installations FOR EACH ROW EXECUTE FUNCTION inventory.test_carcass_link_failure();
SQL
probe fault
sql <<'SQL'
DO $$ BEGIN ASSERT (SELECT count(*) FROM inventory.carcass_returns)=0; ASSERT (SELECT count(*) FROM inventory.carcass_return_installations)=0; END $$;
DROP TRIGGER test_carcass_link_failure ON inventory.carcass_return_installations;
DROP FUNCTION inventory.test_carcass_link_failure();
SQL
compose restart api
compose up -d --no-deps --wait --wait-timeout 120 api
probe recover
for capability in inventory workshop; do
 sql <<SQL
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='$capability';
SQL
 probe history
done
file /b09/950_rls_test.sql
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
probe history
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN ('workshop','inventory');
SQL
for behavior in full late; do reset; probe "$behavior"; done
file /b09/950_rls_test.sql
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
print("PASS B09 four healthy hardened containers, no published ports")'
file /b09/990_rollback.sql
file /b09/990_rollback.sql
sql <<'SQL'
DO $$ BEGIN
 ASSERT to_regclass('inventory.carcass_returns') IS NULL AND to_regclass('inventory.carcass_return_installations') IS NULL;
 ASSERT to_regclass('inventory.carcass_locations') IS NULL AND to_regclass('workshop.carcass_policies') IS NULL;
 ASSERT NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='workshop' AND table_name='installations' AND column_name LIKE 'Carcass%');
 ASSERT EXISTS (SELECT 1 FROM workshop.installations) AND EXISTS (SELECT 1 FROM inventory.consumptions);
 ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
END $$;
SQL
# Previous B08 schema remains usable by the app role after B09 rollback.
sql <<'SQL'
BEGIN;
SET LOCAL ROLE :"app_user";
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
SELECT count(*) FROM workshop.installations;
SELECT "Physical" FROM inventory.stock FOR UPDATE;
ROLLBACK;
SQL
file /b09/060_carcass.sql
file /b09/900_synthetic_fixtures.sql
reset
probe full
compose logs --no-log-prefix api | python3 scripts/test-b09-audit.py
printf 'PASS B09 isolated acceptance complete; cleanup verified by EXIT trap.\n'
