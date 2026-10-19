-- Ephemeral B05 only. Export data before any future persisted rollback; no persistent deployment authorized.
BEGIN;
DROP TABLE IF EXISTS workshop.commercial_lines;
DROP TABLE IF EXISTS workshop.line_policies;
DROP INDEX IF EXISTS workshop.orders_tenant_id;
DROP SCHEMA IF EXISTS catalog CASCADE;
DELETE FROM organization_access.company_permissions WHERE "Permission"='workshop.lines.add';
COMMIT;
