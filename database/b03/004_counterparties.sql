BEGIN;
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
COMMIT;
