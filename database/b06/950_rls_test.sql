BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE tenant text; BEGIN
    ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
    ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='inventory' AND c.relname IN ('stock','reservations')
        AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity)=2;
    ASSERT NOT has_table_privilege(current_user,'inventory.reservations','UPDATE');
    ASSERT NOT has_table_privilege(current_user,'inventory.reservations','DELETE');
    ASSERT NOT has_table_privilege(current_user,'inventory.stock','INSERT');
    PERFORM set_config('app.tenant_id','',true);
    ASSERT (SELECT count(*) FROM inventory.stock)=0;
    ASSERT (SELECT count(*) FROM inventory.reservations)=0;
    FOREACH tenant IN ARRAY ARRAY['11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222'] LOOP
        PERFORM set_config('app.tenant_id',tenant,true);
        ASSERT EXISTS (SELECT 1 FROM inventory.stock);
        ASSERT NOT EXISTS (SELECT 1 FROM inventory.stock WHERE "TenantId"::text<>tenant);
        ASSERT NOT EXISTS (SELECT 1 FROM inventory.reservations WHERE "TenantId"::text<>tenant);
    END LOOP;
    BEGIN
        INSERT INTO inventory.reservations VALUES
        (gen_random_uuid(),'11111111-1111-1111-1111-111111111111',gen_random_uuid(),gen_random_uuid(),
        gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),1,1);
        RAISE EXCEPTION 'Cross-tenant insertion accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
    ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
    ASSERT (SELECT count(*) FROM inventory.stock)=0;
    ASSERT (SELECT count(*) FROM inventory.reservations)=0;
END $$;
RESET ROLE;
\echo PASS B06 forced RLS, no-context denial, cross-tenant insert denial, transaction reset
