-- D91/D92 source-bound purchasing quote. Published 0001-0029 remain unchanged.
CREATE FUNCTION organization_access.purchasing_identity() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE m organization_access.memberships; BEGIN
 SELECT a.* INTO m FROM organization_access.memberships a JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=a."IdentitySubject"
 WHERE a."IdentitySubject"=current_setting('app.identity_subject',true)
 AND (nullif(current_setting('app.tenant_id',true),'') IS NULL OR a."TenantId"::text=current_setting('app.tenant_id',true)) FOR SHARE OF a,b;
 IF NOT FOUND THEN RETURN NULL; END IF;
 PERFORM set_config('app.tenant_id',m."TenantId"::text,true);
 RETURN jsonb_build_object('tenantId',m."TenantId",'memberId',m."Id");
END $$;
REVOKE ALL ON FUNCTION organization_access.purchasing_identity() FROM PUBLIC;

-- An owning authority read under purchase grants, not the management/list-read surface.
CREATE FUNCTION organization_access.purchasing_authority(company uuid,site uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE identity jsonb; h organization_access.master_authority_history; BEGIN
 identity:=organization_access.purchasing_identity();
 IF identity IS NULL OR NOT organization_access.purchase_intent_authorized((identity->>'tenantId')::uuid,(identity->>'memberId')::uuid,company,site,warehouse) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||(identity->>'tenantId'),0));
 SELECT * INTO h FROM organization_access.master_authority_history WHERE "TenantId"=(identity->>'tenantId')::uuid ORDER BY "Version" DESC LIMIT 1;
 RETURN jsonb_build_object('state',CASE WHEN h."Version" IS NULL OR NOT company=ANY(h."CompanyIds") THEN 'master_missing' WHEN h."Direction"<>'Enginia360ToExternal' THEN 'master_external' ELSE 'ready' END,'authorityVersion',h."Version");
END $$;
REVOKE ALL ON FUNCTION organization_access.purchasing_authority(uuid,uuid,uuid) FROM PUBLIC;

CREATE FUNCTION counterparties.purchasing_supplier(company uuid,site uuid,warehouse uuid,record uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties AS $$
DECLARE authority jsonb; result jsonb; BEGIN
 authority:=organization_access.purchasing_authority(company,site,warehouse);
 IF authority->>'state'<>'ready' THEN RETURN authority; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('giobby-vendor:'||current_setting('app.tenant_id',true)||':'||company::text,0));
 SELECT jsonb_build_object('id',c."Id",'name',c."LegalName",'isSupplier',c."IsSupplier",'revision',coalesce((SELECT max(h."Revision") FROM counterparties.common_edit_history h WHERE h."CounterpartyId"=c."Id"),0),'mappingRevision',v."Revision",'vendorId',v."VendorId",'vendorName',v."VendorName") INTO result
 FROM counterparties.counterparties c JOIN LATERAL (SELECT * FROM counterparties.giobby_vendor_identity_history h WHERE h."CounterpartyId"=c."Id" AND h."LegalEntityId"=company ORDER BY "Revision" DESC LIMIT 1) v ON true
 WHERE c."Id"=record AND c."TenantId"::text=current_setting('app.tenant_id',true) AND c."IsSupplier" FOR SHARE OF c;
 IF result IS NULL THEN RETURN jsonb_build_object('state','conflict'); END IF;
 RETURN result||authority;
END $$;
REVOKE ALL ON FUNCTION counterparties.purchasing_supplier(uuid,uuid,uuid,uuid) FROM PUBLIC;

CREATE FUNCTION inventory.purchasing_source_context(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE identity jsonb; src jsonb; vendor jsonb; company uuid; site uuid; BEGIN
 identity:=organization_access.purchasing_identity();
 IF identity IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(ord::text,0));
 PERFORM pg_advisory_xact_lock(hashtextextended('inventory:line:'||(identity->>'tenantId')||':'||line::text,0));
 src:=workshop.purchase_source((identity->>'tenantId')::uuid,ord,line);
 IF src IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 company:=(src->>'legalEntityId')::uuid;site:=(src->>'siteId')::uuid;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 IF NOT organization_access.purchase_intent_authorized((identity->>'tenantId')::uuid,(identity->>'memberId')::uuid,company,site,warehouse) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN identity||jsonb_build_object('state','ready','source',src);
