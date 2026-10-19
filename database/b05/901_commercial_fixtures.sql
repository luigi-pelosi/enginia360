INSERT INTO workshop.line_policies VALUES
('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-5555-0000-0000-000000000001',1,'Case001',true),
('22222222-2222-2222-2222-222222222222','22222222-2222-2222-2222-222222222201','22222222-5555-0000-0000-000000000001',1,'Case001',true)
ON CONFLICT DO NOTHING;
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(), "MembershipId", "TenantId", "LegalEntityId", 'workshop.lines.add', "SiteId", "WarehouseId"
FROM organization_access.company_permissions p WHERE "Permission"='workshop.orders.create'
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions q WHERE q."MembershipId"=p."MembershipId"
 AND q."LegalEntityId"=p."LegalEntityId" AND q."Permission"='workshop.lines.add');
