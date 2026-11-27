"""Fixture TaxManagement isolata; riusa provisioning e autenticazione foundation."""
import http.client
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit
import uuid

import run_business_partner_proof as fixture

SCOPE = 'enginia360-tax-proof'


def configure_fixture(scope=SCOPE):
    if scope not in (SCOPE, 'enginia360-taxclassification-proof', 'enginia360-company-tax-proof'):
        raise ValueError('Scope fixture TaxManagement non autorizzato')
    fixture.SCOPE = scope
    fixture.DB, fixture.API, fixture.WEB = (scope + '-' + key for key in ('db', 'api', 'web'))
    fixture.NETWORK, fixture.INGRESS = scope, scope + '-ingress'
    fixture.ORIGIN = 'https://tax-management.invalid'
    fixture.EVIDENCE = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) / scope
    return fixture


def install_transport(state):
    os.environ.update(ENGINIA360_TAX_PROOF='1', ENGINIA360_TEST_BASE=fixture.ORIGIN,
                      ENGINIA360_TEST_ORIGIN=fixture.ORIGIN,
                      ENGINIA360_TEST_CREDENTIALS=state['credentials'])
    class LocalTransport(urllib.request.HTTPSHandler):
        def https_open(self, request):
            if request.host != urlsplit(fixture.ORIGIN).netloc:
                raise RuntimeError('Host fuori dalla fixture TaxManagement')
            return self.do_open(lambda host, **kw: http.client.HTTPConnection(
                '127.0.0.1', state['apiPort'], **kw), request)
    original = urllib.request.build_opener
    urllib.request.build_opener = lambda *handlers: original(LocalTransport(), *handlers)
    return original


def login_root():
    from test_api import Client
    path = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
    credentials = json.loads(path.read_text())
    client = Client()
    status, session = client.login(credentials)
    if status != 200:
        raise AssertionError(('Login TaxManagement', status, session))
    if session['mustChangePassword']:
        password = uuid.uuid4().hex + '-Tax!'
        status, body = client.request('/api/auth/password', 'PUT', {
            'currentPassword': credentials['password'], 'newPassword': password})
        if status != 204:
            raise AssertionError(('Cambio password fixture', status, body))
        credentials['password'] = password
        path.write_text(json.dumps(credentials))
        client.token = None
    return client, credentials
