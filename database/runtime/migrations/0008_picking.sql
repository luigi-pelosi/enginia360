-- Source: database/b07/040_picking.sql (DDL/RLS/technical privileges only).
-- Company-only customizing; locations are physical warehouse data, not site overrides.
CREATE TABLE IF NOT EXISTS inventory.picking_policies (
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "Version" integer NOT NULL CHECK ("Version" > 0),
    "PreparationEnabled" boolean NOT NULL,
    PRIMARY KEY ("TenantId", "LegalEntityId")
);
CREATE TABLE IF NOT EXISTS inventory.picking_locations (
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "OriginLocation" varchar(100) NOT NULL CHECK (length(trim("OriginLocation")) > 0),
    "PreparationLocation" varchar(100) CHECK (length(trim("PreparationLocation")) > 0),
    PRIMARY KEY ("TenantId", "LegalEntityId", "SiteId", "WarehouseId")
);
CREATE TABLE IF NOT EXISTS inventory.picks (
    "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
    "TenantId" uuid NOT NULL,
    "ReservationId" uuid NOT NULL REFERENCES inventory.reservations ("Id"),
    "OrderId" uuid NOT NULL,
    "WorkingGroupId" uuid NOT NULL,
    "LineId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "CatalogItemId" uuid NOT NULL,
    "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion" > 0),
    "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity" > 0),
    "ConfigurationVersion" integer NOT NULL CHECK ("ConfigurationVersion" > 0),
    "OriginLocation" varchar(100) NOT NULL,
    "PlacementLocation" varchar(100),
    "PickingListId" uuid NOT NULL,
    "PickedAt" timestamptz NOT NULL,
    "OperatorId" uuid NOT NULL
);
CREATE INDEX IF NOT EXISTS pick_reservation ON inventory.picks ("TenantId", "ReservationId");
DO $$ DECLARE target text; BEGIN
    FOREACH target IN ARRAY ARRAY['inventory.picking_policies','inventory.picking_locations','inventory.picks'] LOOP
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target);
        EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s', target);
        EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))', target);
    END LOOP;
END $$;
GRANT SELECT ON inventory.picking_policies, inventory.picking_locations TO :"app_user";
GRANT SELECT, INSERT ON inventory.picks TO :"app_user";
