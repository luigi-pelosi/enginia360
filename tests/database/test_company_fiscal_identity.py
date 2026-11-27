"""Company/Site fiscal identity on a network-none disposable PostgreSQL cluster.

COMPANY_FISCAL_IDENTITY_DB_TESTS=1 python -m unittest tests.database.test_company_fiscal_identity -v
Never connects to a retained database. No dump capture or live credentials needed.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
import unittest
import uuid

from database.sql_source import load_foundation_sql
from tests.database import test_taxmanagement_runtime as phase1
from tests.database import test_company_tax_requirements as requirements

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('COMPANY_FISCAL_IDENTITY_DB_TESTS') == '1',
                     'Explicit isolated PostgreSQL opt-in required')
class CompanyFiscalIdentityTests(unittest.TestCase):
    @classmethod
    def sql(cls, statement, database='taxproof', check=True):
        result = subprocess.run(['docker', 'exec', '-i', cls.container, 'psql', '-U', 'postgres',
            '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', database], input=statement,
            text=True, capture_output=True, timeout=60)
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    @classmethod
    def setUpClass(cls):
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)
        cls.sql('CREATE DATABASE fresh;',database='postgres')
        cls.sql(load_foundation_sql(),database='fresh')

    root_sql = requirements.CompanyTaxRequirementsTests.root_sql
    registration_sql = requirements.CompanyTaxRequirementsTests.registration_sql
    profile_sql = requirements.CompanyTaxRequirementsTests.profile_sql
    chain = requirements.CompanyTaxRequirementsTests.chain
    setUp = requirements.CompanyTaxRequirementsTests.setUp
    scalar = phase1.TaxManagementRuntimeTests.scalar
    reject = phase1.TaxManagementRuntimeTests.reject


    def schema_dump(self, db):
        result = subprocess.run(['docker', 'exec', self.container, 'pg_dump', '-U', 'postgres',
            '--schema-only', '--schema=foundation', '--schema=masterdata', '--schema=taxmanagement', db],
            capture_output=True, text=True, timeout=60, check=True)
        return '\n'.join(l for l in result.stdout.splitlines() if not l.startswith(('\\restrict ', '\\unrestrict ')))


    def assert_tax_code_contract(self, db):
        # The current CF is nullable free text on TaxManagement, NOT Company.
        for literal in ('NULL', "'aZ / international 42'", "repeat('é',500)"):
            chain=self.chain(tax_code='original')
            result=self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+chain+
                f"UPDATE taxmanagement.company_tax_configurations SET tax_code={literal},version=version+1 WHERE id='{self.root}';"+
                f"SELECT tax_code IS NOT DISTINCT FROM {literal} FROM taxmanagement.company_tax_configurations WHERE id='{self.root}';ROLLBACK;",database=db)
            self.assertEqual(result.stdout,'t\n')
        for literal in ("''", "'   '", "E'\\t\\n'", "repeat('é',501)"):
            for operation in ('insert','update'):
                chain=self.chain(tax_code='original')
                command=(chain.replace("'original'",literal) if operation=='insert' else chain+
                    f"UPDATE taxmanagement.company_tax_configurations SET tax_code={literal},version=version+1 WHERE id='{self.root}';")
                with self.subTest(literal=literal,operation=operation):
                    rejected=self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+command+'ROLLBACK;',database=db,check=False)
                    self.assertNotEqual(rejected.returncode,0)
                    self.assertIn('company_tax_configurations_tax_code_check',rejected.stderr)


    def test_fresh_tax_code_boundaries_without_format_or_uniqueness_invention(self):
        self.assert_tax_code_contract('taxproof')


    def assert_site_without_identity(self, db):
        result=self.sql(f"BEGIN;INSERT INTO foundation.site(tenant_id,company_id,name,address,city,province,postal_code,country_code) VALUES('{self.tenant}','{self.company}','Physical','Street','City','Region','123','US');"+
            "SELECT count(*) FROM pg_attribute WHERE attrelid IN ('foundation.site'::regclass,'foundation.company'::regclass) AND NOT attisdropped AND attname IN ('vat_number','tax_code');"+
            "SELECT count(*) FROM pg_constraint WHERE conrelid='foundation.site'::regclass AND conname='site_tax_identity_check';ROLLBACK;",database=db)
        self.assertEqual(result.stdout,'0\n0\n')


    def test_fresh_company_optional_text_and_site_without_fiscal_fields(self):
        self.assert_site_without_identity('taxproof')

    def test_final_schema_fiscal_identity_columns(self):
        self.assertEqual(self.sql("SELECT table_schema,table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE (table_schema,table_name) IN (('foundation','company'),('foundation','site'),('taxmanagement','company_tax_configurations')) AND column_name IN ('tax_code','vat_number') ORDER BY 1,2,3;",database='taxproof').stdout,
            'taxmanagement|company_tax_configurations|tax_code|text|YES\n')

    def test_current_cf_edit_preserves_company_site_rows_and_schema(self):
        self.sql('BEGIN;'+self.chain(tax_code='Original')+'COMMIT;',database='taxproof')
        before=self.sql('SELECT row_to_json(c) FROM foundation.company c ORDER BY id;SELECT row_to_json(s) FROM foundation.site s ORDER BY id;',database='taxproof').stdout
        schema=self.schema_dump('taxproof')
        self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.company_tax_configurations SET tax_code='Edited / international',version=version+1 WHERE id='{self.root}';",database='taxproof')
        self.assertEqual(self.sql('SELECT row_to_json(c) FROM foundation.company c ORDER BY id;SELECT row_to_json(s) FROM foundation.site s ORDER BY id;',database='taxproof').stdout,before)
        self.assertEqual(self.schema_dump('taxproof'),schema)

    def test_current_cf_duplicate_international_values_do_not_create_identity_or_uniqueness(self):
        other_company,other_root,other_reg=[str(uuid.uuid4()) for _ in range(3)]
        value='aZ / international 42'
        command=(self.chain(tax_code=value)+
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{other_company}','{self.tenant}','Second');"+
            self.root_sql(id=other_root,company_id=other_company,tax_code=value)+
            self.registration_sql(id=other_reg,company_tax_configuration_id=other_root,tax_identifier='IT00000000000')+
            self.profile_sql(id=str(uuid.uuid4()),company_tax_registration_id=other_reg))
        result=self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+command+
            f"SELECT count(*) FROM taxmanagement.company_tax_configurations WHERE tenant_id='{self.tenant}' AND tax_code='{value}';ROLLBACK;",database='taxproof')
        self.assertEqual(result.stdout,'2\n')


if __name__ == '__main__':
    unittest.main()
