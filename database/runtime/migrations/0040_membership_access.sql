-- MVP03.b.2a: access state is separate from membership, grants and delegation.
-- Append-only migration; no seeds, binding/membership rewrite or grant backfill.
CREATE TABLE organization_access.membership_access_state (
 "MembershipId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "Enabled" boolean NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0)
);
ALTER TABLE organization_access.membership_access_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.membership_access_state FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_access_state_owner ON organization_access.membership_access_state TO CURRENT_USER
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
REVOKE ALL ON organization_access.membership_access_state FROM PUBLIC, :"app_user";

-- A technical MVCC witness, not a business grant, member backfill or a new
-- advisory key. Absent access-state rows must remain legacy-enabled, but their
-- absence in an OLD RepeatableRead snapshot must not hide a committed disable.
-- Every state change versions this singleton; FOR SHARE below makes an old
-- snapshot fail with40001 rather than authorize from stale absence.
CREATE TABLE organization_access.membership_access_snapshot_fence (
 "Singleton" boolean PRIMARY KEY CHECK ("Singleton"), "Token" boolean NOT NULL
);
ALTER TABLE organization_access.membership_access_snapshot_fence ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.membership_access_snapshot_fence FORCE ROW LEVEL SECURITY;
CREATE POLICY snapshot_fence_owner ON organization_access.membership_access_snapshot_fence TO CURRENT_USER USING (true) WITH CHECK (true);
REVOKE ALL ON organization_access.membership_access_snapshot_fence FROM PUBLIC, :"app_user";
INSERT INTO organization_access.membership_access_snapshot_fence VALUES (true,false);
CREATE FUNCTION organization_access.advance_membership_access_snapshot_fence() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 UPDATE organization_access.membership_access_snapshot_fence SET "Token"=NOT "Token" WHERE "Singleton";
 RETURN coalesce(NEW,OLD);
END $$;
REVOKE ALL ON FUNCTION organization_access.advance_membership_access_snapshot_fence() FROM PUBLIC, :"app_user";
CREATE TRIGGER membership_access_snapshot_changed BEFORE INSERT OR UPDATE OR DELETE ON organization_access.membership_access_state
 FOR EACH ROW EXECUTE FUNCTION organization_access.advance_membership_access_snapshot_fence();

-- Reuse the existing 777036 transaction boundary: no second lock order.
-- Current exact binding and membership are held through this owning transaction.
-- There is deliberately no global-owner or missing-identity business bypass.
CREATE FUNCTION organization_access.current_membership_access(target uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE member_id uuid; member_tenant uuid; enabled boolean; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 PERFORM "Singleton" FROM organization_access.membership_access_snapshot_fence WHERE "Singleton" FOR SHARE;
 SELECT m."Id",m."TenantId" INTO member_id,member_tenant
 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
  ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."IdentitySubject"=current_setting('app.identity_subject',true)
  AND (target IS NULL OR m."TenantId"=target)
  AND b."Issuer"=current_setting('app.identity_issuer',true) COLLATE "C"
  AND b."Subject"=current_setting('app.external_subject',true) COLLATE "C"
 FOR SHARE OF m,b;
 IF member_id IS NULL THEN RETURN false; END IF;
 PERFORM set_config('app.tenant_id',member_tenant::text,true);
 SELECT "Enabled" INTO enabled FROM organization_access.membership_access_state WHERE "MembershipId"=member_id AND "TenantId"=member_tenant;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN coalesce(enabled,true);
END $$;
REVOKE ALL ON FUNCTION organization_access.current_membership_access(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.current_membership_access(uuid) TO :"app_user";

-- These restrictions AND the preexisting permissive policies; never an OR escape.
CREATE POLICY membership_access_current ON organization_access.membership_scopes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON organization_access.company_permissions AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON organization_access.common_edit_permissions AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));

