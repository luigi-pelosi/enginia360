-- Source: database/b08/050_installation.sql (DDL/RLS/technical privileges only).
CREATE TABLE IF NOT EXISTS workshop.installations (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "PickId" uuid NOT NULL,
 "ReservationId" uuid NOT NULL,
 "OrderId" uuid NOT NULL REFERENCES workshop.orders("Id"),
 "WorkingGroupId" uuid NOT NULL,
 "LineId" uuid NOT NULL REFERENCES workshop.commercial_lines("Id"),
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL,
 "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "PickingConfigurationVersion" integer NOT NULL CHECK ("PickingConfigurationVersion">0),
 "DocumentTypeId" uuid NOT NULL,
 "ConfigurationVersion" integer NOT NULL CHECK ("ConfigurationVersion">0),
 "InstalledAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS installation_pick ON workshop.installations("TenantId","PickId");
CREATE TABLE IF NOT EXISTS inventory.consumptions (
 "InstallationId" uuid PRIMARY KEY CHECK ("InstallationId" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "PickId" uuid NOT NULL REFERENCES inventory.picks("Id"),
 "ReservationId" uuid NOT NULL REFERENCES inventory.reservations("Id"),
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL,
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "ConsumedAt" timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS consumption_stock ON inventory.consumptions("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId");
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.installations','inventory.consumptions'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT SELECT,INSERT ON workshop.installations,inventory.consumptions TO :"app_user";
GRANT UPDATE ("Physical") ON inventory.stock TO :"app_user";
