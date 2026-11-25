-- Catalogo: definizioni finali per una nuova installazione, senza tenant o associazioni precreati.
-- UOM riutilizzabili: DDL in foundation.sql, stesso namespace masterdata e API tenant.
-- Numerazione condivisa: kernel finale in foundation.sql. Nessuna fase storica richiesta.

CREATE TABLE masterdata.catalog_category (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    code text CHECK (code IS NULL OR length(btrim(code)) BETWEEN 1 AND 30),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    description text CHECK (length(description)<=2000), parent_id uuid,
    sort_order integer NOT NULL DEFAULT 0, is_active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,id), CHECK (parent_id IS DISTINCT FROM id),
    FOREIGN KEY(tenant_id,parent_id) REFERENCES masterdata.catalog_category(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX catalog_category_code_unique ON masterdata.catalog_category(tenant_id,lower(code)) WHERE code IS NOT NULL;
CREATE INDEX catalog_category_parent_idx ON masterdata.catalog_category(tenant_id,parent_id);
CREATE TABLE masterdata.catalog_item_type (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    code text CHECK (code IS NULL OR length(btrim(code)) BETWEEN 1 AND 30),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    kind text NOT NULL CHECK (kind IN ('GOOD','INTANGIBLE','SERVICE','CHARGE')),
    default_sellable boolean NOT NULL DEFAULT true, default_purchasable boolean NOT NULL DEFAULT true,
    default_track_stock boolean NOT NULL DEFAULT false, is_active boolean NOT NULL DEFAULT true,
    version bigint NOT NULL DEFAULT 1 CHECK (version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,id), CHECK (kind='GOOD' OR NOT default_track_stock)
);
CREATE UNIQUE INDEX catalog_type_code_unique ON masterdata.catalog_item_type(tenant_id,lower(code)) WHERE code IS NOT NULL;

CREATE TABLE masterdata.catalog_brand (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 200),
    code text CHECK(code IS NULL OR length(btrim(code)) BETWEEN 1 AND 30), description text CHECK(length(description)<=2000),
    is_active boolean NOT NULL DEFAULT true, version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id)
);
CREATE UNIQUE INDEX catalog_brand_code_unique ON masterdata.catalog_brand(tenant_id,lower(code)) WHERE code IS NOT NULL;
CREATE TABLE masterdata.catalog_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL REFERENCES foundation.tenant(id) ON DELETE RESTRICT,
    code text NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 100),
    name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 200), description text CHECK(length(description)<=2000),
    item_type_id uuid NOT NULL, category_id uuid, base_uom_id uuid, brand_id uuid,
    status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUSPENDED','ARCHIVED')),
    activated_at timestamptz, version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id),
    FOREIGN KEY(tenant_id,item_type_id) REFERENCES masterdata.catalog_item_type(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,category_id) REFERENCES masterdata.catalog_category(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,base_uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,brand_id) REFERENCES masterdata.catalog_brand(tenant_id,id) ON DELETE RESTRICT,
    CHECK(status<>'ACTIVE' OR (activated_at IS NOT NULL AND category_id IS NOT NULL AND base_uom_id IS NOT NULL))
);
CREATE UNIQUE INDEX catalog_item_code_unique ON masterdata.catalog_item(tenant_id,lower(code));
CREATE INDEX catalog_item_list_idx ON masterdata.catalog_item(tenant_id,status,lower(name),id);
CREATE TABLE masterdata.catalog_item_code (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, item_id uuid NOT NULL,
    code text NOT NULL CHECK(length(btrim(code)) BETWEEN 1 AND 100), created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX catalog_item_reserved_code_unique ON masterdata.catalog_item_code(tenant_id,lower(code));
CREATE TABLE masterdata.catalog_item_unit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, item_id uuid NOT NULL, uom_id uuid NOT NULL,
    conversion_numerator numeric NOT NULL CHECK(conversion_numerator>0 AND conversion_numerator<10000000000000000 AND scale(conversion_numerator)<=12),
    conversion_denominator numeric NOT NULL CHECK(conversion_denominator>0 AND conversion_denominator<10000000000000000 AND scale(conversion_denominator)<=12),
    is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,item_id,uom_id), UNIQUE(tenant_id,item_id,id),
    FOREIGN KEY(tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT
);
CREATE TABLE masterdata.catalog_item_identifier (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, item_id uuid NOT NULL,
    identifier_type text NOT NULL CHECK(identifier_type IN ('GTIN','OEM','MPN','BARCODE','LEGACY')),
    value text NOT NULL CHECK(length(btrim(value)) BETWEEN 1 AND 200), normalized_value text NOT NULL,
    uom_id uuid, is_primary boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,item_id,id), UNIQUE(tenant_id,item_id,identifier_type,normalized_value),
    FOREIGN KEY(tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX catalog_identifier_unique ON masterdata.catalog_item_identifier(tenant_id,identifier_type,normalized_value) WHERE identifier_type IN ('GTIN','BARCODE');
CREATE UNIQUE INDEX catalog_identifier_primary_unique ON masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type) WHERE is_primary;
CREATE TABLE masterdata.catalog_item_physical_data (
    item_id uuid PRIMARY KEY, tenant_id uuid NOT NULL,
    net_weight numeric, gross_weight numeric, weight_uom_id uuid,
    length numeric, width numeric, height numeric, dimension_uom_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,weight_uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,dimension_uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT,
    CHECK(net_weight IS NULL OR (net_weight>=0 AND net_weight<10000000000000000 AND scale(net_weight)<=12)),
    CHECK(gross_weight IS NULL OR (gross_weight>=0 AND gross_weight<10000000000000000 AND scale(gross_weight)<=12)),
    CHECK(length IS NULL OR (length>=0 AND length<10000000000000000 AND scale(length)<=12)),
    CHECK(width IS NULL OR (width>=0 AND width<10000000000000000 AND scale(width)<=12)),
    CHECK(height IS NULL OR (height>=0 AND height<10000000000000000 AND scale(height)<=12)),
    CHECK(net_weight IS NULL OR gross_weight IS NULL OR gross_weight>=net_weight),
    CHECK((net_weight IS NULL AND gross_weight IS NULL) OR weight_uom_id IS NOT NULL),
    CHECK((length IS NULL AND width IS NULL AND height IS NULL) OR dimension_uom_id IS NOT NULL)
);

