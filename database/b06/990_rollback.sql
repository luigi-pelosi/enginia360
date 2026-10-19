-- Destructive rollback: ONLY the verified ephemeral B06 synthetic fixture.
-- Deletes all B06 reservations and stock. Never use on a retained environment.
BEGIN;
DROP SCHEMA IF EXISTS inventory CASCADE;
COMMIT;
