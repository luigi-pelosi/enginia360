-- Source: database/001_b02_organization_access.sql (DDL/RLS/technical privileges only).
-- Organization structure only: no tenants, identities, grants or business configuration.
CREATE SCHEMA IF NOT EXISTS organization_access;

CREATE TABLE IF NOT EXISTS organization_access.tenants (
    "Id" uuid PRIMARY KEY,
    "Name" varchar(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS organization_access.legal_entities (
    "Id" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL REFERENCES organization_access.tenants ("Id") ON DELETE CASCADE,
    "Name" varchar(100) NOT NULL,
    UNIQUE ("Id", "TenantId")
);

CREATE TABLE IF NOT EXISTS organization_access.sites (
    "Id" uuid PRIMARY KEY,
    "LegalEntityId" uuid NOT NULL,
    "TenantId" uuid NOT NULL,
    "Name" varchar(100) NOT NULL,
    UNIQUE ("Id", "LegalEntityId", "TenantId"),
    FOREIGN KEY ("LegalEntityId", "TenantId") REFERENCES organization_access.legal_entities ("Id", "TenantId") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization_access.warehouses (
    "Id" uuid PRIMARY KEY,
    "SiteId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "TenantId" uuid NOT NULL,
    "Name" varchar(100) NOT NULL,
    UNIQUE ("Id", "SiteId", "LegalEntityId", "TenantId"),
    FOREIGN KEY ("SiteId", "LegalEntityId", "TenantId") REFERENCES organization_access.sites ("Id", "LegalEntityId", "TenantId") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization_access.memberships (
    "Id" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL REFERENCES organization_access.tenants ("Id") ON DELETE CASCADE,
    "IdentitySubject" varchar(200) NOT NULL,
    UNIQUE ("Id", "TenantId")
);

CREATE UNIQUE INDEX IF NOT EXISTS memberships_identity_subject_b02_unique ON organization_access.memberships ("IdentitySubject");

CREATE TABLE IF NOT EXISTS organization_access.membership_scopes (
    "Id" uuid PRIMARY KEY,
    "MembershipId" uuid NOT NULL,
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Permission" varchar(100) NOT NULL,
    UNIQUE ("MembershipId", "LegalEntityId", "SiteId", "WarehouseId", "Permission"),
    FOREIGN KEY ("MembershipId", "TenantId") REFERENCES organization_access.memberships ("Id", "TenantId") ON DELETE CASCADE,
    FOREIGN KEY ("WarehouseId", "SiteId", "LegalEntityId", "TenantId") REFERENCES organization_access.warehouses ("Id", "SiteId", "LegalEntityId", "TenantId") ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organization_access.capability_activations (
    "LegalEntityId" uuid NOT NULL REFERENCES organization_access.legal_entities ("Id") ON DELETE CASCADE,
    "Capability" varchar(100) NOT NULL,
    "Enabled" boolean NOT NULL,
    PRIMARY KEY ("LegalEntityId", "Capability")
);

CREATE TABLE IF NOT EXISTS organization_access.context_notes (
    "Id" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Message" varchar(200) NOT NULL CHECK (length(btrim("Message")) BETWEEN 1 AND 200),
    FOREIGN KEY ("WarehouseId", "SiteId", "LegalEntityId", "TenantId") REFERENCES organization_access.warehouses ("Id", "SiteId", "LegalEntityId", "TenantId") ON DELETE CASCADE
);















DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['tenants', 'legal_entities', 'sites', 'warehouses', 'memberships', 'membership_scopes', 'capability_activations', 'context_notes'] LOOP
        EXECUTE format('ALTER TABLE organization_access.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE organization_access.%I FORCE ROW LEVEL SECURITY', t);
    END LOOP;
END
$$;

DROP POLICY IF EXISTS identity_memberships ON organization_access.memberships;

CREATE POLICY identity_memberships ON organization_access.memberships
    USING ("IdentitySubject" = current_setting('app.identity_subject', TRUE));

DROP POLICY IF EXISTS tenant_identity ON organization_access.tenants;

CREATE POLICY tenant_identity ON organization_access.tenants
    USING ("Id"::text = current_setting('app.tenant_id', TRUE));

DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['legal_entities', 'sites', 'warehouses', 'membership_scopes', 'context_notes'] LOOP
        EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON organization_access.%I', t);
        EXECUTE format('CREATE POLICY tenant_identity ON organization_access.%I USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))', t);
    END LOOP;
END
$$;

DROP POLICY IF EXISTS legal_entity_identity ON organization_access.capability_activations;

CREATE POLICY legal_entity_identity ON organization_access.capability_activations
    USING (EXISTS (
        SELECT
            1
        FROM
            organization_access.legal_entities le
        WHERE
            le."Id" = "LegalEntityId" AND le."TenantId"::text = current_setting('app.tenant_id', TRUE)));







GRANT USAGE ON SCHEMA organization_access TO :"app_user";
GRANT SELECT ON organization_access.tenants, organization_access.legal_entities, organization_access.sites, organization_access.warehouses, organization_access.memberships, organization_access.membership_scopes, organization_access.capability_activations TO :"app_user";
GRANT SELECT, INSERT ON organization_access.context_notes TO :"app_user";
