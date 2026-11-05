-- MVP08/#147 — D100/D101. Append only; published 0001–0045 untouched.
-- No seed data, no new physical reservation, no universal workflow engine.
CREATE TABLE document_types.passages (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL,
 "SourceTypeId" uuid NOT NULL, "DestinationTypeId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),
 PRIMARY KEY("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId"),
 FOREIGN KEY("TenantId","LegalEntityId","SourceTypeId") REFERENCES document_types.definitions("TenantId","LegalEntityId","Id"),
 FOREIGN KEY("TenantId","LegalEntityId","DestinationTypeId") REFERENCES document_types.definitions("TenantId","LegalEntityId","Id")
);
CREATE TABLE document_types.passage_versions (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL,
 "SourceTypeId" uuid NOT NULL, "DestinationTypeId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0), "Enabled" boolean NOT NULL,
 "AllowCrossSite" boolean NOT NULL DEFAULT false, "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId","Revision"),
 FOREIGN KEY("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId") REFERENCES document_types.passages
);
ALTER TABLE document_types.passages ADD CONSTRAINT exact_passage_version FOREIGN KEY("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId","Revision") REFERENCES document_types.passage_versions DEFERRABLE INITIALLY DEFERRED;
CREATE TRIGGER immutable_fact BEFORE UPDATE OR DELETE OR TRUNCATE ON document_types.passage_versions FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
CREATE TABLE documents.origins (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "DocumentId" uuid NOT NULL, "LineId" uuid NOT NULL,
 "SourceDocumentId" uuid NOT NULL, "SourceLineId" uuid NOT NULL, "SourceTypeId" uuid NOT NULL, "DestinationTypeId" uuid NOT NULL,
 "Quantity" numeric(24,6) NOT NULL CHECK ("Quantity">0), "SourceSnapshot" jsonb NOT NULL, "Rule" jsonb NOT NULL,
 PRIMARY KEY("TenantId","LegalEntityId","DocumentId","LineId","SourceDocumentId","SourceLineId"),
 FOREIGN KEY("TenantId","LegalEntityId","DocumentId","LineId") REFERENCES documents.lines DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY("TenantId","LegalEntityId","SourceDocumentId","SourceLineId") REFERENCES documents.lines,
 FOREIGN KEY("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId") REFERENCES document_types.passages,
 CHECK("DocumentId"<>"SourceDocumentId")
);
CREATE INDEX origins_capacity ON documents.origins("TenantId","LegalEntityId","SourceDocumentId","SourceLineId","DestinationTypeId");
CREATE TRIGGER protect_confirmed BEFORE INSERT OR UPDATE OR DELETE ON documents.origins FOR EACH ROW EXECUTE FUNCTION documents.protect_confirmed();
DO $$ DECLARE entry text; schema_name text; table_name text; BEGIN
 FOREACH entry IN ARRAY ARRAY['document_types.passages','document_types.passage_versions','documents.origins'] LOOP
  schema_name:=split_part(entry,'.',1);table_name:=split_part(entry,'.',2);
  EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',schema_name,table_name);
  EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY',schema_name,table_name);
  EXECUTE format('CREATE POLICY private_owner ON %I.%I TO CURRENT_USER USING ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true))',schema_name,table_name);
 END LOOP;
END $$;

CREATE FUNCTION document_types.passage(source_type uuid,destination_type uuid) RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,document_types AS $$
 SELECT jsonb_build_object('sourceTypeId',p."SourceTypeId",'destinationTypeId',p."DestinationTypeId",'revision',p."Revision",'enabled',v."Enabled",'allowCrossSite',v."AllowCrossSite",'occurredAt',v."OccurredAt")
 FROM document_types.passages p JOIN document_types.passage_versions v USING("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId","Revision")
 WHERE p."TenantId"::text=current_setting('app.tenant_id',true) AND p."LegalEntityId"::text=current_setting('app.legal_entity_id',true) AND p."SourceTypeId"=source_type AND p."DestinationTypeId"=destination_type
