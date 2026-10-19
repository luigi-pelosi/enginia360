-- Isolated synthetic acceptance only; no production configuration provisioning.
INSERT INTO inventory.picking_policies
SELECT "TenantId", "Id", 1, true FROM organization_access.legal_entities
ON CONFLICT DO NOTHING;
INSERT INTO inventory.picking_locations
SELECT "TenantId", "LegalEntityId", "SiteId", "Id", 'Stock A', 'Preparazione A'
FROM organization_access.warehouses ON CONFLICT DO NOTHING;
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(), m."Id", w."TenantId", w."LegalEntityId", permission, w."SiteId", w."Id"
FROM organization_access.memberships m JOIN organization_access.warehouses w ON w."TenantId" = m."TenantId"
CROSS JOIN (VALUES ('inventory.picks.read'), ('inventory.picks.create')) p(permission)
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001','bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions p2
    WHERE p2."MembershipId" = m."Id" AND p2."WarehouseId" = w."Id" AND p2."SiteId" = w."SiteId" AND p2."Permission" = permission);
