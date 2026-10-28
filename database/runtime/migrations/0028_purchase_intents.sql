-- R04.b.2a / D88, D90. Manual pending intent only; no external or stock writer.
-- Owning Counterparties public chooser: no provider identifiers exposed to the browser.
CREATE FUNCTION counterparties.purchase_suppliers(company uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties,organization_access AS $$
DECLARE result jsonb; authority jsonb; BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||current_setting('app.tenant_id',true),0));
 authority:=organization_access.read_master_authority(company);
 IF authority->>'state'='forbidden' THEN RETURN authority; END IF;
 IF authority->>'state'<>'local' THEN RETURN jsonb_build_object('state','master_'||(authority->>'state')); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('giobby-vendor:'||current_setting('app.tenant_id',true)||':'||company::text,0));
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',c."Id",'name',c."LegalName",
  'revision',coalesce((SELECT max(h."Revision") FROM counterparties.common_edit_history h WHERE h."CounterpartyId"=c."Id"),0),
  'mappingRevision',v."Revision") ORDER BY c."Id"),'[]'::jsonb) INTO result
 FROM counterparties.counterparties c JOIN LATERAL (
  SELECT "Revision" FROM counterparties.giobby_vendor_identity_history h WHERE h."CounterpartyId"=c."Id" AND h."LegalEntityId"=company ORDER BY "Revision" DESC LIMIT 1
 ) v ON true WHERE c."IsSupplier";
 RETURN jsonb_build_object('state','ready','suppliers',result);
