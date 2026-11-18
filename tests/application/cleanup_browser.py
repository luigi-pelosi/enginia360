"""Rimuove soltanto i record identificati dal percorso browser di verifica."""

import json
import os
from pathlib import Path

from test_api import Client

secret = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
manifest = Path(os.environ.get('ENGINIA360_EVIDENCE', '/root/.hermes/cache/scratch/enginia360-app-evidence')) / 'browser-created.json'
created = json.loads(manifest.read_text())
tenants = [record['id'] for record in created if record['resource'] == 'tenants']
assert len(tenants) == 1
scope = '?tenantId=' + tenants[0]
client = Client()
assert client.login(secret)[0] == 200
for record in created:
    relations = {
        'users': ['user-roles'], 'groups': ['group-users', 'group-roles'],
        'roles': ['role-permissions'],
    }.get(record['resource'], [])
    for relation in relations:
        assert client.request(f"/api/links/{relation}/{record['id']}{scope}", 'PUT', {'ids': []})[0] == 204
for record in reversed(created):
    path = f"/api/data/{record['resource']}/{record['id']}"
    if record['resource'] != 'tenants':
        path += scope
    status, _ = client.request(path, 'DELETE')
    assert status == 204, (record['resource'], status)
manifest.rename(manifest.with_name('browser-created-cleaned.json'))
print('Record browser di verifica rimossi:', len(created))
