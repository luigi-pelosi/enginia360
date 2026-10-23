-- R03.a: persisted order workspace. Append-only unit; never edit published units. No business seed data.
-- The migration owner is subject to forced RLS: it is relaxed only for the backfill below and restored in this unit.
ALTER TABLE workshop.orders NO FORCE ROW LEVEL SECURITY;
ALTER TABLE workshop.commercial_lines NO FORCE ROW LEVEL SECURITY;

ALTER TABLE workshop.orders ADD COLUMN "CommercialRevision" integer NOT NULL DEFAULT 0 CHECK ("CommercialRevision" >= 0);
-- Policy attribute only: whether the document profile admits several working groups. Default keeps every existing policy single-group.
ALTER TABLE workshop.line_policies ADD COLUMN "MultipleWorkingGroups" boolean NOT NULL DEFAULT false;
ALTER TABLE workshop.commercial_lines
 ADD COLUMN "Description" varchar(500) CHECK ("Description" IS NULL OR length("Description") BETWEEN 1 AND 500),
 ADD COLUMN "State" varchar(10) NOT NULL DEFAULT 'Active' CHECK ("State" IN ('Active','Removed')),
 ADD COLUMN "Version" integer NOT NULL DEFAULT 1 CHECK ("Version" > 0);

CREATE TABLE workshop.working_groups (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL,
 "Title" varchar(100) NOT NULL CHECK (length(btrim("Title")) BETWEEN 1 AND 100),
 "State" varchar(10) NOT NULL CHECK ("State" IN ('Active','Removed')),
 "Version" integer NOT NULL CHECK ("Version" > 0),
 "CreatedRevision" integer NOT NULL CHECK ("CreatedRevision" >= 0),
 UNIQUE ("TenantId","OrderId","Id"),
 FOREIGN KEY ("TenantId","OrderId") REFERENCES workshop.orders ("TenantId","Id")
);
CREATE INDEX working_group_order ON workshop.working_groups ("TenantId","OrderId","CreatedRevision");
CREATE TABLE workshop.order_notes (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL, "WorkingGroupId" uuid NOT NULL,
 "Description" varchar(500) NOT NULL CHECK (length("Description") BETWEEN 1 AND 500),
 "State" varchar(10) NOT NULL CHECK ("State" IN ('Active','Removed')),
 "Version" integer NOT NULL CHECK ("Version" > 0),
 "CreatedRevision" integer NOT NULL CHECK ("CreatedRevision" >= 0),
 FOREIGN KEY ("TenantId","OrderId","WorkingGroupId") REFERENCES workshop.working_groups ("TenantId","OrderId","Id")
);
CREATE INDEX order_note_order ON workshop.order_notes ("TenantId","OrderId","CreatedRevision");
-- Insert-only version history of every group, row and note (jsonb snapshot of the saved state).
CREATE TABLE workshop.workspace_history (
 "TargetKind" varchar(10) NOT NULL CHECK ("TargetKind" IN ('Group','Line','Note')),
 "TargetId" uuid NOT NULL, "Version" integer NOT NULL CHECK ("Version" > 0),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL,
 "Revision" integer NOT NULL CHECK ("Revision" >= 0),
 "Operation" varchar(12) NOT NULL CHECK ("Operation" IN ('Baseline','Created','Updated','Removed')),
 "CommandId" uuid,
 "Snapshot" jsonb NOT NULL,
 PRIMARY KEY ("TargetKind","TargetId","Version"),
 FOREIGN KEY ("TenantId","OrderId") REFERENCES workshop.orders ("TenantId","Id")
);
CREATE INDEX workspace_history_order ON workshop.workspace_history ("TenantId","OrderId","Revision");
-- Immutable receipts: the exact original answer survives later edits, policy changes and closure.
CREATE TABLE workshop.editor_commands (
 "CommandId" uuid PRIMARY KEY CHECK ("CommandId" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "OrderId" uuid NOT NULL,
 "Type" varchar(30) NOT NULL,
 "Canonical" jsonb NOT NULL,
 "TargetId" uuid NOT NULL,
 "InitialRevision" integer NOT NULL CHECK ("InitialRevision" >= 0),
 "AppliedRevision" integer NOT NULL CHECK ("AppliedRevision" > "InitialRevision"),
 "ResultKind" varchar(10) NOT NULL CHECK ("ResultKind" IN ('Created','Updated','Removed')),
 "LinePolicyVersion" integer, "StructurePolicyVersion" integer NOT NULL,
 FOREIGN KEY ("TenantId","OrderId") REFERENCES workshop.orders ("TenantId","Id")
);
CREATE INDEX editor_command_order ON workshop.editor_commands ("TenantId","OrderId","AppliedRevision");

-- Backfill (owner relaxed above): the legacy working group is the order itself; revision keeps the historical line count.
UPDATE workshop.orders o SET "CommercialRevision" = (SELECT count(*) FROM workshop.commercial_lines l WHERE l."OrderId" = o."Id" AND l."TenantId" = o."TenantId");
ALTER TABLE workshop.working_groups NO FORCE ROW LEVEL SECURITY;
INSERT INTO workshop.working_groups ("Id","TenantId","OrderId","Title","State","Version","CreatedRevision")
 SELECT o."Id", o."TenantId", o."Id", 'Lavorazione', 'Active', 1, 0 FROM workshop.orders o
 WHERE EXISTS (SELECT 1 FROM workshop.commercial_lines l WHERE l."OrderId" = o."Id" AND l."TenantId" = o."TenantId");
ALTER TABLE workshop.workspace_history NO FORCE ROW LEVEL SECURITY;
INSERT INTO workshop.workspace_history ("TargetKind","TargetId","Version","TenantId","OrderId","Revision","Operation","Snapshot")
 SELECT 'Group', g."Id", 1, g."TenantId", g."OrderId", o."CommercialRevision", 'Baseline', to_jsonb(g) FROM workshop.working_groups g JOIN workshop.orders o ON o."Id" = g."OrderId";
INSERT INTO workshop.workspace_history ("TargetKind","TargetId","Version","TenantId","OrderId","Revision","Operation","Snapshot")
 SELECT 'Line', l."Id", 1, l."TenantId", l."OrderId", o."CommercialRevision", 'Baseline', to_jsonb(l) FROM workshop.commercial_lines l JOIN workshop.orders o ON o."Id" = l."OrderId";

-- One kind per order and group=order were fixture-profile rules; membership is now a composite foreign key.
DO $$ DECLARE c text; BEGIN
 FOR c IN SELECT conname FROM pg_constraint WHERE conrelid = 'workshop.commercial_lines'::regclass
   AND ((contype = 'u' AND pg_get_constraintdef(oid) = 'UNIQUE ("TenantId", "OrderId", "Kind")')
     OR (contype = 'c' AND pg_get_constraintdef(oid) LIKE 'CHECK (("WorkingGroupId" = "OrderId"))%')) LOOP
  EXECUTE format('ALTER TABLE workshop.commercial_lines DROP CONSTRAINT %I', c);
 END LOOP;
 IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'workshop.commercial_lines'::regclass AND (contype = 'u' AND pg_get_constraintdef(oid) LIKE '%"Kind"%'
   OR contype = 'c' AND pg_get_constraintdef(oid) LIKE '%"WorkingGroupId" = "OrderId"%')) THEN
  RAISE EXCEPTION 'legacy single-row constraints not removed';
 END IF;
