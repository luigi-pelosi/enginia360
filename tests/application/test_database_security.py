"""Verifica rollback applicativo e privilegi del ruolo database."""

import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid

from test_api import Client


def sql(statement, check=True):
    return subprocess.run(
        ['docker', 'exec', '-i', os.environ.get('ENGINIA360_DB_CONTAINER', 'enginia360-foundation-db'), 'psql', '-U', 'postgres',
         '-d', os.environ.get('ENGINIA360_DB_DATABASE', 'enginia360'), '-X', '-At', '-v', 'ON_ERROR_STOP=1'],
        input=statement, text=True, capture_output=True, check=check,
    )


@unittest.skipUnless(os.environ.get('ENGINIA360_TEST_CREDENTIALS'), 'Richiede account temporaneo')
class DatabaseSecurityTests(unittest.TestCase):
    def test_audit_failure_rolls_back_business_insert(self):
        client = Client()
        credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
        self.assertEqual(client.login(credentials)[0], 200)
        code = 'qa-atomic-' + uuid.uuid4().hex
        sql("""
            CREATE FUNCTION foundation.verification_reject_audit() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                IF NEW.resource='tenants' AND NEW.action='create' THEN
                    RAISE EXCEPTION 'Verifica rollback audit';
                END IF;
                RETURN NEW;
            END $$;
            CREATE TRIGGER verification_reject_audit BEFORE INSERT ON foundation.audit_event
            FOR EACH ROW EXECUTE FUNCTION foundation.verification_reject_audit();
        """)
        try:
            status, body = client.request('/api/data/tenants', 'POST', {'code': code, 'name': 'Verifica atomicità'})
            self.assertEqual(status, 500)
            self.assertEqual(body, {'code': 'server_error'})
            self.assertEqual(sql(f"SELECT count(*) FROM foundation.tenant WHERE code='{code}'").stdout.strip(), '0')
        finally:
            sql('DROP TRIGGER verification_reject_audit ON foundation.audit_event; DROP FUNCTION foundation.verification_reject_audit();')

    def test_runtime_role_cannot_alter_audit_or_schema(self):
        for statement in (
            'SELECT * FROM foundation.audit_event LIMIT 1',
            'UPDATE foundation.audit_event SET action=action',
            'DELETE FROM foundation.audit_event',
            'TRUNCATE foundation.audit_event',
            'CREATE TABLE foundation.verification_forbidden (id integer)',
        ):
            with self.subTest(statement=statement):
                result = sql('BEGIN; SET LOCAL ROLE enginia360_app; ' + statement + '; ROLLBACK;', check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('permission denied', result.stderr)


if __name__ == '__main__':
    unittest.main()
