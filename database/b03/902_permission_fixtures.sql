-- Synthetic grants only; never a role catalog or production provisioning.
INSERT INTO organization_access.company_permissions VALUES
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa302','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111102','counterparties.destination.publish',NULL,NULL),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaa303','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','counterparties.destination.publish',NULL,NULL),
('dddddddd-dddd-dddd-dddd-ddddddddd301','dddddddd-dddd-dddd-dddd-ddddddddddd1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111102','counterparties.read',NULL,NULL),
('dddddddd-dddd-dddd-dddd-ddddddddd302','dddddddd-dddd-dddd-dddd-ddddddddddd1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111102','counterparties.destination.publish','11111111-1111-1111-1111-111111110201',NULL),
('dddddddd-dddd-dddd-dddd-ddddddddd303','dddddddd-dddd-dddd-dddd-ddddddddddd1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111102','counterparties.destination.publish',NULL,'11111111-1111-1111-1111-111111100301')
ON CONFLICT DO NOTHING;
