-- MVP07/#146. New document-owned quantity authority; NEVER changes inventory.*.
-- 0001-0044 published bytes are immutable. No business seeds or implicit grants.
CREATE SCHEMA documents;
CREATE TABLE documents.headers (
 "Id" uuid PRIMARY KEY, "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL, "DocumentTypeId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0), "State" text NOT NULL CHECK ("State" IN ('Draft','Confirmed')),
 "Title" text NOT NULL CHECK (length("Title") BETWEEN 1 AND 100 AND btrim("Title")<>'' AND "Title" !~ '[[:cntrl:]]'),
 "AppliedConfiguration" jsonb, "ConfirmedAt" timestamptz,
 UNIQUE("TenantId","LegalEntityId","Id"),
 FOREIGN KEY ("SiteId","LegalEntityId","TenantId") REFERENCES organization_access.sites("Id","LegalEntityId","TenantId"),
 FOREIGN KEY ("TenantId","LegalEntityId","DocumentTypeId") REFERENCES document_types.definitions("TenantId","LegalEntityId","Id"),
 CHECK (("State"='Confirmed')=("AppliedConfiguration" IS NOT NULL AND "ConfirmedAt" IS NOT NULL))
);
CREATE TABLE documents.lines (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "DocumentId" uuid NOT NULL,
 "Id" uuid NOT NULL, "Position" integer NOT NULL CHECK ("Position">0),
 "CatalogItemId" uuid NOT NULL REFERENCES catalog.items("Id"), "CatalogVersion" integer NOT NULL CHECK ("CatalogVersion">0),
 "Kind" text NOT NULL CHECK ("Kind" IN ('Article','Service')), "Label" text NOT NULL,
 "Quantity" numeric(24,6) NOT NULL CHECK ("Quantity">0), "WarehouseId" uuid, "DestinationWarehouseId" uuid,
 PRIMARY KEY("TenantId","LegalEntityId","DocumentId","Id"), UNIQUE("TenantId","LegalEntityId","DocumentId","Position"),
 FOREIGN KEY("TenantId","LegalEntityId","DocumentId") REFERENCES documents.headers("TenantId","LegalEntityId","Id"),
 CHECK ("Kind"<>'Service' OR ("WarehouseId" IS NULL AND "DestinationWarehouseId" IS NULL))
);
CREATE TABLE documents.versions (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "DocumentId" uuid NOT NULL,
 "Revision" integer NOT NULL, "Snapshot" jsonb NOT NULL,
 PRIMARY KEY("TenantId","LegalEntityId","DocumentId","Revision"),
 FOREIGN KEY("TenantId","LegalEntityId","DocumentId") REFERENCES documents.headers("TenantId","LegalEntityId","Id")
);
CREATE TABLE documents.policy_versions (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0), "AllowNegative" boolean NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY("TenantId","LegalEntityId","Revision"),
 FOREIGN KEY("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId")
);
CREATE TABLE documents.balances (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL,
 "WarehouseId" uuid NOT NULL, "CatalogItemId" uuid NOT NULL REFERENCES catalog.items("Id"),
 "Quantity" numeric(24,6) NOT NULL,
 PRIMARY KEY("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId"),
 FOREIGN KEY("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId")
);
CREATE TABLE documents.ledger (
 "Id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL,
 "DocumentId" uuid NOT NULL, "LineId" uuid NOT NULL, "WarehouseId" uuid NOT NULL,
 "CatalogItemId" uuid NOT NULL, "CatalogVersion" integer NOT NULL, "CatalogLabel" text NOT NULL,
 "Leg" text NOT NULL CHECK ("Leg" IN ('in','out')), "Quantity" numeric(24,6) NOT NULL CHECK ("Quantity"<>0),
 "OccurredAt" timestamptz NOT NULL,
 UNIQUE("TenantId","LegalEntityId","DocumentId","LineId","Leg"),
 FOREIGN KEY("TenantId","LegalEntityId","DocumentId","LineId") REFERENCES documents.lines("TenantId","LegalEntityId","DocumentId","Id"),
 FOREIGN KEY("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId") REFERENCES documents.balances("TenantId","LegalEntityId","SiteId","WarehouseId","CatalogItemId"),
 CHECK (("Leg"='in')=("Quantity">0))
);
CREATE TABLE documents.command_audit (
 "CommandId" uuid PRIMARY KEY, "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL, "BindingHash" bytea NOT NULL, "Request" jsonb NOT NULL,
 "Before" jsonb NOT NULL, "After" jsonb NOT NULL, "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
-- Technical MVCC witness, NOT business initial stock. Covers absence of policy
-- and balance rows in an old RR snapshot, as well as immutable policy appends.
CREATE TABLE documents.snapshot_fence ("Singleton" boolean PRIMARY KEY CHECK ("Singleton"), "Token" boolean NOT NULL);
INSERT INTO documents.snapshot_fence VALUES(true,false);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['headers','lines','versions','policy_versions','balances','ledger','command_audit','snapshot_fence'] LOOP
  EXECUTE format('ALTER TABLE documents.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE documents.%I FORCE ROW LEVEL SECURITY',t);
  IF t IN ('command_audit','snapshot_fence') THEN
   EXECUTE format('CREATE POLICY owner_only ON documents.%I TO CURRENT_USER USING(true) WITH CHECK(true)',t);
  ELSE
   EXECUTE format('CREATE POLICY owner_only ON documents.%I TO CURRENT_USER USING ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true))',t);
  END IF;
 END LOOP;
 FOREACH t IN ARRAY ARRAY['versions','policy_versions','ledger','command_audit'] LOOP
  EXECUTE format('CREATE TRIGGER immutable_fact BEFORE UPDATE OR DELETE OR TRUNCATE ON documents.%I FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit()',t);
 END LOOP;
END $$;
CREATE FUNCTION documents.protect_confirmed() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,documents AS $$
BEGIN
 IF TG_TABLE_NAME='headers' THEN
  IF OLD."State"='Confirmed' THEN RAISE EXCEPTION 'confirmed document immutable' USING ERRCODE='23514'; END IF;
 ELSE
  IF TG_OP IN ('UPDATE','DELETE') THEN
   IF EXISTS(SELECT 1 FROM documents.headers WHERE "TenantId"=OLD."TenantId" AND "LegalEntityId"=OLD."LegalEntityId" AND "Id"=OLD."DocumentId" AND "State"='Confirmed') THEN
    RAISE EXCEPTION 'confirmed line immutable' USING ERRCODE='23514';
   END IF;
  END IF;
  IF TG_OP IN ('INSERT','UPDATE') THEN
   IF EXISTS(SELECT 1 FROM documents.headers WHERE "TenantId"=NEW."TenantId" AND "LegalEntityId"=NEW."LegalEntityId" AND "Id"=NEW."DocumentId" AND "State"='Confirmed') THEN
    RAISE EXCEPTION 'confirmed line immutable' USING ERRCODE='23514';
   END IF;
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_confirmed BEFORE UPDATE OR DELETE ON documents.headers FOR EACH ROW EXECUTE FUNCTION documents.protect_confirmed();
CREATE TRIGGER protect_confirmed BEFORE INSERT OR UPDATE OR DELETE ON documents.lines FOR EACH ROW EXECUTE FUNCTION documents.protect_confirmed();
REVOKE ALL ON ALL TABLES IN SCHEMA documents FROM PUBLIC, :"app_user";
REVOKE ALL ON SCHEMA documents FROM PUBLIC;
GRANT USAGE ON SCHEMA documents TO :"app_user";

CREATE FUNCTION organization_access.document_permission(action_name text, company uuid, site uuid, warehouse uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR company IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN false; END IF;
 IF action_name IN ('documents.read','documents.save','documents.confirm') THEN
  IF site IS NULL OR warehouse IS NOT NULL THEN RETURN false; END IF;
 ELSIF action_name IN ('inventory.document-effects.apply','inventory.quantities.read') THEN
  IF site IS NULL OR warehouse IS NULL THEN RETURN false; END IF;
 ELSIF action_name IN ('inventory.policy.read','inventory.policy.manage') THEN
  IF site IS NOT NULL OR warehouse IS NOT NULL THEN RETURN false; END IF;
 ELSE RETURN false; END IF;
 PERFORM 1 FROM organization_access.tenant_role_objects WHERE "TenantId"=target FOR SHARE;
 PERFORM 1 FROM organization_access.legal_entities WHERE "TenantId"=target AND "Id"=company FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 IF site IS NOT NULL THEN
  PERFORM 1 FROM organization_access.sites WHERE "TenantId"=target AND "LegalEntityId"=company AND "Id"=site FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;
 END IF;
 IF warehouse IS NOT NULL THEN
  PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "Id"=warehouse FOR SHARE;
  IF NOT FOUND THEN RETURN false; END IF;
 END IF;
 RETURN EXISTS(SELECT 1 FROM organization_access.current_tenant_role_scopes_before_access() s
 JOIN organization_access.tenant_role_objects p ON p."Id"=s."Id" AND p."TenantId"=target AND p."Kind"='permission'
 WHERE s."TenantId"=target AND s."Permission"=action_name AND s."LegalEntityId"=company
 AND s."SiteId" IS NOT DISTINCT FROM site AND s."WarehouseId" IS NOT DISTINCT FROM warehouse
 AND p."Data" ?& ARRAY['action','legalEntityId','siteId','warehouseId']
 AND p."Data"->'legalEntityId'=to_jsonb(company)
 AND p."Data"->'siteId'=coalesce(to_jsonb(site),'null'::jsonb)
 AND p."Data"->'warehouseId'=coalesce(to_jsonb(warehouse),'null'::jsonb));
END $$;
REVOKE ALL ON FUNCTION organization_access.document_permission(text,uuid,uuid,uuid) FROM PUBLIC, :"app_user";

-- Explicit owner projections consumed in the same caller transaction; no app
-- EXECUTE, generic directory fallback, editing right or pooled nested adapter.
CREATE FUNCTION catalog.document_item(item uuid, expected_version integer) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,catalog AS $$
DECLARE result jsonb; BEGIN
 SELECT jsonb_build_object('id',"Id",'revision',"Version",'kind',CASE "Kind" WHEN 'Part' THEN 'Article' ELSE 'Service' END,'label',"Label") INTO result
 FROM catalog.items WHERE "Id"=item AND "TenantId"::text=current_setting('app.tenant_id',true) AND "Version"=expected_version FOR SHARE;
 RETURN result;
END $$;
CREATE FUNCTION catalog.document_choices(search_text text, after_id uuid) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog,catalog AS $$
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',x."Id",'revision',x."Version",'kind',CASE x."Kind" WHEN 'Part' THEN 'Article' ELSE 'Service' END,'label',x."Label") ORDER BY x."Id"),'[]'::jsonb)
 FROM (SELECT * FROM catalog.items WHERE "TenantId"::text=current_setting('app.tenant_id',true)
 AND (search_text IS NULL OR strpos(lower("Label"),lower(search_text))>0) AND (after_id IS NULL OR "Id">after_id) ORDER BY "Id" LIMIT 21) x
$$;
CREATE FUNCTION document_types.for_document(type_id uuid) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,document_types AS $$
DECLARE revision_now integer; BEGIN
 SELECT "Revision" INTO revision_now FROM document_types.definitions WHERE "Id"=type_id
 AND "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true) FOR SHARE;
 RETURN document_types.snapshot(type_id,revision_now);
END $$;
CREATE FUNCTION document_types.document_choices(search_text text, after_id uuid) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog,document_types AS $$
 SELECT coalesce(jsonb_agg(document_types.snapshot(x."Id",x."Revision") ORDER BY x."Id"),'[]'::jsonb)
 FROM (SELECT d."Id",d."Revision" FROM document_types.definitions d JOIN document_types.versions v
 ON (v."TenantId",v."LegalEntityId",v."DocumentTypeId",v."Revision")=(d."TenantId",d."LegalEntityId",d."Id",d."Revision")
 WHERE d."TenantId"::text=current_setting('app.tenant_id',true) AND d."LegalEntityId"::text=current_setting('app.legal_entity_id',true)
 AND (search_text IS NULL OR strpos(lower(v."Label"),lower(search_text))>0) AND (after_id IS NULL OR d."Id">after_id) ORDER BY d."Id" LIMIT 21) x
$$;
REVOKE ALL ON FUNCTION catalog.document_item(uuid,integer),catalog.document_choices(text,uuid),document_types.for_document(uuid),document_types.document_choices(text,uuid) FROM PUBLIC, :"app_user";

CREATE FUNCTION documents.policy() RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,documents AS $$
 SELECT coalesce((SELECT jsonb_build_object('revision',"Revision",'allowNegative',"AllowNegative",'occurredAt',"OccurredAt")
 FROM documents.policy_versions WHERE "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true) ORDER BY "Revision" DESC LIMIT 1),
 jsonb_build_object('revision',0,'allowNegative',false,'occurredAt',NULL))
$$;
CREATE FUNCTION documents.snapshot(record_id uuid) RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,documents AS $$
 SELECT jsonb_build_object('id',h."Id",'legalEntityId',h."LegalEntityId",'siteId',h."SiteId",'documentTypeId',h."DocumentTypeId",'revision',h."Revision",'state',h."State",'title',h."Title",'appliedConfiguration',h."AppliedConfiguration",'confirmedAt',h."ConfirmedAt",'lines',
 coalesce((SELECT jsonb_agg(jsonb_build_object('id',l."Id",'itemId',l."CatalogItemId",'catalogRevision',l."CatalogVersion",'kind',l."Kind",'label',l."Label",'quantity',l."Quantity"::text,'warehouseId',l."WarehouseId",'destinationWarehouseId',l."DestinationWarehouseId") ORDER BY l."Position")
 FROM documents.lines l WHERE (l."TenantId",l."LegalEntityId",l."DocumentId")=(h."TenantId",h."LegalEntityId",h."Id")),'[]'::jsonb))
 FROM documents.headers h WHERE h."Id"=record_id AND h."TenantId"::text=current_setting('app.tenant_id',true) AND h."LegalEntityId"::text=current_setting('app.legal_entity_id',true)
$$;
CREATE FUNCTION documents.valid_uuid(value jsonb, nullable boolean DEFAULT false) RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT CASE WHEN value='null'::jsonb THEN nullable ELSE coalesce(jsonb_typeof(value)='string' AND value#>>'{}' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' AND value#>>'{}'<>'00000000-0000-0000-0000-000000000000',false) END
$$;
CREATE FUNCTION documents.valid_revision(value jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT CASE WHEN jsonb_typeof(value)='number' AND value#>>'{}' ~ '^(0|[1-9][0-9]{0,9})$' THEN (value#>>'{}')::numeric<=2147483647 ELSE false END
$$;
CREATE FUNCTION documents.movement_rows(record_id uuid, effect text) RETURNS TABLE(line_id uuid,item_id uuid,item_revision integer,item_label text,warehouse uuid,leg text,quantity numeric)
LANGUAGE sql SET search_path=pg_catalog,documents AS $$
 SELECT "Id","CatalogItemId","CatalogVersion","Label","WarehouseId",CASE WHEN effect='Load' THEN 'in' ELSE 'out' END,CASE WHEN effect='Load' THEN "Quantity" ELSE -"Quantity" END
 FROM documents.lines WHERE "DocumentId"=record_id AND "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true) AND "Kind"='Article' AND effect IN ('Load','Unload','Transfer')
 UNION ALL
 SELECT "Id","CatalogItemId","CatalogVersion","Label","DestinationWarehouseId",'in',"Quantity"
 FROM documents.lines WHERE "DocumentId"=record_id AND "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true) AND "Kind"='Article' AND effect='Transfer'
$$;

CREATE FUNCTION documents.command(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,documents,organization_access AS $$
DECLARE target uuid; member_id uuid; binding_hash bytea; command_id uuid; record_id uuid; company uuid; site uuid;
 operation text; key text; keys text[]; previous documents.command_audit; header documents.headers;
 before_row jsonb; after_row jsonb; type_config jsonb; policy_config jsonb; item jsonb; line jsonb; normalized_lines jsonb:='[]'::jsonb;
 effect text; line_position integer:=0; quantity_value numeric; current_balance numeric; outgoing numeric; pool record; instant timestamptz;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 PERFORM "Singleton" FROM documents.snapshot_fence WHERE "Singleton" FOR SHARE;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 IF operation IS NULL OR operation NOT IN ('create','save','confirm','policy') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 keys:=ARRAY['commandId','operation','legalEntityId','expectedRevision']||CASE operation
 WHEN 'policy' THEN ARRAY['allowNegative']
 WHEN 'confirm' THEN ARRAY['documentId','siteId','expectedTypeRevision','expectedPolicyRevision']
 ELSE ARRAY['documentId','siteId','documentTypeId','title','expectedTypeRevision','lines'] END;
 IF NOT request ?& keys OR (SELECT count(*) FROM jsonb_object_keys(request))<>cardinality(keys) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','legalEntityId']||CASE WHEN operation='policy' THEN ARRAY[]::text[] ELSE ARRAY['documentId','siteId'] END||CASE WHEN operation IN ('create','save') THEN ARRAY['documentTypeId'] ELSE ARRAY[]::text[] END LOOP
  IF NOT documents.valid_uuid(request->key,operation='create' AND key='documentId') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 FOREACH key IN ARRAY ARRAY['expectedRevision']||CASE WHEN operation='policy' THEN ARRAY[]::text[] ELSE ARRAY['expectedTypeRevision'] END||CASE WHEN operation='confirm' THEN ARRAY['expectedPolicyRevision'] ELSE ARRAY[]::text[] END LOOP
  IF NOT documents.valid_revision(request->key) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 company:=(request->>'legalEntityId')::uuid; site:=(request->>'siteId')::uuid;
 IF operation='policy' THEN
  IF jsonb_typeof(request->'allowNegative') IS DISTINCT FROM 'boolean' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF NOT organization_access.document_permission('inventory.policy.read',company,NULL,NULL) OR NOT organization_access.document_permission('inventory.policy.manage',company,NULL,NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 ELSE
  IF NOT organization_access.document_permission('documents.read',company,site,NULL) OR NOT organization_access.document_permission(CASE WHEN operation='confirm' THEN 'documents.confirm' ELSE 'documents.save' END,company,site,NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 command_id:=(request->>'commandId')::uuid; record_id:=(request->>'documentId')::uuid;
 IF operation IN ('create','save') THEN
  IF jsonb_typeof(request->'title') IS DISTINCT FROM 'string' OR length(request->>'title') NOT BETWEEN 1 AND 100 OR btrim(request->>'title')='' OR request->>'title' ~ '[[:cntrl:]]' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF jsonb_typeof(request->'lines') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF jsonb_array_length(request->'lines') NOT BETWEEN 1 AND 200 THEN RETURN jsonb_build_object('state','invalid'); END IF;
  FOR line IN SELECT value FROM jsonb_array_elements(request->'lines') LOOP
   IF jsonb_typeof(line) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF NOT line ?& ARRAY['id','itemId','catalogRevision','quantity','warehouseId','destinationWarehouseId'] OR (SELECT count(*) FROM jsonb_object_keys(line))<>6 THEN RETURN jsonb_build_object('state','invalid'); END IF;
   FOREACH key IN ARRAY ARRAY['id','itemId','warehouseId','destinationWarehouseId'] LOOP
    IF NOT documents.valid_uuid(line->key,key IN ('warehouseId','destinationWarehouseId')) THEN RETURN jsonb_build_object('state','invalid'); END IF;
   END LOOP;
   IF NOT documents.valid_revision(line->'catalogRevision') OR line->>'catalogRevision'='0' OR jsonb_typeof(line->'quantity') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF line->>'quantity' !~ '^(0|[1-9][0-9]{0,17})(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   quantity_value:=(line->>'quantity')::numeric;
   IF quantity_value<=0 OR quantity_value>999999999999999999.999999 THEN RETURN jsonb_build_object('state','invalid'); END IF;
   normalized_lines:=normalized_lines||jsonb_build_array(jsonb_set(line,'{quantity}',to_jsonb(quantity_value::numeric(24,6)::text)));
  END LOOP;
  IF (SELECT count(*)<>count(DISTINCT value->>'id') FROM jsonb_array_elements(normalized_lines)) THEN RETURN jsonb_build_object('state','invalid'); END IF;
  request:=jsonb_set(request,'{lines}',normalized_lines);
  request:=jsonb_set(request,'{title}',to_jsonb(btrim(request->>'title')));
 END IF;
 -- Current grants checked before replay, including warehouse grants in original
 -- accepted facts (not a changed current type that could surprise a replay).
 IF operation='confirm' THEN
  SELECT * INTO header FROM documents.headers WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "Id"=record_id FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  FOR pool IN SELECT DISTINCT w FROM documents.lines l CROSS JOIN LATERAL unnest(ARRAY[l."WarehouseId",l."DestinationWarehouseId"]) w
   WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."DocumentId"=record_id AND w IS NOT NULL LOOP
   IF NOT organization_access.document_permission('inventory.document-effects.apply',company,site,pool.w) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  END LOOP;
 ELSIF operation IN ('create','save') THEN
  FOR line IN SELECT value FROM jsonb_array_elements(normalized_lines) LOOP
   FOREACH key IN ARRAY ARRAY['warehouseId','destinationWarehouseId'] LOOP
    IF line->key<>'null'::jsonb AND NOT organization_access.document_permission('inventory.document-effects.apply',company,site,(line->>key)::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
   END LOOP;
  END LOOP;
 END IF;
 binding_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 SELECT * INTO previous FROM documents.command_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."LegalEntityId"=company AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=binding_hash AND previous."Request"=request THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 policy_config:=documents.policy();
 IF operation='policy' THEN
  IF (policy_config->>'revision')::integer<>(request->>'expectedRevision')::integer OR request->>'expectedRevision'='2147483647' THEN RETURN jsonb_build_object('state','config_changed'); END IF;
  before_row:=policy_config;
  INSERT INTO documents.policy_versions("TenantId","LegalEntityId","Revision","AllowNegative") VALUES(target,company,(request->>'expectedRevision')::integer+1,(request->>'allowNegative')::boolean);
  after_row:=documents.policy();
 ELSE
  IF operation='create' THEN
   IF record_id IS NOT NULL OR request->>'expectedRevision'<>'0' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   record_id:=gen_random_uuid(); before_row:='{}'::jsonb;
  ELSE
   IF operation='save' THEN
    SELECT * INTO header FROM documents.headers WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "Id"=record_id FOR UPDATE;
    IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
   END IF;
   IF header."State"='Confirmed' THEN RETURN jsonb_build_object('state','already_confirmed'); END IF;
   IF header."Revision"<>(request->>'expectedRevision')::integer OR header."Revision"=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
   before_row:=documents.snapshot(record_id);
  END IF;
  type_config:=document_types.for_document(CASE WHEN operation='confirm' THEN header."DocumentTypeId" ELSE (request->>'documentTypeId')::uuid END);
  IF type_config IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
  IF type_config->>'revision'<>request->>'expectedTypeRevision' OR (operation='confirm' AND policy_config->>'revision'<>request->>'expectedPolicyRevision') THEN RETURN jsonb_build_object('state','config_changed'); END IF;
  effect:=type_config->>'effect';
  IF operation IN ('create','save') THEN
   -- Validate and lock each canonical item before changing any owned row.
   FOR line IN SELECT value FROM jsonb_array_elements(normalized_lines) LOOP
    item:=catalog.document_item((line->>'itemId')::uuid,(line->>'catalogRevision')::integer);
    IF item IS NULL THEN RETURN jsonb_build_object('state','catalog_changed'); END IF;
    IF item->>'kind'='Service' OR effect='None' THEN
     IF line->'warehouseId'<>'null'::jsonb OR line->'destinationWarehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
    ELSE
     IF line->'warehouseId'='null'::jsonb OR (effect='Transfer' AND (line->'destinationWarehouseId'='null'::jsonb OR line->'warehouseId'=line->'destinationWarehouseId')) OR (effect<>'Transfer' AND line->'destinationWarehouseId'<>'null'::jsonb) THEN RETURN jsonb_build_object('state','invalid'); END IF;
    END IF;
   END LOOP;
   IF operation='create' THEN
    INSERT INTO documents.headers("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","Revision","State","Title") VALUES(record_id,target,company,site,(request->>'documentTypeId')::uuid,1,'Draft',request->>'title');
   ELSE
    DELETE FROM documents.lines WHERE "TenantId"=target AND "LegalEntityId"=company AND "DocumentId"=record_id;
    UPDATE documents.headers SET "DocumentTypeId"=(request->>'documentTypeId')::uuid,"Title"=request->>'title',"Revision"="Revision"+1 WHERE "TenantId"=target AND "LegalEntityId"=company AND "Id"=record_id;
   END IF;
   FOR line IN SELECT value FROM jsonb_array_elements(normalized_lines) LOOP
    line_position:=line_position+1; item:=catalog.document_item((line->>'itemId')::uuid,(line->>'catalogRevision')::integer);
    INSERT INTO documents.lines VALUES(target,company,record_id,(line->>'id')::uuid,line_position,(line->>'itemId')::uuid,(line->>'catalogRevision')::integer,item->>'kind',item->>'label',(line->>'quantity')::numeric,(line->>'warehouseId')::uuid,(line->>'destinationWarehouseId')::uuid);
   END LOOP;
  ELSE
   -- A changed effect may require explicit draft editing, never silent assignment.
   IF EXISTS(SELECT 1 FROM documents.lines l WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."DocumentId"=record_id AND l."Kind"='Article' AND
    ((effect='None' AND (l."WarehouseId" IS NOT NULL OR l."DestinationWarehouseId" IS NOT NULL)) OR
     (effect<>'None' AND l."WarehouseId" IS NULL) OR
     (effect='Transfer' AND (l."DestinationWarehouseId" IS NULL OR l."DestinationWarehouseId"=l."WarehouseId")) OR
     (effect NOT IN ('None','Transfer') AND l."DestinationWarehouseId" IS NOT NULL))) THEN RETURN jsonb_build_object('state','draft_requires_save'); END IF;
   -- Complete key order; no per-line lock inversions in opposing transfers.
   FOR pool IN SELECT warehouse,item_id,sum(quantity) AS delta,sum(CASE WHEN quantity<0 THEN -quantity ELSE 0 END) AS outgoing
    FROM documents.movement_rows(record_id,effect) GROUP BY warehouse,item_id ORDER BY warehouse,item_id LOOP
    INSERT INTO documents.balances VALUES(target,company,site,pool.warehouse,pool.item_id,0) ON CONFLICT DO NOTHING;
    SELECT "Quantity" INTO current_balance FROM documents.balances WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "WarehouseId"=pool.warehouse AND "CatalogItemId"=pool.item_id FOR UPDATE;
    IF abs(current_balance+pool.delta)>999999999999999999.999999 THEN RAISE EXCEPTION 'quantity overflow' USING ERRCODE='22003'; END IF;
    -- Check outgoing aggregate before incoming credit, even in mixed same-key legs.
    IF NOT (policy_config->>'allowNegative')::boolean AND pool.outgoing>0 AND current_balance-pool.outgoing<0 THEN
     RAISE EXCEPTION 'insufficient stock' USING ERRCODE='P0045';
    END IF;
   END LOOP;
   instant:=clock_timestamp();
   INSERT INTO documents.ledger("TenantId","LegalEntityId","SiteId","DocumentId","LineId","WarehouseId","CatalogItemId","CatalogVersion","CatalogLabel","Leg","Quantity","OccurredAt")
   SELECT target,company,site,record_id,line_id,warehouse,item_id,item_revision,item_label,leg,quantity,instant FROM documents.movement_rows(record_id,effect);
   FOR pool IN SELECT warehouse,item_id,sum(quantity) AS delta FROM documents.movement_rows(record_id,effect) GROUP BY warehouse,item_id ORDER BY warehouse,item_id LOOP
    UPDATE documents.balances SET "Quantity"="Quantity"+pool.delta WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "WarehouseId"=pool.warehouse AND "CatalogItemId"=pool.item_id;
   END LOOP;
   UPDATE documents.headers SET "State"='Confirmed',"Revision"="Revision"+1,"AppliedConfiguration"=jsonb_build_object('documentType',type_config,'policy',policy_config),"ConfirmedAt"=instant WHERE "TenantId"=target AND "LegalEntityId"=company AND "Id"=record_id;
  END IF;
  after_row:=documents.snapshot(record_id);
  INSERT INTO documents.versions VALUES(target,company,record_id,(after_row->>'revision')::integer,after_row);
 END IF;
 INSERT INTO documents.command_audit("CommandId","TenantId","LegalEntityId","ActorMembershipId","BindingHash","Request","Before","After") VALUES(command_id,target,company,member_id,binding_hash,request,before_row,after_row);
 UPDATE documents.snapshot_fence SET "Token"=NOT "Token" WHERE "Singleton";
 RETURN jsonb_build_object('state','applied','snapshot',after_row);
EXCEPTION
 WHEN SQLSTATE 'P0045' THEN RETURN jsonb_build_object('state','insufficient_stock');
 WHEN numeric_value_out_of_range THEN RETURN jsonb_build_object('state','quantity_overflow');
 WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;

CREATE FUNCTION documents.read(company uuid,site uuid,warehouse uuid,record_id uuid,search_text text,after_id uuid,selection text,selection_after uuid,ledger_after uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,documents,organization_access AS $$
DECLARE target uuid; companies jsonb; sites jsonb:='[]'; warehouses jsonb:='[]'; items jsonb:='[]'; detail jsonb; ledger jsonb:='[]'; balances jsonb:='[]'; types jsonb:='[]'; catalog_items jsonb:='[]'; policy_config jsonb; history jsonb:='[]';
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 PERFORM "Singleton" FROM documents.snapshot_fence WHERE "Singleton" FOR SHARE;
 IF search_text IS NOT NULL AND (length(search_text)>200 OR search_text ~ '[[:cntrl:]]') OR selection IS NOT NULL AND selection NOT IN ('catalog','types') OR company IS NULL AND (site IS NOT NULL OR warehouse IS NOT NULL OR record_id IS NOT NULL OR search_text IS NOT NULL OR after_id IS NOT NULL OR selection IS NOT NULL OR selection_after IS NOT NULL OR ledger_after IS NOT NULL) OR site IS NULL AND (warehouse IS NOT NULL OR record_id IS NOT NULL OR selection IS NOT NULL OR search_text IS NOT NULL OR after_id IS NOT NULL OR selection_after IS NOT NULL OR ledger_after IS NOT NULL) OR selection_after IS NOT NULL AND selection IS NULL OR ledger_after IS NOT NULL AND record_id IS NULL AND warehouse IS NULL THEN RETURN jsonb_build_object('state','invalid'); END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',le."Id",'name',le."Name") ORDER BY le."Name",le."Id"),'[]'::jsonb) INTO companies FROM organization_access.legal_entities le WHERE le."TenantId"=target AND
 (organization_access.document_permission('inventory.policy.read',le."Id",NULL,NULL) OR EXISTS(SELECT 1 FROM organization_access.sites s WHERE s."TenantId"=target AND s."LegalEntityId"=le."Id" AND organization_access.document_permission('documents.read',le."Id",s."Id",NULL)) OR EXISTS(SELECT 1 FROM organization_access.warehouses w WHERE w."TenantId"=target AND w."LegalEntityId"=le."Id" AND organization_access.document_permission('inventory.quantities.read',le."Id",w."SiteId",w."Id")));
 IF company IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(companies) c WHERE c->>'id'=company::text) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  PERFORM set_config('app.legal_entity_id',company::text,true);
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',s."Id",'name',s."Name",'canReadDocuments',organization_access.document_permission('documents.read',company,s."Id",NULL)) ORDER BY s."Name",s."Id"),'[]') INTO sites FROM organization_access.sites s WHERE s."TenantId"=target AND s."LegalEntityId"=company AND (organization_access.document_permission('documents.read',company,s."Id",NULL) OR EXISTS(SELECT 1 FROM organization_access.warehouses w WHERE w."TenantId"=target AND w."LegalEntityId"=company AND w."SiteId"=s."Id" AND organization_access.document_permission('inventory.quantities.read',company,s."Id",w."Id")));
  IF organization_access.document_permission('inventory.policy.read',company,NULL,NULL) THEN
   policy_config:=documents.policy();
   SELECT coalesce(jsonb_agg(jsonb_build_object('revision',x."Revision",'allowNegative',x."AllowNegative",'occurredAt',x."OccurredAt") ORDER BY x."Revision" DESC),'[]') INTO history FROM (SELECT * FROM documents.policy_versions WHERE "TenantId"=target AND "LegalEntityId"=company ORDER BY "Revision" DESC LIMIT 20) x;
  END IF;
 END IF;
 IF site IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM jsonb_array_elements(sites) s WHERE s->>'id'=site::text) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',w."Id",'name',w."Name",'canApply',organization_access.document_permission('inventory.document-effects.apply',company,site,w."Id"),'canReadStock',organization_access.document_permission('inventory.quantities.read',company,site,w."Id")) ORDER BY w."Name",w."Id"),'[]') INTO warehouses FROM organization_access.warehouses w WHERE w."TenantId"=target AND w."LegalEntityId"=company AND w."SiteId"=site AND (organization_access.document_permission('inventory.document-effects.apply',company,site,w."Id") OR organization_access.document_permission('inventory.quantities.read',company,site,w."Id"));
  IF organization_access.document_permission('documents.read',company,site,NULL) THEN
   policy_config:=documents.policy();
   IF selection='catalog' THEN catalog_items:=catalog.document_choices(search_text,selection_after);
   ELSIF selection='types' THEN types:=document_types.document_choices(search_text,selection_after);
   ELSE
    types:=document_types.document_choices(NULL,NULL); catalog_items:=catalog.document_choices(NULL,NULL);
    SELECT coalesce(jsonb_agg((documents.snapshot(x."Id")-'lines')||jsonb_build_object('lines','[]'::jsonb) ORDER BY x."Id"),'[]') INTO items FROM (SELECT "Id" FROM documents.headers WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND (search_text IS NULL OR strpos(lower("Title"),lower(search_text))>0) AND (after_id IS NULL OR warehouse IS NOT NULL OR "Id">after_id) ORDER BY "Id" LIMIT 21) x;
   END IF;
   IF record_id IS NOT NULL THEN
    SELECT documents.snapshot("Id") INTO detail FROM documents.headers WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "Id"=record_id;
    IF detail IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
    -- Always supply the selected type even when it is beyond selector page1.
    types:=types||jsonb_build_array(document_types.for_document((detail->>'documentTypeId')::uuid));
   END IF;
  ELSIF record_id IS NOT NULL OR selection IS NOT NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 END IF;
 IF warehouse IS NOT NULL THEN
  IF NOT organization_access.document_permission('inventory.quantities.read',company,site,warehouse) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  SELECT coalesce(jsonb_agg(jsonb_build_object('itemId',x."CatalogItemId",'label',(SELECT l."CatalogLabel" FROM documents.ledger l WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."SiteId"=site AND l."WarehouseId"=warehouse AND l."CatalogItemId"=x."CatalogItemId" ORDER BY l."OccurredAt" DESC,l."Id" DESC LIMIT 1),'quantity',x."Quantity"::text) ORDER BY x."CatalogItemId"),'[]') INTO balances FROM (SELECT * FROM documents.balances WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND "WarehouseId"=warehouse AND (after_id IS NULL OR "CatalogItemId">after_id) ORDER BY "CatalogItemId" LIMIT 21) x;
 END IF;
 IF record_id IS NOT NULL OR warehouse IS NOT NULL THEN
  SELECT coalesce(jsonb_agg(jsonb_build_object('id',x."Id",'documentId',x."DocumentId",'lineId',x."LineId",'warehouseId',x."WarehouseId",'itemId',x."CatalogItemId",'catalogRevision',x."CatalogVersion",'label',x."CatalogLabel",'leg',x."Leg",'quantity',x."Quantity"::text,'occurredAt',x."OccurredAt",'canReadDocument',organization_access.document_permission('documents.read',company,site,NULL)) ORDER BY x."Id"),'[]') INTO ledger FROM (SELECT * FROM documents.ledger WHERE "TenantId"=target AND "LegalEntityId"=company AND "SiteId"=site AND (record_id IS NULL OR "DocumentId"=record_id) AND (warehouse IS NULL OR "WarehouseId"=warehouse) AND (ledger_after IS NULL OR "Id">ledger_after) ORDER BY "Id" LIMIT 21) x;
 END IF;
 IF companies='[]'::jsonb THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN jsonb_build_object('state','ready','companies',companies,'sites',sites,'warehouses',warehouses,'items',items,'detail',detail,'types',types,'catalog',catalog_items,'policy',policy_config,'policyHistory',history,'balances',balances,'ledger',ledger,
 'canSave',company IS NOT NULL AND site IS NOT NULL AND organization_access.document_permission('documents.read',company,site,NULL) AND organization_access.document_permission('documents.save',company,site,NULL),
 'canConfirm',company IS NOT NULL AND site IS NOT NULL AND organization_access.document_permission('documents.read',company,site,NULL) AND organization_access.document_permission('documents.confirm',company,site,NULL) AND NOT EXISTS(SELECT 1 FROM documents.lines l CROSS JOIN LATERAL unnest(ARRAY[l."WarehouseId",l."DestinationWarehouseId"]) w WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."DocumentId"=record_id AND w IS NOT NULL AND NOT organization_access.document_permission('inventory.document-effects.apply',company,site,w)),
 'canManagePolicy',company IS NOT NULL AND organization_access.document_permission('inventory.policy.read',company,NULL,NULL) AND organization_access.document_permission('inventory.policy.manage',company,NULL,NULL));
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA documents FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION documents.command(jsonb),documents.read(uuid,uuid,uuid,uuid,text,uuid,text,uuid,uuid) TO :"app_user";

ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_documents;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_documents(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior_target text:=current_setting('app.tenant_id',true); BEGIN
 result:=organization_access.read_tenant_roles_before_documents(target);
 IF result->>'state'='ok' AND result ? 'permissions' THEN
  PERFORM set_config('app.tenant_id',result->>'tenantId',true);
  result:=result||jsonb_build_object('sites',coalesce((SELECT jsonb_agg(jsonb_build_object('siteId',s."Id",'legalEntityId',s."LegalEntityId",'name',s."Name") ORDER BY s."Name",s."Id") FROM organization_access.sites s WHERE s."TenantId"=(result->>'tenantId')::uuid),'[]'::jsonb));
 END IF;
 IF result->>'state'='ok' AND result ? 'permissions' THEN
  result:=jsonb_set(result,'{actions}',(result->'actions')||jsonb_build_array('documents.read','documents.save','documents.confirm','inventory.document-effects.apply','inventory.quantities.read','inventory.policy.read','inventory.policy.manage'));
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

-- Preserve all pre-existing D97 branches and exact scope checks.
CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role(target uuid, request jsonb, authority jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE key text; kind text; keys text[]; id uuid; revision integer; before_row organization_access.tenant_role_objects;
 previous organization_access.tenant_role_audit; after_data jsonb; actor uuid:=current_setting('app.identity_subject')::uuid;
 actor_hash bytea:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
BEGIN
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 kind:=request->>'kind';
 IF kind IS NULL OR kind NOT IN ('delegation','permission','role','assignment') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 keys:=ARRAY['commandId','kind','resourceId','expectedRevision']||CASE kind
  WHEN 'delegation' THEN ARRAY['membershipId','internalIdentityId','bindingHash','active']
  WHEN 'assignment' THEN ARRAY['membershipId','internalIdentityId','bindingHash','active','roleId']
  WHEN 'role' THEN ARRAY['label','permissionIds']
  ELSE ARRAY['label','action','legalEntityId','siteId','warehouseId'] END;
 IF NOT request ?& keys OR (SELECT count(*) FROM jsonb_object_keys(request))<>cardinality(keys) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','resourceId']||CASE kind WHEN 'delegation' THEN ARRAY['membershipId','internalIdentityId'] WHEN 'assignment' THEN ARRAY['membershipId','internalIdentityId','roleId'] WHEN 'role' THEN ARRAY[]::text[] ELSE ARRAY['legalEntityId','siteId','warehouseId'] END LOOP
  IF (key='resourceId' OR (kind='permission' AND key IN ('legalEntityId','siteId','warehouseId'))) AND request->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number' OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$'
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->'resourceId'='null'::jsonb)<>(request->>'expectedRevision'='0') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF kind IN ('permission','role') THEN
  IF jsonb_typeof(request->'label') IS DISTINCT FROM 'string' OR length(request->>'label') NOT BETWEEN 1 AND 100 OR request->>'label' ~ '[[:cntrl:]]'
   OR length(btrim(request->>'label'))=0 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END IF;
 IF kind='role' THEN
  IF jsonb_typeof(request->'permissionIds') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF jsonb_array_length(request->'permissionIds')>64 THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements(request->'permissionIds') v WHERE jsonb_typeof(v) IS DISTINCT FROM 'string'
   OR v#>>'{}' !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
   OR (SELECT count(*)<>count(DISTINCT v) FROM jsonb_array_elements(request->'permissionIds') v) THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF EXISTS(SELECT 1 FROM jsonb_array_elements_text(request->'permissionIds') v WHERE NOT EXISTS(
   SELECT 1 FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"='permission' AND "Id"::text=v)) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 ELSIF kind='permission' THEN
  IF jsonb_typeof(request->'action') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF request->>'action' IN ('organization-context.read','organization-context.write') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'='null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "Id"=(request->>'warehouseId')::uuid
    AND "SiteId"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','catalog.shared.read','catalog.shared.create','catalog.shared.edit') THEN
   IF request->'legalEntityId'<>'null'::jsonb OR request->'siteId'<>'null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
  ELSIF request->>'action' IN ('documents.read','documents.save','documents.confirm') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.sites WHERE "TenantId"=target AND "Id"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('inventory.document-effects.apply','inventory.quantities.read') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'='null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "Id"=(request->>'warehouseId')::uuid AND "SiteId"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('counterparties.extensions.read','counterparties.extensions.write','document-types.read','document-types.create','document-types.edit','inventory.policy.read','inventory.policy.manage') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'<>'null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.legal_entities WHERE "TenantId"=target AND "Id"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSE RETURN jsonb_build_object('state','invalid'); END IF;
 ELSE
  IF kind='delegation' AND (authority->>'kind'<>'owner' OR request->>'internalIdentityId'=actor::text) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  IF kind='assignment' AND NOT EXISTS(SELECT 1 FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"='role' AND "Id"=(request->>'roleId')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  IF jsonb_typeof(request->'active') IS DISTINCT FROM 'boolean' OR jsonb_typeof(request->'bindingHash') IS DISTINCT FROM 'string'
   OR request->>'bindingHash' !~ '^[0-9a-f]{64}$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
  WHERE m."TenantId"=target AND m."Id"=(request->>'membershipId')::uuid AND b."InternalIdentityId"::text=request->>'internalIdentityId'
   AND encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex')=request->>'bindingHash' FOR SHARE OF m,b;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 END IF;
 SELECT * INTO previous FROM organization_access.tenant_role_audit WHERE "CommandId"=(request->>'commandId')::uuid AND "Outcome"='applied';
 IF FOUND THEN
  IF previous."ActorId"=actor AND previous."BindingHash"=actor_hash AND previous."TenantId"=target AND previous."Request"=request
  THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF request->'resourceId'='null'::jsonb THEN
  IF EXISTS(SELECT 1 FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"=kind AND "Data"->>'membershipId'=request->>'membershipId'
   AND (kind='delegation' OR "Data"->>'roleId'=request->>'roleId'))
  THEN RETURN jsonb_build_object('state','conflict'); END IF;
  id:=gen_random_uuid();revision:=1;
 ELSE
  id:=(request->>'resourceId')::uuid;
  SELECT * INTO before_row FROM organization_access.tenant_role_objects WHERE "Id"=id AND "TenantId"=target AND "Kind"=kind FOR UPDATE;
  IF NOT FOUND OR before_row."Data"->>'membershipId' IS DISTINCT FROM request->>'membershipId'
   OR before_row."Data"->>'roleId' IS DISTINCT FROM request->>'roleId' THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  IF before_row."Revision"<>(request->>'expectedRevision')::integer OR before_row."Revision"=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
  revision:=before_row."Revision"+1;
 END IF;
 after_data:=(request-'commandId'-'expectedRevision')||jsonb_build_object('resourceId',id,'tenantId',target,'revision',revision);
 INSERT INTO organization_access.tenant_role_objects("Id","TenantId","Kind","Data","Revision") VALUES(id,target,kind,after_data,revision)
 ON CONFLICT("Id") DO UPDATE SET "Data"=excluded."Data","Revision"=excluded."Revision";
 INSERT INTO organization_access.tenant_role_audit("CommandId","ActorId","BindingHash","Authority","TenantId","ResourceId","Request","Before","After","Outcome")
 VALUES((request->>'commandId')::uuid,actor,actor_hash,authority,target,id,request,coalesce(before_row."Data",'{}'::jsonb),after_data,'applied');
 RETURN jsonb_build_object('state','applied','snapshot',after_data);
END $$;
REVOKE ALL ON FUNCTION organization_access.apply_tenant_role(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";

