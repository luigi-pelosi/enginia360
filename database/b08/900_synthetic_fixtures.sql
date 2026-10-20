-- Synthetic scoped grants, not real provisioning or role policy.
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),m."Id",w."TenantId",w."LegalEntityId",permission,w."SiteId",w."Id"
FROM organization_access.memberships m JOIN organization_access.warehouses w ON w."TenantId"=m."TenantId"
CROSS JOIN (VALUES ('inventory.consumptions.read'),('inventory.consumptions.create')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2 WHERE p2."MembershipId"=m."Id" AND p2."WarehouseId"=w."Id" AND p2."SiteId"=w."SiteId" AND p2."Permission"=permission);
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),m."Id",s."TenantId",s."LegalEntityId",permission,s."Id",NULL
FROM organization_access.memberships m JOIN organization_access.sites s ON s."TenantId"=m."TenantId"
CROSS JOIN (VALUES ('workshop.installations.read'),('workshop.installations.create')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2 WHERE p2."MembershipId"=m."Id" AND p2."SiteId"=s."Id" AND p2."Permission"=permission);
