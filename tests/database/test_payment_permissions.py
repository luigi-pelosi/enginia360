"""Payment permission parity and real PostgreSQL constraint checks.

Runtime cases require PAYMENTS_TEST_CONTAINER pointing to the isolated proof cluster
with the fresh baseline loaded into payments_test.
"""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
CODES = (
    'payment-methods.read', 'payment-methods.create', 'payment-methods.update',
    'payment-terms.read', 'payment-terms.create', 'payment-terms.update',
    'payment-settings.read', 'payment-settings.update',
    'payment-partner-defaults.read', 'payment-partner-defaults.update',
    'payment-schedule.preview', 'payment-resolution.read',
)

class PaymentPermissions(unittest.TestCase):
    def test_catalog_and_upgrade_share_exact_finite_permissions(self):
        catalog = (ROOT / 'backend/Modules/AccessControl/PermissionCatalog.cs').read_text()
        baseline = (ROOT / 'database/foundation.sql').read_text()
        migration = (ROOT / 'database/migrations/20261119_payments.sql').read_text()
        for code in CODES:
            self.assertIn('"' + code + '"', catalog)
            self.assertIn("'" + code + "'::text", baseline)
            self.assertIn("('" + code + "')", migration)
        self.assertNotIn('payment-methods.delete', catalog)
        self.assertNotIn('payment-terms.delete', catalog)
        self.assertIn('\\ir masterdata_payments.sql', baseline)

    @unittest.skipUnless(os.environ.get('PAYMENTS_TEST_CONTAINER'), 'requires isolated PostgreSQL proof')
    def test_constraint_accepts_catalog_but_not_unlisted_permissions(self):
        values = ','.join("('b0000000-0000-0000-0000-000000000001','%s','test',true)" % c for c in CODES)
        query = """BEGIN;
        INSERT INTO foundation.tenant(id,code,name) VALUES ('b0000000-0000-0000-0000-000000000001','permissions-proof','Proof');
        INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES %s;
        DO $$ BEGIN
          BEGIN INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES ('b0000000-0000-0000-0000-000000000001','payment-methods.delete','bad',true); RAISE EXCEPTION 'unexpected permission accepted'; EXCEPTION WHEN check_violation THEN NULL; END;
          BEGIN INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES ('b0000000-0000-0000-0000-000000000001','payment-schedule.read','bad',true); RAISE EXCEPTION 'unexpected permission accepted'; EXCEPTION WHEN check_violation THEN NULL; END;
        END $$;
        ROLLBACK;""" % values
        proc = subprocess.run(['docker','exec','-i',os.environ['PAYMENTS_TEST_CONTAINER'],'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','postgres','-d','payments_test'], input=query, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

if __name__ == '__main__':
    unittest.main()
