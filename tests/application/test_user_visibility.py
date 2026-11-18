"""Visibilità della propria utenza globale senza allargare i permessi tenant."""
import json
import os
from pathlib import Path
import unittest
import uuid
from test_api import Client, catalog_permission


@unittest.skipUnless(os.environ.get('ENGINIA360_DB_CONTAINER') in ('enginia360-self-visible-db', 'enginia360-rbac-db'),
                     'Richiede ambiente temporaneo visibilità')
class UserVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
        self.credentials = json.loads(self.path.read_text())
        self.root = Client()
        status, self.session = self.root.login(self.credentials)
        self.assertEqual(status, 200)
        if self.session['mustChangePassword']:
            password = uuid.uuid4().hex + '-Change!'
            self.assertEqual(self.root.request('/api/auth/password', 'PUT', {
                'currentPassword': self.credentials['password'], 'newPassword': password,
            })[0], 204)
            self.credentials['password'] = password
            self.path.write_text(json.dumps(self.credentials))
            self.root.token = None
        status, tenant = self.root.request('/api/data/tenants', 'POST', {
            'code': 'visible-' + uuid.uuid4().hex, 'name': 'Visibilità utenti',
        })
        self.assertEqual(status, 201)
        self.tenant = tenant
        self.users = []

    def tearDown(self):
        for user in reversed(self.users):
            self.root.request(f"/api/links/user-roles/{user['id']}?tenantId={self.tenant['id']}", 'PUT', {'ids': []})
            self.assertEqual(self.root.request(f"/api/data/users/{user['id']}?tenantId={self.tenant['id']}", 'DELETE')[0], 204)
        self.assertEqual(self.root.request(f"/api/data/tenants/{self.tenant['id']}", 'DELETE')[0], 204)

    def listing(self, suffix=''):
        status, result = self.root.request(f"/api/data/users?tenantId={self.tenant['id']}" + suffix)
        self.assertEqual(status, 200)
        return result

    def create_user(self):
        status, row = self.root.request(f"/api/data/users?tenantId={self.tenant['id']}", 'POST', {
            'username': 'operator', 'first_name': 'Operatore', 'last_name': 'Tenant', 'email': 'operator@example.invalid',
        })
        self.assertEqual(status, 201)
        self.users.append(row)
        return row

    def test_own_global_identity_is_listed_without_a_tenant_assignment(self):
        result = self.listing()
        self.assertEqual(result['total'], 1)
        self.assertEqual([row['id'] for row in result['items']], [self.session['id']])
        self.assertIsNone(result['items'][0]['tenant_id'])
        self.assertNotIn('is_super_admin', result['items'][0])
        self.assertNotIn('password_hash', result['items'][0])

    def test_count_search_and_pagination_include_self_once(self):
        user = self.create_user()
        self.assertEqual(self.listing()['total'], 2)
        first = self.listing('&pageSize=1&page=1')
        second = self.listing('&pageSize=1&page=2')
        self.assertEqual(first['total'], 2)
        self.assertEqual({first['items'][0]['id'], second['items'][0]['id']}, {self.session['id'], user['id']})
        searched = self.listing('&search=Operatore')
        self.assertEqual(searched['total'], 1)
        self.assertEqual(searched['items'][0]['id'], user['id'])
        self.assertEqual(self.listing('&search=not-a-match')['total'], 0)

    def test_other_global_admins_are_not_exposed(self):
        from test_database_security import sql
        other = str(uuid.uuid4())
        sql(f'''INSERT INTO foundation."user"(id,username,first_name,last_name,email,is_super_admin,password_hash)
            SELECT '{other}','other-platform','Altro','Admin','other@example.invalid',true,password_hash
            FROM foundation."user" WHERE id='{self.session['id']}';''')
        try:
            ids = {row['id'] for row in self.listing()['items']}
            self.assertIn(self.session['id'], ids)
            self.assertNotIn(other, ids)
        finally:
            sql(f'''DELETE FROM foundation."user" WHERE id='{other}';''')

    def test_tenant_user_cannot_see_global_admin(self):
        user = self.create_user()
        scope = '?tenantId=' + self.tenant['id']
        status, role = self.root.request('/api/data/roles' + scope, 'POST', {'code':'reader','name':'Lettura'})
        self.assertEqual(status, 201)
        permission = catalog_permission(self.root, self.tenant['id'], 'users.read')
        try:
            self.assertEqual(self.root.request('/api/links/role-permissions/' + role['id'] + scope, 'PUT', {'ids':[permission['id']]})[0], 204)
            self.assertEqual(self.root.request('/api/links/user-roles/' + user['id'] + scope, 'PUT', {'ids':[role['id']]})[0], 204)
            password = uuid.uuid4().hex + '-Initial!'
            self.assertEqual(self.root.request('/api/users/' + user['id'] + '/password' + scope, 'PUT', {'newPassword':password})[0], 204)
            client = Client()
            self.assertEqual(client.login({'username':'operator','password':password}, self.tenant['code'])[0], 200)
            self.assertEqual(client.request('/api/auth/password','PUT',{'currentPassword':password,'newPassword':uuid.uuid4().hex+'-Changed!'})[0], 204)
            client.token = None
            status, result = client.request('/api/data/users' + scope)
            self.assertEqual(status, 200)
            self.assertEqual([row['id'] for row in result['items']], [user['id']])
        finally:
            self.root.request('/api/links/user-roles/' + user['id'] + scope, 'PUT', {'ids':[]})
            self.root.request('/api/links/role-permissions/' + role['id'] + scope, 'PUT', {'ids':[]})
            self.root.request('/api/data/roles/' + role['id'] + scope, 'DELETE')

    def test_global_identity_stays_protected_from_tenant_mutations(self):
        user_id = self.session['id']
        target = f"/api/data/users/{user_id}?tenantId={self.tenant['id']}"
        self.assertEqual(self.root.request(target, 'PUT', {'is_enabled': False})[0], 404)
        self.assertEqual(self.root.request(target, 'DELETE')[0], 404)
        self.assertEqual(self.root.request(f"/api/users/{user_id}/password?tenantId={self.tenant['id']}", 'PUT',
                                           {'newPassword': uuid.uuid4().hex + '-Denied!'})[0], 404)
        self.assertEqual(self.root.request(f"/api/links/user-roles/{user_id}?tenantId={self.tenant['id']}")[0], 404)
        self.assertTrue(self.root.request('/api/session')[1]['isSuperAdmin'])


if __name__ == '__main__':
    unittest.main()
