-- Destructive B03 rollback: export any required synthetic results before running.
BEGIN;
DROP SCHEMA IF EXISTS counterparties CASCADE;
DROP TABLE IF EXISTS organization_access.common_edit_permissions;
DROP TABLE IF EXISTS organization_access.company_permissions;
COMMIT;
-- B02 schema/tables/data are intentionally retained.
