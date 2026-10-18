BEGIN;
DROP POLICY IF EXISTS destination_update ON counterparties.destinations;
CREATE POLICY destination_update ON counterparties.destinations FOR UPDATE USING
 ("TenantId"::text=current_setting('app.tenant_id',true) AND "OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true) AND "OwnerLegalEntityId"::text=current_setting('app.legal_entity_id',true));
GRANT UPDATE ("Published") ON counterparties.destinations TO :"app_user";
COMMIT;
