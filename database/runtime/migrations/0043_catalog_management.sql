-- MVP05/#144. Existing canonical catalog.items, no seeds or competing identity.
-- Published migrations 0001-0042 are immutable. Historical prices/stock untouched.
CREATE TABLE catalog.authority_history (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Version" integer NOT NULL CHECK ("Version">0),
 "Direction" text NOT NULL CHECK ("Direction" IN ('Enginia360ToExternal','ExternalToEnginia360')),
 "SourceId" uuid NOT NULL CHECK ("SourceId"<>'00000000-0000-0000-0000-000000000000'),
 "ProfileId" uuid NOT NULL CHECK ("ProfileId"<>'00000000-0000-0000-0000-000000000000'),
 "CompanyIds" uuid[] NOT NULL CHECK (cardinality("CompanyIds")>0),
 "ActorMembershipId" uuid NOT NULL,
 "VerificationReference" uuid NOT NULL CHECK ("VerificationReference"<>'00000000-0000-0000-0000-000000000000'),
 "EffectiveFrom" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","Version"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE catalog.authority_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.authority_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON catalog.authority_history
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE TRIGGER immutable_master_authority BEFORE UPDATE OR DELETE OR TRUNCATE ON catalog.authority_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION catalog.establish_authority(command_id uuid,tenant_id uuid,actor_id uuid,verification_id uuid,expected_version integer,direction_name text,source_id uuid,profile_id uuid,company_ids uuid[]) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access,catalog AS $$
DECLARE previous catalog.authority_history; version_now integer; BEGIN
 -- Invoker, no app EXECUTE; never a web/admin privilege or self-attested claim.
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN
  RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501';
 END IF;
 IF tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM "Singleton" FROM organization_access.membership_access_snapshot_fence WHERE "Singleton" FOR SHARE;
 -- Offline actor reference is not authentication: an existing current binding
 -- and enabled membership remain locked through this explicit owner decision.
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
 ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."Id"=actor_id AND m."TenantId"=tenant_id FOR SHARE OF m,b;
 IF NOT FOUND OR NOT coalesce((SELECT "Enabled" FROM organization_access.membership_access_state
 WHERE "MembershipId"=actor_id AND "TenantId"=tenant_id),true) THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('catalog-authority:'||tenant_id::text,0));
 SELECT * INTO previous FROM catalog.authority_history WHERE "CommandId"=command_id;
 IF FOUND THEN
  RETURN CASE WHEN previous."TenantId"=tenant_id AND previous."ActorMembershipId"=actor_id AND previous."VerificationReference"=verification_id AND previous."Version"::bigint=expected_version::bigint+1 AND previous."Direction"=direction_name AND previous."SourceId"=source_id AND previous."ProfileId"=profile_id AND previous."CompanyIds"=company_ids THEN 'replayed' ELSE 'conflict' END;
 END IF;
 SELECT coalesce(max("Version"),0) INTO version_now FROM catalog.authority_history WHERE "TenantId"=tenant_id;
 IF expected_version IS DISTINCT FROM version_now THEN RETURN 'conflict'; END IF;
 IF company_ids IS NULL OR cardinality(company_ids)=0 OR EXISTS(SELECT 1 FROM unnest(company_ids) c WHERE c IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.legal_entities le WHERE le."Id"=c AND le."TenantId"=tenant_id)) OR cardinality(company_ids)<>(SELECT count(DISTINCT c) FROM unnest(company_ids) c) THEN RETURN 'conflict'; END IF;
 INSERT INTO catalog.authority_history("CommandId","TenantId","Version","Direction","SourceId","ProfileId","CompanyIds","ActorMembershipId","VerificationReference")
 VALUES(command_id,tenant_id,version_now+1,direction_name,source_id,profile_id,company_ids,actor_id,verification_id);
 RETURN 'applied';
END $$;

