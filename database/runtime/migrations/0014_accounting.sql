-- Source: database/b13/100_accounting.sql (DDL/RLS/technical privileges only).
CREATE SCHEMA IF NOT EXISTS accounting;
CREATE TABLE IF NOT EXISTS accounting.chart_accounts (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "Version" integer NOT NULL CHECK ("Version">0),
 "Purpose" varchar(30) NOT NULL CHECK ("Purpose" IN ('Receivable','ServiceRevenue','PartRevenue','TaxPayable')),
 "AccountCode" varchar(20) NOT NULL CHECK ("AccountCode" ~ '^[0-9]{4,20}$'),
 "AccountDescription" varchar(100) NOT NULL,
 PRIMARY KEY ("TenantId","LegalEntityId","Version","Purpose")
);
CREATE TABLE IF NOT EXISTS accounting.journal_entries (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'), "TenantId" uuid NOT NULL,
 "InvoiceId" uuid NOT NULL UNIQUE, "OrderId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL,
 "ChartVersion" integer NOT NULL CHECK ("ChartVersion">0), "EntryDate" date NOT NULL,
 "Currency" char(3) NOT NULL CHECK ("Currency"='EUR'), "InvoiceReference" varchar(64) NOT NULL,
 "TotalDebit" numeric(20,6) NOT NULL CHECK ("TotalDebit">0), "TotalCredit" numeric(20,6) NOT NULL CHECK ("TotalCredit">0),
 "PostedAt" timestamptz NOT NULL, "PostedBy" uuid NOT NULL,
 CONSTRAINT "journal_entries_balanced_check" CHECK ("TotalDebit"="TotalCredit")
);
CREATE TABLE IF NOT EXISTS accounting.journal_entry_lines (
 "EntryId" uuid NOT NULL REFERENCES accounting.journal_entries("Id"),
 "LineNumber" integer NOT NULL CHECK ("LineNumber">0), "TenantId" uuid NOT NULL,
 "AccountCode" varchar(20) NOT NULL, "AccountDescription" varchar(100) NOT NULL,
 "Debit" numeric(20,6) NOT NULL CHECK ("Debit">=0), "Credit" numeric(20,6) NOT NULL CHECK ("Credit">=0),
 PRIMARY KEY ("EntryId","LineNumber"),
 CONSTRAINT "journal_entry_lines_single_side_check" CHECK (("Debit"=0) <> ("Credit"=0))
);
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['accounting.chart_accounts','accounting.journal_entries','accounting.journal_entry_lines'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT USAGE ON SCHEMA accounting TO :"app_user";
GRANT SELECT ON accounting.chart_accounts TO :"app_user";
GRANT SELECT,INSERT ON accounting.journal_entries,accounting.journal_entry_lines TO :"app_user";