END $$;
ALTER TABLE workshop.commercial_lines ADD CONSTRAINT commercial_line_group
 FOREIGN KEY ("TenantId","OrderId","WorkingGroupId") REFERENCES workshop.working_groups ("TenantId","OrderId","Id");
CREATE INDEX commercial_line_group ON workshop.commercial_lines ("TenantId","OrderId","WorkingGroupId");

CREATE FUNCTION workshop.guard_order_revision() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, workshop AS $$
BEGIN
 IF (to_jsonb(NEW) - 'CommercialRevision') IS DISTINCT FROM (to_jsonb(OLD) - 'CommercialRevision') THEN
  RAISE EXCEPTION 'saved order identity is immutable';
 END IF;
 IF NEW."CommercialRevision" NOT IN (OLD."CommercialRevision", OLD."CommercialRevision" + 1) THEN
  RAISE EXCEPTION 'commercial revision is monotonic';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_order_revision BEFORE UPDATE ON workshop.orders FOR EACH ROW EXECUTE FUNCTION workshop.guard_order_revision();

CREATE FUNCTION workshop.guard_line_update() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, workshop AS $$
BEGIN
 IF (NEW."Id",NEW."TenantId",NEW."OrderId",NEW."CatalogItemId",NEW."CatalogVersion",NEW."CatalogLabel",NEW."Kind",NEW."TaxRate",
     NEW."PayerId",NEW."WorkingGroupId",NEW."ConfigurationVersion",NEW."ExpectedRevision")
    IS DISTINCT FROM (OLD."Id",OLD."TenantId",OLD."OrderId",OLD."CatalogItemId",OLD."CatalogVersion",OLD."CatalogLabel",OLD."Kind",OLD."TaxRate",
     OLD."PayerId",OLD."WorkingGroupId",OLD."ConfigurationVersion",OLD."ExpectedRevision") THEN
  RAISE EXCEPTION 'saved line identity is immutable';
 END IF;
 IF NEW."Version" <> OLD."Version" + 1 THEN RAISE EXCEPTION 'every line change creates exactly one version'; END IF;
 IF OLD."State" = 'Removed' AND NEW."State" <> 'Removed' THEN RAISE EXCEPTION 'removal is a permanent tombstone'; END IF;
 -- R03.a delivers no structural Part change: a Part keeps its quantity and cannot be removed (material_structure_edit_not_supported).
 IF OLD."Kind" = 'Part' AND (NEW."Quantity" <> OLD."Quantity" OR NEW."State" <> OLD."State") THEN
  RAISE EXCEPTION 'material_structure_edit_not_supported';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_line_update BEFORE UPDATE ON workshop.commercial_lines FOR EACH ROW EXECUTE FUNCTION workshop.guard_line_update();

