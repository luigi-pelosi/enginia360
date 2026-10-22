-- D77: bounded operative delegation only. No seed, default mandate or provisioning.
CREATE TABLE organization_access.delegation_mandates (
    "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
    "TenantId" uuid NOT NULL,
    "AdminMembershipId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Action" text NOT NULL CHECK ("Action" IN ('organization-context.read','organization-context.write')),
    "ValidFrom" timestamptz NOT NULL,
    "ValidUntil" timestamptz NOT NULL CHECK ("ValidUntil" > "ValidFrom"),
    "RevokedAt" timestamptz,
    FOREIGN KEY ("AdminMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId") ON DELETE CASCADE,
    FOREIGN KEY ("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId") ON DELETE CASCADE
);
CREATE TABLE organization_access.delegated_scopes (
    "Id" uuid PRIMARY KEY,
    "MembershipId" uuid NOT NULL,
    "TenantId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Permission" text NOT NULL CHECK ("Permission" IN ('organization-context.read','organization-context.write')),
    "MandateId" uuid NOT NULL REFERENCES organization_access.delegation_mandates("Id") ON DELETE CASCADE,
    UNIQUE ("MembershipId","LegalEntityId","SiteId","WarehouseId","Permission"),
    FOREIGN KEY ("MembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId") ON DELETE CASCADE,
    FOREIGN KEY ("WarehouseId","SiteId","LegalEntityId","TenantId") REFERENCES organization_access.warehouses("Id","SiteId","LegalEntityId","TenantId") ON DELETE CASCADE
);
CREATE TABLE organization_access.grant_commands (
    "CommandId" uuid PRIMARY KEY,
    "TenantId" uuid NOT NULL,
    "ActorMembershipId" uuid NOT NULL,
    "MandateId" uuid NOT NULL,
    "TargetMembershipId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Action" text NOT NULL,
    "Operation" text NOT NULL CHECK ("Operation" IN ('grant','revoke'))
);
-- No identity subjects, issuer, tokens, email, note content or untrusted strings.
CREATE TABLE organization_access.delegation_audit (
    "Id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
    "TenantId" uuid NOT NULL,
    "ActorId" uuid NOT NULL,
    "CommandId" uuid,
    "MandateId" uuid NOT NULL,
    "TargetMembershipId" uuid NOT NULL,
    "LegalEntityId" uuid NOT NULL,
    "SiteId" uuid NOT NULL,
    "WarehouseId" uuid NOT NULL,
    "Action" text NOT NULL CHECK ("Action" IN ('organization-context.read','organization-context.write','unsupported')),
    "Operation" text NOT NULL CHECK ("Operation" IN ('grant','revoke','mandate-create','mandate-revoke')),
    "Result" text NOT NULL CHECK ("Result" IN ('applied','replayed','conflict','forbidden'))
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['delegation_mandates','delegated_scopes','grant_commands','delegation_audit'] LOOP
  EXECUTE format('ALTER TABLE organization_access.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE organization_access.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY tenant_identity ON organization_access.%I USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',t);
 END LOOP;
 -- Definer is the nonprivileged database owner, not a BYPASSRLS/service role.
 -- Only definer routines can inspect other trusted memberships. Web role keeps own-only RLS.
 EXECUTE format('CREATE POLICY delegation_owner_memberships ON organization_access.memberships TO %I USING ("TenantId"::text=current_setting(''app.tenant_id'',true))',current_user);
 EXECUTE format('CREATE POLICY delegation_owner_bindings ON organization_access.external_identity_bindings TO %I USING (true)',current_user);
END $$;

CREATE FUNCTION organization_access.immutable_delegation_audit() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$ BEGIN
 RAISE EXCEPTION 'delegation audit is append-only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER immutable_delegation_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.delegation_audit
FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION organization_access.audit_owner_mandate() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE actor uuid; BEGIN
 actor := nullif(current_setting('app.owner_actor',true),'')::uuid;
 IF actor IS NULL OR actor='00000000-0000-0000-0000-000000000000'::uuid THEN
  RAISE EXCEPTION 'explicit verified owner actor required' USING ERRCODE='42501';
 END IF;
 IF TG_OP='UPDATE' AND ((to_jsonb(OLD)-'RevokedAt') <> (to_jsonb(NEW)-'RevokedAt') OR OLD."RevokedAt" IS NOT NULL OR NEW."RevokedAt" IS NULL) THEN
  RAISE EXCEPTION 'mandate immutable; renewal requires a new explicit mandate' USING ERRCODE='42501';
 END IF;
 IF TG_OP='INSERT' AND NOT EXISTS (SELECT 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON m."IdentitySubject"=b."InternalIdentityId"::text WHERE m."Id"=NEW."AdminMembershipId" AND m."TenantId"=NEW."TenantId") THEN
  RAISE EXCEPTION 'mandate requires existing trusted membership' USING ERRCODE='23514';
 END IF;
 INSERT INTO organization_access.delegation_audit("TenantId","ActorId","MandateId","TargetMembershipId","LegalEntityId","SiteId","WarehouseId","Action","Operation","Result")
 VALUES (NEW."TenantId",actor,NEW."Id",NEW."AdminMembershipId",NEW."LegalEntityId",NEW."SiteId",NEW."WarehouseId",NEW."Action",CASE WHEN TG_OP='INSERT' THEN 'mandate-create' ELSE 'mandate-revoke' END,'applied');
 RETURN NEW;
END $$;
CREATE TRIGGER audit_owner_mandate BEFORE INSERT OR UPDATE ON organization_access.delegation_mandates
FOR EACH ROW EXECUTE FUNCTION organization_access.audit_owner_mandate();

-- Security-invoker view preserves tenant RLS and applies expiry/revocation on EVERY read.
-- Delegation never changes root grants, entitlement, activation or other module permissions.
CREATE VIEW organization_access.effective_membership_scopes WITH (security_invoker=true) AS
 SELECT "Id","MembershipId","TenantId","LegalEntityId","SiteId","WarehouseId","Permission" FROM organization_access.membership_scopes
 UNION ALL
 SELECT d."Id",d."MembershipId",d."TenantId",d."LegalEntityId",d."SiteId",d."WarehouseId",d."Permission"
 FROM organization_access.delegated_scopes d JOIN organization_access.delegation_mandates m ON m."Id"=d."MandateId" AND m."TenantId"=d."TenantId"
 WHERE m."RevokedAt" IS NULL AND m."ValidFrom"<=statement_timestamp() AND m."ValidUntil">statement_timestamp();

CREATE FUNCTION organization_access.grant_administration() RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
 SELECT coalesce(jsonb_agg(jsonb_build_object('mandateId',d."Id",'tenantId',d."TenantId",'legalEntityId',d."LegalEntityId",'siteId',d."SiteId",'warehouseId',d."WarehouseId",'action',d."Action",'validUntil',d."ValidUntil",'targetMembershipId',t."Id",'granted',EXISTS(SELECT 1 FROM organization_access.delegated_scopes s WHERE s."MandateId"=d."Id" AND s."MembershipId"=t."Id"))), '[]'::jsonb)
 FROM organization_access.delegation_mandates d
 JOIN organization_access.memberships a ON a."Id"=d."AdminMembershipId" AND a."IdentitySubject"=current_setting('app.identity_subject',true)
 JOIN organization_access.external_identity_bindings ab ON ab."InternalIdentityId"::text=a."IdentitySubject"
 JOIN organization_access.memberships t ON t."TenantId"=a."TenantId" AND t."Id"<>a."Id"
 JOIN organization_access.external_identity_bindings tb ON tb."InternalIdentityId"::text=t."IdentitySubject"
 WHERE d."RevokedAt" IS NULL AND d."ValidFrom"<=statement_timestamp() AND d."ValidUntil">statement_timestamp();
$$;

CREATE FUNCTION organization_access.command_operative_grant(command_id uuid,mandate_id uuid,target_id uuid,tenant_id uuid,company_id uuid,site_id uuid,warehouse_id uuid,action_name text,operation_name text) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE m organization_access.delegation_mandates; a uuid; previous organization_access.grant_commands; result text := 'forbidden'; existing uuid; replacing_inactive boolean := false; BEGIN
 SELECT "Id" INTO a FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true) AND "TenantId"=tenant_id;
 IF a IS NULL OR command_id IS NULL OR command_id='00000000-0000-0000-0000-000000000000'::uuid OR operation_name NOT IN ('grant','revoke') THEN RETURN 'forbidden'; END IF;
 -- Consistent order: command ID -> mandate row -> exact resource. Root revocation UPDATE
 -- locks the same row, so a command cannot commit after an earlier committed revocation.
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,0));
 SELECT * INTO m FROM organization_access.delegation_mandates WHERE "Id"=mandate_id AND "TenantId"=tenant_id AND "AdminMembershipId"=a FOR UPDATE;
 IF FOUND AND m."RevokedAt" IS NULL AND m."ValidFrom"<=clock_timestamp() AND m."ValidUntil">clock_timestamp()
    AND EXISTS (SELECT 1 FROM organization_access.memberships x JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=x."IdentitySubject" WHERE x."Id"=a) THEN
  SELECT * INTO previous FROM organization_access.grant_commands WHERE "CommandId"=command_id;
  IF FOUND THEN
   result := CASE WHEN previous."ActorMembershipId"=a AND previous."MandateId"=mandate_id AND previous."TargetMembershipId"=target_id AND previous."TenantId"=tenant_id AND previous."LegalEntityId"=company_id AND previous."SiteId"=site_id AND previous."WarehouseId"=warehouse_id AND previous."Action"=action_name AND previous."Operation"=operation_name THEN 'replayed' ELSE 'conflict' END;
  ELSIF target_id<>a AND m."LegalEntityId"=company_id AND m."SiteId"=site_id AND m."WarehouseId"=warehouse_id AND m."Action"=action_name
   AND EXISTS (SELECT 1 FROM organization_access.memberships t JOIN organization_access.external_identity_bindings b ON t."IdentitySubject"=b."InternalIdentityId"::text WHERE t."Id"=target_id AND t."TenantId"=tenant_id) THEN
   PERFORM pg_advisory_xact_lock(hashtextextended(tenant_id::text||target_id::text||company_id::text||site_id::text||warehouse_id::text||action_name,1));
   SELECT "MandateId" INTO existing FROM organization_access.delegated_scopes WHERE "MembershipId"=target_id AND "LegalEntityId"=company_id AND "SiteId"=site_id AND "WarehouseId"=warehouse_id AND "Permission"=action_name;
   replacing_inactive := operation_name='grant' AND existing IS NOT NULL AND EXISTS (
    SELECT 1 FROM organization_access.delegation_mandates old WHERE old."Id"=existing
    AND (old."RevokedAt" IS NOT NULL OR old."ValidUntil"<=clock_timestamp()));
   IF EXISTS (SELECT 1 FROM organization_access.membership_scopes WHERE "MembershipId"=target_id AND "LegalEntityId"=company_id AND "SiteId"=site_id AND "WarehouseId"=warehouse_id AND "Permission"=action_name)
    OR (existing IS NOT NULL AND NOT replacing_inactive AND (existing<>mandate_id OR operation_name='grant')) THEN result := 'conflict';
   ELSE
    BEGIN
     INSERT INTO organization_access.grant_commands VALUES(command_id,tenant_id,a,mandate_id,target_id,company_id,site_id,warehouse_id,action_name,operation_name);
     IF replacing_inactive THEN
      -- Only this new, explicit command under a live owner mandate can replace an
      -- ineffective row. Never replace a root/active/future mandate or renew implicitly.
      DELETE FROM organization_access.delegated_scopes WHERE "MembershipId"=target_id AND "MandateId"=existing AND "LegalEntityId"=company_id AND "SiteId"=site_id AND "WarehouseId"=warehouse_id AND "Permission"=action_name;
     END IF;
     IF operation_name='grant' THEN
      INSERT INTO organization_access.delegated_scopes VALUES(gen_random_uuid(),target_id,tenant_id,company_id,site_id,warehouse_id,action_name,mandate_id);
     ELSE
      DELETE FROM organization_access.delegated_scopes WHERE "MembershipId"=target_id AND "MandateId"=mandate_id AND "LegalEntityId"=company_id AND "SiteId"=site_id AND "WarehouseId"=warehouse_id AND "Permission"=action_name;
     END IF;
     result := 'applied';
    EXCEPTION WHEN unique_violation THEN result := 'conflict'; END;
   END IF;
  END IF;
 END IF;
 INSERT INTO organization_access.delegation_audit("TenantId","ActorId","CommandId","MandateId","TargetMembershipId","LegalEntityId","SiteId","WarehouseId","Action","Operation","Result")
 VALUES(tenant_id,a,command_id,mandate_id,target_id,company_id,site_id,warehouse_id,CASE WHEN action_name IN ('organization-context.read','organization-context.write') THEN action_name ELSE 'unsupported' END,operation_name,result);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.immutable_delegation_audit(),organization_access.audit_owner_mandate(),organization_access.grant_administration(),organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) FROM PUBLIC;
REVOKE ALL ON organization_access.delegation_mandates,organization_access.delegated_scopes,organization_access.grant_commands,organization_access.delegation_audit FROM PUBLIC;
GRANT SELECT ON organization_access.delegation_mandates,organization_access.delegated_scopes,organization_access.effective_membership_scopes TO :"app_user";
GRANT EXECUTE ON FUNCTION organization_access.grant_administration(),organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text) TO :"app_user";
