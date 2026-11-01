-- D93 dedicated receipt permission. Owner/trusted offline only; D77 mandate is not extended.
CREATE TABLE organization_access.receipt_grant_history (
 "CommandId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,"SiteId" uuid NOT NULL,"WarehouseId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,"TargetMembershipId" uuid NOT NULL,"VerificationReference" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK("Revision">0),"Operation" text NOT NULL CHECK("Operation" IN ('grant','revoke')),
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","LegalEntityId","SiteId","WarehouseId","TargetMembershipId","Revision"),
 FOREIGN KEY("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId"),
 FOREIGN KEY("TargetMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE organization_access.receipt_grant_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.receipt_grant_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON organization_access.receipt_grant_history
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_receipt_grant BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.receipt_grant_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON organization_access.receipt_grant_history FROM PUBLIC;
CREATE FUNCTION organization_access.set_receipt_grant(command uuid,tenant uuid,company uuid,site uuid,warehouse uuid,actor uuid,target uuid,verification uuid,expected integer,operation text) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE revision_now integer; previous organization_access.receipt_grant_history; BEGIN
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501'; END IF;
 IF tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true) OR company::text IS DISTINCT FROM current_setting('app.legal_entity_id',true) OR actor IS NULL OR target IS NULL OR actor=target THEN RETURN 'forbidden'; END IF;
 IF command IS NULL OR command='00000000-0000-0000-0000-000000000000' OR verification IS NULL OR verification='00000000-0000-0000-0000-000000000000' OR expected IS NULL OR expected<0 OR operation IS NULL OR operation NOT IN ('grant','revoke') THEN RETURN 'invalid'; END IF;
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=actor AND m."TenantId"=tenant FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN 'forbidden'; END IF;
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=target AND m."TenantId"=tenant FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN 'forbidden'; END IF;
 PERFORM 1 FROM organization_access.warehouses WHERE "Id"=warehouse AND "SiteId"=site AND "LegalEntityId"=company AND "TenantId"=tenant FOR SHARE;
 IF NOT FOUND THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command::text,33));
 PERFORM pg_advisory_xact_lock(hashtextextended('receipt-grant:'||tenant::text||':'||company::text||':'||warehouse::text||':'||target::text,0));
 SELECT * INTO previous FROM organization_access.receipt_grant_history WHERE "CommandId"=command;
 IF FOUND THEN RETURN CASE WHEN previous."TenantId"=tenant AND previous."LegalEntityId"=company AND previous."SiteId"=site AND previous."WarehouseId"=warehouse AND previous."ActorMembershipId"=actor AND previous."TargetMembershipId"=target AND previous."VerificationReference"=verification AND previous."Operation"=operation AND previous."Revision"::bigint=expected::bigint+1 THEN 'replayed' ELSE 'conflict' END; END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM organization_access.receipt_grant_history WHERE "TenantId"=tenant AND "LegalEntityId"=company AND "SiteId"=site AND "WarehouseId"=warehouse AND "TargetMembershipId"=target;
 IF expected IS DISTINCT FROM revision_now OR expected=2147483647 THEN RETURN 'conflict'; END IF;
 IF operation='grant' THEN
  IF NOT EXISTS(SELECT 1 FROM organization_access.company_permissions WHERE "TenantId"=tenant AND "MembershipId"=target AND "LegalEntityId"=company AND "Permission"='inventory.receipts.create' AND "SiteId"=site AND "WarehouseId"=warehouse) THEN
   INSERT INTO organization_access.company_permissions VALUES(gen_random_uuid(),target,tenant,company,'inventory.receipts.create',site,warehouse);
  END IF;
 ELSE
  DELETE FROM organization_access.company_permissions WHERE "TenantId"=tenant AND "MembershipId"=target AND "LegalEntityId"=company AND "Permission"='inventory.receipts.create' AND "SiteId"=site AND "WarehouseId"=warehouse;
 END IF;
 INSERT INTO organization_access.receipt_grant_history("CommandId","TenantId","LegalEntityId","SiteId","WarehouseId","ActorMembershipId","TargetMembershipId","VerificationReference","Revision","Operation") VALUES(command,tenant,company,site,warehouse,actor,target,verification,expected+1,operation);
 RETURN 'applied';
