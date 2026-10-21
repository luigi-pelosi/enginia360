-- Source: database/b04/010_workshop.sql (DDL/RLS/technical privileges only).
CREATE SCHEMA IF NOT EXISTS vehicles;
CREATE TABLE IF NOT EXISTS vehicles.vehicles (
    "Id" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL,
    "RegisteredCompanyId" uuid NOT NULL,
    "HolderId" uuid NOT NULL,
    "Label" varchar(100) NOT NULL CHECK (length(btrim("Label")) BETWEEN 1 AND 100),
    UNIQUE ("Id", "TenantId")
);
CREATE SCHEMA IF NOT EXISTS workshop;
CREATE TABLE IF NOT EXISTS workshop.document_types (
    "Id" uuid NOT NULL,
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "Version" integer NOT NULL CHECK ("Version" > 0),
    "Name" varchar(100) NOT NULL,
    "DirectCreationEnabled" boolean NOT NULL DEFAULT false,
    PRIMARY KEY ("TenantId", "LegalEntityId", "Id", "Version")
);
CREATE TABLE IF NOT EXISTS workshop.orders (
    "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "DocumentTypeId" uuid NOT NULL,
    "ConfigurationVersion" integer NOT NULL,
    "PayerId" uuid NOT NULL,
    "VehicleId" uuid NOT NULL,
    "VehicleHolderId" uuid NOT NULL,
    "CreatedByMembershipId" uuid NOT NULL,
    FOREIGN KEY ("TenantId", "LegalEntityId", "DocumentTypeId", "ConfigurationVersion")
        REFERENCES workshop.document_types ("TenantId", "LegalEntityId", "Id", "Version")
);
DO $$
DECLARE target text;
BEGIN
    FOREACH target IN ARRAY ARRAY['vehicles.vehicles', 'workshop.document_types', 'workshop.orders'] LOOP
        EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
        EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target);
        EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s', target);
        EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text = current_setting(''app.tenant_id'', true)) WITH CHECK ("TenantId"::text = current_setting(''app.tenant_id'', true))', target);
    END LOOP;
END $$;
GRANT USAGE ON SCHEMA vehicles, workshop TO :"app_user";
GRANT SELECT ON vehicles.vehicles, workshop.document_types TO :"app_user";
GRANT SELECT, INSERT ON workshop.orders TO :"app_user";