-- Preserve the proven directory/authority contract. The internal function is no
-- longer callable by the application; only the authenticated metadata wrapper is.
ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_access;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior_target text:=current_setting('app.tenant_id',true);
BEGIN
 result:=organization_access.read_tenant_roles_before_access(target);
 IF result->>'state'<>'ok' OR NOT result ? 'memberships' THEN RETURN result; END IF;
 PERFORM set_config('app.tenant_id',result->>'tenantId',true);
 result:=result||jsonb_build_object('memberships',coalesce((
  SELECT jsonb_agg(m.value||jsonb_build_object('accessEnabled',coalesce(s."Enabled",true),'accessRevision',coalesce(s."Revision",0),
   'organizationDelegationActive',flags.organization_active,
   'isCurrentIdentity',m.value->>'internalIdentityId'=current_setting('app.identity_subject',true),
   'canEnableAccess',(result->>'mode'='owner' OR
    (m.value->>'internalIdentityId'<>current_setting('app.identity_subject',true)
     AND NOT flags.organization_active AND NOT flags.mandate_active AND m.value->'active'<>'true'::jsonb))) ORDER BY m.ordinality)
  FROM jsonb_array_elements(result->'memberships') WITH ORDINALITY m(value,ordinality)
  LEFT JOIN organization_access.membership_access_state s ON s."MembershipId"=(m.value->>'membershipId')::uuid
   AND s."TenantId"=(result->>'tenantId')::uuid
  CROSS JOIN LATERAL (SELECT
   EXISTS(SELECT 1 FROM organization_access.organization_delegations d WHERE d."TenantId"=(result->>'tenantId')::uuid
    AND d."MembershipId"=(m.value->>'membershipId')::uuid AND d."Active"
    AND d."InternalIdentityId"::text=m.value->>'internalIdentityId'
    AND encode(d."BindingHash",'hex')=m.value->>'bindingHash') AS organization_active,
   EXISTS(SELECT 1 FROM organization_access.delegation_mandates d WHERE d."TenantId"=(result->>'tenantId')::uuid
    AND d."AdminMembershipId"=(m.value->>'membershipId')::uuid AND d."RevokedAt" IS NULL
    AND d."ValidFrom"<=statement_timestamp() AND d."ValidUntil">statement_timestamp()) AS mandate_active
  ) flags),'[]'::jsonb));
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

