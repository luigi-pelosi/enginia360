-- TaxManagement: definizioni finali per una nuova installazione.
-- Transazione, proprietario e prerequisiti sono verificati da foundation.sql.
-- Nessun tenant, permesso tenant o assegnazione viene creato dal baseline.

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
CREATE SCHEMA taxmanagement AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA taxmanagement FROM PUBLIC;
GRANT USAGE ON SCHEMA taxmanagement TO enginia360_app;

CREATE TABLE taxmanagement.tax_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(30) NOT NULL UNIQUE CHECK (btrim(code) <> ''),
    name varchar(100) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    is_active boolean NOT NULL DEFAULT false
);
CREATE TABLE taxmanagement.tax_nature_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    scheme varchar(50) NOT NULL CHECK (btrim(scheme) <> ''),
    code varchar(20) NOT NULL CHECK (btrim(code) <> ''),
    description varchar(255) NOT NULL CHECK (btrim(description) <> ''),
    valid_from date NOT NULL CHECK (isfinite(valid_from)),
    valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
    UNIQUE (country_id, scheme, code, valid_from)
);
CREATE TABLE taxmanagement.tax_codes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    code varchar(50) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    is_active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);
CREATE UNIQUE INDEX tax_codes_tenant_code_key ON taxmanagement.tax_codes(tenant_id, country_id, tax_type_id, lower(code));
CREATE INDEX tax_codes_list_idx ON taxmanagement.tax_codes(tenant_id, is_active, country_id, tax_type_id);
CREATE TABLE taxmanagement.tax_code_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    tax_code_id uuid NOT NULL,
    rate numeric(9,6) NOT NULL CHECK (rate >= 0 AND rate <= 999.999999),
    treatment text NOT NULL CHECK (treatment IN ('TAXABLE','ZERO_RATED','EXEMPT','NON_TAXABLE','OUT_OF_SCOPE','REVERSE_CHARGE','EXCLUDED','MARGIN','OTHER_EU')),
    tax_nature_code_id uuid REFERENCES taxmanagement.tax_nature_codes(id) ON DELETE RESTRICT,
    legal_reference varchar(255),
    valid_from date NOT NULL CHECK (isfinite(valid_from)),
    valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, tax_code_id) REFERENCES taxmanagement.tax_codes(tenant_id, id) ON DELETE RESTRICT,
    CHECK ((treatment = 'TAXABLE' AND rate > 0 AND tax_nature_code_id IS NULL)
        OR (treatment <> 'TAXABLE' AND rate = 0)),
    CHECK (treatment <> 'ZERO_RATED' OR tax_nature_code_id IS NULL),
    CONSTRAINT tax_code_versions_no_overlap EXCLUDE USING gist (
        tax_code_id public.gist_uuid_ops WITH =,
        daterange(valid_from, valid_to, '[]') WITH &&
    )
);
CREATE INDEX tax_code_versions_tenant_root_idx ON taxmanagement.tax_code_versions(tenant_id, tax_code_id, valid_from);
CREATE TABLE taxmanagement.tax_audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    tax_code_id uuid NOT NULL,
    actor_id uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
    action text NOT NULL CHECK (length(btrim(action)) BETWEEN 1 AND 100),
    details jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, tax_code_id) REFERENCES taxmanagement.tax_codes(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX tax_audit_events_root_idx ON taxmanagement.tax_audit_events(tenant_id, tax_code_id, created_at, id);

CREATE FUNCTION taxmanagement.reject_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    RAISE EXCEPTION 'Record TaxManagement immutabile: % %', TG_TABLE_NAME, TG_OP USING ERRCODE = '23514';
END $$;
CREATE FUNCTION taxmanagement.guard_country_identity() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.iso_code IS DISTINCT FROM OLD.iso_code AND (
        EXISTS (SELECT 1 FROM taxmanagement.tax_codes WHERE country_id = OLD.id) OR
        EXISTS (SELECT 1 FROM taxmanagement.tax_nature_codes WHERE country_id = OLD.id)
    ) THEN
        RAISE EXCEPTION 'Identita paese fiscale immutabile' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER taxmanagement_country_identity BEFORE UPDATE OF iso_code ON foundation.country
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_country_identity();

CREATE FUNCTION taxmanagement.guard_tax_code() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Disattivare il codice fiscale, non eliminarlo' USING ERRCODE = '23514';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.id,NEW.tenant_id,NEW.tax_type_id,NEW.country_id,NEW.code,NEW.created_at)
           IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.tax_type_id,OLD.country_id,OLD.code,OLD.created_at) THEN
            RAISE EXCEPTION 'Identita fiscale immutabile' USING ERRCODE = '23514';
        END IF;
        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'Incrementare la revisione fiscale di uno' USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM 1 FROM foundation.country WHERE id = NEW.country_id FOR SHARE;
    PERFORM 1 FROM taxmanagement.tax_types WHERE id = NEW.tax_type_id AND code = 'VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Tipo fiscale non attivo in fase 1' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION taxmanagement.guard_tax_version() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE
    root_country uuid;
    root_iso text;
    nature taxmanagement.tax_nature_codes%ROWTYPE;
    expected_treatment text;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Versione fiscale immutabile' USING ERRCODE = '23514'; END IF;
    -- Il lock della radice coordina anche Save/Schedule applicativi. L'exclusion
    -- constraint resta la prova di assenza overlap a qualsiasi isolamento.
    SELECT c.country_id, p.iso_code INTO root_country, root_iso
    FROM taxmanagement.tax_codes c JOIN foundation.country p ON p.id = c.country_id
    WHERE c.id = NEW.tax_code_id AND c.tenant_id = NEW.tenant_id FOR UPDATE OF c;
    IF NOT FOUND THEN RAISE EXCEPTION 'Radice fiscale del tenant mancante' USING ERRCODE = '23503'; END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.id,NEW.tenant_id,NEW.tax_code_id,NEW.rate,NEW.treatment,NEW.tax_nature_code_id,NEW.legal_reference,NEW.valid_from,NEW.created_at,NEW.created_by)
           IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.tax_code_id,OLD.rate,OLD.treatment,OLD.tax_nature_code_id,OLD.legal_reference,OLD.valid_from,OLD.created_at,OLD.created_by) THEN
            RAISE EXCEPTION 'Payload versione fiscale immutabile' USING ERRCODE = '23514';
        END IF;
        IF NEW.valid_to IS DISTINCT FROM OLD.valid_to AND
           (NEW.valid_to IS NULL OR (OLD.valid_to IS NOT NULL AND NEW.valid_to > OLD.valid_to)) THEN
            RAISE EXCEPTION 'Consentita soltanto la chiusura anticipata della versione' USING ERRCODE = '23514';
        END IF;
    END IF;
    PERFORM 1 FROM foundation."user" u WHERE u.id = NEW.created_by AND
        (u.tenant_id = NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_super_admin)) FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Attore fiscale fuori tenant' USING ERRCODE = '23514'; END IF;
    IF NEW.tax_nature_code_id IS NOT NULL THEN
        SELECT * INTO nature FROM taxmanagement.tax_nature_codes WHERE id = NEW.tax_nature_code_id;
        IF NOT FOUND OR nature.country_id <> root_country OR NEW.valid_from < nature.valid_from OR
           (nature.valid_to IS NOT NULL AND (NEW.valid_to IS NULL OR NEW.valid_to > nature.valid_to)) THEN
            RAISE EXCEPTION 'Natura fiscale incompatibile con paese o intervallo' USING ERRCODE = '23514';
        END IF;
    END IF;
    -- ZERO_RATED è esplicito per paesi diversi da IT. In Italia ogni aliquota
    -- zero deve portare la corretta Natura FatturaPA, mai un generico zero.
    IF root_iso = 'IT' AND NEW.treatment <> 'TAXABLE' THEN
        expected_treatment := CASE
            WHEN nature.code = 'N1' THEN 'EXCLUDED'
            WHEN nature.code IN ('N2.1','N2.2') THEN 'OUT_OF_SCOPE'
            WHEN nature.code IN ('N3.1','N3.2','N3.3','N3.4','N3.5','N3.6') THEN 'NON_TAXABLE'
            WHEN nature.code = 'N4' THEN 'EXEMPT'
            WHEN nature.code = 'N5' THEN 'MARGIN'
            WHEN nature.code IN ('N6.1','N6.2','N6.3','N6.4','N6.5','N6.6','N6.7','N6.8','N6.9') THEN 'REVERSE_CHARGE'
            WHEN nature.code = 'N7' THEN 'OTHER_EU' END;
        IF nature.scheme IS DISTINCT FROM 'FATTURAPA' OR expected_treatment IS DISTINCT FROM NEW.treatment THEN
            RAISE EXCEPTION 'Trattamento e Natura FatturaPA incoerenti' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION taxmanagement.guard_tax_audit() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    PERFORM 1 FROM foundation."user" u WHERE u.id = NEW.actor_id AND
        (u.tenant_id = NEW.tenant_id OR (u.tenant_id IS NULL AND u.is_super_admin)) FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Attore audit fuori tenant' USING ERRCODE = '23514'; END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION taxmanagement.require_tax_version() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM taxmanagement.tax_code_versions WHERE tenant_id = NEW.tenant_id AND tax_code_id = NEW.id) THEN
        RAISE EXCEPTION 'Il codice fiscale richiede almeno una versione' USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER tax_types_immutable BEFORE UPDATE OR DELETE ON taxmanagement.tax_types FOR EACH ROW EXECUTE FUNCTION taxmanagement.reject_mutation();
