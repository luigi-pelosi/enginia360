BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE sample workshop.installations%ROWTYPE; effect inventory.consumptions%ROWTYPE; BEGIN
 ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
 ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE (n.nspname,c.relname) IN (('workshop','installations'),('inventory','consumptions'))
   AND c.relrowsecurity AND c.relforcerowsecurity)=2;
 ASSERT NOT has_table_privilege(current_user,'workshop.installations','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.installations','DELETE');
 ASSERT NOT has_table_privilege(current_user,'inventory.consumptions','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'inventory.consumptions','DELETE');
 PERFORM set_config('app.tenant_id','',true);
 ASSERT (SELECT count(*) FROM workshop.installations)=0;
 ASSERT (SELECT count(*) FROM inventory.consumptions)=0;
 PERFORM set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
 SELECT * INTO STRICT sample FROM workshop.installations LIMIT 1;
 SELECT * INTO STRICT effect FROM inventory.consumptions LIMIT 1;
 sample."Id":=gen_random_uuid(); sample."TenantId":='22222222-2222-2222-2222-222222222222';
 effect."InstallationId":=gen_random_uuid(); effect."TenantId":='22222222-2222-2222-2222-222222222222';
 BEGIN
  INSERT INTO workshop.installations SELECT sample.*;
  RAISE EXCEPTION 'Cross tenant installation accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO inventory.consumptions SELECT effect.*;
  RAISE EXCEPTION 'Cross tenant consumption accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
 ASSERT NOT EXISTS (SELECT 1 FROM workshop.installations WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT NOT EXISTS (SELECT 1 FROM inventory.consumptions WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
 ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
 ASSERT (SELECT count(*) FROM workshop.installations)=0;
 ASSERT (SELECT count(*) FROM inventory.consumptions)=0;
END $$;
RESET ROLE;
\echo PASS B08 forced RLS, no context, cross tenant read/insert denial, immutable grants and transaction context reset
