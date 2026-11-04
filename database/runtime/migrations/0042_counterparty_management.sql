-- MVP04/#143. No seeds/backfill, no automatic master-authority decision.
-- The published 0001-0041 remain immutable.
ALTER TABLE counterparties.counterparties DROP CONSTRAINT "counterparties_FiscalIdentifier_check";
ALTER TABLE counterparties.counterparties DROP CONSTRAINT "counterparties_RegisteredOffice_check";
ALTER TABLE counterparties.counterparties ADD CONSTRAINT counterparties_fiscal_optional CHECK(length("FiscalIdentifier")<=100);
ALTER TABLE counterparties.counterparties ADD CONSTRAINT counterparties_office_optional CHECK(length("RegisteredOffice")<=500);

-- Role/permission changes version the existing access snapshot witness too:
-- an old repeatable-read snapshot cannot resurrect an edited/revoked permission.
CREATE TRIGGER tenant_role_snapshot_changed BEFORE INSERT OR UPDATE OR DELETE ON organization_access.tenant_role_objects
 FOR EACH ROW EXECUTE FUNCTION organization_access.advance_membership_access_snapshot_fence();

-- New scope types never enter the legacy warehouse consumer, even as nulls.
CREATE OR REPLACE FUNCTION organization_access.current_tenant_role_scopes()
RETURNS TABLE("Id" uuid,"MembershipId" uuid,"TenantId" uuid,"LegalEntityId" uuid,"SiteId" uuid,"WarehouseId" uuid,"Permission" varchar(100))
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN; END IF;
 RETURN QUERY SELECT s.* FROM organization_access.current_tenant_role_scopes_before_access() s
 WHERE s."Permission" IN ('organization-context.read','organization-context.write')
 AND s."LegalEntityId" IS NOT NULL AND s."SiteId" IS NOT NULL AND s."WarehouseId" IS NOT NULL;
END $$;

CREATE FUNCTION organization_access.counterparty_permission(action_name text, company uuid DEFAULT NULL) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE target uuid:=nullif(current_setting('app.tenant_id',true),'')::uuid;
BEGIN
 IF NOT organization_access.current_membership_access(target) OR target IS NULL THEN RETURN false; END IF;
 IF (action_name IN ('counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write') AND company IS NOT NULL)
 OR (action_name IN ('counterparties.extensions.read','counterparties.extensions.write') AND company IS NULL)
 OR action_name NOT IN ('counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write') THEN RETURN false; END IF;
 RETURN EXISTS(SELECT 1 FROM organization_access.current_tenant_role_scopes_before_access() s
 JOIN organization_access.tenant_role_objects p ON p."Id"=s."Id" AND p."TenantId"=target AND p."Kind"='permission'
 WHERE s."TenantId"=target AND s."Permission"=action_name AND s."LegalEntityId" IS NOT DISTINCT FROM company
 AND s."SiteId" IS NULL AND s."WarehouseId" IS NULL
 AND p."Data" ?& ARRAY['action','legalEntityId','siteId','warehouseId']
 AND p."Data"->'siteId'='null'::jsonb AND p."Data"->'warehouseId'='null'::jsonb
 AND p."Data"->'legalEntityId'=coalesce(to_jsonb(company),'null'::jsonb));
END $$;
REVOKE ALL ON FUNCTION organization_access.counterparty_permission(text,uuid) FROM PUBLIC, :"app_user";