CREATE TABLE masterdata.catalog_item_company (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    item_id uuid NOT NULL,
    company_id uuid NOT NULL,
    is_enabled boolean NOT NULL DEFAULT true,
    is_sellable boolean NOT NULL,
    is_purchasable boolean NOT NULL,
    track_stock boolean NOT NULL,
    default_sales_uom_id uuid,
    default_purchase_uom_id uuid,
    version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(tenant_id,company_id,item_id),
    FOREIGN KEY(tenant_id,item_id) REFERENCES masterdata.catalog_item(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,default_sales_uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT,
    FOREIGN KEY(tenant_id,default_purchase_uom_id) REFERENCES masterdata.catalog_unit_of_measure(tenant_id,id) ON DELETE RESTRICT
);
CREATE INDEX catalog_item_company_item_idx ON masterdata.catalog_item_company(tenant_id,item_id);
CREATE INDEX catalog_item_company_sales_uom_idx ON masterdata.catalog_item_company(tenant_id,default_sales_uom_id) WHERE default_sales_uom_id IS NOT NULL;
CREATE INDEX catalog_item_company_purchase_uom_idx ON masterdata.catalog_item_company(tenant_id,default_purchase_uom_id) WHERE default_purchase_uom_id IS NOT NULL;


CREATE FUNCTION masterdata.guard_catalog() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $function$
DECLARE owner uuid;
BEGIN
    owner := CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||owner::text,0));
    IF TG_OP='DELETE' THEN
        IF TG_TABLE_NAME='catalog_item_type' THEN
            IF EXISTS(SELECT 1 FROM masterdata.catalog_item WHERE tenant_id=OLD.tenant_id AND item_type_id=OLD.id)
            THEN RAISE EXCEPTION 'Tipologia utilizzata' USING ERRCODE='23503'; END IF;
        ELSIF TG_TABLE_NAME<>'catalog_category' THEN
            RAISE EXCEPTION 'Disattivare il record' USING ERRCODE='23514';
        END IF;
        RETURN OLD;
    END IF;
    IF TG_OP='UPDATE' AND (NEW.id,NEW.tenant_id,NEW.created_at) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.created_at)
    THEN RAISE EXCEPTION 'Identita immutabile' USING ERRCODE='23514'; END IF;
    IF TG_TABLE_NAME='catalog_unit_of_measure' THEN
        IF TG_OP='UPDATE' AND (NEW.dimension,NEW.factor_to_base,NEW.is_base,NEW.conversion_scope) IS DISTINCT FROM (OLD.dimension,OLD.factor_to_base,OLD.is_base,OLD.conversion_scope)
        THEN RAISE EXCEPTION 'Significato unita immutabile' USING ERRCODE='23514'; END IF;
    ELSIF TG_TABLE_NAME='catalog_item_type' THEN
        IF TG_OP='UPDATE' AND NEW.kind<>OLD.kind
            AND EXISTS(SELECT 1 FROM masterdata.catalog_item WHERE tenant_id=NEW.tenant_id AND item_type_id=NEW.id)
        THEN RAISE EXCEPTION 'Natura immutabile' USING ERRCODE='23514'; END IF;
    ELSIF NEW.parent_id IS NOT NULL THEN
        IF EXISTS (WITH RECURSIVE ancestors AS (
            SELECT id,parent_id FROM masterdata.catalog_category WHERE tenant_id=NEW.tenant_id AND id=NEW.parent_id
            UNION SELECT c.id,c.parent_id FROM masterdata.catalog_category c JOIN ancestors a ON c.id=a.parent_id WHERE c.tenant_id=NEW.tenant_id
        ) SELECT 1 FROM ancestors WHERE id=NEW.id)
        THEN RAISE EXCEPTION 'Ciclo categorie' USING ERRCODE='23514'; END IF;
    END IF;
    RETURN NEW;
