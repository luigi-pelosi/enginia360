-- Enginia360 — dominio Business Partner, stato finale per nuove installazioni.
-- Incluso da foundation.sql dopo tutti i prerequisiti, nella sua transazione.
-- Non applicare a database esistenti; nessun dato o privilegio aggiuntivo.

CREATE SCHEMA masterdata AUTHORIZATION postgres;
COMMENT ON SCHEMA masterdata IS 'Anagrafiche condivise del tenant.';
REVOKE ALL ON SCHEMA masterdata FROM PUBLIC;
REVOKE ALL ON SCHEMA masterdata FROM enginia360_app;
GRANT USAGE ON SCHEMA masterdata TO enginia360_app;

-- Numerazione esclusiva BP: nessuna serie viene precreata.
CREATE TABLE foundation.numbering_series (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    scope text NOT NULL DEFAULT 'TENANT' CHECK (scope='TENANT'),
    company_id uuid CHECK (company_id IS NULL),
    entity_type text NOT NULL DEFAULT 'BUSINESS_PARTNER' CHECK (entity_type='BUSINESS_PARTNER'),
    reset_policy text NOT NULL DEFAULT 'NEVER' CHECK (reset_policy='NEVER'),
    mode text NOT NULL CHECK (mode IN ('AUTO','MANUAL')),
    prefix text NOT NULL CHECK (length(prefix)<=32 AND prefix !~ '[[:cntrl:]]'),
    padding integer NOT NULL CHECK (padding BETWEEN 1 AND 15),
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    UNIQUE (tenant_id,entity_type), UNIQUE (tenant_id,id)
);
CREATE TABLE foundation.numbering_counter (
    series_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    next_number bigint NOT NULL CHECK (next_number BETWEEN 1 AND 1000000000000000),
    used boolean NOT NULL DEFAULT false,
    FOREIGN KEY (tenant_id,series_id) REFERENCES foundation.numbering_series(tenant_id,id) ON DELETE RESTRICT
);
CREATE FUNCTION foundation.guard_numbering() RETURNS trigger LANGUAGE plpgsql SET search_path TO pg_catalog AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'La numerazione non si elimina' USING ERRCODE='23514'; END IF;
    IF TG_TABLE_NAME='numbering_series' THEN
        IF NEW.id<>OLD.id OR NEW.tenant_id<>OLD.tenant_id THEN RAISE EXCEPTION 'Identita immutabile' USING ERRCODE='23514'; END IF;
        IF EXISTS(SELECT 1 FROM foundation.numbering_counter WHERE series_id=OLD.id AND used)
           AND (NEW.mode,NEW.prefix,NEW.padding) IS DISTINCT FROM (OLD.mode,OLD.prefix,OLD.padding)
        THEN RAISE EXCEPTION 'Numerazione gia utilizzata' USING ERRCODE='23514'; END IF;
    ELSE
        IF NEW.series_id<>OLD.series_id OR NEW.tenant_id<>OLD.tenant_id OR (OLD.used AND (NOT NEW.used OR NEW.next_number NOT IN (OLD.next_number,OLD.next_number+1)))
        THEN RAISE EXCEPTION 'Contatore non ripristinabile' USING ERRCODE='23514'; END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER numbering_series_guard BEFORE UPDATE OR DELETE ON foundation.numbering_series FOR EACH ROW EXECUTE FUNCTION foundation.guard_numbering();
CREATE TRIGGER numbering_counter_guard BEFORE UPDATE OR DELETE ON foundation.numbering_counter FOR EACH ROW EXECUTE FUNCTION foundation.guard_numbering();
REVOKE ALL ON FUNCTION foundation.guard_numbering() FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON foundation.numbering_series,foundation.numbering_counter TO enginia360_app;

