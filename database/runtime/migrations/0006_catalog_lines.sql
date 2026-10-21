-- Source: database/b05/020_catalog.sql (DDL/RLS/technical privileges only).
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

-- Source: database/b05/021_commercial_lines.sql (DDL/RLS/technical privileges only).
CREATE TABLE IF NOT EXISTS workshop.line_policies (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "DocumentTypeId" uuid NOT NULL,
 "Version" integer NOT NULL CHECK ("Version">0), "Policy" varchar(30) NOT NULL, "SameWorkingGroup" boolean NOT NULL,
 PRIMARY KEY ("TenantId","LegalEntityId","DocumentTypeId","Version")
);
CREATE UNIQUE INDEX IF NOT EXISTS orders_tenant_id ON workshop.orders ("TenantId","Id");
CREATE TABLE IF NOT EXISTS workshop.commercial_lines (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "CatalogItemId" uuid NOT NULL,
 "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0), "CatalogLabel" varchar(100) NOT NULL,
 "Kind" varchar(10) NOT NULL CHECK ("Kind" IN ('Service','Part')),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0), "UnitPrice" numeric(12,6) NOT NULL CHECK ("UnitPrice">=0),
 "DiscountPercent" numeric(5,2) NOT NULL CHECK ("DiscountPercent" BETWEEN 0 AND 100),
 "NetAmount" numeric(18,6) NOT NULL CHECK ("NetAmount">=0), "TaxRate" numeric(3,0) NOT NULL CHECK ("TaxRate"=22),
 "PayerId" uuid NOT NULL, "WorkingGroupId" uuid NOT NULL, "ConfigurationVersion" integer NOT NULL,
 "ExpectedRevision" integer NOT NULL CHECK ("ExpectedRevision">=0),
 UNIQUE ("TenantId","OrderId","Kind"),
 FOREIGN KEY ("TenantId","OrderId") REFERENCES workshop.orders ("TenantId","Id"),
 CHECK ("WorkingGroupId"="OrderId")
);
-- Repeatable widening for an existing private B05 schema; saved net snapshots are preserved.
ALTER TABLE workshop.commercial_lines
 ALTER COLUMN "Quantity" TYPE numeric(12,6),
 ALTER COLUMN "DiscountPercent" TYPE numeric(5,2),
 ALTER COLUMN "NetAmount" TYPE numeric(18,6);
ALTER TABLE workshop.commercial_lines DROP CONSTRAINT IF EXISTS "commercial_lines_UnitPrice_check";
ALTER TABLE workshop.commercial_lines ADD CONSTRAINT "commercial_lines_UnitPrice_check" CHECK ("UnitPrice">=0);
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.line_policies','workshop.commercial_lines'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT SELECT ON workshop.line_policies TO :"app_user";
GRANT SELECT, INSERT ON workshop.commercial_lines TO :"app_user";
