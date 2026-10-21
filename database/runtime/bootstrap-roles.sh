#!/bin/sh
# Infrastructure-only role bootstrap, never business setup. No secret argv/logs.
set -eu
: "${R00_OWNER_USER:?required}" "${R00_OWNER_PASSWORD:?required}"
: "${R00_APP_USER:?required}" "${R00_APP_PASSWORD:?required}"
python3 /runtime/validate-runtime-config.py
psql -X -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
\set ECHO none
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
\getenv owner_user R00_OWNER_USER
\getenv owner_password R00_OWNER_PASSWORD
\getenv app_user R00_APP_USER
\getenv app_password R00_APP_PASSWORD
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', :'owner_user', :'owner_password') \gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS', :'app_user', :'app_password') \gexec
CREATE ROLE enginia360_outbox_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
GRANT enginia360_outbox_reader TO :"owner_user" WITH INHERIT FALSE, SET TRUE;
SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'owner_user') \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
