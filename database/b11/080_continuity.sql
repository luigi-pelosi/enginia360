BEGIN;
-- B11: uncertainty is distinct from a known retryable transport failure. Never blindly resubmit.
ALTER TABLE integrations.administrative_dispatches DROP CONSTRAINT IF EXISTS "administrative_dispatches_State_check";
ALTER TABLE integrations.administrative_dispatches ADD CONSTRAINT "administrative_dispatches_State_check"
 CHECK ("State" IN ('Queued','Received','Retrying','Uncertain','NeedsReconciliation','Completed','Rejected'));
ALTER TABLE integrations.administrative_dispatches ADD COLUMN IF NOT EXISTS "Failures" integer NOT NULL DEFAULT 0 CHECK ("Failures">=0);
GRANT UPDATE ("Failures") ON integrations.administrative_dispatches TO :"app_user";
CREATE TABLE IF NOT EXISTS integrations.administrative_reconciliations (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL, "RequestId" uuid NOT NULL REFERENCES integrations.administrative_dispatches("RequestId"),
 "OperatorId" uuid NOT NULL, "RequestedAt" timestamptz NOT NULL
);
ALTER TABLE integrations.administrative_reconciliations ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations.administrative_reconciliations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_identity ON integrations.administrative_reconciliations;
CREATE POLICY tenant_identity ON integrations.administrative_reconciliations USING ("TenantId"::text=current_setting('app.tenant_id',true))
 WITH CHECK ("TenantId"::text=current_setting('app.tenant_id',true));
GRANT SELECT,INSERT ON integrations.administrative_reconciliations TO :"app_user";
-- Fair bounded envelope discovery; preserves the NOLOGIN owner's column-only grants and payload isolation.
CREATE OR REPLACE FUNCTION workshop.pending_administrative_outbox(max_items integer, scan_offset integer)
RETURNS TABLE ("TenantId" uuid, "RequestId" uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
 SELECT o."TenantId",o."RequestId" FROM workshop.administrative_outbox o
 WHERE NOT EXISTS (SELECT 1 FROM workshop.administrative_outcomes r WHERE r."RequestId"=o."RequestId")
 ORDER BY o."CreatedAt",o."RequestId" LIMIT least(greatest(max_items,1),100) OFFSET greatest(scan_offset,0)
$$;
ALTER FUNCTION workshop.pending_administrative_outbox(integer,integer) OWNER TO enginia360_outbox_reader;
REVOKE ALL ON FUNCTION workshop.pending_administrative_outbox(integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION workshop.pending_administrative_outbox(integer,integer) TO :"app_user";
COMMIT;