CREATE TRIGGER tax_natures_immutable BEFORE UPDATE OR DELETE ON taxmanagement.tax_nature_codes FOR EACH ROW EXECUTE FUNCTION taxmanagement.reject_mutation();
CREATE TRIGGER tax_codes_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_codes FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_code();
CREATE TRIGGER tax_codes_updated_at BEFORE UPDATE ON taxmanagement.tax_codes FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE CONSTRAINT TRIGGER tax_codes_require_version AFTER INSERT ON taxmanagement.tax_codes DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.require_tax_version();
CREATE TRIGGER tax_versions_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_code_versions FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_version();
CREATE TRIGGER tax_audit_insert_guard BEFORE INSERT ON taxmanagement.tax_audit_events FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_audit();
CREATE TRIGGER tax_audit_immutable BEFORE UPDATE OR DELETE ON taxmanagement.tax_audit_events FOR EACH ROW EXECUTE FUNCTION taxmanagement.reject_mutation();

INSERT INTO taxmanagement.tax_types(id,code,name,description,is_active) VALUES
    (md5('taxmanagement.type.VAT')::uuid,'VAT','IVA','Imposta sul valore aggiunto',true),
    (md5('taxmanagement.type.WITHHOLDING')::uuid,'WITHHOLDING','Ritenuta','Non operativa nella fase 1',false),
    (md5('taxmanagement.type.STAMP_DUTY')::uuid,'STAMP_DUTY','Imposta di bollo','Non operativa nella fase 1',false),
    (md5('taxmanagement.type.EXCISE')::uuid,'EXCISE','Accisa','Non operativa nella fase 1',false),
    (md5('taxmanagement.type.SALES_TAX')::uuid,'SALES_TAX','Sales tax','Non operativa nella fase 1',false)
ON CONFLICT (code) DO NOTHING;

-- Fonte: FatturaPA, Specifiche tecniche del formato V1.4, 31 gennaio 2025.
-- https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.4/Specifiche_tecniche_del_formato_FatturaPA_V1.4.pdf
-- SHA256 8adde9acf0596f14e2cce66f3c1a4d36ce4e13f65582b45c333fe28eee4d93dc
-- Catalogo delle 21 nature correnti, descrizioni sintetiche; esclusi N2/N3/N6
-- obsoleti. 2021-01-01 e il limite supportato di questa nomenclatura, non
-- una ricostruzione storica delle descrizioni (N7 aggiornata nel 2022), ne
-- l'inizio giuridico delle singole agevolazioni. Nessun paese fittizio inserito.
CREATE FUNCTION taxmanagement.seed_italian_natures(p_country uuid) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog AS $$
    INSERT INTO taxmanagement.tax_nature_codes(id,country_id,scheme,code,description,valid_from)
    SELECT md5('taxmanagement.IT.FATTURAPA.' || v.code || '.2021-01-01')::uuid,
        p.id,'FATTURAPA',v.code,v.description,DATE '2021-01-01'
    FROM foundation.country p CROSS JOIN (VALUES
        ('N1','Escluse ex art. 15'),
        ('N2.1','Non soggette ad IVA ai sensi degli artt. da 7 a 7-septies del DPR 633/72'),
        ('N2.2','Non soggette - altri casi'),
        ('N3.1','Non imponibili - esportazioni'),
        ('N3.2','Non imponibili - cessioni intracomunitarie'),
        ('N3.3','Non imponibili - cessioni verso San Marino'),
        ('N3.4','Non imponibili - operazioni assimilate alle cessioni all’esportazione'),
        ('N3.5','Non imponibili - a seguito di dichiarazioni d’intento'),
        ('N3.6','Non imponibili - altre operazioni che non concorrono alla formazione del plafond'),
        ('N4','Esenti'),
        ('N5','Regime del margine / IVA non esposta in fattura'),
        ('N6.1','Inversione contabile - cessione di rottami e altri materiali di recupero'),
        ('N6.2','Inversione contabile - cessione di oro e argento puro'),
        ('N6.3','Inversione contabile - subappalto nel settore edile'),
        ('N6.4','Inversione contabile - cessione di fabbricati'),
        ('N6.5','Inversione contabile - cessione di telefoni cellulari'),
        ('N6.6','Inversione contabile - cessione di prodotti elettronici'),
        ('N6.7','Inversione contabile - prestazioni comparto edile e settori connessi'),
        ('N6.8','Inversione contabile - operazioni settore energetico'),
        ('N6.9','Inversione contabile - altri casi'),
        ('N7','IVA assolta in altro stato UE (vendite a distanza e altri servizi)')
    ) AS v(code,description)
    WHERE p.id = p_country AND p.iso_code = 'IT'
    ON CONFLICT (country_id,scheme,code,valid_from) DO NOTHING;
$$;
CREATE FUNCTION taxmanagement.seed_country_natures() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.iso_code = 'IT' THEN PERFORM taxmanagement.seed_italian_natures(NEW.id); END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER taxmanagement_seed_country AFTER INSERT OR UPDATE OF iso_code ON foundation.country
FOR EACH ROW EXECUTE FUNCTION taxmanagement.seed_country_natures();
SELECT taxmanagement.seed_italian_natures(id) FROM foundation.country WHERE iso_code = 'IT';

REVOKE ALL ON ALL TABLES IN SCHEMA taxmanagement FROM PUBLIC, enginia360_app;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA taxmanagement FROM PUBLIC, enginia360_app;
GRANT SELECT ON taxmanagement.tax_types,taxmanagement.tax_nature_codes TO enginia360_app;
GRANT SELECT,INSERT,UPDATE ON taxmanagement.tax_codes TO enginia360_app;
GRANT SELECT,INSERT ON taxmanagement.tax_code_versions TO enginia360_app;
GRANT UPDATE(valid_to) ON taxmanagement.tax_code_versions TO enginia360_app;
GRANT SELECT,INSERT ON taxmanagement.tax_audit_events TO enginia360_app;
COMMENT ON TABLE taxmanagement.tax_audit_events IS 'Audit fiscale append-only del tenant. Details contiene solo metadati minimi, non copie di dati personali.';
COMMENT ON TABLE taxmanagement.tax_code_versions IS 'Validita inclusiva, senza sovrapposizioni; payload immutabile, sola chiusura anticipata consentita.';

CREATE TABLE taxmanagement.item_tax_classifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
    code varchar(50) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    is_active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,country_id,tax_type_id,id)
);
CREATE UNIQUE INDEX item_tax_classifications_code_key ON taxmanagement.item_tax_classifications(tenant_id,country_id,tax_type_id,lower(code));
CREATE INDEX item_tax_classifications_list_idx ON taxmanagement.item_tax_classifications(tenant_id,is_active,country_id,tax_type_id);
CREATE TABLE taxmanagement.item_tax_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    item_id uuid NOT NULL,
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
    item_tax_classification_id uuid NOT NULL,
    valid_from date NOT NULL CHECK (isfinite(valid_from)),
    valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id,country_id,tax_type_id,item_tax_classification_id)
        REFERENCES taxmanagement.item_tax_classifications(tenant_id,country_id,tax_type_id,id) ON DELETE RESTRICT,
    UNIQUE (tenant_id,item_id,revision),
    CONSTRAINT item_tax_profiles_no_overlap EXCLUDE USING gist (
        tenant_id public.gist_uuid_ops WITH =,
        item_id public.gist_uuid_ops WITH =,
        country_id public.gist_uuid_ops WITH =,
        tax_type_id public.gist_uuid_ops WITH =,
        daterange(valid_from,valid_to,'[]') WITH &&
    )
);
CREATE INDEX item_tax_profiles_resolve_idx ON taxmanagement.item_tax_profiles(tenant_id,item_id,country_id,tax_type_id,valid_from);
COMMENT ON TABLE taxmanagement.item_tax_profiles IS 'Intervalli DATE inclusivi. Stream globale soggetto: max(revision), zero se vuoto. Payload immutabile, sola chiusura anticipata. Nessuna inferenza automatica.';
CREATE TABLE taxmanagement.partner_tax_classifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
    code varchar(50) NOT NULL CHECK (btrim(code) <> ''),
    name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
    description text,
    is_active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id,id),
    UNIQUE (tenant_id,country_id,tax_type_id,id)
);
CREATE UNIQUE INDEX partner_tax_classifications_code_key ON taxmanagement.partner_tax_classifications(tenant_id,country_id,tax_type_id,lower(code));
CREATE INDEX partner_tax_classifications_list_idx ON taxmanagement.partner_tax_classifications(tenant_id,is_active,country_id,tax_type_id);
CREATE TABLE taxmanagement.partner_tax_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    business_partner_id uuid NOT NULL,
    country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
    tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
    partner_tax_classification_id uuid NOT NULL,
    valid_from date NOT NULL CHECK (isfinite(valid_from)),
    valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
    revision bigint NOT NULL CHECK (revision BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id,business_partner_id) REFERENCES masterdata.business_partner(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id,country_id,tax_type_id,partner_tax_classification_id)
        REFERENCES taxmanagement.partner_tax_classifications(tenant_id,country_id,tax_type_id,id) ON DELETE RESTRICT,
    UNIQUE (tenant_id,business_partner_id,revision),
    CONSTRAINT partner_tax_profiles_no_overlap EXCLUDE USING gist (
        tenant_id public.gist_uuid_ops WITH =,
        business_partner_id public.gist_uuid_ops WITH =,
        country_id public.gist_uuid_ops WITH =,
        tax_type_id public.gist_uuid_ops WITH =,
        daterange(valid_from,valid_to,'[]') WITH &&
    )
);
CREATE INDEX partner_tax_profiles_resolve_idx ON taxmanagement.partner_tax_profiles(tenant_id,business_partner_id,country_id,tax_type_id,valid_from);
COMMENT ON TABLE taxmanagement.partner_tax_profiles IS 'Intervalli DATE inclusivi. Stream globale soggetto: max(revision), zero se vuoto. Payload immutabile, sola chiusura anticipata. Nessuna inferenza automatica.';

