#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_user="$B02_DB_APP_USER" <<'SQL'
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user') \gexec
SELECT format('GRANT USAGE ON SCHEMA organization_access TO %I', :'app_user') \gexec
SELECT format('GRANT SELECT ON organization_access.tenants, organization_access.legal_entities, organization_access.sites, organization_access.warehouses, organization_access.memberships, organization_access.membership_scopes, organization_access.capability_activations TO %I', :'app_user') \gexec
SELECT format('GRANT SELECT, INSERT ON organization_access.context_notes TO %I', :'app_user') \gexec
SQL
