-- D76 company-owned STOCK, deliberately separate from tenant-wide counterparties master.
-- Initial setup only: immutable version 1; authority switching is not a runtime workflow.
-- No business seeds, pilot values, provider calls, provisioning or delegated setup rights.
CREATE TABLE organization_access.company_stock_profiles (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "LegalEntityId" uuid NOT NULL,
 "Domain" text NOT NULL CHECK ("Domain"='stock'),
 "Version" integer NOT NULL CHECK ("Version"=1),
 "Direction" text NOT NULL CHECK ("Direction" IN ('Enginia360ToExternal','ExternalToEnginia360')),
 "SourceId" uuid NOT NULL CHECK ("SourceId"<>'00000000-0000-0000-0000-000000000000'),
 "ProfileId" uuid NOT NULL CHECK ("ProfileId"<>'00000000-0000-0000-0000-000000000000'),
 "ActorMembershipId" uuid NOT NULL,
 "VerificationReference" uuid NOT NULL CHECK ("VerificationReference"<>'00000000-0000-0000-0000-000000000000'),
 "EffectiveFrom" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","LegalEntityId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId"),
 FOREIGN KEY("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId")
);
ALTER TABLE organization_access.company_stock_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.company_stock_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON organization_access.company_stock_profiles
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE TRIGGER immutable_stock_profile BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.company_stock_profiles
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

-- Owning-module public SQL interfaces: setup does not inspect foreign private tables.
CREATE FUNCTION inventory.company_has_material_facts(tenant_id uuid,company_id uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,inventory AS $$
 SELECT EXISTS(SELECT 1 FROM inventory.reservations WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id)
 OR EXISTS(SELECT 1 FROM inventory.picks WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id)
 OR EXISTS(SELECT 1 FROM inventory.consumptions WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id)
 OR EXISTS(SELECT 1 FROM inventory.carcass_returns WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id)
$$;
CREATE FUNCTION workshop.company_has_installations(tenant_id uuid,company_id uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY INVOKER SET search_path=pg_catalog,workshop AS $$
 SELECT EXISTS(SELECT 1 FROM workshop.installations WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id)
$$;
REVOKE ALL ON FUNCTION inventory.company_has_material_facts(uuid,uuid),workshop.company_has_installations(uuid,uuid) FROM PUBLIC;

CREATE FUNCTION organization_access.establish_stock_profile(command_id uuid,tenant_id uuid,company_id uuid,actor_id uuid,verification_id uuid,direction_name text,source_id uuid,profile_id uuid) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE previous organization_access.company_stock_profiles; BEGIN
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN
  RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501';
 END IF;
 IF tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('stock-profile:'||tenant_id::text||':'||company_id::text,0));
 IF NOT EXISTS(SELECT 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=actor_id AND m."TenantId"=tenant_id) THEN RETURN 'forbidden'; END IF;
 SELECT * INTO previous FROM organization_access.company_stock_profiles WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id;
 IF FOUND THEN
  RETURN CASE WHEN previous."CommandId"=command_id AND previous."ActorMembershipId"=actor_id AND previous."VerificationReference"=verification_id AND previous."Direction"=direction_name AND previous."SourceId"=source_id AND previous."ProfileId"=profile_id THEN 'replayed' ELSE 'stock_profile_immutable' END;
 END IF;
 -- Immutable initial local authority must precede every local material fact.
 -- Legacy Pending without original authority is a controlled refusal, not a local fallback.
 IF direction_name='Enginia360ToExternal' AND (inventory.company_has_material_facts(tenant_id,company_id) OR workshop.company_has_installations(tenant_id,company_id)) THEN RETURN 'original_stock_profile_missing'; END IF;
 INSERT INTO organization_access.company_stock_profiles("CommandId","TenantId","LegalEntityId","Domain","Version","Direction","SourceId","ProfileId","ActorMembershipId","VerificationReference")
 VALUES(command_id,tenant_id,company_id,'stock',1,direction_name,source_id,profile_id,actor_id,verification_id);
 RETURN 'applied';
EXCEPTION WHEN unique_violation OR foreign_key_violation OR check_violation OR not_null_violation THEN RETURN 'conflict';
END $$;

-- Public owning-module SQL projection. Caller already has verified tenant/action context.
CREATE FUNCTION organization_access.company_stock_profile(tenant_id uuid,company_id uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
 SELECT CASE WHEN tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) THEN 'missing'
 ELSE coalesce((SELECT CASE WHEN "Direction"='Enginia360ToExternal' THEN 'local' ELSE 'external' END
 FROM organization_access.company_stock_profiles WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id),'missing') END
$$;
REVOKE ALL ON organization_access.company_stock_profiles FROM PUBLIC;
REVOKE ALL ON FUNCTION organization_access.establish_stock_profile(uuid,uuid,uuid,uuid,uuid,text,uuid,uuid),organization_access.company_stock_profile(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.company_stock_profile(uuid,uuid) TO :"app_user";
