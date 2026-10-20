BEGIN;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM billing.invoice_journal_links) THEN RAISE EXCEPTION 'B12 rollback refused: journal links exist'; END IF;
 IF EXISTS (SELECT 1 FROM billing.invoices) THEN RAISE EXCEPTION 'B12 rollback refused: invoices exist'; END IF;
 IF EXISTS (SELECT 1 FROM workshop.internal_billing_claims) THEN RAISE EXCEPTION 'B12 rollback refused: Workshop claims exist'; END IF;
 IF EXISTS (SELECT 1 FROM workshop.administrative_destinations WHERE "Destination"='Internal') THEN RAISE EXCEPTION 'B12 rollback refused: internal destinations exist'; END IF;
END $$;
DROP TABLE IF EXISTS billing.invoice_journal_links;
DROP TABLE IF EXISTS billing.invoice_confirmations;
DROP TABLE IF EXISTS billing.invoices;
DROP TABLE IF EXISTS billing.issuer_profiles;
DROP TABLE IF EXISTS billing.document_types;
DROP SCHEMA IF EXISTS billing;
DROP TABLE IF EXISTS workshop.internal_billing_claims;
ALTER TABLE workshop.administrative_destinations DROP CONSTRAINT IF EXISTS "administrative_destinations_Destination_check";
ALTER TABLE workshop.administrative_destinations ADD CONSTRAINT "administrative_destinations_Destination_check" CHECK ("Destination" IN ('External'));
COMMIT;