END $function$;
CREATE FUNCTION masterdata.check_catalog_base() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=NEW.tenant_id AND u.dimension=NEW.dimension AND u.is_active AND u.conversion_scope='UNIVERSAL')
       AND NOT EXISTS (SELECT 1 FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=NEW.tenant_id AND u.dimension=NEW.dimension AND u.is_active AND u.is_base)
    THEN RAISE EXCEPTION 'Base attiva richiesta' USING ERRCODE='23514'; END IF;
    RETURN NULL;
END $$;

CREATE TRIGGER catalog_unit_guard BEFORE INSERT OR UPDATE OR DELETE ON masterdata.catalog_unit_of_measure FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog();
CREATE TRIGGER catalog_category_guard BEFORE INSERT OR UPDATE OR DELETE ON masterdata.catalog_category FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog();
CREATE TRIGGER catalog_type_guard BEFORE INSERT OR UPDATE OR DELETE ON masterdata.catalog_item_type FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog();
CREATE CONSTRAINT TRIGGER catalog_unit_active_base AFTER INSERT OR UPDATE ON masterdata.catalog_unit_of_measure DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION masterdata.check_catalog_base();
CREATE TRIGGER catalog_unit_updated_at BEFORE UPDATE ON masterdata.catalog_unit_of_measure FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER catalog_category_updated_at BEFORE UPDATE ON masterdata.catalog_category FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER catalog_type_updated_at BEFORE UPDATE ON masterdata.catalog_item_type FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
REVOKE ALL ON FUNCTION masterdata.guard_catalog(),masterdata.check_catalog_base() FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON masterdata.catalog_unit_of_measure,masterdata.catalog_item_type TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON masterdata.catalog_category TO enginia360_app;

GRANT DELETE ON masterdata.catalog_item_type TO enginia360_app;

CREATE FUNCTION masterdata.seed_catalog(p_tenant uuid,p_actor uuid DEFAULT NULL) RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE inserted_id uuid;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||p_tenant::text,0));
    FOR inserted_id IN
        INSERT INTO masterdata.catalog_unit_of_measure(tenant_id,code,name,dimension,factor_to_base,decimal_places,is_base,is_active)
        SELECT p_tenant,s.code,s.name,s.dimension,s.factor,s.places,s.base,
            coalesce((SELECT u.is_active FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=p_tenant AND u.dimension=s.dimension AND u.is_base),
                     NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=p_tenant AND lower(u.code)=lower(s.base_code)))
        FROM (SELECT v.*,max(v.code) FILTER(WHERE v.base) OVER(PARTITION BY v.dimension) AS base_code FROM (VALUES
            ('PZ','Pezzi','COUNT',1::numeric,0,true),
            ('KG','Chilogrammi','MASS',1,3,true),('G','Grammi','MASS',0.001,3,false),
            ('M','Metri','LENGTH',1,3,true),('CM','Centimetri','LENGTH',0.01,2,false),
            ('L','Litri','VOLUME',1,3,true),('ML','Millilitri','VOLUME',0.001,2,false),
            ('MIN','Minuti','TIME',1,2,true),('H','Ore','TIME',60,2,false),
            ('M2','Metri quadrati','AREA',1,4,true),('CM2','Centimetri quadrati','AREA',0.0001,2,false)
        ) v(code,name,dimension,factor,places,base)) s
        WHERE NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=p_tenant AND lower(u.code)=lower(s.code))
          AND (NOT s.base OR NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure u WHERE u.tenant_id=p_tenant AND u.dimension=s.dimension AND u.is_base))
        ON CONFLICT DO NOTHING RETURNING id
    LOOP
        INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details)
        VALUES(p_actor,p_tenant,'create','catalog-units',inserted_id,'{"seed":true}'::jsonb);
    END LOOP;
    FOR inserted_id IN
        INSERT INTO masterdata.catalog_item_type(tenant_id,code,name,kind,default_track_stock)
        SELECT p_tenant,NULL,s.name,s.kind,s.stock FROM (VALUES ('Merce','GOOD',true),('Servizio','SERVICE',false)) s(name,kind,stock)
        WHERE NOT EXISTS(SELECT 1 FROM masterdata.catalog_item_type t WHERE t.tenant_id=p_tenant AND t.kind=s.kind)
        RETURNING id
    LOOP
        INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details)
        VALUES(p_actor,p_tenant,'create','catalog-types',inserted_id,'{"seed":true}'::jsonb);
    END LOOP;
