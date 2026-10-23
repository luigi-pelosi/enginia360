-- R03.a.2 owning-module public SQL contracts. Invoker security preserves forced RLS.
-- Canonical serialization key (UUID lowercase D format): inventory:line:{tenant}:{line}.
-- No release/new-part return/compensation contract exists in the published runtime.
-- A carcass receipt does NOT compensate a reservation, pick or installation (D73).
CREATE FUNCTION inventory.line_has_commitments(tenant uuid, line uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path = pg_catalog, inventory AS $$
 SELECT tenant::text = current_setting('app.tenant_id',true) AND (
  EXISTS (SELECT 1 FROM inventory.reservations r WHERE r."TenantId"=tenant AND r."LineId"=line)
  OR EXISTS (SELECT 1 FROM inventory.picks p WHERE p."TenantId"=tenant AND p."LineId"=line)
  OR EXISTS (SELECT 1 FROM inventory.consumptions c JOIN inventory.reservations r ON r."Id"=c."ReservationId" AND r."TenantId"=c."TenantId" WHERE c."TenantId"=tenant AND r."LineId"=line)
 );
$$;
REVOKE ALL ON FUNCTION inventory.line_has_commitments(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.line_has_commitments(uuid,uuid) TO :"app_user";

CREATE FUNCTION workshop.reservation_line(tenant uuid, ord uuid, line uuid)
RETURNS TABLE ("OrderId" uuid,"LineId" uuid,"LegalEntityId" uuid,"SiteId" uuid,
 "CatalogItemId" uuid,"CatalogVersion" integer,"Kind" text,"Quantity" numeric,"WorkingGroupId" uuid)
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path = pg_catalog, workshop AS $$
 SELECT o."Id",l."Id",o."LegalEntityId",o."SiteId",l."CatalogItemId",l."CatalogVersion",l."Kind"::text,l."Quantity",l."WorkingGroupId"
 FROM workshop.orders o JOIN workshop.commercial_lines l ON l."OrderId"=o."Id" AND l."TenantId"=o."TenantId"
 WHERE tenant::text=current_setting('app.tenant_id',true) AND o."TenantId"=tenant AND o."Id"=ord AND l."Id"=line AND l."State"='Active'
 AND NOT EXISTS (SELECT 1 FROM workshop.technical_closures c WHERE c."TenantId"=tenant AND c."OrderId"=ord);
$$;
REVOKE ALL ON FUNCTION workshop.reservation_line(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.reservation_line(uuid,uuid,uuid) TO :"app_user";

CREATE OR REPLACE FUNCTION workshop.guard_line_update() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, workshop AS $$
BEGIN
 IF (NEW."Id",NEW."TenantId",NEW."OrderId",NEW."Kind",NEW."TaxRate",NEW."PayerId",NEW."ConfigurationVersion",NEW."ExpectedRevision")
 IS DISTINCT FROM (OLD."Id",OLD."TenantId",OLD."OrderId",OLD."Kind",OLD."TaxRate",OLD."PayerId",OLD."ConfigurationVersion",OLD."ExpectedRevision") THEN
  RAISE EXCEPTION 'saved line identity is immutable';
 END IF;
 IF NEW."Version" <> OLD."Version" + 1 THEN RAISE EXCEPTION 'every line change creates exactly one version'; END IF;
 IF OLD."State"='Removed' THEN RAISE EXCEPTION 'removal is a permanent tombstone'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(OLD."OrderId"::text,0));
 IF EXISTS (SELECT 1 FROM workshop.technical_closures c WHERE c."TenantId"=OLD."TenantId" AND c."OrderId"=OLD."OrderId") THEN
  RAISE EXCEPTION 'order_technically_closed';
 END IF;
 IF OLD."Kind"='Part' AND (NEW."Quantity",NEW."State",NEW."WorkingGroupId",NEW."CatalogItemId",NEW."CatalogVersion",NEW."CatalogLabel")
    IS DISTINCT FROM (OLD."Quantity",OLD."State",OLD."WorkingGroupId",OLD."CatalogItemId",OLD."CatalogVersion",OLD."CatalogLabel") THEN
  PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||OLD."TenantId"::text||':'||OLD."Id"::text,0));
  IF inventory.line_has_commitments(OLD."TenantId",OLD."Id") THEN RAISE EXCEPTION 'active_material_commitments'; END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION workshop.guard_line_update() FROM PUBLIC;
GRANT UPDATE ("CatalogItemId","CatalogVersion","CatalogLabel","WorkingGroupId") ON workshop.commercial_lines TO :"app_user";
