-- D80 / R04.c.1: append-only compensation; no physical or commercial mutation.
CREATE TABLE inventory.reservation_releases (
 "Id" uuid PRIMARY KEY CHECK ("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "ReservationId" uuid NOT NULL REFERENCES inventory.reservations("Id"),
 "OrderId" uuid NOT NULL, "LineId" uuid NOT NULL, "WorkingGroupId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL, "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL, "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "ReleasedAt" timestamptz NOT NULL, "OperatorId" uuid NOT NULL CHECK ("OperatorId"<>'00000000-0000-0000-0000-000000000000')
);
CREATE INDEX release_reservation ON inventory.reservation_releases("TenantId","ReservationId");
CREATE INDEX release_line ON inventory.reservation_releases("TenantId","LineId");
CREATE INDEX release_pool ON inventory.reservation_releases("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId");
ALTER TABLE inventory.reservation_releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.reservation_releases FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON inventory.reservation_releases USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE FUNCTION inventory.immutable_release() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'reservation_release_is_immutable'; END $$;
CREATE TRIGGER immutable_release BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.reservation_releases FOR EACH STATEMENT EXECUTE FUNCTION inventory.immutable_release();
REVOKE ALL ON FUNCTION inventory.immutable_release() FROM PUBLIC;
GRANT SELECT,INSERT ON inventory.reservation_releases TO :"app_user";
CREATE FUNCTION inventory.guard_release() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,inventory AS $$
DECLARE source inventory.reservations; released numeric;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW."OrderId"::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||NEW."TenantId"::text||':'||NEW."LineId"::text,0));
 SELECT * INTO source FROM inventory.reservations WHERE "TenantId"=NEW."TenantId" AND "Id"=NEW."ReservationId";
 IF source."Id" IS NULL OR (source."OrderId",source."LineId",source."WorkingGroupId",source."LegalEntityId",source."SiteId",source."WarehouseId",source."CatalogItemId",source."CatalogVersion")
   IS DISTINCT FROM (NEW."OrderId",NEW."LineId",NEW."WorkingGroupId",NEW."LegalEntityId",NEW."SiteId",NEW."WarehouseId",NEW."CatalogItemId",NEW."CatalogVersion") THEN RAISE EXCEPTION 'release_source_mismatch'; END IF;
 IF NOT EXISTS (SELECT 1 FROM workshop.reservation_line(NEW."TenantId",NEW."OrderId",NEW."LineId")) THEN RAISE EXCEPTION 'release_source_not_open'; END IF;
 PERFORM 1 FROM inventory.stock WHERE "TenantId"=NEW."TenantId" AND "LegalEntityId"=NEW."LegalEntityId" AND "SiteId"=NEW."SiteId" AND "WarehouseId"=NEW."WarehouseId" AND "CatalogItemId"=NEW."CatalogItemId" FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'release_stock_missing'; END IF;
 IF EXISTS (SELECT 1 FROM inventory.picks WHERE "TenantId"=NEW."TenantId" AND "ReservationId"=NEW."ReservationId") THEN RAISE EXCEPTION 'release_source_picked'; END IF;
 SELECT coalesce(sum("Quantity"),0) INTO released FROM inventory.reservation_releases WHERE "TenantId"=NEW."TenantId" AND "ReservationId"=NEW."ReservationId";
 IF NEW."Quantity">source."Quantity"-released THEN RAISE EXCEPTION 'release_exceeds_remaining'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER release_source BEFORE INSERT ON inventory.reservation_releases FOR EACH ROW EXECUTE FUNCTION inventory.guard_release();
REVOKE ALL ON FUNCTION inventory.guard_release() FROM PUBLIC;

-- OrganizationAccess-owned public SQL fence, on the caller connection. Narrow
-- boolean only; SECURITY DEFINER can lock grants without giving app UPDATE rights.
CREATE FUNCTION organization_access.inventory_release_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid, warehouse uuid, require_write boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true)
 OR identity_subject IS DISTINCT FROM current_setting('app.identity_subject',true) THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.memberships m WHERE m."TenantId"=tenant AND m."Id"=member AND m."IdentitySubject"=identity_subject FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p JOIN organization_access.warehouses w ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId" AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
 WHERE p."MembershipId"=member AND p."TenantId"=tenant AND p."LegalEntityId"=company AND p."SiteId"=site AND p."WarehouseId"=warehouse AND p."Permission"='inventory.reservations.release' FOR SHARE OF p,w;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p JOIN organization_access.sites s ON s."LegalEntityId"=p."LegalEntityId" AND s."TenantId"=p."TenantId"
 WHERE p."MembershipId"=member AND p."TenantId"=tenant AND p."LegalEntityId"=company AND s."Id"=site AND p."Permission"='workshop.orders.read' AND p."WarehouseId" IS NULL AND (p."SiteId" IS NULL OR p."SiteId"=site) FOR SHARE OF p,s;
 IF NOT FOUND THEN RETURN false; END IF;
 IF require_write THEN
  PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='inventory' AND "Enabled" FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;
  PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='workshop' AND "Enabled" FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;
 END IF;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) TO :"app_user";

-- Public Inventory-owned P2 fence: historical fully compensated reservations alone
-- are not active commitments. Picks/consumptions always retain provenance protection.
CREATE OR REPLACE FUNCTION inventory.line_has_commitments(tenant uuid, line uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$
 SELECT tenant::text=current_setting('app.tenant_id',true) AND (
 EXISTS (SELECT 1 FROM inventory.reservations r WHERE r."TenantId"=tenant AND r."LineId"=line
   AND r."Quantity">coalesce((SELECT sum(x."Quantity") FROM inventory.reservation_releases x WHERE x."TenantId"=tenant AND x."ReservationId"=r."Id"),0))
 OR EXISTS (SELECT 1 FROM inventory.picks p WHERE p."TenantId"=tenant AND p."LineId"=line)
 OR EXISTS (SELECT 1 FROM inventory.consumptions c JOIN inventory.reservations r ON r."Id"=c."ReservationId" AND r."TenantId"=c."TenantId" WHERE c."TenantId"=tenant AND r."LineId"=line));
$$;
