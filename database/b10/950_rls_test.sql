BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE request workshop.administrative_requests%ROWTYPE; closure workshop.technical_closures%ROWTYPE; pending integer; BEGIN
 ASSERT NOT (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user);
 ASSERT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE (n.nspname,c.relname) IN (('workshop','administrative_destinations'),('workshop','technical_closures'),('workshop','administrative_requests'),
     ('workshop','administrative_outbox'),('workshop','administrative_outcomes'),('workshop','administrative_closures'),('integrations','administrative_dispatches'))
   AND c.relrowsecurity AND c.relforcerowsecurity)=7;
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_destinations','INSERT');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_requests','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_requests','DELETE');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_outbox','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_outbox','DELETE');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_outcomes','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'workshop.technical_closures','DELETE');
 ASSERT NOT has_table_privilege(current_user,'workshop.administrative_closures','UPDATE');
 ASSERT NOT has_table_privilege(current_user,'integrations.administrative_dispatches','DELETE');
 ASSERT NOT has_column_privilege(current_user,'integrations.administrative_dispatches','TenantId','UPDATE');
 ASSERT NOT has_column_privilege(current_user,'integrations.administrative_dispatches','RequestId','UPDATE');
 -- The privileged discovery function exposes envelopes only, and only to the app role.
 ASSERT (SELECT rolbypassrls AND NOT rolcanlogin AND NOT rolsuper FROM pg_roles WHERE rolname='enginia360_outbox_reader');
 ASSERT NOT has_function_privilege('public','workshop.pending_administrative_outbox(integer)','EXECUTE');
 ASSERT NOT has_table_privilege('enginia360_outbox_reader','workshop.administrative_requests','SELECT');
 ASSERT NOT has_column_privilege('enginia360_outbox_reader','workshop.administrative_outcomes','ExternalReference','SELECT');
 PERFORM set_config('app.tenant_id','',true);
 ASSERT (SELECT count(*) FROM workshop.administrative_requests)=0;
 ASSERT (SELECT count(*) FROM workshop.technical_closures)=0;
 ASSERT (SELECT count(*) FROM integrations.administrative_dispatches)=0;
 SELECT count(*) INTO pending FROM workshop.pending_administrative_outbox(100);
 PERFORM set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
 SELECT * INTO STRICT request FROM workshop.administrative_requests LIMIT 1;
 SELECT * INTO STRICT closure FROM workshop.technical_closures WHERE "OrderId"=request."OrderId";
 BEGIN
  INSERT INTO workshop.technical_closures SELECT closure.*;
  RAISE EXCEPTION 'Order technically closed twice';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 request."Id":=gen_random_uuid();
 BEGIN
  INSERT INTO workshop.administrative_requests SELECT request.*;
  RAISE EXCEPTION 'Second request for one order';
 EXCEPTION WHEN unique_violation THEN NULL; END;
 request."TenantId":='22222222-2222-2222-2222-222222222222';
 BEGIN
  INSERT INTO workshop.administrative_requests SELECT request.*;
  RAISE EXCEPTION 'Cross tenant request accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO workshop.administrative_outcomes VALUES (gen_random_uuid(),'11111111-1111-1111-1111-111111111111','Confirmed',NULL,NULL,now());
  RAISE EXCEPTION 'Confirmation without stable reference accepted';
 EXCEPTION WHEN check_violation THEN NULL; END;
 BEGIN
  INSERT INTO integrations.administrative_dispatches VALUES (gen_random_uuid(),'22222222-2222-2222-2222-222222222222','Queued',0,NULL,now(),NULL,NULL,NULL,NULL,now());
  RAISE EXCEPTION 'Cross tenant dispatch accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
 ASSERT NOT EXISTS (SELECT 1 FROM workshop.administrative_requests WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT NOT EXISTS (SELECT 1 FROM workshop.administrative_outcomes WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT NOT EXISTS (SELECT 1 FROM integrations.administrative_dispatches WHERE "TenantId"::text<>'22222222-2222-2222-2222-222222222222');
 ASSERT pending >= 0;
END $$;
ROLLBACK;
SET ROLE :"app_user";
DO $$ BEGIN
 ASSERT coalesce(current_setting('app.tenant_id',true),'')='';
 ASSERT (SELECT count(*) FROM workshop.administrative_requests)=0;
END $$;
RESET ROLE;
\echo PASS B10 forced RLS, no context, cross tenant denial, one closure/request per order, reference required, insert-only grants, envelope-only discovery role and context reset
