"""Contratti finali delle nature; le prove runtime verificano SQL e handler reali."""
from pathlib import Path
import unittest
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]
class CatalogNaturesSourceTests(unittest.TestCase):
    def test_four_natures_and_five_numbering_entities(self):
        sql=load_foundation_sql()
        for kind in ('GOOD','INTANGIBLE','SERVICE','CHARGE'):
            self.assertIn("'"+kind+"'",sql)
            self.assertIn("'CATALOG_"+kind+"'",sql)
        self.assertIn("'BUSINESS_PARTNER'",sql)
        self.assertRegex(sql,r"CHECK\s*\(kind='GOOD' OR NOT default_track_stock\)")
    def test_final_baseline_is_atomic_and_does_not_preseed_tenants(self):
        sql=load_foundation_sql()
        self.assertIn('BEGIN;',sql);self.assertIn('COMMIT;',sql)
        self.assertNotIn('INSERT INTO foundation.tenant',sql)
    def test_existing_guards_already_cover_new_natures_without_replacement(self):
        historical=load_foundation_sql()
        for invariant in ("IF new_kind<>old_kind", "entity_type='CATALOG_'||new_kind", "IF new_kind<>'GOOD'"):
            self.assertIn(invariant,historical)
        self.assertIn("NEW.kind<>OLD.kind",load_foundation_sql())
    def test_four_independent_prefixes_and_kind_length(self):
        kernel=(ROOT/'backend/Modules/Numbering/NumberingKernel.cs').read_text()
        for entity,prefix in [('BUSINESS_PARTNER','BP-'),('CATALOG_GOOD','ART-'),('CATALOG_SERVICE','SRV-'),('CATALOG_INTANGIBLE','IMM-'),('CATALOG_CHARGE','ONR-')]:
            self.assertIn('"'+entity+'"=>"'+prefix+'"',kernel)
        endpoints=(ROOT/'backend/Modules/Catalog/CatalogEndpoints.cs').read_text()
        self.assertIn('Text(values,"kind",before,10,true)',endpoints)
        for kind in ('GOOD','INTANGIBLE','SERVICE','CHARGE'):
            self.assertIn('"'+kind+'"=>"CATALOG_'+kind+'"',endpoints)
if __name__=='__main__':unittest.main()