END $$;
REVOKE ALL ON FUNCTION masterdata.seed_catalog(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION masterdata.seed_catalog(uuid,uuid) TO enginia360_app;

CREATE FUNCTION masterdata.catalog_normalize_identifier(p_type text,p_value text) RETURNS text LANGUAGE plpgsql IMMUTABLE SET search_path=pg_catalog AS $$
DECLARE i integer; s integer:=0; n integer; v text:=btrim(p_value);
BEGIN
    IF p_type<>'GTIN' THEN RETURN upper(v); END IF;
    n:=length(v);
    IF n NOT IN (8,12,13,14) OR v !~ '^[0-9]+$' THEN RAISE EXCEPTION 'GTIN: formato non valido' USING ERRCODE='23514'; END IF;
    FOR i IN 1..n-1 LOOP s:=s+substr(v,i,1)::integer * CASE WHEN (n-i)%2=1 THEN 3 ELSE 1 END; END LOOP;
    IF (10-s%10)%10<>right(v,1)::integer THEN RAISE EXCEPTION 'GTIN: cifra di controllo non valida' USING ERRCODE='23514'; END IF;
    RETURN lpad(v,14,'0');
END $$;

CREATE FUNCTION masterdata.guard_catalog_item() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE owner uuid; p masterdata.catalog_item; old_kind text; new_kind text; ref_active boolean; mode text; changed boolean;
BEGIN
    owner:=CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||owner::text,0));
    IF TG_TABLE_NAME='catalog_item_code' THEN
        IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Registro codici append-only' USING ERRCODE='23514'; END IF;
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME IN ('catalog_item','catalog_brand') THEN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Archiviare o disattivare il record' USING ERRCODE='23514'; END IF;
        IF TG_OP='UPDATE' AND (NEW.id,NEW.tenant_id,NEW.created_at) IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.created_at)
        THEN RAISE EXCEPTION 'Identita immutabile' USING ERRCODE='23514'; END IF;
        IF TG_TABLE_NAME='catalog_brand' THEN RETURN NEW; END IF;
        SELECT kind INTO new_kind FROM masterdata.catalog_item_type WHERE tenant_id=owner AND id=NEW.item_type_id;
        IF TG_OP='INSERT' THEN
            IF NEW.status NOT IN ('ACTIVE','SUSPENDED') OR (NEW.status='SUSPENDED' AND NEW.activated_at IS NOT NULL) THEN RAISE EXCEPTION 'Stato iniziale non valido' USING ERRCODE='23514'; END IF;
            IF NEW.status='ACTIVE' THEN NEW.activated_at:=coalesce(NEW.activated_at,now()); END IF;
        ELSE
            IF OLD.status='ARCHIVED' THEN RAISE EXCEPTION 'Articolo archiviato' USING ERRCODE='23514'; END IF;
            SELECT kind INTO old_kind FROM masterdata.catalog_item_type WHERE tenant_id=owner AND id=OLD.item_type_id;
            IF new_kind<>old_kind THEN RAISE EXCEPTION 'Natura immutabile' USING ERRCODE='23514'; END IF;
            IF NEW.status<>OLD.status AND NOT ((OLD.status='ACTIVE' AND NEW.status IN ('SUSPENDED','ARCHIVED')) OR (OLD.status='SUSPENDED' AND NEW.status IN ('ACTIVE','ARCHIVED')))
            THEN RAISE EXCEPTION 'Transizione non valida' USING ERRCODE='23514'; END IF;
            IF NEW.status='ACTIVE' THEN NEW.activated_at:=coalesce(NEW.activated_at,now()); END IF;
            IF OLD.activated_at IS NOT NULL AND (NEW.code,NEW.base_uom_id,NEW.activated_at) IS DISTINCT FROM (OLD.code,OLD.base_uom_id,OLD.activated_at)
            THEN RAISE EXCEPTION 'Codice e base immutabili dopo attivazione' USING ERRCODE='23514'; END IF;
            IF OLD.activated_at IS NULL AND NEW.activated_at IS NOT NULL AND NEW.status<>'ACTIVE' THEN RAISE EXCEPTION 'Prima attivazione non valida' USING ERRCODE='23514'; END IF;
            IF NEW.code IS DISTINCT FROM OLD.code THEN
                SELECT s.mode INTO mode FROM foundation.numbering_series s WHERE tenant_id=owner AND entity_type='CATALOG_'||new_kind;
                IF OLD.status<>'SUSPENDED' OR OLD.activated_at IS NOT NULL OR mode IS DISTINCT FROM 'MANUAL'
                THEN RAISE EXCEPTION 'Codice modificabile solo se sospeso mai attivato e manuale' USING ERRCODE='23514'; END IF;
            END IF;
            IF NEW.base_uom_id IS DISTINCT FROM OLD.base_uom_id AND (EXISTS(SELECT 1 FROM masterdata.catalog_item_unit WHERE tenant_id=owner AND item_id=OLD.id) OR EXISTS(SELECT 1 FROM masterdata.catalog_item_identifier WHERE tenant_id=owner AND item_id=OLD.id) OR EXISTS(SELECT 1 FROM masterdata.catalog_item_physical_data WHERE tenant_id=owner AND item_id=OLD.id))
            THEN RAISE EXCEPTION 'Base utilizzata da unita o identificativi' USING ERRCODE='23514'; END IF;
        END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.item_type_id IS DISTINCT FROM OLD.item_type_id; END IF;
        IF changed AND NOT coalesce((SELECT is_active FROM masterdata.catalog_item_type WHERE tenant_id=owner AND id=NEW.item_type_id),false) THEN RAISE EXCEPTION 'Tipologia non attiva' USING ERRCODE='23514'; END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.category_id IS DISTINCT FROM OLD.category_id; END IF;
        IF changed AND NEW.category_id IS NOT NULL AND NOT coalesce((SELECT is_active FROM masterdata.catalog_category WHERE tenant_id=owner AND id=NEW.category_id),false) THEN RAISE EXCEPTION 'Categoria non attiva' USING ERRCODE='23514'; END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.brand_id IS DISTINCT FROM OLD.brand_id; END IF;
        IF changed AND NEW.brand_id IS NOT NULL AND NOT coalesce((SELECT is_active FROM masterdata.catalog_brand WHERE tenant_id=owner AND id=NEW.brand_id),false) THEN RAISE EXCEPTION 'Marchio non attivo' USING ERRCODE='23514'; END IF;
        IF NEW.base_uom_id IS NOT NULL AND NOT coalesce((SELECT conversion_scope='UNIVERSAL' FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=NEW.base_uom_id),false) THEN RAISE EXCEPTION 'Base universale richiesta' USING ERRCODE='23514'; END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.base_uom_id IS DISTINCT FROM OLD.base_uom_id; END IF;
        IF changed AND NEW.base_uom_id IS NOT NULL AND NOT coalesce((SELECT is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=NEW.base_uom_id),false) THEN RAISE EXCEPTION 'Unita base non attiva' USING ERRCODE='23514'; END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO p FROM masterdata.catalog_item WHERE tenant_id=owner AND id=CASE WHEN TG_OP='DELETE' THEN OLD.item_id ELSE NEW.item_id END FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Articolo non trovato' USING ERRCODE='23503'; END IF;
    IF p.status='ARCHIVED' THEN RAISE EXCEPTION 'Articolo archiviato' USING ERRCODE='23514'; END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    IF TG_OP='UPDATE' THEN
        IF (NEW.tenant_id,NEW.item_id,NEW.created_at) IS DISTINCT FROM (OLD.tenant_id,OLD.item_id,OLD.created_at) OR (TG_TABLE_NAME<>'catalog_item_physical_data' AND to_jsonb(NEW)->'id' IS DISTINCT FROM to_jsonb(OLD)->'id')
        THEN RAISE EXCEPTION 'Identita figlio immutabile' USING ERRCODE='23514'; END IF;
    END IF;
    IF TG_TABLE_NAME='catalog_item_identifier' THEN
        NEW.value:=btrim(NEW.value); NEW.normalized_value:=masterdata.catalog_normalize_identifier(NEW.identifier_type,NEW.value);
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.uom_id IS DISTINCT FROM OLD.uom_id; END IF;
        IF changed AND (NOT coalesce((SELECT is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=coalesce(NEW.uom_id,p.base_uom_id)),false) OR (NEW.uom_id IS NOT NULL AND NEW.uom_id IS DISTINCT FROM p.base_uom_id AND NOT EXISTS(SELECT 1 FROM masterdata.catalog_item_unit WHERE tenant_id=owner AND item_id=p.id AND uom_id=NEW.uom_id AND is_active)))
        THEN RAISE EXCEPTION 'Unita identificativo non associata attiva' USING ERRCODE='23514'; END IF;
    ELSIF TG_TABLE_NAME='catalog_item_unit' THEN
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.uom_id IS DISTINCT FROM OLD.uom_id OR (NEW.is_active AND NOT OLD.is_active); END IF;
        IF changed AND NOT coalesce((SELECT is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=NEW.uom_id),false) THEN RAISE EXCEPTION 'Unita non attiva' USING ERRCODE='23514'; END IF;
    ELSE
        SELECT kind INTO new_kind FROM masterdata.catalog_item_type WHERE tenant_id=owner AND id=p.item_type_id;
        IF new_kind<>'GOOD' THEN RAISE EXCEPTION 'Dati fisici solo per beni' USING ERRCODE='23514'; END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.weight_uom_id IS DISTINCT FROM OLD.weight_uom_id; END IF;
        IF changed AND NEW.weight_uom_id IS NOT NULL AND NOT coalesce((SELECT is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=NEW.weight_uom_id),false) THEN RAISE EXCEPTION 'Unita peso non attiva' USING ERRCODE='23514'; END IF;
        IF TG_OP='INSERT' THEN changed:=true; ELSE changed:=NEW.dimension_uom_id IS DISTINCT FROM OLD.dimension_uom_id; END IF;
        IF changed AND NEW.dimension_uom_id IS NOT NULL AND NOT coalesce((SELECT is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=owner AND id=NEW.dimension_uom_id),false) THEN RAISE EXCEPTION 'Unita dimensioni non attiva' USING ERRCODE='23514'; END IF;
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION masterdata.check_catalog_item(p_tenant uuid,p_item uuid,p_activation boolean DEFAULT false) RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p masterdata.catalog_item;
BEGIN
    SELECT * INTO p FROM masterdata.catalog_item WHERE tenant_id=p_tenant AND id=p_item;
    IF NOT FOUND THEN RETURN; END IF;
    IF EXISTS(SELECT 1 FROM masterdata.catalog_item_unit a JOIN masterdata.catalog_unit_of_measure u ON u.tenant_id=a.tenant_id AND u.id=a.uom_id LEFT JOIN masterdata.catalog_unit_of_measure b ON b.tenant_id=p.tenant_id AND b.id=p.base_uom_id
        WHERE a.tenant_id=p_tenant AND a.item_id=p_item AND (p.base_uom_id IS NULL OR a.uom_id=p.base_uom_id OR (u.conversion_scope='UNIVERSAL' AND (u.dimension<>b.dimension OR a.conversion_numerator*b.factor_to_base<>a.conversion_denominator*u.factor_to_base))))
    THEN RAISE EXCEPTION 'Rapporto unita non coerente con la base' USING ERRCODE='23514'; END IF;
    IF EXISTS(SELECT 1 FROM masterdata.catalog_item_identifier i WHERE i.tenant_id=p_tenant AND i.item_id=p_item AND (p.base_uom_id IS NULL OR (i.uom_id IS NOT NULL AND i.uom_id IS DISTINCT FROM p.base_uom_id AND NOT EXISTS(SELECT 1 FROM masterdata.catalog_item_unit a WHERE a.tenant_id=p_tenant AND a.item_id=p_item AND a.uom_id=i.uom_id AND a.is_active))))
    THEN RAISE EXCEPTION 'Identificativo dipendente da unita non associata attiva' USING ERRCODE='23514'; END IF;
    IF EXISTS(SELECT 1 FROM masterdata.catalog_item_physical_data d JOIN masterdata.catalog_item_type t ON t.tenant_id=p.tenant_id AND t.id=p.item_type_id
        LEFT JOIN masterdata.catalog_unit_of_measure w ON w.tenant_id=d.tenant_id AND w.id=d.weight_uom_id
        LEFT JOIN masterdata.catalog_unit_of_measure m ON m.tenant_id=d.tenant_id AND m.id=d.dimension_uom_id
        WHERE d.tenant_id=p_tenant AND d.item_id=p_item AND (t.kind<>'GOOD' OR (d.weight_uom_id IS NOT NULL AND (w.conversion_scope<>'UNIVERSAL' OR w.dimension<>'MASS')) OR (d.dimension_uom_id IS NOT NULL AND (m.conversion_scope<>'UNIVERSAL' OR m.dimension<>'LENGTH'))))
    THEN RAISE EXCEPTION 'Unita dati fisici non coerenti' USING ERRCODE='23514'; END IF;
    IF p_activation AND p.status='ACTIVE' THEN
        IF NOT EXISTS(SELECT 1 FROM masterdata.catalog_item_type WHERE tenant_id=p_tenant AND id=p.item_type_id AND is_active)
        OR NOT EXISTS(SELECT 1 FROM masterdata.catalog_category WHERE tenant_id=p_tenant AND id=p.category_id AND is_active)
        OR NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure WHERE tenant_id=p_tenant AND id=p.base_uom_id AND is_active AND conversion_scope='UNIVERSAL')
        OR (p.brand_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM masterdata.catalog_brand WHERE tenant_id=p_tenant AND id=p.brand_id AND is_active))
        OR EXISTS(SELECT 1 FROM masterdata.catalog_item_unit a JOIN masterdata.catalog_unit_of_measure u ON u.tenant_id=a.tenant_id AND u.id=a.uom_id WHERE a.tenant_id=p_tenant AND a.item_id=p_item AND a.is_active AND NOT u.is_active)
        OR EXISTS(SELECT 1 FROM masterdata.catalog_item_identifier i JOIN masterdata.catalog_unit_of_measure u ON u.tenant_id=i.tenant_id AND u.id=coalesce(i.uom_id,p.base_uom_id) WHERE i.tenant_id=p_tenant AND i.item_id=p_item AND NOT u.is_active)
        OR EXISTS(SELECT 1 FROM masterdata.catalog_item_physical_data d JOIN masterdata.catalog_unit_of_measure u ON u.tenant_id=d.tenant_id AND u.id IN (d.weight_uom_id,d.dimension_uom_id) WHERE d.tenant_id=p_tenant AND d.item_id=p_item AND NOT u.is_active)
        THEN RAISE EXCEPTION 'Attivazione: riferimenti attivi richiesti' USING ERRCODE='23514'; END IF;
    END IF;
