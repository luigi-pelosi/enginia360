-- D26/D65: one actual tenant-wide authority, not one direction per company.
-- Owner-only atomic decisions. Company references select the SAME technical source/profile.
-- No provider credentials, pilot values, ERP calls, identity provisioning or new delegation.
CREATE TABLE organization_access.master_authority_history (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Domain" text NOT NULL DEFAULT 'counterparties' CHECK ("Domain"='counterparties'),
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
ALTER TABLE organization_access.master_authority_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.master_authority_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON organization_access.master_authority_history
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE TRIGGER immutable_master_authority BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.master_authority_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION organization_access.establish_master_authority(command_id uuid,tenant_id uuid,actor_id uuid,verification_id uuid,expected_version integer,direction_name text,source_id uuid,profile_id uuid,company_ids uuid[]) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE previous organization_access.master_authority_history; version_now integer; BEGIN
 -- Invoker, no app EXECUTE; never a web/admin privilege or self-attested claim.
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN
  RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501';
 END IF;
 IF tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||tenant_id::text,0));
 IF NOT EXISTS(SELECT 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=actor_id AND m."TenantId"=tenant_id) THEN RETURN 'forbidden'; END IF;
 SELECT * INTO previous FROM organization_access.master_authority_history WHERE "CommandId"=command_id;
 IF FOUND THEN
  RETURN CASE WHEN previous."TenantId"=tenant_id AND previous."ActorMembershipId"=actor_id AND previous."VerificationReference"=verification_id AND previous."Version"::bigint=expected_version::bigint+1 AND previous."Direction"=direction_name AND previous."SourceId"=source_id AND previous."ProfileId"=profile_id AND previous."CompanyIds"=company_ids THEN 'replayed' ELSE 'conflict' END;
 END IF;
 SELECT coalesce(max("Version"),0) INTO version_now FROM organization_access.master_authority_history WHERE "TenantId"=tenant_id;
 IF expected_version IS DISTINCT FROM version_now THEN RETURN 'conflict'; END IF;
 IF company_ids IS NULL OR cardinality(company_ids)=0 OR EXISTS(SELECT 1 FROM unnest(company_ids) c WHERE c IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.legal_entities le WHERE le."Id"=c AND le."TenantId"=tenant_id)) OR cardinality(company_ids)<>(SELECT count(DISTINCT c) FROM unnest(company_ids) c) THEN RETURN 'conflict'; END IF;
 INSERT INTO organization_access.master_authority_history("CommandId","TenantId","Version","Direction","SourceId","ProfileId","CompanyIds","ActorMembershipId","VerificationReference")
 VALUES(command_id,tenant_id,version_now+1,direction_name,source_id,profile_id,company_ids,actor_id,verification_id);
 RETURN 'applied';
END $$;

