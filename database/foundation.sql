-- Enginia360 — schema finale, esclusivamente per un database nuovo.
-- Prerequisiti: PostgreSQL 18; esecuzione con psql -X -v ON_ERROR_STOP=1
-- come proprietario postgres, fuori da altre transazioni.
-- Il ruolo enginia360_app deve ESISTERE: il bootstrap SQL non crea login,
-- password o utenti. Deve essere non privilegiato e senza membership elevate.
-- I nomi dei vincoli NOT NULL preesistenti sono conservati per identità canonica.
-- Nessun dato iniziale: cataloghi geografici soltanto con la CLI esplicita
-- documentata in database/seeds/italy/README.md, dopo questa inizializzazione.
-- Non è un aggiornamento: lo schema foundation già presente causa un errore.

BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
SELECT pg_catalog.pg_advisory_xact_lock(3607902026);
DO $foundation_guard$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname IN ('foundation','masterdata')) THEN
        RAISE EXCEPTION 'foundation o masterdata esiste già: usare esclusivamente un database nuovo';
    END IF;
    IF current_user <> 'postgres' THEN
        RAISE EXCEPTION 'Il proprietario di installazione deve essere postgres';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'enginia360_app') THEN
        RAISE EXCEPTION 'Ruoli prerequisiti mancanti: enginia360_app';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'enginia360_app'
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m
                  JOIN pg_catalog.pg_roles r ON r.oid = m.member
                  WHERE r.rolname = 'enginia360_app') THEN
        RAISE EXCEPTION 'enginia360_app deve essere privo di privilegi elevati e membership';
    END IF;
END;
$foundation_guard$;
SET LOCAL search_path = pg_catalog;

-- Schema e proprietà.


CREATE SCHEMA foundation;


ALTER SCHEMA foundation OWNER TO postgres;

COMMENT ON SCHEMA foundation IS 'Struttura organizzativa e autorizzazioni del tenant.';

-- Funzioni di integrità: acquisti, identità geografica, timestamp e classificazione.

CREATE FUNCTION foundation.assert_purchasing_coverage(p_tenant uuid, p_organization uuid, p_company uuid) RETURNS void
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog'
    AS $$
DECLARE
    coverage_mode text;
    site_count bigint;
BEGIN
    -- Serializza anche scritture SQL concorrenti dello stesso aggregato in READ COMMITTED.
    SELECT site_scope INTO coverage_mode FROM foundation.purchasing_organization_company
    WHERE tenant_id=p_tenant AND purchasing_organization_id=p_organization AND company_id=p_company
    FOR NO KEY UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    SELECT count(*) INTO site_count FROM foundation.purchasing_organization_site
    WHERE tenant_id=p_tenant AND purchasing_organization_id=p_organization AND company_id=p_company;
    IF (coverage_mode='all_sites' AND site_count<>0) OR (coverage_mode='selected_sites' AND site_count=0) THEN
        RAISE EXCEPTION 'Invalid purchasing organization site coverage' USING ERRCODE='23514';
    END IF;
END;
$$;


ALTER FUNCTION foundation.assert_purchasing_coverage(p_tenant uuid, p_organization uuid, p_company uuid) OWNER TO postgres;

CREATE FUNCTION foundation.check_purchasing_coverage() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog'
    AS $$
BEGIN
    IF TG_OP<>'INSERT' THEN
        PERFORM foundation.assert_purchasing_coverage(OLD.tenant_id,OLD.purchasing_organization_id,OLD.company_id);
    END IF;
    IF TG_OP<>'DELETE' THEN
        PERFORM foundation.assert_purchasing_coverage(NEW.tenant_id,NEW.purchasing_organization_id,NEW.company_id);
    END IF;
    RETURN NULL;
END;
$$;


ALTER FUNCTION foundation.check_purchasing_coverage() OWNER TO postgres;

CREATE FUNCTION foundation.guard_country_iso_identity() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.iso_code IS DISTINCT FROM OLD.iso_code
       AND EXISTS(SELECT 1 FROM foundation.city WHERE country_id=OLD.id) THEN
        RAISE EXCEPTION 'Referenced country identity cannot change' USING ERRCODE='23503';
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION foundation.guard_country_iso_identity() OWNER TO postgres;

CREATE FUNCTION foundation.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog'
    AS $$
BEGIN
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END;
$$;


ALTER FUNCTION foundation.set_updated_at() OWNER TO postgres;