EXCEPTION WHEN unique_violation THEN RETURN 'conflict';
END $$;
REVOKE ALL ON FUNCTION organization_access.set_receipt_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,integer,text) FROM PUBLIC;

-- Envelope-only context resolution; source facts remain FORCE-RLS and are read only after dedicated authorization.
GRANT CREATE ON SCHEMA inventory TO enginia360_outbox_reader;
CREATE FUNCTION inventory.receipt_source_company(source_intent uuid) RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT "LegalEntityId" FROM inventory.purchase_intents WHERE "Id"=source_intent AND "TenantId"::text=current_setting('app.tenant_id',true)
$$;
REVOKE ALL ON FUNCTION inventory.receipt_source_company(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.receipt_source_company(uuid) TO CURRENT_USER;
ALTER FUNCTION inventory.receipt_source_company(uuid) OWNER TO enginia360_outbox_reader;
SET LOCAL ROLE enginia360_outbox_reader;
DO $$ BEGIN EXECUTE format('GRANT EXECUTE ON FUNCTION inventory.receipt_source_company(uuid) TO %I',(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())); END $$;
RESET ROLE;
REVOKE CREATE ON SCHEMA inventory FROM enginia360_outbox_reader;

CREATE FUNCTION organization_access.receipt_member(tenant uuid,company uuid,site uuid,warehouse uuid,writable boolean) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE member uuid; BEGIN
 SELECT m."Id" INTO member FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."TenantId"=tenant AND m."IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE OF m,b;
 IF member IS NULL THEN RETURN NULL; END IF;
 PERFORM 1 FROM organization_access.company_permissions WHERE "TenantId"=tenant AND "MembershipId"=member AND "LegalEntityId"=company AND "Permission"='workshop.orders.read' AND "WarehouseId" IS NULL AND ("SiteId" IS NULL OR "SiteId"=site) FOR SHARE;
 IF NOT FOUND THEN RETURN NULL; END IF;
 PERFORM 1 FROM organization_access.company_permissions p JOIN organization_access.warehouses w
 ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId" AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
 WHERE p."TenantId"=tenant AND p."MembershipId"=member AND p."LegalEntityId"=company AND p."SiteId"=site AND p."WarehouseId"=warehouse AND p."Permission"='inventory.receipts.create' FOR SHARE OF p,w;
 IF NOT FOUND THEN RETURN NULL; END IF;
 IF writable THEN
  PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='inventory' AND "Enabled" FOR SHARE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='external-administration' AND "Enabled" FOR SHARE;
  IF NOT FOUND THEN RETURN NULL; END IF;
 END IF;
 RETURN member;
END $$;
REVOKE ALL ON FUNCTION organization_access.receipt_member(uuid,uuid,uuid,uuid,boolean) FROM PUBLIC;

CREATE TABLE inventory.receipt_intents (
 "Id" uuid PRIMARY KEY CHECK("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,"SiteId" uuid NOT NULL,"WarehouseId" uuid NOT NULL,
 "SourceIntentId" uuid NOT NULL,"ActorMembershipId" uuid NOT NULL,"Quantity" numeric(12,6) NOT NULL CHECK("Quantity">0),
 "Payload" jsonb NOT NULL,"Snapshot" jsonb NOT NULL,"Destination" jsonb NOT NULL,"CreatedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("Id","TenantId","LegalEntityId"),
 FOREIGN KEY("SourceIntentId","TenantId","LegalEntityId") REFERENCES inventory.purchase_intents("Id","TenantId","LegalEntityId"),
 FOREIGN KEY("SourceIntentId") REFERENCES inventory.purchase_intent_outcomes("IntentId"),
 FOREIGN KEY("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
CREATE INDEX receipt_source_budget ON inventory.receipt_intents("TenantId","SourceIntentId");
CREATE TABLE inventory.receipt_outbox (
 "ReceiptId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 FOREIGN KEY("ReceiptId","TenantId","LegalEntityId") REFERENCES inventory.receipt_intents("Id","TenantId","LegalEntityId")
);
ALTER TABLE inventory.receipt_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.receipt_intents FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.receipt_intents
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
ALTER TABLE inventory.receipt_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.receipt_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.receipt_outbox
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_receipt_intent BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.receipt_intents FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
CREATE TRIGGER immutable_receipt_outbox BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.receipt_outbox FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON inventory.receipt_intents,inventory.receipt_outbox FROM PUBLIC;

CREATE FUNCTION inventory.create_receipt_intent(command uuid,source_intent uuid,quantity_text text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE tenant uuid;company uuid;member uuid;src inventory.purchase_intents;price inventory.purchase_intent_prices;reference text;snapshot jsonb;previous inventory.receipt_intents;payload jsonb; BEGIN
 IF command IS NULL OR command='00000000-0000-0000-0000-000000000000' OR source_intent IS NULL OR quantity_text IS NULL OR length(quantity_text)>13 OR quantity_text !~ '^[0-9]{1,6}(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF quantity_text::numeric<=0 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 tenant:=nullif(current_setting('app.tenant_id',true),'')::uuid;
 company:=inventory.receipt_source_company(source_intent);
 PERFORM set_config('app.legal_entity_id',company::text,true);
 SELECT * INTO src FROM inventory.purchase_intents WHERE "Id"=source_intent AND "TenantId"=tenant;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 member:=organization_access.receipt_member(tenant,company,src."SiteId",src."WarehouseId",true);
 IF member IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command::text,34));
 PERFORM pg_advisory_xact_lock(hashtextextended('receipt-source:'||tenant::text||':'||source_intent::text,0));
 payload:=jsonb_build_object('sourceIntentId',source_intent,'quantity',quantity_text);
 SELECT * INTO previous FROM inventory.receipt_intents WHERE "Id"=command;
 IF FOUND THEN
  IF previous."ActorMembershipId"=member AND previous."Payload"=payload THEN RETURN jsonb_build_object('state','replayed','id',command,'snapshot',previous."Snapshot"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 SELECT "ExternalReference" INTO reference FROM inventory.purchase_intent_outcomes WHERE "IntentId"=source_intent;
 SELECT * INTO price FROM inventory.purchase_intent_prices WHERE "IntentId"=source_intent;
 IF reference IS NULL OR reference !~ '^GiobbyPurchaseOrder-[1-9][0-9]*$' OR price."IntentId" IS NULL THEN RETURN jsonb_build_object('state','source_unconfirmed'); END IF;
 IF destination->>'kind' IS DISTINCT FROM 'GiobbyReceiptV1' OR organization_access.purchase_destination_matches(tenant,company,src."SiteId",jsonb_set(destination,'{kind}','"GiobbyPurchaseV1"')) IS DISTINCT FROM true THEN RETURN jsonb_build_object('state','destination_unavailable'); END IF;
 IF quantity_text::numeric>src."Quantity"-coalesce((SELECT sum("Quantity") FROM inventory.receipt_intents WHERE "TenantId"=tenant AND "SourceIntentId"=source_intent),0) THEN RETURN jsonb_build_object('state','exceeds_remaining'); END IF;
 snapshot:=jsonb_build_object('source',src."Source",'supplier',src."Supplier",'orderedQuantity',to_char(src."Quantity",'FM999990.000000'),'quantity',to_char(quantity_text::numeric,'FM999990.000000'),'unitPrice',to_char(price."AcceptedUnitPurchasePrice",'FM999990.000000'),'priceProvenance',to_jsonb(price),'externalOrderReference',reference);
 INSERT INTO inventory.receipt_intents("Id","TenantId","LegalEntityId","SiteId","WarehouseId","SourceIntentId","ActorMembershipId","Quantity","Payload","Snapshot","Destination")
 VALUES(command,tenant,company,src."SiteId",src."WarehouseId",source_intent,member,quantity_text::numeric,jsonb_build_object('sourceIntentId',source_intent,'quantity',quantity_text),snapshot,destination);
 INSERT INTO inventory.receipt_outbox VALUES(command,tenant,company);
 RETURN jsonb_build_object('state','applied','id',command,'snapshot',snapshot);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION inventory.create_receipt_intent(uuid,uuid,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.create_receipt_intent(uuid,uuid,text,jsonb) TO :"app_user";

-- Business confirmation is immutable; every receipt intent continues to count against D94 forever.
CREATE TABLE inventory.receipt_outcomes (
 "ReceiptId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "ExternalReference" varchar(64) NOT NULL CHECK("ExternalReference" ~ '^GiobbyReceipt-[1-9][0-9]*$'),
 "RecordedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY("ReceiptId","TenantId","LegalEntityId") REFERENCES inventory.receipt_intents("Id","TenantId","LegalEntityId"),
 UNIQUE("TenantId","LegalEntityId","ExternalReference")
);
ALTER TABLE inventory.receipt_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.receipt_outcomes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.receipt_outcomes
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_receipt_outcome BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.receipt_outcomes FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON inventory.receipt_outcomes FROM PUBLIC;
CREATE FUNCTION inventory.record_receipt_outcome(tenant uuid,company uuid,receipt uuid,reference text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE previous text; BEGIN
 IF tenant IS NULL OR company IS NULL OR current_setting('app.tenant_id',true) IS DISTINCT FROM tenant::text THEN RETURN 'forbidden'; END IF;
 IF reference IS NULL OR length(reference)>64 OR reference !~ '^GiobbyReceipt-[1-9][0-9]*$' THEN RETURN 'invalid'; END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 PERFORM pg_advisory_xact_lock(hashtextextended('receipt-outcome:'||tenant::text||':'||receipt::text,0));
 IF NOT EXISTS(SELECT 1 FROM inventory.receipt_intents WHERE "Id"=receipt AND "TenantId"=tenant AND "LegalEntityId"=company) THEN RETURN 'not_found'; END IF;
 SELECT "ExternalReference" INTO previous FROM inventory.receipt_outcomes WHERE "ReceiptId"=receipt;
 IF FOUND THEN RETURN CASE WHEN previous=reference THEN 'replayed' ELSE 'conflict' END; END IF;
 INSERT INTO inventory.receipt_outcomes("ReceiptId","TenantId","LegalEntityId","ExternalReference") VALUES(receipt,tenant,company,reference);
 RETURN 'recorded';
EXCEPTION WHEN unique_violation THEN RETURN 'conflict';
END $$;
REVOKE ALL ON FUNCTION inventory.record_receipt_outcome(uuid,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.record_receipt_outcome(uuid,uuid,uuid,text) TO :"app_user";

CREATE FUNCTION inventory.receipt_state(source_intent uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE tenant uuid;company uuid;src inventory.purchase_intents;result jsonb; BEGIN
 tenant:=nullif(current_setting('app.tenant_id',true),'')::uuid;
 company:=inventory.receipt_source_company(source_intent);
 PERFORM set_config('app.legal_entity_id',company::text,true);
 SELECT * INTO src FROM inventory.purchase_intents WHERE "Id"=source_intent AND "TenantId"=tenant;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 IF organization_access.receipt_member(tenant,company,src."SiteId",src."WarehouseId",false) IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('receipt-source:'||tenant::text||':'||source_intent::text,0));
 IF NOT EXISTS(SELECT 1 FROM inventory.purchase_intent_outcomes WHERE "IntentId"=source_intent) THEN RETURN jsonb_build_object('state','source_unconfirmed'); END IF;
 SELECT jsonb_build_object('state','ready','sourceIntentId',source_intent,'nonAuthoritative',true,'erpPerOrderResidual',NULL,
  'precisionDiscrepancy','receipt_q6_stock_report_q5_observed','linkKind','internal_standalone_not_erp_native',
  'orderedQuantity',to_char(src."Quantity",'FM999990.000000'),
  'acceptedQuantity',to_char(coalesce(sum(r."Quantity") FILTER(WHERE o."ReceiptId" IS NOT NULL),0),'FM999990.000000'),
  'uncertainQuantity',to_char(coalesce(sum(r."Quantity") FILTER(WHERE o."ReceiptId" IS NULL),0),'FM999990.000000'),
  'remainingQuantity',to_char(src."Quantity"-coalesce(sum(r."Quantity"),0),'FM999990.000000'),
  'receipts',coalesce(jsonb_agg(jsonb_build_object('id',r."Id",'snapshot',r."Snapshot",'createdAt',r."CreatedAt",'status',CASE WHEN o."ReceiptId" IS NULL THEN 'PendingUnconfirmed' ELSE 'Confirmed' END,'externalReference',o."ExternalReference") ORDER BY r."CreatedAt",r."Id") FILTER(WHERE r."Id" IS NOT NULL),'[]'::jsonb)) INTO result
 FROM inventory.receipt_intents r LEFT JOIN inventory.receipt_outcomes o ON o."ReceiptId"=r."Id"
 WHERE r."SourceIntentId"=source_intent AND r."TenantId"=tenant;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION inventory.receipt_state(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.receipt_state(uuid) TO :"app_user";

GRANT CREATE ON SCHEMA inventory TO enginia360_outbox_reader;
GRANT SELECT("Id","TenantId","LegalEntityId","CreatedAt") ON inventory.receipt_intents TO enginia360_outbox_reader;
GRANT SELECT("ReceiptId") ON inventory.receipt_outcomes TO enginia360_outbox_reader;
CREATE FUNCTION inventory.pending_receipt_dispatch(max_items integer,scan_offset integer) RETURNS TABLE("TenantId" uuid,"LegalEntityId" uuid,"ReceiptId" uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT r."TenantId",r."LegalEntityId",r."Id" FROM inventory.receipt_intents r
 WHERE NOT EXISTS(SELECT 1 FROM inventory.receipt_outcomes o WHERE o."ReceiptId"=r."Id")
 ORDER BY r."CreatedAt",r."Id" LIMIT least(greatest(max_items,1),100) OFFSET greatest(scan_offset,0)
$$;
REVOKE ALL ON FUNCTION inventory.pending_receipt_dispatch(integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.pending_receipt_dispatch(integer,integer) TO :"app_user";
ALTER FUNCTION inventory.pending_receipt_dispatch(integer,integer) OWNER TO enginia360_outbox_reader;
REVOKE CREATE ON SCHEMA inventory FROM enginia360_outbox_reader;
CREATE FUNCTION inventory.read_receipt_dispatch(tenant uuid,company uuid,receipt uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE result jsonb; BEGIN
 IF tenant IS NULL OR company IS NULL OR current_setting('app.tenant_id',true) IS DISTINCT FROM tenant::text THEN RETURN NULL; END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 SELECT jsonb_build_object('tenantId',r."TenantId",'legalEntityId',r."LegalEntityId",'siteId',r."SiteId",'receiptId',r."Id",
  'catalogItemId',r."Snapshot"->'source'->>'catalogItemId','description',r."Snapshot"->'source'->>'description',
  'quantity',r."Snapshot"->>'quantity','unitPrice',r."Snapshot"->>'unitPrice','vendorId',r."Snapshot"->'supplier'->>'vendorId',
  'vendorName',r."Snapshot"->'supplier'->>'vendorName','fingerprint',r."Destination"->>'fingerprint') INTO result
 FROM inventory.receipt_intents r WHERE r."Id"=receipt AND r."TenantId"=tenant AND r."LegalEntityId"=company;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION inventory.read_receipt_dispatch(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.read_receipt_dispatch(uuid,uuid,uuid) TO :"app_user";

CREATE TABLE integrations.receipt_dispatches (
 "ReceiptId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "State" varchar(20) NOT NULL CHECK("State" IN ('Queued','Uncertain','Completed')),
 "Attempts" integer NOT NULL CHECK("Attempts">=0),"Failures" integer NOT NULL DEFAULT 0 CHECK("Failures">=0),
 "KnownDocumentId" integer CHECK("KnownDocumentId">0),"LastAttemptAt" timestamptz,"NextAttemptAt" timestamptz NOT NULL,"LeaseUntil" timestamptz,
 "ExternalReference" varchar(64),"LastError" varchar(64),"UpdatedAt" timestamptz NOT NULL
);
ALTER TABLE integrations.receipt_dispatches ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations.receipt_dispatches FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON integrations.receipt_dispatches USING("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true));
GRANT SELECT,INSERT ON integrations.receipt_dispatches TO :"app_user";
GRANT UPDATE("State","Attempts","Failures","KnownDocumentId","LastAttemptAt","NextAttemptAt","LeaseUntil","ExternalReference","LastError","UpdatedAt") ON integrations.receipt_dispatches TO :"app_user";
