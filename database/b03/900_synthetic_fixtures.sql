INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(), m."Id", m."TenantId", le."Id", 'counterparties.read', NULL, NULL
FROM organization_access.memberships m JOIN organization_access.legal_entities le ON le."TenantId"=m."TenantId"
WHERE m."IdentitySubject" IN ('aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001')
AND NOT EXISTS(SELECT 1 FROM organization_access.company_permissions p WHERE p."MembershipId"=m."Id" AND p."LegalEntityId"=le."Id" AND p."Permission"='counterparties.read');
INSERT INTO counterparties.counterparties VALUES
('11111111-3333-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','Controparte sintetica Alfa','SYNTHETIC-ALFA','Sede legale sintetica Alfa'),
('22222222-3333-0000-0000-000000000001','22222222-2222-2222-2222-222222222222','Controparte sintetica Beta','SYNTHETIC-BETA','Sede legale sintetica Beta')
ON CONFLICT DO NOTHING;
