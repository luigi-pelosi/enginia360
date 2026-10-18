BEGIN;
CREATE TABLE IF NOT EXISTS organization_access.company_permissions (
 "Id" uuid PRIMARY KEY, "MembershipId" uuid NOT NULL, "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL, "Permission" varchar(100) NOT NULL,
 "SiteId" uuid NULL, "WarehouseId" uuid NULL,
 FOREIGN KEY ("MembershipId", "TenantId") REFERENCES organization_access.memberships("Id", "TenantId"),
 FOREIGN KEY ("LegalEntityId", "TenantId") REFERENCES organization_access.legal_entities("Id", "TenantId")
);
ALTER TABLE organization_access.company_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.company_permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON organization_access.company_permissions;
CREATE POLICY tenant_identity ON organization_access.company_permissions USING ("TenantId"::text=current_setting('app.tenant_id',true));
COMMIT;
