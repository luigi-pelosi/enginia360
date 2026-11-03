-- MVP-02.a. Explicit single owner authority; no seeds, membership or business privileges.
CREATE TABLE organization_access.platform_authority (
 "Slot" boolean PRIMARY KEY CHECK ("Slot"),
 "InternalIdentityId" uuid NOT NULL CHECK ("InternalIdentityId"<>'00000000-0000-0000-0000-000000000000'),
 "Issuer" text COLLATE "C" NOT NULL,
 "Subject" text COLLATE "C" NOT NULL,
 "Active" boolean NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0)
);
CREATE TABLE organization_access.platform_authority_audit (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "Request" jsonb NOT NULL,
 "Snapshot" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE organization_access.platform_authority ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.platform_authority FORCE ROW LEVEL SECURITY;
ALTER TABLE organization_access.platform_authority_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.platform_authority_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY platform_owner ON organization_access.platform_authority TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY platform_audit_owner ON organization_access.platform_authority_audit TO CURRENT_USER USING (true) WITH CHECK (true);
CREATE POLICY platform_actor ON organization_access.platform_authority FOR SELECT TO :"app_user" USING (
 "Active" AND "InternalIdentityId"::text=current_setting('app.identity_subject',true)
 AND "Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
 AND "Subject"=current_setting('app.external_subject',true) COLLATE "C"
 AND EXISTS(SELECT 1 FROM organization_access.external_identity_bindings b
 WHERE b."InternalIdentityId"=platform_authority."InternalIdentityId"
 AND b."Issuer"=platform_authority."Issuer" AND b."Subject"=platform_authority."Subject")
);
CREATE TRIGGER immutable_platform_authority_audit BEFORE UPDATE OR DELETE OR TRUNCATE
 ON organization_access.platform_authority_audit FOR EACH STATEMENT
 EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON organization_access.platform_authority,organization_access.platform_authority_audit FROM PUBLIC, :"app_user";
GRANT SELECT ON organization_access.platform_authority TO :"app_user";

CREATE FUNCTION organization_access.command_platform_authority(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE actor uuid; snapshot jsonb; binding organization_access.external_identity_bindings;
 current_row organization_access.platform_authority; old_request jsonb; key text; next_revision integer; active boolean;
BEGIN
 IF session_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=session_user) THEN
  RETURN jsonb_build_object('state','forbidden');
 END IF;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','operation','internalIdentityId','issuer','subject','verificationReference','expectedRevision']
 OR (SELECT count(*) FROM jsonb_object_keys(request))<>7 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','internalIdentityId','verificationReference'] LOOP
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string'
  OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'operation') IS DISTINCT FROM 'string' OR request->>'operation' NOT IN ('grant','revoke')
 OR jsonb_typeof(request->'issuer') IS DISTINCT FROM 'string' OR octet_length(request->>'issuer') NOT BETWEEN 9 AND 2048
 OR request->>'issuer' !~ '^https://[!-~]+$' OR request->>'issuer' ~ '[@?#]'
 OR jsonb_typeof(request->'subject') IS DISTINCT FROM 'string' OR octet_length(request->>'subject') NOT BETWEEN 1 AND 255
 OR request->>'subject' !~ '^[ -~]+$'
 OR jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number'
 OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 actor:=(request->>'internalIdentityId')::uuid;
 PERFORM pg_advisory_xact_lock(777036);
 SELECT "Request","Snapshot" INTO old_request,snapshot FROM organization_access.platform_authority_audit WHERE "CommandId"=(request->>'commandId')::uuid;
 IF FOUND THEN
  IF old_request=request THEN RETURN jsonb_build_object('state','replayed','snapshot',snapshot); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 SELECT * INTO current_row FROM organization_access.platform_authority WHERE "Slot" FOR UPDATE;
 IF coalesce(current_row."Revision",0)<>(request->>'expectedRevision')::integer
 OR coalesce(current_row."Revision",0)=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 active:=request->>'operation'='grant';
 IF active THEN
  IF current_row."Active" AND (current_row."InternalIdentityId"<>actor OR current_row."Issuer"<>request->>'issuer' COLLATE "C" OR current_row."Subject"<>request->>'subject' COLLATE "C") THEN RETURN jsonb_build_object('state','conflict'); END IF;
  PERFORM set_config('app.identity_issuer',request->>'issuer',true);
  PERFORM set_config('app.external_subject',request->>'subject',true);
  SELECT * INTO binding FROM organization_access.external_identity_bindings
  WHERE "InternalIdentityId"=actor AND "Issuer"=request->>'issuer' COLLATE "C"
  AND "Subject"=request->>'subject' COLLATE "C" FOR SHARE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 ELSE
  IF current_row."InternalIdentityId" IS NULL OR current_row."InternalIdentityId"<>actor
  OR current_row."Issuer"<>request->>'issuer' COLLATE "C" OR current_row."Subject"<>request->>'subject' COLLATE "C" THEN RETURN jsonb_build_object('state','conflict'); END IF;
 END IF;
 next_revision:=coalesce(current_row."Revision",0)+1;
 snapshot:=jsonb_build_object('internalIdentityId',actor,'active',active,'revision',next_revision);
 INSERT INTO organization_access.platform_authority VALUES(true,actor,request->>'issuer',request->>'subject',active,next_revision)
 ON CONFLICT ("Slot") DO UPDATE SET "InternalIdentityId"=EXCLUDED."InternalIdentityId","Issuer"=EXCLUDED."Issuer","Subject"=EXCLUDED."Subject","Active"=EXCLUDED."Active","Revision"=EXCLUDED."Revision";
 INSERT INTO organization_access.platform_authority_audit("CommandId","Request","Snapshot")
 VALUES((request->>'commandId')::uuid,request,snapshot);
 RETURN jsonb_build_object('state','applied','snapshot',snapshot);
END $$;
REVOKE ALL ON FUNCTION organization_access.command_platform_authority(jsonb) FROM PUBLIC, :"app_user";
