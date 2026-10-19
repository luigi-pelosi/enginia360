-- Destructive, isolated synthetic proof only. Never run on a persistent environment.
BEGIN;
DROP SCHEMA IF EXISTS workshop CASCADE;
DROP SCHEMA IF EXISTS vehicles CASCADE;
DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE 'workshop.%';
DELETE FROM organization_access.capability_activations WHERE "Capability" = 'workshop';
DELETE FROM counterparties.counterparties WHERE "Id" = '11111111-3333-0000-0000-000000000002';
COMMIT;
-- Reapply the B03 synthetic fixtures to restore grants deliberately narrowed by B04.
