-- Only isolated synthetic acceptance. Not stock administration or procurement.
INSERT INTO inventory.stock VALUES
('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-1111-1111-1111-111111110101','11111111-1111-1111-1111-111111100101','11111111-7777-0000-0000-000000000002',2)
ON CONFLICT DO NOTHING;
INSERT INTO organization_access.warehouses VALUES
('11111111-1111-1111-1111-111111100102','11111111-1111-1111-1111-111111110101','11111111-1111-1111-1111-111111111101','11111111-1111-1111-1111-111111111111','Alfa Nord Magazzino B sintetico')
ON CONFLICT DO NOTHING;
INSERT INTO organization_access.capability_activations
SELECT "Id",'inventory',true FROM organization_access.legal_entities ON CONFLICT DO NOTHING;
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),m."Id",w."TenantId",w."LegalEntityId",permission,w."SiteId",w."Id"
FROM organization_access.memberships m JOIN organization_access.warehouses w ON w."TenantId"=m."TenantId"
CROSS JOIN (VALUES ('inventory.reservations.read'),('inventory.reservations.create')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2 WHERE p2."MembershipId"=m."Id"
 AND p2."WarehouseId"=w."Id" AND p2."SiteId"=w."SiteId" AND p2."Permission"=permission);
INSERT INTO inventory.stock VALUES
('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-1111-1111-1111-111111110101','11111111-1111-1111-1111-111111100102','11111111-7777-0000-0000-000000000002',2),
('22222222-2222-2222-2222-222222222222','22222222-2222-2222-2222-222222222201','22222222-2222-2222-2222-222222220101','22222222-2222-2222-2222-222222220101','22222222-7777-0000-0000-000000000002',2)
ON CONFLICT DO NOTHING;
