BEGIN;
INSERT INTO organization_access.capability_activations ("LegalEntityId","Capability","Enabled") VALUES
 ('11111111-1111-1111-1111-111111111101','internal-accounting',true)
ON CONFLICT ("LegalEntityId","Capability") DO UPDATE SET "Enabled"=excluded."Enabled";
INSERT INTO organization_access.company_permissions ("Id","MembershipId","TenantId","LegalEntityId","Permission","SiteId","WarehouseId") VALUES
 (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','accounting.journal-entries.post','11111111-1111-1111-1111-111111110101',NULL),
 (gen_random_uuid(),'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1','11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101','accounting.journal-entries.read','11111111-1111-1111-1111-111111110101',NULL)
ON CONFLICT DO NOTHING;
-- Demonstration chart of the F04 reference only (D43/D44); not a universal or approved chart of accounts.
INSERT INTO accounting.chart_accounts VALUES
 ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,'Receivable','120100','Crediti verso clienti'),
 ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,'ServiceRevenue','700100','Ricavi prestazioni officina'),
 ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,'PartRevenue','700200','Ricavi vendita ricambi'),
 ('11111111-1111-1111-1111-111111111111','11111111-1111-1111-1111-111111111101',1,'TaxPayable','220100','Erario c/IVA a debito')
ON CONFLICT DO NOTHING;
COMMIT;
