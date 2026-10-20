-- Run only against the isolated synthetic B13 stack, with the real application role.
BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ DECLARE n integer; t text; BEGIN
 FOREACH t IN ARRAY ARRAY['accounting.chart_accounts','accounting.journal_entries','accounting.journal_entry_lines'] LOOP
  EXECUTE format('SELECT count(*) FROM %s',t) INTO n;
  IF n<>0 THEN RAISE EXCEPTION 'B13 no-context data leak %',t; END IF;
  IF has_table_privilege(current_user,t,'UPDATE') OR has_table_privilege(current_user,t,'DELETE') THEN
   RAISE EXCEPTION 'B13 immutable journal exposes mutable grants %',t;
  END IF;
 END LOOP;
 IF has_table_privilege(current_user,'accounting.chart_accounts','INSERT') THEN
  RAISE EXCEPTION 'B13 application must not provision the chart of accounts';
 END IF;
END $$;
SELECT set_config('app.tenant_id','22222222-2222-2222-2222-222222222222',true);
DO $$ BEGIN
 IF EXISTS(SELECT FROM accounting.journal_entries) OR EXISTS(SELECT FROM accounting.journal_entry_lines) THEN
  RAISE EXCEPTION 'B13 cross-tenant RLS leak'; END IF;
END $$;
SELECT set_config('app.tenant_id','11111111-1111-1111-1111-111111111111',true);
DO $$ DECLARE debit numeric; credit numeric; BEGIN
 IF (SELECT count(*) FROM accounting.journal_entries)<>1 THEN RAISE EXCEPTION 'B13 alpha entry visibility incorrect'; END IF;
 SELECT sum("Debit"),sum("Credit") INTO debit,credit FROM accounting.journal_entry_lines;
 IF debit<>credit OR debit<>200.69 THEN RAISE EXCEPTION 'B13 persisted journal is not the balanced F04 reference: % %',debit,credit; END IF;
 BEGIN
  UPDATE accounting.journal_entry_lines SET "Debit"=0;
  RAISE EXCEPTION 'B13 application can rewrite posted journal lines';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO accounting.journal_entries SELECT gen_random_uuid(),'22222222-2222-2222-2222-222222222222',gen_random_uuid(),"OrderId","LegalEntityId","SiteId","ChartVersion","EntryDate","Currency","InvoiceReference","TotalDebit","TotalCredit","PostedAt","PostedBy" FROM accounting.journal_entries LIMIT 1;
  RAISE EXCEPTION 'B13 application can post into a foreign tenant';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
COMMIT;
BEGIN;
SET LOCAL ROLE :"app_user";
DO $$ BEGIN IF EXISTS(SELECT FROM accounting.journal_entries) THEN RAISE EXCEPTION 'B13 context leaked after transaction reuse'; END IF; END $$;
COMMIT;
DO $$ DECLARE n integer; BEGIN
 SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON c.relnamespace=s.oid
 WHERE s.nspname='accounting' AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity;
 IF n<>3 THEN RAISE EXCEPTION 'B13 FORCE RLS missing on introduced tables'; END IF;
END $$;
\echo PASS B13 real application role: forced RLS, no context, cross-tenant denial, insert-only balanced journal and transaction reset
