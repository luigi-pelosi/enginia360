-- Payments master data; apply once to an existing BP-enabled database as postgres.
CREATE TABLE masterdata.fatturapa_payment_codes (
 code varchar(4) PRIMARY KEY CHECK (code ~ '^MP[0-9]{2}$'), description text NOT NULL,
 is_active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1 CHECK(version>0)
);
INSERT INTO masterdata.fatturapa_payment_codes(code,description) VALUES
 ('MP01','Contanti'),('MP02','Assegno'),('MP05','Bonifico'),('MP08','Carta di pagamento'),
 ('MP12','Ri.Ba.'),('MP19','SEPA Direct Debit'),('MP20','SEPA Direct Debit CORE'),('MP21','SEPA Direct Debit B2B');
CREATE TABLE masterdata.payment_methods (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid NOT NULL,
 code varchar(30) NOT NULL CHECK(length(btrim(code))>0), name varchar(100) NOT NULL CHECK(length(btrim(name))>0),
 category text NOT NULL CHECK(category IN ('BANK_TRANSFER','CASH','CARD','DIRECT_DEBIT','BANK_RECEIPT','CHEQUE','OTHER')),
 fatturapa_code varchar(4) REFERENCES masterdata.fatturapa_payment_codes(code) ON DELETE RESTRICT,
 direction text NOT NULL CHECK(direction IN ('INBOUND','OUTBOUND','BOTH')),
 inbound_compatible boolean GENERATED ALWAYS AS (direction IN ('INBOUND','BOTH')) STORED,
 outbound_compatible boolean GENERATED ALWAYS AS (direction IN ('OUTBOUND','BOTH')) STORED,
 requires_bank_account boolean NOT NULL DEFAULT false, is_active boolean NOT NULL DEFAULT true, sort_order integer NOT NULL DEFAULT 0,
 version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,company_id,id), UNIQUE(tenant_id,company_id,id,inbound_compatible), UNIQUE(tenant_id,company_id,id,outbound_compatible),
 FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX payment_methods_code_unique ON masterdata.payment_methods(tenant_id,company_id,lower(code));
CREATE TABLE masterdata.payment_terms (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid NOT NULL,
 code varchar(30) NOT NULL CHECK(length(btrim(code))>0), name varchar(120) NOT NULL CHECK(length(btrim(name))>0),
 default_method_id uuid, reference_date_type text NOT NULL CHECK(reference_date_type IN ('DOCUMENT_DATE','RECEIPT_DATE','CUSTOM_DATE')),
 is_active boolean NOT NULL DEFAULT true, version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,company_id,id),
 FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,default_method_id) REFERENCES masterdata.payment_methods(tenant_id,company_id,id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX payment_terms_code_unique ON masterdata.payment_terms(tenant_id,company_id,lower(code));
CREATE TABLE masterdata.payment_term_installments (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid NOT NULL, company_id uuid NOT NULL, payment_term_id uuid NOT NULL,
 sequence integer NOT NULL CHECK(sequence>0), percentage numeric(7,4) NOT NULL CHECK(percentage>0 AND percentage<=100),
 offset_months integer NOT NULL DEFAULT 0 CHECK(offset_months>=0), offset_days integer NOT NULL DEFAULT 0 CHECK(offset_days>=0),
 date_rule text NOT NULL CHECK(date_rule IN ('EXACT','END_OF_MONTH','FIXED_DAY')),
 offset_base text NOT NULL CHECK(offset_base IN ('REFERENCE_DATE','REFERENCE_MONTH_END')),
 fixed_day integer, method_id uuid,
 CHECK ((date_rule='FIXED_DAY' AND fixed_day BETWEEN 1 AND 31 AND fixed_day IS NOT NULL) OR (date_rule<>'FIXED_DAY' AND fixed_day IS NULL)),
 UNIQUE(tenant_id,company_id,payment_term_id,sequence),
 FOREIGN KEY(tenant_id,company_id,payment_term_id) REFERENCES masterdata.payment_terms(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,method_id) REFERENCES masterdata.payment_methods(tenant_id,company_id,id) ON DELETE RESTRICT
);
CREATE TABLE masterdata.company_payment_settings (
 tenant_id uuid NOT NULL, company_id uuid NOT NULL, default_sales_term_id uuid, default_purchase_term_id uuid,
 default_sales_method_id uuid, default_purchase_method_id uuid,
 sales_compatible boolean NOT NULL DEFAULT true CHECK(sales_compatible), purchase_compatible boolean NOT NULL DEFAULT true CHECK(purchase_compatible),
 version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,company_id),
 FOREIGN KEY(tenant_id,company_id) REFERENCES foundation.company(tenant_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,default_sales_term_id) REFERENCES masterdata.payment_terms(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,default_purchase_term_id) REFERENCES masterdata.payment_terms(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,default_sales_method_id,sales_compatible) REFERENCES masterdata.payment_methods(tenant_id,company_id,id,inbound_compatible) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,default_purchase_method_id,purchase_compatible) REFERENCES masterdata.payment_methods(tenant_id,company_id,id,outbound_compatible) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX company_bp_tenant_company_id_unique ON masterdata.company_business_partner(tenant_id,company_id,id);
