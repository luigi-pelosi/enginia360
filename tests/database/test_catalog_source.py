"""Contratti statici Catalogo; i vincoli effettivi sono provati separatamente su PostgreSQL isolato."""
from pathlib import Path
import unittest
from database.sql_source import load_foundation_sql

ROOT = Path(__file__).resolve().parents[2]

class CatalogSourceTests(unittest.TestCase):
    def test_catalog_schema_has_exact_scale_and_tenant_references(self):
        p = ROOT / 'database/masterdata_catalog.sql'
        self.assertTrue(p.exists(), 'Catalog SQL is not implemented')
        sql = load_foundation_sql()
        for table in ('catalog_unit_of_measure', 'catalog_category', 'catalog_item_type'):
            self.assertIn('CREATE TABLE masterdata.' + table, sql)
        self.assertIn('scale(factor_to_base)<=12', sql)
        self.assertIn('REFERENCES masterdata.catalog_category(tenant_id,id)', sql)
        self.assertIn('WITH RECURSIVE', sql)

if __name__ == '__main__': unittest.main()