CREATE FUNCTION foundation.valid_site_functions(p_values text[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE PARALLEL SAFE
    AS $$
    SELECT coalesce(array_ndims(p_values), 1) = 1
       AND coalesce(array_lower(p_values, 1), 1) = 1
       AND p_values <@ ARRAY['OPERATIONAL', 'ADMINISTRATIVE', 'COMMERCIAL',
                           'PRODUCTION', 'LOGISTICS', 'WAREHOUSE',
                           'TECHNICAL_SERVICE', 'MANAGEMENT', 'RETAIL']::text[]
       AND cardinality(p_values) = (SELECT count(DISTINCT item) FROM unnest(p_values) AS item);
$$;


ALTER FUNCTION foundation.valid_site_functions(p_values text[]) OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

-- Organizzazione del tenant.

CREATE TABLE foundation.tenant (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT tenant_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT tenant_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT tenant_code_key UNIQUE (code),
    CONSTRAINT tenant_pkey PRIMARY KEY (id)
);


ALTER TABLE foundation.tenant OWNER TO postgres;

COMMENT ON TABLE foundation.tenant IS 'Cliente o gruppo cliente della piattaforma.';

CREATE TABLE foundation.company (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT company_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT company_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT company_pkey PRIMARY KEY (id),
    CONSTRAINT company_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT company_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.company OWNER TO postgres;

COMMENT ON TABLE foundation.company IS 'Società giuridica appartenente al tenant.';

CREATE TABLE foundation.site (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    site_type text,
    vat_number text,
    tax_code text,
    address text NOT NULL,
    city text NOT NULL,
    province text NOT NULL,
    postal_code text NOT NULL,
    country_code character varying(2) NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    functions text[] DEFAULT '{}'::text[] NOT NULL,
    region text,
    CONSTRAINT site_address_required_check CHECK (((address ~ '[^[:space:]]'::text) AND (city ~ '[^[:space:]]'::text) AND (province ~ '[^[:space:]]'::text) AND (postal_code ~ '[^[:space:]]'::text))),
    CONSTRAINT site_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT site_country_code_check CHECK (country_code IN (
        'AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU', 'AW', 'AX', 'AZ',
        'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ', 'BR', 'BS',
        'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN',
        'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE',
        'EG', 'EH', 'ER', 'ES', 'ET', 'FI', 'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF',
        'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM',
        'HN', 'HR', 'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT', 'JE', 'JM',
        'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC',
        'LI', 'LK', 'LR', 'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH', 'MK',
        'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU', 'MV', 'MW', 'MX', 'MY', 'MZ', 'NA',
        'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG',
        'PH', 'PK', 'PL', 'PM', 'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW',
        'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS',
        'ST', 'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK', 'TL', 'TM', 'TN', 'TO',
        'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI',
        'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW'
    )),
    CONSTRAINT site_functions_check CHECK (foundation.valid_site_functions(functions)),
    CONSTRAINT site_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT site_region_check CHECK ((length(region) <= 500)),
    CONSTRAINT site_tax_identity_check CHECK ((COALESCE((vat_number ~ '[^[:space:]]'::text), false) OR COALESCE((tax_code ~ '[^[:space:]]'::text), false))),
    CONSTRAINT site_type_check CHECK ((site_type = ANY (ARRAY['LEGAL'::text, 'LOCAL_UNIT'::text, 'SECONDARY'::text]))),
    CONSTRAINT site_pkey PRIMARY KEY (id),
    CONSTRAINT site_tenant_id_company_id_code_key UNIQUE (tenant_id, company_id, code),
    CONSTRAINT site_tenant_id_company_id_id_key UNIQUE (tenant_id, company_id, id),
    CONSTRAINT site_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.site OWNER TO postgres;

COMMENT ON TABLE foundation.site IS 'Sede della società, inclusa la sede legale.';

COMMENT ON COLUMN foundation.site.site_type IS 'Tipologia giuridica facoltativa: LEGAL, LOCAL_UNIT o SECONDARY.';

COMMENT ON COLUMN foundation.site.vat_number IS 'Partita IVA mantenuta sulla sede per scelta del proprietario del prodotto.';

COMMENT ON COLUMN foundation.site.tax_code IS 'Codice fiscale mantenuto sulla sede per scelta del proprietario del prodotto.';

COMMENT ON COLUMN foundation.site.functions IS 'Funzioni aziendali della sede, indipendenti dalla tipologia giuridica.';

COMMENT ON COLUMN foundation.site.region IS 'Regione facoltativa come snapshot indirizzo, indipendente dai cataloghi.';

-- Magazzini e ubicazioni.

CREATE TABLE foundation.warehouse_type (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT warehouse_type_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT warehouse_type_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT warehouse_type_pkey PRIMARY KEY (id),
    CONSTRAINT warehouse_type_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT warehouse_type_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.warehouse_type OWNER TO postgres;

COMMENT ON TABLE foundation.warehouse_type IS 'Tipologia di magazzino mantenuta dal cliente nel proprio tenant.';

CREATE TABLE foundation.warehouse (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    site_id uuid NOT NULL,
    warehouse_type_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT warehouse_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT warehouse_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT warehouse_pkey PRIMARY KEY (id),
    CONSTRAINT warehouse_tenant_id_id_key UNIQUE (tenant_id, id),
    CONSTRAINT warehouse_tenant_id_site_id_code_key UNIQUE (tenant_id, site_id, code)
);


ALTER TABLE foundation.warehouse OWNER TO postgres;

COMMENT ON TABLE foundation.warehouse IS 'Magazzino appartenente a una sede.';

CREATE TABLE foundation.warehouse_location (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    warehouse_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT warehouse_location_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT warehouse_location_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT warehouse_location_pkey PRIMARY KEY (id),
    CONSTRAINT warehouse_location_tenant_id_warehouse_id_code_key UNIQUE (tenant_id, warehouse_id, code)
);


ALTER TABLE foundation.warehouse_location OWNER TO postgres;

COMMENT ON TABLE foundation.warehouse_location IS 'Ubicazione interna al magazzino.';

-- Identità, gruppi e autorizzazioni.

CREATE TABLE foundation."user" (
    id uuid DEFAULT gen_random_uuid() CONSTRAINT account_id_not_null NOT NULL,
    tenant_id uuid,
    username text CONSTRAINT account_username_not_null NOT NULL,
    password_hash text,
    security_stamp uuid DEFAULT gen_random_uuid() CONSTRAINT account_security_stamp_not_null NOT NULL,
    is_super_admin boolean DEFAULT false CONSTRAINT account_is_super_admin_not_null NOT NULL,
    is_enabled boolean DEFAULT true CONSTRAINT account_is_enabled_not_null NOT NULL,
    must_change_password boolean DEFAULT true CONSTRAINT account_must_change_password_not_null NOT NULL,
    failed_attempts integer DEFAULT 0 CONSTRAINT account_failed_attempts_not_null NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() CONSTRAINT account_created_at_not_null NOT NULL,
    updated_at timestamp with time zone DEFAULT now() CONSTRAINT account_updated_at_not_null NOT NULL,
    email text NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    date_of_birth date,
    phone_number text,
    preferred_language text DEFAULT 'it'::text NOT NULL,
    CONSTRAINT user_date_of_birth_check CHECK ((date_of_birth <= ((CURRENT_TIMESTAMP AT TIME ZONE 'UTC'::text))::date)),
    CONSTRAINT user_email_check CHECK (((char_length(email) <= 254) AND (email ~ '^[A-Za-z0-9!#$%&''*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&''*+/=?^_`{|}~-]+)*@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$'::text))),
    CONSTRAINT user_failed_attempts_check CHECK ((failed_attempts >= 0)),
    CONSTRAINT user_first_name_check CHECK (((first_name ~ '[^[:space:]]'::text) AND (char_length(first_name) <= 200))),
    CONSTRAINT user_global_admin_check CHECK ((((tenant_id IS NULL) AND is_super_admin) OR ((tenant_id IS NOT NULL) AND (NOT is_super_admin)))),
    CONSTRAINT user_last_name_check CHECK (((last_name ~ '[^[:space:]]'::text) AND (char_length(last_name) <= 200))),
    CONSTRAINT user_phone_number_check CHECK ((char_length(phone_number) <= 50)),
    CONSTRAINT user_preferred_language_check CHECK ((preferred_language = ANY (ARRAY['it'::text, 'en'::text]))),
    CONSTRAINT user_username_check CHECK ((btrim(username) <> ''::text)),
    CONSTRAINT user_pkey PRIMARY KEY (id),
    CONSTRAINT user_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation."user" OWNER TO postgres;

COMMENT ON TABLE foundation."user" IS 'Identità unica del tenant; Super Admin globale esplicito senza tenant.';

COMMENT ON COLUMN foundation."user".password_hash IS 'NULL per utenti in attesa di impostazione esplicita della password.';

CREATE TABLE foundation.user_group (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_group_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT user_group_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT user_group_pkey PRIMARY KEY (id),
    CONSTRAINT user_group_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT user_group_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.user_group OWNER TO postgres;

COMMENT ON TABLE foundation.user_group IS 'Gruppo di utenti del tenant, senza annidamento.';

CREATE TABLE foundation.role (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text,
    name text NOT NULL,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT role_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT role_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT role_pkey PRIMARY KEY (id),
    CONSTRAINT role_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT role_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.role OWNER TO postgres;

COMMENT ON TABLE foundation.role IS 'Insieme di permessi valido nel tenant, senza ereditarietà.';

CREATE TABLE foundation.permission (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_system boolean DEFAULT false NOT NULL,
    CONSTRAINT permission_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT permission_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT permission_system_code_check CHECK (((NOT is_system) OR (code = ANY (ARRAY['permissions.read'::text, 'users.reset_password'::text, 'roles.assign'::text, 'groups.assign_users'::text, 'roles.assign_permissions'::text, 'purchasing-organizations.assign_scope'::text, 'business-partners.read'::text, 'business-partners.create'::text, 'business-partners.update'::text, 'business-partner-numbering.read'::text, 'business-partner-numbering.update'::text, 'roles.assign_companies'::text, 'business-partner-companies.read'::text, 'business-partner-companies.create'::text, 'business-partner-companies.update'::text, 'business-partner-companies.use_customer'::text, 'business-partner-companies.use_supplier'::text])) OR ((split_part(code, '.'::text, 1) = ANY (ARRAY['companies'::text, 'sites'::text, 'warehouse-types'::text, 'warehouses'::text, 'warehouse-locations'::text, 'settings'::text, 'users'::text, 'groups'::text, 'roles'::text, 'sales-organizations'::text, 'purchasing-organizations'::text])) AND (split_part(code, '.'::text, 2) = ANY (ARRAY['read'::text, 'create'::text, 'update'::text, 'delete'::text])) AND (code = ((split_part(code, '.'::text, 1) || '.'::text) || split_part(code, '.'::text, 2)))))),
    CONSTRAINT permission_pkey PRIMARY KEY (id),
    CONSTRAINT permission_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT permission_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.permission OWNER TO postgres;

COMMENT ON TABLE foundation.permission IS 'Catalogo applicativo materializzato per tenant; gestione dei ruoli separata dalla definizione delle operazioni.';

COMMENT ON COLUMN foundation.permission.is_system IS 'Voce del catalogo applicativo; i vecchi codici non supportati restano conservati fuori dal catalogo.';

CREATE TABLE foundation.user_group_member (
    tenant_id uuid NOT NULL,
    user_group_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_group_member_pkey PRIMARY KEY (tenant_id, user_group_id, user_id)
);


ALTER TABLE foundation.user_group_member OWNER TO postgres;

COMMENT ON TABLE foundation.user_group_member IS 'Appartenenza di un utente a un gruppo dello stesso tenant.';

CREATE TABLE foundation.user_role (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_role_pkey PRIMARY KEY (tenant_id, user_id, role_id)
);


ALTER TABLE foundation.user_role OWNER TO postgres;

COMMENT ON TABLE foundation.user_role IS 'Assegnazione diretta di un ruolo a un utente dello stesso tenant.';

CREATE TABLE foundation.user_group_role (
    tenant_id uuid NOT NULL,
    user_group_id uuid NOT NULL,
    role_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT user_group_role_pkey PRIMARY KEY (tenant_id, user_group_id, role_id)
);


ALTER TABLE foundation.user_group_role OWNER TO postgres;

COMMENT ON TABLE foundation.user_group_role IS 'Assegnazione di un ruolo a un gruppo dello stesso tenant.';

CREATE TABLE foundation.role_permission (
    tenant_id uuid NOT NULL,
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT role_permission_pkey PRIMARY KEY (tenant_id, role_id, permission_id)
);


ALTER TABLE foundation.role_permission OWNER TO postgres;

COMMENT ON TABLE foundation.role_permission IS 'Associazione tra un ruolo e un permesso dello stesso tenant.';

-- Organizzazioni commerciali e copertura acquisti.

CREATE TABLE foundation.sales_organization (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid NOT NULL,
    name text NOT NULL,
    code text,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sales_organization_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT sales_organization_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT sales_organization_pkey PRIMARY KEY (id),
    CONSTRAINT sales_organization_tenant_id_company_id_code_key UNIQUE (tenant_id, company_id, code),
    CONSTRAINT sales_organization_tenant_id_company_id_id_key UNIQUE (tenant_id, company_id, id),
    CONSTRAINT sales_organization_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.sales_organization OWNER TO postgres;

COMMENT ON TABLE foundation.sales_organization IS 'Unità commerciale di vendita appartenente a una sola azienda.';

CREATE TABLE foundation.purchasing_organization (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    name text NOT NULL,
    code text,
    description text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT purchasing_organization_code_check CHECK ((btrim(code) <> ''::text)),
    CONSTRAINT purchasing_organization_name_check CHECK ((btrim(name) <> ''::text)),
    CONSTRAINT purchasing_organization_pkey PRIMARY KEY (id),
    CONSTRAINT purchasing_organization_tenant_id_code_key UNIQUE (tenant_id, code),
    CONSTRAINT purchasing_organization_tenant_id_id_key UNIQUE (tenant_id, id)
);


ALTER TABLE foundation.purchasing_organization OWNER TO postgres;

COMMENT ON TABLE foundation.purchasing_organization IS 'Unità di approvvigionamento del tenant, distinta dalle aziende acquirenti.';

CREATE TABLE foundation.purchasing_organization_company (
    tenant_id uuid NOT NULL,
    purchasing_organization_id uuid CONSTRAINT purchasing_organization_com_purchasing_organization_id_not_null NOT NULL,
    company_id uuid NOT NULL,
    site_scope text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT purchasing_organization_company_site_scope_check CHECK ((site_scope = ANY (ARRAY['all_sites'::text, 'selected_sites'::text]))),
    CONSTRAINT purchasing_organization_company_pkey PRIMARY KEY (tenant_id, purchasing_organization_id, company_id)
);


ALTER TABLE foundation.purchasing_organization_company OWNER TO postgres;

COMMENT ON TABLE foundation.purchasing_organization_company IS 'Copertura acquisti esplicita per azienda: tutte le sedi oppure sedi selezionate.';

CREATE TABLE foundation.purchasing_organization_site (
    tenant_id uuid NOT NULL,
    purchasing_organization_id uuid CONSTRAINT purchasing_organization_sit_purchasing_organization_id_not_null NOT NULL,
    company_id uuid NOT NULL,
    site_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT purchasing_organization_site_pkey PRIMARY KEY (tenant_id, purchasing_organization_id, company_id, site_id)
);


ALTER TABLE foundation.purchasing_organization_site OWNER TO postgres;

COMMENT ON TABLE foundation.purchasing_organization_site IS 'Sedi selezionate entro la copertura aziendale dell’organizzazione acquisti.';

-- Configurazione, autenticazione e audit.

CREATE TABLE foundation.setting (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    tenant_id uuid NOT NULL,
    company_id uuid,
    site_id uuid,
    key text NOT NULL,
    value jsonb NOT NULL,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT setting_check CHECK (((site_id IS NULL) OR (company_id IS NOT NULL))),
    CONSTRAINT setting_key_check CHECK ((btrim(key) <> ''::text)),
    CONSTRAINT setting_pkey PRIMARY KEY (id),
    CONSTRAINT setting_tenant_id_company_id_site_id_key_key UNIQUE NULLS NOT DISTINCT (tenant_id, company_id, site_id, key)
);


ALTER TABLE foundation.setting OWNER TO postgres;

COMMENT ON TABLE foundation.setting IS 'Configurazione riferita esattamente al tenant, alla società o alla sede; nessuna ereditarietà implicita.';

COMMENT ON COLUMN foundation.setting.value IS 'Valore JSON della configurazione; non destinato a credenziali o segreti.';

CREATE TABLE foundation.login_limit (
    key text NOT NULL,
    window_start timestamp with time zone NOT NULL,
    attempts integer NOT NULL,
    CONSTRAINT login_limit_attempts_check CHECK ((attempts >= 0)),
    CONSTRAINT login_limit_pkey PRIMARY KEY (key)
);


ALTER TABLE foundation.login_limit OWNER TO postgres;

COMMENT ON TABLE foundation.login_limit IS 'Limiti persistenti di accesso; chiave derivata tramite SHA-256.';

CREATE TABLE foundation.audit_event (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_id uuid,
    tenant_id uuid,
    action text NOT NULL,
    resource text NOT NULL,
    record_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    details jsonb,
    CONSTRAINT audit_event_details_check CHECK (((details IS NULL) OR (jsonb_typeof(details) = 'object'::text))),
    CONSTRAINT audit_event_pkey PRIMARY KEY (id)
);


ALTER TABLE foundation.audit_event OWNER TO postgres;

COMMENT ON TABLE foundation.audit_event IS 'Registro minimo atomico senza credenziali o dati dei record.';

COMMENT ON COLUMN foundation.audit_event.details IS 'Variazioni amministrative prima/dopo, senza credenziali o campi di sicurezza.';

-- Cataloghi geografici globali, inizialmente vuoti.

CREATE TABLE foundation.country (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    iso_code text NOT NULL,
    notes text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT country_iso_code_check CHECK (iso_code IN (
        'AD', 'AE', 'AF', 'AG', 'AI', 'AL', 'AM', 'AO', 'AQ', 'AR', 'AS', 'AT', 'AU', 'AW', 'AX', 'AZ',
        'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BL', 'BM', 'BN', 'BO', 'BQ', 'BR', 'BS',
        'BT', 'BV', 'BW', 'BY', 'BZ', 'CA', 'CC', 'CD', 'CF', 'CG', 'CH', 'CI', 'CK', 'CL', 'CM', 'CN',
        'CO', 'CR', 'CU', 'CV', 'CW', 'CX', 'CY', 'CZ', 'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ', 'EC', 'EE',
        'EG', 'EH', 'ER', 'ES', 'ET', 'FI', 'FJ', 'FK', 'FM', 'FO', 'FR', 'GA', 'GB', 'GD', 'GE', 'GF',
        'GG', 'GH', 'GI', 'GL', 'GM', 'GN', 'GP', 'GQ', 'GR', 'GS', 'GT', 'GU', 'GW', 'GY', 'HK', 'HM',
        'HN', 'HR', 'HT', 'HU', 'ID', 'IE', 'IL', 'IM', 'IN', 'IO', 'IQ', 'IR', 'IS', 'IT', 'JE', 'JM',
        'JO', 'JP', 'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP', 'KR', 'KW', 'KY', 'KZ', 'LA', 'LB', 'LC',
        'LI', 'LK', 'LR', 'LS', 'LT', 'LU', 'LV', 'LY', 'MA', 'MC', 'MD', 'ME', 'MF', 'MG', 'MH', 'MK',
        'ML', 'MM', 'MN', 'MO', 'MP', 'MQ', 'MR', 'MS', 'MT', 'MU', 'MV', 'MW', 'MX', 'MY', 'MZ', 'NA',
        'NC', 'NE', 'NF', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NU', 'NZ', 'OM', 'PA', 'PE', 'PF', 'PG',
        'PH', 'PK', 'PL', 'PM', 'PN', 'PR', 'PS', 'PT', 'PW', 'PY', 'QA', 'RE', 'RO', 'RS', 'RU', 'RW',
        'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SH', 'SI', 'SJ', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS',
        'ST', 'SV', 'SX', 'SY', 'SZ', 'TC', 'TD', 'TF', 'TG', 'TH', 'TJ', 'TK', 'TL', 'TM', 'TN', 'TO',
        'TR', 'TT', 'TV', 'TW', 'TZ', 'UA', 'UG', 'UM', 'US', 'UY', 'UZ', 'VA', 'VC', 'VE', 'VG', 'VI',
        'VN', 'VU', 'WF', 'WS', 'YE', 'YT', 'ZA', 'ZM', 'ZW'
    )),
    CONSTRAINT country_name_check CHECK (((length(name) <= 500) AND (name ~ '[^[:space:]]'::text))),
    CONSTRAINT country_notes_check CHECK ((length(notes) <= 4000)),
    CONSTRAINT country_iso_code_key UNIQUE (iso_code),
    CONSTRAINT country_pkey PRIMARY KEY (id)
);


ALTER TABLE foundation.country OWNER TO postgres;

COMMENT ON TABLE foundation.country IS 'Nazioni globali condivise: scrittura applicativa riservata al Super Admin.';

CREATE TABLE foundation.city (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    country_id uuid NOT NULL,
    name text NOT NULL,
    postal_code text NOT NULL,
    province text,
    region text,
    notes text,
    istat_code text,
    is_enabled boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT city_istat_code_check CHECK ((istat_code ~ '^[0-9]{6}$'::text)),
    CONSTRAINT city_name_check CHECK (((length(name) <= 500) AND (name ~ '[^[:space:]]'::text))),
    CONSTRAINT city_notes_check CHECK ((length(notes) <= 4000)),
    CONSTRAINT city_postal_code_check CHECK (((length(postal_code) <= 500) AND (postal_code ~ '[^[:space:]]'::text))),
    CONSTRAINT city_province_check CHECK ((length(province) <= 500)),
    CONSTRAINT city_region_check CHECK ((length(region) <= 500)),
    CONSTRAINT city_pkey PRIMARY KEY (id)
);


ALTER TABLE foundation.city OWNER TO postgres;

COMMENT ON TABLE foundation.city IS 'Località globali, una riga per CAP.';

COMMENT ON COLUMN foundation.city.istat_code IS 'Identità tecnica facoltativa per importazione idempotente, esclusa dal CRUD pubblico.';

-- Relazioni: vincoli composti impediscono collegamenti tra tenant e aziende diversi.

ALTER TABLE ONLY foundation.city
    ADD CONSTRAINT city_country_id_fkey FOREIGN KEY (country_id) REFERENCES foundation.country(id) ON DELETE RESTRICT;

ALTER TABLE ONLY foundation.company
    ADD CONSTRAINT company_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.permission
    ADD CONSTRAINT permission_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.purchasing_organization_company
    ADD CONSTRAINT purchasing_organization_compa_tenant_id_purchasing_organiz_fkey FOREIGN KEY (tenant_id, purchasing_organization_id) REFERENCES foundation.purchasing_organization(tenant_id, id);

ALTER TABLE ONLY foundation.purchasing_organization_company
    ADD CONSTRAINT purchasing_organization_company_tenant_id_company_id_fkey FOREIGN KEY (tenant_id, company_id) REFERENCES foundation.company(tenant_id, id);

ALTER TABLE ONLY foundation.purchasing_organization_site
    ADD CONSTRAINT purchasing_organization_site_tenant_id_company_id_site_id_fkey FOREIGN KEY (tenant_id, company_id, site_id) REFERENCES foundation.site(tenant_id, company_id, id);

ALTER TABLE ONLY foundation.purchasing_organization_site
    ADD CONSTRAINT purchasing_organization_site_tenant_id_purchasing_organiza_fkey FOREIGN KEY (tenant_id, purchasing_organization_id, company_id) REFERENCES foundation.purchasing_organization_company(tenant_id, purchasing_organization_id, company_id);

ALTER TABLE ONLY foundation.purchasing_organization
    ADD CONSTRAINT purchasing_organization_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.role_permission
    ADD CONSTRAINT role_permission_tenant_id_permission_id_fkey FOREIGN KEY (tenant_id, permission_id) REFERENCES foundation.permission(tenant_id, id);

ALTER TABLE ONLY foundation.role_permission
    ADD CONSTRAINT role_permission_tenant_id_role_id_fkey FOREIGN KEY (tenant_id, role_id) REFERENCES foundation.role(tenant_id, id);

ALTER TABLE ONLY foundation.role
    ADD CONSTRAINT role_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.sales_organization
    ADD CONSTRAINT sales_organization_tenant_id_company_id_fkey FOREIGN KEY (tenant_id, company_id) REFERENCES foundation.company(tenant_id, id);

ALTER TABLE ONLY foundation.sales_organization
    ADD CONSTRAINT sales_organization_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.setting
    ADD CONSTRAINT setting_tenant_id_company_id_fkey FOREIGN KEY (tenant_id, company_id) REFERENCES foundation.company(tenant_id, id);

ALTER TABLE ONLY foundation.setting
    ADD CONSTRAINT setting_tenant_id_company_id_site_id_fkey FOREIGN KEY (tenant_id, company_id, site_id) REFERENCES foundation.site(tenant_id, company_id, id);

ALTER TABLE ONLY foundation.setting
    ADD CONSTRAINT setting_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.site
    ADD CONSTRAINT site_tenant_id_company_id_fkey FOREIGN KEY (tenant_id, company_id) REFERENCES foundation.company(tenant_id, id);

ALTER TABLE ONLY foundation.user_group_member
    ADD CONSTRAINT user_group_member_tenant_id_user_group_id_fkey FOREIGN KEY (tenant_id, user_group_id) REFERENCES foundation.user_group(tenant_id, id);

ALTER TABLE ONLY foundation.user_group_member
    ADD CONSTRAINT user_group_member_tenant_id_user_id_fkey FOREIGN KEY (tenant_id, user_id) REFERENCES foundation."user"(tenant_id, id);

ALTER TABLE ONLY foundation.user_group_role
    ADD CONSTRAINT user_group_role_tenant_id_role_id_fkey FOREIGN KEY (tenant_id, role_id) REFERENCES foundation.role(tenant_id, id);

ALTER TABLE ONLY foundation.user_group_role
    ADD CONSTRAINT user_group_role_tenant_id_user_group_id_fkey FOREIGN KEY (tenant_id, user_group_id) REFERENCES foundation.user_group(tenant_id, id);

ALTER TABLE ONLY foundation.user_group
    ADD CONSTRAINT user_group_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.user_role
    ADD CONSTRAINT user_role_tenant_id_role_id_fkey FOREIGN KEY (tenant_id, role_id) REFERENCES foundation.role(tenant_id, id);

ALTER TABLE ONLY foundation.user_role
    ADD CONSTRAINT user_role_tenant_id_user_id_fkey FOREIGN KEY (tenant_id, user_id) REFERENCES foundation."user"(tenant_id, id);

ALTER TABLE ONLY foundation."user"
    ADD CONSTRAINT user_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

ALTER TABLE ONLY foundation.warehouse_location
    ADD CONSTRAINT warehouse_location_tenant_id_warehouse_id_fkey FOREIGN KEY (tenant_id, warehouse_id) REFERENCES foundation.warehouse(tenant_id, id);

ALTER TABLE ONLY foundation.warehouse
    ADD CONSTRAINT warehouse_tenant_id_site_id_fkey FOREIGN KEY (tenant_id, site_id) REFERENCES foundation.site(tenant_id, id);

ALTER TABLE ONLY foundation.warehouse
    ADD CONSTRAINT warehouse_tenant_id_warehouse_type_id_fkey FOREIGN KEY (tenant_id, warehouse_type_id) REFERENCES foundation.warehouse_type(tenant_id, id);

ALTER TABLE ONLY foundation.warehouse_type
    ADD CONSTRAINT warehouse_type_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES foundation.tenant(id);

-- Indici aggiuntivi: identità naturali e accessi inversi alle associazioni.

CREATE INDEX city_country_id ON foundation.city USING btree (country_id);

CREATE UNIQUE INDEX city_import_identity ON foundation.city USING btree (country_id, istat_code, postal_code) WHERE (istat_code IS NOT NULL);

CREATE UNIQUE INDEX city_natural_identity ON foundation.city USING btree (country_id, lower(btrim(name)), lower(btrim(COALESCE(province, ''::text))), btrim(postal_code));

CREATE INDEX ix_audit_event_created_at ON foundation.audit_event USING btree (created_at);

CREATE INDEX ix_role_permission_permission ON foundation.role_permission USING btree (tenant_id, permission_id);

CREATE INDEX ix_user_group_member_user ON foundation.user_group_member USING btree (tenant_id, user_id);

CREATE INDEX ix_user_group_role_role ON foundation.user_group_role USING btree (tenant_id, role_id);

CREATE INDEX ix_user_role_role ON foundation.user_role USING btree (tenant_id, role_id);

CREATE INDEX ix_warehouse_type ON foundation.warehouse USING btree (tenant_id, warehouse_type_id);

CREATE UNIQUE INDEX ux_user_username ON foundation."user" USING btree (COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), lower(username));

-- Trigger: copertura acquisti differita al commit e aggiornamento timestamp.

CREATE TRIGGER country_iso_identity BEFORE UPDATE OF iso_code ON foundation.country FOR EACH ROW EXECUTE FUNCTION foundation.guard_country_iso_identity();

CREATE CONSTRAINT TRIGGER purchasing_coverage_company_check AFTER INSERT OR DELETE OR UPDATE ON foundation.purchasing_organization_company DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.check_purchasing_coverage();

CREATE CONSTRAINT TRIGGER purchasing_coverage_site_check AFTER INSERT OR DELETE OR UPDATE ON foundation.purchasing_organization_site DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.check_purchasing_coverage();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.city FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.company FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.country FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.permission FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.purchasing_organization FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.role FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.sales_organization FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.setting FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.site FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.tenant FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation."user" FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.user_group FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.warehouse FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.warehouse_location FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

CREATE TRIGGER set_updated_at BEFORE UPDATE ON foundation.warehouse_type FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();

-- Privilegi espliciti invariati; audit applicativo limitato al solo INSERT.
-- Nessun ALTER DEFAULT PRIVILEGES né concessione DDL al ruolo applicativo.

GRANT USAGE ON SCHEMA foundation TO enginia360_app;

REVOKE ALL ON FUNCTION foundation.set_updated_at() FROM PUBLIC;

GRANT INSERT ON TABLE foundation.audit_event TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.city TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.company TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.country TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.login_limit TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.permission TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.purchasing_organization TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.purchasing_organization_company TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.purchasing_organization_site TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.role TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.role_permission TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.sales_organization TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.setting TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.site TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.tenant TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation."user" TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.user_group TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.user_group_member TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.user_group_role TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.user_role TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.warehouse TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.warehouse_location TO enginia360_app;

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.warehouse_type TO enginia360_app;

-- Dominio Business Partner: definizioni finali e privilegi espliciti.
\ir masterdata_business_partner.sql

COMMIT;
