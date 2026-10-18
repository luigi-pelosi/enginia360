BEGIN;
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
COMMIT;