CREATE FUNCTION taxmanagement.guard_classification_country_identity() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF NEW.iso_code IS DISTINCT FROM OLD.iso_code AND (
        EXISTS (SELECT 1 FROM taxmanagement.item_tax_classifications WHERE country_id=OLD.id) OR
        EXISTS (SELECT 1 FROM taxmanagement.partner_tax_classifications WHERE country_id=OLD.id)
    ) THEN RAISE EXCEPTION 'Identita paese classificazione immutabile' USING ERRCODE='23514'; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER taxclassification_country_identity BEFORE UPDATE OF iso_code ON foundation.country
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_classification_country_identity();

CREATE FUNCTION taxmanagement.guard_classification() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Disattivare la classificazione, non eliminarla' USING ERRCODE='23514'; END IF;
    IF TG_OP='UPDATE' THEN
        IF (NEW.id,NEW.tenant_id,NEW.country_id,NEW.tax_type_id,NEW.code,NEW.created_at)
           IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.country_id,OLD.tax_type_id,OLD.code,OLD.created_at) THEN
            RAISE EXCEPTION 'Identita classificazione immutabile' USING ERRCODE='23514';
        END IF;
        IF NEW.version <> OLD.version+1 THEN
            RAISE EXCEPTION 'Incrementare versione classificazione di uno' USING ERRCODE='23514';
        END IF;
    ELSE
        IF NEW.version <> 1 THEN RAISE EXCEPTION 'Versione iniziale classificazione uno' USING ERRCODE='23514'; END IF;
        NEW.created_at := transaction_timestamp();
    END IF;
    NEW.updated_at := transaction_timestamp();
    PERFORM 1 FROM foundation.country WHERE id=NEW.country_id FOR SHARE;
    PERFORM 1 FROM taxmanagement.tax_types WHERE id=NEW.tax_type_id AND code='VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 2' USING ERRCODE='23514'; END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION taxmanagement.guard_item_tax_profile() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE previous_revision bigint;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Profilo fiscale immutabile' USING ERRCODE='23514'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('tax-profile:item:' || NEW.tenant_id::text || ':' || NEW.item_id::text,0));
    PERFORM 1 FROM masterdata.catalog_item WHERE tenant_id=NEW.tenant_id AND id=NEW.item_id FOR KEY SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Soggetto profilo fuori tenant o mancante' USING ERRCODE='23503'; END IF;
    IF TG_OP='UPDATE' THEN
        IF (to_jsonb(NEW)-'valid_to') IS DISTINCT FROM (to_jsonb(OLD)-'valid_to') THEN
            RAISE EXCEPTION 'Payload profilo fiscale immutabile' USING ERRCODE='23514';
        END IF;
        IF NEW.valid_to IS DISTINCT FROM OLD.valid_to AND
           (NEW.valid_to IS NULL OR (OLD.valid_to IS NOT NULL AND NEW.valid_to>OLD.valid_to)) THEN
            RAISE EXCEPTION 'Solo chiusura anticipata profilo' USING ERRCODE='23514';
        END IF;
        -- Non ricontrollare is_active su uno storico legittimo da chiudere.
        RETURN NEW;
    END IF;
    PERFORM 1 FROM taxmanagement.item_tax_classifications
    WHERE id=NEW.item_tax_classification_id AND tenant_id=NEW.tenant_id
      AND country_id=NEW.country_id AND tax_type_id=NEW.tax_type_id AND is_active FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Classificazione incompatibile o inattiva' USING ERRCODE='23514'; END IF;
    PERFORM 1 FROM taxmanagement.tax_types WHERE id=NEW.tax_type_id AND code='VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 2' USING ERRCODE='23514'; END IF;
    PERFORM 1 FROM foundation."user" WHERE id=NEW.created_by AND
        (tenant_id=NEW.tenant_id OR (tenant_id IS NULL AND is_super_admin)) FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Attore profilo fuori tenant' USING ERRCODE='23514'; END IF;
    SELECT coalesce(max(revision),0) INTO previous_revision FROM taxmanagement.item_tax_profiles
    WHERE tenant_id=NEW.tenant_id AND item_id=NEW.item_id;
    IF NEW.revision <> previous_revision+1 THEN
        RAISE EXCEPTION 'Sequenza revisione profilo inattesa' USING ERRCODE='23514';
    END IF;
    NEW.created_at := transaction_timestamp();
    RETURN NEW;
END $$;
CREATE TRIGGER item_classifications_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.item_tax_classifications
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_classification();
CREATE TRIGGER item_profiles_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.item_tax_profiles
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_item_tax_profile();
REVOKE ALL ON taxmanagement.item_tax_classifications,taxmanagement.item_tax_profiles FROM PUBLIC,enginia360_app;
GRANT SELECT,INSERT,UPDATE ON taxmanagement.item_tax_classifications TO enginia360_app;
GRANT SELECT,INSERT ON taxmanagement.item_tax_profiles TO enginia360_app;
GRANT UPDATE(valid_to) ON taxmanagement.item_tax_profiles TO enginia360_app;

CREATE FUNCTION taxmanagement.guard_partner_tax_profile() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE previous_revision bigint;
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Profilo fiscale immutabile' USING ERRCODE='23514'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended('tax-profile:partner:' || NEW.tenant_id::text || ':' || NEW.business_partner_id::text,0));
    PERFORM 1 FROM masterdata.business_partner WHERE tenant_id=NEW.tenant_id AND id=NEW.business_partner_id FOR KEY SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Soggetto profilo fuori tenant o mancante' USING ERRCODE='23503'; END IF;
    IF TG_OP='UPDATE' THEN
        IF (to_jsonb(NEW)-'valid_to') IS DISTINCT FROM (to_jsonb(OLD)-'valid_to') THEN
            RAISE EXCEPTION 'Payload profilo fiscale immutabile' USING ERRCODE='23514';
        END IF;
        IF NEW.valid_to IS DISTINCT FROM OLD.valid_to AND
           (NEW.valid_to IS NULL OR (OLD.valid_to IS NOT NULL AND NEW.valid_to>OLD.valid_to)) THEN
            RAISE EXCEPTION 'Solo chiusura anticipata profilo' USING ERRCODE='23514';
        END IF;
        -- Non ricontrollare is_active su uno storico legittimo da chiudere.
        RETURN NEW;
    END IF;
    PERFORM 1 FROM taxmanagement.partner_tax_classifications
    WHERE id=NEW.partner_tax_classification_id AND tenant_id=NEW.tenant_id
      AND country_id=NEW.country_id AND tax_type_id=NEW.tax_type_id AND is_active FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Classificazione incompatibile o inattiva' USING ERRCODE='23514'; END IF;
    PERFORM 1 FROM taxmanagement.tax_types WHERE id=NEW.tax_type_id AND code='VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 2' USING ERRCODE='23514'; END IF;
    PERFORM 1 FROM foundation."user" WHERE id=NEW.created_by AND
        (tenant_id=NEW.tenant_id OR (tenant_id IS NULL AND is_super_admin)) FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Attore profilo fuori tenant' USING ERRCODE='23514'; END IF;
    SELECT coalesce(max(revision),0) INTO previous_revision FROM taxmanagement.partner_tax_profiles
    WHERE tenant_id=NEW.tenant_id AND business_partner_id=NEW.business_partner_id;
    IF NEW.revision <> previous_revision+1 THEN
        RAISE EXCEPTION 'Sequenza revisione profilo inattesa' USING ERRCODE='23514';
    END IF;
    NEW.created_at := transaction_timestamp();
    RETURN NEW;
END $$;
CREATE TRIGGER partner_classifications_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.partner_tax_classifications
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_classification();
CREATE TRIGGER partner_profiles_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.partner_tax_profiles
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_partner_tax_profile();
REVOKE ALL ON taxmanagement.partner_tax_classifications,taxmanagement.partner_tax_profiles FROM PUBLIC,enginia360_app;
GRANT SELECT,INSERT,UPDATE ON taxmanagement.partner_tax_classifications TO enginia360_app;
GRANT SELECT,INSERT ON taxmanagement.partner_tax_profiles TO enginia360_app;
GRANT UPDATE(valid_to) ON taxmanagement.partner_tax_profiles TO enginia360_app;

-- Template configurabili, NON regole normative e NON deduzioni da kind/VAT ID.
CREATE FUNCTION taxmanagement.install_item_classification_templates(p_tenant uuid,p_country uuid,p_tax_type uuid) RETURNS integer
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE installed integer;
BEGIN
    PERFORM 1 FROM taxmanagement.tax_types WHERE id=p_tax_type AND code='VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 2' USING ERRCODE='23514'; END IF;
    INSERT INTO taxmanagement.item_tax_classifications(tenant_id,country_id,tax_type_id,code,name)
    SELECT p_tenant,p_country,p_tax_type,v.code,v.name FROM (VALUES
        ('GENERAL_GOODS','Beni generici'),
        ('GENERAL_SERVICES','Servizi generici'),
        ('FOOD','Alimentari'),
        ('BOOKS','Libri'),
        ('MEDICAL_GOODS','Beni medicali'),
        ('DIGITAL_SERVICES','Servizi digitali'),
        ('REPAIR_SERVICES','Riparazioni'),
        ('TRANSPORT_SERVICES','Trasporto'),
        ('INTELLECTUAL_PROPERTY','Proprieta intellettuale'),
        ('ANCILLARY_CHARGES','Oneri accessori')
    ) v(code,name)
    ON CONFLICT (tenant_id,country_id,tax_type_id,lower(code)) DO NOTHING;
    GET DIAGNOSTICS installed = ROW_COUNT;
    RETURN installed;