END $$;

CREATE FUNCTION masterdata.catalog_item_after_write() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE t uuid; i uuid; activation boolean:=false;
BEGIN
    t:=CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    IF TG_TABLE_NAME='catalog_item' THEN
        i:=NEW.id;
        IF TG_OP='INSERT' OR NEW.code IS DISTINCT FROM OLD.code THEN
            INSERT INTO masterdata.catalog_item_code(tenant_id,item_id,code) VALUES(t,i,NEW.code);
        END IF;
    ELSE
        i:=CASE WHEN TG_OP='DELETE' THEN OLD.item_id ELSE NEW.item_id END;
        -- La prima creazione dell'aggregato resta versione 1; le righe successive avanzano la radice.
        UPDATE masterdata.catalog_item SET version=version+1 WHERE tenant_id=t AND id=i AND NOT (xmin::text::bigint=txid_current() AND created_at=transaction_timestamp());
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION masterdata.catalog_item_deferred_check() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE t uuid; i uuid; activation boolean:=false;
BEGIN
    t:=CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    IF TG_TABLE_NAME='catalog_item' THEN
        i:=NEW.id;
        IF TG_OP='INSERT' THEN activation:=NEW.status='ACTIVE';
        ELSE activation:=NEW.status='ACTIVE' AND OLD.status<>'ACTIVE'; END IF;
    ELSE i:=CASE WHEN TG_OP='DELETE' THEN OLD.item_id ELSE NEW.item_id END;
    END IF;
    PERFORM masterdata.check_catalog_item(t,i,activation);
    RETURN NULL;
