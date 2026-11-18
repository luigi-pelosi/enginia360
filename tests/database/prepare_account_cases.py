"""Prepara casi legacy autentici esclusivamente nel database isolato."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

os.environ['ENGINIA360_TEST_BASE'] = 'https://vmi3659251.tailfcced0.ts.net:8443'
os.environ['ENGINIA360_TEST_ORIGIN'] = os.environ['ENGINIA360_TEST_BASE']
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from test_api import Client

PRIVATE = Path('/root/.config/enginia360/account-migration')
assert not (PRIVATE / 'cases.json').exists(), 'Casi già preparati'
credentials = json.loads((PRIVATE / 'credentials.json').read_text())
client = Client()
status, session = client.login(credentials)
assert status == 200
if session['mustChangePassword']:
    password = secrets.token_urlsafe(24)
    assert client.request('/api/auth/password', 'PUT', {'currentPassword': credentials['password'], 'newPassword': password})[0] == 204
    credentials['password'] = password
    (PRIVATE / 'credentials.json').write_text(json.dumps(credentials))
    client.token = None


def create(resource, data, tenant=None):
    path = f'/api/data/{resource}' + (f'?tenantId={tenant}' if tenant else '')
    status, row = client.request(path, 'POST', data)
    assert status == 201, (resource, status)
    return row['id']


def query(statement):
    result = subprocess.run(
        ['docker', 'exec', '-i', 'enginia360-foundation-db', 'psql', '-U', 'postgres',
         '-d', 'enginia360_account_cases', '-X', '-At', '-v', 'ON_ERROR_STOP=1'],
        input=statement, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


first = create('tenants', {'code': 'migration-a', 'name': 'Cliente A'})
second = create('tenants', {'code': 'migration-b', 'name': 'Cliente B'})
create('companies', {'code': 'main', 'name': 'Società A'}, first)
create('companies', {'code': 'main', 'name': 'Società B'}, second)
users = []
for tenant, code, username, enabled, with_password in (
    (first, 'migration-a', 'reader', True, True),
    (first, 'migration-a', 'disabled-profile', False, True),
    (first, 'migration-a', 'disabled-account', True, True),
    (first, 'migration-a', 'pending', True, False),
    (second, 'migration-b', 'reader', True, True),
):
    user_id = create('users', {'username': username, 'display_name': username, 'email': username + '@example.invalid', 'is_enabled': enabled}, tenant)
    entry = {'tenant_id': tenant, 'tenant_code': code, 'username': username, 'legacy_id': user_id, 'enabled': enabled, 'with_password': with_password}
    if with_password:
        password = secrets.token_urlsafe(24)
        assert client.request(f'/api/users/{user_id}/password?tenantId={tenant}', 'PUT', {'newPassword': password})[0] == 204
        if enabled:
            limited = Client()
            result, identity = limited.login({'username': username, 'password': password}, code)
            assert result == 200
            entry['account_id'] = identity['id']
            next_password = secrets.token_urlsafe(24)
            assert limited.request('/api/auth/password', 'PUT', {'currentPassword': password, 'newPassword': next_password})[0] == 204
            password = next_password
        else:
            entry['account_id'] = query(f"SELECT id FROM foundation.account WHERE tenant_id='{tenant}' AND user_id='{user_id}'")
        entry['password'] = password
    users.append(entry)

disabled = next(user for user in users if user['username'] == 'disabled-account')
query(f"UPDATE foundation.account SET is_enabled=false WHERE id='{disabled['account_id']}'")
global_id = session['id']
query(f"INSERT INTO foundation.app_user (id,tenant_id,username,display_name,email) VALUES ('{global_id}','{first}','collision-pending','Collisione identificativo','collision@example.invalid')")
users.append({'tenant_id': first, 'tenant_code': 'migration-a', 'username': 'collision-pending', 'legacy_id': global_id, 'enabled': True, 'with_password': False})
role = create('roles', {'code': 'reader', 'name': 'Lettura società'}, first)
permission = create('permissions', {'code': 'companies.read', 'name': 'Lettura società'}, first)
group = create('groups', {'code': 'readers', 'name': 'Lettori'}, first)
reader = next(user for user in users if user['username'] == 'reader' and user['tenant_id'] == first)
pending = next(user for user in users if user['username'] == 'pending')
for relation, owner, ids in (
    ('role-permissions', role, [permission]), ('group-roles', group, [role]),
    ('group-users', group, [reader['legacy_id'], pending['legacy_id'], global_id]),
    ('user-roles', reader['legacy_id'], [role]), ('user-roles', pending['legacy_id'], [role]),
):
    assert client.request(f'/api/links/{relation}/{owner}?tenantId={first}', 'PUT', {'ids': ids})[0] == 204
for entry in users:
    if entry.get('password') and (not entry['enabled'] or entry['username'] == 'disabled-account'):
        limited = Client()
        assert limited.login({'username': entry['username'], 'password': entry['password']}, entry['tenant_code'])[0] == 401
reader_client = Client()
status, identity = reader_client.login({'username': reader['username'], 'password': reader['password']}, reader['tenant_code'])
assert status == 200 and identity['permissions'] == ['companies.read']
assert reader_client.request(f'/api/data/companies?tenantId={first}')[0] == 200
assert reader_client.request(f'/api/data/companies?tenantId={second}')[0] == 403
cases = {'first_tenant': first, 'second_tenant': second, 'role': role, 'permission': permission, 'group': group, 'global_id': global_id, 'users': users}
fd = os.open(PRIVATE / 'cases.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as handle:
    json.dump(cases, handle)
print(json.dumps({'legacy_users': len(users), 'tenants': 2, 'legacy_login_verified': True, 'legacy_rbac_verified': True, 'collision_case': True}))