$$;
CREATE FUNCTION document_types.path_command(request jsonb) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,document_types,documents,organization_access AS $$
DECLARE target uuid; member_id uuid; company uuid; source_type uuid; destination_type uuid; command_id uuid; revision_now integer:=0; key text; before_row jsonb; after_row jsonb; previous document_types.command_audit; actor_hash bytea;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 PERFORM "Singleton" FROM documents.snapshot_fence WHERE "Singleton" FOR SHARE;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' OR NOT request ?& ARRAY['commandId','operation','legalEntityId','sourceTypeId','destinationTypeId','expectedRevision','enabled','allowCrossSite'] OR (SELECT count(*) FROM jsonb_object_keys(request))<>8 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','legalEntityId','sourceTypeId','destinationTypeId'] LOOP
  IF NOT documents.valid_uuid(request->key) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF request->>'operation' IS DISTINCT FROM 'path' OR NOT documents.valid_revision(request->'expectedRevision') OR request->>'expectedRevision'='2147483647' OR jsonb_typeof(request->'enabled') IS DISTINCT FROM 'boolean' OR jsonb_typeof(request->'allowCrossSite') IS DISTINCT FROM 'boolean' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 company:=(request->>'legalEntityId')::uuid; source_type:=(request->>'sourceTypeId')::uuid;destination_type:=(request->>'destinationTypeId')::uuid;command_id:=(request->>'commandId')::uuid;
 IF NOT organization_access.document_type_permission('document-types.read',company) OR NOT organization_access.document_type_permission('document-types.paths.manage',company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 actor_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 SELECT * INTO previous FROM document_types.command_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."LegalEntityId"=company AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=actor_hash AND previous."Request"=request THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF document_types.for_document(source_type) IS NULL OR document_types.for_document(destination_type) IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT "Revision" INTO revision_now FROM document_types.passages WHERE "TenantId"=target AND "LegalEntityId"=company AND "SourceTypeId"=source_type AND "DestinationTypeId"=destination_type FOR UPDATE;
 revision_now:=coalesce(revision_now,0);before_row:=coalesce(document_types.passage(source_type,destination_type),'{}'::jsonb);
 IF revision_now<>(request->>'expectedRevision')::integer THEN RETURN jsonb_build_object('state','config_changed'); END IF;
 INSERT INTO document_types.passages VALUES(target,company,source_type,destination_type,revision_now+1) ON CONFLICT("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId") DO UPDATE SET "Revision"=excluded."Revision";
 INSERT INTO document_types.passage_versions("TenantId","LegalEntityId","SourceTypeId","DestinationTypeId","Revision","Enabled","AllowCrossSite") VALUES(target,company,source_type,destination_type,revision_now+1,(request->>'enabled')::boolean,(request->>'allowCrossSite')::boolean);
 after_row:=document_types.passage(source_type,destination_type);
 INSERT INTO document_types.command_audit("CommandId","TenantId","LegalEntityId","ActorMembershipId","BindingHash","Request","Before","After") VALUES(command_id,target,company,member_id,actor_hash,request,before_row,after_row);
 UPDATE documents.snapshot_fence SET "Token"=NOT "Token" WHERE "Singleton";
 RETURN jsonb_build_object('state','applied','snapshot',after_row);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict'); END $$;

CREATE FUNCTION documents.origin_snapshot(record_id uuid,line_id uuid) RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,documents AS $$
 SELECT coalesce(jsonb_agg(CASE WHEN organization_access.document_permission('documents.read',o."LegalEntityId",(o."SourceSnapshot"->>'siteId')::uuid,NULL) THEN jsonb_build_object('sourceDocumentId',o."SourceDocumentId",'sourceLineId',o."SourceLineId",'quantity',o."Quantity"::text,'expectedPathRevision',(o."Rule"->>'revision')::integer,'source',o."SourceSnapshot",'rule',o."Rule",'canReadSource',organization_access.document_permission('documents.read',o."LegalEntityId",(o."SourceSnapshot"->>'siteId')::uuid,NULL)) ELSE jsonb_build_object('quantity',o."Quantity"::text,'restricted',true) END ORDER BY o."SourceDocumentId",o."SourceLineId"),'[]'::jsonb)
 FROM documents.origins o WHERE o."TenantId"::text=current_setting('app.tenant_id',true) AND o."LegalEntityId"::text=current_setting('app.legal_entity_id',true) AND o."DocumentId"=record_id AND o."LineId"=line_id
$$;

-- Validate a complete proposed plan without reserving capacity. Source snapshots
-- are server-owned; only a Confirmed line can supply an accepted snapshot.
CREATE FUNCTION documents.prepare_plan(input_lines jsonb,destination_type uuid,destination_site uuid) RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,documents AS $$
DECLARE line jsonb; origin jsonb; result jsonb:='[]'; normalized_origins jsonb; src documents.lines; source_header documents.headers; rule jsonb; first_source jsonb; source_fact jsonb; quantity_value numeric; total numeric; count_origins integer:=0;
BEGIN
 FOR line IN SELECT value FROM jsonb_array_elements(input_lines) LOOP
  IF jsonb_typeof(line) IS DISTINCT FROM 'object' OR NOT line ?& ARRAY['id','itemId','catalogRevision','quantity','warehouseId','destinationWarehouseId','origins'] OR (SELECT count(*) FROM jsonb_object_keys(line))<>7 OR jsonb_typeof(line->'origins') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  normalized_origins:='[]';first_source:=NULL;total:=0;
  FOR origin IN SELECT value FROM jsonb_array_elements(line->'origins') LOOP
   count_origins:=count_origins+1;
   IF count_origins>200 OR jsonb_typeof(origin) IS DISTINCT FROM 'object' OR NOT origin ?& ARRAY['sourceDocumentId','sourceLineId','quantity','expectedPathRevision'] OR (SELECT count(*) FROM jsonb_object_keys(origin))<>4 OR NOT documents.valid_uuid(origin->'sourceDocumentId') OR NOT documents.valid_uuid(origin->'sourceLineId') OR NOT documents.valid_revision(origin->'expectedPathRevision') OR jsonb_typeof(origin->'quantity') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF origin->>'quantity' !~ '^(0|[1-9][0-9]{0,17})(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   quantity_value:=(origin->>'quantity')::numeric;
   IF quantity_value<=0 THEN RETURN jsonb_build_object('state','invalid'); END IF;
   SELECT * INTO source_header FROM documents.headers WHERE "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true) AND "Id"=(origin->>'sourceDocumentId')::uuid;
   IF NOT FOUND OR source_header."State"<>'Confirmed' THEN RETURN jsonb_build_object('state','source_not_confirmed'); END IF;
   IF NOT organization_access.document_permission('documents.read',source_header."LegalEntityId",source_header."SiteId",NULL) OR NOT organization_access.document_permission('documents.develop',source_header."LegalEntityId",source_header."SiteId",NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
   SELECT * INTO src FROM documents.lines WHERE "TenantId"=source_header."TenantId" AND "LegalEntityId"=source_header."LegalEntityId" AND "DocumentId"=source_header."Id" AND "Id"=(origin->>'sourceLineId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
   rule:=document_types.passage(source_header."DocumentTypeId",destination_type);
   IF rule IS NULL OR NOT (rule->>'enabled')::boolean OR (source_header."SiteId"<>destination_site AND NOT (rule->>'allowCrossSite')::boolean) THEN RETURN jsonb_build_object('state','path_forbidden'); END IF;
   IF rule->>'revision'<>origin->>'expectedPathRevision' THEN RETURN jsonb_build_object('state','config_changed'); END IF;
   source_fact:=jsonb_build_object('itemId',src."CatalogItemId",'catalogRevision',src."CatalogVersion",'kind',src."Kind",'label',src."Label");
   IF first_source IS NOT NULL AND first_source<>source_fact THEN RETURN jsonb_build_object('state','incompatible_origins'); END IF;
   first_source:=source_fact;
   IF line->>'itemId'<>src."CatalogItemId"::text OR line->>'catalogRevision'<>src."CatalogVersion"::text THEN RETURN jsonb_build_object('state','incompatible_origins'); END IF;
   total:=total+quantity_value;
   normalized_origins:=normalized_origins||jsonb_build_array(jsonb_build_object('sourceDocumentId',source_header."Id",'sourceLineId',src."Id",'quantity',quantity_value::numeric(24,6)::text,'expectedPathRevision',(rule->>'revision')::integer,'rule',rule,'source',source_fact||jsonb_build_object('siteId',source_header."SiteId",'warehouseId',src."WarehouseId",'destinationWarehouseId',src."DestinationWarehouseId",'sourceQuantity',src."Quantity"::text,'documentTypeId',source_header."DocumentTypeId",'appliedConfiguration',source_header."AppliedConfiguration")));
  END LOOP;
  IF jsonb_array_length(normalized_origins)>0 THEN
   IF total>999999999999999999.999999 THEN RETURN jsonb_build_object('state','quantity_overflow'); END IF;
   IF (SELECT count(*)<>count(DISTINCT (value->>'sourceDocumentId',value->>'sourceLineId')) FROM jsonb_array_elements(normalized_origins)) THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF jsonb_typeof(line->'quantity') IS DISTINCT FROM 'string' OR line->>'quantity' !~ '^(0|[1-9][0-9]{0,17})(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF (line->>'quantity')::numeric<>total THEN RETURN jsonb_build_object('state','origin_quantity_mismatch'); END IF;
  END IF;
  result:=result||jsonb_build_array(jsonb_set(line,'{origins}',normalized_origins));
 END LOOP;
 RETURN jsonb_build_object('state','ready','lines',result);
END $$;

CREATE FUNCTION documents.check_origins(record_id uuid,check_capacity boolean) RETURNS text LANGUAGE plpgsql SET search_path=pg_catalog,documents AS $$
DECLARE origin record; h documents.headers; rule jsonb; used numeric; proposed numeric; source_quantity numeric;
BEGIN
 SELECT * INTO h FROM documents.headers WHERE "Id"=record_id AND "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true);
 -- Ordered stage/source locks follow the owning authorization fence and header.
 FOR origin IN SELECT * FROM documents.origins WHERE "TenantId"=h."TenantId" AND "LegalEntityId"=h."LegalEntityId" AND "DocumentId"=record_id ORDER BY "SourceTypeId","DestinationTypeId","SourceDocumentId","SourceLineId","LineId" LOOP
  IF NOT organization_access.document_permission('documents.read',h."LegalEntityId",(origin."SourceSnapshot"->>'siteId')::uuid,NULL) OR NOT organization_access.document_permission('documents.develop',h."LegalEntityId",(origin."SourceSnapshot"->>'siteId')::uuid,NULL) THEN RETURN 'forbidden'; END IF;
  IF NOT check_capacity THEN CONTINUE; END IF;
  PERFORM 1 FROM document_types.passages WHERE "TenantId"=h."TenantId" AND "LegalEntityId"=h."LegalEntityId" AND "SourceTypeId"=origin."SourceTypeId" AND "DestinationTypeId"=origin."DestinationTypeId" FOR UPDATE;
  PERFORM 1 FROM documents.headers WHERE "TenantId"=h."TenantId" AND "LegalEntityId"=h."LegalEntityId" AND "Id"=origin."SourceDocumentId" AND "State"='Confirmed' FOR SHARE;
  IF NOT FOUND THEN RETURN 'source_not_confirmed'; END IF;
  rule:=document_types.passage(origin."SourceTypeId",h."DocumentTypeId");
  IF rule IS NULL OR NOT (rule->>'enabled')::boolean OR (h."SiteId"<>(origin."SourceSnapshot"->>'siteId')::uuid AND NOT (rule->>'allowCrossSite')::boolean) THEN RETURN 'path_forbidden'; END IF;
  IF rule<>origin."Rule" THEN RETURN 'config_changed'; END IF;
  SELECT "Quantity" INTO source_quantity FROM documents.lines WHERE "TenantId"=h."TenantId" AND "LegalEntityId"=h."LegalEntityId" AND "DocumentId"=origin."SourceDocumentId" AND "Id"=origin."SourceLineId" FOR SHARE;
  SELECT coalesce(sum(o."Quantity"),0) INTO used FROM documents.origins o JOIN documents.headers d ON (d."TenantId",d."LegalEntityId",d."Id")=(o."TenantId",o."LegalEntityId",o."DocumentId") WHERE o."TenantId"=h."TenantId" AND o."LegalEntityId"=h."LegalEntityId" AND o."SourceDocumentId"=origin."SourceDocumentId" AND o."SourceLineId"=origin."SourceLineId" AND o."DestinationTypeId"=origin."DestinationTypeId" AND d."State"='Confirmed';
  SELECT sum("Quantity") INTO proposed FROM documents.origins WHERE "TenantId"=h."TenantId" AND "LegalEntityId"=h."LegalEntityId" AND "DocumentId"=record_id AND "SourceDocumentId"=origin."SourceDocumentId" AND "SourceLineId"=origin."SourceLineId" AND "DestinationTypeId"=origin."DestinationTypeId";
  IF used+proposed>source_quantity THEN RETURN 'insufficient_residual'; END IF;
 END LOOP;
 IF check_capacity AND EXISTS(SELECT 1 FROM documents.lines l JOIN documents.origins o ON (o."TenantId",o."LegalEntityId",o."DocumentId",o."LineId")=(l."TenantId",l."LegalEntityId",l."DocumentId",l."Id") WHERE l."TenantId"=h."TenantId" AND l."LegalEntityId"=h."LegalEntityId" AND l."DocumentId"=record_id GROUP BY l."Id",l."Quantity" HAVING sum(o."Quantity")<>l."Quantity") THEN RETURN 'origin_quantity_mismatch'; END IF;
 RETURN 'ready';
END $$;

REVOKE ALL ON document_types.passages,document_types.passage_versions,documents.origins FROM PUBLIC, :"app_user";

CREATE OR REPLACE FUNCTION organization_access.document_permission(action_name text, company uuid, site uuid, warehouse uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR company IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN false; END IF;
 IF action_name IN ('documents.read','documents.save','documents.confirm','documents.develop') THEN
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
CREATE OR REPLACE FUNCTION organization_access.document_type_permission(action_name text, company uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR company IS NULL OR action_name NOT IN ('document-types.read','document-types.create','document-types.edit','document-types.paths.manage')
 OR NOT organization_access.current_membership_access(target) THEN RETURN false; END IF;
 -- Current assignment/role/permission tuples and the existing snapshot witness
 -- are held in the owning transaction, not a detached access adapter.
 PERFORM 1 FROM organization_access.tenant_role_objects WHERE "TenantId"=target FOR SHARE;
 PERFORM 1 FROM organization_access.legal_entities WHERE "TenantId"=target AND "Id"=company FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 RETURN EXISTS(SELECT 1 FROM organization_access.current_tenant_role_scopes_before_access() s
 JOIN organization_access.tenant_role_objects p ON p."Id"=s."Id" AND p."TenantId"=target AND p."Kind"='permission'
 WHERE s."TenantId"=target AND s."Permission"=action_name AND s."LegalEntityId"=company
 AND s."SiteId" IS NULL AND s."WarehouseId" IS NULL
 AND p."Data" ?& ARRAY['action','legalEntityId','siteId','warehouseId']
 AND p."Data"->'legalEntityId'=to_jsonb(company)
 AND p."Data"->'siteId'='null'::jsonb AND p."Data"->'warehouseId'='null'::jsonb);
END $$;

CREATE OR REPLACE FUNCTION documents.snapshot(record_id uuid) RETURNS jsonb LANGUAGE sql SET search_path=pg_catalog,documents AS $$
 SELECT jsonb_build_object('id',h."Id",'legalEntityId',h."LegalEntityId",'siteId',h."SiteId",'documentTypeId',h."DocumentTypeId",'revision',h."Revision",'state',h."State",'title',h."Title",'appliedConfiguration',h."AppliedConfiguration",'confirmedAt',h."ConfirmedAt",'lines',
 coalesce((SELECT jsonb_agg(jsonb_build_object('id',l."Id",'itemId',l."CatalogItemId",'catalogRevision',l."CatalogVersion",'kind',l."Kind",'label',l."Label",'quantity',l."Quantity"::text,'warehouseId',l."WarehouseId",'destinationWarehouseId',l."DestinationWarehouseId",'origins',documents.origin_snapshot(h."Id",l."Id")) ORDER BY l."Position")
 FROM documents.lines l WHERE (l."TenantId",l."LegalEntityId",l."DocumentId")=(h."TenantId",h."LegalEntityId",h."Id")),'[]'::jsonb))
 FROM documents.headers h WHERE h."Id"=record_id AND h."TenantId"::text=current_setting('app.tenant_id',true) AND h."LegalEntityId"::text=current_setting('app.legal_entity_id',true)
$$;

-- Wire-only canonicalization before replay; current path/capacity are checked
-- only for a new effect, whereas current source authorization precedes replay.
CREATE FUNCTION documents.normalize_plan(input_lines jsonb) RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog,documents AS $$
DECLARE line jsonb; origin jsonb; origins jsonb; result jsonb:='[]'; total_origins integer:=0; source_site uuid; company uuid:=current_setting('app.legal_entity_id')::uuid;
BEGIN
 FOR line IN SELECT value FROM jsonb_array_elements(input_lines) LOOP
  IF jsonb_typeof(line) IS DISTINCT FROM 'object' OR jsonb_typeof(line->'origins') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  origins:='[]';
  FOR origin IN SELECT value FROM jsonb_array_elements(line->'origins') LOOP
   total_origins:=total_origins+1;
   IF total_origins>200 OR jsonb_typeof(origin) IS DISTINCT FROM 'object' OR NOT origin ?& ARRAY['sourceDocumentId','sourceLineId','quantity','expectedPathRevision'] OR (SELECT count(*) FROM jsonb_object_keys(origin))<>4 OR NOT documents.valid_uuid(origin->'sourceDocumentId') OR NOT documents.valid_uuid(origin->'sourceLineId') OR NOT documents.valid_revision(origin->'expectedPathRevision') OR jsonb_typeof(origin->'quantity') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF origin->>'quantity' !~ '^(0|[1-9][0-9]{0,17})(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF (origin->>'quantity')::numeric<=0 THEN RETURN jsonb_build_object('state','invalid'); END IF;
   SELECT "SiteId" INTO source_site FROM documents.headers WHERE "TenantId"::text=current_setting('app.tenant_id') AND "LegalEntityId"=company AND "Id"=(origin->>'sourceDocumentId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
   IF NOT organization_access.document_permission('documents.read',company,source_site,NULL) OR NOT organization_access.document_permission('documents.develop',company,source_site,NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
   IF NOT EXISTS(SELECT 1 FROM documents.headers WHERE "TenantId"::text=current_setting('app.tenant_id') AND "LegalEntityId"=company AND "Id"=(origin->>'sourceDocumentId')::uuid AND "State"='Confirmed') THEN RETURN jsonb_build_object('state','source_not_confirmed'); END IF;
   origins:=origins||jsonb_build_array(jsonb_set(origin,'{quantity}',to_jsonb((origin->>'quantity')::numeric(24,6)::text)));
  END LOOP;
  result:=result||jsonb_build_array(jsonb_set(line,'{origins}',origins));
 END LOOP;
 RETURN jsonb_build_object('state','ready','lines',result);
END $$;
REVOKE ALL ON FUNCTION documents.normalize_plan(jsonb) FROM PUBLIC, :"app_user";

CREATE OR REPLACE FUNCTION documents.command(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,documents,organization_access AS $$
DECLARE target uuid; member_id uuid; binding_hash bytea; command_id uuid; record_id uuid; company uuid; site uuid;
 operation text; key text; keys text[]; previous documents.command_audit; header documents.headers;
 before_row jsonb; after_row jsonb; type_config jsonb; policy_config jsonb; item jsonb; line jsonb; normalized_lines jsonb:='[]'::jsonb;
 plan jsonb; origin jsonb; origin_state text; development boolean:=false;
 effect text; line_position integer:=0; quantity_value numeric; current_balance numeric; outgoing numeric; pool record; instant timestamptz;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 PERFORM "Singleton" FROM documents.snapshot_fence WHERE "Singleton" FOR SHARE;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 development:=operation IN ('develop','develop-save');
 IF development THEN operation:=CASE operation WHEN 'develop' THEN 'create' ELSE 'save' END; END IF;
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
  IF development THEN
   IF NOT organization_access.document_permission('documents.develop',company,site,NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
   IF jsonb_typeof(request->'lines') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF jsonb_array_length(request->'lines') NOT BETWEEN 1 AND 200 THEN RETURN jsonb_build_object('state','invalid'); END IF;
   plan:=documents.normalize_plan(request->'lines');
   IF plan->>'state'<>'ready' THEN RETURN plan; END IF;
  END IF;
  IF jsonb_typeof(request->'title') IS DISTINCT FROM 'string' OR length(request->>'title') NOT BETWEEN 1 AND 100 OR btrim(request->>'title')='' OR request->>'title' ~ '[[:cntrl:]]' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF jsonb_typeof(request->'lines') IS DISTINCT FROM 'array' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF jsonb_array_length(request->'lines') NOT BETWEEN 1 AND 200 THEN RETURN jsonb_build_object('state','invalid'); END IF;
  FOR line IN SELECT value FROM jsonb_array_elements(request->'lines') LOOP
   IF jsonb_typeof(line) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
   IF NOT line ?& ARRAY['id','itemId','catalogRevision','quantity','warehouseId','destinationWarehouseId'] OR (SELECT count(*) FROM jsonb_object_keys(line))<>(CASE WHEN development THEN 7 ELSE 6 END) OR (development AND NOT line ? 'origins') THEN RETURN jsonb_build_object('state','invalid'); END IF;
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
  IF development THEN
   normalized_lines:='[]'::jsonb;
   FOR line IN SELECT value FROM jsonb_array_elements(plan->'lines') LOOP
    normalized_lines:=normalized_lines||jsonb_build_array(jsonb_set(jsonb_set(line,'{quantity}',to_jsonb((line->>'quantity')::numeric(24,6)::text)),'{origins}',coalesce((SELECT jsonb_agg(value-'source'-'rule' ORDER BY value->>'sourceDocumentId',value->>'sourceLineId') FROM jsonb_array_elements(line->'origins')),'[]'::jsonb)));
   END LOOP;
  END IF;
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
 IF operation='confirm' OR (development AND operation='save') THEN
  origin_state:=documents.check_origins(record_id,false);
  IF origin_state<>'ready' THEN RETURN jsonb_build_object('state',origin_state); END IF;
 END IF;
 binding_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 SELECT * INTO previous FROM documents.command_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."LegalEntityId"=company AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=binding_hash AND previous."Request"=request THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF development THEN
  plan:=documents.prepare_plan(normalized_lines,(request->>'documentTypeId')::uuid,site);
  IF plan->>'state'<>'ready' THEN RETURN plan; END IF;
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
   IF NOT development AND operation='save' AND EXISTS(SELECT 1 FROM documents.origins WHERE "TenantId"=target AND "LegalEntityId"=company AND "DocumentId"=record_id) THEN RETURN jsonb_build_object('state','development_plan_required'); END IF;
   IF development AND operation='save' THEN
    origin_state:=documents.check_origins(record_id,false);
    IF origin_state<>'ready' THEN RETURN jsonb_build_object('state',origin_state); END IF;
    IF EXISTS(SELECT 1 FROM documents.origins o JOIN jsonb_array_elements(normalized_lines) n ON n->>'id'=o."LineId"::text WHERE o."TenantId"=target AND o."LegalEntityId"=company AND o."DocumentId"=record_id AND jsonb_array_length(n->'origins')=0) THEN RETURN jsonb_build_object('state','origin_quantity_mismatch'); END IF;
   END IF;
   before_row:=documents.snapshot(record_id);
  END IF;
  type_config:=document_types.for_document(CASE WHEN operation='confirm' THEN header."DocumentTypeId" ELSE (request->>'documentTypeId')::uuid END);
  IF type_config IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
  IF type_config->>'revision'<>request->>'expectedTypeRevision' OR (operation='confirm' AND policy_config->>'revision'<>request->>'expectedPolicyRevision') THEN RETURN jsonb_build_object('state','config_changed'); END IF;
  effect:=type_config->>'effect';
  IF operation IN ('create','save') THEN
   -- Validate and lock each canonical item before changing any owned row.
   FOR line IN SELECT value FROM jsonb_array_elements(normalized_lines) LOOP
    IF development THEN
     SELECT value INTO origin FROM jsonb_array_elements(plan->'lines') WHERE value->>'id'=line->>'id';
     item:=origin->'origins'->0->'source';
    ELSE item:=NULL; END IF;
    IF item IS NULL THEN item:=catalog.document_item((line->>'itemId')::uuid,(line->>'catalogRevision')::integer); END IF;
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
    DELETE FROM documents.origins WHERE "TenantId"=target AND "LegalEntityId"=company AND "DocumentId"=record_id;
    DELETE FROM documents.lines WHERE "TenantId"=target AND "LegalEntityId"=company AND "DocumentId"=record_id;
    UPDATE documents.headers SET "DocumentTypeId"=(request->>'documentTypeId')::uuid,"Title"=request->>'title',"Revision"="Revision"+1 WHERE "TenantId"=target AND "LegalEntityId"=company AND "Id"=record_id;
   END IF;
   FOR line IN SELECT value FROM jsonb_array_elements(normalized_lines) LOOP
    line_position:=line_position+1; IF development THEN
     SELECT value INTO origin FROM jsonb_array_elements(plan->'lines') WHERE value->>'id'=line->>'id';
     item:=origin->'origins'->0->'source';
    ELSE item:=NULL; END IF;
    IF item IS NULL THEN item:=catalog.document_item((line->>'itemId')::uuid,(line->>'catalogRevision')::integer); END IF;
    INSERT INTO documents.lines VALUES(target,company,record_id,(line->>'id')::uuid,line_position,(line->>'itemId')::uuid,(line->>'catalogRevision')::integer,item->>'kind',item->>'label',(line->>'quantity')::numeric,(line->>'warehouseId')::uuid,(line->>'destinationWarehouseId')::uuid);
   END LOOP;
   IF development THEN
    FOR line IN SELECT value FROM jsonb_array_elements(plan->'lines') LOOP
     FOR origin IN SELECT value FROM jsonb_array_elements(line->'origins') LOOP
      INSERT INTO documents.origins VALUES(target,company,record_id,(line->>'id')::uuid,(origin->>'sourceDocumentId')::uuid,(origin->>'sourceLineId')::uuid,(origin->'source'->>'documentTypeId')::uuid,(request->>'documentTypeId')::uuid,(origin->>'quantity')::numeric,origin->'source',origin->'rule');
     END LOOP;
    END LOOP;
   END IF;
  ELSE
   origin_state:=documents.check_origins(record_id,true);
   IF origin_state<>'ready' THEN RETURN jsonb_build_object('state',origin_state); END IF;
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
  ELSIF request->>'action' IN ('documents.read','documents.save','documents.confirm','documents.develop') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.sites WHERE "TenantId"=target AND "Id"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('inventory.document-effects.apply','inventory.quantities.read') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'='null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "Id"=(request->>'warehouseId')::uuid AND "SiteId"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('counterparties.extensions.read','counterparties.extensions.write','document-types.read','document-types.create','document-types.edit','inventory.policy.read','inventory.policy.manage','document-types.paths.manage') THEN
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


ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_development;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_development(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; BEGIN
 result:=organization_access.read_tenant_roles_before_development(target);
 IF result->>'state'='ok' AND result ? 'permissions' THEN result:=jsonb_set(result,'{actions}',(result->'actions')||jsonb_build_array('documents.develop','document-types.paths.manage')); END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";
ALTER FUNCTION document_types.command(jsonb) RENAME TO command_before_development;
REVOKE ALL ON FUNCTION document_types.command_before_development(jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION document_types.command(request jsonb) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,document_types AS $$
BEGIN
 IF request->>'operation'='path' THEN RETURN document_types.path_command(request); END IF;
 RETURN document_types.command_before_development(request);
END $$;
REVOKE ALL ON FUNCTION document_types.command(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_types.command(jsonb) TO :"app_user";
REVOKE ALL ON FUNCTION document_types.path_command(jsonb),document_types.passage(uuid,uuid),documents.origin_snapshot(uuid,uuid),documents.prepare_plan(jsonb,uuid,uuid),documents.check_origins(uuid,boolean) FROM PUBLIC, :"app_user";

CREATE OR REPLACE FUNCTION documents.read(company uuid,site uuid,warehouse uuid,record_id uuid,search_text text,after_id uuid,selection text,selection_after uuid,ledger_after uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,documents,organization_access AS $$
DECLARE target uuid; companies jsonb; sites jsonb:='[]'; warehouses jsonb:='[]'; items jsonb:='[]'; detail jsonb; ledger jsonb:='[]'; balances jsonb:='[]'; types jsonb:='[]'; catalog_items jsonb:='[]'; policy_config jsonb; history jsonb:='[]'; sources jsonb:='[]'; paths jsonb:='[]'; stages jsonb:='[]';
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 PERFORM "Singleton" FROM documents.snapshot_fence WHERE "Singleton" FOR SHARE;
 IF search_text IS NOT NULL AND (length(search_text)>200 OR search_text ~ '[[:cntrl:]]') OR selection IS NOT NULL AND selection NOT IN ('catalog','types','sources') OR company IS NULL AND (site IS NOT NULL OR warehouse IS NOT NULL OR record_id IS NOT NULL OR search_text IS NOT NULL OR after_id IS NOT NULL OR selection IS NOT NULL OR selection_after IS NOT NULL OR ledger_after IS NOT NULL) OR site IS NULL AND (warehouse IS NOT NULL OR record_id IS NOT NULL OR selection IS NOT NULL OR search_text IS NOT NULL OR after_id IS NOT NULL OR selection_after IS NOT NULL OR ledger_after IS NOT NULL) OR selection_after IS NOT NULL AND selection IS NULL OR ledger_after IS NOT NULL AND record_id IS NULL AND warehouse IS NULL THEN RETURN jsonb_build_object('state','invalid'); END IF;
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
   SELECT coalesce(jsonb_agg(document_types.passage(p."SourceTypeId",p."DestinationTypeId") ORDER BY p."SourceTypeId",p."DestinationTypeId"),'[]'::jsonb) INTO paths FROM document_types.passages p WHERE p."TenantId"=target AND p."LegalEntityId"=company;
   IF selection='sources' THEN
    SELECT coalesce(jsonb_agg(documents.snapshot(x."Id") ORDER BY x."Id"),'[]'::jsonb) INTO sources FROM (SELECT "Id" FROM documents.headers WHERE "TenantId"=target AND "LegalEntityId"=company AND "State"='Confirmed' AND organization_access.document_permission('documents.read',company,"SiteId",NULL) AND organization_access.document_permission('documents.develop',company,"SiteId",NULL) AND (search_text IS NULL OR strpos(lower("Title"),lower(search_text))>0) AND (selection_after IS NULL OR "Id">selection_after) ORDER BY "Id" LIMIT 21) x;
   ELSIF selection='catalog' THEN catalog_items:=catalog.document_choices(search_text,selection_after);
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
    IF detail->>'state'='Confirmed' THEN
     SELECT coalesce(jsonb_agg(jsonb_build_object('lineId',l."Id",'destinationTypeId',p."DestinationTypeId",'sourceQuantity',l."Quantity"::text,'committed',coalesce(a.committed,0)::text,'plannedNotReserved',coalesce(a.planned,0)::text,'residual',(l."Quantity"-coalesce(a.committed,0))::text,'rule',document_types.passage(p."SourceTypeId",p."DestinationTypeId")) ORDER BY l."Position",p."DestinationTypeId"),'[]'::jsonb) INTO stages
     FROM documents.lines l JOIN document_types.passages p ON p."TenantId"=target AND p."LegalEntityId"=company AND p."SourceTypeId"=(detail->>'documentTypeId')::uuid
     LEFT JOIN LATERAL (SELECT sum(o."Quantity") FILTER(WHERE h."State"='Confirmed') committed,sum(o."Quantity") FILTER(WHERE h."State"='Draft') planned FROM documents.origins o JOIN documents.headers h ON (h."TenantId",h."LegalEntityId",h."Id")=(o."TenantId",o."LegalEntityId",o."DocumentId") WHERE o."TenantId"=target AND o."LegalEntityId"=company AND o."SourceDocumentId"=record_id AND o."SourceLineId"=l."Id" AND o."DestinationTypeId"=p."DestinationTypeId") a ON true
     WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."DocumentId"=record_id;
    END IF;
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
 RETURN jsonb_build_object('state','ready','sources',sources,'paths',paths,'stages',stages,'canDevelop',company IS NOT NULL AND site IS NOT NULL AND organization_access.document_permission('documents.develop',company,site,NULL),'companies',companies,'sites',sites,'warehouses',warehouses,'items',items,'detail',detail,'types',types,'catalog',catalog_items,'policy',policy_config,'policyHistory',history,'balances',balances,'ledger',ledger,
 'canSave',company IS NOT NULL AND site IS NOT NULL AND organization_access.document_permission('documents.read',company,site,NULL) AND organization_access.document_permission('documents.save',company,site,NULL),
 'canConfirm',company IS NOT NULL AND site IS NOT NULL AND documents.check_origins(record_id,false)='ready' AND organization_access.document_permission('documents.read',company,site,NULL) AND organization_access.document_permission('documents.confirm',company,site,NULL) AND NOT EXISTS(SELECT 1 FROM documents.lines l CROSS JOIN LATERAL unnest(ARRAY[l."WarehouseId",l."DestinationWarehouseId"]) w WHERE l."TenantId"=target AND l."LegalEntityId"=company AND l."DocumentId"=record_id AND w IS NOT NULL AND NOT organization_access.document_permission('inventory.document-effects.apply',company,site,w)),
 'canManagePolicy',company IS NOT NULL AND organization_access.document_permission('inventory.policy.read',company,NULL,NULL) AND organization_access.document_permission('inventory.policy.manage',company,NULL,NULL));
END $$;

ALTER FUNCTION document_types.read(uuid,text,uuid,uuid,integer,integer) RENAME TO read_before_development;
REVOKE ALL ON FUNCTION document_types.read_before_development(uuid,text,uuid,uuid,integer,integer) FROM PUBLIC, :"app_user";
CREATE FUNCTION document_types.read(company uuid,search_text text,after_id uuid,record_id uuid,revision_number integer,before_revision integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,document_types AS $$
DECLARE result jsonb; paths jsonb; BEGIN
 result:=document_types.read_before_development(company,search_text,after_id,record_id,revision_number,before_revision);
 IF result->>'state'='ready' AND company IS NOT NULL THEN
  SELECT coalesce(jsonb_agg(document_types.passage(p."SourceTypeId",p."DestinationTypeId") ORDER BY p."SourceTypeId",p."DestinationTypeId"),'[]') INTO paths FROM document_types.passages p WHERE p."TenantId"::text=current_setting('app.tenant_id',true) AND p."LegalEntityId"=company AND (record_id IS NULL OR p."SourceTypeId"=record_id);
  result:=result||jsonb_build_object('paths',paths,'canManagePaths',organization_access.document_type_permission('document-types.paths.manage',company));
 END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION document_types.read(uuid,text,uuid,uuid,integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_types.read(uuid,text,uuid,uuid,integer,integer) TO :"app_user";
