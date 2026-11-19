-- Enginia360 — Business Partner fase 1 + numerazione BP tenant-wide.
-- Solo su database foundation esistente, come postgres. Nessun dato BP/serie iniziale.
BEGIN;
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='60s';
SELECT pg_catalog.pg_advisory_xact_lock(3607902026);
DO $guard$
BEGIN
    IF current_user <> 'postgres' OR NOT EXISTS(SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname='foundation') THEN
        RAISE EXCEPTION 'Richiesti postgres e foundation esistente';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='enginia360_app' AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.member WHERE r.rolname='enginia360_app') THEN
        RAISE EXCEPTION 'Ruolo runtime elevato';
    END IF;
END $guard$;
SET LOCAL search_path=pg_catalog;
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
CREATE TABLE foundation.business_partner (
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
CREATE UNIQUE INDEX business_partner_code_unique ON foundation.business_partner(tenant_id,lower(code));
CREATE TABLE foundation.business_partner_tax_identifier (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    country_code text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    identifier_type text NOT NULL CHECK (identifier_type IN ('VAT','FISCAL_CODE','FOREIGN_TAX_ID')),
    value text NOT NULL CHECK (length(btrim(value)) BETWEEN 1 AND 100),
    normalized_value text NOT NULL CHECK (length(normalized_value) BETWEEN 1 AND 100 AND normalized_value=regexp_replace(upper(value),'[\s.\-]','','g')),
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES foundation.business_partner(tenant_id,id) ON DELETE RESTRICT,
    CONSTRAINT business_partner_tax_unique UNIQUE (tenant_id,country_code,identifier_type,normalized_value)
);
CREATE TABLE foundation.business_partner_address (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    label text CHECK (length(label)<=200), street text NOT NULL CHECK (length(btrim(street)) BETWEEN 1 AND 500),
    street_number text CHECK (length(street_number)<=50), postal_code text NOT NULL CHECK (length(btrim(postal_code)) BETWEEN 1 AND 30),
    city text NOT NULL CHECK (length(btrim(city)) BETWEEN 1 AND 200), province text CHECK (length(province)<=100),
    country_code text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'), additional_info text CHECK (length(additional_info)<=1000),
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES foundation.business_partner(tenant_id,id) ON DELETE RESTRICT,
    UNIQUE (tenant_id,business_partner_id,id)
);
CREATE TABLE foundation.business_partner_address_usage (
    tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL, address_id uuid NOT NULL,
    usage text NOT NULL CHECK (usage IN ('REGISTERED','BILLING','SHIPPING','CORRESPONDENCE')), is_default boolean NOT NULL DEFAULT false,
    PRIMARY KEY (address_id,usage),
    FOREIGN KEY (tenant_id,business_partner_id,address_id) REFERENCES foundation.business_partner_address(tenant_id,business_partner_id,id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX business_partner_address_default_unique ON foundation.business_partner_address_usage(tenant_id,business_partner_id,usage) WHERE is_default;
CREATE TABLE foundation.business_partner_contact_channel (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, business_partner_id uuid NOT NULL,
    channel_type text NOT NULL CHECK (channel_type IN ('EMAIL','PHONE','MOBILE','PEC','WEBSITE')),
    value text NOT NULL CHECK (length(btrim(value)) BETWEEN 1 AND 500), purpose text CHECK (length(purpose)<=200),
    is_primary boolean NOT NULL DEFAULT false,
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES foundation.business_partner(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX business_partner_contact_primary_unique ON foundation.business_partner_contact_channel(tenant_id,business_partner_id,channel_type) WHERE is_primary;
CREATE FUNCTION foundation.guard_business_partner() RETURNS trigger LANGUAGE plpgsql SET search_path TO pg_catalog AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Archiviare il business partner' USING ERRCODE='23514'; END IF;
    IF (NEW.id,NEW.tenant_id,NEW.code) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.code) THEN
        RAISE EXCEPTION 'Identita e codice immutabili' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER business_partner_guard BEFORE UPDATE OR DELETE ON foundation.business_partner FOR EACH ROW EXECUTE FUNCTION foundation.guard_business_partner();
CREATE TRIGGER business_partner_updated_at BEFORE UPDATE ON foundation.business_partner FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
REVOKE ALL ON FUNCTION foundation.guard_business_partner() FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON foundation.business_partner TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON foundation.business_partner_tax_identifier,foundation.business_partner_address,foundation.business_partner_address_usage,foundation.business_partner_contact_channel TO enginia360_app;

ALTER TABLE foundation.permission DROP CONSTRAINT permission_system_code_check;
ALTER TABLE foundation.permission ADD CONSTRAINT permission_system_code_check CHECK (((NOT is_system) OR (code = ANY (ARRAY['permissions.read'::text, 'users.reset_password'::text, 'roles.assign'::text, 'groups.assign_users'::text, 'roles.assign_permissions'::text, 'purchasing-organizations.assign_scope'::text, 'business-partners.read'::text, 'business-partners.create'::text, 'business-partners.update'::text, 'business-partner-numbering.read'::text, 'business-partner-numbering.update'::text])) OR ((split_part(code, '.'::text, 1) = ANY (ARRAY['companies'::text, 'sites'::text, 'warehouse-types'::text, 'warehouses'::text, 'warehouse-locations'::text, 'settings'::text, 'users'::text, 'groups'::text, 'roles'::text, 'sales-organizations'::text, 'purchasing-organizations'::text])) AND (split_part(code, '.'::text, 2) = ANY (ARRAY['read'::text, 'create'::text, 'update'::text, 'delete'::text])) AND (code = ((split_part(code, '.'::text, 1) || '.'::text) || split_part(code, '.'::text, 2))))));

-- Catalogo incrementale per tenant esistenti; nessun ruolo o grant automatico.
INSERT INTO foundation.permission(tenant_id,code,name,is_system)
SELECT t.id,c.code,c.code,true FROM foundation.tenant t
CROSS JOIN (VALUES ('business-partners.read'),('business-partners.create'),('business-partners.update'),('business-partner-numbering.read'),('business-partner-numbering.update')) c(code)
ON CONFLICT(tenant_id,code) DO UPDATE SET is_system=true WHERE NOT foundation.permission.is_system;

COMMIT;
