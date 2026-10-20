#!/bin/sh
# Synthetic ephemeral B13 acceptance; no published ports or retained volumes.
set -eu
B04_POOL_SIZE=12
export B04_POOL_SIZE
project="enginia360-b13-$$"
state="${TMPDIR:?use a scratch directory}/${project}"
mkdir -m 700 "$state"
env_file="$state/runtime.env"
compose(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml -f compose.b03-test.yaml -f compose.b04-test.yaml -f compose.b05-test.yaml -f compose.b06-test.yaml -f compose.b07-test.yaml -f compose.b08-test.yaml -f compose.b09-test.yaml -f compose.b10-test.yaml -f compose.b12-test.yaml -f compose.b13-test.yaml "$@"; }
cleanup(){
  rc=$?
  if [ "$rc" -ne 0 ]; then compose logs --no-log-prefix api | python3 -c 'import sys; print("".join(line for line in sys.stdin if any(term in line for term in ["Exception", "ERROR", "could not", "constraint", "permission denied"])))' > "${TMPDIR}/b13-api-fault.log"; fi
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -f "$env_file" "$state/runtime.json" "$state/rollback-refusal.log"
  rmdir "$state" 2>/dev/null || true
  test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
  test -z "$(docker network ls -q --filter "label=com.docker.compose.project=$project")"
}
trap cleanup EXIT INT TERM
umask 077
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 24)" > "$env_file"
compose up -d --build --wait --wait-timeout 240
compose exec -T postgres sh -c 'for f in /b03/00*.sql /b03/90*.sql /b04/010*.sql /b04/900*.sql /b05/020*.sql /b05/021*.sql /b05/900*.sql /b05/901*.sql /b06/030*.sql /b06/900*.sql /b07/040*.sql /b07/900*.sql /b08/050*.sql /b08/900*.sql /b09/060*.sql /b09/900*.sql /b10/070*.sql /b11/080*.sql /b10/900*.sql /b11/900*.sql /b12/090*.sql /b12/900*.sql /b13/100*.sql /b13/900*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f "$f" || exit; done'
docker run --rm --network "${project}_backend" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710 python3 scripts/test-b13.py http://web:8080 > "$state/runtime.json"
python3 scripts/test-b13-recovery.py "$project" "$state/runtime.json"
entry_id=$(python3 -c 'import json,sys; print([json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")][0]["entryId"])' "$state/runtime.json")
invoice_id=$(python3 -c 'import json,sys; print([json.loads(l) for l in open(sys.argv[1]) if l.startswith("{")][0]["invoiceId"])' "$state/runtime.json")
docker run --rm --network "${project}_backend" -e VITE_B13_HTTP_BASE=http://web:8080 -e VITE_B13_INVOICE="$invoice_id" -e VITE_B13_ENTRY="$entry_id" -v "$PWD/web:/source" -w /source node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test -- --run src/B13.runtime.test.tsx
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
 IF (SELECT count(*) FROM accounting.journal_entries) <> 1 THEN RAISE EXCEPTION '\''unexpected journal entry count'\''; END IF;
 IF (SELECT count(*) FROM accounting.journal_entry_lines) <> 4 THEN RAISE EXCEPTION '\''unexpected journal line count'\''; END IF;
 IF (SELECT count(*) FROM billing.invoice_journal_links) <> 1 THEN RAISE EXCEPTION '\''unexpected invoice link count'\''; END IF;
END \$\$;
SQL'
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f /b13/950_rls_test.sql'
compose logs --no-log-prefix api | python3 scripts/test-b13-audit.py
if compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /b13/990_rollback.sql' > "$state/rollback-refusal.log" 2>&1; then
  printf 'B13 rollback unexpectedly removed posted accounting evidence.\n' >&2; exit 1
fi
compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<SQL
TRUNCATE billing.invoice_journal_links,accounting.journal_entry_lines,accounting.journal_entries;
SQL
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /b13/990_rollback.sql
test "$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT to_regnamespace('\''accounting'\'') IS NULL")" = t
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER" -f /b13/100_accounting.sql'
printf 'PASS B13 isolated tracer; migration reapplied and cleanup verified by EXIT trap.\n'
