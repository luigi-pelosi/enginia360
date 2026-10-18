BEGIN;
-- Explicit tenant-common action, separate from company publication grants.
CREATE TABLE IF NOT EXISTS organization_access.common_edit_permissions (
 "MembershipId" uuid NOT NULL, "TenantId" uuid NOT NULL,
 PRIMARY KEY ("MembershipId", "TenantId"),
 FOREIGN KEY ("MembershipId", "TenantId") REFERENCES organization_access.memberships("Id", "TenantId")
);
ALTER TABLE organization_access.common_edit_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.common_edit_permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON organization_access.common_edit_permissions;
CREATE POLICY tenant_identity ON organization_access.common_edit_permissions USING ("TenantId"::text=current_setting('app.tenant_id',true));
GRANT SELECT ON organization_access.common_edit_permissions TO :"app_user";
GRANT UPDATE ("LegalName", "FiscalIdentifier", "RegisteredOffice") ON counterparties.counterparties TO :"app_user";
COMMIT;