END $$;
DO $$ DECLARE tbl text; BEGIN
    FOREACH tbl IN ARRAY ARRAY['catalog_brand','catalog_item','catalog_item_code','catalog_item_unit','catalog_item_identifier','catalog_item_physical_data'] LOOP
        EXECUTE format('CREATE TRIGGER %I BEFORE INSERT OR UPDATE OR DELETE ON masterdata.%I FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog_item()',tbl||'_guard',tbl);
        IF tbl<>'catalog_item_code' THEN
            EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON masterdata.%I FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at()',tbl||'_updated_at',tbl);
        END IF;
        IF tbl NOT IN ('catalog_brand','catalog_item_code') THEN
            EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON masterdata.%I FOR EACH ROW EXECUTE FUNCTION masterdata.catalog_item_after_write()',tbl||'_after',tbl);
            EXECUTE format('CREATE CONSTRAINT TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON masterdata.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION masterdata.catalog_item_deferred_check()',tbl||'_consistency',tbl);
        END IF;
    END LOOP;
END $$;
REVOKE ALL ON FUNCTION masterdata.catalog_normalize_identifier(text,text),masterdata.guard_catalog_item(),masterdata.check_catalog_item(uuid,uuid,boolean),masterdata.catalog_item_after_write(),masterdata.catalog_item_deferred_check() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION masterdata.catalog_normalize_identifier(text,text),masterdata.check_catalog_item(uuid,uuid,boolean) TO enginia360_app;
GRANT SELECT,INSERT,UPDATE ON masterdata.catalog_brand,masterdata.catalog_item TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON masterdata.catalog_item_identifier,masterdata.catalog_item_unit,masterdata.catalog_item_physical_data TO enginia360_app;
GRANT SELECT,INSERT ON masterdata.catalog_item_code TO enginia360_app;

