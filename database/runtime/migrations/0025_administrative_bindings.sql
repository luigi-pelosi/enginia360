-- R05.b.0: request-time technical binding of the existing synthetic connector only.
-- Published requests remain byte-for-byte unchanged; historical requests are NOT backfilled.
ALTER TABLE workshop.administrative_requests ADD CONSTRAINT administrative_binding_provenance
 UNIQUE ("Id","TenantId","OrderId","LegalEntityId","SiteId","DestinationVersion","ContractVersion","RequestedAt","OperatorId");
CREATE TABLE workshop.administrative_bindings (
 "RequestId" uuid PRIMARY KEY,
 "TenantId" uuid NOT NULL,
 "OrderId" uuid NOT NULL,
 "LegalEntityId" uuid NOT NULL,
 "SiteId" uuid NOT NULL,
 "DestinationVersion" integer NOT NULL,
 "ContractVersion" integer NOT NULL,
 "RequestedAt" timestamptz NOT NULL,
 "OperatorId" uuid NOT NULL,
 "Kind" text NOT NULL CHECK ("Kind"='SimulatorV1'),
 "ProtocolVersion" integer NOT NULL CHECK ("ProtocolVersion"=1),
 "DestinationFingerprint" text NOT NULL CHECK ("DestinationFingerprint" ~ '^[0-9a-f]{64}$'),
 FOREIGN KEY ("RequestId","TenantId","OrderId","LegalEntityId","SiteId","DestinationVersion","ContractVersion","RequestedAt","OperatorId")
 REFERENCES workshop.administrative_requests ("Id","TenantId","OrderId","LegalEntityId","SiteId","DestinationVersion","ContractVersion","RequestedAt","OperatorId")
);
ALTER TABLE workshop.administrative_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE workshop.administrative_bindings FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_identity ON workshop.administrative_bindings
 USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
CREATE FUNCTION workshop.immutable_administrative_binding() RETURNS trigger LANGUAGE plpgsql AS $$
 BEGIN RAISE EXCEPTION 'administrative_binding_is_immutable'; END $$;
CREATE TRIGGER immutable_administrative_binding BEFORE UPDATE OR DELETE OR TRUNCATE ON workshop.administrative_bindings
 FOR EACH STATEMENT EXECUTE FUNCTION workshop.immutable_administrative_binding();
REVOKE ALL ON FUNCTION workshop.immutable_administrative_binding() FROM PUBLIC;
-- Bind only beside the original request INSERT in that same transaction. Even an
-- otherwise authorized app role cannot assign a current descriptor to old history.
CREATE FUNCTION workshop.guard_administrative_binding_creation() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,workshop AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM workshop.administrative_requests r
     WHERE r."Id"=NEW."RequestId" AND r."TenantId"=NEW."TenantId"
       AND r.xmin=pg_current_xact_id()::text::xid)
 THEN RAISE EXCEPTION 'administrative_binding_requires_original_transaction'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER administrative_binding_creation BEFORE INSERT ON workshop.administrative_bindings
 FOR EACH ROW EXECUTE FUNCTION workshop.guard_administrative_binding_creation();
REVOKE ALL ON FUNCTION workshop.guard_administrative_binding_creation() FROM PUBLIC;
-- OrganizationAccess-owned public fence on the caller's connection: no nested pool
-- and no Workshop query of another module's private tables. Exact existing action.
CREATE FUNCTION organization_access.administrative_request_authorized(tenant uuid, member uuid, identity_subject text, company uuid, site uuid)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,organization_access AS $$
BEGIN
 IF tenant::text IS DISTINCT FROM current_setting('app.tenant_id',true)
 OR identity_subject IS DISTINCT FROM current_setting('app.identity_subject',true) THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.memberships m WHERE m."TenantId"=tenant AND m."Id"=member AND m."IdentitySubject"=identity_subject FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.sites s WHERE s."Id"=site AND s."TenantId"=tenant AND s."LegalEntityId"=company FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=member AND p."TenantId"=tenant AND p."LegalEntityId"=company
  AND p."Permission"='workshop.administrative-requests.create' AND p."WarehouseId" IS NULL AND (p."SiteId" IS NULL OR p."SiteId"=site) FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.capability_activations c WHERE c."LegalEntityId"=company AND c."Capability"='workshop' AND c."Enabled" FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 PERFORM 1 FROM organization_access.capability_activations c WHERE c."LegalEntityId"=company AND c."Capability"='external-administration' AND c."Enabled" FOR SHARE;
 IF NOT FOUND THEN RETURN false; END IF;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid) TO :"app_user";
GRANT SELECT,INSERT ON workshop.administrative_bindings TO :"app_user";