ALTER FUNCTION organization_access.read_tenant_roles(uuid) RENAME TO read_tenant_roles_before_counterparties;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles_before_counterparties(uuid) FROM PUBLIC, :"app_user";
CREATE FUNCTION organization_access.read_tenant_roles(target uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE result jsonb; prior text:=current_setting('app.tenant_id',true);
BEGIN
 result:=organization_access.read_tenant_roles_before_counterparties(target);
 IF result->>'state'='ok' AND result ? 'permissions' THEN
  PERFORM set_config('app.tenant_id',result->>'tenantId',true);
  result:=result||jsonb_build_object('actions',jsonb_build_array('organization-context.read','organization-context.write',
   'counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write'),
   'companies',coalesce((SELECT jsonb_agg(jsonb_build_object('legalEntityId',"Id",'name',"Name") ORDER BY "Id") FROM organization_access.legal_entities WHERE "TenantId"=(result->>'tenantId')::uuid),'[]'::jsonb));
 END IF;
 PERFORM set_config('app.tenant_id',coalesce(prior,''),true);
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION organization_access.read_tenant_roles(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.read_tenant_roles(uuid) TO :"app_user";

-- Private immutable command receipt: exact typed request plus historical response.
-- No FK to historical rows: immutable TRUNCATE refusal must not be intercepted by FK.
CREATE TABLE counterparties.management_audit (
 "CommandId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,
 "BindingHash" bytea NOT NULL,
 "Request" jsonb NOT NULL,
 "Before" jsonb NOT NULL,
 "After" jsonb NOT NULL,
 "AuthorityVersion" integer,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE counterparties.management_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.management_audit FORCE ROW LEVEL SECURITY;
CREATE POLICY management_audit_owner ON counterparties.management_audit TO CURRENT_USER
 USING ("TenantId"::text=current_setting('app.tenant_id',true)) WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
REVOKE ALL ON counterparties.management_audit FROM PUBLIC, :"app_user";
CREATE TRIGGER immutable_management_audit BEFORE UPDATE OR DELETE OR TRUNCATE ON counterparties.management_audit
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();

-- Addresses are the existing company-owned extension, not a second shared identity.
CREATE TABLE counterparties.destination_revisions (
 "DestinationId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK("Revision">0)
);
ALTER TABLE counterparties.destination_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE counterparties.destination_revisions FORCE ROW LEVEL SECURITY;
CREATE POLICY destination_revision_owner ON counterparties.destination_revisions TO CURRENT_USER
 USING ("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
REVOKE ALL ON counterparties.destination_revisions FROM PUBLIC, :"app_user";

CREATE FUNCTION counterparties.management_snapshot(record_id uuid) RETURNS jsonb
LANGUAGE sql SET search_path=pg_catalog,counterparties AS $$
 SELECT jsonb_build_object('id',c."Id",'legalName',c."LegalName",'fiscalIdentifier',c."FiscalIdentifier",'registeredOffice',c."RegisteredOffice",'isSupplier',c."IsSupplier",
 'revision',coalesce((SELECT max("Revision") FROM counterparties.common_edit_history h WHERE h."TenantId"=c."TenantId" AND h."CounterpartyId"=c."Id"),0))
 FROM counterparties.counterparties c WHERE c."Id"=record_id AND c."TenantId"::text=current_setting('app.tenant_id',true)
$$;
REVOKE ALL ON FUNCTION counterparties.management_snapshot(uuid) FROM PUBLIC, :"app_user";

CREATE FUNCTION counterparties.management_read(search_text text, after_id uuid, record_id uuid, company uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties,organization_access AS $$
DECLARE target uuid; result jsonb; authority jsonb; companies jsonb; items jsonb; detail jsonb;
BEGIN
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId" INTO target FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF NOT organization_access.counterparty_permission('counterparties.shared.read') THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF search_text IS NOT NULL AND (length(search_text)>200 OR search_text ~ '[[:cntrl:]]') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||target::text,0));
 SELECT jsonb_build_object('state',CASE WHEN "Direction"='Enginia360ToExternal' THEN 'local' ELSE 'external' END,'version',"Version") INTO authority
 FROM organization_access.master_authority_history WHERE "TenantId"=target ORDER BY "Version" DESC LIMIT 1;
 authority:=coalesce(authority,jsonb_build_object('state','missing','version',0));
 SELECT coalesce(jsonb_agg(counterparties.management_snapshot(x."Id") ORDER BY x."Id"),'[]'::jsonb) INTO items FROM
 (SELECT c."Id" FROM counterparties.counterparties c WHERE c."TenantId"=target
 AND (search_text IS NULL OR strpos(lower(c."LegalName"),lower(search_text))>0 OR strpos(lower(c."FiscalIdentifier"),lower(search_text))>0)
 AND (after_id IS NULL OR c."Id">after_id) ORDER BY c."Id" LIMIT 21) x;
 IF record_id IS NOT NULL THEN
  detail:=counterparties.management_snapshot(record_id);
  IF detail IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 END IF;
 SELECT coalesce(jsonb_agg(jsonb_build_object('id',le."Id",'name',le."Name",'canWrite',organization_access.counterparty_permission('counterparties.extensions.write',le."Id")) ORDER BY le."Id"),'[]'::jsonb)
 INTO companies FROM organization_access.legal_entities le WHERE le."TenantId"=target AND organization_access.counterparty_permission('counterparties.extensions.read',le."Id");
 result:=jsonb_build_object('state','ready','tenantId',target,'authority',authority,'items',items,'detail',detail,'companies',companies,
 'canCreate',organization_access.counterparty_permission('counterparties.shared.create'),
 'canEdit',organization_access.counterparty_permission('counterparties.shared.edit'),
 'canWriteRoles',organization_access.counterparty_permission('counterparties.business-roles.write'));
 IF company IS NOT NULL THEN
  IF record_id IS NULL OR NOT organization_access.counterparty_permission('counterparties.extensions.read',company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  PERFORM set_config('app.legal_entity_id',company::text,true);
  result:=result||jsonb_build_object('companyId',company,'destinations',coalesce((SELECT jsonb_agg(jsonb_build_object('id',d."Id",'address',d."Address",'published',d."Published",'ownerLegalEntityId',d."OwnerLegalEntityId",'revision',coalesce(r."Revision",0)) ORDER BY d."Id")
   FROM counterparties.destinations d LEFT JOIN counterparties.destination_revisions r ON r."DestinationId"=d."Id" AND r."TenantId"=target AND r."LegalEntityId"=company
   WHERE d."TenantId"=target AND d."CounterpartyId"=record_id AND d."OwnerLegalEntityId"=company),'[]'::jsonb));
 END IF;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION counterparties.management_read(text,uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.management_read(text,uuid,uuid,uuid) TO :"app_user";

CREATE FUNCTION counterparties.management_command(request jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties,organization_access AS $$
DECLARE target uuid; member_id uuid; binding_hash bytea; command_id uuid; record_id uuid; company uuid; destination_id uuid;
 operation text; action_name text; keys text[]; key text; revision_now integer; authority organization_access.master_authority_history;
 previous counterparties.management_audit; row_before jsonb; row_after jsonb; snapshot jsonb; bound integer;
BEGIN
 -- Current binding/access/777036 precede every payload, grant, authority and replay lookup.
 PERFORM pg_advisory_xact_lock(777036);
 IF NOT organization_access.current_membership_access(NULL) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 SELECT "TenantId","Id" INTO target,member_id FROM organization_access.memberships WHERE "IdentitySubject"=current_setting('app.identity_subject',true);
 PERFORM set_config('app.tenant_id',target::text,true);
 IF NOT organization_access.counterparty_permission('counterparties.shared.read') THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF jsonb_typeof(request) IS DISTINCT FROM 'object' OR jsonb_typeof(request->'operation') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 operation:=request->>'operation';
 IF operation NOT IN ('create','edit','supplier-role','destination-create','destination-edit') THEN RETURN jsonb_build_object('state','invalid'); END IF;
 keys:=ARRAY['commandId','operation','counterpartyId','expectedRevision']||CASE operation
 WHEN 'create' THEN ARRAY['authorityVersion','legalName','fiscalIdentifier','registeredOffice']
 WHEN 'edit' THEN ARRAY['authorityVersion','legalName','fiscalIdentifier','registeredOffice']
 WHEN 'supplier-role' THEN ARRAY['authorityVersion','isSupplier']
 ELSE ARRAY['legalEntityId','destinationId','address'] END;
 IF NOT request ?& keys OR (SELECT count(*) FROM jsonb_object_keys(request))<>cardinality(keys) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['commandId','counterpartyId']||CASE WHEN operation LIKE 'destination-%' THEN ARRAY['legalEntityId','destinationId'] ELSE ARRAY[]::text[] END LOOP
  IF ((operation='create' AND key='counterpartyId') OR (operation='destination-create' AND key='destinationId')) AND request->key='null'::jsonb THEN CONTINUE; END IF;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR request->>key !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  OR request->>key='00000000-0000-0000-0000-000000000000' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF operation='create' AND request->'counterpartyId'<>'null'::jsonb OR operation='destination-create' AND request->'destinationId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY ARRAY['expectedRevision']||CASE WHEN operation NOT LIKE 'destination-%' THEN ARRAY['authorityVersion'] ELSE ARRAY[]::text[] END LOOP
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'number' OR request->>key !~ '^(0|[1-9][0-9]{0,9})$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF (request->>key)::bigint>2147483647 THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF operation IN ('create','destination-create') AND request->>'expectedRevision'<>'0' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 FOREACH key IN ARRAY CASE WHEN operation IN ('create','edit') THEN ARRAY['legalName','fiscalIdentifier','registeredOffice'] WHEN operation LIKE 'destination-%' THEN ARRAY['address'] ELSE ARRAY[]::text[] END LOOP
  bound:=CASE key WHEN 'legalName' THEN 200 WHEN 'fiscalIdentifier' THEN 100 ELSE 500 END;
  IF jsonb_typeof(request->key) IS DISTINCT FROM 'string' OR length(request->>key)>bound OR request->>key ~ '[[:cntrl:]]'
   OR (key IN ('legalName','address') AND length(btrim(request->>key))=0) THEN RETURN jsonb_build_object('state','invalid'); END IF;
 END LOOP;
 IF operation='supplier-role' AND jsonb_typeof(request->'isSupplier') IS DISTINCT FROM 'boolean' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 company:=(request->>'legalEntityId')::uuid;
 action_name:=CASE operation WHEN 'create' THEN 'counterparties.shared.create' WHEN 'edit' THEN 'counterparties.shared.edit' WHEN 'supplier-role' THEN 'counterparties.business-roles.write' ELSE 'counterparties.extensions.write' END;
 IF NOT organization_access.counterparty_permission(action_name,company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF company IS NOT NULL THEN
  IF NOT organization_access.counterparty_permission('counterparties.extensions.read',company) OR NOT EXISTS(SELECT 1 FROM organization_access.legal_entities WHERE "Id"=company AND "TenantId"=target) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  PERFORM set_config('app.legal_entity_id',company::text,true);
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||target::text,0));
 IF company IS NULL THEN
  SELECT * INTO authority FROM organization_access.master_authority_history WHERE "TenantId"=target ORDER BY "Version" DESC LIMIT 1;
  IF authority."Version" IS NULL THEN RETURN jsonb_build_object('state','missing'); END IF;
  IF authority."Direction"<>'Enginia360ToExternal' THEN RETURN jsonb_build_object('state','external'); END IF;
  IF authority."Version"<>(request->>'authorityVersion')::integer THEN RETURN jsonb_build_object('state','stale_authority'); END IF;
 END IF;
 command_id:=(request->>'commandId')::uuid; record_id:=(request->>'counterpartyId')::uuid;
 binding_hash:=sha256(convert_to(jsonb_build_array(current_setting('app.identity_issuer'),current_setting('app.external_subject'))::text,'UTF8'));
 PERFORM pg_advisory_xact_lock(hashtextextended(command_id::text,2));
 SELECT * INTO previous FROM counterparties.management_audit WHERE "CommandId"=command_id;
 IF FOUND THEN
  IF previous."TenantId"=target AND previous."ActorMembershipId"=member_id AND previous."BindingHash"=binding_hash AND previous."Request"=request THEN
   RETURN jsonb_build_object('state','replayed','snapshot',previous."After"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 -- Namespace shared with older common/role/external-projection commands.
 IF EXISTS(SELECT 1 FROM counterparties.common_edit_history WHERE "CommandId"=command_id) THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF operation='create' THEN
  record_id:=gen_random_uuid(); revision_now:=0; row_before:='{}';
  INSERT INTO counterparties.counterparties("Id","TenantId","LegalName","FiscalIdentifier","RegisteredOffice")
  VALUES(record_id,target,btrim(request->>'legalName'),btrim(request->>'fiscalIdentifier'),btrim(request->>'registeredOffice'));
 ELSE
  PERFORM 1 FROM counterparties.counterparties WHERE "Id"=record_id AND "TenantId"=target FOR UPDATE;
  IF NOT FOUND THEN RETURN jsonb_build_object('state','not_found'); END IF;
  row_before:=counterparties.management_snapshot(record_id);
  revision_now:=(row_before->>'revision')::integer;
 END IF;
 IF company IS NULL THEN
  IF revision_now<>(request->>'expectedRevision')::integer OR revision_now=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
  IF operation='edit' THEN
   UPDATE counterparties.counterparties SET "LegalName"=btrim(request->>'legalName'),"FiscalIdentifier"=btrim(request->>'fiscalIdentifier'),"RegisteredOffice"=btrim(request->>'registeredOffice') WHERE "Id"=record_id AND "TenantId"=target;
  ELSIF operation='supplier-role' THEN
   UPDATE counterparties.counterparties SET "IsSupplier"=(request->>'isSupplier')::boolean WHERE "Id"=record_id AND "TenantId"=target;
  END IF;
  row_after:=counterparties.management_snapshot(record_id)||jsonb_build_object('revision',revision_now+1);
  -- Legacy history has a company provenance column: use the explicit authority
  -- reference company, not browser context; this does not change shared ownership.
  INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After")
  VALUES(command_id,target,record_id,(authority."CompanyIds")[1],member_id,authority."Version",revision_now+1,row_before,row_after);
  snapshot:=row_after;
 ELSE
  destination_id:=(request->>'destinationId')::uuid;
  IF operation='destination-create' THEN
   destination_id:=gen_random_uuid();revision_now:=0;row_before:='{}';
  ELSE
   SELECT jsonb_build_object('id',d."Id",'address',d."Address",'published',d."Published",'revision',coalesce(r."Revision",0)) INTO row_before
   FROM counterparties.destinations d LEFT JOIN counterparties.destination_revisions r ON r."DestinationId"=d."Id" AND r."TenantId"=target AND r."LegalEntityId"=company
   WHERE d."Id"=destination_id AND d."TenantId"=target AND d."CounterpartyId"=record_id AND d."OwnerLegalEntityId"=company FOR UPDATE OF d;
   IF row_before IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
   IF row_before->'published'='true'::jsonb THEN RETURN jsonb_build_object('state','conflict'); END IF;
   revision_now:=(row_before->>'revision')::integer;
  END IF;
  IF revision_now<>(request->>'expectedRevision')::integer OR revision_now=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
  IF operation='destination-create' THEN
   INSERT INTO counterparties.destinations("Id","TenantId","CounterpartyId","OwnerLegalEntityId","Address","Published") VALUES(destination_id,target,record_id,company,btrim(request->>'address'),false);
  ELSE UPDATE counterparties.destinations SET "Address"=btrim(request->>'address') WHERE "Id"=destination_id AND "TenantId"=target AND "OwnerLegalEntityId"=company; END IF;
  INSERT INTO counterparties.destination_revisions VALUES(destination_id,target,company,revision_now+1)
  ON CONFLICT("DestinationId") DO UPDATE SET "Revision"=excluded."Revision";
  snapshot:=jsonb_build_object('id',destination_id,'counterpartyId',record_id,'ownerLegalEntityId',company,'address',btrim(request->>'address'),'published',false,'revision',revision_now+1);
 END IF;
 INSERT INTO counterparties.management_audit("CommandId","TenantId","ActorMembershipId","BindingHash","Request","Before","After","AuthorityVersion")
 VALUES(command_id,target,member_id,binding_hash,request,row_before,snapshot,authority."Version");
 RETURN jsonb_build_object('state','applied','snapshot',snapshot);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION counterparties.management_command(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.management_command(jsonb) TO :"app_user";

-- Preserve the finite role command/audit algorithm; extend only permission scope validation.
CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role(target uuid, request jsonb, authority jsonb) RETURNS jsonb
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
  IF (key='resourceId' OR (kind='permission' AND key IN ('legalEntityId','siteId','warehouseId'))) AND request->key='null'::jsonb THEN CONTINUE; END IF;
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
  IF jsonb_typeof(request->'action') IS DISTINCT FROM 'string' THEN RETURN jsonb_build_object('state','invalid'); END IF;
  IF request->>'action' IN ('organization-context.read','organization-context.write') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'='null'::jsonb OR request->'warehouseId'='null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.warehouses WHERE "TenantId"=target AND "Id"=(request->>'warehouseId')::uuid
    AND "SiteId"=(request->>'siteId')::uuid AND "LegalEntityId"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSIF request->>'action' IN ('counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write') THEN
   IF request->'legalEntityId'<>'null'::jsonb OR request->'siteId'<>'null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
  ELSIF request->>'action' IN ('counterparties.extensions.read','counterparties.extensions.write') THEN
   IF request->'legalEntityId'='null'::jsonb OR request->'siteId'<>'null'::jsonb OR request->'warehouseId'<>'null'::jsonb THEN RETURN jsonb_build_object('state','invalid'); END IF;
   PERFORM 1 FROM organization_access.legal_entities WHERE "TenantId"=target AND "Id"=(request->>'legalEntityId')::uuid;
   IF NOT FOUND THEN RETURN jsonb_build_object('state','forbidden'); END IF;
  ELSE RETURN jsonb_build_object('state','invalid'); END IF;
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


-- Do not let an older replay comparator reinterpret a new management UUID.
ALTER FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) RENAME TO edit_common_before_management;
REVOKE ALL ON FUNCTION counterparties.edit_common_before_management(uuid,uuid,uuid,integer,integer,text,text,text) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.edit_common(company_id uuid,record_id uuid,command_id uuid,authority_version integer,expected_revision integer,legal_name text,fiscal_identifier text,registered_office text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF EXISTS(SELECT 1 FROM counterparties.management_audit WHERE "CommandId"=command_id) THEN RETURN jsonb_build_object('state','conflict'); END IF;
 RETURN counterparties.edit_common_before_management($1,$2,$3,$4,$5,$6,$7,$8);
END $$;
REVOKE ALL ON FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text) TO :"app_user";

-- Do not let an older replay comparator reinterpret a new management UUID.
ALTER FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) RENAME TO set_supplier_role_before_management;
REVOKE ALL ON FUNCTION counterparties.set_supplier_role_before_management(uuid,uuid,uuid,integer,integer,boolean) FROM PUBLIC, :"app_user";
CREATE FUNCTION counterparties.set_supplier_role(company_id uuid,record_id uuid,command_id uuid,authority_version integer,expected_revision integer,is_supplier boolean) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access,counterparties AS $$
BEGIN
 IF NOT organization_access.current_membership_access(nullif(current_setting('app.tenant_id',true),'')::uuid) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF EXISTS(SELECT 1 FROM counterparties.management_audit WHERE "CommandId"=command_id) THEN RETURN jsonb_build_object('state','conflict'); END IF;
 RETURN counterparties.set_supplier_role_before_management($1,$2,$3,$4,$5,$6);
END $$;
REVOKE ALL ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean) TO :"app_user";
