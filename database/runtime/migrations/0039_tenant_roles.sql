-- MVP03.b.1: finite tenant role configuration. No seed, identity or profile migration.
CREATE TABLE organization_access.tenant_role_objects (
 "Id" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Kind" text NOT NULL CHECK ("Kind" IN ('delegation','permission','role','assignment')),
 "Data" jsonb NOT NULL CHECK (jsonb_typeof("Data")='object'),
 "Revision" integer NOT NULL CHECK ("Revision">0)
);
CREATE UNIQUE INDEX tenant_user_delegate_member ON organization_access.tenant_role_objects("TenantId",("Data"->>'membershipId')) WHERE "Kind"='delegation';
CREATE UNIQUE INDEX tenant_role_member_assignment ON organization_access.tenant_role_objects("TenantId",("Data"->>'membershipId'),("Data"->>'roleId')) WHERE "Kind"='assignment';
ALTER TABLE organization_access.tenant_role_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.tenant_role_objects FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_role_owner ON organization_access.tenant_role_objects TO CURRENT_USER
 USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
REVOKE ALL ON organization_access.tenant_role_objects FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.lock_user_administrator(target uuid) RETURNS boolean
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM 1 FROM organization_access.memberships m
 JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 JOIN organization_access.tenant_role_objects d ON d."TenantId"=m."TenantId" AND d."Kind"='delegation'
  AND d."Data"->>'membershipId'=m."Id"::text AND d."Data"->>'internalIdentityId'=b."InternalIdentityId"::text
  AND d."Data"->>'bindingHash'=encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex')
 WHERE m."TenantId"=target AND d."Data"->'active'='true'::jsonb
  AND b."InternalIdentityId"::text=current_setting('app.identity_subject',true)
  AND b."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
  AND b."Subject"=current_setting('app.external_subject',true) COLLATE "C"
 FOR SHARE OF m,b;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION organization_access.lock_user_administrator(uuid) FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; owner boolean; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 owner:=organization_access.lock_organization_actor();
 IF target IS NULL AND NOT owner THEN
  SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 END IF;
 IF target IS NULL THEN
  IF owner THEN RETURN organization_access.read_organization(NULL)||jsonb_build_object('mode','owner'); END IF;
  RETURN jsonb_build_object('state','forbidden');
 END IF;
 PERFORM set_config('app.tenant_id',target::text,true);
 IF NOT owner AND NOT organization_access.lock_user_administrator(target) THEN
  result:=jsonb_build_object('state','forbidden');
 ELSE
  PERFORM 1 FROM organization_access.tenants WHERE "Id"=target;
  IF NOT FOUND THEN result:=jsonb_build_object('state','forbidden');
  ELSE
   PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
    ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."TenantId"=target FOR SHARE OF m,b;
   result:=jsonb_build_object('state','ok','mode',CASE WHEN owner THEN 'owner' ELSE 'delegate' END,'tenantId',target,
    'actions',jsonb_build_array('organization-context.read','organization-context.write'),
    'memberships',coalesce((SELECT jsonb_agg(jsonb_build_object('membershipId',m."Id",'internalIdentityId',b."InternalIdentityId",
      'bindingHash',encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex'),
      'active',coalesce(d."Data"->'active'='true'::jsonb AND d."Data"->>'internalIdentityId'=b."InternalIdentityId"::text
        AND d."Data"->>'bindingHash'=encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex'),false),
      'resourceId',d."Id",'revision',coalesce(d."Revision",0)) ORDER BY m."Id")
     FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
     LEFT JOIN organization_access.tenant_role_objects d ON d."TenantId"=target AND d."Kind"='delegation' AND d."Data"->>'membershipId'=m."Id"::text
     WHERE m."TenantId"=target),'[]'::jsonb),
    'permissions',coalesce((SELECT jsonb_agg("Data" ORDER BY "Id") FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"='permission'),'[]'::jsonb),
    'roles',coalesce((SELECT jsonb_agg("Data" ORDER BY "Id") FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"='role'),'[]'::jsonb),
    'assignments',coalesce((SELECT jsonb_agg("Data" ORDER BY "Id") FROM organization_access.tenant_role_objects WHERE "TenantId"=target AND "Kind"='assignment'),'[]'::jsonb),
    'warehouses',coalesce((SELECT jsonb_agg(jsonb_build_object('warehouseId',"Id",'siteId',"SiteId",'legalEntityId',"LegalEntityId",'name',"Name") ORDER BY "Id") FROM organization_access.warehouses WHERE "TenantId"=target),'[]'::jsonb));
  END IF;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

CREATE TABLE organization_access.tenant_role_audit (
 "Id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 "CommandId" uuid,
 "ActorId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "Authority" jsonb NOT NULL,
 "TenantId" uuid,
 "ResourceId" uuid,
 "Request" jsonb NOT NULL,
 "Before" jsonb NOT NULL,
 "After" jsonb NOT NULL,
 "Outcome" text NOT NULL CHECK ("Outcome" IN ('applied','forbidden','invalid','conflict')),
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX tenant_role_applied_command ON organization_access.tenant_role_audit("CommandId") WHERE "Outcome"='applied';
ALTER TABLE organization_access.tenant_role_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.tenant_role_audit FORCE ROW LEVEL SECURITY;
-- Private immutable history only, never a business-data policy or app directory.
CREATE POLICY tenant_role_audit_owner ON organization_access.tenant_role_audit TO CURRENT_USER USING(true) WITH CHECK(true);
REVOKE ALL ON organization_access.tenant_role_audit FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_tenant_role_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.tenant_role_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION organization_access.apply_tenant_role(target uuid, request jsonb, authority jsonb) RETURNS jsonb
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
  IF key='resourceId' AND request->key='null'::jsonb THEN CONTINUE; END IF;
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
  IF jsonb_typeof(request->'action') IS DISTINCT FROM 'string'
   OR request->>'action' NOT IN ('organization-context.read','organization-context.write') THEN RETURN jsonb_build_object('state','invalid'); END IF;
  PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "Id"=(request->>'warehouseId')::uuid
   AND "SiteId"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
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

CREATE FUNCTION organization_access.command_tenant_role(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; authority jsonb; owner boolean; prior_target text:=current_setting('app.tenant_id',true); actor uuid;
BEGIN
 owner:=organization_access.lock_organization_actor();
 PERFORM set_config('app.tenant_id',coalesce(target::text,''),true);
 IF owner THEN SELECT jsonb_build_object('kind','owner','revision',"Revision") INTO authority FROM organization_access.platform_authority WHERE "Slot";
 ELSIF organization_access.lock_user_administrator(target) THEN
  SELECT jsonb_build_object('kind','user-administration','resourceId',d."Id",'revision',d."Revision") INTO authority
   FROM organization_access.tenant_role_objects d JOIN organization_access.memberships m ON d."Data"->>'membershipId'=m."Id"::text AND m."TenantId"=d."TenantId"
   WHERE d."Kind"='delegation' AND d."TenantId"=target AND m."IdentitySubject"=current_setting('app.identity_subject',true);
 END IF;
 IF authority IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.tenants WHERE "Id"=target) THEN result:=jsonb_build_object('state','forbidden');
 ELSE result:=organization_access.apply_tenant_role(target,request,authority); END IF;
 IF result->>'state' IN ('forbidden','invalid','conflict') THEN
  -- Exact verified actor only; deliberately no requested target, payload or foreign identifiers.
  SELECT "InternalIdentityId" INTO actor FROM organization_access.external_identity_bindings
   WHERE "InternalIdentityId"::text=current_setting('app.identity_subject',true)
    AND "Issuer"=current_setting('app.identity_issuer',true) COLLATE "C" AND "Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE;
  IF actor IS NOT NULL THEN
   INSERT INTO organization_access.tenant_role_audit("ActorId","BindingHash","Authority","Request","Before","After","Outcome")
   VALUES(actor,sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8')),coalesce(authority,'{}'::jsonb),'{}','{}','{}',result->>'state');
  END IF;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.command_tenant_role(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.command_tenant_role(uuid,jsonb) TO :"app_user";

-- Exact current binding, never a cached role claim. Private objects stay unreadable to app.
CREATE FUNCTION organization_access.current_tenant_role_scopes()
RETURNS TABLE("Id" uuid,"MembershipId" uuid,"TenantId" uuid,"LegalEntityId" uuid,"SiteId" uuid,"WarehouseId" uuid,"Permission" varchar(100))
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."TenantId"::text=current_setting('app.tenant_id',true) AND b."InternalIdentityId"::text=current_setting('app.identity_subject',true)
  AND b."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C" AND b."Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN; END IF;
 RETURN QUERY SELECT DISTINCT ON (p."Data"->>'legalEntityId',p."Data"->>'siteId',p."Data"->>'warehouseId',p."Data"->>'action')
  a."Id",m."Id",m."TenantId",(p."Data"->>'legalEntityId')::uuid,(p."Data"->>'siteId')::uuid,(p."Data"->>'warehouseId')::uuid,(p."Data"->>'action')::varchar(100)
 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 JOIN organization_access.tenant_role_objects a ON a."TenantId"=m."TenantId" AND a."Kind"='assignment'
  AND a."Data"->>'membershipId'=m."Id"::text AND a."Data"->>'internalIdentityId'=b."InternalIdentityId"::text
  AND a."Data"->>'bindingHash'=encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex') AND a."Data"->'active'='true'::jsonb
 JOIN organization_access.tenant_role_objects r ON r."TenantId"=a."TenantId" AND r."Kind"='role' AND r."Id"::text=a."Data"->>'roleId'
 CROSS JOIN LATERAL jsonb_array_elements_text(r."Data"->'permissionIds') x
 JOIN organization_access.tenant_role_objects p ON p."TenantId"=r."TenantId" AND p."Kind"='permission' AND p."Id"::text=x
 WHERE m."IdentitySubject"=current_setting('app.identity_subject',true) AND m."TenantId"::text=current_setting('app.tenant_id',true)
 ORDER BY p."Data"->>'legalEntityId',p."Data"->>'siteId',p."Data"->>'warehouseId',p."Data"->>'action',a."Id";
END $$;
REVOKE ALL ON FUNCTION organization_access.current_tenant_role_scopes() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.current_tenant_role_scopes() TO :"app_user";
CREATE OR REPLACE VIEW organization_access.effective_membership_scopes WITH (security_invoker=true) AS
 SELECT "Id","MembershipId","TenantId","LegalEntityId","SiteId","WarehouseId","Permission" FROM organization_access.membership_scopes
 UNION ALL
 SELECT d."Id",d."MembershipId",d."TenantId",d."LegalEntityId",d."SiteId",d."WarehouseId",d."Permission"
 FROM organization_access.delegated_scopes d JOIN organization_access.delegation_mandates m ON m."Id"=d."MandateId" AND m."TenantId"=d."TenantId"
 WHERE m."RevokedAt" IS NULL AND m."ValidFrom"<=statement_timestamp() AND m."ValidUntil">statement_timestamp()
 UNION ALL
 SELECT "Id","MembershipId","TenantId","LegalEntityId","SiteId","WarehouseId","Permission" FROM organization_access.current_tenant_role_scopes();
