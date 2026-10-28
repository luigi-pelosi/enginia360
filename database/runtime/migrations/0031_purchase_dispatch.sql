-- R04.b.2b.3 Giobby purchase-order dispatch. Appended only: 0001-0030 are unchanged and the Held outbox stays immutable.
-- Eligibility is derived: a priced intent (D91 frozen price) without an outcome row. An unpriced 0028 intent is structurally never dispatchable.
-- Giobby stays the only writer of stock and purchase documents (D82); nothing here writes local stock or documents.
CREATE TABLE inventory.purchase_intent_outcomes (
 "IntentId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "Status" text NOT NULL DEFAULT 'Confirmed' CHECK ("Status"='Confirmed'),
 "ExternalReference" varchar(64) NOT NULL CHECK ("ExternalReference" ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,63}$'),
 "RecordedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY("IntentId","TenantId","LegalEntityId") REFERENCES inventory.purchase_intents("Id","TenantId","LegalEntityId"),
 FOREIGN KEY("IntentId") REFERENCES inventory.purchase_intent_prices("IntentId")
);
CREATE UNIQUE INDEX purchase_outcome_reference ON inventory.purchase_intent_outcomes("TenantId","ExternalReference");
ALTER TABLE inventory.purchase_intent_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory.purchase_intent_outcomes FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON inventory.purchase_intent_outcomes
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_purchase_outcome BEFORE UPDATE OR DELETE OR TRUNCATE ON inventory.purchase_intent_outcomes
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON inventory.purchase_intent_outcomes FROM PUBLIC;