END $$;
REVOKE ALL ON FUNCTION taxmanagement.install_item_classification_templates(uuid,uuid,uuid) FROM PUBLIC,enginia360_app;
GRANT EXECUTE ON FUNCTION taxmanagement.install_item_classification_templates(uuid,uuid,uuid) TO enginia360_app;

-- Template configurabili, NON regole normative e NON deduzioni da kind/VAT ID.
CREATE FUNCTION taxmanagement.install_partner_classification_templates(p_tenant uuid,p_country uuid,p_tax_type uuid) RETURNS integer
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
DECLARE installed integer;
BEGIN
    PERFORM 1 FROM taxmanagement.tax_types WHERE id=p_tax_type AND code='VAT' AND is_active;
    IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 2' USING ERRCODE='23514'; END IF;
    INSERT INTO taxmanagement.partner_tax_classifications(tenant_id,country_id,tax_type_id,code,name)
    SELECT p_tenant,p_country,p_tax_type,v.code,v.name FROM (VALUES
        ('TAXABLE_PERSON','Soggetto passivo'),
        ('NON_TAXABLE_PERSON','Soggetto non passivo'),
        ('UNKNOWN','Non determinato')
    ) v(code,name)
    ON CONFLICT (tenant_id,country_id,tax_type_id,lower(code)) DO NOTHING;
    GET DIAGNOSTICS installed = ROW_COUNT;
    RETURN installed;
END $$;
REVOKE ALL ON FUNCTION taxmanagement.install_partner_classification_templates(uuid,uuid,uuid) FROM PUBLIC,enginia360_app;
GRANT EXECUTE ON FUNCTION taxmanagement.install_partner_classification_templates(uuid,uuid,uuid) TO enginia360_app;
REVOKE ALL ON FUNCTION taxmanagement.guard_classification_country_identity(),taxmanagement.guard_classification(),
    taxmanagement.guard_item_tax_profile(),taxmanagement.guard_partner_tax_profile() FROM PUBLIC,enginia360_app;

CREATE TABLE taxmanagement.tax_regimes (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
 tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
 code varchar(50) NOT NULL CHECK (btrim(code) <> ''),
 name varchar(150) NOT NULL CHECK (btrim(name) <> ''),
 description text,
 legal_reference text,
 valid_from date NOT NULL CHECK (isfinite(valid_from)),
 valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
 is_active boolean NOT NULL DEFAULT false,
 is_supported boolean NOT NULL DEFAULT false,
 UNIQUE (country_id,tax_type_id,code,valid_from),
 CONSTRAINT tax_regimes_no_overlap EXCLUDE USING gist (
 country_id public.gist_uuid_ops WITH =,tax_type_id public.gist_uuid_ops WITH =,
 code public.gist_text_ops WITH =,daterange(valid_from,valid_to,'[]') WITH &&)
);
CREATE TABLE taxmanagement.company_tax_configurations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 company_id uuid NOT NULL,
 tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
 establishment_country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
 status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','ACTIVE','SUSPENDED')),
 version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 FOREIGN KEY (tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,company_id,tax_type_id),
 tax_code text,
 CONSTRAINT company_tax_configurations_tax_code_check CHECK ((tax_code IS NULL OR ((tax_code ~ '[^[:space:]]'::text) AND (length(tax_code) <= 500))))
);
CREATE TABLE taxmanagement.company_tax_registrations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 company_tax_configuration_id uuid NOT NULL,
 country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
 tax_identifier varchar(30) NOT NULL,
 registration_type text NOT NULL CHECK (registration_type IN ('DOMESTIC','DIRECT_IDENTIFICATION','FISCAL_REPRESENTATIVE')),
 valid_from date NOT NULL CHECK (isfinite(valid_from)),
 valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
 notes text,
 created_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 FOREIGN KEY (tenant_id,company_tax_configuration_id) REFERENCES taxmanagement.company_tax_configurations(tenant_id,id) ON DELETE RESTRICT,
 UNIQUE (tenant_id,id),
 CONSTRAINT company_tax_domestic_no_overlap EXCLUDE USING gist (
 company_tax_configuration_id public.gist_uuid_ops WITH =,
 daterange(valid_from,valid_to,'[]') WITH &&) WHERE (registration_type='DOMESTIC'),
 -- Phase 3 accepts VAT only; root guard fixes tax_type to the single VAT identity.
 CONSTRAINT company_tax_identifier_no_overlap EXCLUDE USING gist (
 tenant_id public.gist_uuid_ops WITH =,country_id public.gist_uuid_ops WITH =,
 tax_identifier public.gist_text_ops WITH =,daterange(valid_from,valid_to,'[]') WITH &&)
);
CREATE INDEX company_tax_registrations_root_idx ON taxmanagement.company_tax_registrations(tenant_id,company_tax_configuration_id,valid_from);
CREATE TABLE taxmanagement.company_tax_regime_profiles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 company_tax_registration_id uuid NOT NULL,
 tax_regime_id uuid NOT NULL REFERENCES taxmanagement.tax_regimes(id) ON DELETE RESTRICT,
 valid_from date NOT NULL CHECK (isfinite(valid_from)),
 valid_to date CHECK (isfinite(valid_to) AND valid_to >= valid_from),
 created_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 FOREIGN KEY (tenant_id,company_tax_registration_id) REFERENCES taxmanagement.company_tax_registrations(tenant_id,id) ON DELETE RESTRICT,
 CONSTRAINT company_tax_regime_profiles_no_overlap EXCLUDE USING gist (
 company_tax_registration_id public.gist_uuid_ops WITH =,daterange(valid_from,valid_to,'[]') WITH &&)
);
CREATE INDEX company_tax_profiles_registration_idx ON taxmanagement.company_tax_regime_profiles(tenant_id,company_tax_registration_id,valid_from);

-- Sola validazione formale canonica; nessuna verifica checksum, VIES o idoneità.
CREATE FUNCTION taxmanagement.company_tax_identifier_valid(p_iso text,p_identifier text) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
 SELECT CASE p_iso WHEN 'IT' THEN p_identifier ~ '^IT[0-9]{11}$'
 WHEN 'DE' THEN p_identifier ~ '^DE[0-9]{9}$'
 WHEN 'FR' THEN p_identifier ~ '^FR[0-9A-HJ-NP-Z]{2}[0-9]{9}$'
 ELSE false END
$$;

CREATE FUNCTION taxmanagement.guard_company_tax_root() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Configurazione fiscale non eliminabile' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (to_jsonb(NEW)-ARRAY['status','version','updated_at','tax_code']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','version','updated_at','tax_code']) THEN
   RAISE EXCEPTION 'Identita configurazione fiscale immutabile' USING ERRCODE='23514'; END IF;
  IF NEW.version<>OLD.version+1 THEN RAISE EXCEPTION 'Incrementare root version esattamente di uno' USING ERRCODE='23514'; END IF;
  IF NEW.status='DRAFT' AND OLD.status<>'DRAFT' THEN RAISE EXCEPTION 'Stato DRAFT non ripristinabile' USING ERRCODE='23514'; END IF;
 ELSE
  IF NEW.version<>1 OR NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'Configurazione iniziale DRAFT versione uno' USING ERRCODE='23514'; END IF;
  PERFORM 1 FROM foundation."user" WHERE id=NEW.created_by AND (tenant_id=NEW.tenant_id OR (tenant_id IS NULL AND is_super_admin));
  IF NOT FOUND THEN RAISE EXCEPTION 'Attore configurazione fuori tenant' USING ERRCODE='23514'; END IF;
  PERFORM 1 FROM foundation.country WHERE id=NEW.establishment_country_id AND is_enabled AND iso_code IN ('IT','DE','FR') FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Paese stabilimento non supportato' USING ERRCODE='23514'; END IF;
  PERFORM 1 FROM taxmanagement.tax_types WHERE id=NEW.tax_type_id AND code='VAT' AND is_active;
  IF NOT FOUND THEN RAISE EXCEPTION 'Solo VAT attiva in fase 3' USING ERRCODE='23514'; END IF;
  NEW.created_at:=transaction_timestamp();
 END IF;
 NEW.updated_at:=transaction_timestamp();
 RETURN NEW;
END $$;
CREATE TRIGGER company_tax_root_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.company_tax_configurations
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_company_tax_root();