-- Chiamata sotto il lock catalog:<tenant>, condiviso con tutte le guardie pubblicate.
CREATE FUNCTION masterdata.assert_catalog_company_unit(p_tenant uuid,p_item uuid,p_base uuid,p_unit uuid)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
    IF p_base IS NULL OR NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure
        WHERE tenant_id=p_tenant AND id=coalesce(p_unit,p_base) AND is_active)
       OR (p_unit IS NOT NULL AND p_unit IS DISTINCT FROM p_base AND NOT EXISTS(
           SELECT 1 FROM masterdata.catalog_item_unit WHERE tenant_id=p_tenant AND item_id=p_item AND uom_id=p_unit AND is_active))
    THEN RAISE EXCEPTION 'Unita predefinita aziendale non associata attiva' USING ERRCODE='23503',CONSTRAINT='catalog_company_default_unit'; END IF;
END $$;

CREATE FUNCTION masterdata.guard_catalog_item_company() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE p masterdata.catalog_item; company_enabled boolean; nature text;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END::text,0));
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Disabilitare la configurazione aziendale' USING ERRCODE='23514'; END IF;
    IF TG_OP='UPDATE' AND (NEW.id,NEW.tenant_id,NEW.company_id,NEW.item_id,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.tenant_id,OLD.company_id,OLD.item_id,OLD.created_at)
    THEN RAISE EXCEPTION 'Identita configurazione aziendale immutabile' USING ERRCODE='23514'; END IF;
    SELECT * INTO p FROM masterdata.catalog_item WHERE tenant_id=NEW.tenant_id AND id=NEW.item_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Articolo non trovato nel tenant' USING ERRCODE='23503'; END IF;
    -- SHARE serializza la verifica con la disabilitazione della società, senza bloccare la radice.
    SELECT is_enabled INTO company_enabled FROM foundation.company WHERE tenant_id=NEW.tenant_id AND id=NEW.company_id FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Societa non trovata nel tenant' USING ERRCODE='23503'; END IF;
    IF p.status='ARCHIVED' OR NOT company_enabled THEN
        IF TG_OP='UPDATE' THEN
            IF OLD.is_enabled AND NOT NEW.is_enabled
                AND (NEW.is_sellable,NEW.is_purchasable,NEW.track_stock,NEW.default_sales_uom_id,NEW.default_purchase_uom_id)
                    IS NOT DISTINCT FROM (OLD.is_sellable,OLD.is_purchasable,OLD.track_stock,OLD.default_sales_uom_id,OLD.default_purchase_uom_id)
            THEN RETURN NEW; END IF;
        END IF;
        RAISE EXCEPTION 'Articolo archiviato o societa disabilitata: consentita solo disabilitazione' USING ERRCODE='23514';
    END IF;
    SELECT kind INTO nature FROM masterdata.catalog_item_type WHERE tenant_id=p.tenant_id AND id=p.item_type_id;
    IF NEW.track_stock AND nature IS DISTINCT FROM 'GOOD'
    THEN RAISE EXCEPTION 'Gestione stock solo per beni materiali GOOD' USING ERRCODE='23514'; END IF;
    IF NOT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure WHERE tenant_id=NEW.tenant_id AND id=p.base_uom_id AND is_active)
    THEN RAISE EXCEPTION 'Unita base attiva richiesta per configurazione aziendale' USING ERRCODE='23503'; END IF;
    PERFORM masterdata.assert_catalog_company_unit(NEW.tenant_id,NEW.item_id,p.base_uom_id,NEW.default_sales_uom_id);
    PERFORM masterdata.assert_catalog_company_unit(NEW.tenant_id,NEW.item_id,p.base_uom_id,NEW.default_purchase_uom_id);
    RETURN NEW;
