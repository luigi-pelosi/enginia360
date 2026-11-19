"""Phase 2 real PostgreSQL proof; explicitly isolated container only."""
import os
import subprocess
import unittest
import uuid

@unittest.skipUnless(os.environ.get('BP_PHASE2_DATABASE_PROOF') == '1', 'isolated phase2 PostgreSQL required')
class Phase2DatabaseTests(unittest.TestCase):
    def sql(self, text):
        return subprocess.run(['docker','exec','-i',os.environ.get('BP_PHASE2_DATABASE_CONTAINER','enginia360-bp-phase2-db'),'psql','-X','-U','postgres','-d','phase2','-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose','-At'],input=text,text=True,capture_output=True)
    def test_01_three_tables_have_same_tenant_foreign_keys_and_no_relationship_delete(self):
        result=self.sql("SELECT to_regclass('masterdata.company_business_partner') IS NOT NULL,to_regclass('masterdata.company_business_partner_role') IS NOT NULL,to_regclass('foundation.role_company') IS NOT NULL;")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'t|t|t')
        result=self.sql("SELECT has_table_privilege('enginia360_app','masterdata.company_business_partner','DELETE'),has_table_privilege('enginia360_app','masterdata.company_business_partner_role','DELETE'),has_table_privilege('enginia360_app','foundation.role_company','SELECT,INSERT,DELETE');")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'f|f|t')
    def fixture(self, tail):
        t,o,c,b,r=(str(uuid.uuid4()) for _ in range(5))
        return self.sql(f"BEGIN; INSERT INTO foundation.tenant(id,code,name) VALUES('{t}','{t}','A'),('{o}','{o}','B'); INSERT INTO foundation.company(id,tenant_id,name) VALUES('{c}','{t}','C'); INSERT INTO masterdata.business_partner(id,tenant_id,kind,code,legal_name) VALUES('{b}','{t}','ORGANIZATION','BP','BP'); INSERT INTO masterdata.company_business_partner(id,tenant_id,company_id,business_partner_id) VALUES('{r}','{t}','{c}','{b}'); "+tail.format(t=t,o=o,c=c,b=b,r=r)+' ROLLBACK;')
    def test_02_cross_tenant_relation_refused(self):
        r=self.fixture("INSERT INTO masterdata.company_business_partner(tenant_id,company_id,business_partner_id) VALUES('{o}','{c}','{b}');")
        self.assertNotEqual(r.returncode,0);self.assertIn('23503',r.stderr)
    def test_03_relation_and_role_history_cannot_be_deleted(self):
        for sql in ["DELETE FROM masterdata.company_business_partner WHERE id='{r}';", "INSERT INTO masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code) VALUES('{t}','{r}','CUSTOMER'); DELETE FROM masterdata.company_business_partner_role WHERE company_business_partner_id='{r}';"]:
            r=self.fixture(sql);self.assertNotEqual(r.returncode,0);self.assertIn('23514',r.stderr)
    def test_04_duplicate_relation_and_role_refused(self):
        for sql in ["INSERT INTO masterdata.company_business_partner(tenant_id,company_id,business_partner_id) VALUES('{t}','{c}','{b}');", "INSERT INTO masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code) VALUES('{t}','{r}','CUSTOMER'),('{t}','{r}','CUSTOMER');"]:
            r=self.fixture(sql);self.assertNotEqual(r.returncode,0);self.assertIn('23505',r.stderr)
    def test_05_identity_and_history_fields_immutable(self):
        for sql in ["UPDATE masterdata.company_business_partner SET business_partner_id=gen_random_uuid() WHERE id='{r}';", "UPDATE masterdata.company_business_partner SET created_at=now()+interval '1 day' WHERE id='{r}';"]:
            r=self.fixture(sql);self.assertNotEqual(r.returncode,0);self.assertIn('23514',r.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