CREATE FUNCTION taxmanagement.guard_company_tax_child() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE root taxmanagement.company_tax_configurations%ROWTYPE; reg taxmanagement.company_tax_registrations%ROWTYPE; iso text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Figlio fiscale immutabile' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='company_tax_registrations' THEN
  SELECT * INTO root FROM taxmanagement.company_tax_configurations WHERE tenant_id=NEW.tenant_id AND id=NEW.company_tax_configuration_id FOR UPDATE;
 ELSE
  SELECT * INTO reg FROM taxmanagement.company_tax_registrations WHERE tenant_id=NEW.tenant_id AND id=NEW.company_tax_registration_id;
  SELECT * INTO root FROM taxmanagement.company_tax_configurations WHERE tenant_id=NEW.tenant_id AND id=reg.company_tax_configuration_id FOR UPDATE;
 END IF;
 IF root.id IS NULL THEN RAISE EXCEPTION 'Root fiscale fuori tenant o mancante' USING ERRCODE='23503'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (to_jsonb(NEW)-'valid_to') IS DISTINCT FROM (to_jsonb(OLD)-'valid_to') THEN RAISE EXCEPTION 'Payload figlio fiscale immutabile' USING ERRCODE='23514'; END IF;
  IF NEW.valid_to IS DISTINCT FROM OLD.valid_to AND (NEW.valid_to IS NULL OR (OLD.valid_to IS NOT NULL AND NEW.valid_to>OLD.valid_to)) THEN
   RAISE EXCEPTION 'Solo chiusura anticipata fiscale' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 PERFORM 1 FROM foundation."user" WHERE id=NEW.created_by AND (tenant_id=NEW.tenant_id OR (tenant_id IS NULL AND is_super_admin));
 IF NOT FOUND THEN RAISE EXCEPTION 'Attore figlio fiscale fuori tenant' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='company_tax_registrations' THEN
  SELECT iso_code INTO iso FROM foundation.country WHERE id=NEW.country_id FOR SHARE;
  IF NOT coalesce(taxmanagement.company_tax_identifier_valid(iso,NEW.tax_identifier),false) THEN
   RAISE EXCEPTION 'Identificativo IVA non supportato o non valido' USING ERRCODE='23514'; END IF;
  IF NEW.registration_type='FISCAL_REPRESENTATIVE' AND iso<>'IT' THEN
   RAISE EXCEPTION 'Rappresentante fiscale non supportato per giurisdizione' USING ERRCODE='23514'; END IF;
  IF (NEW.registration_type='DOMESTIC') IS DISTINCT FROM (NEW.country_id=root.establishment_country_id) THEN
   RAISE EXCEPTION 'Tipo registrazione incompatibile con stabilimento IVA' USING ERRCODE='23514'; END IF;
 ELSE
  PERFORM 1 FROM taxmanagement.tax_regimes r JOIN taxmanagement.tax_types t ON t.id=r.tax_type_id
  WHERE r.id=NEW.tax_regime_id AND r.country_id=reg.country_id AND r.tax_type_id=root.tax_type_id
   AND r.is_active AND r.is_supported AND r.code='ORDINARY' AND t.code='VAT' AND t.is_active;
  IF NOT FOUND THEN RAISE EXCEPTION 'Regime incompatibile inattivo o non supportato' USING ERRCODE='23514'; END IF;
 END IF;
 NEW.created_at:=transaction_timestamp();
 RETURN NEW;
END $$;
CREATE TRIGGER company_tax_registration_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.company_tax_registrations
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_company_tax_child();
CREATE TRIGGER company_tax_profile_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.company_tax_regime_profiles
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_company_tax_child();

CREATE FUNCTION taxmanagement.check_company_tax_final_state() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE root_id uuid; root taxmanagement.company_tax_configurations%ROWTYPE; today date := (statement_timestamp() AT TIME ZONE 'UTC')::date;
BEGIN
 IF TG_TABLE_NAME='company_tax_configurations' THEN root_id:=NEW.id;
 ELSIF TG_TABLE_NAME='company_tax_registrations' THEN root_id:=NEW.company_tax_configuration_id;
 ELSE SELECT company_tax_configuration_id INTO root_id FROM taxmanagement.company_tax_registrations WHERE tenant_id=NEW.tenant_id AND id=NEW.company_tax_registration_id;
 END IF;
 SELECT * INTO root FROM taxmanagement.company_tax_configurations WHERE tenant_id=NEW.tenant_id AND id=root_id FOR UPDATE;
 IF EXISTS (SELECT 1 FROM taxmanagement.company_tax_registrations g
  JOIN taxmanagement.company_tax_regime_profiles p ON (p.tenant_id,p.company_tax_registration_id)=(g.tenant_id,g.id)
  JOIN taxmanagement.tax_regimes r ON r.id=p.tax_regime_id
  WHERE g.tenant_id=root.tenant_id AND g.company_tax_configuration_id=root.id AND
   (r.country_id<>g.country_id OR r.tax_type_id<>root.tax_type_id OR
    NOT (daterange(p.valid_from,p.valid_to,'[]') <@ daterange(g.valid_from,g.valid_to,'[]')) OR
    NOT (daterange(p.valid_from,p.valid_to,'[]') <@ daterange(r.valid_from,r.valid_to,'[]')))) THEN
  RAISE EXCEPTION 'Intervallo profilo fuori registrazione o regime' USING ERRCODE='23514'; END IF;
 IF root.status='ACTIVE' THEN
  PERFORM 1 FROM foundation.company WHERE tenant_id=root.tenant_id AND id=root.company_id AND is_enabled FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Company non abilitata per ACTIVE' USING ERRCODE='23514'; END IF;
  IF NOT EXISTS (SELECT 1 FROM taxmanagement.company_tax_registrations g
   JOIN taxmanagement.company_tax_regime_profiles p ON (p.tenant_id,p.company_tax_registration_id)=(g.tenant_id,g.id)
   JOIN taxmanagement.tax_regimes r ON r.id=p.tax_regime_id
   JOIN taxmanagement.tax_types t ON t.id=root.tax_type_id
   WHERE g.tenant_id=root.tenant_id AND g.company_tax_configuration_id=root.id AND r.is_active AND r.is_supported AND t.is_active
    AND daterange(g.valid_from,g.valid_to,'[]') @> today
    AND daterange(p.valid_from,p.valid_to,'[]') @> today
    AND daterange(r.valid_from,r.valid_to,'[]') @> today) THEN
   RAISE EXCEPTION 'ACTIVE richiede copertura fiscale supportata oggi UTC; sospendere prima' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER company_tax_root_final AFTER INSERT OR UPDATE ON taxmanagement.company_tax_configurations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.check_company_tax_final_state();
CREATE CONSTRAINT TRIGGER company_tax_registration_final AFTER INSERT OR UPDATE ON taxmanagement.company_tax_registrations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.check_company_tax_final_state();
CREATE CONSTRAINT TRIGGER company_tax_profile_final AFTER INSERT OR UPDATE ON taxmanagement.company_tax_regime_profiles
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.check_company_tax_final_state();

CREATE FUNCTION taxmanagement.guard_company_tax_country() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF NEW.iso_code IS DISTINCT FROM OLD.iso_code AND (
 EXISTS (SELECT 1 FROM taxmanagement.tax_regimes WHERE country_id=OLD.id) OR
 EXISTS (SELECT 1 FROM taxmanagement.company_tax_configurations WHERE establishment_country_id=OLD.id) OR
 EXISTS (SELECT 1 FROM taxmanagement.company_tax_registrations WHERE country_id=OLD.id)) THEN
 RAISE EXCEPTION 'Identita paese Company Tax immutabile' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER company_tax_country_identity BEFORE UPDATE OF iso_code ON foundation.country
FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_company_tax_country();

-- Solo geografia esistente: nessun dato società/tenant o decorrenza normativa implicita.
INSERT INTO taxmanagement.tax_regimes(country_id,tax_type_id,code,name,description,legal_reference,valid_from,is_active,is_supported)
SELECT c.id,t.id,'ORDINARY','Ordinary VAT regime',
 'Supported implementation snapshot; identifier format is not proof of VAT registration.',
 NULL,
 DATE '2026-11-26',true,true
FROM foundation.country c CROSS JOIN taxmanagement.tax_types t WHERE c.iso_code IN ('IT','DE','FR') AND t.code='VAT';
CREATE TRIGGER tax_regimes_immutable BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_regimes
FOR EACH ROW EXECUTE FUNCTION taxmanagement.reject_mutation();
REVOKE ALL ON taxmanagement.tax_regimes,taxmanagement.company_tax_configurations,taxmanagement.company_tax_registrations,taxmanagement.company_tax_regime_profiles FROM PUBLIC,enginia360_app;
GRANT SELECT ON taxmanagement.tax_regimes TO enginia360_app;
GRANT SELECT,INSERT,UPDATE ON taxmanagement.company_tax_configurations TO enginia360_app;
GRANT SELECT,INSERT ON taxmanagement.company_tax_registrations,taxmanagement.company_tax_regime_profiles TO enginia360_app;
GRANT UPDATE(valid_to) ON taxmanagement.company_tax_registrations,taxmanagement.company_tax_regime_profiles TO enginia360_app;
REVOKE ALL ON FUNCTION taxmanagement.guard_company_tax_root(),taxmanagement.guard_company_tax_child(),taxmanagement.check_company_tax_final_state(),taxmanagement.guard_company_tax_country(),taxmanagement.company_tax_identifier_valid(text,text) FROM PUBLIC,enginia360_app;
GRANT EXECUTE ON FUNCTION taxmanagement.company_tax_identifier_valid(text,text) TO enginia360_app;
COMMENT ON TABLE taxmanagement.company_tax_configurations IS 'Company VAT establishment explicit; root optimistic version advanced exactly once by application command. ACTIVE is not perpetual coverage.';
COMMENT ON TABLE taxmanagement.company_tax_registrations IS 'Canonical prefixed identifier; finite IT/DE/FR formal-only policy, no checksum/VIES/eligibility claim. Shared group VAT identifiers explicitly outside Phase 3.';

COMMENT ON COLUMN taxmanagement.company_tax_configurations.tax_code IS 'Codice fiscale facoltativo della configurazione fiscale; massimo 500 caratteri, normalizzazione esterna applicativa; nessuna inferenza IVA.';


CREATE FUNCTION taxmanagement.require_company_tax_initial_chain() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 -- Leggere le righe correnti, non l'immagine INSERT: conta lo stato finale.
 PERFORM 1 FROM taxmanagement.company_tax_configurations
 WHERE tenant_id=NEW.tenant_id AND id=NEW.id FOR UPDATE;
 IF NOT EXISTS (SELECT 1 FROM taxmanagement.company_tax_registrations g
  WHERE g.tenant_id=NEW.tenant_id AND g.company_tax_configuration_id=NEW.id) THEN
  RAISE EXCEPTION 'Nuova configurazione richiede almeno una registrazione iniziale' USING ERRCODE='23514';
 END IF;
 IF EXISTS (SELECT 1 FROM taxmanagement.company_tax_registrations g
  WHERE g.tenant_id=NEW.tenant_id AND g.company_tax_configuration_id=NEW.id
  AND NOT EXISTS (SELECT 1 FROM taxmanagement.company_tax_regime_profiles p
   WHERE p.tenant_id=g.tenant_id AND p.company_tax_registration_id=g.id)) THEN
  RAISE EXCEPTION 'Ogni registrazione iniziale richiede almeno un profilo di regime' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER company_tax_root_require_initial_chain
 AFTER INSERT ON taxmanagement.company_tax_configurations
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
 EXECUTE FUNCTION taxmanagement.require_company_tax_initial_chain();