END $$;
REVOKE ALL ON FUNCTION inventory.purchasing_source_context(uuid,uuid,uuid) FROM PUBLIC;
CREATE FUNCTION inventory.purchasing_context(ord uuid,line uuid,warehouse uuid,supplier uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE context jsonb; src jsonb; vendor jsonb; company uuid; site uuid; BEGIN
 context:=inventory.purchasing_source_context(ord,line,warehouse);
 IF context->>'state'<>'ready' THEN RETURN context; END IF;
 src:=context->'source';company:=(src->>'legalEntityId')::uuid;site:=(src->>'siteId')::uuid;
 IF src->>'kind'<>'Part' OR src->>'state'<>'Active' OR src->>'isOpen'<>'true' THEN RETURN jsonb_build_object('state','conflict'); END IF;
 vendor:=counterparties.purchasing_supplier(company,site,warehouse,supplier);
 IF vendor->>'state'<>'ready' THEN RETURN vendor; END IF;
 RETURN context||jsonb_build_object('supplier',vendor-'state'-'authorityVersion','authorityVersion',vendor->'authorityVersion');
END $$;
REVOKE ALL ON FUNCTION inventory.purchasing_context(uuid,uuid,uuid,uuid) FROM PUBLIC;

CREATE FUNCTION catalog.purchasing_price(context jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE version_now integer; latest catalog.supplier_purchase_price_history; BEGIN
 SELECT i."Version" INTO version_now FROM catalog.items i WHERE i."Id"=(context->'source'->>'catalogItemId')::uuid AND i."TenantId"=(context->>'tenantId')::uuid FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','conflict'); END IF;
 SELECT * INTO latest FROM catalog.supplier_purchase_price_history WHERE "TenantId"=(context->>'tenantId')::uuid AND "LegalEntityId"=(context->'source'->>'legalEntityId')::uuid AND "SupplierId"=(context->'supplier'->>'id')::uuid AND "CatalogItemId"=(context->'source'->>'catalogItemId')::uuid ORDER BY "Revision" DESC LIMIT 1;
 RETURN jsonb_build_object('state','ready','revision',coalesce(latest."Revision",0),'catalogVersion',version_now,'authorityVersion',context->'authorityVersion','sourcePresent',latest."Revision" IS NOT NULL,'unitPurchasePrice',CASE WHEN latest."Revision" IS NOT NULL THEN to_char(latest."UnitPurchasePrice",'FM999990.000000') ELSE NULL END,'provenance',CASE WHEN latest."Revision" IS NOT NULL THEN to_jsonb(latest)-'Payload' ELSE NULL END);
END $$;
REVOKE ALL ON FUNCTION catalog.purchasing_price(jsonb) FROM PUBLIC;
CREATE FUNCTION catalog.purchase_intent_quote(ord uuid,line uuid,warehouse uuid,supplier uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE context jsonb; price jsonb; BEGIN
 context:=inventory.purchasing_context(ord,line,warehouse,supplier);
 IF context->>'state'<>'ready' THEN RETURN jsonb_build_object('state',context->>'state'); END IF;
 price:=catalog.purchasing_price(context);
 IF price->>'state'<>'ready' THEN RETURN price; END IF;
 RETURN jsonb_build_object('state','ready','quote',price-'state'-'provenance');
END $$;
REVOKE ALL ON FUNCTION catalog.purchase_intent_quote(uuid,uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.purchase_intent_quote(uuid,uuid,uuid,uuid) TO :"app_user";

CREATE TABLE inventory.purchase_intent_prices (
 "IntentId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "AcceptedUnitPurchasePrice" numeric(12,6) NOT NULL CHECK ("AcceptedUnitPurchasePrice">=0),
 "PriceSource" jsonb NOT NULL,"Method" text NOT NULL CHECK ("Method" IN ('manual','listed')),
 "ActorMembershipId" uuid NOT NULL,"AcceptedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 "Version" integer NOT NULL DEFAULT 1 CHECK ("Version"=1),
 FOREIGN KEY("IntentId","TenantId","LegalEntityId") REFERENCES inventory.purchase_intents("Id","TenantId","LegalEntityId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE inventory.purchase_intent_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.purchase_intent_prices FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.purchase_intent_prices
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_purchase_intent_price BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.purchase_intent_prices FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON inventory.purchase_intent_prices FROM PUBLIC;

CREATE FUNCTION inventory.accept_purchase_intent(command uuid,ord uuid,line uuid,warehouse uuid,supplier uuid,
 revision integer,role_revision integer,mapping_revision integer,quantity_text text,quote_revision integer,catalog_version integer,authority_version integer,manual_price text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE context jsonb; price jsonb; tenant uuid; member uuid; company uuid; site uuid; payload jsonb; previous inventory.purchase_intents; BEGIN
 IF command IS NULL OR command='00000000-0000-0000-0000-000000000000' OR quantity_text IS NULL OR length(quantity_text)>13 OR quantity_text !~ '^[0-9]{1,6}(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF quantity_text::numeric<=0 OR (manual_price IS NOT NULL AND (length(manual_price)>13 OR manual_price !~ '^[0-9]{1,6}(\.[0-9]{1,6})?$')) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command::text,0));
 context:=inventory.purchasing_source_context(ord,line,warehouse);
 IF context->>'state'<>'ready' THEN RETURN jsonb_build_object('state',context->>'state'); END IF;
 tenant:=(context->>'tenantId')::uuid;member:=(context->>'memberId')::uuid;
 company:=(context->'source'->>'legalEntityId')::uuid;site:=(context->'source'->>'siteId')::uuid;
 payload:=jsonb_build_object('orderId',ord,'lineId',line,'warehouseId',warehouse,'supplierId',supplier,'sourceRevision',revision,'supplierRevision',role_revision,'mappingRevision',mapping_revision,'quantity',quantity_text,'quoteRevision',quote_revision,'catalogVersion',catalog_version,'authorityVersion',authority_version,'manualUnitPurchasePrice',manual_price);
 SELECT * INTO previous FROM inventory.purchase_intents WHERE "Id"=command;
 IF FOUND THEN
  IF previous."ActorMembershipId"=member AND previous."Payload"=payload AND EXISTS(SELECT 1 FROM inventory.purchase_intent_prices WHERE "IntentId"=command) THEN RETURN jsonb_build_object('state','replayed','id',command,'status','Held'); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 context:=inventory.purchasing_context(ord,line,warehouse,supplier);
 IF context->>'state'<>'ready' THEN RETURN jsonb_build_object('state',context->>'state'); END IF;
 price:=catalog.purchasing_price(context);
 IF price->>'state'<>'ready' THEN RETURN price; END IF;
 IF revision IS DISTINCT FROM (context->'source'->>'revision')::integer OR role_revision IS DISTINCT FROM (context->'supplier'->>'revision')::integer OR mapping_revision IS DISTINCT FROM (context->'supplier'->>'mappingRevision')::integer OR quote_revision IS DISTINCT FROM (price->>'revision')::integer OR catalog_version IS DISTINCT FROM (price->>'catalogVersion')::integer OR authority_version IS DISTINCT FROM (price->>'authorityVersion')::integer THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF (price->>'sourcePresent'='false' AND manual_price IS NULL) OR (price->>'sourcePresent'='true' AND manual_price IS NOT NULL) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF organization_access.purchase_destination_matches(tenant,company,site,destination) IS DISTINCT FROM true THEN RETURN jsonb_build_object('state','destination_unavailable'); END IF;
 IF quantity_text::numeric > (context->'source'->>'quantity')::numeric - coalesce((SELECT sum("Quantity") FROM inventory.purchase_intents WHERE "TenantId"=tenant AND "LineId"=line),0) THEN RETURN jsonb_build_object('state','exceeds_remaining'); END IF;
 INSERT INTO inventory.purchase_intents("Id","TenantId","LegalEntityId","SiteId","WarehouseId","OrderId","LineId","ActorMembershipId","Quantity","Payload","Source","Supplier","Destination") VALUES(command,tenant,company,site,warehouse,ord,line,member,quantity_text::numeric,payload,context->'source',context->'supplier',destination);
 INSERT INTO inventory.purchase_intent_prices("IntentId","TenantId","LegalEntityId","AcceptedUnitPurchasePrice","PriceSource","Method","ActorMembershipId") VALUES(command,tenant,company,CASE WHEN price->>'sourcePresent'='true' THEN (price->>'unitPurchasePrice')::numeric ELSE manual_price::numeric END,price-'state',CASE WHEN price->>'sourcePresent'='true' THEN 'listed' ELSE 'manual' END,member);
 INSERT INTO inventory.purchase_intent_outbox VALUES(command,tenant,company,'Held','purchase_connector_not_implemented');
 RETURN jsonb_build_object('state','applied','id',command,'status','Held');
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) TO :"app_user";

-- Preserve the published pending-budget projection; add only immutable accepted-price facts.
CREATE OR REPLACE FUNCTION inventory.purchase_intent_state(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
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
  'intents',coalesce((SELECT jsonb_agg(jsonb_build_object('id',i."Id",'quantity',to_char(i."Quantity",'FM999999990.000000'),'supplierId',i."Supplier"->>'id','supplierName',i."Supplier"->>'name','status',o."State",'acceptedPrice',CASE WHEN p."IntentId" IS NULL THEN NULL ELSE jsonb_build_object('unitPurchasePrice',to_char(p."AcceptedUnitPurchasePrice",'FM999990.000000'),'sourcePresent',(p."PriceSource"->>'sourcePresent')::boolean,'revision',p."PriceSource"->'revision','method',p."Method",'actorMembershipId',p."ActorMembershipId",'acceptedAt',p."AcceptedAt",'version',p."Version") END) ORDER BY i."CreatedAt",i."Id")
   FROM inventory.purchase_intents i JOIN inventory.purchase_intent_outbox o ON o."IntentId"=i."Id" LEFT JOIN inventory.purchase_intent_prices p ON p."IntentId"=i."Id" WHERE i."TenantId"=tenant AND i."LineId"=line),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) TO :"app_user";
