#!/bin/sh
set -eu
project="enginia360-b02-$PPID-$$"
env_file="${TMPDIR:-/tmp}/${project}.env"
cleanup(){ docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml down --volumes --remove-orphans >/dev/null 2>&1 || true; rm -f "$env_file"; }
trap cleanup EXIT INT TERM
umask 077
password="$(openssl rand -hex 24)"
printf 'B02_DB_NAME=enginia360\nB02_DB_USER=enginia360\nB02_DB_PASSWORD=%s\nB02_DB_APP_USER=enginia360_app\nB02_DB_APP_PASSWORD=%s\n' "$password" "$password" >"$env_file"
docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml up -d --build --wait --wait-timeout 240
network="${project}_backend"
docker run --rm --network "$network" -v "$PWD:/source:ro" -w /source python:3.14.0-alpine3.22 python3 scripts/test-b02.py http://web:8080
# Reapply the exact baseline and prove relational coherence rejects mixed identifiers.
docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/001_b02_organization_access.sql' >/dev/null
if docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "INSERT INTO organization_access.context_notes VALUES (gen_random_uuid(), '\''11111111-1111-1111-1111-111111111111'\'', '\''11111111-1111-1111-1111-111111111101'\'', '\''11111111-1111-1111-1111-111111110101'\'', '\''22222222-2222-2222-2222-222222220101'\'', '\''mixed'\'')"' >/dev/null 2>&1; then echo 'mixed context IDs were accepted' >&2; exit 1; fi
if docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "INSERT INTO organization_access.memberships VALUES ('\''aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2'\'', '\''22222222-2222-2222-2222-222222222222'\'', '\''aaaaaaaa-0000-0000-0000-000000000001'\'')"' >/dev/null 2>&1; then echo 'one identity subject was accepted in a second tenant' >&2; exit 1; fi
privileges="$(docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml exec -T postgres sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -v app_user="$B02_DB_APP_USER"' <<'SQL'
SELECT has_table_privilege(:'app_user', 'organization_access.memberships', 'SELECT')
    AND NOT has_table_privilege(:'app_user', 'organization_access.memberships', 'INSERT')
    AND has_table_privilege(:'app_user', 'organization_access.context_notes', 'SELECT')
    AND has_table_privilege(:'app_user', 'organization_access.context_notes', 'INSERT')
    AND NOT has_table_privilege(:'app_user', 'organization_access.context_notes', 'UPDATE')
    AND NOT has_table_privilege(:'app_user', 'organization_access.context_notes', 'DELETE');
SQL
)"
test "$privileges" = t
inspect="$(docker compose --env-file "$env_file" -p "$project" -f compose.b02-test.yaml ps -q | xargs docker inspect)"
printf '%s' "$inspect" | python3 -c 'import json, sys

items = json.load(sys.stdin)
assert len(items) == 4
for item in items:
    c = item["HostConfig"]
    assert item["Config"]["User"] not in ("", "0", "root")
    assert c["ReadonlyRootfs"] is True
    assert c["CapDrop"] == ["ALL"]
    assert "no-new-privileges:true" in c["SecurityOpt"]
    assert c["PidsLimit"] > 0
    assert c["Memory"] > 0
    assert c["NanoCpus"] > 0
    assert c["LogConfig"]["Type"] == "json-file"
    assert c["LogConfig"]["Config"].get("max-size") and c["LogConfig"]["Config"].get(
        "max-file"
    )
    assert not item["NetworkSettings"]["Ports"] or all(
        v is None for v in item["NetworkSettings"]["Ports"].values()
    )
    assert item["Image"].startswith("sha256:")
'
printf 'PASS: B02 compose integration, repeat baseline, cross-tenant identity rejection, coherence rejection, and hardening verified.\n'