REVOKE ALL ON FUNCTION taxmanagement.require_company_tax_initial_chain() FROM PUBLIC,enginia360_app;


CREATE FUNCTION taxmanagement.require_company_tax_registration_initial_profile() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 -- Stessa serializzazione dei guard figli; la revisione resta application-owned.
 PERFORM 1 FROM taxmanagement.company_tax_configurations
 WHERE tenant_id=NEW.tenant_id AND id=NEW.company_tax_configuration_id FOR UPDATE;
 -- Stato finale corrente, non immagine INSERT e nessun controllo retroattivo.
 IF NOT EXISTS (SELECT 1 FROM taxmanagement.company_tax_regime_profiles p
  WHERE p.tenant_id=NEW.tenant_id AND p.company_tax_registration_id=NEW.id) THEN
  RAISE EXCEPTION 'Nuova registrazione richiede almeno un profilo di regime iniziale' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER company_tax_registration_require_initial_profile
 AFTER INSERT ON taxmanagement.company_tax_registrations
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
 EXECUTE FUNCTION taxmanagement.require_company_tax_registration_initial_profile();
REVOKE ALL ON FUNCTION taxmanagement.require_company_tax_registration_initial_profile() FROM PUBLIC,enginia360_app;

CREATE TABLE taxmanagement.tax_rules (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 company_id uuid,
 country_id uuid NOT NULL REFERENCES foundation.country(id) ON DELETE RESTRICT,
 tax_type_id uuid NOT NULL REFERENCES taxmanagement.tax_types(id) ON DELETE RESTRICT,
 code varchar(50) NOT NULL CHECK (code ~ '[^[:space:]]'),
 name varchar(150) NOT NULL CHECK (name ~ '[^[:space:]]'),
 description text,
 version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX tax_rules_code_key ON taxmanagement.tax_rules(tenant_id,company_id,country_id,tax_type_id,lower(code)) NULLS NOT DISTINCT;
CREATE TABLE taxmanagement.tax_rule_versions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 tax_rule_id uuid NOT NULL,
 version_number integer NOT NULL CHECK(version_number>=1),
 tax_code_id uuid NOT NULL,
 priority integer NOT NULL DEFAULT 100,
 operation_type text NOT NULL CHECK(operation_type IN ('SALE','PURCHASE')),
 status text NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','PUBLISHED','WITHDRAWN')),
 legal_reference varchar(255) NOT NULL CHECK(legal_reference ~ '[^[:space:]]'),
 valid_from date NOT NULL CHECK(isfinite(valid_from)),
 valid_to date CHECK(isfinite(valid_to) AND valid_to>=valid_from),
 created_at timestamptz NOT NULL DEFAULT now(),
 created_by uuid NOT NULL REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 published_at timestamptz, published_by uuid REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 withdrawn_at timestamptz, withdrawn_by uuid REFERENCES foundation."user"(id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,tax_rule_id) REFERENCES taxmanagement.tax_rules(tenant_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,tax_code_id) REFERENCES taxmanagement.tax_codes(tenant_id,id) ON DELETE RESTRICT,
 UNIQUE(tenant_id,id), UNIQUE(tax_rule_id,version_number),
 CHECK ((status='DRAFT' AND published_at IS NULL AND published_by IS NULL AND withdrawn_at IS NULL AND withdrawn_by IS NULL)
 OR (status='PUBLISHED' AND published_at IS NOT NULL AND published_by IS NOT NULL AND withdrawn_at IS NULL AND withdrawn_by IS NULL)
 OR (status='WITHDRAWN' AND published_at IS NOT NULL AND published_by IS NOT NULL AND withdrawn_at IS NOT NULL AND withdrawn_by IS NOT NULL AND withdrawn_at>=published_at)),
 CONSTRAINT tax_rule_versions_no_overlap EXCLUDE USING gist (
 tax_rule_id public.gist_uuid_ops WITH =,daterange(valid_from,valid_to,'[]') WITH &&) WHERE (status='PUBLISHED')
);
CREATE INDEX tax_rule_versions_candidates ON taxmanagement.tax_rule_versions(tenant_id,operation_type,status,priority,valid_from);
CREATE TABLE taxmanagement.tax_rule_conditions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
 tax_rule_version_id uuid NOT NULL,
 field varchar(80) NOT NULL,
 operator text NOT NULL CHECK(operator IN ('EQUALS','NOT_EQUALS','IN','NOT_IN','IS_TRUE','IS_FALSE')),
 value jsonb NOT NULL,
 FOREIGN KEY(tenant_id,tax_rule_version_id) REFERENCES taxmanagement.tax_rule_versions(tenant_id,id) ON DELETE RESTRICT,
 UNIQUE(tax_rule_version_id,field,operator,value)
);

-- Registro finito, senza una quarta tabella né percorsi JSON arbitrari.
CREATE FUNCTION taxmanagement.tax_rule_field_spec(p_field text) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT CASE
 WHEN p_field IN ('company.registrationCountry','company.establishmentCountry','partner.taxIdentifierCountry',
 'transaction.dispatchCountry','transaction.destinationCountry','transaction.serviceLocationCountry',
 'transaction.placeOfSupply','partner.establishmentCountry') THEN '{"type":"REFERENCE","reference":"countries","available":true}'::jsonb
 WHEN p_field='company.taxRegime' THEN '{"type":"REFERENCE","reference":"regimes","available":true}'::jsonb
 WHEN p_field='partner.taxClassification' THEN '{"type":"REFERENCE","reference":"partnerClassifications","available":true}'::jsonb
 WHEN p_field='item.taxClassification' THEN '{"type":"REFERENCE","reference":"itemClassifications","available":true}'::jsonb
 WHEN p_field IN ('partner.actingAsTaxablePerson','transaction.ordinaryVatTerritoryConfirmed') THEN '{"type":"BOOLEAN","available":true,"values":[true,false]}'::jsonb
 WHEN p_field='item.nature' THEN '{"type":"ENUM","available":true,"values":["GOOD","INTANGIBLE","SERVICE","CHARGE"]}'::jsonb
 WHEN p_field='transaction.operationType' THEN '{"type":"ENUM","available":true,"values":["SALE","PURCHASE"]}'::jsonb
 WHEN p_field='transaction.territorialScope' THEN '{"type":"ENUM","available":true,"values":["DOMESTIC","INTRA_EU","EXTRA_EU"]}'::jsonb
 WHEN p_field='transaction.operationCategory' THEN '{"type":"ENUM","available":true,"values":["ORDINARY_MOVABLE_GOODS","GENERAL_SERVICES"]}'::jsonb
 WHEN p_field='transaction.specialTaxTreatment' THEN '{"type":"ENUM","available":true,"values":["NONE","REVERSE_CHARGE","SPLIT_PAYMENT","EXEMPT","MARGIN","OTHER"]}'::jsonb
 WHEN p_field='transaction.goodsCustomsStatus' THEN '{"type":"ENUM","available":true,"values":["NATIONAL_OR_UNION","OTHER"]}'::jsonb
 WHEN p_field='partner.vatValidationStatus' THEN '{"type":"ENUM","available":false,"values":["VALID","INVALID"]}'::jsonb
 END
$$;
CREATE FUNCTION taxmanagement.tax_rule_lock_key(p_tenant uuid,p_country uuid,p_type uuid,p_operation text) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
 SELECT hashtextextended('tax-determination:rules:'||p_tenant::text||':'||p_country::text||':'||p_type::text||':'||p_operation,0)
$$;
CREATE FUNCTION taxmanagement.tax_rule_condition_accepts(p_operator text,p_value jsonb,p_candidate jsonb) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT SET search_path=pg_catalog AS $$
 SELECT CASE p_operator WHEN 'EQUALS' THEN p_candidate=p_value WHEN 'NOT_EQUALS' THEN p_candidate<>p_value
 WHEN 'IN' THEN p_value @> jsonb_build_array(p_candidate) WHEN 'NOT_IN' THEN NOT p_value @> jsonb_build_array(p_candidate)
 WHEN 'IS_TRUE' THEN p_candidate='true'::jsonb WHEN 'IS_FALSE' THEN p_candidate='false'::jsonb ELSE false END
