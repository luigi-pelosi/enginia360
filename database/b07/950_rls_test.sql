BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE target text; sample inventory.picks%ROWTYPE; BEGIN
    ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
    ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='inventory' AND c.relname IN ('picks','picking_policies','picking_locations')
        AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity)=3;
    ASSERT NOT has_table_privilege(current_user,'inventory.picks','UPDATE');
    ASSERT NOT has_table_privilege(current_user,'inventory.picks','DELETE');
    ASSERT NOT has_table_privilege(current_user,'inventory.picking_policies','UPDATE');
    PERFORM set_config('app.tenant_id','',true);
    ASSERT (SELECT count(*) FROM inventory.picks)=0;
    ASSERT (SELECT count(*) FROM inventory.picking_policies)=0;
    ASSERT (SELECT count(*) FROM inventory.picking_locations)=0;
    PERFORM set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
    SELECT * INTO STRICT sample FROM inventory.picks LIMIT 1;
    sample."Id" := gen_random_uuid();
    sample."TenantId" := '22222222-2222-2222-2222-222222222222';
    BEGIN
        INSERT INTO inventory.picks SELECT sample.*;
        RAISE EXCEPTION 'Cross-tenant insertion accepted';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
    ASSERT NOT EXISTS (SELECT 1 FROM inventory.picks WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
    ASSERT NOT EXISTS (SELECT 1 FROM inventory.picking_policies WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
    ASSERT NOT EXISTS (SELECT 1 FROM inventory.picking_locations WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
    ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
    ASSERT (SELECT count(*) FROM inventory.picks)=0;
END $$;
RESET ROLE;
\echo PASS B07 forced RLS, no-context reads, cross-tenant insert denial, immutable app grants and transaction reset
