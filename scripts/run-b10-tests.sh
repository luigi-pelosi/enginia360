#!/bin/sh
# Synthetic ephemeral B10 acceptance; no published ports or retained volumes.
set -eu
export B04_POOL_SIZE=8
project="enginia360-b10-$$"
state="${TMPDIR:?use a scratch directory}/${project}"
mkdir -m 700 "$state"
env_file="$state/runtime.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b07-test.yaml -f compose.b08-test.yaml -f compose.b09-test.yaml -f compose.b10-test.yaml "$@"; }
cleanup(){
    compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    rm -f "$env_file" "$state/b10-history.json" "$state/b11-audit.jsonl"
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
print("PASS B10 ephemeral fixture identity, private network and tmpfs")' "$project"
sql(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"'; }
file(){ compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$1"' sh "$1"; }
probe(){ docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b10.py http://web:8080 "$1"; }
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql /b05/020*.sql /b05/021*.sql /b05/900*.sql /b05/901*.sql /b06/030*.sql /b06/900*.sql /b07/040*.sql /b07/900*.sql /b08/050*.sql /b08/900*.sql /b09/060*.sql /b09/900*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
file /b10/070_administration.sql
file /b10/070_administration.sql
file /b11/080_continuity.sql
file /b12/090_billing.sql
file /b10/900_synthetic_fixtures.sql
file /b11/900_synthetic_fixtures.sql
reset(){
 printf 'TRUNCATE billing.invoice_journal_links, billing.invoice_confirmations, billing.invoices, workshop.internal_billing_claims, integrations.administrative_reconciliations, workshop.administrative_closures, workshop.administrative_outcomes, workshop.administrative_outbox, workshop.administrative_requests, workshop.technical_closures, integrations.administrative_dispatches, inventory.carcass_return_installations, inventory.carcass_returns, inventory.consumptions, workshop.installations, inventory.picks, inventory.reservations; UPDATE inventory.stock SET "Physical"=20; DELETE FROM workshop.administrative_destinations WHERE "Version">1; UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability" IN (%s);\n' "'workshop','inventory','external-administration'" | sql
 file /b09/900_synthetic_fixtures.sql >/dev/null
 file /b10/900_synthetic_fixtures.sql
file /b11/900_synthetic_fixtures.sql >/dev/null
}
ui(){ docker run --rm --network "${project}_backend" -e VITE_B10_HTTP_BASE=http://web:8080 -e VITE_B10_SIMULATOR=http://admin-simulator:8080 -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B10.runtime.test.tsx; }
grants(){
 sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" IN ('workshop.orders.complete-technical','workshop.administrative-requests.create','workshop.administrative-requests.read','workshop.orders.complete-administrative');
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',
CASE WHEN '$1'='common-edit' THEN 'counterparties.edit' WHEN '$1'='wrong-action' THEN 'workshop.orders.read' ELSE permission END,
CASE WHEN '$1'='other-site' THEN '11111111-1111-1111-1111-111111110201'::uuid ELSE '11111111-1111-1111-1111-111111110101'::uuid END,
CASE WHEN '$1'='warehouse-only' THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
FROM (VALUES ('workshop.orders.complete-technical'),('workshop.administrative-requests.create'),('workshop.administrative-requests.read'),('workshop.orders.complete-administrative')) p(permission)
WHERE permission <> '$2';
SQL
}
restore_grants(){
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission" IN ('workshop.orders.complete-technical','workshop.administrative-requests.create','workshop.administrative-requests.read','workshop.orders.complete-administrative','counterparties.edit');
SQL
 file /b10/900_synthetic_fixtures.sql
file /b11/900_synthetic_fixtures.sql >/dev/null
}
paused(){
 reset
 probe paused_prepare
 printf "UPDATE organization_access.capability_activations SET \"Enabled\"=false WHERE \"Capability\"='external-administration';\n" | sql
 probe paused_check
 printf "UPDATE organization_access.capability_activations SET \"Enabled\"=true WHERE \"Capability\"='external-administration';\n" | sql
 probe paused_resume
}
b11probe(){ docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b11.py http://web:8080 "$1"; }
restart_api(){
 if [ "${B11_FORCE_API_RECREATE:-false}" = true ]; then
  compose up -d --no-deps --force-recreate --wait --wait-timeout 90 api
 else
  compose up -d --no-deps --wait --wait-timeout 90 api
 fi
}
lease_test(){
 reset
 b11probe restart_prepare
 request_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["saved"]["id"])' "$state/b10-history.json")
 sql <<SQL
UPDATE integrations.administrative_dispatches SET "State"='NeedsReconciliation', "Failures"=4, "LeaseUntil"=now()+interval '20 minutes'
WHERE "TenantId"='11111111-1111-1111-1111-111111111111' AND "RequestId"='$request_id';
SQL
 b11probe lease_verify
}
fairness_test(){
 reset
 printf 'UPDATE inventory.stock SET "Physical"=200;\n' | sql
 b11probe fairness
}
if [ "${B10_BEHAVIOR:-all}" = b11 ] && [ "${B11_BEHAVIOR:-all}" = fairness ]; then fairness_test; exit; fi
if [ "${B10_BEHAVIOR:-all}" = b11 ] && [ "${B11_BEHAVIOR:-all}" = lease ]; then lease_test; exit; fi
if [ "${B10_BEHAVIOR:-all}" = b11 ] && [ "${B11_BEHAVIOR:-all}" = all ]; then
 file /b11/080_continuity.sql
 lease_test
 fairness_test
 reset; b11probe uncertain
 reset; b11probe reconcile
 reset; b11probe recovery_prepare
 if file /b11/990_rollback.sql > "$state/rollback-block.log" 2>&1; then
  printf 'FAIL unsafe B11 rollback accepted unresolved uncertainty\n'; exit 1
 fi
 rm -f "$state/rollback-block.log"
 printf 'PASS B11 rollback refuses unresolved uncertainty rather than enabling blind resubmission\n'
 for scope in no-action other-site warehouse-only; do
  sql <<SQL
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.administrative-requests.reconcile';
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',
 'workshop.administrative-requests.reconcile',
 CASE WHEN '$scope'='other-site' THEN '11111111-1111-1111-1111-111111110201'::uuid ELSE '11111111-1111-1111-1111-111111110101'::uuid END,
 CASE WHEN '$scope'='warehouse-only' THEN '11111111-1111-1111-1111-111111100101'::uuid ELSE NULL END
WHERE '$scope'<>'no-action';
SQL
  b11probe recovery_denied
  printf 'PASS B11 independent insufficient reconciliation scope %s\n' "$scope"
 done
 sql <<'SQL'
DELETE FROM organization_access.company_permissions WHERE "MembershipId"='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1' AND "Permission"='workshop.administrative-requests.reconcile';
SQL
 file /b11/900_synthetic_fixtures.sql
 printf "UPDATE organization_access.capability_activations SET \"Enabled\"=false WHERE \"Capability\"='external-administration';\n" | sql
 b11probe recovery_denied
 printf "UPDATE organization_access.capability_activations SET \"Enabled\"=true WHERE \"Capability\"='external-administration';\n" | sql
 b11probe recovery_negatives
 file /b11/950_rls_test.sql
 reset; b11probe restart_prepare
 # Preserve real audit records before Compose is allowed to replace this API container.
 compose logs --no-log-prefix api | python3 scripts/test-b11-audit.py --capture > "$state/b11-audit.jsonl"
 compose kill -s SIGKILL api
 restart_api
 b11probe restart_verify
 reset
 printf 'REVOKE INSERT ON workshop.administrative_outcomes FROM :"app_user";\n' | sql
 b11probe completion_prepare
 compose logs --no-log-prefix api | python3 scripts/test-b11-audit.py --capture >> "$state/b11-audit.jsonl"
 printf 'GRANT INSERT ON workshop.administrative_outcomes TO :"app_user";\n' | sql
 compose kill -s SIGKILL api
 restart_api
 b11probe completion_verify
 reset; b11probe recovery_prepare
 order_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["order"]["id"])' "$state/b10-history.json")
 docker run --rm --network "${project}_backend" -e VITE_B10_HTTP_BASE=http://web:8080 -e VITE_B10_SIMULATOR=http://admin-simulator:8080 -e VITE_B11_ORDER="$order_id" -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B11.runtime.test.tsx
 compose logs --no-log-prefix api | python3 scripts/test-b11-audit.py --capture >> "$state/b11-audit.jsonl"
 python3 scripts/test-b11-audit.py < "$state/b11-audit.jsonl"
 reset
 file /b11/990_rollback.sql
 file /b11/990_rollback.sql
 file /b11/080_continuity.sql
 file /b11/080_continuity.sql
 b11probe uncertain
 printf 'PASS B11 complete ephemeral continuity/reconciliation acceptance; cleanup checked by EXIT trap\n'
 exit
fi
if [ "${B10_BEHAVIOR:-all}" = b11 ] && [ "${B11_BEHAVIOR:-all}" = restart ]; then
 reset
 b11probe restart_prepare
 compose kill -s SIGKILL api
 restart_api
 b11probe restart_verify
 exit
fi
if [ "${B10_BEHAVIOR:-all}" = paused ]; then paused; exit; fi
if [ "${B10_BEHAVIOR:-all}" != all ]; then
 reset
 case "$B10_BEHAVIOR" in b11) docker run --rm --network "${project}_backend" -e B06_STATE_DIR=/evidence -v "$state:/evidence" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b11.py http://web:8080 "${B11_BEHAVIOR:-uncertain}" ;; ui) ui ;; race) for first in close install; do reset; python3 scripts/test-b10-closure-race.py "$project" "$state" "$first"; done ;; *) probe "$B10_BEHAVIOR" ;; esac
 exit
fi
probe smoke
for behavior in request complete reject closure_gate idempotency invalid references tenants; do reset; probe "$behavior"; done
for iteration in 1 2 3 4 5; do reset; probe closure_race; done
# Deterministic lock-queue interleavings of the real requests, each order twice.
for first in close install close install; do reset; python3 scripts/test-b10-closure-race.py "$project" "$state" "$first"; done
reset
ui
for scope in common-edit other-site warehouse-only wrong-action; do
 reset
 grants "$scope" none
 probe denied_scope
 restore_grants
 printf 'PASS B10 independent insufficient grant: %s\n' "$scope"
done
reset; grants exact workshop.administrative-requests.create; probe read_only; restore_grants
reset; grants exact workshop.administrative-requests.read; probe create_only; restore_grants
reset
sql <<'SQL'
UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"='external-administration' AND "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
probe capability_disabled
reset
sql <<'SQL'
DELETE FROM workshop.administrative_destinations WHERE "LegalEntityId"='11111111-1111-1111-1111-111111111101';
SQL
probe destination_missing
# D9: later company customizing applies only to later requests.
paused
reset
probe version_before
sql <<'SQL'
INSERT INTO workshop.administrative_destinations SELECT "TenantId","LegalEntityId",2,"Destination" FROM workshop.administrative_destinations WHERE "Version"=1;
SQL
probe version_after
file /b10/950_rls_test.sql
B04_POOL_SIZE=1 compose up -d --no-deps --wait --wait-timeout 120 api
for behavior in closure_gate complete; do reset; probe "$behavior"; done
file /b10/950_rls_test.sql
B04_POOL_SIZE=8 compose up -d --no-deps --wait --wait-timeout 120 api
compose ps -q | xargs docker inspect | python3 -c 'import json,sys
items=json.load(sys.stdin); assert len(items)==5
for item in items:
 c=item["HostConfig"]
 assert item["Config"]["User"] not in ("","0","root")
 assert c["ReadonlyRootfs"] and c["CapDrop"]==["ALL"] and "no-new-privileges:true" in c["SecurityOpt"]
 assert c["Memory"]>0 and c["NanoCpus"]>0 and c["PidsLimit"]>0
 assert c["LogConfig"]["Config"]["max-size"] and c["LogConfig"]["Config"]["max-file"]
 assert all(v is None for v in (item["NetworkSettings"]["Ports"] or {}).values())
 assert item["State"]["Health"]["Status"]=="healthy"
 assert not any(m["Type"]=="volume" for m in item["Mounts"])
print("PASS B10 five healthy hardened containers incl. simulator, no published ports or volumes")'
file /b12/990_rollback.sql
file /b11/990_rollback.sql
file /b11/990_rollback.sql
file /b10/990_rollback.sql
file /b10/990_rollback.sql
sql <<'SQL'
DO $$ BEGIN
 ASSERT to_regclass('workshop.technical_closures') IS NULL AND to_regclass('workshop.administrative_requests') IS NULL;
 ASSERT to_regclass('workshop.administrative_outbox') IS NULL AND to_regclass('workshop.administrative_destinations') IS NULL;
 ASSERT to_regnamespace('integrations') IS NULL;
 ASSERT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='enginia360_outbox_reader');
 ASSERT EXISTS (SELECT 1 FROM workshop.installations) AND EXISTS (SELECT 1 FROM inventory.carcass_returns);
 ASSERT (SELECT count(*) FROM organization_access.tenants)=2;
END $$;
SQL
# Previous B09 schema remains usable by the app role after B10 rollback.
sql <<'SQL'
BEGIN;
SET LOCAL ROLE :"app_user";
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
SELECT count(*) FROM inventory.carcass_returns;
SELECT count(*) FROM workshop.installations;
ROLLBACK;
SQL
file /b10/070_administration.sql
file /b11/080_continuity.sql
file /b12/090_billing.sql
file /b10/900_synthetic_fixtures.sql
file /b11/900_synthetic_fixtures.sql
reset
probe request
compose logs --no-log-prefix api | python3 scripts/test-b10-audit.py
printf 'PASS B10 isolated acceptance complete; cleanup verified by EXIT trap.\n'
