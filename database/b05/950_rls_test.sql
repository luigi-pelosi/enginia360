BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE tenant text; BEGIN
 ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
 ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE ((n.nspname='catalog' AND c.relname='items') OR (n.nspname='workshop' AND c.relname IN ('line_policies','commercial_lines')))
   AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity)=3;
 ASSERT NOT has_table_privilege(current_user,'catalog.items','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'catalog.items','INSERT');
 ASSERT NOT has_table_privilege(current_user,'workshop.line_policies','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.commercial_lines','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.commercial_lines','DELETE');
 PERFORM set_config('app.tenant_id','',true);
 ASSERT (SELECT count(*) FROM catalog.items)=0;
 ASSERT (SELECT count(*) FROM workshop.commercial_lines)=0;
 FOREACH tenant IN ARRAY ARRAY['11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222'] LOOP
   PERFORM set_config('app.tenant_id',tenant,true);
   ASSERT (SELECT count(*) FROM catalog.items)=2;
   ASSERT EXISTS (SELECT 1 FROM workshop.commercial_lines);
   ASSERT NOT EXISTS (SELECT 1 FROM catalog.items WHERE "TenantId"::text<>tenant);
   ASSERT NOT EXISTS (SELECT 1 FROM workshop.commercial_lines WHERE "TenantId"::text<>tenant);
 END LOOP;
 PERFORM set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
 BEGIN
   INSERT INTO workshop.commercial_lines ("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision")
   VALUES (gen_random_uuid(),'11111111-1111-1111-1111-111111111111','11111111-8888-0000-0000-000000000001',gen_random_uuid(),1,'Denied','Part',1,95,5,90.25,22,gen_random_uuid(),'11111111-8888-0000-0000-000000000001',1,1);
   RAISE EXCEPTION 'Cross-tenant insertion not rejected';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
 ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
 ASSERT (SELECT count(*) FROM catalog.items)=0;
 ASSERT (SELECT count(*) FROM workshop.commercial_lines)=0;
END $$;
RESET ROLE;
\echo PASS B05 forced RLS/least privilege, no-context denial, two-tenant reads/writes, transaction reset
