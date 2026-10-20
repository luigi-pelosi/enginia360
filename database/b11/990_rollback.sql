BEGIN;
-- Never downgrade uncertain work to a state whose old worker could blindly resubmit.
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM integrations.administrative_dispatches WHERE "State" IN ('Uncertain','NeedsReconciliation')) THEN
  RAISE EXCEPTION 'B11 rollback blocked: unresolved uncertainty; stop worker and reconcile or restore a compatible backup';
 END IF;
END $$;
DROP FUNCTION IF EXISTS workshop.pending_administrative_outbox(integer,integer);
DROP TABLE IF EXISTS integrations.administrative_reconciliations;
ALTER TABLE integrations.administrative_dispatches DROP COLUMN IF EXISTS "Failures";
ALTER TABLE integrations.administrative_dispatches DROP CONSTRAINT IF EXISTS "administrative_dispatches_State_check";
ALTER TABLE integrations.administrative_dispatches ADD CONSTRAINT "administrative_dispatches_State_check"
 CHECK ("State" IN ('Queued','Received','Retrying','Completed','Rejected'));
COMMIT;
