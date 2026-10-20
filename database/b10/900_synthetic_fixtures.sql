-- Isolated synthetic acceptance only: both synthetic tenants declare the simulated external destination, version 1.
INSERT INTO workshop.administrative_destinations
SELECT "TenantId","Id",1,'External' FROM organization_access.legal_entities
WHERE "Id" IN ('11111111-1111-1111-1111-111111111101','22222222-2222-2222-2222-222222222201') ON CONFLICT DO NOTHING;
INSERT INTO organization_access.capability_activations
SELECT "Id",'external-administration',true FROM organization_access.legal_entities ON CONFLICT DO NOTHING;
-- Synthetic site-scoped exact actions, not real provisioning or role policy.
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),m."Id",s."TenantId",s."LegalEntityId",permission,s."Id",NULL
FROM organization_access.memberships m JOIN organization_access.sites s ON s."TenantId"=m."TenantId"
CROSS JOIN (VALUES ('workshop.orders.complete-technical'),('workshop.administrative-requests.create'),
 ('workshop.administrative-requests.read'),('workshop.orders.complete-administrative')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2 WHERE p2."MembershipId"=m."Id" AND p2."SiteId"=s."Id" AND p2."Permission"=permission);
