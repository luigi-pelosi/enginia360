#!/usr/bin/env python3
"""Published-byte/fixture-free own-time schema regressions; live SQL in run-r03b-tests.py."""
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='3a7d956da80692fa84bdfb7d4a489b5465c6e9c5'
class OwnTimeMigration(unittest.TestCase):
    def test_published_21_units_and_checksums_preserved_next_unit_is_22(self):
        manifest=json.loads((ROOT/'database/runtime/manifest.json').read_text())
        published=json.loads(subprocess.check_output(['git','show',BASE+':database/runtime/manifest.json'],cwd=ROOT,text=True))
        self.assertGreaterEqual(len(manifest),22);self.assertEqual(manifest[:21],published)
        for unit in manifest:
            path=ROOT/'database/runtime'/unit['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),unit['sha256'])
            if unit in published:self.assertEqual(path.read_bytes(),subprocess.check_output(['git','show',BASE+':database/runtime/'+unit['path']],cwd=ROOT))
        self.assertEqual(manifest[21]['id'],'0022_workshop_own_actual_time')
    def test_schema_owns_five_minimal_tables_and_does_not_seed_or_read_foreign_private_sql(self):
        sql=(ROOT/'database/runtime/migrations/0022_workshop_own_actual_time.sql').read_text()
        self.assertEqual(sql.count('CREATE TABLE workshop.'),5)
        self.assertNotRegex(sql,r'(?im)^\s*(INSERT|UPDATE|DELETE|TRUNCATE)\s')
        self.assertNotIn('SECURITY DEFINER',sql)
        for schema in ('inventory.','billing.','accounting.','organization_access.'):
            self.assertNotIn(schema,sql)
        self.assertIn('app.workshop_actor_membership_id',sql)
        self.assertIn('DEFERRABLE INITIALLY DEFERRED',sql)
        self.assertIn('FORCE ROW LEVEL SECURITY',sql)
if __name__=='__main__':unittest.main()
