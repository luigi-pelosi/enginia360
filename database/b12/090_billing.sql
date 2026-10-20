BEGIN;
ALTER TABLE workshop.administrative_destinations DROP CONSTRAINT IF EXISTS "administrative_destinations_Destination_check";
ALTER TABLE workshop.administrative_destinations ADD CONSTRAINT "administrative_destinations_Destination_check"
 CHECK ("Destination" IN ('External','Internal'));
CREATE TABLE IF NOT EXISTS workshop.internal_billing_claims (
 "InvoiceId" uuid PRIMARY KEY CHECK ("InvoiceId" <> '00000000-0000-0000-0000-000000000000'),
 "TenantId" uuid NOT NULL,
 "OrderId" uuid NOT NULL UNIQUE REFERENCES workshop.technical_closures("OrderId"),
 "DestinationVersion" integer NOT NULL CHECK ("DestinationVersion">0),
 "Revision" integer NOT NULL CHECK ("Revision">=0),
 "AllocatedAt" timestamptz NOT NULL
);
CREATE SCHEMA IF NOT EXISTS billing;
CREATE TABLE IF NOT EXISTS billing.document_types (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "Id" uuid NOT NULL, "Version" integer NOT NULL CHECK ("Version">0),
 "Code" varchar(30) NOT NULL, "WorkshopSourceAllowed" boolean NOT NULL, "ConfirmationAllowed" boolean NOT NULL,
 PRIMARY KEY ("TenantId","LegalEntityId","Id","Version")
);
CREATE TABLE IF NOT EXISTS billing.issuer_profiles (
 "TenantId" uuid NOT NULL, "LegalEntityId" uuid NOT NULL, "Version" integer NOT NULL CHECK ("Version">0),
 "LegalName" varchar(100) NOT NULL, "FiscalIdentifier" varchar(40) NOT NULL, "RegisteredOffice" varchar(200) NOT NULL,
 PRIMARY KEY ("TenantId","LegalEntityId","Version")
);
CREATE TABLE IF NOT EXISTS billing.invoices (
 "Id" uuid PRIMARY KEY CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'), "TenantId" uuid NOT NULL,
 "OrderId" uuid NOT NULL UNIQUE, "LegalEntityId" uuid NOT NULL, "SiteId" uuid NOT NULL, "PayerId" uuid NOT NULL,
 "DocumentTypeId" uuid NOT NULL, "ConfigurationVersion" integer NOT NULL CHECK ("ConfigurationVersion">0),
 "DestinationVersion" integer NOT NULL CHECK ("DestinationVersion">0), "SourceRevision" integer NOT NULL CHECK ("SourceRevision">=0),
 "DocumentDate" date NOT NULL, "Currency" char(3) NOT NULL CHECK ("Currency"='EUR'), "Reference" varchar(64) NOT NULL,
 "Summary" jsonb NOT NULL, "CreatedAt" timestamptz NOT NULL, "CreatedBy" uuid NOT NULL
);
CREATE TABLE IF NOT EXISTS billing.invoice_confirmations (
 "InvoiceId" uuid PRIMARY KEY REFERENCES billing.invoices("Id"),
 "Id" uuid NOT NULL UNIQUE CHECK ("Id" <> '00000000-0000-0000-0000-000000000000'), "TenantId" uuid NOT NULL,
 "ConfigurationVersion" integer NOT NULL CHECK ("ConfigurationVersion">0), "Issuer" jsonb NOT NULL, "Recipient" jsonb NOT NULL,
 "ConfirmedAt" timestamptz NOT NULL, "ConfirmedBy" uuid NOT NULL
);
CREATE TABLE IF NOT EXISTS billing.invoice_journal_links (
 "InvoiceId" uuid PRIMARY KEY REFERENCES billing.invoice_confirmations("InvoiceId"), "TenantId" uuid NOT NULL,
 "JournalEntryId" uuid NOT NULL UNIQUE, "LinkedAt" timestamptz NOT NULL
);
DO $$ DECLARE target text; BEGIN
 FOREACH target IN ARRAY ARRAY['workshop.internal_billing_claims','billing.document_types','billing.issuer_profiles','billing.invoices','billing.invoice_confirmations','billing.invoice_journal_links'] LOOP
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY',target);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY',target);
  EXECUTE format('DROP POLICY IF EXISTS tenant_identity ON %s',target);
  EXECUTE format('CREATE POLICY tenant_identity ON %s USING ("TenantId"::text=current_setting(''app.tenant_id'',true)) WITH CHECK ("TenantId"::text=current_setting(''app.tenant_id'',true))',target);
 END LOOP;
END $$;
GRANT SELECT,INSERT ON workshop.internal_billing_claims TO :"app_user";
GRANT USAGE ON SCHEMA billing TO :"app_user";
GRANT SELECT ON billing.document_types,billing.issuer_profiles TO :"app_user";
GRANT SELECT,INSERT ON billing.invoices,billing.invoice_confirmations,billing.invoice_journal_links TO :"app_user";
COMMIT;
