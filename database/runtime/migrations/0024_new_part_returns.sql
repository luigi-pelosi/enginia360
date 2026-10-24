-- D81 / R04.c.2 Inventory-owned append-only new intact never-installed part returns.
CREATE TABLE inventory.new_part_returns (
 "Id" uuid PRIMARY KEY CHECK ("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "ReservationId" uuid NOT NULL REFERENCES inventory.reservations("Id"),
 "PickId" uuid NOT NULL REFERENCES inventory.picks("Id"), "MembershipId" uuid NOT NULL,
 "OrderId" uuid NOT NULL, "LineId" uuid NOT NULL, "WorkingGroupId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL, "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL, "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0),
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),
 "ReturnedAt" timestamptz NOT NULL, "OperatorId" uuid NOT NULL CHECK ("OperatorId"<>'00000000-0000-0000-0000-000000000000')
);
CREATE INDEX new_return_pick ON inventory.new_part_returns("TenantId","PickId");
CREATE INDEX new_return_line ON inventory.new_part_returns("TenantId","LineId");
CREATE INDEX new_return_pool ON inventory.new_part_returns("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId");
ALTER TABLE inventory.new_part_returns ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.new_part_returns FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON inventory.new_part_returns USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE FUNCTION inventory.immutable_new_return() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'new_part_return_is_immutable'; END $$;
CREATE TRIGGER immutable_new_return BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.new_part_returns FOR EACH STATEMENT EXECUTE FUNCTION inventory.immutable_new_return();
REVOKE ALL ON FUNCTION inventory.immutable_new_return() FROM PUBLIC;
GRANT SELECT,INSERT ON inventory.new_part_returns TO :"app_user";
-- OrganizationAccess-owned public SQL fence, on the caller connection. Narrow
-- boolean only; SECURITY DEFINER can lock grants without giving app UPDATE rights.
CREATE FUNCTION organization_access.inventory_new_return_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid, warehouse uuid, require_write boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true)
 OR identity_subject IS DISTINCT FROM current_setting('app.identity_subject',true) THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.memberships m WHERE m."TenantId"=tenant AND m."Id"=member AND m."IdentitySubject"=identity_subject FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p JOIN organization_access.warehouses w ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId" AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
 WHERE p."MembershipId"=member AND p."TenantId"=tenant AND p."LegalEntityId"=company AND p."SiteId"=site AND p."WarehouseId"=warehouse AND p."Permission"='inventory.new-part-returns.create' FOR SHARE OF p,w;
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
REVOKE ALL ON FUNCTION organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) TO :"app_user";


-- Inventory-owned quantity contract. Call after canonical order/line serialization for writes.
CREATE FUNCTION inventory.pick_returned(tenant uuid, pick uuid) RETURNS numeric
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$
 SELECT coalesce(sum("Quantity"),0) FROM inventory.new_part_returns
 WHERE tenant::text=current_setting('app.tenant_id',true) AND "TenantId"=tenant AND "PickId"=pick;
