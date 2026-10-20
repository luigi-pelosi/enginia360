-- Run only against the isolated synthetic B12 stack, with real application role.
BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE n integer; t text; BEGIN
 FOREACH t IN ARRAY ARRAY['billing.document_types','billing.issuer_profiles','billing.invoices','billing.invoice_confirmations','billing.invoice_journal_links','workshop.internal_billing_claims'] LOOP
  EXECUTE format('SELECT count(*) FROM %s',t) INTO n;
  IF n<>0 THEN RAISE EXCEPTION 'B12 no-context data leak %',t; END IF;
  IF has_table_privilege(current_user,t,'UPDATE') OR has_table_privilege(current_user,t,'DELETE') THEN
   RAISE EXCEPTION 'B12 immutable tables expose mutable grants %',t;
  END IF;
 END LOOP;
END $$;
SELECT set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
DO $$ BEGIN
 IF EXISTS(SELECT FROM billing.invoices) OR EXISTS(SELECT FROM workshop.internal_billing_claims) THEN
  RAISE EXCEPTION 'B12 cross-tenant RLS leak'; END IF;
END $$;
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM billing.invoices)<>3 THEN RAISE EXCEPTION 'B12 alpha invoice visibility incorrect'; END IF;
 BEGIN
  UPDATE billing.invoices SET "Reference"='tampered';
  RAISE EXCEPTION 'B12 application can rewrite invoice history';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO billing.invoices SELECT gen_random_uuid(),'22222222-2222-2222-2222-222222222222',gen_random_uuid(),"LegalEntityId","SiteId","PayerId","DocumentTypeId","ConfigurationVersion","DestinationVersion","SourceRevision","DocumentDate","Currency","Reference","Summary","CreatedAt","CreatedBy" FROM billing.invoices LIMIT 1;
  RAISE EXCEPTION 'B12 application can insert foreign tenant';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
COMMIT;
BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ BEGIN IF EXISTS(SELECT FROM billing.invoices) THEN RAISE EXCEPTION 'B12 context leaked after transaction reuse'; END IF; END $$;
COMMIT;
DO $$ DECLARE n integer; BEGIN
 SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON c.relnamespace=s.oid
 WHERE (s.nspname='billing' OR (s.nspname='workshop' AND c.relname='internal_billing_claims'))
 AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity;
 IF n<>6 THEN RAISE EXCEPTION 'B12 FORCE RLS missing on introduced tables'; END IF;
END $$;
\echo PASS B12 real application role: forced RLS, no context, cross tenant write/read denial, insert-only immutable history and transaction reset
