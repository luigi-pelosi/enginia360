-- D91 company purchase-price extension; shared supplier/item identities remain separate.
CREATE TABLE catalog.supplier_purchase_price_history (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId"<>'00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,"SupplierId" uuid NOT NULL,"CatalogItemId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),
 "UnitPurchasePrice" numeric(12,6) NOT NULL CHECK ("UnitPurchasePrice">=0),
 "ActorMembershipId" uuid NOT NULL,"SupplierRevision" integer NOT NULL,"CatalogVersion" integer NOT NULL,"AuthorityVersion" integer NOT NULL,
 "Payload" jsonb NOT NULL,"RecordedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","LegalEntityId","SupplierId","CatalogItemId","Revision"),
 FOREIGN KEY("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE catalog.supplier_purchase_price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE catalog.supplier_purchase_price_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON catalog.supplier_purchase_price_history
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_purchase_price BEFORE UPDATE OR DELETE OR TRUNCATE ON catalog.supplier_purchase_price_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON catalog.supplier_purchase_price_history FROM PUBLIC;

-- Owner/trusted offline grants ONLY; D77's operative mandate is deliberately unchanged.
CREATE TABLE organization_access.purchase_price_grant_history (
 "CommandId" uuid PRIMARY KEY,"TenantId" uuid NOT NULL,"LegalEntityId" uuid NOT NULL,
 "ActorMembershipId" uuid NOT NULL,"TargetMembershipId" uuid NOT NULL,"VerificationReference" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision">0),"Action" text NOT NULL,"Operation" text NOT NULL,
 "OccurredAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE("TenantId","LegalEntityId","TargetMembershipId","Action","Revision"),
 FOREIGN KEY("LegalEntityId","TenantId") REFERENCES organization_access.legal_entities("Id","TenantId"),
 FOREIGN KEY("ActorMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId"),
 FOREIGN KEY("TargetMembershipId","TenantId") REFERENCES organization_access.memberships("Id","TenantId")
);
ALTER TABLE organization_access.purchase_price_grant_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_access.purchase_price_grant_history FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_company ON organization_access.purchase_price_grant_history
 USING("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true))
 WITH CHECK("TenantId"::text=current_setting('app.tenant_id',true) AND "LegalEntityId"::text=current_setting('app.legal_entity_id',true));
CREATE TRIGGER immutable_purchase_price_grant BEFORE UPDATE OR DELETE OR TRUNCATE ON organization_access.purchase_price_grant_history
 FOR EACH STATEMENT EXECUTE FUNCTION organization_access.immutable_delegation_audit();
REVOKE ALL ON organization_access.purchase_price_grant_history FROM PUBLIC;
CREATE FUNCTION organization_access.set_purchase_price_grant(command uuid,tenant uuid,company uuid,actor uuid,target uuid,verification uuid,expected integer,action text,operation text) RETURNS text
LANGUAGE plpgsql SET search_path=pg_catalog,organization_access AS $$
DECLARE revision_now integer; previous organization_access.purchase_price_grant_history; BEGIN
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'nonprivileged database owner required' USING ERRCODE='42501'; END IF;
 IF tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true) OR company::text IS DISTINCT FROM current_setting('app.legal_entity_id',true) OR actor IS NULL OR target IS NULL OR actor=target OR action IS NULL OR action NOT IN ('catalog.purchase-prices.read','catalog.purchase-prices.manage') THEN RETURN 'forbidden'; END IF;
 IF command IS NULL OR command='00000000-0000-0000-0000-000000000000' OR verification IS NULL OR verification='00000000-0000-0000-0000-000000000000' OR expected IS NULL OR expected<0 OR operation IS NULL OR operation NOT IN ('grant','revoke') THEN RETURN 'invalid'; END IF;
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=actor AND m."TenantId"=tenant FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN 'forbidden'; END IF;
 PERFORM 1 FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject" WHERE m."Id"=target AND m."TenantId"=tenant FOR SHARE OF m,b;
 IF NOT FOUND THEN RETURN 'forbidden'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended('price-grant:'||tenant::text||':'||company::text||':'||target::text||':'||action,0));
 SELECT * INTO previous FROM organization_access.purchase_price_grant_history WHERE "CommandId"=command;
 IF FOUND THEN RETURN CASE WHEN previous."TenantId"=tenant AND previous."LegalEntityId"=company AND previous."ActorMembershipId"=actor AND previous."TargetMembershipId"=target AND previous."VerificationReference"=verification AND previous."Action"=action AND previous."Operation"=operation AND previous."Revision"::bigint=expected::bigint+1 THEN 'replayed' ELSE 'conflict' END; END IF;
 SELECT coalesce(max("Revision"),0) INTO revision_now FROM organization_access.purchase_price_grant_history WHERE "TenantId"=tenant AND "LegalEntityId"=company AND "TargetMembershipId"=target AND "Action"=action;
 IF expected IS DISTINCT FROM revision_now OR expected=2147483647 THEN RETURN 'conflict'; END IF;
 IF operation='grant' THEN
  IF NOT EXISTS(SELECT 1 FROM organization_access.company_permissions WHERE "TenantId"=tenant AND "MembershipId"=target AND "LegalEntityId"=company AND "Permission"=action AND "SiteId" IS NULL AND "WarehouseId" IS NULL) THEN
   INSERT INTO organization_access.company_permissions VALUES (gen_random_uuid(),target,tenant,company,action,NULL,NULL);
  END IF;
 ELSIF operation='revoke' THEN
  DELETE FROM organization_access.company_permissions WHERE "TenantId"=tenant AND "MembershipId"=target AND "LegalEntityId"=company AND "Permission"=action AND "SiteId" IS NULL AND "WarehouseId" IS NULL;
 ELSE RETURN 'invalid'; END IF;
 INSERT INTO organization_access.purchase_price_grant_history("CommandId","TenantId","LegalEntityId","ActorMembershipId","TargetMembershipId","VerificationReference","Revision","Action","Operation") VALUES(command,tenant,company,actor,target,verification,expected+1,action,operation);
 RETURN 'applied';
