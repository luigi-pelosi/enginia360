"""Supporto Catalogo: solo fixture sintetiche etichettate e trasporto locale."""
import http.client
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit
import uuid

import run_business_partner_proof as fixture
from database.sql_source import read_sql
fixture.read_sql = read_sql
_fixture_start = fixture.start


def _start_with_canonical_sql(args):
    """Retain ordered future migrations, parsed by the shared SQL loader."""
    fixture.EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    migrations = []
    for index, path in enumerate(args.migration or []):
        target = fixture.EVIDENCE / ('expanded-migration-%02d.sql' % index)
        target.write_text(read_sql(path))
        migrations.append(str(target))
    args.migration = migrations
    return _fixture_start(args)


fixture.start = _start_with_canonical_sql

SCOPE = os.environ.get('ENGINIA360_CATALOG_SCOPE', 'enginia360-catalog-proof')
if SCOPE not in ('enginia360-catalog-proof', 'enginia360-catalog-http-proof'):
    raise ValueError('Scope Catalogo non autorizzato')

def configure_fixture():
    fixture.SCOPE = SCOPE
    fixture.DB, fixture.API, fixture.WEB = (SCOPE + '-' + part for part in ('db', 'api', 'web'))
    fixture.NETWORK, fixture.INGRESS = SCOPE, SCOPE + '-ingress'
    fixture.EVIDENCE = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) / SCOPE
    return fixture


def install_transport(state):
    """HTTPS logico, non prova TLS; nessuna destinazione esterna ammessa."""
    os.environ.update(ENGINIA360_CATALOG_PROOF='1', ENGINIA360_TEST_BASE=fixture.ORIGIN,
                      ENGINIA360_TEST_ORIGIN=fixture.ORIGIN,
                      ENGINIA360_TEST_CREDENTIALS=state['credentials'])
    class LocalTransport(urllib.request.HTTPSHandler):
        def https_open(self, request):
            if request.host != urlsplit(fixture.ORIGIN).netloc:
                raise RuntimeError('Host fuori dalla fixture Catalogo')
            return self.do_open(lambda host, **kw: http.client.HTTPConnection(
                '127.0.0.1', state['apiPort'], **kw), request)
    original = urllib.request.build_opener
    urllib.request.build_opener = lambda *handlers: original(LocalTransport(), *handlers)
    return original


def login_root():
    # Import dopo install_transport: test_api legge l'ambiente all'importazione.
    from test_api import Client
    path = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
    credentials = json.loads(path.read_text())
    client = Client()
    status, session = client.login(credentials)
    if status != 200:
        raise AssertionError(('Login Catalogo', status, session))
    if session['mustChangePassword']:
        password = uuid.uuid4().hex + '-Catalog!'
        status, body = client.request('/api/auth/password', 'PUT', {
            'currentPassword': credentials['password'], 'newPassword': password})
        if status != 204:
            raise AssertionError(('Cambio password Catalogo', status, body))
        credentials['password'] = password
        path.write_text(json.dumps(credentials))
        client.token = None
    return client, credentials


def fixture_sql(statement):
    configure_fixture()
    return fixture.sql(statement).stdout.strip()


def reseed(tenant_id):
    """Richiama il seed canonico reale, senza migrazioni né dati live."""
    fixture_sql(f"SELECT masterdata.seed_catalog('{uuid.UUID(tenant_id)}'::uuid,NULL);")
