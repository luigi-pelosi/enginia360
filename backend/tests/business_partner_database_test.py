"""Vincoli BP reali: eseguire soltanto nel container effimero esplicito."""
import os
import subprocess
import unittest
import uuid


@unittest.skipUnless(os.environ.get('BP_DATABASE_PROOF') == '1', 'Richiede cluster isolato BP')
class BusinessPartnerDatabaseTests(unittest.TestCase):
    def sql(self, sql, database='bp_fresh'):
        return subprocess.run(['docker', 'exec', '-i', os.environ.get('BP_DATABASE_CONTAINER', 'enginia360-bp-proof-db'), 'psql', '-X', '-U', 'postgres', '-d', database, '-v', 'ON_ERROR_STOP=1', '-v', 'VERBOSITY=verbose', '-At'], input=sql, text=True, capture_output=True)

    def fixture(self, extra):
        tenant, other, partner = (str(uuid.uuid4()) for _ in range(3))
        sql = f"""BEGIN;
INSERT INTO foundation.tenant(id,code,name) VALUES('{tenant}','{tenant}','Proof'),('{other}','{other}','Other');
INSERT INTO masterdata.business_partner(id,tenant_id,kind,code,legal_name) VALUES('{partner}','{tenant}','ORGANIZATION','BP-1','Proof');
"""
        return self.sql(sql + extra.format(t=tenant, o=other, p=partner) + '\nROLLBACK;')

    def test_01_tax_normalized_value_cannot_lie(self):
        result = self.fixture("INSERT INTO masterdata.business_partner_tax_identifier(tenant_id,business_partner_id,country_code,identifier_type,value,normalized_value) VALUES('{t}','{p}','DE','FOREIGN_TAX_ID','de-123','FAKE');")
        self.assertNotEqual(result.returncode, 0, 'Database accepted a fabricated normalization')
        self.assertIn('23514', result.stderr)

    def test_02_cross_tenant_children_refused(self):
        result = self.fixture("INSERT INTO masterdata.business_partner_contact_channel(tenant_id,business_partner_id,channel_type,value) VALUES('{o}','{p}','EMAIL','a@example.test');")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('23503', result.stderr)

    def test_03_code_immutable(self):
        result = self.fixture("UPDATE masterdata.business_partner SET code='REWRITE' WHERE id='{p}';")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('23514', result.stderr)

    def test_04_physical_delete_refused(self):
        result = self.fixture("DELETE FROM masterdata.business_partner WHERE id='{p}';")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('23514', result.stderr)

    def test_05_scope_company_entity_and_reset_are_bounded(self):
        for column, value in [('scope', "'COMPANY'"), ('company_id', "'{o}'"), ('entity_type', "'ORDER'"), ('reset_policy', "'YEARLY'")]:
            result = self.fixture("INSERT INTO foundation.numbering_series(tenant_id,mode,prefix,padding,"+column+") VALUES('{t}','AUTO','BP-',6,"+value+");")
            self.assertNotEqual(result.returncode, 0, column)
            self.assertIn('23514', result.stderr)

    def test_06_used_counter_cannot_decrease_or_reset(self):
        base = "INSERT INTO foundation.numbering_series(id,tenant_id,mode,prefix,padding) VALUES('{p}','{t}','AUTO','BP-',6); INSERT INTO foundation.numbering_counter(series_id,tenant_id,next_number,used) VALUES('{p}','{t}',10,true);"
        for change in ['next_number=1', 'used=false']:
            result = self.fixture(base + "UPDATE foundation.numbering_counter SET "+change+" WHERE series_id='{p}';")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('23514', result.stderr)

    def test_07_runtime_has_no_delete_or_ddl_authority(self):
        for database in ['bp_fresh', 'bp_incremental']:
            result = self.sql("SELECT has_table_privilege('enginia360_app','masterdata.business_partner','SELECT,INSERT,UPDATE'),has_table_privilege('enginia360_app','masterdata.business_partner','DELETE'),has_table_privilege('enginia360_app','foundation.numbering_series','DELETE'),has_schema_privilege('enginia360_app','foundation','CREATE'),has_schema_privilege('enginia360_app','masterdata','USAGE'),has_schema_privilege('enginia360_app','masterdata','CREATE'),EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname='masterdata' AND a.grantee=0);", database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 't|f|f|f|t|f|f')


if __name__ == '__main__':
    unittest.main(verbosity=2)
