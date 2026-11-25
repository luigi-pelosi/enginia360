"""Contratto finale Catalogo multi-company."""
from pathlib import Path
import re
import unittest
from database.sql_source import load_foundation_sql

ROOT = Path(__file__).resolve().parents[2]

class CatalogCompaniesSourceTests(unittest.TestCase):
    def test_additive_table_and_tenant_foreign_keys(self):
        sql = load_foundation_sql()
        self.assertIn('CREATE TABLE masterdata.catalog_item_company', sql)
        for target, column in [('masterdata.catalog_item','item_id'), ('foundation.company','company_id'), ('masterdata.catalog_unit_of_measure','default_sales_uom_id'), ('masterdata.catalog_unit_of_measure','default_purchase_uom_id')]:
            self.assertRegex(sql, rf'FOREIGN KEY\s*\(tenant_id,\s*{column}\) REFERENCES {target}\(tenant_id,\s*id\) ON DELETE RESTRICT')
        self.assertIn('UNIQUE(tenant_id,company_id,item_id)', sql)
        self.assertIn('CHECK(version BETWEEN 1 AND 9007199254740991)', sql)
        self.assertNotIn('INSERT INTO foundation.role_permission',sql)
        self.assertIn("hashtextextended('catalog:'||", sql)
        self.assertIn('REVOKE ALL ON FUNCTION', sql)

    def test_finite_company_permissions_and_atomic_baseline(self):
        sql=load_foundation_sql()
        self.assertEqual(set(re.findall(r'catalog-item-companies\.[a-z_]+',sql)), {'catalog-item-companies.read','catalog-item-companies.create','catalog-item-companies.update'})
        self.assertNotIn('INSERT INTO foundation.role_permission',sql)
        self.assertIn('BEGIN;',sql);self.assertIn('COMMIT;',sql)

if __name__ == '__main__':
    unittest.main()
