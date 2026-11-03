-- MVP-03.a organization delegation only. No provisioning or business grants.
CREATE TABLE organization_access.organization_delegations (
 "MembershipId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "InternalIdentityId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "Active" boolean NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0)
);
CREATE TABLE organization_access.organization_delegation_commands (
 "CommandId" uuid PRIMARY KEY,
 "ActorId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "TargetId" uuid NOT NULL,
 "Request" jsonb NOT NULL,
 "Snapshot" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE organization_access.organization_delegations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.organization_delegations FORCE ROW LEVEL SECURITY;
ALTER TABLE organization_access.organization_delegation_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.organization_delegation_commands FORCE ROW LEVEL SECURITY;
CREATE POLICY organization_delegation_owner ON organization_access.organization_delegations TO CURRENT_USER USING(true) WITH CHECK(true);
CREATE POLICY organization_delegation_command_owner ON organization_access.organization_delegation_commands TO CURRENT_USER USING(true) WITH CHECK(true);
REVOKE ALL ON organization_access.organization_delegations,organization_access.organization_delegation_commands FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_organization_delegation_commands BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.organization_delegation_commands
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
CREATE FUNCTION organization_access.read_organization_delegations(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 IF NOT organization_access.lock_organization_actor() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM 1 FROM organization_access.tenants WHERE "Id"=target;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 PERFORM set_config('app.tenant_id',target::text,true);
 -- Hold exact preexisting rows; never return external identity or contact data.
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
 ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."TenantId"=target FOR SHARE OF m,b;
 result:=jsonb_build_object('state','ok','memberships',coalesce((SELECT jsonb_agg(jsonb_build_object(
 'membershipId',m."Id",'internalIdentityId',b."InternalIdentityId",
 'bindingHash',encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex'),
 'active',coalesce(d."Active" AND d."InternalIdentityId"=b."InternalIdentityId" AND d."BindingHash"=sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),false),'revision',coalesce(d."Revision",0)) ORDER BY m."Id")
 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
 ON b."InternalIdentityId"::text=m."IdentitySubject"
 LEFT JOIN organization_access.organization_delegations d ON d."MembershipId"=m."Id" AND d."TenantId"=target
 WHERE m."TenantId"=target),'[]'::jsonb));
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_organization_delegations(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_organization_delegations(uuid) TO :"app_user";

CREATE FUNCTION organization_access.command_organization_delegation(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE key text; result jsonb; revision integer; previous organization_access.organization_delegation_commands;
 actor uuid; actor_hash bytea; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 IF NOT organization_access.lock_organization_actor() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 actor:=current_setting('app.identity_subject')::uuid;
 actor_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','operation','membershipId','internalIdentityId','bindingHash','expectedRevision']
 OR (SELECT count(*) FROM jsonb_object_keys(request))<>6 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','membershipId','internalIdentityId'] LOOP
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF request->>'operation' IS NULL OR request->>'operation' NOT IN ('grant','revoke')
 OR jsonb_typeof(request->'bindingHash') IS DISTINCT FROM 'string' OR request->>'bindingHash' !~ '^[0-9a-f]{64}$'
 OR jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number' OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$'
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'internalIdentityId')::uuid=actor THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM 1 FROM organization_access.tenants WHERE "Id"=target;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 PERFORM set_config('app.tenant_id',target::text,true);
 -- Current exact target tuple and membership are required even for historical replay.
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
 ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."TenantId"=target AND m."Id"=(request->>'membershipId')::uuid
 AND b."InternalIdentityId"=(request->>'internalIdentityId')::uuid
 AND sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8'))=decode(request->>'bindingHash','hex')
 FOR SHARE OF m,b;
 IF NOT FOUND THEN result:=jsonb_build_object('state','forbidden');
 ELSE
  SELECT * INTO previous FROM organization_access.organization_delegation_commands WHERE "CommandId"=(request->>'commandId')::uuid;
  IF FOUND THEN
   IF previous."ActorId"=actor AND previous."BindingHash"=actor_hash AND previous."TargetId"=target AND previous."Request"=request
   THEN result:=jsonb_build_object('state','replayed','snapshot',previous."Snapshot");
   ELSE result:=jsonb_build_object('state','conflict'); END IF;
  ELSE
   SELECT "Revision" INTO revision FROM organization_access.organization_delegations WHERE "MembershipId"=(request->>'membershipId')::uuid FOR UPDATE;
   revision:=coalesce(revision,0);
   IF revision<>(request->>'expectedRevision')::integer OR revision=2147483647
   OR EXISTS(SELECT 1 FROM organization_access.organization_commands WHERE "CommandId"=(request->>'commandId')::uuid)
   THEN result:=jsonb_build_object('state','conflict');
   ELSE
    revision:=revision+1;
    INSERT INTO organization_access.organization_delegations("MembershipId","TenantId","InternalIdentityId","BindingHash","Active","Revision")
    VALUES((request->>'membershipId')::uuid,target,(request->>'internalIdentityId')::uuid,decode(request->>'bindingHash','hex'),request->>'operation'='grant',revision)
    ON CONFLICT("MembershipId") DO UPDATE SET "TenantId"=excluded."TenantId","InternalIdentityId"=excluded."InternalIdentityId","BindingHash"=excluded."BindingHash","Active"=excluded."Active","Revision"=excluded."Revision";
    result:=jsonb_build_object('tenantId',target,'membershipId',request->>'membershipId','internalIdentityId',request->>'internalIdentityId','bindingHash',request->>'bindingHash','active',request->>'operation'='grant','revision',revision);
    INSERT INTO organization_access.organization_delegation_commands("CommandId","ActorId","BindingHash","TargetId","Request","Snapshot")
    VALUES((request->>'commandId')::uuid,actor,actor_hash,target,request,result);
    result:=jsonb_build_object('state','applied','snapshot',result);
   END IF;
  END IF;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.command_organization_delegation(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.command_organization_delegation(uuid,jsonb) TO :"app_user";

-- Invoker-only helper: exact current membership AND binding AND grant, held through commit.
CREATE FUNCTION organization_access.lock_organization_delegate(target uuid) RETURNS boolean
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM 1 FROM organization_access.memberships m
 JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 JOIN organization_access.organization_delegations d ON d."MembershipId"=m."Id" AND d."TenantId"=m."TenantId"
 AND d."InternalIdentityId"=b."InternalIdentityId"
 AND d."BindingHash"=sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8'))
 WHERE m."TenantId"=target AND d."Active" AND b."InternalIdentityId"::text=current_setting('app.identity_subject',true)
 AND b."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
 AND b."Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE OF m,b;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION organization_access.lock_organization_delegate(uuid) FROM PUBLIC, :"app_user";

CREATE OR REPLACE FUNCTION organization_access.command_organization(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior_target text:=current_setting('app.tenant_id',true); owner boolean;
BEGIN
 owner:=organization_access.lock_organization_actor();
 IF NOT owner THEN
  IF NOT organization_access.lock_organization_delegate(target) OR request->>'kind' IS NULL
  OR request->>'kind' NOT IN ('company','site','warehouse') THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 END IF;
 IF EXISTS(SELECT 1 FROM organization_access.organization_delegation_commands WHERE "CommandId"::text=request->>'commandId') THEN RETURN jsonb_build_object('state','conflict'); END IF;
 PERFORM set_config('app.tenant_id',coalesce(target::text,''),true);
 result:=organization_access.apply_organization_command(target,request);
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;

-- Workspace discovery never turns the owner-only global directory into a delegate directory.
CREATE FUNCTION organization_access.read_organization_workspace() RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid; tree jsonb;
BEGIN
 IF organization_access.lock_organization_actor() THEN
  RETURN organization_access.read_organization(NULL)||jsonb_build_object('mode','owner');
 END IF;
 SELECT m."TenantId" INTO target FROM organization_access.memberships m
 WHERE m."IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE OF m;
 IF NOT FOUND OR NOT organization_access.lock_organization_delegate(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 tree:=organization_access.read_organization(target);
 IF tree->>'state'<>'ok' THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN jsonb_build_object('state','ok','mode','delegate','tenants',jsonb_build_array(tree->'tenant'));
END $$;
REVOKE ALL ON FUNCTION organization_access.read_organization_workspace() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_organization_workspace() TO :"app_user";

CREATE OR REPLACE FUNCTION organization_access.read_organization(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE tenant jsonb; result jsonb; prior_target text:=current_setting('app.tenant_id',true); owner boolean;
BEGIN
 owner:=organization_access.lock_organization_actor();
 IF NOT owner AND NOT organization_access.lock_organization_delegate(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF target IS NULL THEN
  RETURN jsonb_build_object('state','ok','tenants',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.tenants),'[]'::jsonb));
 END IF;
 PERFORM set_config('app.tenant_id',target::text,true);
 SELECT jsonb_build_object('id',"Id",'name',"Name",'revision',"Revision") INTO tenant FROM organization_access.tenants WHERE "Id"=target;
 IF NOT FOUND THEN result:=jsonb_build_object('state','not_found');
 ELSE
  result:=jsonb_build_object('state','ok','tenant',tenant,
  'companies',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"TenantId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.legal_entities WHERE "TenantId"=target),'[]'::jsonb),
  'sites',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"LegalEntityId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.sites WHERE "TenantId"=target),'[]'::jsonb),
  'warehouses',coalesce((SELECT jsonb_agg(jsonb_build_object('id',"Id",'parentId',"SiteId",'name',"Name",'revision',"Revision") ORDER BY "Id") FROM organization_access.warehouses WHERE "TenantId"=target),'[]'::jsonb));
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