CREATE FUNCTION workshop.guard_workspace_item() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, workshop AS $$
BEGIN
 IF (to_jsonb(NEW) - 'Title' - 'Description' - 'State' - 'Version') IS DISTINCT FROM (to_jsonb(OLD) - 'Title' - 'Description' - 'State' - 'Version') THEN
  RAISE EXCEPTION 'saved workspace identity is immutable';
 END IF;
 IF NEW."Version" <> OLD."Version" + 1 THEN RAISE EXCEPTION 'every change creates exactly one version'; END IF;
 IF OLD."State" = 'Removed' AND NEW."State" <> 'Removed' THEN RAISE EXCEPTION 'removal is a permanent tombstone'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_group_update BEFORE UPDATE ON workshop.working_groups FOR EACH ROW EXECUTE FUNCTION workshop.guard_workspace_item();
CREATE TRIGGER guard_note_update BEFORE UPDATE ON workshop.order_notes FOR EACH ROW EXECUTE FUNCTION workshop.guard_workspace_item();

CREATE FUNCTION workshop.immutable_workspace() RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN RAISE EXCEPTION 'append-only workspace record'; END $$;
CREATE TRIGGER immutable_workspace_history BEFORE UPDATE OR DELETE OR TRUNCATE ON workshop.workspace_history FOR EACH STATEMENT EXECUTE FUNCTION workshop.immutable_workspace();
CREATE TRIGGER immutable_editor_commands BEFORE UPDATE OR DELETE OR TRUNCATE ON workshop.editor_commands FOR EACH STATEMENT EXECUTE FUNCTION workshop.immutable_workspace();

DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.orders','workshop.commercial_lines','workshop.working_groups','workshop.order_notes','workshop.workspace_history','workshop.editor_commands'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s', target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))', target);
 END LOOP;
END $$;
GRANT UPDATE ("CommercialRevision") ON workshop.orders TO :"app_user";
GRANT UPDATE ("Quantity","UnitPrice","DiscountPercent","NetAmount","Description","State","Version") ON workshop.commercial_lines TO :"app_user";
GRANT SELECT, INSERT ON workshop.working_groups, workshop.order_notes, workshop.workspace_history, workshop.editor_commands TO :"app_user";
GRANT UPDATE ("Title","State","Version") ON workshop.working_groups TO :"app_user";
GRANT UPDATE ("Description","State","Version") ON workshop.order_notes TO :"app_user";
