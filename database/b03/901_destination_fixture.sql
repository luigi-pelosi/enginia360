INSERT INTO organization_access.company_permissions
SELECT 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa301', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111102', 'counterparties.destination.write', NULL, NULL ON CONFLICT DO NOTHING;