END $$;
REVOKE ALL ON FUNCTION organization_access.set_purchase_price_grant(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text) FROM PUBLIC;

CREATE FUNCTION organization_access.purchase_price_member(company uuid) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE member uuid; tenant uuid; BEGIN
 tenant:=nullif(current_setting('app.tenant_id',true),'')::uuid;
 SELECT m."Id",m."TenantId" INTO member,tenant FROM organization_access.memberships m JOIN organization_access.external_identity_bindings b ON b."InternalIdentityId"::text=m."IdentitySubject"
 WHERE (tenant IS NULL OR m."TenantId"=tenant) AND m."IdentitySubject"=current_setting('app.identity_subject',true) FOR SHARE OF m,b;
 IF member IS NULL THEN RETURN NULL; END IF;
 PERFORM set_config('app.tenant_id',tenant::text,true);
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."TenantId"=tenant AND p."MembershipId"=member AND p."LegalEntityId"=company AND p."Permission"='catalog.purchase-prices.read' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL FOR SHARE;
 IF NOT FOUND THEN RETURN NULL; END IF;
 RETURN member;
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_price_member(uuid) FROM PUBLIC;

CREATE FUNCTION organization_access.purchase_price_writable(company uuid) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
DECLARE member uuid; BEGIN
 member:=organization_access.purchase_price_member(company);
 IF member IS NULL THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."TenantId"::text=current_setting('app.tenant_id',true) AND p."MembershipId"=member AND p."LegalEntityId"=company AND p."Permission"='catalog.purchase-prices.manage' AND p."SiteId" IS NULL AND p."WarehouseId" IS NULL FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.capability_activations WHERE "LegalEntityId"=company AND "Capability"='catalog' AND "Enabled" FOR SHARE;
 RETURN FOUND;
END $$;
REVOKE ALL ON FUNCTION organization_access.purchase_price_writable(uuid) FROM PUBLIC;

