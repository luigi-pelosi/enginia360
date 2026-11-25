"""Verifiche HTTP locali della foundation, con account di prova dedicato."""

import http.cookiejar
import json
import os
from pathlib import Path
import unittest
import urllib.error
import urllib.request
import urllib.parse
import uuid

BASE = os.environ.get('ENGINIA360_TEST_BASE', 'https://vmi3659251.tailfcced0.ts.net:8080')
ORIGIN = os.environ.get('ENGINIA360_TEST_ORIGIN', 'https://vmi3659251.tailfcced0.ts.net:8080')
CREDENTIAL_PATH = os.environ.get('ENGINIA360_TEST_CREDENTIALS')


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self.token = None

    def request(self, path, method='GET', data=None, csrf=True, origin=ORIGIN):
        headers = {'Origin': origin, 'Host': urllib.parse.urlsplit(ORIGIN).netloc, 'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        if method not in ('GET', 'HEAD') and csrf:
            if not self.token:
                self.token = self.request('/api/auth/csrf')[1]['token']
            headers['X-CSRF-TOKEN'] = self.token
        request = urllib.request.Request(
            BASE + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            return response.status, json.loads(body) if body else None

    def login(self, credentials, tenant_code=None):
        data = {'username': credentials['username'], 'password': credentials['password']}
        if tenant_code:
            data['tenantCode'] = tenant_code
        status, session = self.request('/api/auth/login', 'POST', data)
        self.token = None
        return status, session


def catalog_permission(client, tenant_id, code):
    status, result = client.request(f'/api/data/permissions?tenantId={tenant_id}&pageSize=100')
    if status != 200:
        raise AssertionError(f'Lettura catalogo permessi: {status}')
    matches = [row for row in result['items'] if row['code'] == code]
    if len(matches) != 1:
        raise AssertionError(f'Permesso applicativo non univoco nel catalogo: {code}')
    return matches[0]


@unittest.skipUnless(CREDENTIAL_PATH, 'Richiede un account di verifica dedicato')
class ApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.credentials = json.loads(Path(CREDENTIAL_PATH).read_text())
        cls.client = Client()
        status, session = cls.client.login(cls.credentials)
        if status != 200:
            raise AssertionError(f'Login verifica: {status}')
        if session['mustChangePassword']:
            new_password = uuid.uuid4().hex + '-Test!'
            status, _ = cls.client.request('/api/auth/password', 'PUT', {
                'currentPassword': cls.credentials['password'], 'newPassword': new_password,
            })
            if status != 204:
                raise AssertionError(f'Cambio password verifica: {status}')
            cls.credentials['password'] = new_password
            cls.client.token = None
            # Aggiornamento solo del segreto di verifica, mai delle credenziali del proprietario.
            Path(CREDENTIAL_PATH).write_text(json.dumps(cls.credentials))
        cls.tag = 'qa-' + uuid.uuid4().hex[:12]

    def test_01_anonymous_reads_are_denied(self):
        self.assertEqual(Client().request('/api/data/tenants')[0], 401)

    def test_02_csrf_and_foreign_origin_are_denied(self):
        data = {'code': self.tag, 'name': 'Verifica'}
        self.assertIn(self.client.request('/api/data/tenants', 'POST', data, csrf=False)[0], (400, 403))
        self.assertIn(self.client.request('/api/data/tenants', 'POST', data, origin='http://foreign.invalid')[0], (400, 403))

    def test_03_superadmin_session(self):
        status, session = self.client.request('/api/session')
        self.assertEqual(status, 200)
        self.assertTrue(session['isSuperAdmin'])
        self.assertIsNone(session['tenantId'])

    def test_04_metadata(self):
        status, resources = self.client.request('/api/resources')
        self.assertEqual(status, 200)
        self.assertEqual(len(resources), 11)

    def test_05_foundation_crud_and_tenant_boundaries(self):
        created = []
        tenant_ids = []
        try:
            for suffix in ('a', 'b'):
                status, tenant = self.client.request('/api/data/tenants', 'POST', {
                    'code': self.tag + suffix, 'name': 'Verifica ' + suffix, 'is_enabled': True,
                })
                self.assertEqual(status, 201)
                tenant_ids.append(tenant['id'])
            first, second = tenant_ids

            def create(resource, data, tenant_id=first):
                status, record = self.client.request(f'/api/data/{resource}?tenantId={tenant_id}', 'POST', data)
                self.assertEqual(status, 201, (resource, status, record))
                created.append((resource, record['id'], tenant_id))
                return record['id']

            company = create('companies', {'code': 'main', 'name': 'Società', 'is_enabled': True})
            site = create('sites', {'company_id': company, 'code': 'hq', 'name': 'Sede legale', 'vat_number': 'IT-test', 'is_enabled': True})
            kind = create('warehouse-types', {'code': 'returns', 'name': 'Resi', 'is_enabled': True})
            warehouse = create('warehouses', {'site_id': site, 'warehouse_type_id': kind, 'code': 'main', 'name': 'Magazzino', 'is_enabled': True})
            create('warehouse-locations', {'warehouse_id': warehouse, 'code': 'a1', 'name': 'Scaffale', 'is_enabled': True})
            user = create('users', {'username': 'operator', 'first_name': 'Operatore', 'last_name': 'Verifica', 'email': 'operator@example.invalid', 'is_enabled': True})
            group = create('groups', {'code': 'operators', 'name': 'Operatori', 'is_enabled': True})
            role = create('roles', {'code': 'reader', 'name': 'Lettura', 'is_enabled': True})
            permission = catalog_permission(self.client, first, 'companies.read')['id']
            self.assertEqual(self.client.request('/api/data/settings?tenantId=' + first)[0], 404)
            for relation, owner, ids in (
                ('user-roles', user, [role]), ('group-users', group, [user]),
                ('group-roles', group, [role]), ('role-permissions', role, [permission]),
            ):
                path = f'/api/links/{relation}/{owner}?tenantId={first}'
                self.assertEqual(self.client.request(path, 'PUT', {'ids': ids})[0], 204)
                self.assertEqual(self.client.request(path)[1]['ids'], ids)
                self.assertEqual(self.client.request(path, 'PUT', {'ids': []})[0], 204)
            self.assertEqual(self.client.request(f'/api/data/companies/{company}?tenantId={second}', 'PUT', {'name': 'Wrong'})[0], 404)
            status, records = self.client.request(f'/api/data/companies?tenantId={second}')
            self.assertEqual(status, 200)
            self.assertEqual(records['total'], 0)
            invalid = {'company_id': company, 'code': 'invalid', 'name': 'Wrong'}
            self.assertIn(self.client.request(f'/api/data/sites?tenantId={second}', 'POST', invalid)[0], (400, 409))
            self.assertIn(self.client.request(f'/api/data/companies/{company}?tenantId={first}', 'DELETE')[0], (400, 409))
            status, changed = self.client.request(f'/api/data/companies/{company}?tenantId={first}', 'PUT', {'name': 'Società aggiornata'})
            self.assertEqual(status, 200)
            self.assertEqual(changed['name'], 'Società aggiornata')
        finally:
            for resource, record_id, tenant_id in reversed(created):
                status, _ = self.client.request(f'/api/data/{resource}/{record_id}?tenantId={tenant_id}', 'DELETE')
                if status != 204:
                    raise AssertionError(f'Pulizia record verifica fallita: {resource}, {status}')
            for tenant_id in reversed(tenant_ids):
                self.assertEqual(self.client.request(f'/api/data/tenants/{tenant_id}', 'DELETE')[0], 204)


    def test_06_tenant_permissions_and_live_revocation(self):
        client = self.client
        code = self.tag + '-rbac'
        status, tenant = client.request('/api/data/tenants', 'POST', {'code': code, 'name': 'Verifica autorizzazioni'})
        self.assertEqual(status, 201)
        tenant_id = tenant['id']
        created = []
        links = []
        try:
            def create(resource, data):
                status, record = client.request(f'/api/data/{resource}?tenantId={tenant_id}', 'POST', data)
                self.assertEqual(status, 201)
                created.append((resource, record['id']))
                return record['id']

            user = create('users', {'username': 'reader', 'first_name': 'Lettore', 'last_name': 'Verifica', 'email': 'reader@example.invalid', 'is_enabled': True})
            role = create('roles', {'code': 'reader', 'name': 'Lettura', 'is_enabled': True})
            permission = catalog_permission(client, tenant_id, 'companies.read')['id']
            role_link = f'/api/links/user-roles/{user}?tenantId={tenant_id}'
            permission_link = f'/api/links/role-permissions/{role}?tenantId={tenant_id}'
            for path, ids in ((role_link, [role]), (permission_link, [permission])):
                links.append(path)
                self.assertEqual(client.request(path, 'PUT', {'ids': ids})[0], 204)
            password = uuid.uuid4().hex + '-Initial!'
            self.assertEqual(client.request(f'/api/users/{user}/password?tenantId={tenant_id}', 'PUT', {'newPassword': password})[0], 204)
            limited = Client()
            status, session = limited.login({'username': 'reader', 'password': password}, code)
            self.assertEqual(status, 200)
            self.assertFalse(session['isSuperAdmin'])
            self.assertTrue(session['mustChangePassword'])
            self.assertIn(limited.request(f'/api/data/companies?tenantId={tenant_id}')[0], (403, 428))
            self.assertEqual(limited.request('/api/auth/password', 'PUT', {
                'currentPassword': password, 'newPassword': uuid.uuid4().hex + '-Changed!',
            })[0], 204)
            limited.token = None
            self.assertEqual(limited.request(f'/api/data/companies?tenantId={tenant_id}')[0], 200)
            self.assertEqual(limited.request('/api/data/tenants')[0], 403)
            self.assertEqual(limited.request(f'/api/data/companies?tenantId={uuid.uuid4()}')[0], 403)
            self.assertEqual(limited.request(f'/api/data/companies?tenantId={tenant_id}', 'POST', {'code': 'denied', 'name': 'Negato'})[0], 403)
            self.assertEqual(client.request(permission_link, 'PUT', {'ids': []})[0], 204)
            self.assertEqual(limited.request(f'/api/data/companies?tenantId={tenant_id}')[0], 403)
            self.assertEqual(client.request(permission_link, 'PUT', {'ids': [permission]})[0], 204)
            self.assertEqual(limited.request(f'/api/data/companies?tenantId={tenant_id}')[0], 200)
            self.assertEqual(client.request(f'/api/data/users/{user}?tenantId={tenant_id}', 'PUT', {'is_enabled': False})[0], 200)
            self.assertEqual(limited.request('/api/session')[0], 401)
        finally:
            for path in reversed(links):
                client.request(path, 'PUT', {'ids': []})
            for resource, record_id in reversed(created):
                status, _ = client.request(f'/api/data/{resource}/{record_id}?tenantId={tenant_id}', 'DELETE')
                if status != 204:
                    raise AssertionError(f'Pulizia RBAC fallita: {resource}, {status}')
            self.assertEqual(client.request(f'/api/data/tenants/{tenant_id}', 'DELETE')[0], 204)


if __name__ == '__main__':
    unittest.main()