END $$;

-- Nuove guardie inverse, senza sostituire funzioni o alterare dati pubblicati.
CREATE FUNCTION masterdata.guard_catalog_company_defaults() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE owner uuid; configuration masterdata.catalog_item_company;
BEGIN
    owner:=CASE WHEN TG_OP='DELETE' THEN OLD.tenant_id ELSE NEW.tenant_id END;
    PERFORM pg_advisory_xact_lock(hashtextextended('catalog:'||owner::text,0));
    IF TG_TABLE_NAME='catalog_item_unit' THEN
        IF TG_OP='DELETE' OR NOT NEW.is_active OR NEW.uom_id IS DISTINCT FROM OLD.uom_id THEN
            IF EXISTS(SELECT 1 FROM masterdata.catalog_item_company c
                JOIN masterdata.catalog_item i ON i.tenant_id=c.tenant_id AND i.id=c.item_id
                WHERE c.tenant_id=OLD.tenant_id AND c.item_id=OLD.item_id AND OLD.uom_id IS DISTINCT FROM i.base_uom_id
                    AND OLD.uom_id IN (c.default_sales_uom_id,c.default_purchase_uom_id))
            THEN RAISE EXCEPTION 'Unita utilizzata da configurazione aziendale' USING ERRCODE='23503',CONSTRAINT='catalog_company_default_unit'; END IF;
        END IF;
    ELSIF TG_TABLE_NAME='catalog_unit_of_measure' THEN
        IF OLD.is_active AND NOT NEW.is_active AND EXISTS(
            SELECT 1 FROM masterdata.catalog_item_company c JOIN masterdata.catalog_item i ON i.tenant_id=c.tenant_id AND i.id=c.item_id
            WHERE c.tenant_id=owner AND OLD.id IN (coalesce(c.default_sales_uom_id,i.base_uom_id),coalesce(c.default_purchase_uom_id,i.base_uom_id)))
        THEN RAISE EXCEPTION 'Unita predefinita utilizzata da configurazione aziendale' USING ERRCODE='23503',CONSTRAINT='catalog_company_default_unit'; END IF;
    ELSIF NEW.base_uom_id IS DISTINCT FROM OLD.base_uom_id THEN
        FOR configuration IN SELECT * FROM masterdata.catalog_item_company WHERE tenant_id=owner AND item_id=OLD.id LOOP
            PERFORM masterdata.assert_catalog_company_unit(owner,OLD.id,NEW.base_uom_id,configuration.default_sales_uom_id);
            PERFORM masterdata.assert_catalog_company_unit(owner,OLD.id,NEW.base_uom_id,configuration.default_purchase_uom_id);
        END LOOP;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER catalog_item_company_guard BEFORE INSERT OR UPDATE OR DELETE ON masterdata.catalog_item_company
    FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog_item_company();
CREATE TRIGGER catalog_item_company_updated_at BEFORE UPDATE ON masterdata.catalog_item_company
    FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
-- Ordinamento alfabetico prima delle guardie esistenti; stesso lock, nessun nuovo lock radice.
CREATE TRIGGER catalog_company_defaults_guard BEFORE UPDATE OR DELETE ON masterdata.catalog_item_unit
    FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog_company_defaults();
CREATE TRIGGER catalog_company_defaults_guard BEFORE UPDATE OF is_active ON masterdata.catalog_unit_of_measure
    FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog_company_defaults();
CREATE TRIGGER catalog_company_defaults_guard BEFORE UPDATE OF base_uom_id ON masterdata.catalog_item
    FOR EACH ROW EXECUTE FUNCTION masterdata.guard_catalog_company_defaults();
REVOKE ALL ON FUNCTION masterdata.assert_catalog_company_unit(uuid,uuid,uuid,uuid),masterdata.guard_catalog_item_company(),masterdata.guard_catalog_company_defaults() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION masterdata.assert_catalog_company_unit(uuid,uuid,uuid,uuid) TO enginia360_app;
GRANT SELECT,INSERT,UPDATE ON masterdata.catalog_item_company TO enginia360_app;
