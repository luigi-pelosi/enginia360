-- Fase 2, dopo 20261119_business_partner_masterdata.sql. Eseguire come postgres.
-- Non rieseguibile: le collisioni annullano la transazione senza adottare oggetti preesistenti.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SELECT pg_catalog.pg_advisory_xact_lock(3607902026);
SET LOCAL search_path=pg_catalog;
DO $$ BEGIN
    IF current_user <> 'postgres' OR session_user <> 'postgres' THEN RAISE EXCEPTION 'postgres required'; END IF;
    IF to_regclass('masterdata.company_business_partner') IS NOT NULL OR to_regclass('masterdata.company_business_partner_role') IS NOT NULL OR to_regclass('foundation.role_company') IS NOT NULL THEN RAISE EXCEPTION 'Phase2 destination collision'; END IF;
    IF EXISTS(SELECT 1 FROM foundation.permission WHERE code IN ('roles.assign_companies','business-partner-companies.read','business-partner-companies.create','business-partner-companies.update','business-partner-companies.use_customer','business-partner-companies.use_supplier')) THEN RAISE EXCEPTION 'Phase2 permission collision'; END IF;
END $$;
-- PHASE2 SCHEMA START
CREATE TABLE foundation.role_company (
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    role_id uuid NOT NULL, company_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,role_id,company_id),
    FOREIGN KEY(tenant_id,role_id) REFERENCES foundation.role(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT
);
CREATE INDEX role_company_company_idx ON foundation.role_company(tenant_id,company_id,role_id);
CREATE TABLE masterdata.company_business_partner (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    company_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','BLOCKED')),
    version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,id), CONSTRAINT company_business_partner_unique UNIQUE(tenant_id,company_id,business_partner_id),
    FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,business_partner_id) REFERENCES masterdata.business_partner(tenant_id,id) ON DELETE RESTRICT
);
CREATE INDEX company_business_partner_bp_idx ON masterdata.company_business_partner(tenant_id,business_partner_id,company_id);
CREATE TABLE masterdata.company_business_partner_role (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL,
    company_business_partner_id uuid NOT NULL,
    role_code text NOT NULL CHECK(role_code IN ('CUSTOMER','SUPPLIER')),
    status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','BLOCKED')),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,company_business_partner_id,role_code),
    FOREIGN KEY(tenant_id,company_business_partner_id) REFERENCES masterdata.company_business_partner(tenant_id,id) ON DELETE RESTRICT
);
CREATE FUNCTION masterdata.guard_company_business_partner() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Commercial history cannot be deleted' USING ERRCODE='23514'; END IF;
    IF (NEW.id,NEW.tenant_id,NEW.created_at) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.created_at) THEN RAISE EXCEPTION 'Immutable commercial identity' USING ERRCODE='23514'; END IF;
    IF TG_TABLE_NAME='company_business_partner' THEN
        IF (NEW.company_id,NEW.business_partner_id) IS DISTINCT FROM (OLD.company_id,OLD.business_partner_id) THEN RAISE EXCEPTION 'Immutable commercial reference' USING ERRCODE='23514'; END IF;
    ELSE
        IF (NEW.company_business_partner_id,NEW.role_code) IS DISTINCT FROM (OLD.company_business_partner_id,OLD.role_code) THEN RAISE EXCEPTION 'Immutable commercial role' USING ERRCODE='23514'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER company_business_partner_guard BEFORE UPDATE OR DELETE ON masterdata.company_business_partner FOR EACH ROW EXECUTE FUNCTION masterdata.guard_company_business_partner();
CREATE TRIGGER company_business_partner_role_guard BEFORE UPDATE OR DELETE ON masterdata.company_business_partner_role FOR EACH ROW EXECUTE FUNCTION masterdata.guard_company_business_partner();
CREATE TRIGGER company_business_partner_updated_at BEFORE UPDATE ON masterdata.company_business_partner FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER company_business_partner_role_updated_at BEFORE UPDATE ON masterdata.company_business_partner_role FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
REVOKE ALL ON FUNCTION masterdata.guard_company_business_partner() FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON masterdata.company_business_partner,masterdata.company_business_partner_role TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON foundation.role_company TO enginia360_app;
-- PHASE2 SCHEMA END
-- Conserva il CHECK finito esistente ed estende solo i sei nuovi codici approvati.
DO $$ DECLARE old_check text; BEGIN
    SELECT pg_get_expr(conbin,conrelid) INTO STRICT old_check FROM pg_constraint WHERE conrelid='foundation.permission'::regclass AND conname='permission_system_code_check';
    ALTER TABLE foundation.permission DROP CONSTRAINT permission_system_code_check;
    EXECUTE 'ALTER TABLE foundation.permission ADD CONSTRAINT permission_system_code_check CHECK ((' || old_check || ') OR code IN (''roles.assign_companies'',''business-partner-companies.read'',''business-partner-companies.create'',''business-partner-companies.update'',''business-partner-companies.use_customer'',''business-partner-companies.use_supplier''))';
END $$;
INSERT INTO foundation.permission(tenant_id,code,name,is_system)
SELECT t.id,c.code,c.code,true FROM foundation.tenant t CROSS JOIN (VALUES ('roles.assign_companies'),('business-partner-companies.read'),('business-partner-companies.create'),('business-partner-companies.update'),('business-partner-companies.use_customer'),('business-partner-companies.use_supplier')) c(code);
-- Nessuna assegnazione role_permission o role_company viene creata.
COMMIT;