$$;
-- Intersezione esatta sugli stessi campi; nessuna correlazione inventata.
-- Per UUID bastano tutti i punti nominati ed un punto simbolico "altro";
-- per enum/bool si enumera l'intero dominio finito. Ogni versione ha al massimo
-- 100 condizioni e ciascun insieme contiene al massimo 100 valori.
CREATE FUNCTION taxmanagement.tax_rule_conditions_overlap(p_left uuid,p_right uuid) RETURNS boolean
LANGUAGE plpgsql STABLE SET search_path=pg_catalog AS $$
DECLARE f text; spec jsonb; candidates jsonb; possible boolean;
BEGIN
 FOR f IN SELECT DISTINCT field FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id IN (p_left,p_right) LOOP
  spec:=taxmanagement.tax_rule_field_spec(f);
  IF spec->>'type'='REFERENCE' THEN
   SELECT coalesce(jsonb_agg(DISTINCT v),'[]'::jsonb)||'["__other_uuid__"]'::jsonb INTO candidates
   FROM taxmanagement.tax_rule_conditions c CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN c.operator IN ('IN','NOT_IN') THEN c.value ELSE jsonb_build_array(c.value) END) v
   WHERE c.tax_rule_version_id IN (p_left,p_right) AND c.field=f;
  ELSE candidates:=spec->'values'; END IF;
  SELECT EXISTS (SELECT 1 FROM jsonb_array_elements(candidates) x WHERE NOT EXISTS (
   SELECT 1 FROM taxmanagement.tax_rule_conditions c
   WHERE c.tax_rule_version_id IN (p_left,p_right) AND c.field=f
   AND NOT taxmanagement.tax_rule_condition_accepts(c.operator,c.value,x))) INTO possible;
  IF NOT possible THEN RETURN false; END IF;
 END LOOP;
 RETURN true;
END $$;

CREATE FUNCTION taxmanagement.guard_tax_rule_root() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Regola non eliminabile' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' THEN
  IF (to_jsonb(NEW)-ARRAY['name','description','version','updated_at']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['name','description','version','updated_at']) THEN
   RAISE EXCEPTION 'Identita regola immutabile' USING ERRCODE='23514'; END IF;
  IF NEW.version<>OLD.version+1 THEN RAISE EXCEPTION 'Incrementare root version esattamente di uno' USING ERRCODE='23514'; END IF;
 ELSE
  IF NEW.version<>1 THEN RAISE EXCEPTION 'Versione iniziale uno' USING ERRCODE='23514'; END IF;
  NEW.created_at:=transaction_timestamp();
 END IF;
 NEW.updated_at:=transaction_timestamp();
 RETURN NEW;
END $$;

