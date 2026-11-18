"""Fixture HTTP limitata allo stack temporaneo del salvataggio unico."""
import http.client
import json
import os
from pathlib import Path
import secrets
import urllib.request
import uuid

PRIVATE = Path(os.environ.get('ENGINIA360_VALIDATION_DIR', '/root/.config/enginia360/unified-save'))
DB_CONTAINER = os.environ.get('ENGINIA360_VALIDATION_DB_CONTAINER', 'enginia360-unified-save-db')
if DB_CONTAINER not in ('enginia360-unified-save-db', 'enginia360-optional-code-db', 'enginia360-commercial-organizations-db', 'enginia360-site-classification-db', 'enginia360-site-addresses-db', 'enginia360-required-search-db'):
    raise RuntimeError('Questo fixture non può utilizzare il database principale')
PORTS = json.loads((PRIVATE / 'ports.json').read_text())
ORIGIN = 'https://vmi3659251.tailfcced0.ts.net:8080'
os.environ.update(ENGINIA360_TEST_BASE=ORIGIN, ENGINIA360_TEST_ORIGIN=ORIGIN,
                  ENGINIA360_DB_CONTAINER=DB_CONTAINER,
                  ENGINIA360_DB_DATABASE='enginia360',
                  ENGINIA360_TEST_CREDENTIALS=str(PRIVATE / 'bootstrap.json'))


class IsolatedTransport(urllib.request.HTTPSHandler):
    def https_open(self, request):
        if request.host != 'vmi3659251.tailfcced0.ts.net:8080':
            raise RuntimeError('Host esterno non ammesso nel fixture')
        return self.do_open(lambda host, **kwargs: http.client.HTTPConnection('127.0.0.1', PORTS['backend'], **kwargs), request)


original = urllib.request.build_opener
urllib.request.build_opener = lambda *handlers: original(IsolatedTransport(), *handlers)
from test_api import Client
from test_database_security import sql


def root_client():
    credentials = json.loads((PRIVATE / 'bootstrap.json').read_text())
    root = Client()
    status, session = root.login(credentials)
    if status != 200:
        raise AssertionError('Login QA isolato non riuscito')
    if session['mustChangePassword']:
        updated = secrets.token_urlsafe(28)
        if root.request('/api/auth/password', 'PUT', {
            'currentPassword': credentials['password'], 'newPassword': updated,
        })[0] != 204:
            raise AssertionError('Attivazione QA isolata non riuscita')
        credentials['password'] = updated
        (PRIVATE / 'bootstrap.json').write_text(json.dumps(credentials))
        root.token = None
    return root, credentials


class Case:
    def __init__(self, root):
        self.root = root
        status, self.tenant = root.request('/api/data/tenants', 'POST', {
            'code': 'save-' + uuid.uuid4().hex, 'name': 'Verifica salvataggio',
        })
        if status != 201:
            raise AssertionError('Creazione tenant fixture non riuscita')
        status, catalog = root.request(self.path('permissions') + '&pageSize=100')
        if status != 200 or not catalog['items'] or len(catalog['items']) != catalog['total']:
            raise AssertionError('Catalogo fixture non valido')
        self.catalog = {row['code']: row['id'] for row in catalog['items']}

    def path(self, resource, record_id=None, save=False):
        return '/api/data/' + resource + ('/' + record_id if record_id else '') + ('/save' if save else '') + '?tenantId=' + self.tenant['id']

    def link(self, relation, owner):
        return '/api/links/' + relation + '/' + owner + '?tenantId=' + self.tenant['id']

    def create(self, resource, body):
        # Le anagrafiche sintetiche valide rispettano identificativo fiscale e indirizzo obbligatori.
        if resource == 'sites':
            body = {'tax_code': 'QA-SITE-TAX', 'address': 'Via QA 1', 'city': 'Città QA',
                    'province': 'Provincia QA', 'postal_code': '00000', 'country_code': 'IT', **body}
        status, row = self.root.request(self.path(resource), 'POST', body)
        if status != 201:
            raise AssertionError(f'Fixture {resource} non valida: {status}')
        return row

    def role(self, codes=(), name='Ruolo verifica'):
        role = self.create('roles', {'code': 'role-' + uuid.uuid4().hex, 'name': name})
        if self.root.request(self.link('role-permissions', role['id']), 'PUT', {'ids': [self.catalog[code] for code in codes]})[0] != 204:
            raise AssertionError('Grant fixture non validi')
        return role

    def user(self, name='Operatore'):
        username = 'operator-' + uuid.uuid4().hex[:10]
        return self.create('users', {'username': username, 'first_name': name, 'last_name': 'Verifica', 'email': username + '@example.invalid'})

    def actor(self, codes):
        user, role = self.user(), self.role(codes)
        if self.root.request(self.link('user-roles', user['id']), 'PUT', {'ids': [role['id']]})[0] != 204:
            raise AssertionError('Assegnazione fixture non valida')
        initial, changed = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        if self.root.request('/api/users/' + user['id'] + '/password?tenantId=' + self.tenant['id'], 'PUT', {'newPassword': initial})[0] != 204:
            raise AssertionError('Password fixture non valida')
        client = Client()
        if client.login({'username': user['username'], 'password': initial}, self.tenant['code'])[0] != 200:
            raise AssertionError('Login attore non riuscito')
        if client.request('/api/auth/password', 'PUT', {'currentPassword': initial, 'newPassword': changed})[0] != 204:
            raise AssertionError('Cambio password attore non riuscito')
        client.token = None
        return client, user, role, {'username': user['username'], 'password': changed}

    def close(self):
        tenant = self.tenant['id']
        tables = ('purchasing_organization_site','purchasing_organization_company','purchasing_organization','sales_organization',
                  'role_permission','user_role','user_group_member','user_group_role','permission','role','user_group','user',
                  'setting','warehouse_location','warehouse','warehouse_type','site','company')
        statements=[]
        for table in tables:
            if table.startswith(('purchasing_organization','sales_organization')) and sql(f"SELECT to_regclass('foundation.{table}') IS NOT NULL").stdout.strip() != 't':
                continue
            statements.append(f'DELETE FROM foundation."{table}" WHERE tenant_id=\'{tenant}\';')
        sql('BEGIN;'+''.join(statements)+f"DELETE FROM foundation.tenant WHERE id='{tenant}';COMMIT;")