CREATE FUNCTION organization_access.read_master_authority(company_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE h organization_access.master_authority_history; member_id uuid; tenant_id uuid; editable boolean; BEGIN
 SELECT "Id","TenantId" INTO member_id,tenant_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 IF member_id IS NULL OR NOT EXISTS(SELECT 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id AND p."LegalEntityId"=company_id AND p."Permission"='counterparties.read' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT * INTO h FROM organization_access.master_authority_history WHERE "TenantId"=tenant_id ORDER BY "Version" DESC LIMIT 1;
 editable:=EXISTS(SELECT 1 FROM organization_access.common_edit_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id);
 IF h."Version" IS NULL OR NOT company_id=ANY(h."CompanyIds") THEN RETURN jsonb_build_object('state','missing','canEdit',editable); END IF;
 RETURN jsonb_build_object('state',CASE WHEN h."Direction"='Enginia360ToExternal' THEN 'local' ELSE 'external' END,'version',h."Version",'direction',h."Direction",'sourceId',h."SourceId",'profileId',h."ProfileId",'effectiveFrom',h."EffectiveFrom",'canEdit',editable);
END $$;
REVOKE ALL ON organization_access.master_authority_history FROM PUBLIC;
REVOKE ALL ON FUNCTION organization_access.establish_master_authority(uuid,uuid,uuid,uuid,integer,text,uuid,uuid,uuid[]),organization_access.read_master_authority(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_master_authority(uuid) TO :"app_user";

REVOKE UPDATE ON counterparties.counterparties FROM :"app_user";

-- Module-owned committed edit history. No broad UPDATE grant to the application.
CREATE TABLE counterparties.common_edit_history (
 "CommandId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "CounterpartyId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,
 "AuthorityVersion" integer NOT NULL,
 "Revision" integer NOT NULL,
 "Before" jsonb NOT NULL,
 "After" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","CounterpartyId","Revision")
);
ALTER TABLE counterparties.common_edit_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.common_edit_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON counterparties.common_edit_history USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE TRIGGER immutable_common_edit BEFORE UPDATE OR DELETE OR TRUNCATE ON counterparties.common_edit_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION counterparties.common_edit_state(company_id uuid,record_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE authority jsonb; row_data jsonb; revision_now integer; BEGIN
 -- Read identity, revision and authority under the same serialization boundary as writes.
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||current_setting('app.tenant_id',true),0));
 authority:=organization_access.read_master_authority(company_id);
 IF authority->>'state'='forbidden' THEN RETURN authority; END IF;
 SELECT jsonb_build_object('id',"Id",'legalName',"LegalName",'fiscalIdentifier',"FiscalIdentifier",'registeredOffice',"RegisteredOffice") INTO row_data FROM counterparties.counterparties WHERE "Id"=record_id;
 IF row_data IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.common_edit_history WHERE "CounterpartyId"=record_id;
 RETURN jsonb_build_object('state','ready','authority',authority,'counterparty',row_data,'revision',revision_now);
END $$;
CREATE FUNCTION counterparties.edit_common(company_id uuid,record_id uuid,command_id uuid,authority_version integer,expected_revision integer,legal_name text,fiscal_identifier text,registered_office text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE tenant_id uuid; member_id uuid; authority jsonb; previous counterparties.common_edit_history; row_before jsonb; row_after jsonb; revision_now integer; BEGIN
 SELECT "Id","TenantId" INTO member_id,tenant_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE;
 IF member_id IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 -- Same lock as owner decision. Held through commit of both authority check and local write.
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||tenant_id::text,0));
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id AND p."LegalEntityId"=company_id AND p."Permission"='counterparties.read' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM 1 FROM organization_access.common_edit_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 authority:=organization_access.read_master_authority(company_id);
 IF authority->>'state'='missing' THEN RETURN jsonb_build_object('state','missing'); END IF;
 IF authority_version IS DISTINCT FROM (authority->>'version')::integer THEN RETURN jsonb_build_object('state','stale_authority'); END IF;
 IF authority->>'state'<>'local' THEN RETURN jsonb_build_object('state','external'); END IF;
 IF command_id IS NULL OR command_id='00000000-0000-0000-0000-000000000000' OR expected_revision IS NULL OR expected_revision<0 OR legal_name IS NULL OR length(btrim(legal_name)) NOT BETWEEN 1 AND 200 OR fiscal_identifier IS NULL OR length(btrim(fiscal_identifier)) NOT BETWEEN 1 AND 100 OR registered_office IS NULL OR length(btrim(registered_office)) NOT BETWEEN 1 AND 500 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 row_after:=jsonb_build_object('legalName',btrim(legal_name),'fiscalIdentifier',btrim(fiscal_identifier),'registeredOffice',btrim(registered_office));
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,2));
 SELECT * INTO previous FROM counterparties.common_edit_history WHERE "CommandId"=command_id;
 IF FOUND THEN
  RETURN jsonb_build_object('state',CASE WHEN previous."ActorMembershipId"=member_id AND previous."LegalEntityId"=company_id AND previous."CounterpartyId"=record_id AND previous."AuthorityVersion"=authority_version AND previous."Revision"::bigint=expected_revision::bigint+1 AND previous."After"=row_after THEN 'replayed' ELSE 'conflict' END);
 END IF;
 SELECT jsonb_build_object('legalName',"LegalName",'fiscalIdentifier',"FiscalIdentifier",'registeredOffice',"RegisteredOffice") INTO row_before FROM counterparties.counterparties WHERE "Id"=record_id FOR UPDATE;
 IF row_before IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.common_edit_history WHERE "CounterpartyId"=record_id;
 IF revision_now<>expected_revision THEN RETURN jsonb_build_object('state','conflict'); END IF;
 INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After") VALUES(command_id,tenant_id,record_id,company_id,member_id,authority_version,revision_now+1,row_before,row_after);
 UPDATE counterparties.counterparties SET "LegalName"=btrim(legal_name),"FiscalIdentifier"=btrim(fiscal_identifier),"RegisteredOffice"=btrim(registered_office) WHERE "Id"=record_id;
 RETURN jsonb_build_object('state','applied');
EXCEPTION WHEN unique_violation THEN
 -- A globally repeated command may belong to an RLS-hidden tenant; disclose no row or payload.
 RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON counterparties.common_edit_history FROM PUBLIC;
REVOKE ALL ON FUNCTION counterparties.common_edit_state(uuid,uuid),counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.common_edit_state(uuid,uuid),counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) TO :"app_user";
