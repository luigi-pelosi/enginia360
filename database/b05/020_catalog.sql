BEGIN;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE TABLE IF NOT EXISTS catalog.items (
    "Id" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL,
    "RegisteredCompanyId" uuid NOT NULL,
    "Kind" varchar(10) NOT NULL CHECK ("Kind" IN ('Service', 'Part')),
    "Label" varchar(100) NOT NULL CHECK (length(btrim("Label")) BETWEEN 1 AND 100),
    "Version" integer NOT NULL CHECK ("Version" > 0)
);
ALTER TABLE catalog.items ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.items FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON catalog.items;
CREATE POLICY tenant_identity ON catalog.items USING ("TenantId"::text = current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text = current_setting('app.tenant_id',true));
GRANT USAGE ON SCHEMA catalog TO :"app_user";
GRANT SELECT ON catalog.items TO :"app_user";
COMMIT;