-- Private immutable applied-command history doubles as replay ledger.
CREATE TABLE organization_access.membership_access_audit (
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
CREATE UNIQUE INDEX membership_access_applied_command ON organization_access.membership_access_audit("CommandId") WHERE "Outcome"='applied';
ALTER TABLE organization_access.membership_access_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.membership_access_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_access_audit_owner ON organization_access.membership_access_audit TO CURRENT_USER USING(true) WITH CHECK(true);
REVOKE ALL ON organization_access.membership_access_audit FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_membership_access_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.membership_access_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION organization_access.apply_membership_access(target uuid, request jsonb, authority jsonb) RETURNS jsonb
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE key text; member_id uuid; revision integer; was_enabled boolean; after_data jsonb;
 previous organization_access.membership_access_audit;
 actor uuid:=current_setting('app.identity_subject')::uuid;
 actor_hash bytea:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
BEGIN
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','membershipId','internalIdentityId','bindingHash','expectedRevision','enabled']
  OR (SELECT count(*) FROM jsonb_object_keys(request))<>6 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','membershipId','internalIdentityId'] LOOP
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
   OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF jsonb_typeof(request->'enabled') IS DISTINCT FROM 'boolean'
  OR jsonb_typeof(request->'bindingHash') IS DISTINCT FROM 'string' OR request->>'bindingHash' !~ '^[0-9a-f]{64}$'
  OR jsonb_typeof(request->'expectedRevision') IS DISTINCT FROM 'number' OR request->>'expectedRevision' !~ '^(0|[1-9][0-9]{0,9})$'
 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF (request->>'expectedRevision')::bigint>2147483646 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 SELECT m."Id" INTO member_id FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
  ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."TenantId"=target AND m."Id"=(request->>'membershipId')::uuid
  AND b."InternalIdentityId"::text=request->>'internalIdentityId'
  AND encode(sha256(convert_to(jsonb_build_array(b."Issuer",b."Subject")::text,'UTF8')),'hex')=request->>'bindingHash' FOR SHARE OF m,b;
 IF member_id IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 -- Enable must not implicitly restore current administrative authority. Disable
 -- intentionally accepts privileged targets and self, without altering grants.
 IF authority->>'kind'<>'owner' AND request->'enabled'='true'::jsonb AND (
  request->>'internalIdentityId'=actor::text OR
  EXISTS(SELECT 1 FROM organization_access.organization_delegations d WHERE d."MembershipId"=member_id AND d."TenantId"=target
   AND d."Active" AND d."InternalIdentityId"::text=request->>'internalIdentityId' AND encode(d."BindingHash",'hex')=request->>'bindingHash') OR
  EXISTS(SELECT 1 FROM organization_access.tenant_role_objects d WHERE d."TenantId"=target AND d."Kind"='delegation'
   AND d."Data"->>'membershipId'=member_id::text AND d."Data"->'active'='true'::jsonb
   AND d."Data"->>'internalIdentityId'=request->>'internalIdentityId' AND d."Data"->>'bindingHash'=request->>'bindingHash') OR
  EXISTS(SELECT 1 FROM organization_access.delegation_mandates d WHERE d."TenantId"=target AND d."AdminMembershipId"=member_id
   AND d."RevokedAt" IS NULL AND d."ValidFrom"<=statement_timestamp() AND d."ValidUntil">statement_timestamp())
 ) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 -- Current actor and target binding checks precede lookup, including retries.
 SELECT * INTO previous FROM organization_access.membership_access_audit WHERE "CommandId"=(request->>'commandId')::uuid AND "Outcome"='applied';
 IF FOUND THEN
  IF previous."ActorId"=actor AND previous."BindingHash"=actor_hash AND previous."TenantId"=target AND previous."Request"=request
   THEN RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 SELECT "Enabled","Revision" INTO was_enabled,revision FROM organization_access.membership_access_state WHERE "MembershipId"=member_id AND "TenantId"=target FOR UPDATE;
 was_enabled:=coalesce(was_enabled,true); revision:=coalesce(revision,0);
 IF revision<>(request->>'expectedRevision')::integer OR revision=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 after_data:=jsonb_build_object('tenantId',target,'membershipId',member_id,'internalIdentityId',request->>'internalIdentityId','bindingHash',request->>'bindingHash','enabled',request->'enabled','revision',revision+1);
 INSERT INTO organization_access.membership_access_state VALUES(member_id,target,(request->>'enabled')::boolean,revision+1)
 ON CONFLICT("MembershipId") DO UPDATE SET "Enabled"=excluded."Enabled","Revision"=excluded."Revision";
 INSERT INTO organization_access.membership_access_audit("CommandId","ActorId","BindingHash","Authority","TenantId","ResourceId","Request","Before","After","Outcome")
 VALUES((request->>'commandId')::uuid,actor,actor_hash,authority,target,member_id,request,jsonb_build_object('enabled',was_enabled,'revision',revision),after_data,'applied');
 RETURN jsonb_build_object('state','applied','snapshot',after_data);
END $$;
REVOKE ALL ON FUNCTION organization_access.apply_membership_access(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";

CREATE FUNCTION organization_access.command_membership_access(target uuid, request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; authority jsonb; owner boolean; prior_target text:=current_setting('app.tenant_id',true); actor uuid;
BEGIN
 owner:=organization_access.lock_organization_actor();
 PERFORM set_config('app.tenant_id',coalesce(target::text,''),true);
 IF owner THEN SELECT jsonb_build_object('kind','owner','revision',"Revision") INTO authority FROM organization_access.platform_authority WHERE "Slot";
 ELSIF organization_access.current_membership_access(target) AND organization_access.lock_user_administrator(target) THEN
  SELECT jsonb_build_object('kind','user-administration','resourceId',d."Id",'revision',d."Revision") INTO authority
   FROM organization_access.tenant_role_objects d JOIN organization_access.memberships m ON d."Data"->>'membershipId'=m."Id"::text AND m."TenantId"=d."TenantId"
   WHERE d."Kind"='delegation' AND d."TenantId"=target AND m."IdentitySubject"=current_setting('app.identity_subject',true);
 END IF;
 IF authority IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.tenants WHERE "Id"=target) THEN result:=jsonb_build_object('state','forbidden');
 ELSE result:=organization_access.apply_membership_access(target,request,authority); END IF;
 IF result->>'state' IN ('forbidden','invalid','conflict') THEN
  SELECT "InternalIdentityId" INTO actor FROM organization_access.external_identity_bindings
   WHERE "InternalIdentityId"::text=current_setting('app.identity_subject',true)
    AND "Issuer"=current_setting('app.identity_issuer',true) COLLATE "C" AND "Subject"=current_setting('app.external_subject',true) COLLATE "C" FOR SHARE;
  IF actor IS NOT NULL THEN
   INSERT INTO organization_access.membership_access_audit("ActorId","BindingHash","Authority","Request","Before","After","Outcome")
   VALUES(actor,sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8')),coalesce(authority,'{}'::jsonb),'{}','{}','{}',result->>'state');
  END IF;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_target,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.command_membership_access(uuid,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.command_membership_access(uuid,jsonb) TO :"app_user";

-- Public user-derived SD entries acquire777036 BEFORE master-authority.
-- Keep existing authority/grants/replay bodies private and byte-preserved.
ALTER FUNCTION counterparties.common_edit_state(uuid,uuid) RENAME TO common_edit_state_before_access;
REVOKE ALL ON FUNCTION counterparties.common_edit_state_before_access(uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.common_edit_state(company_id uuid, record_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN counterparties.common_edit_state_before_access(company_id,record_id);
END $$;
REVOKE ALL ON FUNCTION counterparties.common_edit_state(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.common_edit_state(uuid,uuid) TO :"app_user";

ALTER FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) RENAME TO edit_common_before_access;
REVOKE ALL ON FUNCTION counterparties.edit_common_before_access(uuid,uuid,uuid,integer,integer,text,text,text) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.edit_common(company_id uuid, record_id uuid, command_id uuid, authority_version integer, expected_revision integer, legal_name text, fiscal_identifier text, registered_office text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN counterparties.edit_common_before_access(company_id,record_id,command_id,authority_version,expected_revision,legal_name,fiscal_identifier,registered_office);
END $$;
REVOKE ALL ON FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) TO :"app_user";

ALTER FUNCTION counterparties.purchase_suppliers(uuid) RENAME TO purchase_suppliers_before_access;
REVOKE ALL ON FUNCTION counterparties.purchase_suppliers_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.purchase_suppliers(company uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN counterparties.purchase_suppliers_before_access(company);
END $$;
REVOKE ALL ON FUNCTION counterparties.purchase_suppliers(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.purchase_suppliers(uuid) TO :"app_user";

ALTER FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) RENAME TO set_supplier_role_before_access;
REVOKE ALL ON FUNCTION counterparties.set_supplier_role_before_access(uuid,uuid,uuid,integer,integer,boolean) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.set_supplier_role(company_id uuid, record_id uuid, command_id uuid, authority_version integer, expected_revision integer, is_supplier boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF target IS NULL OR NOT organization_access.current_membership_access(target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN counterparties.set_supplier_role_before_access(company_id,record_id,command_id,authority_version,expected_revision,is_supplier);
END $$;
REVOKE ALL ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) TO :"app_user";

-- Direct application-role business SQL is user-derived, never a worker port.
-- Existing tenant/company policies still apply. Owner-only offline supplier
-- projection and private definer helpers are separately classified; no missing
-- identity branch is permitted for runtime_app. Definer user ingresses retain
-- their exact grant checks and require separate entry/lock-order acceptance.
CREATE POLICY membership_access_current ON counterparties.counterparties AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON counterparties.destinations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));

-- Current delegation and configurable-role origins share the same boundary.
ALTER FUNCTION organization_access.lock_user_administrator(uuid) RENAME TO lock_user_administrator_before_access;
REVOKE ALL ON FUNCTION organization_access.lock_user_administrator_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.lock_user_administrator(target uuid) RETURNS boolean
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(target) THEN RETURN false; END IF;
 RETURN organization_access.lock_user_administrator_before_access(target);
END $$;
REVOKE ALL ON FUNCTION organization_access.lock_user_administrator(uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.lock_organization_delegate(uuid) RENAME TO lock_organization_delegate_before_access;
REVOKE ALL ON FUNCTION organization_access.lock_organization_delegate_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.lock_organization_delegate(target uuid) RETURNS boolean
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(target) THEN RETURN false; END IF;
 RETURN organization_access.lock_organization_delegate_before_access(target);
END $$;
REVOKE ALL ON FUNCTION organization_access.lock_organization_delegate(uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.current_tenant_role_scopes() RENAME TO current_tenant_role_scopes_before_access;
REVOKE ALL ON FUNCTION organization_access.current_tenant_role_scopes_before_access() FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.current_tenant_role_scopes()
RETURNS TABLE("Id" uuid,"MembershipId" uuid,"TenantId" uuid,"LegalEntityId" uuid,"SiteId" uuid,"WarehouseId" uuid,"Permission" varchar(100))
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN; END IF;
 RETURN QUERY SELECT * FROM organization_access.current_tenant_role_scopes_before_access();
END $$;
REVOKE ALL ON FUNCTION organization_access.current_tenant_role_scopes() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.current_tenant_role_scopes() TO :"app_user";

CREATE POLICY membership_access_current ON organization_access.delegated_scopes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON organization_access.delegation_mandates AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId"))
 WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE OR REPLACE VIEW organization_access.effective_membership_scopes WITH (security_invoker=true) AS
 SELECT "Id","MembershipId","TenantId","LegalEntityId","SiteId","WarehouseId","Permission" FROM organization_access.membership_scopes
 UNION ALL
 SELECT d."Id",d."MembershipId",d."TenantId",d."LegalEntityId",d."SiteId",d."WarehouseId",d."Permission"
 FROM organization_access.delegated_scopes d JOIN organization_access.delegation_mandates m ON m."Id"=d."MandateId" AND m."TenantId"=d."TenantId"
 WHERE m."RevokedAt" IS NULL AND m."ValidFrom"<=statement_timestamp() AND m."ValidUntil">statement_timestamp()
 UNION ALL
 SELECT "Id","MembershipId","TenantId","LegalEntityId","SiteId","WarehouseId","Permission" FROM organization_access.current_tenant_role_scopes();

-- Workshop accepted-work ports are explicit persisted-envelope operations, NOT
-- a session/client flag or a missing-identity branch on new-user operations.
-- The existing tenant policy still applies to these narrowly bounded SD bodies.
CREATE FUNCTION workshop.read_accepted_administrative_request(tenant uuid, request uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,workshop AS $$
DECLARE result jsonb; prior_tenant text:=current_setting('app.tenant_id',true);
BEGIN
 PERFORM set_config('app.tenant_id',tenant::text,true);
 SELECT to_jsonb(r)||jsonb_build_object('Summary',r."Summary"::text,'Binding',to_jsonb(b)) INTO result
 FROM workshop.administrative_requests r
 JOIN workshop.administrative_outbox o ON o."RequestId"=r."Id" AND o."TenantId"=r."TenantId"
 LEFT JOIN workshop.administrative_bindings b ON
  (b."RequestId",b."TenantId",b."OrderId",b."LegalEntityId",b."SiteId",b."DestinationVersion",b."ContractVersion",b."RequestedAt",b."OperatorId")=
  (r."Id",r."TenantId",r."OrderId",r."LegalEntityId",r."SiteId",r."DestinationVersion",r."ContractVersion",r."RequestedAt",r."OperatorId")
 WHERE r."Id"=request AND r."TenantId"=tenant;
 PERFORM set_config('app.tenant_id',coalesce(prior_tenant,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION workshop.read_accepted_administrative_request(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.read_accepted_administrative_request(uuid,uuid) TO :"app_user";

CREATE FUNCTION workshop.record_accepted_administrative_outcome(tenant uuid, request uuid, status text, reference text, rejection text) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,workshop AS $$
DECLARE prior_tenant text:=current_setting('app.tenant_id',true); existing workshop.administrative_outcomes; inserted integer; result boolean;
BEGIN
 IF NOT coalesce((status='Confirmed' AND rejection IS NULL AND reference COLLATE "C" ~ '^[A-Za-z0-9][A-Za-z0-9-]{0,63}$')
  OR (status='Rejected' AND reference IS NULL AND rejection COLLATE "C" ~ '^[a-z0-9_]{1,64}$'),false) THEN RETURN false; END IF;
 PERFORM set_config('app.tenant_id',tenant::text,true);
 PERFORM pg_advisory_xact_lock(hashtextextended(request::text,0));
 -- An unbound historical request may be read for a controlled hold, never
 -- recorded as an accepted provider outcome or silently bound/backfilled.
 IF jsonb_typeof(workshop.read_accepted_administrative_request(tenant,request)->'Binding') IS DISTINCT FROM 'object' THEN
  PERFORM set_config('app.tenant_id',coalesce(prior_tenant,''),true); RETURN false;
 END IF;
 SELECT * INTO existing FROM workshop.administrative_outcomes WHERE "RequestId"=request AND "TenantId"=tenant;
 IF FOUND THEN
  result:=(existing."Status",existing."ExternalReference",existing."RejectionCode") IS NOT DISTINCT FROM (status,reference,rejection);
 ELSE
  INSERT INTO workshop.administrative_outcomes ("RequestId","TenantId","Status","ExternalReference","RejectionCode","RecordedAt")
   VALUES (request,tenant,status,reference,rejection,clock_timestamp()) ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS inserted=ROW_COUNT; result:=inserted=1;
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior_tenant,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION workshop.record_accepted_administrative_outcome(uuid,uuid,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.record_accepted_administrative_outcome(uuid,uuid,text,text,text) TO :"app_user";

-- Restrictive application-role membership AND the original tenant/domain rules.
-- SD accepted work has no operator membership requirement and cannot create new
-- requests/bindings/outbox, edit content, or cancel already accepted requests.
CREATE POLICY membership_access_current ON workshop.orders AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.document_types AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.line_policies AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.carcass_policies AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.commercial_lines AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.working_groups AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.order_notes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.editor_commands AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.workspace_history AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.technical_closures AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.installations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_destinations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_requests AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_bindings AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_outbox AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_outcomes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.administrative_closures AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.internal_billing_claims AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.own_actual_time_streams AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.own_actual_time_entries AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.own_actual_time_commands AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.own_actual_time_versions AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON workshop.actual_time_group_references AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));

-- Finite user-derived SECURITY DEFINER ingress. Guard BEFORE any resource,
-- master-authority, command or grant lock, on the SAME transaction.
-- Originals are private; neither a client flag nor absent identity selects work.
ALTER FUNCTION organization_access.grant_administration() RENAME TO grant_administration_before_access;
REVOKE ALL ON FUNCTION organization_access.grant_administration_before_access() FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.grant_administration() RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN '[]'::jsonb; END IF;
 RETURN organization_access.grant_administration_before_access();
END $$;
REVOKE ALL ON FUNCTION organization_access.grant_administration() FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.grant_administration() TO :"app_user";

ALTER FUNCTION organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) RENAME TO command_operative_grant_before_access;
REVOKE ALL ON FUNCTION organization_access.command_operative_grant_before_access(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.command_operative_grant(command_id uuid,mandate_id uuid,target_id uuid,tenant_id uuid,company_id uuid,site_id uuid,warehouse_id uuid,action_name text,operation_name text) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN 'forbidden'; END IF;
 RETURN organization_access.command_operative_grant_before_access($1,$2,$3,$4,$5,$6,$7,$8,$9);
END $$;
REVOKE ALL ON FUNCTION organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) TO :"app_user";

ALTER FUNCTION organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) RENAME TO inventory_release_authorized_before_access;
REVOKE ALL ON FUNCTION organization_access.inventory_release_authorized_before_access(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.inventory_release_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid, warehouse uuid, require_write boolean) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN false; END IF;
 RETURN organization_access.inventory_release_authorized_before_access($1,$2,$3,$4,$5,$6,$7);
END $$;
REVOKE ALL ON FUNCTION organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) TO :"app_user";

ALTER FUNCTION organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) RENAME TO inventory_new_return_authorized_before_access;
REVOKE ALL ON FUNCTION organization_access.inventory_new_return_authorized_before_access(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.inventory_new_return_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid, warehouse uuid, require_write boolean) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN false; END IF;
 RETURN organization_access.inventory_new_return_authorized_before_access($1,$2,$3,$4,$5,$6,$7);
END $$;
REVOKE ALL ON FUNCTION organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean) TO :"app_user";

ALTER FUNCTION organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid) RENAME TO administrative_request_authorized_before_access;
REVOKE ALL ON FUNCTION organization_access.administrative_request_authorized_before_access(uuid,uuid,text,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.administrative_request_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN false; END IF;
 RETURN organization_access.administrative_request_authorized_before_access($1,$2,$3,$4,$5);
END $$;
REVOKE ALL ON FUNCTION organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid) TO :"app_user";

ALTER FUNCTION catalog.supplier_purchase_price_state(uuid,uuid,uuid) RENAME TO supplier_purchase_price_state_before_access;
REVOKE ALL ON FUNCTION catalog.supplier_purchase_price_state_before_access(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION catalog.supplier_purchase_price_state(company uuid,supplier uuid,item uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN catalog.supplier_purchase_price_state_before_access($1,$2,$3);
END $$;
REVOKE ALL ON FUNCTION catalog.supplier_purchase_price_state(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION catalog.supplier_purchase_price_state(uuid,uuid,uuid) TO :"app_user";

ALTER FUNCTION catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) RENAME TO set_supplier_purchase_price_before_access;
REVOKE ALL ON FUNCTION catalog.set_supplier_purchase_price_before_access(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) FROM PUBLIC, :"app_user";
CREATE FUNCTION catalog.set_supplier_purchase_price(company uuid,supplier uuid,item uuid,command uuid,expected integer,supplier_revision integer,catalog_version integer,authority_version integer,price_text text) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN catalog.set_supplier_purchase_price_before_access($1,$2,$3,$4,$5,$6,$7,$8,$9);
END $$;
REVOKE ALL ON FUNCTION catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) TO :"app_user";

ALTER FUNCTION catalog.purchase_intent_quote(uuid,uuid,uuid,uuid) RENAME TO purchase_intent_quote_before_access;
REVOKE ALL ON FUNCTION catalog.purchase_intent_quote_before_access(uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION catalog.purchase_intent_quote(ord uuid,line uuid,warehouse uuid,supplier uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN catalog.purchase_intent_quote_before_access($1,$2,$3,$4);
END $$;
REVOKE ALL ON FUNCTION catalog.purchase_intent_quote(uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION catalog.purchase_intent_quote(uuid,uuid,uuid,uuid) TO :"app_user";

ALTER FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) RENAME TO purchase_intent_state_before_access;
REVOKE ALL ON FUNCTION inventory.purchase_intent_state_before_access(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.purchase_intent_state(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.purchase_intent_state_before_access($1,$2,$3);
END $$;
REVOKE ALL ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.purchase_intent_state(uuid,uuid,uuid) TO :"app_user";

ALTER FUNCTION inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) RENAME TO create_purchase_intent_before_access;
REVOKE ALL ON FUNCTION inventory.create_purchase_intent_before_access(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.create_purchase_intent(command uuid,ord uuid,line uuid,warehouse uuid,supplier uuid, revision integer,role_revision integer,mapping_revision integer,quantity_text text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.create_purchase_intent_before_access($1,$2,$3,$4,$5,$6,$7,$8,$9,$10);
END $$;
REVOKE ALL ON FUNCTION inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb) TO :"app_user";

ALTER FUNCTION inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) RENAME TO accept_purchase_intent_before_access;
REVOKE ALL ON FUNCTION inventory.accept_purchase_intent_before_access(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.accept_purchase_intent(command uuid,ord uuid,line uuid,warehouse uuid,supplier uuid, revision integer,role_revision integer,mapping_revision integer,quantity_text text,quote_revision integer,catalog_version integer,authority_version integer,manual_price text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.accept_purchase_intent_before_access($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14);
END $$;
REVOKE ALL ON FUNCTION inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb) TO :"app_user";

ALTER FUNCTION inventory.create_receipt_intent(uuid,uuid,text,jsonb) RENAME TO create_receipt_intent_before_access;
REVOKE ALL ON FUNCTION inventory.create_receipt_intent_before_access(uuid,uuid,text,jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.create_receipt_intent(command uuid,source_intent uuid,quantity_text text,destination jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.create_receipt_intent_before_access($1,$2,$3,$4);
END $$;
REVOKE ALL ON FUNCTION inventory.create_receipt_intent(uuid,uuid,text,jsonb) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.create_receipt_intent(uuid,uuid,text,jsonb) TO :"app_user";

ALTER FUNCTION inventory.receipt_state(uuid) RENAME TO receipt_state_before_access;
REVOKE ALL ON FUNCTION inventory.receipt_state_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.receipt_state(source_intent uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.receipt_state_before_access($1);
END $$;
REVOKE ALL ON FUNCTION inventory.receipt_state(uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.receipt_state(uuid) TO :"app_user";

ALTER FUNCTION inventory.receipt_sources(uuid,uuid,uuid) RENAME TO receipt_sources_before_access;
REVOKE ALL ON FUNCTION inventory.receipt_sources_before_access(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.receipt_sources(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.receipt_sources_before_access($1,$2,$3);
END $$;
REVOKE ALL ON FUNCTION inventory.receipt_sources(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION inventory.receipt_sources(uuid,uuid,uuid) TO :"app_user";

ALTER FUNCTION organization_access.read_master_authority(uuid) RENAME TO read_master_authority_before_access;
REVOKE ALL ON FUNCTION organization_access.read_master_authority_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_master_authority(company_id uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN organization_access.read_master_authority_before_access($1);
END $$;
REVOKE ALL ON FUNCTION organization_access.read_master_authority(uuid) FROM PUBLIC, :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.read_master_authority(uuid) TO :"app_user";

ALTER FUNCTION organization_access.purchasing_identity() RENAME TO purchasing_identity_before_access;
REVOKE ALL ON FUNCTION organization_access.purchasing_identity_before_access() FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.purchasing_identity() RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN NULL; END IF;
 RETURN organization_access.purchasing_identity_before_access();
END $$;
REVOKE ALL ON FUNCTION organization_access.purchasing_identity() FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.purchasing_authority(uuid,uuid,uuid) RENAME TO purchasing_authority_before_access;
REVOKE ALL ON FUNCTION organization_access.purchasing_authority_before_access(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.purchasing_authority(company uuid,site uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN organization_access.purchasing_authority_before_access($1,$2,$3);
END $$;
REVOKE ALL ON FUNCTION organization_access.purchasing_authority(uuid,uuid,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.purchase_price_member(uuid) RENAME TO purchase_price_member_before_access;
REVOKE ALL ON FUNCTION organization_access.purchase_price_member_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.purchase_price_member(company uuid) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN NULL; END IF;
 RETURN organization_access.purchase_price_member_before_access($1);
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_price_member(uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.purchase_price_writable(uuid) RENAME TO purchase_price_writable_before_access;
REVOKE ALL ON FUNCTION organization_access.purchase_price_writable_before_access(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.purchase_price_writable(company uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN false; END IF;
 RETURN organization_access.purchase_price_writable_before_access($1);
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_price_writable(uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.receipt_member(uuid,uuid,uuid,uuid,boolean) RENAME TO receipt_member_before_access;
REVOKE ALL ON FUNCTION organization_access.receipt_member_before_access(uuid,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.receipt_member(tenant uuid,company uuid,site uuid,warehouse uuid,writable boolean) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN NULL; END IF;
 RETURN organization_access.receipt_member_before_access($1,$2,$3,$4,$5);
END $$;
REVOKE ALL ON FUNCTION organization_access.receipt_member(uuid,uuid,uuid,uuid,boolean) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.purchase_intent_authorized(uuid,uuid,uuid,uuid,uuid) RENAME TO purchase_intent_authorized_before_access;
REVOKE ALL ON FUNCTION organization_access.purchase_intent_authorized_before_access(uuid,uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.purchase_intent_authorized(tenant uuid,member uuid,company uuid,site uuid,warehouse uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN false; END IF;
 RETURN organization_access.purchase_intent_authorized_before_access($1,$2,$3,$4,$5);
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_intent_authorized(uuid,uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION inventory.purchasing_source_context(uuid,uuid,uuid) RENAME TO purchasing_source_context_before_access;
REVOKE ALL ON FUNCTION inventory.purchasing_source_context_before_access(uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.purchasing_source_context(ord uuid,line uuid,warehouse uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.purchasing_source_context_before_access($1,$2,$3);
END $$;
REVOKE ALL ON FUNCTION inventory.purchasing_source_context(uuid,uuid,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION inventory.purchasing_context(uuid,uuid,uuid,uuid) RENAME TO purchasing_context_before_access;
REVOKE ALL ON FUNCTION inventory.purchasing_context_before_access(uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION inventory.purchasing_context(ord uuid,line uuid,warehouse uuid,supplier uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,inventory,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN inventory.purchasing_context_before_access($1,$2,$3,$4);
END $$;
REVOKE ALL ON FUNCTION inventory.purchasing_context(uuid,uuid,uuid,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION catalog.purchasing_price(jsonb) RENAME TO purchasing_price_before_access;
REVOKE ALL ON FUNCTION catalog.purchasing_price_before_access(jsonb) FROM PUBLIC, :"app_user";
CREATE FUNCTION catalog.purchasing_price(context jsonb) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN catalog.purchasing_price_before_access($1);
END $$;
REVOKE ALL ON FUNCTION catalog.purchasing_price(jsonb) FROM PUBLIC, :"app_user";

-- Business table access by the application always requires a current operator.
-- Accepted purchase/receipt dispatch remains confined to existing SD ports,
-- which can only project/record already persisted frozen requests.
CREATE POLICY membership_access_current ON vehicles.vehicles AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON catalog.items AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.stock AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.reservations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.picking_policies AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.picking_locations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.picks AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.consumptions AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.carcass_locations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.carcass_returns AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.carcass_return_installations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON billing.document_types AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON billing.issuer_profiles AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON billing.invoices AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON billing.invoice_confirmations AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON billing.invoice_journal_links AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON accounting.chart_accounts AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON accounting.journal_entries AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON accounting.journal_entry_lines AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.reservation_releases AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.new_part_returns AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.purchase_intents AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.purchase_intent_outbox AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON catalog.supplier_purchase_price_history AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.purchase_intent_prices AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.purchase_intent_outcomes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.receipt_intents AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.receipt_outbox AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));
CREATE POLICY membership_access_current ON inventory.receipt_outcomes AS RESTRICTIVE TO :"app_user"
 USING (organization_access.current_membership_access("TenantId")) WITH CHECK (organization_access.current_membership_access("TenantId"));

-- Company-specific supplier identity read is another public user-derived SD
-- ingress; it must acquire the access boundary before the master lock too.
ALTER FUNCTION counterparties.read_giobby_vendor_identity(uuid,uuid) RENAME TO read_giobby_vendor_identity_before_access;
REVOKE ALL ON FUNCTION counterparties.read_giobby_vendor_identity_before_access(uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.read_giobby_vendor_identity(company_id uuid,record_id uuid) RETURNS jsonb
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,counterparties,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 RETURN counterparties.read_giobby_vendor_identity_before_access(company_id,record_id);
END $$;
REVOKE ALL ON FUNCTION counterparties.read_giobby_vendor_identity(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.read_giobby_vendor_identity(uuid,uuid) TO :"app_user";

-- Existing owner-offline grant functions remain owner-only; the restrictive
-- grant-table policies above target the application, not the trusted migration
-- owner. Every user-derived public definer independently verifies current access.
-- Stock-profile read is the remaining metadata ingress, not an accepted worker.
ALTER FUNCTION organization_access.company_stock_profile(uuid,uuid) RENAME TO company_stock_profile_before_access;
REVOKE ALL ON FUNCTION organization_access.company_stock_profile_before_access(uuid,uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.company_stock_profile(tenant_id uuid,company_id uuid) RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(tenant_id) THEN RETURN 'missing'; END IF;
 RETURN organization_access.company_stock_profile_before_access(tenant_id,company_id);
END $$;
REVOKE ALL ON FUNCTION organization_access.company_stock_profile(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.company_stock_profile(uuid,uuid) TO :"app_user";