-- Anagrafica tenant-wide; nessun ruolo cliente/fornitore o legame aziendale.
CREATE TABLE masterdata.business_partner (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    kind text NOT NULL CHECK (kind IN ('PERSON','ORGANIZATION')),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','ACTIVE','BLOCKED','ARCHIVED')),
    code text NOT NULL CHECK (length(btrim(code)) BETWEEN 1 AND 100),
    legal_name text CHECK (length(legal_name)<=500),
    first_name text CHECK (length(first_name)<=200),
    last_name text CHECK (length(last_name)<=200),
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    CHECK ((kind='ORGANIZATION' AND coalesce(btrim(legal_name),'')<>'' AND first_name IS NULL AND last_name IS NULL)
        OR (kind='PERSON' AND legal_name IS NULL AND (coalesce(btrim(first_name),'')<>'' OR coalesce(btrim(last_name),'')<>'')
            AND (status='DRAFT' OR (coalesce(btrim(first_name),'')<>'' AND coalesce(btrim(last_name),'')<>''))))
);
CREATE UNIQUE INDEX business_partner_code_unique ON masterdata.business_partner(tenant_id,lower(code));
CREATE TABLE masterdata.business_partner_tax_identifier (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    country_code text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    identifier_type text NOT NULL CHECK (identifier_type IN ('VAT','FISCAL_CODE','FOREIGN_TAX_ID')),
    value text NOT NULL CHECK (length(btrim(value)) BETWEEN 1 AND 100),
    normalized_value text NOT NULL CHECK (length(normalized_value) BETWEEN 1 AND 100 AND normalized_value=regexp_replace(upper(value),'[\s.\-]','','g')),
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES masterdata.business_partner(tenant_id,id) ON DELETE RESTRICT,
    CONSTRAINT business_partner_tax_unique UNIQUE (tenant_id,country_code,identifier_type,normalized_value)
);
CREATE TABLE masterdata.business_partner_address (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    label text CHECK (length(label)<=200), street text NOT NULL CHECK (length(btrim(street)) BETWEEN 1 AND 500),
    street_number text CHECK (length(street_number)<=50), postal_code text NOT NULL CHECK (length(btrim(postal_code)) BETWEEN 1 AND 30),
    city text NOT NULL CHECK (length(btrim(city)) BETWEEN 1 AND 200), province text CHECK (length(province)<=100),
    country_code text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'), additional_info text CHECK (length(additional_info)<=1000),
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES masterdata.business_partner(tenant_id,id) ON DELETE RESTRICT,
    UNIQUE (tenant_id,business_partner_id,id)
);
CREATE TABLE masterdata.business_partner_address_usage (
    tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL, address_id uuid NOT NULL,
    usage text NOT NULL CHECK (usage IN ('REGISTERED','BILLING','SHIPPING','CORRESPONDENCE')), is_default boolean NOT NULL DEFAULT false,
    PRIMARY KEY (address_id,usage),
    FOREIGN KEY (tenant_id,business_partner_id,address_id) REFERENCES masterdata.business_partner_address(tenant_id,business_partner_id,id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX business_partner_address_default_unique ON masterdata.business_partner_address_usage(tenant_id,business_partner_id,usage) WHERE is_default;
CREATE TABLE masterdata.business_partner_contact_channel (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    channel_type text NOT NULL CHECK (channel_type IN ('EMAIL','PHONE','MOBILE','PEC','WEBSITE')),
    value text NOT NULL CHECK (length(btrim(value)) BETWEEN 1 AND 500), purpose text CHECK (length(purpose)<=200),
    is_primary boolean NOT NULL DEFAULT false,
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES masterdata.business_partner(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX business_partner_contact_primary_unique ON masterdata.business_partner_contact_channel(tenant_id,business_partner_id,channel_type) WHERE is_primary;
CREATE FUNCTION masterdata.guard_business_partner() RETURNS trigger LANGUAGE plpgsql SET search_path TO pg_catalog AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Archiviare il business partner' USING ERRCODE='23514'; END IF;
    IF (NEW.id,NEW.tenant_id,NEW.code) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.code) THEN
        RAISE EXCEPTION 'Identita e codice immutabili' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER business_partner_guard BEFORE UPDATE OR DELETE ON masterdata.business_partner FOR EACH ROW EXECUTE FUNCTION masterdata.guard_business_partner();
CREATE TRIGGER business_partner_updated_at BEFORE UPDATE ON masterdata.business_partner FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
REVOKE ALL ON FUNCTION masterdata.guard_business_partner() FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON masterdata.business_partner TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON masterdata.business_partner_tax_identifier,masterdata.business_partner_address,masterdata.business_partner_address_usage,masterdata.business_partner_contact_channel TO enginia360_app;

-- Phase 2 company commercial relationships and explicit role scopes.
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
