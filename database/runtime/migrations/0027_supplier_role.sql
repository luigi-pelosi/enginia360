-- D88: a supplier is a ROLE in the tenant-wide shared Counterparties master (D26/D65); the external ERP (Giobby)
-- vendor identity is a COMPANY extension, never part of the shared master. Append-only migration.
-- No purchase request, no ERP traffic, no new delegable grant, no host-configured vendor list.

ALTER TABLE counterparties.counterparties ADD COLUMN "IsSupplier" boolean NOT NULL DEFAULT false;

-- The role is a shared-master fact: it is written only by this gated command, with the same exact grants
-- (company counterparties.read + tenant counterparties.common.edit), the same single master authority
-- (local profile and exact version), the same optimistic revision sequence and the same immutable history
-- as the existing bounded common edit. External or missing authority refuses; nothing is projected.
CREATE FUNCTION counterparties.set_supplier_role(company_id uuid,record_id uuid,command_id uuid,authority_version integer,expected_revision integer,is_supplier boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE tenant_id uuid; member_id uuid; authority jsonb; previous counterparties.common_edit_history; row_before jsonb; row_after jsonb; revision_now integer; BEGIN
 SELECT "Id","TenantId" INTO member_id,tenant_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE;
 IF member_id IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||tenant_id::text,0));
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id AND p."LegalEntityId"=company_id AND p."Permission"='counterparties.read' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM 1 FROM organization_access.common_edit_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 authority:=organization_access.read_master_authority(company_id);
 IF authority->>'state'='missing' THEN RETURN jsonb_build_object('state','missing'); END IF;
 IF authority_version IS DISTINCT FROM (authority->>'version')::integer THEN RETURN jsonb_build_object('state','stale_authority'); END IF;
 IF authority->>'state'<>'local' THEN RETURN jsonb_build_object('state','external'); END IF;
 IF command_id IS NULL OR command_id='00000000-0000-0000-0000-000000000000' OR expected_revision IS NULL OR expected_revision<0 OR is_supplier IS NULL THEN RETURN jsonb_build_object('state','invalid'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,2));
 SELECT * INTO previous FROM counterparties.common_edit_history WHERE "CommandId"=command_id;
 IF FOUND THEN
  RETURN jsonb_build_object('state',CASE WHEN previous."ActorMembershipId"=member_id AND previous."LegalEntityId"=company_id AND previous."CounterpartyId"=record_id AND previous."AuthorityVersion"=authority_version AND previous."Revision"::bigint=expected_revision::bigint+1 AND previous."After" ? 'isSupplier' AND (previous."After"->>'isSupplier')::boolean=is_supplier THEN 'replayed' ELSE 'conflict' END);
 END IF;
 SELECT jsonb_build_object('legalName',"LegalName",'fiscalIdentifier',"FiscalIdentifier",'registeredOffice',"RegisteredOffice",'isSupplier',"IsSupplier") INTO row_before FROM counterparties.counterparties WHERE "Id"=record_id FOR UPDATE;
 IF row_before IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.common_edit_history WHERE "CounterpartyId"=record_id;
 IF revision_now<>expected_revision THEN RETURN jsonb_build_object('state','conflict'); END IF;
 row_after:=row_before||jsonb_build_object('isSupplier',is_supplier);
 INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After") VALUES(command_id,tenant_id,record_id,company_id,member_id,authority_version,revision_now+1,row_before,row_after);
 UPDATE counterparties.counterparties SET "IsSupplier"=is_supplier WHERE "Id"=record_id;
 RETURN jsonb_build_object('state','applied');
EXCEPTION WHEN unique_violation THEN
 -- A globally repeated command may belong to an RLS-hidden tenant; disclose no row or payload.
 RETURN jsonb_build_object('state','conflict');
END $$;

-- The edit state also reports the role under the same serialization boundary (no extension is projected).
CREATE OR REPLACE FUNCTION counterparties.common_edit_state(company_id uuid,record_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE authority jsonb; row_data jsonb; revision_now integer; BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||current_setting('app.tenant_id',true),0));
 authority:=organization_access.read_master_authority(company_id);
 IF authority->>'state'='forbidden' THEN RETURN authority; END IF;
 SELECT jsonb_build_object('id',"Id",'legalName',"LegalName",'fiscalIdentifier',"FiscalIdentifier",'registeredOffice',"RegisteredOffice",'isSupplier',"IsSupplier") INTO row_data FROM counterparties.counterparties WHERE "Id"=record_id;
 IF row_data IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.common_edit_history WHERE "CounterpartyId"=record_id;
 RETURN jsonb_build_object('state','ready','authority',authority,'counterparty',row_data,'revision',revision_now);
END $$;

