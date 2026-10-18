-- Disposable database only; this file deliberately exercises the restricted runtime role.
INSERT INTO counterparties.destinations VALUES
 ('11111111-4444-0000-0000-000000000091','11111111-1111-1111-1111-111111111111','11111111-3333-0000-0000-000000000001','11111111-1111-1111-1111-111111111102','RLS private synthetic',false),
 ('11111111-4444-0000-0000-000000000092','11111111-1111-1111-1111-111111111111','11111111-3333-0000-0000-000000000001','11111111-1111-1111-1111-111111111102','RLS published synthetic',true)
ON CONFLICT DO NOTHING;
SET ROLE :"app_user";
BEGIN;
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true),set_config('app.legal_entity_id','11111111-1111-1111-1111-111111111101',true);
DO $$
DECLARE changed integer;
BEGIN
 IF (SELECT rolbypassrls OR rolsuper FROM pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'runtime bypasses RLS'; END IF;
 IF EXISTS(SELECT 1 FROM counterparties.destinations WHERE "Id"='11111111-4444-0000-0000-000000000091') THEN RAISE EXCEPTION 'private company leak'; END IF;
 IF NOT EXISTS(SELECT 1 FROM counterparties.destinations WHERE "Id"='11111111-4444-0000-0000-000000000092') THEN RAISE EXCEPTION 'published same-tenant row missing'; END IF;
 IF EXISTS(SELECT 1 FROM counterparties.counterparties WHERE "Id"='22222222-3333-0000-0000-000000000001') THEN RAISE EXCEPTION 'cross tenant read'; END IF;
 UPDATE counterparties.counterparties SET "LegalName"='forbidden' WHERE "Id"='22222222-3333-0000-0000-000000000001';
 GET DIAGNOSTICS changed=ROW_COUNT;
 IF changed<>0 THEN RAISE EXCEPTION 'cross tenant update'; END IF;
 UPDATE counterparties.destinations SET "Published"=true WHERE "Id"='11111111-4444-0000-0000-000000000091';
 GET DIAGNOSTICS changed=ROW_COUNT;
 IF changed<>0 THEN RAISE EXCEPTION 'private owner update'; END IF;
 BEGIN
  INSERT INTO counterparties.destinations VALUES(gen_random_uuid(),'22222222-2222-2222-2222-222222222222','22222222-3333-0000-0000-000000000001','11111111-1111-1111-1111-111111111101','cross tenant synthetic',false);
  RAISE EXCEPTION 'cross tenant insert accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
 BEGIN
  INSERT INTO counterparties.destinations VALUES(gen_random_uuid(),'11111111-1111-1111-1111-111111111111','11111111-3333-0000-0000-000000000001','11111111-1111-1111-1111-111111111101','implicit publish synthetic',true);
  RAISE EXCEPTION 'implicit publish accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL;
 END;
END $$;
COMMIT;
DO $$ BEGIN
 IF nullif(current_setting('app.tenant_id',true),'') IS NOT NULL OR nullif(current_setting('app.legal_entity_id',true),'') IS NOT NULL THEN RAISE EXCEPTION 'transaction context retained'; END IF;
 IF EXISTS(SELECT 1 FROM counterparties.counterparties) OR EXISTS(SELECT 1 FROM counterparties.destinations) THEN RAISE EXCEPTION 'unset context leaks'; END IF;
END $$;
BEGIN;
SELECT set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true),set_config('app.legal_entity_id','22222222-2222-2222-2222-222222222201',true);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM counterparties.destinations WHERE "Id"='11111111-4444-0000-0000-000000000092') THEN RAISE EXCEPTION 'published cross tenant leak'; END IF;
END $$;
COMMIT;
RESET ROLE;
SELECT 'PASS RLS: private/published scope, cross-tenant SELECT/INSERT/UPDATE, no implicit publication, non-bypass role and transaction reset' AS result;
