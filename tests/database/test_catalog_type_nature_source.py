"""Contratto sorgente circoscritto; comportamento SQL/HTTP verificato separatamente."""
from pathlib import Path
import unittest
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]
class CatalogTypeNatureSourceTests(unittest.TestCase):
    def test_single_snapshot_metadata_only_on_single_type_reads(self):
        text=(ROOT/'backend/Modules/Catalog/CatalogEndpoints.cs').read_text()
        read=text.split('private static async Task<Dictionary<string,object?>?> Read',1)[1].split('private static string? Text',1)[0]
        self.assertIn('resource==Types?',read)
        self.assertIn('NOT EXISTS(SELECT 1 FROM masterdata.catalog_item i WHERE i.tenant_id=t.tenant_id AND i.item_type_id=t.id)',read)
        self.assertIn('canChangeKind',read)
        self.assertIn('SELECT t.*',read)
        self.assertIn('FOR UPDATE OF t',read)
        for forbidden in ['status','catalog-items.read','catalog-types.delete','TypeInUse','db.Scalar','db.Audit']:
            self.assertNotIn(forbidden,read)
        fields=text.split('Resource Types=',1)[1].split(';',1)[0]
        self.assertNotIn('canChangeKind',fields)
        listing=text.split('private static async Task<IResult> List',1)[1].split('private static async Task<List<',1)[0]
        self.assertNotIn('canChangeKind',listing)
    def test_save_lock_precedes_root_lock_and_kind_change_is_conditional(self):
        text=(ROOT/'backend/Modules/Catalog/CatalogEndpoints.cs').read_text()
        save=text.split('private static async Task<IResult> Save',1)[1].split('private static async Task<bool> TypeInUse',1)[0]
        self.assertIn('if(resource==Types && id.HasValue)',save)
        self.assertLess(save.index('pg_advisory_xact_lock'),save.index('Read(db,resource,tenant,id.Value,true)'))
        self.assertIn('before!=null && kind!=(string)before["kind"]!',save)
        self.assertIn('!await TypeInUse(db,tenant,id!.Value),409,"immutable_item_kind"',save)
        self.assertIn('resource.Fields.AsEnumerable()',save)
        self.assertIn('var after=await Read(db,resource,tenant,record)',save)
        self.assertIn('return Results.Json(after,statusCode:id.HasValue?200:201)',save)
    def test_final_guard_checks_any_reference_before_nature_change(self):
        sql=load_foundation_sql()
        self.assertIn('NEW.kind<>OLD.kind',sql)
        self.assertIn('EXISTS(SELECT 1 FROM masterdata.catalog_item WHERE tenant_id=NEW.tenant_id AND item_type_id=NEW.id)',sql)
        self.assertIn('Natura immutabile',sql)
    def test_final_guards_retain_advisory_lock_and_stock_rules(self):
        sql=load_foundation_sql()
        self.assertIn("hashtextextended('catalog:'||",sql)
        self.assertRegex(sql,r"CHECK\s*\(kind='GOOD' OR NOT default_track_stock\)")
        self.assertNotIn('DISABLE TRIGGER',sql)
    def test_guard_is_installed_once_not_replayed(self):
        sql=load_foundation_sql()
        self.assertEqual(len(__import__('re').findall(r'CREATE(?: OR REPLACE)? FUNCTION masterdata\.guard_catalog\(\)',sql)),1)
if __name__=='__main__':unittest.main()