-- Company extension: the Giobby vendor identity is an opaque ID plus the exact name used for the lookup.
-- Per company, immutable and revisioned. Written only by the owner/trusted-operator path (like the stock
-- profile and master authority setup); the application role can neither write nor read the table directly.
CREATE TABLE counterparties.giobby_vendor_identity_history (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "CounterpartyId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),
 "VendorId" varchar(64) NOT NULL CHECK ("VendorId" ~ '^[!-~]{1,64}$'),
 "VendorName" varchar(200) NOT NULL CHECK (length(btrim("VendorName")) BETWEEN 1 AND 200 AND "VendorName"=btrim("VendorName") AND "VendorName" !~ '[[:cntrl:]]'),
 "ActorMembershipId" uuid NOT NULL,
 "VerificationReference" uuid NOT NULL CHECK ("VerificationReference"<>'00000000-0000-0000-0000-000000000000'),
 "EffectiveFrom" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","LegalEntityId","CounterpartyId","Revision"),
 FOREIGN KEY ("CounterpartyId","TenantId") REFERENCES counterparties.counterparties("Id","TenantId"),
 FOREIGN KEY ("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId"),
 FOREIGN KEY ("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE counterparties.giobby_vendor_identity_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.giobby_vendor_identity_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON counterparties.giobby_vendor_identity_history
 USING ("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_giobby_vendor_identity BEFORE UPDATE OR DELETE OR TRUNCATE ON counterparties.giobby_vendor_identity_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION counterparties.establish_giobby_vendor_identity(command_id uuid,tenant_id uuid,company_id uuid,record_id uuid,actor_id uuid,verification_id uuid,expected_revision integer,vendor_id text,vendor_name text) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE previous counterparties.giobby_vendor_identity_history; supplier boolean; revision_now integer; name_now text; BEGIN
 -- Invoker, no app EXECUTE; never a web/admin privilege or self-attested claim.
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN
  RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501';
 END IF;
 IF tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) OR company_id::text IS DISTINCT FROM current_setting('app.legal_entity_id',true) THEN RETURN 'forbidden'; END IF;
 name_now:=btrim(vendor_name);
 IF command_id IS NULL OR command_id='00000000-0000-0000-0000-000000000000' OR record_id IS NULL OR actor_id IS NULL OR verification_id IS NULL OR verification_id='00000000-0000-0000-0000-000000000000'
 OR expected_revision IS NULL OR expected_revision<0 OR vendor_id IS NULL OR vendor_id !~ '^[!-~]{1,64}$'
 OR name_now IS NULL OR length(name_now) NOT BETWEEN 1 AND 200 OR name_now ~ '[[:cntrl:]]' THEN RETURN 'invalid'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('giobby-vendor:'||tenant_id::text||':'||company_id::text,0));
 IF NOT EXISTS(SELECT 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=actor_id AND m."TenantId"=tenant_id) THEN RETURN 'forbidden'; END IF;
 SELECT * INTO previous FROM counterparties.giobby_vendor_identity_history WHERE "CommandId"=command_id;
 IF FOUND THEN
  RETURN CASE WHEN previous."TenantId"=tenant_id AND previous."LegalEntityId"=company_id AND previous."CounterpartyId"=record_id AND previous."ActorMembershipId"=actor_id AND previous."VerificationReference"=verification_id AND previous."Revision"::bigint=expected_revision::bigint+1 AND previous."VendorId"=vendor_id AND previous."VendorName"=name_now THEN 'replayed' ELSE 'conflict' END;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM organization_access.legal_entities le WHERE le."Id"=company_id AND le."TenantId"=tenant_id) THEN RETURN 'conflict'; END IF;
 SELECT "IsSupplier" INTO supplier FROM counterparties.counterparties WHERE "Id"=record_id AND "TenantId"=tenant_id;
 IF NOT FOUND THEN RETURN 'conflict'; END IF;
 IF NOT supplier THEN RETURN 'not_supplier'; END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.giobby_vendor_identity_history WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id AND "CounterpartyId"=record_id;
 IF revision_now<>expected_revision THEN RETURN 'conflict'; END IF;
 -- One vendor ID identifies one counterparty within a company (the latest revision of each counterparty counts).
 IF EXISTS(SELECT 1 FROM (SELECT DISTINCT ON ("CounterpartyId") "CounterpartyId","VendorId" FROM counterparties.giobby_vendor_identity_history WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id ORDER BY "CounterpartyId","Revision" DESC) latest WHERE latest."VendorId"=vendor_id AND latest."CounterpartyId"<>record_id) THEN RETURN 'conflict'; END IF;
 INSERT INTO counterparties.giobby_vendor_identity_history("CommandId","TenantId","LegalEntityId","CounterpartyId","Revision","VendorId","VendorName","ActorMembershipId","VerificationReference")
 VALUES(command_id,tenant_id,company_id,record_id,revision_now+1,vendor_id,name_now,actor_id,verification_id);
 RETURN 'applied';
EXCEPTION WHEN unique_violation OR foreign_key_violation OR check_violation OR not_null_violation THEN RETURN 'conflict';
END $$;

-- Application read: exact company counterparties.read; the mapping is served only while the counterparty holds the role.
CREATE FUNCTION counterparties.read_giobby_vendor_identity(company_id uuid,record_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE member_id uuid; tenant_id uuid; supplier boolean; h counterparties.giobby_vendor_identity_history; BEGIN
 SELECT "Id","TenantId" INTO member_id,tenant_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 IF member_id IS NULL OR tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true) OR company_id::text IS DISTINCT FROM current_setting('app.legal_entity_id',true)
 OR NOT EXISTS(SELECT 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member_id AND p."TenantId"=tenant_id AND p."LegalEntityId"=company_id AND p."Permission"='counterparties.read' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "IsSupplier" INTO supplier FROM counterparties.counterparties WHERE "Id"=record_id AND "TenantId"=tenant_id;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 IF supplier THEN
  SELECT * INTO h FROM counterparties.giobby_vendor_identity_history WHERE "TenantId"=tenant_id AND "LegalEntityId"=company_id AND "CounterpartyId"=record_id ORDER BY "Revision" DESC LIMIT 1;
 END IF;
 RETURN jsonb_build_object('state','ready','isSupplier',supplier,'vendor',CASE WHEN h."CommandId" IS NULL THEN NULL ELSE jsonb_build_object('vendorId',h."VendorId",'vendorName',h."VendorName",'revision',h."Revision",'effectiveFrom',h."EffectiveFrom") END);
END $$;

REVOKE ALL ON counterparties.giobby_vendor_identity_history FROM PUBLIC;
REVOKE ALL ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean),
 counterparties.establish_giobby_vendor_identity(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text),
 counterparties.read_giobby_vendor_identity(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean),
 counterparties.read_giobby_vendor_identity(uuid,uuid) TO :"app_user";
