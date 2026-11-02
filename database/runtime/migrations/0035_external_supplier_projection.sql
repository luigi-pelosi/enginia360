-- D95 bounded positive projection. Existing shared identity only; no company mapping or provider traffic.
-- 0001-0034 remain immutable. Owner-only capability, not a web permission or common-edit bypass.
CREATE TABLE counterparties.external_supplier_projection_history (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL REFERENCES organization_access.tenants("Id"),
 "Request" jsonb NOT NULL,
 "Snapshot" jsonb NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE counterparties.external_supplier_projection_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.external_supplier_projection_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON counterparties.external_supplier_projection_history
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE TRIGGER immutable_external_supplier_projection BEFORE UPDATE OR DELETE OR TRUNCATE
 ON counterparties.external_supplier_projection_history FOR EACH STATEMENT
 EXECUTE FUNCTION organization_access.immutable_delegation_audit();

CREATE FUNCTION counterparties.project_external_supplier_role(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
DECLARE tenant_id uuid; company_id uuid; record_id uuid; actor_id uuid; command_id uuid;
 source_id uuid; profile_id uuid; version_expected integer; revision_expected integer;
 authority organization_access.master_authority_history; row_before jsonb; row_after jsonb;
 revision_now integer; snapshot jsonb; input_key text;
BEGIN
 -- SECURITY DEFINER is narrow; a function call must originate from the existing nonprivileged DB owner.
 IF session_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=session_user) THEN
  RETURN jsonb_build_object('state','forbidden');
 END IF;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 IF NOT request ?& ARRAY['commandId','tenantId','legalEntityId','counterpartyId','actorMembershipId','verificationReference','sourceFactReference','sourceId','profileId','sourceSystem','authorityVersion','expectedRevision','isSupplier']
 OR (SELECT count(*) FROM jsonb_object_keys(request))<>13 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH input_key IN ARRAY ARRAY['commandId','tenantId','legalEntityId','counterpartyId','actorMembershipId','verificationReference','sourceFactReference','sourceId','profileId'] LOOP
  IF jsonb_typeof(request->input_key) IS DISTINCT FROM 'string'
  OR (request->>input_key) !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>input_key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 FOREACH input_key IN ARRAY ARRAY['authorityVersion','expectedRevision'] LOOP
  IF jsonb_typeof(request->input_key) IS DISTINCT FROM 'number'
  OR (request->>input_key) !~ '^(0|[1-9][0-9]{0,9})$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF (request->>input_key)::bigint>2147483647 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 tenant_id:=(request->>'tenantId')::uuid; company_id:=(request->>'legalEntityId')::uuid;
 record_id:=(request->>'counterpartyId')::uuid; actor_id:=(request->>'actorMembershipId')::uuid;
 command_id:=(request->>'commandId')::uuid; source_id:=(request->>'sourceId')::uuid;
 profile_id:=(request->>'profileId')::uuid; version_expected:=(request->>'authorityVersion')::integer;
 revision_expected:=(request->>'expectedRevision')::integer;
 IF tenant_id::text IS DISTINCT FROM current_setting('app.tenant_id',true)
 OR company_id::text IS DISTINCT FROM current_setting('app.legal_entity_id',true) THEN
  RETURN jsonb_build_object('state','forbidden');
 END IF;
 IF request->'isSupplier' IS DISTINCT FROM 'true'::jsonb OR request->>'sourceSystem' IS DISTINCT FROM 'Giobby'
 OR command_id IS NULL OR command_id='00000000-0000-0000-0000-000000000000'
 OR revision_expected IS NULL OR revision_expected<0 OR version_expected IS NULL OR version_expected<1
 OR (request->>'verificationReference')::uuid IS NULL OR (request->>'verificationReference')::uuid='00000000-0000-0000-0000-000000000000'
 OR (request->>'sourceFactReference')::uuid IS NULL OR (request->>'sourceFactReference')::uuid='00000000-0000-0000-0000-000000000000' THEN
  RETURN jsonb_build_object('state','invalid');
 END IF;
 -- Same authority lock as both ordinary common writers. Trust rows remain locked until commit.
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||tenant_id::text,0));
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b
 ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE m."Id"=actor_id AND m."TenantId"=tenant_id FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 PERFORM 1 FROM organization_access.legal_entities le WHERE le."Id"=company_id AND le."TenantId"=tenant_id FOR SHARE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','conflict'); END IF;
 SELECT * INTO authority FROM organization_access.master_authority_history WHERE "TenantId"=tenant_id ORDER BY "Version" DESC LIMIT 1;
 IF authority."Version" IS NULL OR NOT company_id=ANY(authority."CompanyIds") THEN RETURN jsonb_build_object('state','missing'); END IF;
 IF authority."Direction"<>'ExternalToEnginia360' OR authority."Version"<>version_expected
 OR authority."SourceId" IS DISTINCT FROM source_id OR authority."ProfileId" IS DISTINCT FROM profile_id THEN
  RETURN jsonb_build_object('state','stale_authority');
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,2));
 SELECT "Snapshot" INTO snapshot FROM counterparties.external_supplier_projection_history WHERE "CommandId"=command_id AND "Request"=request;
 IF FOUND THEN RETURN jsonb_build_object('state','replayed','snapshot',snapshot); END IF;
 IF EXISTS(SELECT 1 FROM counterparties.external_supplier_projection_history WHERE "CommandId"=command_id)
 OR EXISTS(SELECT 1 FROM counterparties.common_edit_history WHERE "CommandId"=command_id) THEN RETURN jsonb_build_object('state','conflict'); END IF;
 SELECT jsonb_build_object('legalName',"LegalName",'fiscalIdentifier',"FiscalIdentifier",'registeredOffice',"RegisteredOffice",'isSupplier',"IsSupplier")
 INTO row_before FROM counterparties.counterparties WHERE "Id"=record_id AND "TenantId"=tenant_id FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM counterparties.common_edit_history WHERE "CounterpartyId"=record_id;
 IF revision_now<>revision_expected OR revision_now=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 row_after:=row_before||jsonb_build_object('isSupplier',true);
 snapshot:=jsonb_build_object('counterpartyId',record_id,'isSupplier',true,'revision',revision_now+1,'authorityVersion',version_expected);
 INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After")
 VALUES(command_id,tenant_id,record_id,company_id,actor_id,version_expected,revision_now+1,row_before,row_after);
 INSERT INTO counterparties.external_supplier_projection_history("CommandId","TenantId","Request","Snapshot") VALUES(command_id,tenant_id,request,snapshot);
 UPDATE counterparties.counterparties SET "IsSupplier"=true WHERE "Id"=record_id AND "TenantId"=tenant_id;
 RETURN jsonb_build_object('state','applied','snapshot',snapshot);
EXCEPTION WHEN unique_violation OR foreign_key_violation OR check_violation OR not_null_violation THEN
 RETURN jsonb_build_object('state','conflict');
 WHEN invalid_text_representation OR numeric_value_out_of_range THEN RETURN jsonb_build_object('state','invalid');
END $$;
REVOKE ALL ON counterparties.external_supplier_projection_history FROM PUBLIC, :"app_user";
REVOKE ALL ON FUNCTION counterparties.project_external_supplier_role(jsonb) FROM PUBLIC, :"app_user";
