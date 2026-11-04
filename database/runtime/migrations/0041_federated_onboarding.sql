-- MVP03.b.2b. No identity seed, backfill, app DML or cardinality change.
-- All public entries are finite; app GUCs are populated only by trusted handlers.
CREATE TABLE organization_access.onboarding_invitations (
 "Id" uuid PRIMARY KEY, "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Active" boolean NOT NULL, "Revision" integer NOT NULL CHECK ("Revision">0),
 "ExpiresAt" timestamptz NOT NULL
);
CREATE TABLE organization_access.onboarding_requests (
 "Id" uuid PRIMARY KEY, "InvitationId" uuid NOT NULL UNIQUE REFERENCES organization_access.onboarding_invitations("Id"),
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Issuer" text COLLATE "C" NOT NULL, "Subject" varchar(255) COLLATE "C" NOT NULL,
 "ExpiresAt" timestamptz NOT NULL, "Revision" integer NOT NULL CHECK ("Revision">0),
 "InternalIdentityId" uuid, "MembershipId" uuid,
 CHECK (("InternalIdentityId" IS NULL)=("MembershipId" IS NULL))
);
CREATE TABLE organization_access.onboarding_audit (
 "Id" uuid PRIMARY KEY DEFAULT gen_random_uuid(), "CommandId" uuid,
 "ActorId" uuid, "BindingHash" bytea NOT NULL, "Authority" jsonb NOT NULL,
 "TenantId" uuid, "Request" jsonb NOT NULL, "Before" jsonb NOT NULL, "After" jsonb NOT NULL,
 "Outcome" text NOT NULL CHECK ("Outcome" IN ('applied','initiated','forbidden','invalid','conflict')),
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX onboarding_applied_command ON organization_access.onboarding_audit("CommandId") WHERE "Outcome"='applied';
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['onboarding_invitations','onboarding_requests','onboarding_audit'] LOOP
  EXECUTE format('ALTER TABLE organization_access.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE organization_access.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY onboarding_owner ON organization_access.%I TO %I USING(true) WITH CHECK(true)',t,current_user);
 END LOOP;
END $$;
REVOKE ALL ON organization_access.onboarding_invitations,organization_access.onboarding_requests,organization_access.onboarding_audit FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_onboarding_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.onboarding_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION organization_access.onboarding_authority(target uuid) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE owner boolean; authority jsonb;
BEGIN
 owner:=organization_access.lock_organization_actor();
 IF owner THEN
  SELECT jsonb_build_object('kind','owner','revision',"Revision") INTO authority FROM organization_access.platform_authority WHERE "Slot" AND "Active" FOR SHARE;
 ELSIF organization_access.lock_user_administrator(target) THEN
  SELECT jsonb_build_object('kind','user-administration','resourceId',d."Id",'revision',d."Revision") INTO authority
  FROM organization_access.tenant_role_objects d JOIN organization_access.memberships m
   ON d."Data"->>'membershipId'=m."Id"::text AND m."TenantId"=d."TenantId"
  WHERE d."Kind"='delegation' AND d."TenantId"=target AND m."IdentitySubject"=current_setting('app.identity_subject',true)
   AND d."Data"->'active'='true'::jsonb FOR SHARE OF d,m;
 END IF;
 RETURN authority;
END $$;
REVOKE ALL ON FUNCTION organization_access.onboarding_authority(uuid) FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.read_onboarding(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE directory jsonb; result jsonb; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 -- Reuse current enabled delegate/exact-binding directory. Owner NULL only lists tenants.
 directory:=organization_access.read_tenant_roles(target);
 IF directory->>'state'<>'ok' THEN RETURN directory; END IF;
 IF NOT directory ? 'tenantId' THEN
  IF organization_access.onboarding_authority(NULL) IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  RETURN directory-'actions';
 END IF;
 target:=(directory->>'tenantId')::uuid;
 PERFORM set_config('app.tenant_id',target::text,true);
 IF organization_access.onboarding_authority(target) IS NULL THEN
  PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
  RETURN jsonb_build_object('state','forbidden');
 END IF;
 result:=jsonb_build_object('state','ok','mode',directory->>'mode','tenantId',target,
  'invitations',coalesce((SELECT jsonb_agg(jsonb_build_object('invitationId',"Id",'revision',"Revision",'active',"Active",'expiresAt',"ExpiresAt") ORDER BY "Id")
   FROM organization_access.onboarding_invitations WHERE "TenantId"=target),'[]'::jsonb),
  'requests',coalesce((SELECT jsonb_agg(jsonb_build_object('requestId',r."Id",'invitationId',r."InvitationId",'revision',r."Revision",
   'issuer',r."Issuer",'subject',r."Subject",'expiresAt',r."ExpiresAt",'approved',r."MembershipId" IS NOT NULL,
   'available',i."Active" AND i."ExpiresAt">clock_timestamp() AND r."ExpiresAt">clock_timestamp(),
   'membershipId',r."MembershipId",'internalIdentityId',r."InternalIdentityId") ORDER BY r."Id")
   FROM organization_access.onboarding_requests r JOIN organization_access.onboarding_invitations i ON i."Id"=r."InvitationId"
   WHERE r."TenantId"=target),'[]'::jsonb));
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_onboarding(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_onboarding(uuid) TO :"app_user";

-- Called ONLY after OIDC code/signature/issuer/audience/nonce/state/PKCE validation.
-- The invitation routes to a tenant; neither it nor any supplied tuple authenticates.
CREATE FUNCTION organization_access.begin_onboarding(invitation uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE i organization_access.onboarding_invitations; r organization_access.onboarding_requests;
 issuer text:=current_setting('app.identity_issuer',true); subject text:=current_setting('app.external_subject',true);
 fingerprint bytea;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF issuer IS NULL OR issuer !~ '^https://[!-~]+$' OR issuer ~ '[@?#]' OR octet_length(issuer)>2048
  OR subject IS NULL OR subject !~ '^[ -~]{1,255}$' THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT * INTO i FROM organization_access.onboarding_invitations WHERE "Id"=invitation FOR UPDATE;
 IF NOT FOUND OR NOT i."Active" OR i."ExpiresAt"<=clock_timestamp() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 -- Private owner policy sees occupied external keys across all tenants. No global app directory.
 IF EXISTS(SELECT 1 FROM organization_access.external_identity_bindings WHERE "Issuer"=issuer COLLATE "C" AND "Subject"=subject COLLATE "C")
 THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 fingerprint:=sha256(convert_to(jsonb_build_array(issuer,subject)::text,'UTF8'));
 SELECT * INTO r FROM organization_access.onboarding_requests WHERE "InvitationId"=invitation FOR UPDATE;
 IF FOUND THEN
  IF r."Issuer"<>issuer COLLATE "C" OR r."Subject"<>subject COLLATE "C" OR r."ExpiresAt"<=clock_timestamp()
   OR r."MembershipId" IS NOT NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 ELSE
  INSERT INTO organization_access.onboarding_requests VALUES(gen_random_uuid(),invitation,i."TenantId",issuer,subject,
   least(i."ExpiresAt",clock_timestamp()+interval '15 minutes'),1,NULL,NULL) RETURNING * INTO r;
  INSERT INTO organization_access.onboarding_audit("BindingHash","Authority","TenantId","Request","Before","After","Outcome")
   VALUES(fingerprint,'{}',i."TenantId",jsonb_build_object('requestId',r."Id"),'{}',jsonb_build_object('revision',1),'initiated');
 END IF;
 RETURN jsonb_build_object('state','ok','requestId',r."Id",'tenantId',r."TenantId",'expiresAt',r."ExpiresAt");
END $$;
REVOKE ALL ON FUNCTION organization_access.begin_onboarding(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.begin_onboarding(uuid) TO :"app_user";

CREATE FUNCTION organization_access.pending_onboarding_status(request_id uuid, tenant uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE r organization_access.onboarding_requests; i organization_access.onboarding_invitations;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 SELECT * INTO r FROM organization_access.onboarding_requests WHERE "Id"=request_id AND "TenantId"=tenant
  AND "Issuer"=current_setting('app.identity_issuer',true) COLLATE "C" AND "Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE;
 IF NOT FOUND OR r."ExpiresAt"<=clock_timestamp() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT * INTO i FROM organization_access.onboarding_invitations WHERE "Id"=r."InvitationId" FOR SHARE;
 IF NOT i."Active" OR i."ExpiresAt"<=clock_timestamp() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN jsonb_build_object('state','ok','requestId',r."Id",'tenantId',r."TenantId",'revision',r."Revision",'expiresAt',r."ExpiresAt",
  'approved',r."MembershipId" IS NOT NULL);
END $$;
REVOKE ALL ON FUNCTION organization_access.pending_onboarding_status(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.pending_onboarding_status(uuid,uuid) TO :"app_user";

CREATE FUNCTION organization_access.apply_onboarding(target uuid, request jsonb, authority jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE operation text; key text; previous organization_access.onboarding_audit; r organization_access.onboarding_requests;
 i organization_access.onboarding_invitations; snapshot jsonb; before_data jsonb:='{}';
 actor uuid:=current_setting('app.identity_subject')::uuid;
 actor_hash bytea:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 internal_id uuid; member_id uuid; prior_identity text:=current_setting('app.identity_subject',true);
BEGIN
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 IF operation IS NULL OR operation NOT IN ('invite','revoke','approve') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','operation','resourceId','expectedRevision'] OR (SELECT count(*) FROM jsonb_object_keys(request))<>4
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','resourceId'] LOOP
  IF key='resourceId' AND operation='invite' AND request->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number' OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$'
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 OR (operation='invite' AND (request->'resourceId'<>'null'::jsonb OR request->>'expectedRevision'<>'0'))
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 -- Current actor authority already locked; current exact target binding also precedes replay.
 IF operation='approve' THEN
  SELECT * INTO r FROM organization_access.onboarding_requests WHERE "Id"=(request->>'resourceId')::uuid AND "TenantId"=target FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  IF r."MembershipId" IS NOT NULL THEN
   PERFORM 1 FROM organization_access.external_identity_bindings b JOIN organization_access.memberships m ON m."IdentitySubject"=b."InternalIdentityId"::text
    WHERE b."InternalIdentityId"=r."InternalIdentityId" AND b."Issuer"=r."Issuer" AND b."Subject"=r."Subject"
     AND m."Id"=r."MembershipId" AND m."TenantId"=target FOR SHARE OF b,m;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  END IF;
 ELSIF operation='revoke' THEN
  SELECT * INTO i FROM organization_access.onboarding_invitations WHERE "Id"=(request->>'resourceId')::uuid AND "TenantId"=target FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 END IF;
 SELECT * INTO previous FROM organization_access.onboarding_audit WHERE "CommandId"=(request->>'commandId')::uuid AND "Outcome"='applied';
 IF FOUND THEN
  IF previous."ActorId"=actor AND previous."BindingHash"=actor_hash AND previous."TenantId"=target AND previous."Request"=request
   THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 IF operation='invite' THEN
  INSERT INTO organization_access.onboarding_invitations VALUES(gen_random_uuid(),target,true,1,clock_timestamp()+interval '24 hours') RETURNING * INTO i;
  snapshot:=jsonb_build_object('invitationId',i."Id",'revision',1,'active',true,'expiresAt',i."ExpiresAt");
 ELSIF operation='revoke' THEN
  IF i."Revision"<>(request->>'expectedRevision')::integer OR i."Revision"=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
  before_data:=jsonb_build_object('active',i."Active",'revision',i."Revision");
  UPDATE organization_access.onboarding_invitations SET "Active"=false,"Revision"="Revision"+1 WHERE "Id"=i."Id" RETURNING * INTO i;
  snapshot:=jsonb_build_object('invitationId',i."Id",'active',false,'revision',i."Revision");
 ELSE
  SELECT * INTO i FROM organization_access.onboarding_invitations WHERE "Id"=r."InvitationId" AND "TenantId"=target FOR UPDATE;
  IF r."MembershipId" IS NOT NULL OR r."Revision"<>(request->>'expectedRevision')::integer OR r."Revision"=2147483647
   THEN RETURN jsonb_build_object('state','conflict'); END IF;
  IF NOT i."Active" OR i."ExpiresAt"<=clock_timestamp() OR r."ExpiresAt"<=clock_timestamp() THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  IF EXISTS(SELECT 1 FROM organization_access.external_identity_bindings WHERE "Issuer"=r."Issuer" AND "Subject"=r."Subject")
   THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  internal_id:=gen_random_uuid(); member_id:=gen_random_uuid();
  -- No caller supplied internal ID, no merge/rebind/ON CONFLICT UPDATE.
  -- A savepoint catches hidden unique collisions and rolls back ALL inserts.
  BEGIN
   INSERT INTO organization_access.external_identity_bindings VALUES(internal_id,r."Issuer",r."Subject");
   PERFORM set_config('app.identity_subject',internal_id::text,true);
   INSERT INTO organization_access.memberships("Id","TenantId","IdentitySubject") VALUES(member_id,target,internal_id::text);
   INSERT INTO organization_access.membership_access_state VALUES(member_id,target,false,1);
   PERFORM set_config('app.identity_subject',coalesce(prior_identity,''),true);
  EXCEPTION WHEN unique_violation THEN
   PERFORM set_config('app.identity_subject',coalesce(prior_identity,''),true);
   RETURN jsonb_build_object('state','forbidden');
  END;
  UPDATE organization_access.onboarding_requests SET "InternalIdentityId"=internal_id,"MembershipId"=member_id,"Revision"="Revision"+1 WHERE "Id"=r."Id";
  before_data:=jsonb_build_object('requestId',r."Id",'revision',r."Revision");
  snapshot:=jsonb_build_object('requestId',r."Id",'revision',r."Revision"+1,'membershipId',member_id,'internalIdentityId',internal_id,'enabled',false);
 END IF;
 INSERT INTO organization_access.onboarding_audit("CommandId","ActorId","BindingHash","Authority","TenantId","Request","Before","After","Outcome")
 VALUES((request->>'commandId')::uuid,actor,actor_hash,authority,target,request,before_data,snapshot,'applied');
 RETURN jsonb_build_object('state','applied','snapshot',snapshot);
END $$;
REVOKE ALL ON FUNCTION organization_access.apply_onboarding(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.command_onboarding(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE authority jsonb; result jsonb; prior_target text:=current_setting('app.tenant_id',true); actor uuid;
BEGIN
 -- Same777036 lock as owner/delegation/access/role edits, before any resource row.
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM set_config('app.tenant_id',coalesce(target::text,''),true);
 authority:=organization_access.onboarding_authority(target);
 IF authority IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.tenants WHERE "Id"=target) THEN result:=jsonb_build_object('state','forbidden');
 ELSE result:=organization_access.apply_onboarding(target,request,authority); END IF;
 IF result->>'state' IN ('forbidden','invalid','conflict') THEN
  SELECT "InternalIdentityId" INTO actor FROM organization_access.external_identity_bindings
   WHERE "InternalIdentityId"::text=current_setting('app.identity_subject',true)
    AND "Issuer"=current_setting('app.identity_issuer',true) COLLATE "C" AND "Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE;
  IF actor IS NOT NULL THEN
   INSERT INTO organization_access.onboarding_audit("ActorId","BindingHash","Authority","Request","Before","After","Outcome")
    VALUES(actor,sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8')),
     coalesce(authority,'{}'),'{}','{}','{}',result->>'state');
  END IF;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.command_onboarding(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.command_onboarding(uuid,jsonb) TO :"app_user";
