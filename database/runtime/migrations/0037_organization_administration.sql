-- MVP-02.b finite metadata operations. No membership or business policy changes.
ALTER TABLE organization_access.tenants ADD COLUMN "Revision" integer NOT NULL DEFAULT 1 CHECK ("Revision">0);
ALTER TABLE organization_access.legal_entities ADD COLUMN "Revision" integer NOT NULL DEFAULT 1 CHECK ("Revision">0);
ALTER TABLE organization_access.sites ADD COLUMN "Revision" integer NOT NULL DEFAULT 1 CHECK ("Revision">0);
ALTER TABLE organization_access.warehouses ADD COLUMN "Revision" integer NOT NULL DEFAULT 1 CHECK ("Revision">0);

-- Invoker helper only; definer entry points hold this lock through caller commit.
CREATE FUNCTION organization_access.lock_organization_actor() RETURNS boolean
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM 1 FROM organization_access.external_identity_bindings b
 JOIN organization_access.platform_authority a ON a."InternalIdentityId"=b."InternalIdentityId"
  AND a."Issuer"=b."Issuer" AND a."Subject"=b."Subject"
 WHERE a."Active" AND a."InternalIdentityId"::text=current_setting('app.identity_subject',true)
  AND a."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
  AND a."Subject"=current_setting('app.external_subject',true) COLLATE "C"
 FOR SHARE OF b;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION organization_access.lock_organization_actor() FROM PUBLIC, :"app_user";

