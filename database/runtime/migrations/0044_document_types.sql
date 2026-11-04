-- MVP06/#145: company-owned definitions, not a document or stock writer.
-- 0001-0043 remain published/immutable. No business data or implicit grants.
CREATE SCHEMA document_types;
CREATE TABLE document_types.definitions (
 "Id" uuid PRIMARY KEY CHECK ("Id"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),
 UNIQUE ("TenantId","LegalEntityId","Id"),
 FOREIGN KEY ("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId")
);
CREATE TABLE document_types.versions (
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "DocumentTypeId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),
 "Label" text NOT NULL CHECK (length("Label") BETWEEN 1 AND 100 AND length(btrim("Label"))>0 AND "Label" !~ '[[:cntrl:]]'),
 "Effect" text NOT NULL CHECK ("Effect" IN ('Load','Unload','Transfer','None')),
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY ("TenantId","LegalEntityId","DocumentTypeId","Revision"),
 FOREIGN KEY ("TenantId","LegalEntityId","DocumentTypeId") REFERENCES document_types.definitions("TenantId","LegalEntityId","Id")
);
ALTER TABLE document_types.definitions ADD CONSTRAINT exact_current_version
 FOREIGN KEY ("TenantId","LegalEntityId","Id","Revision") REFERENCES document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision")
 DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE document_types.command_audit (
 "CommandId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "Request" jsonb NOT NULL,
 "Before" jsonb NOT NULL,
 "After" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['definitions','versions','command_audit'] LOOP
  EXECUTE format('ALTER TABLE document_types.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE document_types.%I FORCE ROW LEVEL SECURITY',t);
  -- Owner-only functions establish verified tenant/company context. Audit owner
  -- can detect an already-used command across scopes but never returns its data.
  IF t='command_audit' THEN
   EXECUTE format('CREATE POLICY private_owner ON document_types.%I TO CURRENT_USER USING(true) WITH CHECK(true)',t);
  ELSE
   EXECUTE format('CREATE POLICY private_owner ON document_types.%I TO CURRENT_USER USING ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "LegalEntityId"::text=current_setting(''app.legal_entity_id'',true))',t);
  END IF;
 END LOOP;
END $$;
CREATE TRIGGER immutable_versions BEFORE UPDATE OR DELETE OR TRUNCATE ON document_types.versions
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
CREATE TRIGGER immutable_command_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON document_types.command_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON ALL TABLES IN SCHEMA document_types FROM PUBLIC, :"app_user";
REVOKE ALL ON SCHEMA document_types FROM PUBLIC;
GRANT USAGE ON SCHEMA document_types TO :"app_user";

CREATE FUNCTION organization_access.document_type_permission(action_name text, company uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR company IS NULL OR action_name NOT IN ('document-types.read','document-types.create','document-types.edit')
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
REVOKE ALL ON FUNCTION organization_access.document_type_permission(text,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_document_types;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_document_types(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb;
BEGIN
 result:=organization_access.read_tenant_roles_before_document_types(target);
 IF result->>'state'='ok' AND result ? 'permissions' THEN
  result:=jsonb_set(result,'{actions}',(result->'actions')||jsonb_build_array('document-types.read','document-types.create','document-types.edit'));
 END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

CREATE FUNCTION document_types.snapshot(record_id uuid, revision_number integer) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog,document_types AS $$
 SELECT jsonb_build_object('id',"DocumentTypeId",'legalEntityId',"LegalEntityId",'revision',"Revision",'label',"Label",'effect',"Effect",'occurredAt',"OccurredAt")
 FROM document_types.versions WHERE "DocumentTypeId"=record_id AND "Revision"=revision_number
 AND "TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true)
$$;
REVOKE ALL ON FUNCTION document_types.snapshot(uuid,integer) FROM PUBLIC, :"app_user";

CREATE FUNCTION document_types.read(company uuid, search_text text, after_id uuid, record_id uuid, revision_number integer, before_revision integer) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,document_types,organization_access AS $$
DECLARE target uuid; companies jsonb; items jsonb:='[]'::jsonb; detail jsonb; history jsonb:='[]'::jsonb; selected jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF search_text IS NOT NULL AND (length(search_text)>200 OR search_text ~ '[[:cntrl:]]')
 OR (revision_number IS NOT NULL AND (record_id IS NULL OR revision_number<1))
 OR (before_revision IS NOT NULL AND (record_id IS NULL OR before_revision<1))
 OR (company IS NULL AND (record_id IS NOT NULL OR after_id IS NOT NULL OR search_text IS NOT NULL))
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 -- No all-directory fallback: names originate only from actual current read rights.
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',le."Id",'name',le."Name") ORDER BY le."Name",le."Id"),'[]'::jsonb)
 INTO companies FROM organization_access.legal_entities le
 WHERE le."TenantId"=target AND organization_access.document_type_permission('document-types.read',le."Id");
 IF company IS NULL THEN
  IF companies='[]'::jsonb THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 ELSE
  IF NOT organization_access.document_type_permission('document-types.read',company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  PERFORM set_config('app.legal_entity_id',company::text,true);
  SELECT coalesce(jsonb_agg(document_types.snapshot(x."Id",x."Revision") ORDER BY x."Id"),'[]'::jsonb) INTO items FROM
   (SELECT d."Id",d."Revision" FROM document_types.definitions d
    JOIN document_types.versions v ON (v."TenantId",v."LegalEntityId",v."DocumentTypeId",v."Revision")=(d."TenantId",d."LegalEntityId",d."Id",d."Revision")
    WHERE d."TenantId"=target AND d."LegalEntityId"=company AND (after_id IS NULL OR d."Id">after_id)
    AND (search_text IS NULL OR strpos(lower(v."Label"),lower(search_text))>0) ORDER BY d."Id" LIMIT 21) x;
  IF record_id IS NOT NULL THEN
   SELECT document_types.snapshot(d."Id",d."Revision") INTO detail FROM document_types.definitions d
    WHERE d."TenantId"=target AND d."LegalEntityId"=company AND d."Id"=record_id;
   IF detail IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
   selected:=document_types.snapshot(record_id,coalesce(revision_number,(detail->>'revision')::integer));
   IF selected IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
   SELECT coalesce(jsonb_agg(document_types.snapshot(record_id,x."Revision") ORDER BY x."Revision" DESC),'[]'::jsonb) INTO history FROM
    (SELECT "Revision" FROM document_types.versions WHERE "TenantId"=target AND "LegalEntityId"=company AND "DocumentTypeId"=record_id
     AND (before_revision IS NULL OR "Revision"<before_revision) ORDER BY "Revision" DESC LIMIT 21) x;
  END IF;
 END IF;
 RETURN jsonb_build_object('state','ready','companies',companies,'selectedCompanyId',company,'items',items,'detail',detail,'history',history,'selectedVersion',selected,
 'canCreate',company IS NOT NULL AND organization_access.document_type_permission('document-types.create',company),
 'canEdit',company IS NOT NULL AND organization_access.document_type_permission('document-types.edit',company));
END $$;
REVOKE ALL ON FUNCTION document_types.read(uuid,text,uuid,uuid,integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_types.read(uuid,text,uuid,uuid,integer,integer) TO :"app_user";

CREATE FUNCTION document_types.command(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,document_types,organization_access AS $$
DECLARE target uuid; member_id uuid; binding_hash bytea; command_id uuid; record_id uuid; company uuid;
 operation text; key text; revision_now integer; previous document_types.command_audit; row_before jsonb; row_after jsonb;
 keys text[]:=ARRAY['commandId','operation','legalEntityId','documentTypeId','expectedRevision','label','effect'];
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& keys OR (SELECT count(*) FROM jsonb_object_keys(request))<>cardinality(keys) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF jsonb_typeof(request->'operation') IS DISTINCT FROM 'string' OR request->>'operation' NOT IN ('create','edit')
 OR jsonb_typeof(request->'effect') IS DISTINCT FROM 'string' OR request->>'effect' NOT IN ('Load','Unload','Transfer','None')
 OR jsonb_typeof(request->'label') IS DISTINCT FROM 'string' OR length(request->>'label') NOT BETWEEN 1 AND 100
 OR length(btrim(request->>'label'))=0 OR request->>'label' ~ '[[:cntrl:]]' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 FOREACH key IN ARRAY ARRAY['commandId','legalEntityId','documentTypeId'] LOOP
  IF operation='create' AND key='documentTypeId' AND request->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number' OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483647 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF operation='create' AND (request->'documentTypeId'<>'null'::jsonb OR request->>'expectedRevision'<>'0')
 OR operation='edit' AND request->>'expectedRevision'='0' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 company:=(request->>'legalEntityId')::uuid;
 IF NOT organization_access.document_type_permission('document-types.read',company)
 OR NOT organization_access.document_type_permission('document-types.'||operation,company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 command_id:=(request->>'commandId')::uuid; record_id:=(request->>'documentTypeId')::uuid;
 binding_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 -- Current scope and binding rechecked before even historical replay lookup.
 SELECT * INTO previous FROM document_types.command_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."LegalEntityId"=company AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=binding_hash AND previous."Request"=request
  THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF operation='create' THEN
  record_id:=gen_random_uuid(); revision_now:=0; row_before:='{}'::jsonb;
 ELSE
  SELECT "Revision" INTO revision_now FROM document_types.definitions WHERE "Id"=record_id AND "TenantId"=target AND "LegalEntityId"=company FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  row_before:=document_types.snapshot(record_id,revision_now);
 END IF;
 IF revision_now<>(request->>'expectedRevision')::integer OR revision_now=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF operation='create' THEN
  INSERT INTO document_types.definitions VALUES(record_id,target,company,1);
 ELSE
  UPDATE document_types.definitions SET "Revision"=revision_now+1 WHERE "Id"=record_id AND "TenantId"=target AND "LegalEntityId"=company;
 END IF;
 INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect")
 VALUES(target,company,record_id,revision_now+1,btrim(request->>'label'),request->>'effect');
 row_after:=document_types.snapshot(record_id,revision_now+1);
 INSERT INTO document_types.command_audit("CommandId","TenantId","LegalEntityId","ActorMembershipId","BindingHash","Request","Before","After")
 VALUES(command_id,target,company,member_id,binding_hash,request,row_before,row_after);
 RETURN jsonb_build_object('state','applied','snapshot',row_after);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION document_types.command(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_types.command(jsonb) TO :"app_user";

-- Preserve every historical finite action/scope and add only COMPANY actions.
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
  ELSIF request->>'action' IN ('counterparties.extensions.read','counterparties.extensions.write','document-types.read','document-types.create','document-types.edit') THEN
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
