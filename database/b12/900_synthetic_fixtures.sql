BEGIN;
INSERT INTO organization_access.capability_activations ("LegalEntityId","Capability","Enabled") VALUES
 ('11111111-1111-1111-1111-111111111101','internal-billing',true)
ON CONFLICT ("LegalEntityId","Capability") DO UPDATE SET "Enabled"=excluded."Enabled";
INSERT INTO organization_access.company_permissions ("Id","MembershipId","TenantId","LegalEntityId","Permission","SiteId","WarehouseId") VALUES
 (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','billing.invoices.create','11111111-1111-1111-1111-111111110101',NULL),
 (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','billing.invoices.confirm','11111111-1111-1111-1111-111111110101',NULL),
 (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','billing.invoices.read','11111111-1111-1111-1111-111111110101',NULL)
ON CONFLICT DO NOTHING;
DELETE FROM workshop.administrative_destinations WHERE "TenantId"='11111111-1111-1111-1111-111111111111' AND "LegalEntityId"='11111111-1111-1111-1111-111111111101';
INSERT INTO workshop.administrative_destinations VALUES ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,'Internal');
INSERT INTO billing.document_types VALUES ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','11111111-7777-0000-0000-000000000010',1,'TechnicalInvoice',true,true)
ON CONFLICT DO NOTHING;
INSERT INTO billing.issuer_profiles VALUES ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,
 'Società sintetica Alfa S.r.l.','IT00000000001','Via Sintetica 1, Roma') ON CONFLICT DO NOTHING;
COMMIT;
