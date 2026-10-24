-- R03.b: Workshop-owned own-time facts. No fixtures, commercial revisions or monetary effects.
CREATE TABLE workshop.own_actual_time_streams (
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "MembershipId" uuid NOT NULL CHECK ("MembershipId" <> '00000000-0000-0000-0000-000000000000'),
 "Revision" integer NOT NULL CHECK ("Revision">=0),
 PRIMARY KEY ("TenantId","OrderId","MembershipId"),
 FOREIGN KEY ("TenantId","OrderId") REFERENCES workshop.orders ("TenantId","Id")
);
CREATE TABLE workshop.actual_time_group_references (
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "WorkingGroupId" uuid NOT NULL,
 PRIMARY KEY ("TenantId","OrderId","WorkingGroupId"),
 FOREIGN KEY ("TenantId","OrderId","WorkingGroupId") REFERENCES workshop.working_groups ("TenantId","OrderId","Id")
);
CREATE TABLE workshop.own_actual_time_entries (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "MembershipId" uuid NOT NULL,
 "InternalIdentityId" uuid NOT NULL CHECK ("InternalIdentityId" <> '00000000-0000-0000-0000-000000000000'),
 "WorkingGroupId" uuid NOT NULL,
 UNIQUE ("TenantId","OrderId","MembershipId","Id","InternalIdentityId"),
 FOREIGN KEY ("TenantId","OrderId","MembershipId") REFERENCES workshop.own_actual_time_streams ("TenantId","OrderId","MembershipId"),
 FOREIGN KEY ("TenantId","OrderId","WorkingGroupId") REFERENCES workshop.actual_time_group_references ("TenantId","OrderId","WorkingGroupId")
);
CREATE TABLE workshop.own_actual_time_versions (
 "EntryId" uuid NOT NULL, "Version" integer NOT NULL CHECK ("Version">0),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "MembershipId" uuid NOT NULL, "InternalIdentityId" uuid NOT NULL,
 "WorkDate" date NOT NULL CHECK ("WorkDate" BETWEEN DATE '0001-01-01' AND DATE '9999-12-31'),
 "DurationSeconds" integer NOT NULL CHECK ("DurationSeconds">0), "Note" text NOT NULL CHECK (length("Note")<=500 AND "Note" !~ '[[:cntrl:]]'),
 "CorrectionNote" text CHECK ("CorrectionNote" IS NULL OR length("CorrectionNote")<=500 AND "CorrectionNote" !~ '[[:cntrl:]]'),
 "CommandId" uuid NOT NULL UNIQUE CHECK ("CommandId" <> '00000000-0000-0000-0000-000000000000'),
 "OwnRevision" integer NOT NULL CHECK ("OwnRevision">0), "RecordedAt" timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY ("EntryId","Version"),
 UNIQUE ("TenantId","OrderId","MembershipId","OwnRevision"),
 FOREIGN KEY ("TenantId","OrderId","MembershipId","EntryId","InternalIdentityId") REFERENCES workshop.own_actual_time_entries ("TenantId","OrderId","MembershipId","Id","InternalIdentityId")
);
CREATE TABLE workshop.own_actual_time_commands (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "MembershipId" uuid NOT NULL, "InternalIdentityId" uuid NOT NULL,
 "EntryId" uuid NOT NULL, "Canonical" jsonb NOT NULL, "Receipt" jsonb NOT NULL,
 FOREIGN KEY ("TenantId","OrderId","MembershipId","EntryId","InternalIdentityId") REFERENCES workshop.own_actual_time_entries ("TenantId","OrderId","MembershipId","Id","InternalIdentityId")
);
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['own_actual_time_streams','own_actual_time_entries','own_actual_time_versions','own_actual_time_commands','actual_time_group_references'] LOOP
  EXECUTE format('ALTER TABLE workshop.%I ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE workshop.%I FORCE ROW LEVEL SECURITY',target);
  IF target='actual_time_group_references' THEN
   EXECUTE format('CREATE POLICY tenant_identity ON workshop.%I USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
  ELSE
   EXECUTE format('CREATE POLICY own_identity ON workshop.%I USING ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "MembershipId"::text=current_setting(''app.workshop_actor_membership_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true) AND "MembershipId"::text=current_setting(''app.workshop_actor_membership_id'',true))',target);
  END IF;
  IF target<>'own_actual_time_streams' THEN
   EXECUTE format('CREATE TRIGGER immutable_actual_time BEFORE UPDATE OR DELETE OR TRUNCATE ON workshop.%I FOR EACH STATEMENT EXECUTE FUNCTION workshop.immutable_workspace()',target);
  END IF;
 END LOOP;
END $$;
GRANT SELECT,INSERT ON workshop.own_actual_time_streams,workshop.own_actual_time_entries,workshop.own_actual_time_versions,workshop.own_actual_time_commands,workshop.actual_time_group_references TO :"app_user";
GRANT UPDATE ("Revision") ON workshop.own_actual_time_streams TO :"app_user";

CREATE FUNCTION workshop.guard_actual_time_version() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,workshop AS $$
DECLARE previous integer; stream_revision integer;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW."OrderId"::text,0));
 SELECT coalesce(max("Version"),0) INTO previous FROM workshop.own_actual_time_versions WHERE "EntryId"=NEW."EntryId";
 SELECT "Revision" INTO stream_revision FROM workshop.own_actual_time_streams WHERE "TenantId"=NEW."TenantId" AND "OrderId"=NEW."OrderId" AND "MembershipId"=NEW."MembershipId";
 IF NEW."Version"::bigint<>previous::bigint+1 OR NEW."OwnRevision"::bigint<>stream_revision::bigint+1
   OR (NEW."Version"=1)<>(NEW."CorrectionNote" IS NULL) THEN RAISE EXCEPTION 'actual_time_version_chain'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER actual_time_version_chain BEFORE INSERT ON workshop.own_actual_time_versions FOR EACH ROW EXECUTE FUNCTION workshop.guard_actual_time_version();