-- Connector-owned technical delivery state of one purchase intent. Mutable, never a business outcome by itself.
CREATE TABLE integrations.purchase_dispatches (
 "IntentId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "State" varchar(20) NOT NULL CHECK ("State" IN ('Queued','Uncertain','Completed')),
 "Attempts" integer NOT NULL CHECK ("Attempts">=0),"Failures" integer NOT NULL DEFAULT 0 CHECK ("Failures">=0),
 "LastAttemptAt" timestamptz,"NextAttemptAt" timestamptz NOT NULL,"LeaseUntil" timestamptz,
 "ExternalReference" varchar(64),"LastError" varchar(64),"UpdatedAt" timestamptz NOT NULL
);
ALTER TABLE integrations.purchase_dispatches ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations.purchase_dispatches FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON integrations.purchase_dispatches USING("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true));
GRANT SELECT,INSERT ON integrations.purchase_dispatches TO :"app_user";
GRANT UPDATE("State","Attempts","Failures","LastAttemptAt","NextAttemptAt","LeaseUntil","ExternalReference","LastError","UpdatedAt") ON integrations.purchase_dispatches TO :"app_user";

-- Cross-tenant discovery of envelopes only (identifiers, never payloads), by the same NOLOGIN owner pattern as 0011/0012.
GRANT CREATE ON SCHEMA inventory TO enginia360_outbox_reader;
GRANT USAGE ON SCHEMA inventory TO enginia360_outbox_reader;
GRANT SELECT("TenantId","LegalEntityId","Id","CreatedAt") ON inventory.purchase_intents TO enginia360_outbox_reader;
GRANT SELECT("IntentId") ON inventory.purchase_intent_prices TO enginia360_outbox_reader;
GRANT SELECT("IntentId") ON inventory.purchase_intent_outcomes TO enginia360_outbox_reader;
CREATE FUNCTION inventory.pending_purchase_dispatch(max_items integer,scan_offset integer)
RETURNS TABLE("TenantId" uuid,"LegalEntityId" uuid,"IntentId" uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT i."TenantId",i."LegalEntityId",i."Id" FROM inventory.purchase_intents i
 WHERE EXISTS(SELECT 1 FROM inventory.purchase_intent_prices p WHERE p."IntentId"=i."Id")
  AND NOT EXISTS(SELECT 1 FROM inventory.purchase_intent_outcomes o WHERE o."IntentId"=i."Id")
 ORDER BY i."CreatedAt",i."Id" LIMIT least(greatest(max_items,1),100) OFFSET greatest(scan_offset,0)
$$;
-- Set ACLs while the migration role still owns the function: ALTER OWNER first would turn these into warning-only no-ops.
REVOKE ALL ON FUNCTION inventory.pending_purchase_dispatch(integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.pending_purchase_dispatch(integer,integer) TO :"app_user";
ALTER FUNCTION inventory.pending_purchase_dispatch(integer,integer) OWNER TO enginia360_outbox_reader;
REVOKE CREATE ON SCHEMA inventory FROM enginia360_outbox_reader;

-- Frozen facts of one priced intent. The caller must already be in the verified tenant context; the arguments only select the row.
CREATE FUNCTION inventory.read_purchase_dispatch(tenant uuid,company uuid,intent uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE result jsonb; BEGIN
 IF tenant IS NULL OR company IS NULL OR current_setting('app.tenant_id',true) IS DISTINCT FROM tenant::text THEN RETURN NULL; END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 SELECT jsonb_build_object('tenantId',i."TenantId",'legalEntityId',i."LegalEntityId",'siteId',i."SiteId",'intentId',i."Id",
  'catalogItemId',i."Source"->>'catalogItemId','description',i."Source"->>'description','quantity',to_char(i."Quantity",'FM999999990.000000'),
  'unitPrice',to_char(p."AcceptedUnitPurchasePrice",'FM999990.000000'),'vendorId',i."Supplier"->>'vendorId','vendorName',i."Supplier"->>'vendorName',
  'fingerprint',i."Destination"->>'fingerprint') INTO result
 FROM inventory.purchase_intents i JOIN inventory.purchase_intent_prices p ON p."IntentId"=i."Id"
 WHERE i."Id"=intent AND i."TenantId"=tenant AND i."LegalEntityId"=company;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION inventory.read_purchase_dispatch(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.read_purchase_dispatch(uuid,uuid,uuid) TO :"app_user";

-- Insert-only, idempotent outcome. An unpriced intent can never be confirmed; one external order confirms at most one intent.
CREATE FUNCTION inventory.record_purchase_outcome(tenant uuid,company uuid,intent uuid,reference text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,inventory AS $$
DECLARE existing inventory.purchase_intent_outcomes; BEGIN
 IF tenant IS NULL OR company IS NULL OR current_setting('app.tenant_id',true) IS DISTINCT FROM tenant::text THEN RETURN 'forbidden'; END IF;
 IF reference IS NULL OR reference !~ '^[A-Za-z0-9][A-Za-z0-9-]{0,63}$' THEN RETURN 'invalid'; END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 PERFORM pg_advisory_xact_lock(hashtextextended('purchase-outcome:'||tenant::text||':'||intent::text,0));
 IF NOT EXISTS(SELECT 1 FROM inventory.purchase_intents WHERE "Id"=intent AND "TenantId"=tenant AND "LegalEntityId"=company) THEN RETURN 'not_found'; END IF;
 IF NOT EXISTS(SELECT 1 FROM inventory.purchase_intent_prices WHERE "IntentId"=intent) THEN RETURN 'not_priced'; END IF;
 SELECT * INTO existing FROM inventory.purchase_intent_outcomes WHERE "IntentId"=intent;
 IF FOUND THEN RETURN CASE WHEN existing."ExternalReference"=reference THEN 'replayed' ELSE 'conflict' END; END IF;
 INSERT INTO inventory.purchase_intent_outcomes("IntentId","TenantId","LegalEntityId","ExternalReference") VALUES(intent,tenant,company,reference);
 RETURN 'recorded';
EXCEPTION WHEN unique_violation THEN RETURN 'conflict';
END $$;
REVOKE ALL ON FUNCTION inventory.record_purchase_outcome(uuid,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION inventory.record_purchase_outcome(uuid,uuid,uuid,text) TO :"app_user";