-- Only metadata SELECT, only the nonprivileged function owner, only active exact authority.
CREATE POLICY platform_tenant_directory ON organization_access.tenants FOR SELECT TO CURRENT_USER USING (
 EXISTS(SELECT 1 FROM organization_access.platform_authority a
 JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"=a."InternalIdentityId"
  AND b."Issuer"=a."Issuer" AND b."Subject"=a."Subject"
 WHERE a."Active" AND a."InternalIdentityId"::text=current_setting('app.identity_subject',true)
  AND a."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
  AND a."Subject"=current_setting('app.external_subject',true) COLLATE "C")
);
CREATE FUNCTION organization_access.read_organization(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access
AS $$
DECLARE tenant jsonb; result jsonb; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 IF NOT organization_access.lock_organization_actor() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF target IS NULL THEN
  RETURN jsonb_build_object('state','ok','tenants',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.tenants),'[]'::jsonb));
 END IF;
 SELECT jsonb_build_object('id',"Id",'name',"Name",'revision',"Revision") INTO tenant
 FROM organization_access.tenants WHERE "Id"=target;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 PERFORM set_config('app.tenant_id',target::text,true);
 result:=jsonb_build_object('state','ok','tenant',tenant,
  'companies',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"TenantId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.legal_entities WHERE "TenantId"=target),'[]'::jsonb),
  'sites',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"LegalEntityId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.sites WHERE "TenantId"=target),'[]'::jsonb),
  'warehouses',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"SiteId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.warehouses WHERE "TenantId"=target),'[]'::jsonb));
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_organization(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_organization(uuid) TO :"app_user";

CREATE TABLE organization_access.organization_commands (
 "CommandId" uuid PRIMARY KEY,
 "ActorId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "TargetId" uuid,
 "Request" jsonb NOT NULL,
 "Snapshot" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE organization_access.organization_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.organization_commands FORCE ROW LEVEL SECURITY;
CREATE POLICY organization_command_owner ON organization_access.organization_commands TO CURRENT_USER USING (true) WITH CHECK (true);
REVOKE ALL ON organization_access.organization_commands FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_organization_commands BEFORE UPDATE OR DELETE OR TRUNCATE
 ON organization_access.organization_commands FOR EACH STATEMENT
 EXECUTE FUNCTION organization_access.immutable_delegation_audit();

-- Private invoker body; called only after the definer wrapper verifies authority.
CREATE FUNCTION organization_access.apply_organization_command(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE key text; id uuid; snapshot jsonb; previous organization_access.organization_commands;
 table_name text; parent_column text; actual_parent uuid; current_revision integer; next_revision integer:=1;
 actor uuid:=current_setting('app.identity_subject',true)::uuid;
 binding_hash bytea:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer',true),current_setting('app.external_subject',true))::text,'UTF8'));
BEGIN
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','operation','kind','tenantId','resourceId','parentId','name','expectedRevision']
 OR (SELECT count(*) FROM jsonb_object_keys(request))<>8 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','tenantId','resourceId','parentId'] LOOP
  IF request->key='null'::jsonb AND key<>'commandId' THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'name') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 request:=jsonb_set(request,'{name}',to_jsonb(btrim(request->>'name',E' \t\r\n\f\v')));
 IF length(request->>'name') NOT BETWEEN 1 AND 100 OR request->>'name' ~ '[[:cntrl:]]'
 OR jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number'
 OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$'
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF request->>'operation' NOT IN ('create','rename') OR request->>'operation' IS NULL
 OR request->>'kind' NOT IN ('tenant','company','site','warehouse') OR request->>'kind' IS NULL THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF request->>'operation'='create' AND (request->'resourceId'<>'null'::jsonb OR request->>'expectedRevision'<>'0')
 OR request->>'operation'='rename' AND (request->'resourceId'='null'::jsonb OR request->>'expectedRevision'='0') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF request->>'kind'='tenant' AND request->>'operation'='create' THEN
  IF target IS NOT NULL OR request->'tenantId'<>'null'::jsonb OR request->'parentId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
 ELSE
  IF target IS NULL OR (request->>'tenantId')::uuid IS DISTINCT FROM target
  THEN RETURN jsonb_build_object('state','not_found'); END IF;
  PERFORM 1 FROM organization_access.tenants WHERE "Id"=target;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  PERFORM set_config('app.tenant_id',target::text,true);
  IF request->>'kind'='tenant' THEN
   IF (request->>'resourceId')::uuid IS DISTINCT FROM target OR request->'parentId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','not_found'); END IF;
  ELSIF request->>'kind'='company' THEN
   IF (request->>'parentId')::uuid IS DISTINCT FROM target THEN RETURN jsonb_build_object('state','not_found'); END IF;
  ELSIF request->>'kind'='warehouse' THEN
   PERFORM 1 FROM organization_access.sites WHERE "Id"=(request->>'parentId')::uuid AND "TenantId"=target;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  ELSE
   PERFORM 1 FROM organization_access.legal_entities WHERE "Id"=(request->>'parentId')::uuid AND "TenantId"=target;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  END IF;
 END IF;
 SELECT * INTO previous FROM organization_access.organization_commands WHERE "CommandId"=(request->>'commandId')::uuid;
 IF FOUND THEN
  IF previous."ActorId"=actor AND previous."BindingHash"=binding_hash AND previous."TargetId" IS NOT DISTINCT FROM target AND previous."Request"=request THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."Snapshot"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF request->>'operation'='rename' THEN
  id:=(request->>'resourceId')::uuid;
  table_name:=CASE request->>'kind' WHEN 'tenant' THEN 'tenants' WHEN 'company' THEN 'legal_entities' WHEN 'site' THEN 'sites' WHEN 'warehouse' THEN 'warehouses' END;
  parent_column:=CASE request->>'kind' WHEN 'tenant' THEN 'NULL::uuid' WHEN 'company' THEN '"TenantId"' WHEN 'site' THEN '"LegalEntityId"' WHEN 'warehouse' THEN '"SiteId"' END;
  EXECUTE format('SELECT "Revision",%s FROM organization_access.%I WHERE "Id"=$1 FOR UPDATE',parent_column,table_name) INTO current_revision,actual_parent USING id;
  IF current_revision IS NULL OR actual_parent IS DISTINCT FROM (request->>'parentId')::uuid THEN RETURN jsonb_build_object('state','not_found'); END IF;
  IF current_revision<>(request->>'expectedRevision')::integer OR current_revision=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
  next_revision:=current_revision+1;
  EXECUTE format('UPDATE organization_access.%I SET "Name"=$1,"Revision"=$2 WHERE "Id"=$3',table_name) USING request->>'name',next_revision,id;
 ELSE
 id:=gen_random_uuid();
 PERFORM set_config('app.tenant_id',coalesce(target,id)::text,true);
 IF request->>'kind'='tenant' THEN
  INSERT INTO organization_access.tenants("Id","Name") VALUES(id,request->>'name');
 ELSIF request->>'kind'='company' THEN
  INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES(id,target,request->>'name');
 ELSIF request->>'kind'='warehouse' THEN
  INSERT INTO organization_access.warehouses("Id","TenantId","LegalEntityId","SiteId","Name")
  SELECT id,target,s."LegalEntityId",s."Id",request->>'name' FROM organization_access.sites s WHERE s."Id"=(request->>'parentId')::uuid AND s."TenantId"=target;
 ELSE
  INSERT INTO organization_access.sites("Id","TenantId","LegalEntityId","Name") VALUES(id,target,(request->>'parentId')::uuid,request->>'name');
 END IF;
 END IF;
 snapshot:=jsonb_build_object('resourceId',id,'tenantId',coalesce(target,id),'parentId',request->'parentId','kind',request->>'kind','name',request->>'name','revision',next_revision);
 INSERT INTO organization_access.organization_commands("CommandId","ActorId","BindingHash","TargetId","Request","Snapshot")
 VALUES((request->>'commandId')::uuid,actor,binding_hash,target,request,snapshot);
 RETURN jsonb_build_object('state','applied','snapshot',snapshot);
END $$;
REVOKE ALL ON FUNCTION organization_access.apply_organization_command(uuid,jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.command_organization(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 IF NOT organization_access.lock_organization_actor() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 result:=organization_access.apply_organization_command(target,request);
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.command_organization(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.command_organization(uuid,jsonb) TO :"app_user";