REVOKE ALL ON catalog.authority_history FROM PUBLIC, :"app_user";
REVOKE ALL ON FUNCTION catalog.establish_authority(uuid,uuid,uuid,uuid,integer,text,uuid,uuid,uuid[]) FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.catalog_permission(action_name text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF NOT organization_access.current_membership_access(target) OR target IS NULL THEN RETURN false; END IF;
 IF action_name NOT IN ('catalog.shared.read','catalog.shared.create','catalog.shared.edit') THEN RETURN false; END IF;
 RETURN EXISTS(SELECT 1 FROM organization_access.current_tenant_role_scopes_before_access() s
 JOIN organization_access.tenant_role_objects p ON p."Id"=s."Id" AND p."TenantId"=target AND p."Kind"='permission'
 WHERE s."TenantId"=target AND s."Permission"=action_name AND s."LegalEntityId" IS NULL
 AND s."SiteId" IS NULL AND s."WarehouseId" IS NULL
 AND p."Data" ?& ARRAY['action','legalEntityId','siteId','warehouseId']
 AND p."Data"->'siteId'='null'::jsonb AND p."Data"->'warehouseId'='null'::jsonb
 AND p."Data"->'legalEntityId'='null'::jsonb);
END $$;
REVOKE ALL ON FUNCTION organization_access.catalog_permission(text) FROM PUBLIC, :"app_user";


ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_catalog;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_catalog(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb;
BEGIN
 result:=organization_access.read_tenant_roles_before_catalog(target);
 IF result->>'state'='ok' AND result ? 'permissions' THEN
  result:=jsonb_set(result,'{actions}',(result->'actions')||jsonb_build_array('catalog.shared.read','catalog.shared.create','catalog.shared.edit'));
 END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

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
  ELSIF request->>'action' IN ('counterparties.extensions.read','counterparties.extensions.write') THEN
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



-- Private receipt/audit; no direct application reads/writes, including TRUNCATE.
CREATE TABLE catalog.management_audit (
 "CommandId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "Request" jsonb NOT NULL,
 "Before" jsonb NOT NULL,
 "After" jsonb NOT NULL,
 "AuthorityVersion" integer NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE catalog.management_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.management_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY management_audit_owner ON catalog.management_audit TO CURRENT_USER
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
REVOKE ALL ON catalog.management_audit FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_management_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON catalog.management_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION catalog.management_snapshot(record_id uuid) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog,catalog AS $$
 SELECT jsonb_build_object('id',"Id",'kind',CASE "Kind" WHEN 'Part' THEN 'Article' WHEN 'Service' THEN 'Service' END,
 'label',"Label",'revision',"Version") FROM catalog.items
 WHERE "Id"=record_id AND "TenantId"::text=current_setting('app.tenant_id',true)
$$;
REVOKE ALL ON FUNCTION catalog.management_snapshot(uuid) FROM PUBLIC, :"app_user";

CREATE FUNCTION catalog.management_read(search_text text, after_id uuid, record_id uuid, kind_name text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
DECLARE target uuid; authority jsonb; items jsonb; detail jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF NOT organization_access.catalog_permission('catalog.shared.read') THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF search_text IS NOT NULL AND (length(search_text)>200 OR search_text ~ '[[:cntrl:]]')
 OR kind_name IS NOT NULL AND kind_name NOT IN ('Article','Service') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('catalog-authority:'||target::text,0));
 SELECT jsonb_build_object('state',CASE WHEN "Direction"='Enginia360ToExternal' THEN 'local' ELSE 'external' END,'version',"Version") INTO authority
 FROM catalog.authority_history WHERE "TenantId"=target ORDER BY "Version" DESC LIMIT 1;
 authority:=coalesce(authority,jsonb_build_object('state','missing','version',0));
 SELECT coalesce(jsonb_agg(catalog.management_snapshot(x."Id") ORDER BY x."Id"),'[]'::jsonb) INTO items FROM
 (SELECT "Id" FROM catalog.items WHERE "TenantId"=target
 AND (search_text IS NULL OR strpos(lower("Label"),lower(search_text))>0)
 AND (kind_name IS NULL OR "Kind"=CASE kind_name WHEN 'Article' THEN 'Part' ELSE 'Service' END)
 AND (after_id IS NULL OR "Id">after_id) ORDER BY "Id" LIMIT 21) x;
 IF record_id IS NOT NULL THEN
  detail:=catalog.management_snapshot(record_id);
  IF detail IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 END IF;
 RETURN jsonb_build_object('state','ready','tenantId',target,'authority',authority,'items',items,'detail',detail,
 'canCreate',organization_access.catalog_permission('catalog.shared.create'),'canEdit',organization_access.catalog_permission('catalog.shared.edit'));
END $$;
REVOKE ALL ON FUNCTION catalog.management_read(text,uuid,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.management_read(text,uuid,uuid,text) TO :"app_user";

CREATE FUNCTION catalog.management_command(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
DECLARE target uuid; member_id uuid; binding_hash bytea; command_id uuid; record_id uuid;
 operation text; action_name text; key text; revision_now integer; authority catalog.authority_history;
 previous catalog.management_audit; row_before jsonb; row_after jsonb; stored_kind text;
 keys text[]:=ARRAY['commandId','operation','itemId','expectedRevision','authorityVersion','kind','label'];
BEGIN
 -- The exact current verified binding, access state and role objects share the
 -- 777036 owning transaction boundary, including before an idempotent replay.
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF NOT organization_access.catalog_permission('catalog.shared.read') THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& keys OR (SELECT count(*) FROM jsonb_object_keys(request))<>cardinality(keys) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF jsonb_typeof(request->'operation') IS DISTINCT FROM 'string' OR request->>'operation' NOT IN ('create','edit')
 OR jsonb_typeof(request->'kind') IS DISTINCT FROM 'string' OR request->>'kind' NOT IN ('Article','Service')
 OR jsonb_typeof(request->'label') IS DISTINCT FROM 'string' OR length(request->>'label') NOT BETWEEN 1 AND 100
 OR length(btrim(request->>'label'))=0 OR request->>'label' ~ '[[:cntrl:]]' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 FOREACH key IN ARRAY ARRAY['commandId','itemId'] LOOP
  IF operation='create' AND key='itemId' AND request->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 FOREACH key IN ARRAY ARRAY['expectedRevision','authorityVersion'] LOOP
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'number' OR request->>key !~ '^(0|[1-9][0-9]{0,9})$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF (request->>key)::bigint>2147483647 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF operation='create' AND (request->'itemId'<>'null'::jsonb OR request->>'expectedRevision'<>'0') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 action_name:=CASE operation WHEN 'create' THEN 'catalog.shared.create' ELSE 'catalog.shared.edit' END;
 IF NOT organization_access.catalog_permission(action_name) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('catalog-authority:'||target::text,0));
 SELECT * INTO authority FROM catalog.authority_history WHERE "TenantId"=target ORDER BY "Version" DESC LIMIT 1;
 IF authority."Version" IS NULL THEN RETURN jsonb_build_object('state','missing'); END IF;
 IF authority."Direction"<>'Enginia360ToExternal' THEN RETURN jsonb_build_object('state','external'); END IF;
 IF authority."Version"<>(request->>'authorityVersion')::integer THEN RETURN jsonb_build_object('state','stale_authority'); END IF;
 command_id:=(request->>'commandId')::uuid; record_id:=(request->>'itemId')::uuid;
 binding_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,2));
 SELECT * INTO previous FROM catalog.management_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=binding_hash AND previous."Request"=request
  THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 stored_kind:=CASE request->>'kind' WHEN 'Article' THEN 'Part' ELSE 'Service' END;
 IF operation='create' THEN
  record_id:=gen_random_uuid(); revision_now:=0; row_before:='{}'::jsonb;
 ELSE
  SELECT "Version" INTO revision_now FROM catalog.items WHERE "Id"=record_id AND "TenantId"=target FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  row_before:=catalog.management_snapshot(record_id);
  IF row_before->>'kind'<>request->>'kind' THEN RETURN jsonb_build_object('state','conflict'); END IF;
 END IF;
 IF revision_now<>(request->>'expectedRevision')::integer OR revision_now=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF operation='create' THEN
  INSERT INTO catalog.items("Id","TenantId","RegisteredCompanyId","Kind","Label","Version")
  VALUES(record_id,target,(authority."CompanyIds")[1],stored_kind,btrim(request->>'label'),1);
 ELSE
  UPDATE catalog.items SET "Label"=btrim(request->>'label'),"Version"=revision_now+1 WHERE "Id"=record_id AND "TenantId"=target;
 END IF;
 row_after:=catalog.management_snapshot(record_id);
 INSERT INTO catalog.management_audit("CommandId","TenantId","ActorMembershipId","BindingHash","Request","Before","After","AuthorityVersion")
 VALUES(command_id,target,member_id,binding_hash,request,row_before,row_after,authority."Version");
 RETURN jsonb_build_object('state','applied','snapshot',row_after);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION catalog.management_command(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.management_command(jsonb) TO :"app_user";
