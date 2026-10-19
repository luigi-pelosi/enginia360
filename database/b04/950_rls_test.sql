BEGIN;
SET LOCAL ROLE :"app_user";
DO $$
DECLARE item text;
BEGIN
    ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user), 'App role must not bypass RLS';
    ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('vehicles','workshop') AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity) = 3;
    ASSERT NOT has_table_privilege(current_user, 'workshop.document_types', 'INSERT');
    ASSERT NOT has_table_privilege(current_user, 'vehicles.vehicles', 'UPDATE');
    ASSERT NOT has_table_privilege(current_user, 'workshop.orders', 'UPDATE');
    PERFORM set_config('app.tenant_id', '', true);
    ASSERT (SELECT count(*) FROM workshop.orders) = 0;
    ASSERT (SELECT count(*) FROM workshop.document_types) = 0;
    ASSERT (SELECT count(*) FROM vehicles.vehicles) = 0;
    FOREACH item IN ARRAY ARRAY['11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222'] LOOP
        PERFORM set_config('app.tenant_id', item, true);
        ASSERT (SELECT count(*) FROM vehicles.vehicles) = 1;
        ASSERT NOT EXISTS (SELECT 1 FROM workshop.orders WHERE "TenantId"::text <> item);
        ASSERT NOT EXISTS (SELECT 1 FROM workshop.document_types WHERE "TenantId"::text <> item);
        ASSERT NOT EXISTS (SELECT 1 FROM vehicles.vehicles WHERE "TenantId"::text <> item);
        ASSERT EXISTS (SELECT 1 FROM workshop.orders);
    END LOOP;
    PERFORM set_config('app.tenant_id', '11111111-1111-1111-1111-111111111111', true);
    BEGIN
        INSERT INTO workshop.orders VALUES (gen_random_uuid(), '22222222-2222-2222-2222-222222222222',
            '22222222-2222-2222-2222-222222222201', '22222222-2222-2222-2222-222222220101',
            '22222222-5555-0000-0000-000000000001', 1,
            '22222222-3333-0000-0000-000000000001', '22222222-4444-0000-0000-000000000001',
            '22222222-3333-0000-0000-000000000001', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbb1');
        RAISE EXCEPTION 'Cross-tenant insert was not denied';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;
    PERFORM set_config('app.tenant_id', '', true);
    ASSERT (SELECT count(*) FROM workshop.orders) = 0;
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
    ASSERT coalesce(current_setting('app.tenant_id', true), '') = '', 'Transaction-local tenant must reset';
    ASSERT (SELECT count(*) FROM workshop.orders) = 0;
    ASSERT (SELECT count(*) FROM vehicles.vehicles) = 0;
END $$;
RESET ROLE;
\echo PASS B04 SQL: forced RLS, non-bypass app role, no-context denial, two-tenant reads, cross-tenant insert denial, least privilege
