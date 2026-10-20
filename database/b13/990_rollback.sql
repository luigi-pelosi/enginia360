BEGIN;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM accounting.journal_entries) THEN RAISE EXCEPTION 'B13 rollback refused: posted journal entries exist'; END IF;
 IF EXISTS (SELECT 1 FROM billing.invoice_journal_links) THEN RAISE EXCEPTION 'B13 rollback refused: invoice journal links exist'; END IF;
END $$;
DROP TABLE IF EXISTS accounting.journal_entry_lines;
DROP TABLE IF EXISTS accounting.journal_entries;
DROP TABLE IF EXISTS accounting.chart_accounts;
DROP SCHEMA IF EXISTS accounting;
COMMIT;