-- Counterparties owns this public transaction-local source contract. No ERP identity is required or exposed.
CREATE FUNCTION counterparties.purchase_price_supplier(company uuid,record uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,counterparties AS $$
DECLARE tenant uuid; source jsonb; authority jsonb; BEGIN
 tenant:=nullif(current_setting('app.tenant_id',true),'')::uuid;
 PERFORM pg_advisory_xact_lock(hashtextextended('master-authority:'||tenant::text,0));
 SELECT jsonb_build_object('id',c."Id",'name',c."LegalName",'isSupplier',c."IsSupplier",'revision',coalesce((SELECT max(h."Revision") FROM counterparties.common_edit_history h WHERE h."CounterpartyId"=c."Id"),0)) INTO source
 FROM counterparties.counterparties c WHERE c."Id"=record AND c."TenantId"=tenant FOR SHARE OF c;
 IF source IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 authority:=organization_access.read_master_authority(company);
 RETURN source||jsonb_build_object('state','ready','authority',authority);
END $$;
REVOKE ALL ON FUNCTION counterparties.purchase_price_supplier(uuid,uuid) FROM PUBLIC;

CREATE FUNCTION catalog.supplier_purchase_price_state(company uuid,supplier uuid,item uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE vendor jsonb; product jsonb; history jsonb; latest jsonb; BEGIN
 IF organization_access.purchase_price_member(company) IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 vendor:=counterparties.purchase_price_supplier(company,supplier);
 IF vendor->>'state'<>'ready' THEN RETURN vendor; END IF;
 IF vendor->>'isSupplier'<>'true' THEN RETURN jsonb_build_object('state','not_supplier'); END IF;
 SELECT jsonb_build_object('id',i."Id",'label',i."Label",'version',i."Version") INTO product FROM catalog.items i WHERE i."Id"=item FOR SHARE;
 IF product IS NULL THEN RETURN jsonb_build_object('state','not_found'); END IF;
 PERFORM set_config('app.legal_entity_id',company::text,true);
 SELECT coalesce(jsonb_agg(jsonb_build_object('commandId',h."CommandId",'revision',h."Revision",'unitPurchasePrice',to_char(h."UnitPurchasePrice",'FM999990.000000'),
  'actorMembershipId',h."ActorMembershipId",'supplierRevision',h."SupplierRevision",'catalogVersion',h."CatalogVersion",'authorityVersion',h."AuthorityVersion",'recordedAt',h."RecordedAt") ORDER BY h."Revision" DESC),'[]'::jsonb) INTO history
 FROM catalog.supplier_purchase_price_history h WHERE h."LegalEntityId"=company AND h."SupplierId"=supplier AND h."CatalogItemId"=item;
 latest:=history->0;
 RETURN jsonb_build_object('state','ready','entry',latest,'history',history,'revision',coalesce((latest->>'revision')::integer,0),'provisionalUnitPurchasePrice',CASE WHEN latest IS NULL THEN '0.000000' ELSE NULL END,'requiresManualPrice',latest IS NULL,
  'supplier',vendor-'authority'-'state','item',product,'authorityVersion',vendor->'authority'->'version',
  'canManage',vendor->'authority'->>'state'='local' AND organization_access.purchase_price_writable(company),'writeState','master_'||(vendor->'authority'->>'state'));
END $$;
REVOKE ALL ON FUNCTION catalog.supplier_purchase_price_state(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.supplier_purchase_price_state(uuid,uuid,uuid) TO :"app_user";

CREATE FUNCTION catalog.set_supplier_purchase_price(company uuid,supplier uuid,item uuid,command uuid,expected integer,supplier_revision integer,catalog_version integer,authority_version integer,price_text text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE member uuid; tenant uuid; snapshot jsonb; payload jsonb; previous catalog.supplier_purchase_price_history; BEGIN
 PERFORM set_config('app.legal_entity_id',company::text,true);
 member:=organization_access.purchase_price_member(company);
 IF member IS NULL THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 tenant:=current_setting('app.tenant_id',true)::uuid;
 IF NOT organization_access.purchase_price_writable(company) THEN RETURN jsonb_build_object('state','forbidden'); END IF;
 IF command IS NULL OR command='00000000-0000-0000-0000-000000000000' OR company IS NULL OR supplier IS NULL OR item IS NULL OR expected IS NULL OR expected<0 OR supplier_revision IS NULL OR supplier_revision<0 OR catalog_version IS NULL OR catalog_version<1 OR authority_version IS NULL OR authority_version<1 OR price_text IS NULL OR length(price_text)>13 OR price_text !~ '^[0-9]{1,6}(\.[0-9]{1,6})?$' THEN RETURN jsonb_build_object('state','invalid'); END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(command::text,29));
 payload:=jsonb_build_object('legalEntityId',company,'supplierId',supplier,'catalogItemId',item,'expectedRevision',expected,'supplierRevision',supplier_revision,'catalogVersion',catalog_version,'authorityVersion',authority_version,'unitPurchasePrice',price_text);
 SELECT * INTO previous FROM catalog.supplier_purchase_price_history WHERE "CommandId"=command;
 IF FOUND THEN
  IF previous."ActorMembershipId"=member AND previous."Payload"=payload THEN RETURN jsonb_build_object('state','replayed','commandId',command,'revision',previous."Revision"); END IF;
  RETURN jsonb_build_object('state','conflict');
 END IF;
 snapshot:=catalog.supplier_purchase_price_state(company,supplier,item);
 IF snapshot->>'state'<>'ready' THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF snapshot->>'writeState'<>'master_local' THEN RETURN jsonb_build_object('state',snapshot->>'writeState'); END IF;
 IF supplier_revision IS DISTINCT FROM (snapshot->'supplier'->>'revision')::integer OR catalog_version IS DISTINCT FROM (snapshot->'item'->>'version')::integer OR authority_version IS DISTINCT FROM (snapshot->>'authorityVersion')::integer THEN RETURN jsonb_build_object('state','conflict'); END IF;
 IF expected IS DISTINCT FROM (snapshot->>'revision')::integer OR expected=2147483647 THEN RETURN jsonb_build_object('state','conflict'); END IF;
 INSERT INTO catalog.supplier_purchase_price_history("CommandId","TenantId","LegalEntityId","SupplierId","CatalogItemId","Revision","UnitPurchasePrice","ActorMembershipId","SupplierRevision","CatalogVersion","AuthorityVersion","Payload")
 VALUES(command,tenant,company,supplier,item,expected+1,price_text::numeric,member,supplier_revision,catalog_version,authority_version,payload);
 RETURN jsonb_build_object('state','applied','commandId',command,'revision',expected+1);
EXCEPTION WHEN unique_violation THEN RETURN jsonb_build_object('state','conflict');
END $$;
REVOKE ALL ON FUNCTION catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text) TO :"app_user";
