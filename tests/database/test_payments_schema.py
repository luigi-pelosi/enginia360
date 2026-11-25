"""Runtime payment constraints on an isolated PostgreSQL test database.

Set PAYMENTS_TEST_CONTAINER to a disposable container with payments_test loaded.
"""
import os
import subprocess
import unittest

CONTAINER = os.environ.get('PAYMENTS_TEST_CONTAINER', 'enginia360-payments-schema-proof')

def sql(text):
    return subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-qAt','-U','postgres','-d','payments_test','-v','ON_ERROR_STOP=1'],input=text,text=True,capture_output=True)

FIXTURE = """
BEGIN;
INSERT INTO foundation.tenant(id,code,name) VALUES ('10000000-0000-0000-0000-000000000001','payment-test','Payment test');
INSERT INTO foundation.company(id,tenant_id,name) VALUES
 ('20000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','One'),
 ('20000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000001','Two');
INSERT INTO masterdata.payment_methods(id,tenant_id,company_id,code,name,category,direction,fatturapa_code) VALUES
 ('30000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','BON','Bonifico','BANK_TRANSFER','INBOUND','MP05'),
 ('30000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002','BON','Bonifico','BANK_TRANSFER','BOTH','MP05');
INSERT INTO masterdata.payment_terms(id,tenant_id,company_id,code,name,reference_date_type) VALUES
 ('40000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','30_60','30/60','DOCUMENT_DATE');
INSERT INTO masterdata.payment_term_installments(tenant_id,company_id,payment_term_id,sequence,percentage,offset_days,date_rule,offset_base) VALUES
 ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001',1,50,30,'EXACT','REFERENCE_DATE'),
 ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001',2,50,60,'EXACT','REFERENCE_DATE');
SET CONSTRAINTS ALL IMMEDIATE;
"""

class PaymentSchema(unittest.TestCase):
    def check(self, query):
        r = sql(FIXTURE + query + '\nROLLBACK;')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_valid_schedule_and_sales_default(self):
        self.check("INSERT INTO masterdata.company_payment_settings(tenant_id,company_id,default_sales_term_id,default_sales_method_id) VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001');")

    def test_cross_company_and_wrong_direction_rejected(self):
        self.check("""DO $$ BEGIN
          BEGIN INSERT INTO masterdata.company_payment_settings(tenant_id,company_id,default_sales_method_id) VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002'); RAISE EXCEPTION 'cross-company accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
          BEGIN INSERT INTO masterdata.company_payment_settings(tenant_id,company_id,default_purchase_method_id) VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000001'); RAISE EXCEPTION 'wrong direction accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        END $$;""")

    def test_invalid_aggregate_rejected_at_deferred_check(self):
        self.check("""SET CONSTRAINTS ALL DEFERRED; DO $$ BEGIN
          BEGIN UPDATE masterdata.payment_term_installments SET percentage=40 WHERE sequence=1 AND payment_term_id='40000000-0000-0000-0000-000000000001'; SET CONSTRAINTS ALL IMMEDIATE; RAISE EXCEPTION 'bad total accepted'; EXCEPTION WHEN check_violation THEN NULL; END;
        END $$;""")

    def test_bp_role_default_direction_and_company(self):
        self.check("""INSERT INTO masterdata.business_partner(id,tenant_id,kind,code,legal_name) VALUES ('50000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','ORGANIZATION','BP','BP');
        INSERT INTO masterdata.company_business_partner(id,tenant_id,company_id,business_partner_id) VALUES ('60000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001');
        INSERT INTO masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code) VALUES ('10000000-0000-0000-0000-000000000001','60000000-0000-0000-0000-000000000001','SUPPLIER');
        DO $$ BEGIN
          BEGIN INSERT INTO masterdata.business_partner_payment_defaults(tenant_id,company_id,company_business_partner_id,role_code,payment_method_id) VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001','60000000-0000-0000-0000-000000000001','SUPPLIER','30000000-0000-0000-0000-000000000001'); RAISE EXCEPTION 'wrong BP direction accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
          BEGIN INSERT INTO masterdata.business_partner_payment_defaults(tenant_id,company_id,company_business_partner_id,role_code) VALUES ('10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000002','60000000-0000-0000-0000-000000000001','SUPPLIER'); RAISE EXCEPTION 'wrong BP company accepted'; EXCEPTION WHEN foreign_key_violation THEN NULL; END;
        END $$;""")

    def test_no_delete_privilege_for_master_records(self):
        self.check("""SET ROLE enginia360_app; DO $$ BEGIN
          BEGIN DELETE FROM masterdata.payment_methods; RAISE EXCEPTION 'delete accepted'; EXCEPTION WHEN insufficient_privilege THEN NULL; END;
        END $$; RESET ROLE;""")

if __name__ == '__main__': unittest.main()
