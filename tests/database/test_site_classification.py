"""Classificazione sedi: SQL su copia isolata, nessuna scrittura sul principale."""
import json
import os
import subprocess
import unittest

from dbbaseline import CONTAINER, DATABASE, sql as baseline_sql


def sql(statement):
    return baseline_sql(statement, check=False)


def fixture(body):
    return sql("BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('90000000-0000-0000-0000-000000000001','site-proof','Prova sedi');"
               "INSERT INTO foundation.company(id,tenant_id,name) VALUES('90000000-0000-0000-0000-000000000002','90000000-0000-0000-0000-000000000001','Azienda prova');"
               "INSERT INTO foundation.site(id,tenant_id,company_id,name,vat_number,tax_code,address,city,province,postal_code,country_code) VALUES('90000000-0000-0000-0000-000000000003','90000000-0000-0000-0000-000000000001','90000000-0000-0000-0000-000000000002','Sede prova','VAT preservata','CF preservato','Via prova','Roma','RM','00100','IT');"
               + body + ';ROLLBACK;')


class SiteClassificationDatabaseTests(unittest.TestCase):
    def test_functions_are_empty_nonnullable_array_without_legal_default(self):
        result = fixture("SELECT json_build_object('functions',functions,'site_type',site_type,'vat_number',vat_number,'tax_code',tax_code) FROM foundation.site WHERE id='90000000-0000-0000-0000-000000000003'")
        self.assertEqual(result.returncode, 0, result.stderr)
        value = next(json.loads(line) for line in result.stdout.splitlines() if line.startswith('{'))
        self.assertEqual(value, {'functions': [], 'site_type': None, 'vat_number': 'VAT preservata', 'tax_code': 'CF preservato'})

    def test_legal_classification_accepts_only_exact_optional_choices(self):
        for value in ('LEGAL', 'LOCAL_UNIT', 'SECONDARY', None):
            with self.subTest(value=value):
                literal = 'NULL' if value is None else "'" + value + "'"
                result = fixture('UPDATE foundation.site SET site_type=' + literal)
                self.assertEqual(result.returncode, 0, result.stderr)
        for value in ('OFFICE', 'legal', '', 'WAREHOUSE'):
            with self.subTest(invalid=value):
                result = fixture("UPDATE foundation.site SET site_type='" + value + "'")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('site_type_check', result.stderr)

    def test_multiple_functions_are_sets_with_no_unknown_duplicate_or_null_items(self):
        for value in ("ARRAY['OPERATIONAL','WAREHOUSE','TECHNICAL_SERVICE']", "ARRAY[]::text[]",
                      "ARRAY['RETAIL','LOGISTICS','MANAGEMENT','PRODUCTION','COMMERCIAL','ADMINISTRATIVE']"):
            result = fixture('UPDATE foundation.site SET functions=' + value)
            self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("ARRAY['UNKNOWN']", "ARRAY['OPERATIONAL','OPERATIONAL']", "ARRAY[NULL]::text[]",
                      "ARRAY['OPERATIONAL',NULL]", "ARRAY[['OPERATIONAL','WAREHOUSE']]", "'[0:0]={WAREHOUSE}'::text[]"):
            with self.subTest(invalid=value):
                result = fixture('UPDATE foundation.site SET functions=' + value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('site_functions_check', result.stderr)
        result = fixture('UPDATE foundation.site SET functions=NULL')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('not-null constraint', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