$$;
REVOKE ALL ON FUNCTION inventory.pick_returned(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.pick_returned(uuid,uuid) TO :"app_user";

-- Workshop-owned public fact contract includes Pending: absence of Inventory consumption is irrelevant.
CREATE FUNCTION workshop.pick_has_installations(tenant uuid, pick uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,workshop AS $$
 SELECT tenant::text=current_setting('app.tenant_id',true) AND EXISTS
 (SELECT 1 FROM workshop.installations WHERE "TenantId"=tenant AND "PickId"=pick);
$$;
REVOKE ALL ON FUNCTION workshop.pick_has_installations(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.pick_has_installations(uuid,uuid) TO :"app_user";

-- Historical picks remain immutable; only fully compensated facts cease to fence structure.
CREATE OR REPLACE FUNCTION inventory.line_has_commitments(tenant uuid, line uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$
 SELECT tenant::text=current_setting('app.tenant_id',true) AND (
 EXISTS (SELECT 1 FROM inventory.reservations r WHERE r."TenantId"=tenant AND r."LineId"=line
   AND r."Quantity">coalesce((SELECT sum(x."Quantity") FROM inventory.reservation_releases x WHERE x."TenantId"=tenant AND x."ReservationId"=r."Id"),0)
      +coalesce((SELECT sum(x."Quantity") FROM inventory.new_part_returns x WHERE x."TenantId"=tenant AND x."ReservationId"=r."Id"),0))
 OR EXISTS (SELECT 1 FROM inventory.picks p WHERE p."TenantId"=tenant AND p."LineId"=line AND p."Quantity">inventory.pick_returned(tenant,p."Id"))
 OR EXISTS (SELECT 1 FROM inventory.consumptions c JOIN inventory.reservations r ON r."Id"=c."ReservationId" AND r."TenantId"=c."TenantId" WHERE c."TenantId"=tenant AND r."LineId"=line));
$$;

CREATE FUNCTION inventory.guard_new_return_source() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,inventory AS $$
DECLARE source inventory.picks;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW."OrderId"::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||NEW."TenantId"::text||':'||NEW."LineId"::text,0));
 SELECT * INTO source FROM inventory.picks WHERE "TenantId"=NEW."TenantId" AND "Id"=NEW."PickId";
 IF source."Id" IS NULL OR (source."ReservationId",source."OrderId",source."LineId",source."WorkingGroupId",source."LegalEntityId",source."SiteId",source."WarehouseId",source."CatalogItemId",source."CatalogVersion")
 IS DISTINCT FROM (NEW."ReservationId",NEW."OrderId",NEW."LineId",NEW."WorkingGroupId",NEW."LegalEntityId",NEW."SiteId",NEW."WarehouseId",NEW."CatalogItemId",NEW."CatalogVersion") THEN RAISE EXCEPTION 'new_return_source_mismatch'; END IF;
 IF NEW."OperatorId"::text IS DISTINCT FROM current_setting('app.identity_subject',true)
 OR NOT organization_access.inventory_new_return_authorized(NEW."TenantId",NEW."MembershipId",NEW."OperatorId"::text,NEW."LegalEntityId",NEW."SiteId",NEW."WarehouseId",true)
 THEN RAISE EXCEPTION 'new_return_actor_unauthorized'; END IF;
 IF NOT EXISTS (SELECT 1 FROM workshop.reservation_line(NEW."TenantId",NEW."OrderId",NEW."LineId")) THEN RAISE EXCEPTION 'new_return_not_open'; END IF;
 IF organization_access.company_stock_profile(NEW."TenantId",NEW."LegalEntityId")<>'local' THEN RAISE EXCEPTION 'new_return_stock_authority'; END IF;
 PERFORM 1 FROM inventory.stock WHERE "TenantId"=NEW."TenantId" AND "LegalEntityId"=NEW."LegalEntityId" AND "SiteId"=NEW."SiteId" AND "WarehouseId"=NEW."WarehouseId" AND "CatalogItemId"=NEW."CatalogItemId" FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'new_return_stock_missing'; END IF;
 IF workshop.pick_has_installations(NEW."TenantId",NEW."PickId") THEN RAISE EXCEPTION 'new_return_pick_has_installations'; END IF;
 IF NEW."Quantity">source."Quantity"-inventory.pick_returned(NEW."TenantId",NEW."PickId") THEN RAISE EXCEPTION 'new_return_exceeds_remaining'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER new_return_source BEFORE INSERT ON inventory.new_part_returns FOR EACH ROW EXECUTE FUNCTION inventory.guard_new_return_source();
REVOKE ALL ON FUNCTION inventory.guard_new_return_source() FROM PUBLIC;

CREATE FUNCTION inventory.pick_installation_capacity(tenant uuid, pick uuid) RETURNS numeric
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$
 SELECT "Quantity"-inventory.pick_returned(tenant,pick) FROM inventory.picks
 WHERE tenant::text=current_setting('app.tenant_id',true) AND "TenantId"=tenant AND "Id"=pick;
$$;
REVOKE ALL ON FUNCTION inventory.pick_installation_capacity(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.pick_installation_capacity(uuid,uuid) TO :"app_user";
CREATE FUNCTION workshop.guard_installation_return_allowance() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,workshop AS $$
DECLARE capacity numeric; installed numeric;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW."OrderId"::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||NEW."TenantId"::text||':'||NEW."LineId"::text,0));
 capacity:=inventory.pick_installation_capacity(NEW."TenantId",NEW."PickId");
 SELECT coalesce(sum("Quantity"),0) INTO installed FROM workshop.installations WHERE "TenantId"=NEW."TenantId" AND "PickId"=NEW."PickId" AND "Id"<>NEW."Id";
 IF capacity IS NULL OR NEW."Quantity">capacity-installed THEN RAISE EXCEPTION 'installation_exceeds_unreturned'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER installation_return_allowance BEFORE INSERT ON workshop.installations FOR EACH ROW EXECUTE FUNCTION workshop.guard_installation_return_allowance();
REVOKE ALL ON FUNCTION workshop.guard_installation_return_allowance() FROM PUBLIC;

CREATE FUNCTION workshop.pick_installed_quantity(tenant uuid, pick uuid) RETURNS numeric
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,workshop AS $$
 SELECT coalesce(sum("Quantity"),0) FROM workshop.installations
 WHERE tenant::text=current_setting('app.tenant_id',true) AND "TenantId"=tenant AND "PickId"=pick;
$$;
REVOKE ALL ON FUNCTION workshop.pick_installed_quantity(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.pick_installed_quantity(uuid,uuid) TO :"app_user";