CREATE TABLE masterdata.business_partner_payment_defaults (
 tenant_id uuid NOT NULL, company_id uuid NOT NULL, company_business_partner_id uuid NOT NULL,
 role_code text NOT NULL CHECK(role_code IN ('CUSTOMER','SUPPLIER')), payment_term_id uuid, payment_method_id uuid,
 inbound_compatible boolean GENERATED ALWAYS AS (CASE WHEN role_code='CUSTOMER' THEN true END) STORED,
 outbound_compatible boolean GENERATED ALWAYS AS (CASE WHEN role_code='SUPPLIER' THEN true END) STORED,
 version bigint NOT NULL DEFAULT 1 CHECK(version BETWEEN 1 AND 9007199254740991),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,company_business_partner_id,role_code),
 FOREIGN KEY(tenant_id,company_id,company_business_partner_id) REFERENCES masterdata.company_business_partner(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_business_partner_id,role_code) REFERENCES masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,payment_term_id) REFERENCES masterdata.payment_terms(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,payment_method_id) REFERENCES masterdata.payment_methods(tenant_id,company_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,payment_method_id,inbound_compatible) REFERENCES masterdata.payment_methods(tenant_id,company_id,id,inbound_compatible) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,company_id,payment_method_id,outbound_compatible) REFERENCES masterdata.payment_methods(tenant_id,company_id,id,outbound_compatible) ON DELETE RESTRICT
);
-- Deferred aggregate validation allows atomic replacement of a term's installments.
CREATE FUNCTION masterdata.check_payment_installments() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE t uuid; ten uuid; co uuid;
BEGIN
 IF TG_TABLE_NAME='payment_terms' THEN t:=NEW.id; ten:=NEW.tenant_id; co:=NEW.company_id;
 ELSIF TG_OP='DELETE' THEN t:=OLD.payment_term_id; ten:=OLD.tenant_id; co:=OLD.company_id;
 ELSE t:=NEW.payment_term_id; ten:=NEW.tenant_id; co:=NEW.company_id; END IF;
 IF EXISTS(SELECT 1 FROM masterdata.payment_terms WHERE id=t AND tenant_id=ten AND company_id=co)
 AND (SELECT coalesce(sum(percentage),0) FROM masterdata.payment_term_installments WHERE payment_term_id=t AND tenant_id=ten AND company_id=co)<>100 THEN
 RAISE EXCEPTION 'Payment installments must total 100 percent' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER payment_term_total AFTER INSERT OR UPDATE ON masterdata.payment_terms DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION masterdata.check_payment_installments();
CREATE CONSTRAINT TRIGGER payment_installment_total AFTER INSERT OR UPDATE OR DELETE ON masterdata.payment_term_installments DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION masterdata.check_payment_installments();
CREATE FUNCTION masterdata.lock_payment_installments() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='UPDATE' AND (OLD.tenant_id,OLD.company_id,OLD.payment_term_id) IS DISTINCT FROM (NEW.tenant_id,NEW.company_id,NEW.payment_term_id) THEN RAISE EXCEPTION 'Installment parent immutable' USING ERRCODE='23514'; END IF;
 PERFORM 1 FROM masterdata.payment_terms WHERE tenant_id=coalesce(NEW.tenant_id,OLD.tenant_id) AND company_id=coalesce(NEW.company_id,OLD.company_id) AND id=coalesce(NEW.payment_term_id,OLD.payment_term_id) FOR UPDATE;
 RETURN coalesce(NEW,OLD);
END $$;
CREATE TRIGGER payment_installment_lock BEFORE INSERT OR UPDATE OR DELETE ON masterdata.payment_term_installments FOR EACH ROW EXECUTE FUNCTION masterdata.lock_payment_installments();
CREATE TRIGGER payment_methods_updated_at BEFORE UPDATE ON masterdata.payment_methods FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER payment_terms_updated_at BEFORE UPDATE ON masterdata.payment_terms FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER company_payment_settings_updated_at BEFORE UPDATE ON masterdata.company_payment_settings FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
CREATE TRIGGER bp_payment_defaults_updated_at BEFORE UPDATE ON masterdata.business_partner_payment_defaults FOR EACH ROW EXECUTE FUNCTION foundation.set_updated_at();
REVOKE ALL ON FUNCTION masterdata.check_payment_installments(),masterdata.lock_payment_installments() FROM PUBLIC;
GRANT SELECT ON masterdata.fatturapa_payment_codes TO enginia360_app;
GRANT SELECT,INSERT,UPDATE ON masterdata.payment_methods,masterdata.payment_terms,masterdata.company_payment_settings,masterdata.business_partner_payment_defaults TO enginia360_app;
GRANT SELECT,INSERT,UPDATE,DELETE ON masterdata.payment_term_installments TO enginia360_app;
