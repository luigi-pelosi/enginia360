-- Enginia360 — correzione della proprietà di persistenza BP, dopo 20261118.
-- Eseguire con psql -X -v ON_ERROR_STOP=1 come postgres sul database scelto.
-- Non rieseguibile: masterdata deve essere assente, anche se vuoto.
-- Nessun oggetto o dato applicativo viene ricreato; ACL e dipendenze restano sugli OID.
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
SELECT pg_catalog.pg_advisory_xact_lock(3607902026);
SET LOCAL search_path = pg_catalog;
DO $masterdata_guard$
DECLARE
    runtime_oid oid;
    owner_oid oid;
    table_name text;
    relation_oid oid;
BEGIN
    IF current_user <> 'postgres' OR session_user <> 'postgres' THEN
        RAISE EXCEPTION 'Esecuzione richiesta come postgres';
    END IF;
    SELECT oid INTO owner_oid FROM pg_catalog.pg_roles WHERE rolname = 'postgres';
    SELECT oid INTO runtime_oid FROM pg_catalog.pg_roles WHERE rolname = 'enginia360_app';
    IF runtime_oid IS NULL THEN
        RAISE EXCEPTION 'Ruolo runtime enginia360_app mancante';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE oid = runtime_oid
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member = runtime_oid)
       OR EXISTS (SELECT 1 FROM pg_catalog.pg_database WHERE datname = current_database() AND datdba = runtime_oid) THEN
        RAISE EXCEPTION 'Ruolo runtime elevato o proprietario del database';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'foundation' AND nspowner = owner_oid) THEN
        RAISE EXCEPTION 'Richiesto schema foundation di postgres';
    END IF;
    IF pg_catalog.has_schema_privilege(runtime_oid, 'foundation', 'CREATE') THEN
        RAISE EXCEPTION 'Runtime con autorita DDL su foundation';
    END IF;
    -- Il rifiuto di qualsiasi namespace destinazione evita collisioni su tabelle,
    -- indici, tipi e funzioni, stati misti e applicazioni ripetute.
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = 'masterdata') THEN
        RAISE EXCEPTION 'masterdata esiste: migrazione gia applicata, stato misto o collisione';
    END IF;
    FOREACH table_name IN ARRAY ARRAY['business_partner','business_partner_tax_identifier',
        'business_partner_address','business_partner_address_usage','business_partner_contact_channel',
        'numbering_series','numbering_counter'] LOOP
        SELECT c.oid INTO relation_oid FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'foundation' AND c.relname = table_name
          AND c.relkind = 'r' AND c.relowner = owner_oid AND NOT c.relispartition;
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'Stato sorgente non valido: foundation.%', table_name;
        END IF;
        IF pg_catalog.has_table_privilege(runtime_oid, relation_oid, 'TRUNCATE,TRIGGER')
           OR (table_name IN ('business_partner','numbering_series','numbering_counter')
               AND pg_catalog.has_table_privilege(runtime_oid, relation_oid, 'DELETE')) THEN
            RAISE EXCEPTION 'Runtime con privilegi non sicuri: foundation.%', table_name;
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p
                   JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname = 'foundation' AND p.proname = 'guard_business_partner'
                     AND p.pronargs = 0 AND p.prokind = 'f' AND p.proowner = owner_oid
                     AND p.prorettype = 'pg_catalog.trigger'::pg_catalog.regtype AND NOT p.prosecdef) THEN
        RAISE EXCEPTION 'Funzione guard_business_partner sorgente mancante o non valida';
    END IF;
END;
$masterdata_guard$;

CREATE SCHEMA masterdata AUTHORIZATION postgres;
COMMENT ON SCHEMA masterdata IS 'Anagrafiche condivise del tenant.';
REVOKE ALL ON SCHEMA masterdata FROM PUBLIC;
REVOKE ALL ON SCHEMA masterdata FROM enginia360_app;
GRANT USAGE ON SCHEMA masterdata TO enginia360_app;

ALTER TABLE foundation.business_partner SET SCHEMA masterdata;
ALTER TABLE foundation.business_partner_tax_identifier SET SCHEMA masterdata;
ALTER TABLE foundation.business_partner_address SET SCHEMA masterdata;
ALTER TABLE foundation.business_partner_address_usage SET SCHEMA masterdata;
ALTER TABLE foundation.business_partner_contact_channel SET SCHEMA masterdata;
ALTER FUNCTION foundation.guard_business_partner() SET SCHEMA masterdata;

COMMIT;
