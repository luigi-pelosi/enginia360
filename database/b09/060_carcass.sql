BEGIN;
-- D30/D39/D14: company document-type customizing; which part requires a carcass return before technical closure.
CREATE TABLE IF NOT EXISTS workshop.carcass_policies (
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "DocumentTypeId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL,
 "Version" integer NOT NULL CHECK ("Version">0),
 "ReturnRequired" boolean NOT NULL,
 PRIMARY KEY ("TenantId","LegalEntityId","DocumentTypeId","CatalogItemId","Version")
);
-- D9 snapshot of the obligation at installation time. Defaults describe "no snapshotted obligation".
ALTER TABLE workshop.installations ADD COLUMN IF NOT EXISTS "CarcassPolicyVersion" integer CHECK ("CarcassPolicyVersion">0);
ALTER TABLE workshop.installations ADD COLUMN IF NOT EXISTS "CarcassReturnRequired" boolean NOT NULL DEFAULT false;
ALTER TABLE workshop.installations DROP CONSTRAINT IF EXISTS installation_carcass_snapshot;
ALTER TABLE workshop.installations ADD CONSTRAINT installation_carcass_snapshot
 CHECK (NOT "CarcassReturnRequired" OR "CarcassPolicyVersion" IS NOT NULL);
CREATE INDEX IF NOT EXISTS installation_order ON workshop.installations("TenantId","OrderId");
-- D38: dedicated replaced-part location per authorized warehouse; never part of stock or availability.
CREATE TABLE IF NOT EXISTS inventory.carcass_locations (
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL,
 "Version" integer NOT NULL CHECK ("Version">0),
 "Location" varchar(100) NOT NULL CHECK (length(btrim("Location"))>0),
 PRIMARY KEY ("TenantId","LegalEntityId","SiteId","WarehouseId","Version")
);
CREATE TABLE IF NOT EXISTS inventory.carcass_returns (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "OrderId" uuid NOT NULL,
 "WorkingGroupId" uuid NOT NULL,
 "LineId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL,
 "Location" varchar(100) NOT NULL,
 "LocationConfigurationVersion" integer NOT NULL CHECK ("LocationConfigurationVersion">0),
 "Description" varchar(200) NOT NULL CHECK (length("Description")>0 AND "Description"=btrim("Description")),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "ReceivedAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS carcass_return_line ON inventory.carcass_returns("TenantId","LineId");
CREATE INDEX IF NOT EXISTS carcass_return_order ON inventory.carcass_returns("TenantId","OrderId");
-- One row per covered installation: the primary key forbids covering an installation twice.
CREATE TABLE IF NOT EXISTS inventory.carcass_return_installations (
 "InstallationId" uuid PRIMARY KEY,
 "ReturnId" uuid NOT NULL REFERENCES inventory.carcass_returns("Id"),
 "TenantId" uuid NOT NULL,
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "CarcassPolicyVersion" integer NOT NULL CHECK ("CarcassPolicyVersion">0)
);
CREATE INDEX IF NOT EXISTS carcass_return_link ON inventory.carcass_return_installations("TenantId","ReturnId");
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.carcass_policies','inventory.carcass_locations','inventory.carcass_returns','inventory.carcass_return_installations'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT SELECT ON workshop.carcass_policies, inventory.carcass_locations TO :"app_user";
GRANT SELECT, INSERT ON inventory.carcass_returns, inventory.carcass_return_installations TO :"app_user";
COMMIT;
