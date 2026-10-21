-- Source: database/b03/004_counterparties.sql (DDL/RLS/technical privileges only).
CREATE SCHEMA IF NOT EXISTS counterparties;
CREATE TABLE IF NOT EXISTS counterparties.counterparties (
 "Id" uuid PRIMARY KEY, "TenantId" uuid NOT NULL,
 "LegalName" varchar(200) NOT NULL CHECK(length(btrim("LegalName")) BETWEEN 1 AND 200),
 "FiscalIdentifier" varchar(100) NOT NULL CHECK(length(btrim("FiscalIdentifier")) BETWEEN 1 AND 100),
 "RegisteredOffice" varchar(500) NOT NULL CHECK(length(btrim("RegisteredOffice")) BETWEEN 1 AND 500),
 UNIQUE("Id", "TenantId")
);
ALTER TABLE counterparties.counterparties ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.counterparties FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON counterparties.counterparties;
CREATE POLICY tenant_identity ON counterparties.counterparties USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));

-- Source: database/b03/005_grants.sql (DDL/RLS/technical privileges only).
GRANT SELECT ON organization_access.company_permissions TO :"app_user";
GRANT USAGE ON SCHEMA counterparties TO :"app_user";
GRANT SELECT ON counterparties.counterparties TO :"app_user";
