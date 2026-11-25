"""Contratti bounded per eliminazione tipologie; runtime separato su PostgreSQL."""
from pathlib import Path
import unittest
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]
class CatalogTypeDeletionSourceTests(unittest.TestCase):
    def test_read_only_preflight_and_dedicated_permission(self):
        text=(ROOT/'backend/Modules/Catalog/CatalogEndpoints.cs').read_text()
        preflight=text.split('private static async Task<IResult> TypeDeletionCheck',1)[1].split('private static async Task<IResult> DeleteType',1)[0]
        self.assertIn('"catalog-types.delete"',preflight)
        self.assertIn('canDelete=!await TypeInUse',preflight)
        for forbidden in ['db.Execute','db.Audit','true)','FOR UPDATE','catalog-items.read']:
            self.assertNotIn(forbidden,preflight)
        deletion=text.split('private static async Task<IResult> DeleteType',1)[1].split('private static async Task<IResult> DeleteCategory',1)[0]
        self.assertLess(deletion.index('pg_advisory_xact_lock'),deletion.index('Read(db,Types,tenant,id,true)'))
        for expected in ['expected_version_required','stale_version','item_type_in_use','after=(object?)null','db.Audit']:
            self.assertIn(expected,deletion)
        query=text.split('private static async Task<bool> TypeInUse',1)[1].split('private static async Task<IResult> TypeDeletionCheck',1)[0]
        self.assertNotIn('status',query)
    def test_final_type_deletion_is_guarded_and_does_not_cascade(self):
        sql=(ROOT/'database/masterdata_catalog.sql').read_text()
        self.assertIn('GRANT DELETE ON masterdata.catalog_item_type TO enginia360_app',sql)
        self.assertIn('Tipologia utilizzata',sql)
        self.assertNotIn('ON DELETE CASCADE',sql)
        self.assertNotIn('INSERT INTO foundation.role_permission',sql)
        self.assertIn('NEW.conversion_scope',sql)
    def test_only_finite_permission_is_added(self):
        source=(ROOT/'backend/Modules/AccessControl/PermissionCatalog.cs').read_text()
        self.assertIn('"catalog-types.delete"',source)
        resources=(ROOT/'backend/Api/Resources/Resources.cs').read_text()
        self.assertNotIn('["catalog-types"]',resources)
if __name__=='__main__':unittest.main()