CREATE FUNCTION workshop.guard_actual_time_stream() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,workshop AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW."Revision"<>0 THEN RAISE EXCEPTION 'actual_time_stream_starts_zero'; END IF;
 ELSE
  IF (to_jsonb(NEW)-'Revision') IS DISTINCT FROM (to_jsonb(OLD)-'Revision') OR NEW."Revision"::bigint<>OLD."Revision"::bigint+1
    OR NOT EXISTS (SELECT 1 FROM workshop.own_actual_time_versions WHERE "TenantId"=NEW."TenantId" AND "OrderId"=NEW."OrderId" AND "MembershipId"=NEW."MembershipId" AND "OwnRevision"=NEW."Revision")
   THEN RAISE EXCEPTION 'actual_time_stream_chain'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER actual_time_stream_chain BEFORE INSERT OR UPDATE ON workshop.own_actual_time_streams FOR EACH ROW EXECUTE FUNCTION workshop.guard_actual_time_stream();
REVOKE ALL ON FUNCTION workshop.guard_actual_time_version(),workshop.guard_actual_time_stream() FROM PUBLIC;

-- Deferred owner-local integrity: no committed half-fact, orphan receipt or empty technical reference.
-- Invoker functions keep forced owner RLS; no cross-operator fact reads are introduced.
CREATE FUNCTION workshop.check_actual_time_complete() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,workshop AS $$
DECLARE v workshop.own_actual_time_versions; c workshop.own_actual_time_commands; e workshop.own_actual_time_entries; expected jsonb;
BEGIN
 IF TG_TABLE_NAME='actual_time_group_references' THEN
  IF NOT EXISTS (SELECT 1 FROM workshop.own_actual_time_entries WHERE "TenantId"=NEW."TenantId" AND "OrderId"=NEW."OrderId" AND "WorkingGroupId"=NEW."WorkingGroupId")
   THEN RAISE EXCEPTION 'actual_time_reference_without_fact'; END IF;
  RETURN NULL;
 END IF;
 IF TG_TABLE_NAME='own_actual_time_entries' THEN
  IF NOT EXISTS (SELECT 1 FROM workshop.own_actual_time_versions WHERE "EntryId"=NEW."Id" AND "Version"=1)
   THEN RAISE EXCEPTION 'actual_time_entry_without_version'; END IF;
  RETURN NULL;
 END IF;
 SELECT * INTO v FROM workshop.own_actual_time_versions WHERE "CommandId"=NEW."CommandId";
 SELECT * INTO c FROM workshop.own_actual_time_commands WHERE "CommandId"=NEW."CommandId";
 IF v."EntryId" IS NULL OR c."EntryId" IS NULL OR (v."TenantId",v."OrderId",v."MembershipId",v."InternalIdentityId",v."EntryId")
   IS DISTINCT FROM (c."TenantId",c."OrderId",c."MembershipId",c."InternalIdentityId",c."EntryId") THEN RAISE EXCEPTION 'actual_time_incomplete_command'; END IF;
 SELECT * INTO e FROM workshop.own_actual_time_entries WHERE "Id"=v."EntryId";
 expected=jsonb_build_object('commandId',v."CommandId",'orderId',v."OrderId",'entryId',v."EntryId",'appliedOwnRevision',v."OwnRevision",'entryVersion',v."Version",'resultKind',CASE WHEN v."Version"=1 THEN 'Created' ELSE 'Corrected' END);
 IF c."Receipt" IS DISTINCT FROM expected THEN RAISE EXCEPTION 'actual_time_receipt_mismatch'; END IF;
 expected=jsonb_build_object('commandId',v."CommandId",'expectedOwnRevision',v."OwnRevision"-1,'workDate',to_char(v."WorkDate",'YYYY-MM-DD'),'durationSeconds',v."DurationSeconds",'note',v."Note");
 IF v."Version"=1 THEN
  expected=expected||jsonb_build_object('entryId',v."EntryId",'workingGroupId',e."WorkingGroupId",'expectedGroupVersion',c."Canonical"->'expectedGroupVersion');
  IF (c."Canonical"->>'expectedGroupVersion')::integer IS NULL OR (c."Canonical"->>'expectedGroupVersion')::integer<=0 THEN RAISE EXCEPTION 'actual_time_group_version_missing'; END IF;
 ELSE
  expected=expected||jsonb_build_object('expectedEntryVersion',v."Version"-1,'correctionNote',v."CorrectionNote");
 END IF;
 IF c."Canonical" IS DISTINCT FROM expected THEN RAISE EXCEPTION 'actual_time_canonical_mismatch'; END IF;
 IF NOT EXISTS (SELECT 1 FROM workshop.own_actual_time_streams s WHERE s."TenantId"=v."TenantId" AND s."OrderId"=v."OrderId" AND s."MembershipId"=v."MembershipId"
  AND s."Revision"=(SELECT max(n."OwnRevision") FROM workshop.own_actual_time_versions n WHERE n."TenantId"=s."TenantId" AND n."OrderId"=s."OrderId" AND n."MembershipId"=s."MembershipId"))
  THEN RAISE EXCEPTION 'actual_time_stream_incomplete'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER actual_time_complete AFTER INSERT ON workshop.own_actual_time_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workshop.check_actual_time_complete();
CREATE CONSTRAINT TRIGGER actual_time_complete AFTER INSERT ON workshop.own_actual_time_commands DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workshop.check_actual_time_complete();
CREATE CONSTRAINT TRIGGER actual_time_complete AFTER INSERT ON workshop.own_actual_time_entries DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workshop.check_actual_time_complete();
CREATE CONSTRAINT TRIGGER actual_time_complete AFTER INSERT ON workshop.actual_time_group_references DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workshop.check_actual_time_complete();
REVOKE ALL ON FUNCTION workshop.check_actual_time_complete() FROM PUBLIC;
