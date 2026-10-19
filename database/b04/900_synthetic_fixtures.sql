-- Only the isolated B04 runner loads these synthetic identities/references.
INSERT INTO organization_access.capability_activations
SELECT "Id", 'workshop', true FROM organization_access.legal_entities
ON CONFLICT DO NOTHING;
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(), m."Id", m."TenantId", le."Id", permission, NULL, NULL
FROM organization_access.memberships m
JOIN organization_access.legal_entities le ON le."TenantId" = m."TenantId"
CROSS JOIN (VALUES ('workshop.orders.create'), ('workshop.orders.read')) permissions(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p
    WHERE p."MembershipId" = m."Id" AND p."LegalEntityId" = le."Id" AND p."Permission" = permission);
INSERT INTO counterparties.counterparties VALUES
('11111111-3333-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', 'Intestatario sintetico', 'SYNTHETIC-HOLDER', 'Sede sintetica intestatario')
ON CONFLICT DO NOTHING;
INSERT INTO vehicles.vehicles VALUES
('11111111-4444-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111102', '11111111-3333-0000-0000-000000000002', 'Veicolo sintetico altra società'),
('22222222-4444-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222201', '22222222-3333-0000-0000-000000000001', 'Veicolo sintetico Beta')
ON CONFLICT DO NOTHING;
INSERT INTO workshop.document_types VALUES
('11111111-5555-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111101', 1, 'Commessa diretta sintetica', true),
('11111111-5555-0000-0000-000000000002', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111101', 1, 'Commessa non diretta sintetica', false),
('22222222-5555-0000-0000-000000000001', '22222222-2222-2222-2222-222222222222', '22222222-2222-2222-2222-222222222201', 1, 'Commessa Beta sintetica', true)
ON CONFLICT DO NOTHING;
UPDATE organization_access.company_permissions
SET "SiteId" = NULL, "WarehouseId" = NULL
WHERE "Permission" IN ('workshop.orders.create', 'workshop.orders.read');
-- D63 regression: alpha can open at A but has no management permission at vehicle company B.
DELETE FROM organization_access.company_permissions
WHERE "MembershipId" = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'
    AND "LegalEntityId" = '11111111-1111-1111-1111-111111111102';