END $$;
REVOKE ALL ON FUNCTION counterparties.purchase_suppliers(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.purchase_suppliers(uuid) TO :"app_user";

-- Owning-module contracts are evaluated on the caller's transaction, never a nested pool.
CREATE FUNCTION workshop.purchase_source(tenant uuid,ord uuid,line uuid) RETURNS jsonb
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,workshop AS $$
 SELECT jsonb_build_object('orderId',o."Id",'lineId',l."Id",'legalEntityId',o."LegalEntityId",'siteId',o."SiteId",
  'workingGroupId',l."WorkingGroupId",'catalogItemId',l."CatalogItemId",'catalogVersion',l."CatalogVersion",
  'isOpen',NOT EXISTS(SELECT 1 FROM workshop.technical_closures x WHERE x."OrderId"=o."Id" AND x."TenantId"=tenant),
  'revision',l."Version",'quantity',l."Quantity"::text,'description',coalesce(l."Description",l."CatalogLabel"),'kind',l."Kind",'state',l."State")
 FROM workshop.orders o JOIN workshop.commercial_lines l ON l."OrderId"=o."Id" AND l."TenantId"=o."TenantId"
 WHERE o."TenantId"=tenant AND o."Id"=ord AND l."Id"=line AND tenant::text=current_setting('app.tenant_id',true)
$$;
CREATE FUNCTION counterparties.purchase_supplier(company uuid,record uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties,organization_access AS $$
DECLARE choices jsonb; result jsonb; BEGIN
 choices:=counterparties.purchase_suppliers(company);
 IF choices->>'state'<>'ready' THEN RETURN choices; END IF;
 SELECT jsonb_build_object('id',c."Id",'name',c."LegalName",'isSupplier',c."IsSupplier",
  'revision',coalesce((SELECT max(h."Revision") FROM counterparties.common_edit_history h WHERE h."CounterpartyId"=c."Id"),0),
  'mappingRevision',v."Revision",'vendorId',v."VendorId",'vendorName',v."VendorName") INTO result
 FROM counterparties.counterparties c JOIN LATERAL (
  SELECT * FROM counterparties.giobby_vendor_identity_history h WHERE h."CounterpartyId"=c."Id" AND h."LegalEntityId"=company ORDER BY "Revision" DESC LIMIT 1
 ) v ON true WHERE c."Id"=record;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION workshop.purchase_source(uuid,uuid,uuid),counterparties.purchase_supplier(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.purchase_source(uuid,uuid,uuid) TO :"app_user";

CREATE TABLE inventory.purchase_intents (
 "Id" uuid PRIMARY KEY CHECK ("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,"SiteId" uuid NOT NULL,"WarehouseId" uuid NOT NULL,
 "OrderId" uuid NOT NULL,"LineId" uuid NOT NULL,"ActorMembershipId" uuid NOT NULL,
 "Quantity" numeric(12,6) NOT NULL CHECK ("Quantity">0),"Payload" jsonb NOT NULL,
 "Source" jsonb NOT NULL,"Supplier" jsonb NOT NULL,"Destination" jsonb NOT NULL,
 "CreatedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId"),
 UNIQUE("Id","TenantId","LegalEntityId")
);
CREATE INDEX purchase_intent_line ON inventory.purchase_intents("TenantId","LineId");
CREATE TABLE inventory.purchase_intent_outbox (
 "IntentId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "State" text NOT NULL CHECK ("State"='Held'),
 "Reason" text NOT NULL CHECK ("Reason"='purchase_connector_not_implemented'),
 FOREIGN KEY("IntentId","TenantId","LegalEntityId") REFERENCES inventory.purchase_intents("Id","TenantId","LegalEntityId")
);
ALTER TABLE inventory.purchase_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.purchase_intents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.purchase_intents
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
ALTER TABLE inventory.purchase_intent_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.purchase_intent_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.purchase_intent_outbox
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_purchase_intent BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.purchase_intents
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
CREATE TRIGGER immutable_purchase_outbox BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.purchase_intent_outbox
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON inventory.purchase_intents,inventory.purchase_intent_outbox FROM PUBLIC;

CREATE FUNCTION organization_access.purchase_intent_authorized(tenant uuid,member uuid,company uuid,site uuid,warehouse uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."Id"=member AND m."TenantId"=tenant AND m."IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member AND p."TenantId"=tenant AND p."LegalEntityId"=company AND p."Permission"='workshop.orders.read' AND p."WarehouseId" IS NULL AND (p."SiteId" IS NULL OR p."SiteId"=site) FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='workshop' AND "Enabled" FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p JOIN organization_access.warehouses w
 ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId" AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
 WHERE p."TenantId"=tenant AND p."MembershipId"=member AND p."LegalEntityId"=company AND p."SiteId"=site AND p."WarehouseId"=warehouse AND p."Permission"='inventory.purchase-intents.create' FOR SHARE OF p,w;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='inventory' AND "Enabled" FOR SHARE;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_intent_authorized(uuid,uuid,uuid,uuid,uuid) FROM PUBLIC;

-- One authoritative read under the same canonical locks as the writer. No vendor identifiers are projected.
CREATE FUNCTION inventory.purchase_intent_state(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE tenant uuid; member uuid; src jsonb; company uuid; site uuid; pending numeric; choices jsonb; BEGIN
 tenant:=current_setting('app.tenant_id',true)::uuid;
 SELECT "Id" INTO member FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true) AND "TenantId"=tenant;
 PERFORM pg_advisory_xact_lock(hashtextextended(ord::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||tenant::text||':'||line::text,0));
 src:=workshop.purchase_source(tenant,ord,line);
 IF src IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 company:=(src->>'legalEntityId')::uuid;site:=(src->>'siteId')::uuid;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 IF member IS NULL OR NOT organization_access.purchase_intent_authorized(tenant,member,company,site,warehouse) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 choices:=counterparties.purchase_suppliers(company);
 IF choices->>'state'<>'ready' THEN RETURN choices; END IF;
 SELECT coalesce(sum("Quantity"),0) INTO pending FROM inventory.purchase_intents WHERE "TenantId"=tenant AND "LineId"=line;
 RETURN jsonb_build_object('state','ready','source',src-'legalEntityId'-'siteId','pending',to_char(pending,'FM999999990.000000'),
  'remaining',to_char(greatest((src->>'quantity')::numeric-pending,0),'FM999999990.000000'),'suppliers',choices->'suppliers',
  'intents',coalesce((SELECT jsonb_agg(jsonb_build_object('id',i."Id",'quantity',to_char(i."Quantity",'FM999999990.000000'),'supplierId',i."Supplier"->>'id','supplierName',i."Supplier"->>'name','status',o."State") ORDER BY i."CreatedAt",i."Id")
   FROM inventory.purchase_intents i JOIN inventory.purchase_intent_outbox o ON o."IntentId"=i."Id" WHERE i."TenantId"=tenant AND i."LineId"=line),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) TO :"app_user";

-- D82: the company's immutable external stock source/profile must equal this purchase destination.
CREATE FUNCTION organization_access.purchase_destination_matches(tenant uuid,company uuid,site uuid,destination jsonb) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('stock-profile:'||tenant::text||':'||company::text,0));
 RETURN destination->>'kind'='GiobbyPurchaseV1' AND destination->>'tenantId'=tenant::text AND destination->>'legalEntityId'=company::text AND destination->>'siteId'=site::text AND destination->>'version'='1' AND destination->>'fingerprint' ~ '^[0-9a-f]{64}$' AND EXISTS(
 SELECT 1 FROM organization_access.company_stock_profiles p WHERE p."TenantId"=tenant AND p."LegalEntityId"=company AND p."Direction"='ExternalToEnginia360'
 AND p."SourceId"::text=destination->>'stockSourceId' AND p."ProfileId"::text=destination->>'stockProfileId');
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_destination_matches(uuid,uuid,uuid,jsonb) FROM PUBLIC;

CREATE FUNCTION inventory.create_purchase_intent(command uuid,ord uuid,line uuid,warehouse uuid,supplier uuid,
 revision integer,role_revision integer,mapping_revision integer,quantity_text text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE tenant uuid; member uuid; src jsonb; vendor jsonb; payload jsonb; company uuid; site uuid; previous inventory.purchase_intents; BEGIN
 IF quantity_text IS NULL OR length(quantity_text)>13 OR quantity_text !~ '^[0-9]{1,6}(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF quantity_text::numeric<=0 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 tenant:=current_setting('app.tenant_id',true)::uuid;
 SELECT "Id" INTO member FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true) AND "TenantId"=tenant;
 PERFORM pg_advisory_xact_lock(hashtextextended(command::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended(ord::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||tenant::text||':'||line::text,0));
 src:=workshop.purchase_source(tenant,ord,line);
 company:=(src->>'legalEntityId')::uuid;site:=(src->>'siteId')::uuid;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 IF NOT organization_access.purchase_intent_authorized(tenant,member,company,site,warehouse) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 payload:=jsonb_build_object('orderId',ord,'lineId',line,'warehouseId',warehouse,'supplierId',supplier,'sourceRevision',revision,'supplierRevision',role_revision,'mappingRevision',mapping_revision,'quantity',quantity_text);
 SELECT * INTO previous FROM inventory.purchase_intents WHERE "Id"=command;
 IF FOUND THEN
  IF previous."ActorMembershipId"=member AND previous."Payload"=payload THEN RETURN jsonb_build_object('state','replayed','id',command,'status','Held'); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF organization_access.purchase_destination_matches(tenant,company,site,destination) IS DISTINCT FROM true THEN RETURN jsonb_build_object('state','destination_unavailable'); END IF;
 IF src IS NULL OR src->>'kind'<>'Part' OR src->>'state'<>'Active' OR src->>'isOpen'<>'true' OR revision IS DISTINCT FROM (src->>'revision')::integer THEN RETURN jsonb_build_object('state','conflict'); END IF;
 vendor:=counterparties.purchase_supplier(company,supplier);
 IF vendor IS NULL OR vendor->>'isSupplier' IS DISTINCT FROM 'true' OR role_revision IS DISTINCT FROM (vendor->>'revision')::integer OR mapping_revision IS DISTINCT FROM (vendor->>'mappingRevision')::integer THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF quantity_text::numeric > (src->>'quantity')::numeric - coalesce((SELECT sum("Quantity") FROM inventory.purchase_intents WHERE "TenantId"=tenant AND "LineId"=line),0) THEN RETURN jsonb_build_object('state','exceeds_remaining'); END IF;
 INSERT INTO inventory.purchase_intents("Id","TenantId","LegalEntityId","SiteId","WarehouseId","OrderId","LineId","ActorMembershipId","Quantity","Payload","Source","Supplier","Destination")
 VALUES(command,tenant,company,site,warehouse,ord,line,member,quantity_text::numeric,payload,src,vendor,destination);
 INSERT INTO inventory.purchase_intent_outbox VALUES(command,tenant,company,'Held','purchase_connector_not_implemented');
 RETURN jsonb_build_object('state','applied','id',command,'status','Held');
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) TO :"app_user";
