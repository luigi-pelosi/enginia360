BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE receipt inventory.carcass_returns%ROWTYPE; link inventory.carcass_return_installations%ROWTYPE; BEGIN
 ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
 ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE (n.nspname,c.relname) IN (('workshop','carcass_policies'),('inventory','carcass_locations'),('inventory','carcass_returns'),('inventory','carcass_return_installations'))
   AND c.relrowsecurity AND c.relforcerowsecurity)=4;
 ASSERT NOT has_table_privilege(current_user,'workshop.carcass_policies','INSERT');
 ASSERT NOT has_table_privilege(current_user,'inventory.carcass_locations','INSERT');
 ASSERT NOT has_table_privilege(current_user,'inventory.carcass_returns','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'inventory.carcass_returns','DELETE');
 ASSERT NOT has_table_privilege(current_user,'inventory.carcass_return_installations','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'inventory.carcass_return_installations','DELETE');
 ASSERT NOT has_column_privilege(current_user,'workshop.installations','CarcassReturnRequired','UPDATE');
 PERFORM set_config('app.tenant_id','',true);
 ASSERT (SELECT count(*) FROM inventory.carcass_returns)=0;
 ASSERT (SELECT count(*) FROM inventory.carcass_return_installations)=0;
 ASSERT (SELECT count(*) FROM workshop.carcass_policies)=0;
 ASSERT (SELECT count(*) FROM inventory.carcass_locations)=0;
 PERFORM set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
 SELECT * INTO STRICT receipt FROM inventory.carcass_returns LIMIT 1;
 SELECT * INTO STRICT link FROM inventory.carcass_return_installations LIMIT 1;
 BEGIN
  INSERT INTO inventory.carcass_return_installations SELECT link.*;
  RAISE EXCEPTION 'Installation covered twice';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 receipt."Id":=gen_random_uuid(); receipt."TenantId":='22222222-2222-2222-2222-222222222222';
 link."InstallationId":=gen_random_uuid(); link."TenantId":='22222222-2222-2222-2222-222222222222';
 BEGIN
  INSERT INTO inventory.carcass_returns SELECT receipt.*;
  RAISE EXCEPTION 'Cross tenant carcass return accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO inventory.carcass_return_installations SELECT link.*;
  RAISE EXCEPTION 'Cross tenant carcass link accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
 ASSERT NOT EXISTS (SELECT 1 FROM inventory.carcass_returns WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT NOT EXISTS (SELECT 1 FROM inventory.carcass_return_installations WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT NOT EXISTS (SELECT 1 FROM workshop.carcass_policies WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
 ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
 ASSERT (SELECT count(*) FROM inventory.carcass_returns)=0;
END $$;
RESET ROLE;
\echo PASS B09 forced RLS, no context, cross tenant read/insert denial, single coverage per installation, insert-only grants and context reset