CREATE FUNCTION taxmanagement.tax_rule_check_condition(p_tenant uuid,p_rule uuid,p_field text,p_operator text,p_value jsonb,p_publish boolean DEFAULT false) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE spec jsonb; vals jsonb; v jsonb; ident uuid; r taxmanagement.tax_rules%ROWTYPE;
BEGIN
 spec:=taxmanagement.tax_rule_field_spec(p_field);
 IF spec IS NULL OR p_value IS NULL THEN RAISE EXCEPTION 'Campo condizione sconosciuto' USING ERRCODE='23514'; END IF;
 IF p_publish AND NOT (spec->>'available')::boolean THEN RAISE EXCEPTION 'Campo condizione non disponibile' USING ERRCODE='23514'; END IF;
 IF spec->>'type'='BOOLEAN' THEN
  IF p_operator IN ('IS_TRUE','IS_FALSE') THEN
   IF p_value<>'null'::jsonb THEN RAISE EXCEPTION 'Boolean IS richiede JSON null' USING ERRCODE='23514'; END IF;
   RETURN;
  END IF;
  IF p_operator NOT IN ('EQUALS','NOT_EQUALS') OR jsonb_typeof(p_value)<>'boolean' THEN RAISE EXCEPTION 'Condizione boolean tipizzata non valida' USING ERRCODE='23514'; END IF;
  RETURN;
 END IF;
 IF p_operator NOT IN ('EQUALS','NOT_EQUALS','IN','NOT_IN') THEN RAISE EXCEPTION 'Operatore condizione incompatibile' USING ERRCODE='23514'; END IF;
 IF p_operator IN ('IN','NOT_IN') THEN
  IF jsonb_typeof(p_value)<>'array' THEN RAISE EXCEPTION 'Condizione IN richiede array' USING ERRCODE='23514'; END IF;
  IF jsonb_array_length(p_value) NOT BETWEEN 1 AND 100 OR
   (SELECT count(*)<>count(DISTINCT x) FROM jsonb_array_elements(p_value) x) THEN RAISE EXCEPTION 'Array condizione vuoto, duplicato o oltre limite' USING ERRCODE='23514'; END IF;
  IF spec->>'type'='REFERENCE' AND (SELECT count(*)<>count(DISTINCT lower(x#>>'{}')) FROM jsonb_array_elements(p_value) x) THEN
   RAISE EXCEPTION 'Array UUID condizione duplicato' USING ERRCODE='23514'; END IF;
  vals:=p_value;
 ELSE vals:=jsonb_build_array(p_value); END IF;
 SELECT * INTO STRICT r FROM taxmanagement.tax_rules WHERE tenant_id=p_tenant AND id=p_rule;
 FOR v IN SELECT x FROM jsonb_array_elements(vals) x LOOP
  IF jsonb_typeof(v)<>'string' THEN RAISE EXCEPTION 'Valore condizione deve essere stringa' USING ERRCODE='23514'; END IF;
  IF spec->>'type'='ENUM' THEN
   IF NOT (spec->'values') @> jsonb_build_array(v) THEN RAISE EXCEPTION 'Enum condizione sconosciuto' USING ERRCODE='23514'; END IF;
  ELSE
   IF (v#>>'{}') !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$' THEN RAISE EXCEPTION 'UUID condizione malformato' USING ERRCODE='23514'; END IF;
   ident:=(v#>>'{}')::uuid;
   CASE spec->>'reference'
    WHEN 'countries' THEN
     PERFORM 1 FROM foundation.country WHERE id=ident AND (NOT p_publish OR is_enabled) FOR SHARE;
    WHEN 'regimes' THEN
     PERFORM 1 FROM taxmanagement.tax_regimes WHERE id=ident AND country_id=r.country_id AND tax_type_id=r.tax_type_id AND (NOT p_publish OR (is_active AND is_supported));
    WHEN 'itemClassifications' THEN
     PERFORM 1 FROM taxmanagement.item_tax_classifications WHERE id=ident AND tenant_id=r.tenant_id AND country_id=r.country_id AND tax_type_id=r.tax_type_id AND (NOT p_publish OR is_active) FOR SHARE;
    WHEN 'partnerClassifications' THEN
     PERFORM 1 FROM taxmanagement.partner_tax_classifications WHERE id=ident AND tenant_id=r.tenant_id AND country_id=r.country_id AND tax_type_id=r.tax_type_id AND (NOT p_publish OR is_active) FOR SHARE;
   END CASE;
   IF NOT FOUND THEN RAISE EXCEPTION 'Riferimento condizione fuori ambito o mancante' USING ERRCODE='23514'; END IF;
  END IF;
 END LOOP;
END $$;

CREATE FUNCTION taxmanagement.guard_tax_rule_condition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE v taxmanagement.tax_rule_versions%ROWTYPE;
BEGIN
 SELECT * INTO STRICT v FROM taxmanagement.tax_rule_versions
 WHERE id=CASE WHEN TG_OP='DELETE' THEN OLD.tax_rule_version_id ELSE NEW.tax_rule_version_id END
 AND tenant_id=CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END FOR UPDATE;
 PERFORM 1 FROM taxmanagement.tax_rules WHERE id=v.tax_rule_id AND tenant_id=v.tenant_id FOR UPDATE;
 IF v.status<>'DRAFT' THEN RAISE EXCEPTION 'Condizioni pubblicate o ritirate immutabili' USING ERRCODE='23514'; END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF TG_OP='UPDATE' AND (NEW.id,NEW.tenant_id,NEW.tax_rule_version_id) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.tax_rule_version_id) THEN
  RAISE EXCEPTION 'Identita condizione immutabile' USING ERRCODE='23514'; END IF;
 PERFORM taxmanagement.tax_rule_check_condition(v.tenant_id,v.tax_rule_id,NEW.field,NEW.operator,NEW.value);
 -- UUID validati prima della conversione; la forma canonica evita falsi conflitti
 -- o falsi disgiunti dovuti esclusivamente alle maiuscole della rappresentazione.
 IF taxmanagement.tax_rule_field_spec(NEW.field)->>'type'='REFERENCE' THEN
  IF NEW.operator IN ('IN','NOT_IN') THEN
   SELECT jsonb_agg(to_jsonb((x#>>'{}')::uuid::text) ORDER BY ord) INTO NEW.value
   FROM jsonb_array_elements(NEW.value) WITH ORDINALITY a(x,ord);
  ELSE NEW.value:=to_jsonb((NEW.value#>>'{}')::uuid::text); END IF;
 END IF;
 IF TG_OP='INSERT' AND (SELECT count(*) FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id=v.id)>=100 THEN
  RAISE EXCEPTION 'Massimo 100 condizioni' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION taxmanagement.guard_tax_rule_version() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE r taxmanagement.tax_rules%ROWTYPE; n integer; c record; actor uuid;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Versione regola non eliminabile' USING ERRCODE='23514'; END IF;
 SELECT * INTO STRICT r FROM taxmanagement.tax_rules WHERE id=NEW.tax_rule_id AND tenant_id=NEW.tenant_id;
 -- Il controllo fra radici richiede snapshot fresco dopo il lock normativo.
 -- Un vecchio snapshot REPEATABLE READ non puo aggirare il controllo conflitti.
 IF current_setting('transaction_isolation')<>'read committed' THEN
  RAISE EXCEPTION 'TaxDetermination richiede READ COMMITTED' USING ERRCODE='25001'; END IF;
 -- Pubblicazione/ritiro/chiusura serializzano PRIMA del lock radice.
 -- DRAFT non e visibile al ruleset: non acquisire qui un lock normativo
 -- dopo quello root gia posseduto dall'editor, evitando l'inversione writer.
 IF TG_OP='UPDATE' AND (OLD.status='PUBLISHED' OR NEW.status='PUBLISHED') THEN
  PERFORM pg_advisory_xact_lock(taxmanagement.tax_rule_lock_key(r.tenant_id,r.country_id,r.tax_type_id,NEW.operation_type));
 END IF;
 PERFORM 1 FROM taxmanagement.tax_rules WHERE id=r.id FOR UPDATE;
 IF TG_OP='INSERT' THEN
  SELECT coalesce(max(version_number),0)+1 INTO n FROM taxmanagement.tax_rule_versions WHERE tax_rule_id=r.id;
  IF NEW.status<>'DRAFT' OR NEW.version_number<>n OR NEW.published_at IS NOT NULL OR NEW.published_by IS NOT NULL OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by IS NOT NULL THEN
   RAISE EXCEPTION 'Nuova versione DRAFT con numero sequenziale' USING ERRCODE='23514'; END IF;
  NEW.created_at:=transaction_timestamp(); actor:=NEW.created_by;
 ELSE
  IF (NEW.id,NEW.tenant_id,NEW.tax_rule_id,NEW.version_number,NEW.created_at,NEW.created_by) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.tax_rule_id,OLD.version_number,OLD.created_at,OLD.created_by) THEN
   RAISE EXCEPTION 'Identita versione immutabile' USING ERRCODE='23514'; END IF;
  IF OLD.status='WITHDRAWN' THEN RAISE EXCEPTION 'Versione ritirata immutabile' USING ERRCODE='23514'; END IF;
  IF OLD.status='PUBLISHED' THEN
   IF NEW.status='WITHDRAWN' THEN
    IF (to_jsonb(NEW)-ARRAY['status','withdrawn_at','withdrawn_by']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','withdrawn_at','withdrawn_by']) THEN
     RAISE EXCEPTION 'Ritiro conserva payload e pubblicazione' USING ERRCODE='23514'; END IF;
    NEW.withdrawn_at:=transaction_timestamp(); actor:=NEW.withdrawn_by;
   ELSIF NEW.status='PUBLISHED' THEN
    IF (to_jsonb(NEW)-'valid_to') IS DISTINCT FROM (to_jsonb(OLD)-'valid_to') OR NEW.valid_to IS NULL OR NEW.valid_to<OLD.valid_from OR
     (OLD.valid_to IS NOT NULL AND NEW.valid_to>=OLD.valid_to) OR NOT EXISTS (
      SELECT 1 FROM taxmanagement.tax_rule_versions s WHERE s.tax_rule_id=r.id AND s.status='DRAFT' AND s.id<>OLD.id AND s.valid_from=NEW.valid_to+1 AND s.valid_from>OLD.valid_from AND (OLD.valid_to IS NULL OR s.valid_from<=OLD.valid_to)) THEN
     RAISE EXCEPTION 'Solo chiusura controllata predecessore pubblicato' USING ERRCODE='23514'; END IF;
    RETURN NEW;
   ELSE RAISE EXCEPTION 'Transizione pubblicata non valida' USING ERRCODE='23514'; END IF;
  ELSIF NEW.status='PUBLISHED' THEN
   IF (to_jsonb(NEW)-ARRAY['status','published_at','published_by']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','published_at','published_by']) THEN
    RAISE EXCEPTION 'Pubblicazione non modifica payload DRAFT' USING ERRCODE='23514'; END IF;
   NEW.published_at:=transaction_timestamp(); actor:=NEW.published_by;
  ELSIF NEW.status<>'DRAFT' THEN RAISE EXCEPTION 'Transizione DRAFT non valida' USING ERRCODE='23514';
  ELSIF NEW.published_at IS NOT NULL OR NEW.published_by IS NOT NULL OR NEW.withdrawn_at IS NOT NULL OR NEW.withdrawn_by IS NOT NULL THEN
   RAISE EXCEPTION 'Metadati ciclo vita DRAFT non validi' USING ERRCODE='23514'; END IF;
 END IF;
 IF actor IS NOT NULL THEN
  PERFORM 1 FROM foundation."user" WHERE id=actor AND (tenant_id=r.tenant_id OR (tenant_id IS NULL AND is_super_admin)) FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Attore regola fuori tenant' USING ERRCODE='23514'; END IF;
 END IF;
 PERFORM 1 FROM taxmanagement.tax_codes WHERE id=NEW.tax_code_id AND tenant_id=r.tenant_id AND country_id=r.country_id AND tax_type_id=r.tax_type_id AND (NEW.status<>'PUBLISHED' OR is_active) FOR SHARE;
 IF NOT FOUND THEN RAISE EXCEPTION 'TaxCode regola fuori ambito o inattivo' USING ERRCODE='23514'; END IF;
 IF NEW.status='PUBLISHED' THEN
  PERFORM 1 FROM foundation.country WHERE id=r.country_id AND is_enabled FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Paese regola non disponibile' USING ERRCODE='23514'; END IF;
  PERFORM 1 FROM taxmanagement.tax_types WHERE id=r.tax_type_id AND code='VAT' AND is_active;
  IF NOT FOUND THEN RAISE EXCEPTION 'Tipo regola non supportato' USING ERRCODE='23514'; END IF;
  FOR c IN SELECT * FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id=NEW.id LOOP
   PERFORM taxmanagement.tax_rule_check_condition(r.tenant_id,r.id,c.field,c.operator,c.value,true);
  END LOOP;
  IF NOT taxmanagement.tax_rule_conditions_overlap(NEW.id,NEW.id) THEN RAISE EXCEPTION 'Condizioni contraddittorie' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM taxmanagement.tax_rule_versions v JOIN taxmanagement.tax_rules q ON q.id=v.tax_rule_id
   WHERE v.id<>NEW.id AND v.status='PUBLISHED' AND q.tenant_id=r.tenant_id AND q.country_id=r.country_id AND q.tax_type_id=r.tax_type_id
   AND (q.company_id IS NULL OR r.company_id IS NULL OR q.company_id=r.company_id)
   AND v.operation_type=NEW.operation_type AND v.priority=NEW.priority
   AND daterange(v.valid_from,v.valid_to,'[]') && daterange(NEW.valid_from,NEW.valid_to,'[]')
   AND taxmanagement.tax_rule_conditions_overlap(NEW.id,v.id)) THEN
   RAISE EXCEPTION 'Conflitto conservativo regole stessa priorita' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;

-- Una chiusura anticipata non puo essere committata da sola: il successore
-- deve essere davvero pubblicato nello stato finale della stessa transazione.
CREATE FUNCTION taxmanagement.guard_tax_rule_closure_final() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF OLD.status='PUBLISHED' AND NEW.status='PUBLISHED' AND NEW.valid_to IS DISTINCT FROM OLD.valid_to AND NOT EXISTS (
  SELECT 1 FROM taxmanagement.tax_rule_versions s WHERE s.tax_rule_id=NEW.tax_rule_id AND s.id<>NEW.id AND s.status='PUBLISHED' AND s.valid_from=NEW.valid_to+1) THEN
  RAISE EXCEPTION 'Chiusura predecessore richiede successore pubblicato' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;
CREATE FUNCTION taxmanagement.guard_determination_country() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' OR NEW.id IS DISTINCT FROM OLD.id OR NEW.iso_code IS DISTINCT FROM OLD.iso_code THEN
  IF EXISTS (SELECT 1 FROM taxmanagement.tax_rule_conditions c WHERE
   taxmanagement.tax_rule_field_spec(c.field)->>'reference'='countries' AND
   (c.value=to_jsonb(OLD.id::text) OR c.value @> jsonb_build_array(OLD.id::text))) THEN
   RAISE EXCEPTION 'Identita paese richiamata dalle condizioni immutabile' USING ERRCODE='23514'; END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
CREATE TRIGGER tax_rules_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_rules FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_rule_root();
CREATE TRIGGER tax_rule_versions_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_rule_versions FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_rule_version();
CREATE TRIGGER tax_rule_conditions_guard BEFORE INSERT OR UPDATE OR DELETE ON taxmanagement.tax_rule_conditions FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_rule_condition();
CREATE CONSTRAINT TRIGGER tax_rule_closure_final AFTER UPDATE ON taxmanagement.tax_rule_versions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_tax_rule_closure_final();
CREATE TRIGGER tax_determination_country_guard BEFORE UPDATE OF id,iso_code OR DELETE ON foundation.country FOR EACH ROW EXECUTE FUNCTION taxmanagement.guard_determination_country();
REVOKE ALL ON taxmanagement.tax_rules,taxmanagement.tax_rule_versions,taxmanagement.tax_rule_conditions FROM PUBLIC,enginia360_app;
GRANT SELECT,INSERT,UPDATE ON taxmanagement.tax_rules,taxmanagement.tax_rule_versions TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON taxmanagement.tax_rule_conditions TO enginia360_app;
REVOKE ALL ON FUNCTION taxmanagement.guard_tax_rule_root(),taxmanagement.guard_tax_rule_version(),taxmanagement.guard_tax_rule_condition(),taxmanagement.guard_tax_rule_closure_final(),taxmanagement.guard_determination_country() FROM PUBLIC,enginia360_app;
REVOKE ALL ON FUNCTION taxmanagement.tax_rule_field_spec(text),taxmanagement.tax_rule_lock_key(uuid,uuid,uuid,text),taxmanagement.tax_rule_condition_accepts(text,jsonb,jsonb),taxmanagement.tax_rule_conditions_overlap(uuid,uuid),taxmanagement.tax_rule_check_condition(uuid,uuid,text,text,jsonb,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION taxmanagement.tax_rule_field_spec(text),taxmanagement.tax_rule_lock_key(uuid,uuid,uuid,text),taxmanagement.tax_rule_condition_accepts(text,jsonb,jsonb),taxmanagement.tax_rule_conditions_overlap(uuid,uuid),taxmanagement.tax_rule_check_condition(uuid,uuid,text,text,jsonb,boolean) TO enginia360_app;
