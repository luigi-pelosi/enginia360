-- R04.b.2b.3 PR2 purchase dispatch readout. Appended only: 0001-0031 are unchanged. Same authorization, tenant/company context and ACL as 0030;
-- the only change is the per-intent confirmation reference from the Inventory-owned insert-only outcome (no timestamp, id or vendor value).
-- Delivery state stays in Integrations and is read through Inventory.Contracts, never from this schema.
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
  'intents',coalesce((SELECT jsonb_agg(jsonb_build_object('id',i."Id",'quantity',to_char(i."Quantity",'FM999999990.000000'),'supplierId',i."Supplier"->>'id','supplierName',i."Supplier"->>'name','status',o."State",'outcome',CASE WHEN oc."IntentId" IS NULL THEN NULL ELSE jsonb_build_object('externalReference',oc."ExternalReference") END,'acceptedPrice',CASE WHEN p."IntentId" IS NULL THEN NULL ELSE jsonb_build_object('unitPurchasePrice',to_char(p."AcceptedUnitPurchasePrice",'FM999990.000000'),'sourcePresent',(p."PriceSource"->>'sourcePresent')::boolean,'revision',p."PriceSource"->'revision','method',p."Method",'actorMembershipId',p."ActorMembershipId",'acceptedAt',p."AcceptedAt",'version',p."Version") END) ORDER BY i."CreatedAt",i."Id")
   FROM inventory.purchase_intents i JOIN inventory.purchase_intent_outbox o ON o."IntentId"=i."Id" LEFT JOIN inventory.purchase_intent_prices p ON p."IntentId"=i."Id" LEFT JOIN inventory.purchase_intent_outcomes oc ON oc."IntentId"=i."Id" WHERE i."TenantId"=tenant AND i."LineId"=line),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) TO :"app_user";
