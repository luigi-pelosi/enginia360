"""Regressioni HTTP del modello utente unico su dati legacy isolati."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import unittest

os.environ['ENGINIA360_TEST_BASE'] = 'https://vmi3659251.tailfcced0.ts.net:8443'
os.environ['ENGINIA360_TEST_ORIGIN'] = os.environ['ENGINIA360_TEST_BASE']
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from test_api import Client

PRIVATE = Path('/root/.config/enginia360/account-migration')
PUBLIC_FIELDS = {'id', 'tenant_id', 'username', 'display_name', 'email', 'is_enabled', 'created_at', 'updated_at'}


class UnifiedAccountApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((PRIVATE / 'cases.json').read_text())
        cls.client = Client()
        status, session = cls.client.login(json.loads((PRIVATE / 'credentials.json').read_text()))
        if status != 200:
            raise AssertionError(f'Login amministrativo isolato: {status}')
        cls.tenant = cls.cases['first_tenant']

    def listing(self):
        status, response = self.client.request(f'/api/data/users?tenantId={self.tenant}&pageSize=100')
        self.assertEqual(status, 200)
        for row in response['items']:
            self.assertEqual(set(row), PUBLIC_FIELDS)
        return {row['username']: row for row in response['items']}

    def case(self, username):
        return next(row for row in self.cases['users'] if row['tenant_id'] == self.tenant and row['username'] == username)

    def reset(self, user_id, password):
        self.assertEqual(self.client.request(f'/api/users/{user_id}/password?tenantId={self.tenant}', 'PUT', {'newPassword': password})[0], 204)

    def change(self, client, old):
        new = secrets.token_urlsafe(24)
        self.assertEqual(client.request('/api/auth/password', 'PUT', {'currentPassword': old, 'newPassword': new})[0], 204)
        client.token = None
        return new

    def create(self, resource, data):
        status, row = self.client.request(f'/api/data/{resource}?tenantId={self.tenant}', 'POST', data)
        self.assertEqual(status, 201)
        return row

    def test_00_user_id_is_canonical_account_id(self):
        reader = self.case('reader')
        self.assertEqual(self.listing()['reader']['id'], reader['account_id'])
        collision = self.listing()['collision-pending']
        self.assertNotEqual(collision['id'], self.cases['global_id'])
        self.assertNotIn(self.cases['global_id'], [row['id'] for row in self.listing().values()])

    def test_01_existing_password_and_rbac_survive(self):
        reader = self.case('reader')
        limited = Client()
        status, session = limited.login({'username': reader['username'], 'password': reader['password']}, reader['tenant_code'])
        self.assertEqual(status, 200)
        self.assertEqual(session['id'], reader['account_id'])
        self.assertEqual(session['permissions'], ['companies.read'])
        self.assertEqual(limited.request(f'/api/data/companies?tenantId={self.tenant}')[0], 200)
        self.assertEqual(limited.request(f"/api/data/companies?tenantId={self.cases['second_tenant']}")[0], 403)
        self.assertEqual(limited.request(f'/api/data/companies?tenantId={self.tenant}', 'POST', {'code': 'denied', 'name': 'Negato'})[0], 403)

    def test_02_pending_user_activates_without_a_second_entity(self):
        row = self.listing()['pending']
        password = secrets.token_urlsafe(24)
        pending = Client()
        self.assertEqual(pending.login({'username': 'pending', 'password': password}, 'migration-a')[0], 401)
        self.reset(row['id'], password)
        status, session = pending.login({'username': 'pending', 'password': password}, 'migration-a')
        self.assertEqual(status, 200)
        self.assertEqual(session['id'], row['id'])
        self.assertTrue(session['mustChangePassword'])
        self.change(pending, password)
        self.assertEqual(pending.request(f'/api/data/companies?tenantId={self.tenant}')[0], 200)
        self.assertEqual(self.listing()['pending']['id'], row['id'])

    def test_03_password_reset_does_not_enable_disabled_users(self):
        for username in ('disabled-profile', 'disabled-account'):
            with self.subTest(username=username):
                row = self.listing()[username]
                self.assertFalse(row['is_enabled'])
                password = secrets.token_urlsafe(24)
                self.reset(row['id'], password)
                self.assertFalse(self.listing()[username]['is_enabled'])
                self.assertEqual(Client().login({'username': username, 'password': password}, 'migration-a')[0], 401)

    def test_04_crud_projection_and_protected_fields(self):
        row = self.create('users', {'username': 'new-unified', 'display_name': 'Nuovo utente', 'email': 'new@example.invalid', 'is_enabled': False})
        self.assertEqual(set(row), PUBLIC_FIELDS)
        status, updated = self.client.request(f"/api/data/users/{row['id']}?tenantId={self.tenant}", 'PUT', {'display_name': 'Nome aggiornato', 'email': 'updated@example.invalid'})
        self.assertEqual(status, 200)
        self.assertEqual(set(updated), PUBLIC_FIELDS)
        self.assertEqual(updated['email'], 'updated@example.invalid')
        for field, value in (
            ('is_super_admin', True), ('password_hash', 'not-a-hash'),
            ('security_stamp', self.cases['global_id']), ('user_id', self.cases['global_id']),
            ('tenant_id', self.cases['second_tenant']),
        ):
            with self.subTest(field=field):
                self.assertEqual(self.client.request(f"/api/data/users/{row['id']}?tenantId={self.tenant}", 'PUT', {field: value})[0], 400)
        password = secrets.token_urlsafe(24)
        self.reset(row['id'], password)
        self.assertFalse(self.listing()['new-unified']['is_enabled'])
        self.assertEqual(self.client.request(f"/api/data/users/{row['id']}?tenantId={self.tenant}", 'PUT', {'is_enabled': True})[0], 200)
        status, session = Client().login({'username': 'new-unified', 'password': password}, 'migration-a')
        self.assertEqual(status, 200)
        self.assertEqual(session['id'], row['id'])

    def test_05_self_update_does_not_restore_stale_ef_fields(self):
        user = self.create('users', {'username': 'self-editor', 'display_name': 'Editor', 'is_enabled': True})
        role = self.create('roles', {'code': 'self-editor', 'name': 'Gestione utenti'})
        permission = self.create('permissions', {'code': 'users.write', 'name': 'Modifica utenti'})
        for relation, owner, ids in (
            ('role-permissions', role['id'], [permission['id']]), ('user-roles', user['id'], [role['id']]),
        ):
            self.assertEqual(self.client.request(f'/api/links/{relation}/{owner}?tenantId={self.tenant}', 'PUT', {'ids': ids})[0], 204)
        password = secrets.token_urlsafe(24)
        self.reset(user['id'], password)
        editor = Client()
        self.assertEqual(editor.login({'username': 'self-editor', 'password': password}, 'migration-a')[0], 200)
        password = self.change(editor, password)
        status, updated = editor.request(f"/api/data/users/{user['id']}?tenantId={self.tenant}", 'PUT', {'username': 'self-renamed', 'display_name': 'Editor aggiornato', 'email': 'self@example.invalid'})
        self.assertEqual(status, 200)
        self.assertEqual(updated['username'], 'self-renamed')
        self.assertEqual(updated['display_name'], 'Editor aggiornato')
        self.assertEqual(updated['email'], 'self@example.invalid')
        self.assertEqual(set(updated), PUBLIC_FIELDS)
        self.assertEqual(editor.request('/api/session')[0], 401)
        status, session = Client().login({'username': 'self-renamed', 'password': password}, 'migration-a')
        self.assertEqual(status, 200)
        self.assertEqual(session['id'], user['id'])
        self.assertEqual(session['displayName'], 'Editor aggiornato')

    def test_06_global_admin_cannot_be_mutated_as_tenant_user(self):
        for method, body in (('PUT', {'is_enabled': False}), ('DELETE', None)):
            with self.subTest(method=method):
                status, _ = self.client.request(f"/api/data/users/{self.cases['global_id']}?tenantId={self.tenant}", method, body)
                self.assertEqual(status, 404)
        self.assertTrue(self.client.request('/api/session')[1]['isSuperAdmin'])


if __name__ == '__main__':
    unittest.main()
