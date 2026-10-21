-- Source: database/b03/006_destinations.sql (DDL/RLS/technical privileges only).
CREATE TABLE IF NOT EXISTS counterparties.destinations (
 "Id" uuid PRIMARY KEY, "TenantId" uuid NOT NULL, "CounterpartyId" uuid NOT NULL,
 "OwnerLegalEntityId" uuid NOT NULL, "Address" varchar(500) NOT NULL CHECK(length(btrim("Address")) BETWEEN 1 AND 500),
 "Published" boolean NOT NULL DEFAULT false,
 FOREIGN KEY ("CounterpartyId", "TenantId") REFERENCES counterparties.counterparties("Id", "TenantId")
);
ALTER TABLE counterparties.destinations ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.destinations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS destination_read ON counterparties.destinations;
CREATE POLICY destination_read ON counterparties.destinations FOR SELECT USING
 ("TenantId"::text=current_setting('app.tenant_id',true) AND ("OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true) OR "Published"));
DROP POLICY IF EXISTS destination_create ON counterparties.destinations;
CREATE POLICY destination_create ON counterparties.destinations FOR INSERT WITH CHECK
 ("TenantId"::text=current_setting('app.tenant_id',true) AND "OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true) AND NOT "Published");
GRANT SELECT, INSERT ON counterparties.destinations TO :"app_user";

-- Source: database/b03/007_publication.sql (DDL/RLS/technical privileges only).
DROP POLICY IF EXISTS destination_update ON counterparties.destinations;
CREATE POLICY destination_update ON counterparties.destinations FOR UPDATE USING
 ("TenantId"::text=current_setting('app.tenant_id',true) AND "OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true) AND "OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true));
GRANT UPDATE ("Published") ON counterparties.destinations TO :"app_user";

-- Source: database/b03/008_common_edit.sql (DDL/RLS/technical privileges only).
-- Explicit tenant-common action, separate from company publication grants.
CREATE TABLE IF NOT EXISTS organization_access.common_edit_permissions (
 "MembershipId" uuid NOT NULL, "TenantId" uuid NOT NULL,
 PRIMARY KEY ("MembershipId", "TenantId"),
 FOREIGN KEY ("MembershipId", "TenantId") REFERENCES organization_access.memberships("Id", "TenantId")
);
ALTER TABLE organization_access.common_edit_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.common_edit_permissions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON organization_access.common_edit_permissions;
CREATE POLICY tenant_identity ON organization_access.common_edit_permissions USING ("TenantId"::text=current_setting('app.tenant_id',true));
GRANT SELECT ON organization_access.common_edit_permissions TO :"app_user";
GRANT UPDATE ("LegalName", "FiscalIdentifier", "RegisteredOffice") ON counterparties.counterparties TO :"app_user";
