-- DESTRUCTIVE synthetic-fixture rollback only, never a disposal or compensation of real received carcasses.
-- Stop writes and retain a full backup before any application/schema rollback.
BEGIN;
DROP TABLE IF EXISTS inventory.carcass_return_installations;
DROP TABLE IF EXISTS inventory.carcass_returns;
DROP TABLE IF EXISTS inventory.carcass_locations;
DROP TABLE IF EXISTS workshop.carcass_policies;
DO $$ BEGIN
 IF to_regclass('workshop.installations') IS NOT NULL THEN
  ALTER TABLE workshop.installations DROP CONSTRAINT IF EXISTS installation_carcass_snapshot;
  ALTER TABLE workshop.installations DROP COLUMN IF EXISTS "CarcassReturnRequired";
  ALTER TABLE workshop.installations DROP COLUMN IF EXISTS "CarcassPolicyVersion";
  DROP INDEX IF EXISTS workshop.installation_order;
 END IF;
END $$;
COMMIT;
