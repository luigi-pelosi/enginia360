"""Bounded Catalog ITEMS fixture. Never connects to a real database/origin."""
import http.client
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[2]
SCOPE = os.environ.get('ENGINIA360_CATALOG_ITEMS_SCOPE', 'enginia360-catalog-items-proof')
if SCOPE not in ('enginia360-catalog-items-proof', 'enginia360-catalog-items-http-proof'):
    raise ValueError('Catalog ITEMS scope outside fixed allowlist')
ORIGIN = 'https://catalog-items.invalid'
_spec = importlib.util.spec_from_file_location('_catalog_items_fixture', ROOT / 'tests/application/run_business_partner_proof.py')
fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fixture)
fixture.SCOPE = SCOPE
fixture.DB, fixture.API, fixture.WEB = (SCOPE + '-' + part for part in ('db', 'api', 'web'))
fixture.NETWORK, fixture.INGRESS = SCOPE, SCOPE + '-ingress'
fixture.ORIGIN = ORIGIN
fixture.EVIDENCE = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) / SCOPE

from database.sql_source import read_sql as canonical_sql
fixture.read_sql = canonical_sql


def start(args):
    """Expand schema AND migrations, leaving published SQL bytes untouched."""
    fixture.EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    migrations = []
    for i, path in enumerate(args.migration):
        target = fixture.EVIDENCE / ('expanded-migration-%02d.sql' % i)
        target.write_text(canonical_sql(path))
        migrations.append(str(target))
    args.migration = migrations
    return fixture.start(args)


def require_fixture(browser=False):
    if os.environ.get('ENGINIA360_CATALOG_ITEMS_PROOF') != '1':
        raise RuntimeError('Use the isolated Catalog ITEMS runner; acceptance cannot skip')
    state = json.loads((fixture.EVIDENCE / 'state.json').read_text())
    if state['scope'] != SCOPE or state['origin'] != ORIGIN:
        raise RuntimeError('Foreign fixture state')
    for name in (fixture.DB, fixture.API) + ((fixture.WEB,) if browser else ()):
        if not fixture.verify_target(name):
            raise RuntimeError('Missing owned fixture: ' + name)
    return state


_STATE = None
class Client:
    """Real cookies/CSRF over local HTTP; logical HTTPS is not TLS evidence."""
    def __init__(self):
        if _STATE is None:
            raise RuntimeError('Transport not installed by isolated runner')
        class Local(urllib.request.HTTPSHandler):
            def https_open(self, request):
                if request.host != urlsplit(ORIGIN).netloc:
                    raise RuntimeError('External destination forbidden')
                return self.do_open(lambda host, **kw: http.client.HTTPConnection('127.0.0.1', _STATE['apiPort'], **kw), request)
        class DenyHTTP(urllib.request.HTTPHandler):
            def http_open(self, request):
                raise RuntimeError('HTTP redirects/external destinations forbidden')
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Local(), DenyHTTP(),
                                                  urllib.request.HTTPCookieProcessor(self.cookies))
        self.token = None

    def request(self, path, method='GET', data=None, csrf=True, origin=ORIGIN):
        if not path.startswith('/api/') or path.startswith('//'):
            raise ValueError('Only fixture API paths permitted')
        headers = {'Origin': origin, 'Host': urlsplit(ORIGIN).netloc, 'Accept': 'application/json'}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        if method not in ('GET', 'HEAD') and csrf:
            if not self.token:
                self.token = self.request('/api/auth/csrf')[1]['token']
            headers['X-CSRF-TOKEN'] = self.token
        request = urllib.request.Request(ORIGIN + path, method=method, headers=headers,
                                         data=json.dumps(data).encode() if data is not None else None)
        try:
            response = self.opener.open(request, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                body = json.loads(raw) if raw else None
            except ValueError:
                body = {'nonJsonResponse': raw.decode(errors='replace')[:1000]}
            return response.status, body

    def login(self, credentials, tenant_code=None):
        data = {key: credentials[key] for key in ('username', 'password')}
        if tenant_code:
            data['tenantCode'] = tenant_code
        result = self.request('/api/auth/login', 'POST', data)
        self.token = None
        return result


def install_transport(state):
    global _STATE
    if state['scope'] != SCOPE or state['origin'] != ORIGIN:
        raise RuntimeError('Foreign fixture state')
    _STATE = state
    os.environ['ENGINIA360_CATALOG_ITEMS_PROOF'] = '1'
    os.environ['ENGINIA360_CATALOG_ITEMS_STATE'] = str(fixture.EVIDENCE / 'state.json')


def login_root():
    state = require_fixture()
    path = Path(state['credentials'])
    credentials = json.loads(path.read_text())
    client = Client()
    status, session = client.login(credentials)
    if status != 200:
        raise AssertionError(('fixture login', status, session))
    if session['mustChangePassword']:
        password = uuid.uuid4().hex + '-Items!'
        status, body = client.request('/api/auth/password', 'PUT', {'currentPassword': credentials['password'], 'newPassword': password})
        if status != 204:
            raise AssertionError(('fixture password', status, body))
        credentials['password'] = password
        path.write_text(json.dumps(credentials))
        path.chmod(0o600)
        client.token = None
    return client, credentials


def fixture_sql(statement):
    require_fixture()
    return fixture.sql(statement).stdout.strip()
