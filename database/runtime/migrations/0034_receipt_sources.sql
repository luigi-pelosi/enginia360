-- D86 PR2 dedicated receiving discovery. Published 0001-0033 remain immutable.
CREATE FUNCTION inventory.receipt_sources(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE tenant uuid;src jsonb;company uuid;site uuid; BEGIN
 tenant:=nullif(current_setting('app.tenant_id',true),'')::uuid;
 PERFORM pg_advisory_xact_lock(hashtextextended(ord::text,0));
 src:=workshop.purchase_source(tenant,ord,line);
 IF src IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 company:=(src->>'legalEntityId')::uuid;site:=(src->>'siteId')::uuid;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 IF organization_access.receipt_member(tenant,company,site,warehouse,false) IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN jsonb_build_object('state','ready','sources',coalesce((
  SELECT jsonb_agg(jsonb_build_object('id',i."Id",'orderedQuantity',to_char(i."Quantity",'FM999990.000000'),
   'unitPurchasePrice',to_char(p."AcceptedUnitPurchasePrice",'FM999990.000000'),'externalOrderReference',o."ExternalReference",
   'supplierName',i."Supplier"->>'name','description',i."Source"->>'description') ORDER BY i."CreatedAt",i."Id")
  FROM inventory.purchase_intents i JOIN inventory.purchase_intent_prices p ON p."IntentId"=i."Id"
   JOIN inventory.purchase_intent_outcomes o ON o."IntentId"=i."Id"
  WHERE i."TenantId"=tenant AND i."LegalEntityId"=company AND i."OrderId"=ord AND i."LineId"=line AND i."SiteId"=site AND i."WarehouseId"=warehouse
   AND o."ExternalReference" ~ '^GiobbyPurchaseOrder-[1-9][0-9]*$'),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION inventory.receipt_sources(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.receipt_sources(uuid,uuid,uuid) TO :"app_user";
