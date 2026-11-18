"""Verifiche incrementali dei dati anagrafici utente sul solo ambiente isolato."""

import json
import os
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from test_api import Client
from user_rename_checks import query

CONTAINER = os.environ.get('ENGINIA360_DB_CONTAINER', '')
PUBLIC = {'id', 'tenant_id', 'username', 'first_name', 'last_name', 'email',
          'date_of_birth', 'phone_number', 'preferred_language', 'is_enabled',
          'created_at', 'updated_at'}


@unittest.skipUnless(CONTAINER == 'enginia360-user-details-db', 'Richiede il cluster temporaneo anagrafica')
class UserDetailsSchemaTests(unittest.TestCase):
    def test_personal_fields_replace_display_name(self):
        fields = json.loads(query(CONTAINER, """SELECT json_object_agg(column_name,is_nullable)
            FROM information_schema.columns WHERE table_schema='foundation' AND table_name='user';"""))
        self.assertNotIn('display_name', fields)
        for name in ['first_name', 'last_name', 'email', 'preferred_language']:
            self.assertEqual(fields.get(name), 'NO', name)
        for name in ['date_of_birth', 'phone_number']:
            self.assertEqual(fields.get(name), 'YES', name)


@unittest.skipUnless(CONTAINER == 'enginia360-user-details-db' and os.environ.get('ENGINIA360_TEST_CREDENTIALS'),
                     'Richiede backend e credenziali temporanei')
class UserDetailsApiTests(unittest.TestCase):
    def setUp(self):
        self.client = Client()
        credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
        self.assertEqual(self.client.login(credentials)[0], 200)
        status, tenant = self.client.request('/api/data/tenants', 'POST', {
            'code': 'profile-' + uuid.uuid4().hex, 'name': 'Verifica anagrafica',
        })
        self.assertEqual(status, 201)
        self.tenant = tenant['id']
        self.path = f'/api/data/users?tenantId={self.tenant}'

    def tearDown(self):
        status, response = self.client.request(self.path)
        if status == 200:
            for row in response['items']:
                if row['tenant_id'] != self.tenant:
                    continue
                self.assertEqual(self.client.request(f"/api/data/users/{row['id']}?tenantId={self.tenant}", 'DELETE')[0], 204)
        self.assertEqual(self.client.request(f'/api/data/tenants/{self.tenant}', 'DELETE')[0], 204)

    def valid(self):
        return {'username': 'operator', 'first_name': 'Anna Maria', 'last_name': "D'Amico",
                'email': 'operator@example.invalid'}

    def test_required_fields_reject_missing_blank_null_and_invalid_email(self):
        for field in ['first_name', 'last_name', 'email']:
            for value in ['missing', None, '', '   ']:
                body = self.valid()
                if value == 'missing':
                    del body[field]
                else:
                    body[field] = value
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.client.request(self.path, 'POST', body)[0], 400)
        for field, value in [('email', 'invalid'), ('email', 'Nome <a@example.invalid>'),
                             ('display_name', 'Non ammesso'), ('preferred_language', 'fr'),
                             ('preferred_language', None), ('date_of_birth', '2024-02-30'),
                             ('date_of_birth', '2999-01-01'), ('date_of_birth', '01/02/2000'),
                             ('date_of_birth', '2000-01-01T00:00:00Z'), ('phone_number', '1' * 51)]:
            with self.subTest(field=field, value=value):
                body = {**self.valid(), field: value}
                self.assertEqual(self.client.request(self.path, 'POST', body)[0], 400)
        self.assertEqual([row for row in self.client.request(self.path)[1]['items'] if row['tenant_id'] == self.tenant], [])

    def test_profile_persists_and_optional_fields_can_be_cleared(self):
        body = {**self.valid(), 'date_of_birth': '2000-02-29', 'phone_number': '+39 (06) 1234 5678',
                'preferred_language': 'en'}
        status, row = self.client.request(self.path, 'POST', body)
        self.assertEqual(status, 201)
        self.assertEqual(set(row), PUBLIC)
        for key, value in body.items():
            self.assertEqual(row[key], value)
        stored = json.loads(query(CONTAINER, f'''SELECT row_to_json(t) FROM foundation."user" t WHERE id='{row['id']}';'''))
        for key, value in body.items():
            self.assertEqual(stored[key], value)
        target = f"/api/data/users/{row['id']}?tenantId={self.tenant}"
        status, changed = self.client.request(target, 'PUT', {'date_of_birth': None, 'phone_number': None})
        self.assertEqual(status, 200)
        self.assertIsNone(changed['date_of_birth'])
        self.assertIsNone(changed['phone_number'])
        for field in ['first_name', 'last_name', 'email']:
            self.assertEqual(self.client.request(target, 'PUT', {field: ' '})[0], 400)
        persisted = next(item for item in self.client.request(self.path)[1]['items'] if item['id'] == row['id'])
        self.assertEqual(persisted, changed)

    def test_default_locale_and_login_full_name(self):
        status, row = self.client.request(self.path, 'POST', self.valid())
        self.assertEqual(status, 201)
        self.assertEqual(row['preferred_language'], 'it')
        target = f"/api/data/users/{row['id']}?tenantId={self.tenant}"
        self.assertEqual(self.client.request(target, 'PUT', {'preferred_language': 'en'})[0], 200)
        password = uuid.uuid4().hex + '-Verify!'
        self.assertEqual(self.client.request(f"/api/users/{row['id']}/password?tenantId={self.tenant}",
                                            'PUT', {'newPassword': password})[0], 204)
        tenant_code = query(CONTAINER, f"SELECT code FROM foundation.tenant WHERE id='{self.tenant}';")
        status, session = Client().login({'username': 'operator', 'password': password}, tenant_code)
        self.assertEqual(status, 200)
        self.assertEqual(session['displayName'], "Anna Maria D'Amico")
        self.assertEqual(session['preferredLanguage'], 'en')
        self.assertNotIn('display_name', row)


if __name__ == '__main__':
    unittest.main()
