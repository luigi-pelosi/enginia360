"""La risorsa users gestisce direttamente la tabella user nel database isolato."""

import json
import os
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from test_api import Client
from user_rename_checks import query

PUBLIC_FIELDS = {'id', 'tenant_id', 'username', 'first_name', 'last_name', 'email', 'date_of_birth', 'phone_number', 'preferred_language', 'is_enabled', 'created_at', 'updated_at'}


@unittest.skipUnless(os.environ.get('ENGINIA360_TEST_CREDENTIALS') and
                     os.environ.get('ENGINIA360_DB_CONTAINER') in ('enginia360-user-rename-db', 'enginia360-user-details-db'),
                     'Richiede il database isolato della rinomina')
class UserCrudTests(unittest.TestCase):
    def test_users_crud_writes_the_user_table(self):
        client = Client()
        credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
        self.assertEqual(client.login(credentials)[0], 200)
        status, tenant = client.request('/api/data/tenants', 'POST', {
            'code': 'rename-' + uuid.uuid4().hex, 'name': 'Verifica rinomina',
        })
        self.assertEqual(status, 201)
        tenant_id = tenant['id']
        path = f'/api/data/users?tenantId={tenant_id}'
        user_id = None
        try:
            status, row = client.request(path, 'POST', {
                'username': 'operator', 'first_name': 'Operatore', 'last_name': 'Verifica', 'email': 'test@example.invalid',
            })
            self.assertEqual(status, 201)
            self.assertEqual(set(row), PUBLIC_FIELDS)
            user_id = row['id']
            target = f'/api/data/users/{user_id}?tenantId={tenant_id}'
            db = os.environ['ENGINIA360_DB_CONTAINER']
            self.assertEqual(query(db, f'''SELECT id FROM foundation."user"
                WHERE tenant_id='{tenant_id}' AND username='operator';'''), user_id)
            self.assertIn(user_id, [item['id'] for item in client.request(path)[1]['items']])
            status, changed = client.request(target, 'PUT', {'first_name': 'Aggiornato'})
            self.assertEqual(status, 200)
            self.assertEqual(set(changed), PUBLIC_FIELDS)
            self.assertEqual(query(db, f'''SELECT first_name FROM foundation."user" WHERE id='{user_id}';'''),
                             'Aggiornato')
            self.assertEqual(client.request(target, 'DELETE')[0], 204)
            self.assertEqual(query(db, f'''SELECT count(*) FROM foundation."user" WHERE id='{user_id}';'''), '0')
            user_id = None
        finally:
            if user_id:
                client.request(f'/api/data/users/{user_id}?tenantId={tenant_id}', 'DELETE')
            self.assertEqual(client.request(f'/api/data/tenants/{tenant_id}', 'DELETE')[0], 204)


if __name__ == '__main__':
    unittest.main()
