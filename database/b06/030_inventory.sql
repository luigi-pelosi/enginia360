BEGIN;
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE TABLE IF NOT EXISTS inventory.stock (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL, "CatalogItemId" uuid NOT NULL,
 "Physical" numeric(12,6) NOT NULL CHECK ("Physical">=0),
 PRIMARY KEY ("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId")
);
CREATE TABLE IF NOT EXISTS inventory.reservations (
 "Id" uuid PRIMARY KEY CHECK ("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "LineId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL, "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL, "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0)
);
CREATE INDEX IF NOT EXISTS reservation_line ON inventory.reservations ("TenantId","LineId");
CREATE INDEX IF NOT EXISTS reservation_pool ON inventory.reservations ("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId");
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['inventory.stock','inventory.reservations'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT USAGE ON SCHEMA inventory TO :"app_user";
GRANT SELECT, UPDATE ("Physical") ON inventory.stock TO :"app_user";
-- PostgreSQL requires UPDATE privilege for SELECT FOR UPDATE; no stock-write API exists.
GRANT SELECT, INSERT ON inventory.reservations TO :"app_user";
COMMIT;
