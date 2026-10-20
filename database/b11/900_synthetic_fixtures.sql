-- Synthetic-only exact recovery permission, independent from create/read and scoped to the same sites.
INSERT INTO organization_access.company_permissions
SELECT gen_random_uuid(),p."MembershipId",p."TenantId",p."LegalEntityId",'workshop.administrative-requests.reconcile',p."SiteId",p."WarehouseId"
FROM organization_access.company_permissions p
WHERE p."Permission"='workshop.administrative-requests.create'
AND NOT EXISTS (SELECT 1 FROM organization_access.company_permissions q WHERE q."MembershipId"=p."MembershipId"
 AND q."LegalEntityId"=p."LegalEntityId" AND q."SiteId" IS NOT DISTINCT FROM p."SiteId" AND q."Permission"='workshop.administrative-requests.reconcile');
