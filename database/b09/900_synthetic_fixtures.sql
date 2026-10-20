-- Isolated synthetic acceptance only: a dedicated demo component with carcass, not case 001's oil filter.
INSERT INTO catalog.items VALUES
('11111111-7777-0000-0000-000000000003','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','Part','Componente sintetico con carcassa',1),
('22222222-7777-0000-0000-000000000003','22222222-2222-2222-2222-222222222222','22222222-2222-2222-2222-222222222201','Part','Componente Beta con carcassa',1)
ON CONFLICT DO NOTHING;
INSERT INTO inventory.stock VALUES
('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-1111-1111-1111-111111110101','11111111-1111-1111-1111-111111100101','11111111-7777-0000-0000-000000000003',2),
('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-1111-1111-1111-111111110101','11111111-1111-1111-1111-111111100102','11111111-7777-0000-0000-000000000003',2),
('22222222-2222-2222-2222-222222222222','22222222-2222-2222-2222-222222222201','22222222-2222-2222-2222-222222220101','22222222-2222-2222-2222-222222220101','22222222-7777-0000-0000-000000000003',2)
ON CONFLICT DO NOTHING;
-- Synthetic D39 configuration: carcass required only for the dedicated component, version 1.
INSERT INTO workshop.carcass_policies
SELECT d."TenantId", d."LegalEntityId", d."Id", i."Id", 1, true
FROM workshop.document_types d JOIN catalog.items i ON i."TenantId"=d."TenantId"
WHERE i."Id" IN ('11111111-7777-0000-0000-000000000003','22222222-7777-0000-0000-000000000003') AND d."Version"=1
ON CONFLICT DO NOTHING;
INSERT INTO inventory.carcass_locations
SELECT "TenantId","LegalEntityId","SiteId","Id",1,
 CASE "Id" WHEN '11111111-1111-1111-1111-111111100102' THEN 'Carcasse B' ELSE 'Carcasse A' END
FROM organization_access.warehouses ON CONFLICT DO NOTHING;
-- Synthetic scoped grants, not real provisioning or role policy.
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),m."Id",w."TenantId",w."LegalEntityId",permission,w."SiteId",w."Id"
FROM organization_access.memberships m JOIN organization_access.warehouses w ON w."TenantId"=m."TenantId"
CROSS JOIN (VALUES ('inventory.carcass-returns.read'),('inventory.carcass-returns.create')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2 WHERE p2."MembershipId"=m."Id" AND p2."WarehouseId"=w."Id" AND p2."SiteId"=w."SiteId" AND p2."Permission"=permission);
