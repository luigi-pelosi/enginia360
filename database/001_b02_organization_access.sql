-- B02 organization access baseline. Synthetic data only.
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

INSERT INTO organization_access.tenants
VALUES
    ('11111111-1111-1111-1111-111111111111', 'Tenant Alfa sintetico'),
    ('22222222-2222-2222-2222-222222222222', 'Tenant Beta sintetico')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.legal_entities
VALUES
    ('11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111111', 'Alfa Società Uno'),
    ('11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111111111', 'Alfa Società Due'),
    ('22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222222222', 'Beta Società Uno')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.sites
VALUES
    ('11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111111', 'Alfa Sede Nord'),
    ('11111111-1111-1111-1111-111111110201', '11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111111111', 'Alfa Due Sede'),
    ('22222222-2222-2222-2222-222222220101', '22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222222222', 'Beta Sede')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.warehouses
VALUES
    ('11111111-1111-1111-1111-111111100101', '11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111111', 'Alfa Nord Magazzino A'),
    ('11111111-1111-1111-1111-111111100301', '11111111-1111-1111-1111-111111110201', '11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111111111', 'Alfa Due Magazzino'),
    ('22222222-2222-2222-2222-222222220101', '22222222-2222-2222-2222-222222220101', '22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222222222', 'Beta Magazzino')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.memberships
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-0000-0000-0000-000000000001'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1', '22222222-2222-2222-2222-222222222222', 'bbbbbbbb-0000-0000-0000-000000000001')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.membership_scopes
VALUES
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa101', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111100101', 'organization-context.read'),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa102', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111100101', 'organization-context.write'),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa103', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111110201', '11111111-1111-1111-1111-111111100301', 'organization-context.read'),
    ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa104', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111110201', '11111111-1111-1111-1111-111111100301', 'organization-context.write'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbb101', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1', '22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222220101', '22222222-2222-2222-2222-222222220101', 'organization-context.read'),
    ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbb102', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1', '22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222220101', '22222222-2222-2222-2222-222222220101', 'organization-context.write')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.capability_activations
VALUES
    ('11111111-1111-1111-1111-111111111101', 'organization-context', TRUE),
    ('11111111-1111-1111-1111-111111111102', 'organization-context', FALSE),
    ('22222222-2222-2222-2222-222222222201', 'organization-context', TRUE)
ON CONFLICT
    DO NOTHING;

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

INSERT INTO organization_access.memberships
    VALUES ('dddddddd-dddd-dddd-dddd-ddddddddddd1', '11111111-1111-1111-1111-111111111111', 'dddddddd-0000-0000-0000-000000000001')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.warehouses
    VALUES ('11111111-1111-1111-1111-111111100102', '11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111111111', 'Alfa Nord Magazzino senza scope')
ON CONFLICT
    DO NOTHING;

INSERT INTO organization_access.context_notes
VALUES
    ('11111111-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111102', '11111111-1111-1111-1111-111111110201', '11111111-1111-1111-1111-111111100301', 'Nota storica sintetica'),
    ('11111111-0000-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111101', '11111111-1111-1111-1111-111111110101', '11111111-1111-1111-1111-111111100102', 'Nota fuori scope sintetica')
ON CONFLICT
    DO NOTHING;
