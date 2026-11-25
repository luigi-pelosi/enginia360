"""Verifiche statiche read-only degli invarianti finali Catalogo."""
from pathlib import Path
import re
import unittest
from database.sql_source import load_foundation_sql

ROOT=Path(__file__).resolve().parents[2]

class CatalogItemsSourceTests(unittest.TestCase):
    def test_final_item_tables_are_unique_and_tenant_scoped(self):
        sql=load_foundation_sql()
        tables=re.findall(r'CREATE TABLE masterdata\.([a-z_]+)',sql)
        for table in ['catalog_item','catalog_item_code','catalog_item_identifier','catalog_item_unit','catalog_item_physical_data','catalog_brand','catalog_item_company']:
            self.assertEqual(tables.count(table),1)
        self.assertNotIn('ENABLE ROW LEVEL SECURITY',sql)

    def test_unit_scope_is_final_not_an_upgrade(self):
        sql=load_foundation_sql()
        self.assertIn("conversion_scope='ITEM' AND factor_to_base IS NULL AND NOT is_base",sql)
        self.assertIn('FUNCTION masterdata.guard_catalog()',sql)
        self.assertIn('FUNCTION masterdata.check_catalog_base()',sql)

    def test_finite_item_permissions_and_no_role_grants(self):
        sql=load_foundation_sql()
        codes=set(re.findall(r"'((?:catalog-items|catalog-brands)\.[a-z]+)'",sql))
        expected={'catalog-items.'+action for action in ('read','create','update','activate','deactivate','archive')}|{'catalog-brands.'+action for action in ('read','create','update')}
        self.assertEqual(codes,expected)
        self.assertNotIn('INSERT INTO foundation.role_permission',sql)

    def test_sql_invariants_and_safe_numeric_storage(self):
        sql=load_foundation_sql()
        self.assertIn('ON DELETE RESTRICT',sql)
        self.assertNotIn('ON DELETE CASCADE',(ROOT/'database/masterdata_catalog.sql').read_text())
        self.assertIn('Registro codici append-only',sql)
        self.assertIn('catalog_item_reserved_code_unique',sql)
        self.assertIn("WHERE identifier_type IN ('GTIN','BARCODE')",sql)
        self.assertIn('DEFERRABLE INITIALLY DEFERRED',sql)
        self.assertIn("n NOT IN (8,12,13,14)",sql)
        self.assertIn('scale(conversion_numerator)<=12',sql)
        self.assertNotRegex(sql,r'\b(?:float|real|double precision)\b')
        self.assertIn('catalog_item_physical_data WHERE tenant_id=owner AND item_id=OLD.id',sql)

    def test_api_routes_version_and_no_root_delete_or_allocate_endpoint(self):
        source=(ROOT/'backend/Modules/Catalog/CatalogItemEndpoints.cs').read_text()
        for route in ('/api/catalog/item-options','/api/catalog/items','/physical-data','/convert','/status'):
            self.assertIn(route,source)
        self.assertIn('CatalogEndpoints.MapBrands(app)',source)
        self.assertIn('NumberingKernel.Allocate',source)
        self.assertIn('CatalogConversion.ConvertRatios',source)
        self.assertIn('"ACTIVE"=>"activate"',source)
        self.assertIn('expectedVersion',source)
        self.assertNotIn('MapDelete("/api/catalog/items/{id:guid}"',source)
        self.assertNotRegex(source,r'Map\w+\([^\n]*allocate')
        self.assertIn('["GOOD"]=new {mode=good.Mode}',source)
        self.assertIn('["SERVICE"]=new {mode=service.Mode}',source)

if __name__=='__main__':unittest.main()
