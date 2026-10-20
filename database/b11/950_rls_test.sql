SELECT set_config('app.test_app_user', :'app_user', false);
BEGIN;
DO $$ BEGIN
 ASSERT (SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='integrations.administrative_reconciliations'::regclass);
 ASSERT EXISTS (SELECT 1 FROM integrations.administrative_reconciliations);
 ASSERT NOT has_table_privilege(current_setting('app.test_app_user'),'integrations.administrative_reconciliations','UPDATE');
 ASSERT NOT has_table_privilege(current_setting('app.test_app_user'),'integrations.administrative_reconciliations','DELETE');
END $$;
ROLLBACK;
BEGIN;
SET LOCAL ROLE :"app_user";
SELECT set_config('app.tenant_id','',true);
DO $$ BEGIN ASSERT (SELECT count(*) FROM integrations.administrative_reconciliations)=0; END $$;
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
DO $$ BEGIN
 ASSERT EXISTS (SELECT 1 FROM integrations.administrative_reconciliations);
 ASSERT NOT EXISTS (SELECT 1 FROM integrations.administrative_reconciliations WHERE "TenantId"<>'11111111-1111-1111-1111-111111111111');
 BEGIN
  INSERT INTO integrations.administrative_reconciliations
   SELECT gen_random_uuid(),'22222222-2222-2222-2222-222222222222',"RequestId","OperatorId",now() FROM integrations.administrative_reconciliations LIMIT 1;
  RAISE EXCEPTION 'Cross-tenant recovery insert unexpectedly accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SELECT set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
DO $$ BEGIN ASSERT (SELECT count(*) FROM integrations.administrative_reconciliations)=0; END $$;
ROLLBACK;
DO $$ BEGIN ASSERT coalesce(current_setting('app.tenant_id',true),'')=''; END $$;
\echo 'PASS B11 forced RLS, no-context/cross-tenant recovery isolation, insert-only audit privileges and context reset'
