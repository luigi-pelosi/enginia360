"""Prove HTTP reali Tax Foundation, attivabili soltanto dal runner isolato."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import unittest
from urllib.parse import urlencode
import uuid

from tax_helpers import configure_fixture, login_root
from test_api import Client


@unittest.skipUnless(os.environ.get('ENGINIA360_TAX_PROOF') == '1', 'Richiede run_tax_proof.py')
class TaxHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = configure_fixture()
        if not all(cls.fixture.verify_target(x) for x in (cls.fixture.DB, cls.fixture.API)):
            raise RuntimeError('Fixture TaxManagement non disponibile')
        cls.root, cls.credentials = login_root()
        status, countries = cls.root.request('/api/data/countries?pageSize=100&search=Italia')
        assert status == 200, countries
        italy = next((x for x in countries['items'] if x['iso_code'] == 'IT'), None)
        if not italy:
            status, italy = cls.root.request('/api/data/countries', 'POST', {'name': 'Italia', 'iso_code': 'IT'})
            assert status == 201, italy
        cls.country_id = italy['id']

    def setUp(self):
        self.code = 'tax-' + uuid.uuid4().hex[:12]
        status, tenant = self.root.request('/api/data/tenants', 'POST', {'code': self.code, 'name': 'Fiscalità sintetica'})
        self.assertEqual(status, 201, tenant)
        self.tenant_id = tenant['id']
        self.types = self.req('types')['items']
        self.vat = next(t for t in self.types if t['code'] == 'VAT')
        self.natures = self.req('nature-codes', countryId=self.country_id, pageSize=100)['items']
        self.nature_ids = {n['code']: n['id'] for n in self.natures}

    def path(self, route, tenant=None, **query):
        return '/api/tax/' + route + '?' + urlencode({'tenantId': tenant or self.tenant_id, **query})

    def req(self, route, method='GET', body=None, expected=200, tenant=None, **query):
        status, response = self.root.request(self.path(route, tenant, **query), method, body)
        self.assertEqual(status, expected, (route, status, response))
        return response

    def payload(self, **version):
        return {'values': {'code': 'VAT_' + uuid.uuid4().hex[:12], 'name': 'IVA di prova',
                           'description': None, 'country_id': self.country_id, 'tax_type_id': self.vat['id']},
                'versions': [{'rate': '22', 'treatment': 'TAXABLE', 'tax_nature_code_id': None,
                              'legal_reference': None, 'valid_from': '2026-01-01', 'valid_to': None, **version}]}

    def create(self, **version):
        return self.req('codes', 'POST', self.payload(**version), 201)

    def update(self, row, values, expected=200):
        return self.req('codes/' + row['id'], 'PUT', {'values': values, 'expectedVersion': row['version']}, expected)

    def schedule(self, row, date='2027-01-01', expected=200, **version):
        values = self.payload(valid_from=date, rate='23', **version)['versions'][0]
        return self.req('codes/' + row['id'] + '/versions', 'POST', {'values': values, 'expectedVersion': row['version']}, expected)

    def sql(self, statement):
        return self.fixture.sql(statement).stdout.strip()

    def test_global_catalogs_full_and_no_implicit_tenant_templates(self):
        self.assertEqual(len(self.types), 5)
        self.assertEqual([t['code'] for t in self.types if t['is_active']], ['VAT'])
        expected = {'N1', 'N2.1', 'N2.2', 'N4', 'N5', 'N7'} | {'N3.' + str(i) for i in range(1, 7)} | {'N6.' + str(i) for i in range(1, 10)}
        self.assertEqual(set(self.nature_ids), expected)
        self.assertEqual(self.req('codes')['total'], 0)
        self.assertTrue(any(c['id'] == self.country_id for c in self.req('countries')['items']))
        for route in ('types', 'nature-codes'):
            self.req(route, 'POST', {}, 404)

    def test_create_metadata_atomic_versions_and_temporal_resolution(self):
        row = self.create()
        self.assertEqual(row['versions'][0]['rate'], '22.000000')
        self.assertEqual(self.req('codes/' + row['id']), row)
        changed = self.update(row, {'name': 'IVA ordinaria configurata'})
        self.assertEqual(changed['code'], row['code'])
        self.assertEqual(changed['version'], row['version'] + 1)
        future = self.schedule(changed)
        versions = sorted(future['versions'], key=lambda v: v['valid_from'])
        self.assertEqual([v['valid_to'] for v in versions], ['2026-12-31', None])
        for date, rate in (('2026-01-01', '22.000000'), ('2026-12-31', '22.000000'), ('2027-01-01', '23.000000')):
            resolved = self.req('codes/' + row['id'] + '/resolve', date=date)
            self.assertEqual(resolved['rate'], rate)
        self.req('codes/' + row['id'] + '/resolve', date='2025-12-31', expected=404)
        self.req('codes/' + row['id'] + '/resolve', date='2027-02-30', expected=400)
        listing = self.req('codes', date='2026-06-01', search=row['code'])
        self.assertEqual(listing['items'][0]['rate'], '22.000000')
        events = self.req('codes/' + row['id'] + '/audit')['items']
        self.assertEqual(len(events), 3)
        self.assertTrue(all(e['tax_code_id'] == row['id'] for e in events))

    def test_tenant_isolation_scope_uniqueness_and_no_deletion(self):
        row = self.create()
        status, other = self.root.request('/api/data/tenants', 'POST', {'code': 'other-' + uuid.uuid4().hex[:12], 'name': 'Altra organizzazione'})
        self.assertEqual(status, 201, other)
        for suffix in ('', '/versions', '/audit', '/resolve'):
            self.req('codes/' + row['id'] + suffix, tenant=other['id'], date='2026-01-01', expected=404)
        self.req('codes/' + row['id'], 'PUT', {'values': {'name': 'Intrusione'}, 'expectedVersion': row['version']}, 404, tenant=other['id'])
        payload = self.payload()
        payload['values']['code'] = row['code'].lower()
        self.req('codes', 'POST', payload, 409)
        self.req('codes', 'POST', payload, 201, tenant=other['id'])
        status, countries = self.root.request('/api/data/countries?pageSize=100&search=Germania')
        self.assertEqual(status, 200, countries)
        germany = next((c for c in countries['items'] if c['iso_code'] == 'DE'), None)
        if germany is None:
            status, germany = self.root.request('/api/data/countries', 'POST', {'name': 'Germania', 'iso_code': 'DE'})
            self.assertEqual(status, 201, germany)
        payload['values']['country_id'] = germany['id']
        self.req('codes', 'POST', payload, 201)
        self.req('codes/' + row['id'], 'DELETE', expected=404)
        self.assertEqual(self.req('codes/' + row['id']), row)

    def test_exact_rate_period_and_treatment_validation_without_partial_write(self):
        before = self.req('codes')['total']
        cases = [{'rate': '-1'}, {'rate': '0.0000001'}, {'rate': '1000'}, {'rate': '1e2'}, {'rate': 'NaN'},
                 {'rate': 22}, {'valid_from': '2026-02-30'}, {'valid_from': '2026-1-01'},
                 {'valid_to': '2025-12-31'}, {'rate': '0'}, {'tax_nature_code_id': self.nature_ids['N4']},
                 {'rate': '0', 'treatment': 'EXEMPT', 'tax_nature_code_id': self.nature_ids['N1']},
                 {'rate': '0', 'treatment': 'ZERO_RATED'}]
        for change in cases:
            with self.subTest(change=change):
                self.req('codes', 'POST', self.payload(**change), 400)
        self.assertEqual(self.req('codes')['total'], before)
        for nature, treatment in (('N1', 'EXCLUDED'), ('N2.1', 'OUT_OF_SCOPE'), ('N3.6', 'NON_TAXABLE'),
                                  ('N4', 'EXEMPT'), ('N5', 'MARGIN'), ('N6.9', 'REVERSE_CHARGE'), ('N7', 'OTHER_EU')):
            self.create(rate='0', treatment=treatment, tax_nature_code_id=self.nature_ids[nature])
        row = self.create()
        for values in ({'country_id': self.country_id}, {'code': 'REWRITE'}, {'tax_type_id': self.vat['id']}):
            self.update(row, values, 400)
        self.assertEqual(self.req('codes/' + row['id']), row)
        payload = self.payload()
        payload['versions'].append({**payload['versions'][0], 'valid_from': '2027-01-01'})
        self.req('codes', 'POST', payload, 409)
        inactive = next(t for t in self.types if t['code'] == 'EXCISE')
        payload = self.payload()
        payload['values']['tax_type_id'] = inactive['id']
        self.req('codes', 'POST', payload, 400)

    def test_deactivation_blocks_new_use_not_history_and_reactivation_is_versioned(self):
        row = self.create()
        disabled = self.req('codes/' + row['id'] + '/deactivate', 'POST', {'expectedVersion': row['version']})
        self.assertFalse(disabled['is_active'])
        self.req('codes/' + row['id'] + '/resolve', date='2026-06-01', forNewUse='true', expected=409)
        self.assertEqual(self.req('codes/' + row['id'] + '/resolve', date='2026-06-01')['rate'], '22.000000')
        self.schedule(disabled, expected=409)
        self.req('codes/' + row['id'] + '/reactivate', 'POST', {'expectedVersion': row['version']}, 409)
        enabled = self.req('codes/' + row['id'] + '/reactivate', 'POST', {'expectedVersion': disabled['version']})
        self.assertTrue(enabled['is_active'])
        self.req('codes/' + row['id'] + '/resolve', date='2026-06-01', forNewUse='true')

    def test_templates_install_is_explicit_idempotent_and_preserves_customization(self):
        first = self.req('codes/templates/install', 'POST', {'validFrom': '2026-11-25'})
        self.assertEqual(first['installed'], 14)
        rows = self.req('codes', pageSize=100)['items']
        standard = next(x for x in rows if x['code'] == 'VAT_STANDARD')
        changed = self.update(standard, {'name': 'Descrizione personalizzata'})
        snapshot = self.req('codes/' + standard['id'])
        second = self.req('codes/templates/install', 'POST', {'validFrom': '2027-01-01'})
        self.assertEqual((second['installed'], second['skipped']), (0, 14))
        self.assertEqual(self.req('codes/' + standard['id']), snapshot)
        self.assertEqual(snapshot['version'], changed['version'])
        self.assertEqual(self.req('codes')['total'], 14)

    def test_stale_and_concurrent_schedules_have_one_winner(self):
        row = self.create()
        def schedule(date):
            return self.root.request(self.path('codes/' + row['id'] + '/versions'), 'POST', {
                'values': self.payload(valid_from=date, rate='23')['versions'][0], 'expectedVersion': row['version']})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(schedule, ('2027-01-01', '2028-01-01')))
        self.assertEqual(sorted(s for s, _ in results), [200, 409], results)
        after = self.req('codes/' + row['id'])
        self.assertEqual(len(after['versions']), 2)
        self.update(row, {'name': 'Bozza obsoleta'}, 409)
        self.assertEqual(self.req('codes/' + row['id']), after)
        self.schedule(after, date='2026-01-01', expected=409)

    def actor(self, grants):
        username = 'taxuser-' + uuid.uuid4().hex[:10]
        status, user = self.root.request('/api/data/users?tenantId=' + self.tenant_id, 'POST', {
            'username': username, 'first_name': 'Prova', 'last_name': 'Fiscalità', 'email': username + '@example.invalid'})
        self.assertEqual(status, 201, user)
        status, role = self.root.request('/api/data/roles?tenantId=' + self.tenant_id, 'POST', {'name': 'Ruolo fiscale'})
        self.assertEqual(status, 201, role)
        permissions, page = [], 1
        while True:
            status, result = self.root.request('/api/data/permissions?' + urlencode({'tenantId': self.tenant_id, 'page': page, 'pageSize': 100}))
            self.assertEqual(status, 200, result)
            permissions.extend(result['items'])
            if len(permissions) >= result['total']:
                break
            self.assertTrue(result['items'])
            page += 1
        ids = [p['id'] for p in permissions if p['code'] in grants]
        self.assertEqual(len(ids), len(grants))
        for relation, owner, targets in (('role-permissions', role['id'], ids), ('user-roles', user['id'], [role['id']])):
            self.assertEqual(self.root.request('/api/links/' + relation + '/' + owner + '?tenantId=' + self.tenant_id, 'PUT', {'ids': targets})[0], 204)
        password, changed = uuid.uuid4().hex + '-Initial!', uuid.uuid4().hex + '-Changed!'
        self.assertEqual(self.root.request('/api/users/' + user['id'] + '/password?tenantId=' + self.tenant_id, 'PUT', {'newPassword': password})[0], 204)
        client = Client()
        self.assertEqual(client.login({'username': username, 'password': password}, self.code)[0], 200)
        self.assertEqual(client.request('/api/auth/password', 'PUT', {'currentPassword': password, 'newPassword': changed})[0], 204)
        client.token = None
        return client, role, {'username': username, 'password': changed}

    def test_rbac_live_revocation_and_no_cross_resource_grant(self):
        row = self.create()
        actor, role, _ = self.actor(['tax-codes.read'])
        self.assertEqual(actor.request(self.path('codes'))[0], 200)
        self.assertEqual(actor.request(self.path('codes/' + row['id'] + '/audit'))[0], 200)
        self.assertEqual(actor.request(self.path('lookups'))[0], 200)
        for route in ('types', 'nature-codes'):
            self.assertEqual(actor.request(self.path(route))[0], 403)
        self.assertEqual(actor.request(self.path('codes'), 'POST', self.payload())[0], 403)
        self.assertEqual(actor.request(self.path('codes/' + row['id'] + '/deactivate'), 'POST', {'expectedVersion': row['version']})[0], 403)
        self.assertEqual(self.root.request('/api/links/role-permissions/' + role['id'] + '?tenantId=' + self.tenant_id, 'PUT', {'ids': []})[0], 204)
        self.assertEqual(actor.request(self.path('codes'))[0], 403)
        self.assertEqual(Client().request(self.path('codes'))[0], 401)
        self.assertEqual(actor.request(self.path('codes', tenant=str(uuid.uuid4())))[0], 403)

    def test_csrf_foreign_origin_and_audit_failure_roll_back_all_changes(self):
        self.assertIn(self.root.request(self.path('codes'), 'POST', self.payload(), csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(self.path('codes'), 'POST', self.payload(), origin='https://foreign.invalid')[0], 403)
        row = self.create()
        self.sql("CREATE FUNCTION taxmanagement.proof_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                 f"IF NEW.tenant_id='{self.tenant_id}'::uuid THEN RAISE EXCEPTION 'Rifiuto audit sintetico'; END IF; RETURN NEW; END $$; "
                 "CREATE CONSTRAINT TRIGGER proof_reject_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.proof_reject_audit();")
        try:
            self.update(row, {'name': 'Mai committata'}, 500)
            self.assertEqual(self.req('codes/' + row['id']), row)
            self.schedule(row, expected=500)
            self.assertEqual(self.req('codes/' + row['id']), row)
            self.assertEqual(len(self.req('codes/' + row['id'] + '/audit')['items']), 1)
            self.req('codes', 'POST', self.payload(), 500)
            self.assertEqual(self.req('codes')['total'], 1)
        finally:
            self.sql('DROP TRIGGER proof_reject_audit ON foundation.audit_event; DROP FUNCTION taxmanagement.proof_reject_audit();')
