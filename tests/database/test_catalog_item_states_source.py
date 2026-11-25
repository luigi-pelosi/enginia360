"""Contratto sorgente limitato alla nuova estensione di ciclo di vita."""
from pathlib import Path
import re
import unittest
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]

class CatalogItemStatesSourceTests(unittest.TestCase):
    def test_three_final_statuses_default_active_and_activation_marker(self):
        sql=load_foundation_sql()
        self.assertIn("DEFAULT 'ACTIVE'",sql)
        self.assertIn("CHECK(status IN ('ACTIVE','SUSPENDED','ARCHIVED'))",sql)
        self.assertIn('activated_at',sql)
        self.assertIn('DEFERRABLE INITIALLY DEFERRED',sql)
        self.assertNotIn('DISABLE TRIGGER',sql)
    def test_final_item_checks_have_no_retired_statuses(self):
        sql=(ROOT/'database/masterdata_catalog.sql').read_text()
        self.assertNotRegex(sql,r"'DRAFT'|'INACTIVE'")
        self.assertNotIn('state-backfill',sql)
        self.assertNotIn('INSERT INTO foundation.role_permission',sql)
    def test_backend_exposes_only_new_states_and_exact_permission_actions(self):
        endpoint=(ROOT/'backend/Modules/Catalog/CatalogItemEndpoints.cs').read_text()
        pure=(ROOT/'backend/Modules/Catalog/CatalogItem.cs').read_text()
        for source in (endpoint,pure):
            self.assertNotIn('"DRAFT"',source);self.assertNotIn('"INACTIVE"',source)
            self.assertIn('"SUSPENDED"=>"deactivate"',source)
        self.assertIn('data["status"]=requestedStatus',endpoint)
        self.assertIn('id.HasValue || requestedStatus!="ARCHIVED"',endpoint)
        self.assertIn('if(!id.HasValue && activating) await Gate(ctx,db,"catalog-items.activate")',endpoint)
        self.assertIn('incrementRoot:!childWillWrite',endpoint)
if __name__=='__main__':unittest.main()
