-- DESTRUCTIVE synthetic-fixture rollback only. It discards closures, requests, outcomes and delivery state:
-- never use it on retained data, where an external system may already hold the request. Back up first.
BEGIN;
DROP FUNCTION IF EXISTS workshop.pending_administrative_outbox(integer);
DROP SCHEMA IF EXISTS integrations CASCADE;
DROP TABLE IF EXISTS workshop.administrative_closures;
DROP TABLE IF EXISTS workshop.administrative_outcomes;
DROP TABLE IF EXISTS workshop.administrative_outbox;
DROP TABLE IF EXISTS workshop.administrative_requests;
DROP TABLE IF EXISTS workshop.technical_closures;
DROP TABLE IF EXISTS workshop.administrative_destinations;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='enginia360_outbox_reader') THEN
  IF to_regnamespace('workshop') IS NOT NULL THEN REVOKE ALL ON SCHEMA workshop FROM enginia360_outbox_reader; END IF;
  DROP ROLE enginia360_outbox_reader;
 END IF;
END $$;
DELETE FROM organization_access.capability_activations WHERE "Capability"='external-administration';
COMMIT;
