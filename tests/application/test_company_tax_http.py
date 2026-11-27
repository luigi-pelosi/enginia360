"""Phase 3 real cookie/CSRF HTTP acceptance; writes only to labelled tmpfs DB.

Synthetic identifiers satisfy the implemented formal policy, not VIES validation.
Discovery is safe; execution requires run_company_tax_proof.py and exact labels.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import json
import os
from pathlib import Path
import unittest
from urllib.parse import urlencode
import uuid

from tax_helpers import configure_fixture, login_root
from test_api import Client
from test_tax_http import TaxHttp

ACTIONS = ('read', 'create', 'update', 'activate', 'suspend', 'register', 'close', 'assign_regime', 'schedule_regime')
PREFIX = 'company-tax-configurations.'


class CompanyTaxHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('ENGINIA360_COMPANY_TAX_PROOF') != '1':
            raise RuntimeError('Execute only through run_company_tax_proof.py')
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        if not all(cls.fixture.verify_target(x) for x in (cls.fixture.DB, cls.fixture.API)):
            raise RuntimeError('Labelled isolated CompanyTax fixture unavailable')
        cls.root, cls.credentials = login_root()

    def setUp(self):
        self.code = 'ctax-' + uuid.uuid4().hex[:12]
        status, tenant = self.root.request('/api/data/tenants', 'POST', {'code': self.code, 'name': 'Synthetic company tax proof'})
        self.assertEqual(status, 201, tenant)
        self.tenant_id = tenant['id']
        self.refs = self.req('company-lookups')
        self.vat = next(x for x in self.refs['types'] if x['code'] == 'VAT')
        self.countries = {x['iso_code']: x for x in self.refs['countries']}
        self.country_id = self.countries['IT']['id']
        self.regime = next(x for x in self.refs['regimes'] if x['country_id'] == self.country_id and x['tax_type_id'] == self.vat['id'] and x['code'] == 'ORDINARY' and x['is_supported'] and x['is_active'])
        self.today = date.fromisoformat(self.sql("SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date;"))
        self.start = max(date.fromisoformat(self.regime['valid_from']), self.today - timedelta(days=30)).isoformat()
        self.future = (self.today + timedelta(days=30)).isoformat()
        self.later = (self.today + timedelta(days=60)).isoformat()
        self.company = self.company_create()

    actor = TaxHttp.actor

    def path(self, route, tenant=None, **query):
        return '/api/tax/' + route + '?' + urlencode({'tenantId': tenant or self.tenant_id, **query})

    def scope(self, route):
        return route + ('&' if '?' in route else '?') + 'tenantId=' + self.tenant_id

    def req(self, route, method='GET', body=None, expected=200, tenant=None, client=None, **query):
        status, result = (client or self.root).request(self.path(route, tenant, **query), method, body)
        if isinstance(expected, tuple):
            self.assertIn(status, expected, (method, route, status, result))
        else:
            self.assertEqual(status, expected, (method, route, status, result))
        return result

    def sql(self, statement):
        return self.fixture.sql(statement).stdout.strip()

    def catalog_flag(self, field, value):
        if field not in ('is_supported', 'is_active') or not isinstance(value, bool):
            raise ValueError('Finite fixture catalog fault only')
        self.sql("BEGIN; ALTER TABLE taxmanagement.tax_regimes DISABLE TRIGGER tax_regimes_immutable; UPDATE taxmanagement.tax_regimes SET " + field + "=" + str(value).lower() + " WHERE id='" + self.regime['id'] + "'; ALTER TABLE taxmanagement.tax_regimes ENABLE TRIGGER tax_regimes_immutable; COMMIT;")
        self.assertEqual(self.sql("SELECT " + field + " FROM taxmanagement.tax_regimes WHERE id='" + self.regime['id'] + "';"), 't' if value else 'f')

    def company_create(self, client=None, expected=201, **extra):
        status, row = (client or self.root).request(self.scope('/api/data/companies/save'), 'POST', {'values': {'name': 'Company ' + uuid.uuid4().hex[:12]}, **extra})
        self.assertEqual(status, expected, row)
        return row

    def company_read(self, company=None):
        # Generic resources expose a paged collection GET, not an item GET.
        target = (company or self.company)['id']
        page = 1
        while True:
            status, body = self.root.request(self.scope('/api/data/companies?pageSize=100&page=' + str(page)))
            self.assertEqual(status, 200, body)
            matches = [row for row in body['items'] if row['id'] == target]
            self.assertLessEqual(len(matches), 1, body)
            if matches:
                return matches[0]
            self.assertTrue(body['items'] and page * body['pageSize'] < body['total'], ('Company missing from actual collection', target, body))
            page += 1

    def list_route(self, company=None):
        return 'companies/' + (company or self.company)['id'] + '/configurations'

    def route(self, root):
        return 'company-configurations/' + root['id']

    def identifier(self, iso='IT'):
        digits = f'{uuid.uuid4().int % 100000000000:011d}'
        if iso == 'IT':
            return 'IT' + digits
        if iso == 'DE':
            return 'DE' + digits[:9]
        return 'FRAB' + digits[:9]

    def profile(self, **changes):
        return {'tax_regime_id': self.regime['id'], 'valid_from': self.start, 'valid_to': None, **changes}

    def registration(self, profiles=True, **changes):
        result = {'values': {'country_id': self.country_id, 'tax_identifier': self.identifier(), 'registration_type': 'DOMESTIC', 'valid_from': self.start, 'valid_to': None, 'notes': 'Synthetic formal policy only; not VIES', **changes}}
        if profiles:
            result['profiles'] = [self.profile()]
        return result

    def payload(self, registrations=None, **values):
        # None means a complete valid initial chain; [] remains explicitly empty.
        # Respect the explicit establishment country, not a guessed IT registration.
        if registrations is None:
            country = values.get('establishment_country_id', self.country_id)
            regime = next((r for r in self.refs['regimes'] if r['country_id'] == country and r['is_supported']), self.regime)
            iso = next((c['iso_code'] for c in self.refs['countries'] if c['id'] == country), 'IT')
            registration = self.registration(country_id=country, tax_identifier=self.identifier(iso))
            registration['profiles'] = [self.profile(tax_regime_id=regime['id'])]
            registrations = [registration]
        return {'values': {'tax_type_id': self.vat['id'], 'establishment_country_id': self.country_id, **values}, 'registrations': registrations}

    def foreign_registration(self, profiles=True, **changes):
        reg = self.registration(profiles=profiles, country_id=self.countries['DE']['id'], tax_identifier=self.identifier('DE'), registration_type='DIRECT_IDENTIFICATION', **changes)
        if profiles:
            regime = next(r for r in self.refs['regimes'] if r['country_id'] == self.countries['DE']['id'] and r['is_supported'])
            reg['profiles'] = [self.profile(tax_regime_id=regime['id'])]
        return reg

    def with_unprofiled_registration(self, **changes):
        # Additional registrations intentionally retain the optional-profile contract.
        root = self.create([self.foreign_registration()])
        return self.command(root, 'registrations', self.registration(profiles=False, **changes), 201)

    def create(self, registrations=None, company=None, client=None, expected=201, **values):
        return self.req(self.list_route(company), 'POST', self.payload(registrations, **values), expected, client=client)

    def read(self, root):
        return self.req(self.route(root))

    def command(self, root, action, body=None, expected=200, client=None):
        return self.req(self.route(root) + '/' + action, 'POST', {'expectedVersion': root['version'], **(body or {})}, expected, client=client)

    def assign(self, root, registration, schedule=False, expected=None, **changes):
        return self.command(root, 'registrations/' + registration['id'] + '/regimes' + ('/schedule' if schedule else ''), {'values': self.profile(**changes)}, expected if expected is not None else (200 if schedule else 201))

    def resolve(self, registration, company=None, expected=200, day=None, new=False, client=None):
        return self.req('companies/' + (company or self.company)['id'] + '/registrations/' + registration['id'] + '/resolve', expected=expected, date=day or self.today.isoformat(), forNewUse=str(new).lower(), client=client)

    def assign_companies(self, role, companies):
        status, body = self.root.request(self.scope('/api/roles/' + role['id'] + '/companies'), 'PUT', {'companyIds': [x['id'] for x in companies]})
        self.assertIn(status, (200, 204), body)
        status, actual = self.root.request(self.scope('/api/roles/' + role['id'] + '/companies'))
        self.assertEqual(status, 200, actual)
        self.assertEqual(set(actual['companyIds']), {x['id'] for x in companies})
        return actual

    def test_catalog_readonly_policy_and_permission_catalog(self):
        rows = self.req('regimes', pageSize=100)
        self.assertEqual(rows['total'], len(rows['items']))
        supported = [x for x in rows['items'] if x['is_supported']]
        self.assertEqual({next(c['iso_code'] for c in self.refs['countries'] if c['id'] == x['country_id']) for x in supported}, {'IT', 'DE', 'FR'})
        self.assertTrue(all(x['code'] == 'ORDINARY' and x['tax_type_id'] == self.vat['id'] for x in supported))
        self.assertEqual(len(supported), 3)
        self.assertEqual({x['valid_from'] for x in supported}, {'2026-11-26'}, 'Implementation support snapshot, not a statutory date')
        self.assertEqual(set(self.refs['registrationTypesByCountry']['IT']), {'DOMESTIC', 'DIRECT_IDENTIFICATION', 'FISCAL_REPRESENTATIVE'})
        for iso in ('DE', 'FR'):
            self.assertEqual(set(self.refs['registrationTypesByCountry'][iso]), {'DOMESTIC', 'DIRECT_IDENTIFICATION'})
        for method in ('POST', 'PUT', 'DELETE'):
            self.req('regimes', method, {}, (404, 405))
        catalog = []
        for page in (1, 2):
            status, body = self.root.request(self.scope('/api/data/permissions?pageSize=100&page=' + str(page)))
            self.assertEqual(status, 200, body)
            catalog.extend(body['items'])
        self.assertEqual((body['total'], len(catalog)), (134, 134))
        self.assertTrue({PREFIX + action for action in ACTIONS} | {'tax-regimes.read'} <= {x['code'] for x in catalog})

    def test_draft_nested_read_model_explicit_establishment_and_independent_general(self):
        general = self.company_read()
        root = self.create([self.registration()])
        self.assertEqual((root['status'], root['version'], root['establishment_country_id']), ('DRAFT', 1, self.country_id))
        self.assertEqual(len(root['registrations'][0]['profiles']), 1)
        self.assertEqual(self.req(self.list_route())['items'], [root])
        self.assertEqual(self.read(root), root)
        self.assertEqual(self.company_read(), general)
        self.req(self.list_route(), 'POST', {'values': {'tax_type_id': self.vat['id']}}, 400)
        self.req(self.route(root), 'PUT', {'values': {'establishment_country_id': self.countries['DE']['id']}, 'expectedVersion': 1}, 400)
        self.req(self.route(root), 'DELETE', expected=(404, 405))
        self.create(expected=409)

    def test_activation_utc_coverage_and_historical_suspension(self):
        initial = self.foreign_registration(valid_from=self.future)
        initial['profiles'][0]['valid_from'] = self.future
        root = self.create([initial])
        self.command(root, 'activate', expected=409)
        root = self.command(root, 'registrations', self.registration(profiles=False), 201)
        registration = next(r for r in root['registrations'] if r['country_id'] == self.country_id)
        self.command(root, 'activate', expected=409)
        root = self.assign(root, registration)
        self.assertEqual(root['version'], 3)
        root = self.command(root, 'activate')
        self.assertEqual((root['status'], root['version']), ('ACTIVE', 4))
        resolved = self.resolve(registration, new=True)
        self.assertEqual((resolved['tenantId'], resolved['companyId'], resolved['taxRegimeCode']), (self.tenant_id, self.company['id'], 'ORDINARY'))
        root = self.command(root, 'suspend')
        self.resolve(registration, new=True, expected=409)
        self.assertEqual(self.resolve(registration), resolved)
        self.assertEqual(root['status'], 'SUSPENDED')

    def test_future_only_and_gap_fail_closed(self):
        reg = self.registration(valid_from=self.future)
        reg['profiles'] = [self.profile(valid_from=self.future, valid_to=self.future)]
        root = self.create([reg])
        self.command(root, 'activate', expected=409)
        child = root['registrations'][0]
        self.resolve(child, expected=404)
        self.resolve(child, day=self.future)
        self.resolve(child, day=self.later, expected=404)
        for invalid in ('2026-02-30', '2026-1-01'):
            self.resolve(child, day=invalid, expected=400)

    def test_schedule_boundaries_overlap_and_stale_root_revision(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        general = self.company_read()
        scheduled = self.assign(root, child, schedule=True, valid_from=self.future)
        profiles = sorted(scheduled['registrations'][0]['profiles'], key=lambda x: x['valid_from'])
        self.assertEqual((scheduled['version'], len(profiles)), (2, 2))
        self.assertEqual(profiles[0]['valid_to'], (date.fromisoformat(self.future) - timedelta(days=1)).isoformat())
        for day, profile in ((self.start, profiles[0]), (profiles[0]['valid_to'], profiles[0]), (self.future, profiles[1])):
            self.assertEqual(self.resolve(child, day=day)['taxRegimeProfileId'], profile['id'])
        self.assign(root, child, schedule=True, valid_from=self.later, expected=409)
        self.assign(scheduled, child, valid_from=self.future, expected=409)
        self.assertEqual(self.read(root), scheduled)
        self.assertEqual(self.company_read(), general)

    def test_two_concurrent_writers_exactly_one_wins(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        # Independent cookie jars avoid using a shared urllib opener concurrently.
        clients = [login_root()[0], login_root()[0]]
        def write(pair):
            client, day = pair
            return client.request(self.path(self.route(root) + '/registrations/' + child['id'] + '/regimes/schedule'), 'POST', {'expectedVersion': root['version'], 'values': self.profile(valid_from=day)})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, zip(clients, (self.future, self.later))))
        self.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        after = self.read(root)
        self.assertEqual((after['version'], len(after['registrations'][0]['profiles'])), (2, 2))

    def test_close_cascades_profiles_and_active_guard(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        root = self.command(root, 'activate')
        yesterday = (self.today - timedelta(days=1)).isoformat()
        self.command(root, 'registrations/' + child['id'] + '/close', {'valid_to': yesterday}, 409 if self.start < self.today.isoformat() else 400)
        self.assertEqual(self.read(root), root)
        root = self.command(root, 'suspend')
        closed = self.command(root, 'registrations/' + child['id'] + '/close', {'valid_to': self.today.isoformat()})
        self.assertEqual(closed['registrations'][0]['valid_to'], self.today.isoformat())
        self.assertEqual(closed['registrations'][0]['profiles'][0]['valid_to'], self.today.isoformat())
        self.command(closed, 'registrations/' + child['id'] + '/close', {'valid_to': self.future}, 409)
        self.resolve(child, day=self.future, expected=404)

    def test_close_rejects_future_profile_without_partial_changes(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        root = self.assign(root, child, schedule=True, valid_from=self.future)
        self.command(root, 'registrations/' + child['id'] + '/close', {'valid_to': self.today.isoformat()}, 409)
        self.assertEqual(self.read(root), root)

    def test_global_initial_company_atomicity_and_update_rejection(self):
        created = self.company_create(taxConfigurations=[self.payload([self.registration()])])
        roots = self.req(self.list_route(created))['items']
        self.assertEqual((len(roots), roots[0]['status'], roots[0]['version']), (1, 'DRAFT', 1))
        count = self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';")
        self.company_create(taxConfigurations=[self.payload([self.registration(tax_identifier='INVALID')])], expected=400)
        self.company_create(taxConfigurations=[self.payload(), self.payload()], expected=400)
        self.assertEqual(self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';"), count)
        for field in ([], [self.payload()]):
            status, body = self.root.request(self.scope('/api/data/companies/' + created['id'] + '/save'), 'PUT', {'values': {'name': 'Must not persist'}, 'taxConfigurations': field})
            self.assertEqual(status, 400, body)
        self.assertEqual(self.company_read(created)['name'], created['name'])

    def test_ordinary_creation_empty_allowed_but_initial_tax_not_provisioning_bypass(self):
        actor, role, _ = self.actor(['companies.read', 'companies.create'] + [PREFIX + x for x in ACTIONS])
        self.assign_companies(role, [self.company])
        self.company_create(client=actor)
        self.company_create(client=actor, taxConfigurations=[])
        self.company_create(client=actor, taxConfigurations=[self.payload()], expected=403)

    def test_cookie_csrf_origin_and_tenant_isolation(self):
        root = self.create([self.registration()])
        self.req(self.list_route(), client=Client(), expected=401)
        route = self.path(self.route(root) + '/activate')
        self.assertIn(self.root.request(route, 'POST', {'expectedVersion': 1}, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(route, 'POST', {'expectedVersion': 1}, origin='https://foreign.invalid')[0], 403)
        status, other = self.root.request('/api/data/tenants', 'POST', {'code': 'foreign-' + uuid.uuid4().hex[:10], 'name': 'Other isolated tenant'})
        self.assertEqual(status, 201, other)
        self.req(self.route(root), tenant=other['id'], expected=404)
        self.req(self.list_route(), tenant=other['id'], expected=404)
        actor, role, _ = self.actor(['companies.read', PREFIX + 'read'])
        self.assign_companies(role, [self.company])
        self.req(self.route(root), tenant=other['id'], client=actor, expected=403)
        self.assertEqual(self.read(root), root)

    def test_same_role_company_action_crossed_union_deny_and_live_revocation(self):
        other = self.company_create()
        root = self.create()
        actor, read_role, _ = self.actor(['companies.read', PREFIX + 'read'])
        self.assign_companies(read_role, [self.company])
        _, write_role, _ = self.actor([PREFIX + 'register'])
        self.assign_companies(write_role, [other])
        status, session = actor.request('/api/session')
        self.assertEqual(status, 200, session)
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/' + session['id']), 'PUT', {'ids': [read_role['id'], write_role['id']]})[0], 204)
        self.req(self.route(root), client=actor)
        permissions = self.req('companies/' + self.company['id'] + '/permissions', client=actor)['permissions']
        self.assertIn('read', permissions)
        self.assertNotIn('register', permissions)
        self.command(root, 'registrations', self.foreign_registration(profiles=False), 403, client=actor)
        self.assign_companies(write_role, [self.company])
        self.command(root, 'registrations', self.foreign_registration(profiles=False), 201, client=actor)
        self.assign_companies(read_role, [])
        self.req(self.route(root), client=actor, expected=403)
        self.assign_companies(read_role, [self.company])
        self.assertEqual(self.root.request(self.scope('/api/links/role-permissions/' + read_role['id']), 'PUT', {'ids': []})[0], 204)
        self.req(self.route(root), client=actor, expected=403)

    def test_scoped_permissions_base_read_and_readonly_lookup_separation(self):
        root = self.create()
        actor, role, _ = self.actor(['companies.read', PREFIX + 'read'])
        self.assign_companies(role, [self.company])
        self.req('company-lookups', client=actor)
        self.req(self.route(root), client=actor)
        self.req('regimes', client=actor, expected=403)
        self.command(root, 'activate', expected=403, client=actor)
        self.assertEqual(set(self.req('companies/' + self.company['id'] + '/permissions')['permissions']), set(ACTIONS))
        reader, _, _ = self.actor(['tax-regimes.read'])
        self.req('regimes', client=reader)
        self.req(self.route(root), client=reader, expected=403)
        no_base, role, _ = self.actor([PREFIX + 'read'])
        self.assign_companies(role, [self.company])
        self.req(self.route(root), client=no_base, expected=403)
        self.req('companies/' + self.company['id'] + '/permissions', client=no_base, expected=403)

    def test_company_disabled_read_history_allowed_new_writes_denied(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        root = self.command(root, 'activate')
        status, body = self.root.request(self.scope('/api/data/companies/' + self.company['id']), 'PUT', {'is_enabled': False})
        self.assertEqual(status, 200, body)
        self.assertFalse(self.company_read()['is_enabled'])
        self.assertEqual(self.read(root), root)
        self.resolve(child)
        self.resolve(child, new=True, expected=409)
        self.command(root, 'registrations', self.registration(), 409)

    def test_formal_identifier_normalization_rejection_and_country_policy(self):
        reg = self.registration()
        identifier = reg['values']['tax_identifier']
        reg['values']['tax_identifier'] = identifier
        root = self.create([reg])
        self.assertEqual(root['registrations'][0]['tax_identifier'], identifier)
        # Independent complete configuration; foreign seed avoids DOMESTIC collisions.
        company = self.company_create()
        other = self.create([self.foreign_registration()], company=company)
        for bad in (' ' + identifier, identifier + ' ', identifier[2:], identifier.lower(), 'IT123'):
            self.command(other, 'registrations', self.registration(tax_identifier=bad), 400)
        self.command(other, 'registrations', self.registration(registration_type='DIRECT_IDENTIFICATION'), 400)
        self.command(other, 'registrations', self.registration(country_id=self.countries['DE']['id'], tax_identifier=self.identifier('DE')), 400)
        self.assertEqual(self.read(other), other)

    def test_tenant_identifier_duplicates_even_between_companies(self):
        reg = self.registration()
        self.create([reg])
        other = self.company_create()
        self.create([reg], company=other, expected=409)
        root = self.create([self.registration()], company=other)
        self.assertEqual(len(root['registrations']), 1)
        self.command(root, 'registrations', self.registration(), 409)  # unique DOMESTIC interval
        self.assertEqual(self.read(root), root)

    def test_unsupported_and_scope_mismatched_regimes_denied(self):
        root = self.with_unprofiled_registration()
        child = next(r for r in root['registrations'] if r['country_id'] == self.country_id)
        # Exercise explicit unsupported policy against the actual finite seed,
        # restoring catalog state even on failure (this is the labelled DB only).
        self.catalog_flag('is_supported', False)
        try:
            self.assign(root, child, expected=409)
        finally:
            self.catalog_flag('is_supported', True)
        wrong = next(x for x in self.refs['regimes'] if x['country_id'] != self.country_id and x['is_supported'])
        self.assign(root, child, tax_regime_id=wrong['id'], expected=400)
        self.assign(root, child, tax_regime_id=str(uuid.uuid4()), expected=404)
        self.assertEqual(self.read(root), root)

    def test_child_strict_payload_and_safe_revision_validation(self):
        root = self.with_unprofiled_registration()
        child = next(r for r in root['registrations'] if r['country_id'] == self.country_id)
        for version in (0, -1, 1.5, 9007199254740992, '1', None):
            self.command(root, 'activate', {'expectedVersion': version}, 400)
        for changes in ({'valid_from': '2026-02-30'}, {'valid_from': '2026-1-01'}, {'valid_to': '1900-01-01'}, {'id': str(uuid.uuid4())}, {'country_id': self.country_id}):
            self.assign(root, child, expected=400, **changes)
        self.command(root, 'registrations', {'values': {**self.registration()['values'], 'company_id': self.company['id']}}, 400)
        self.assertEqual(self.read(root), root)

    def test_audit_failure_rolls_back_root_close_profiles_and_parent_creation(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        count = self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';")
        audits = self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';")
        self.sql("CREATE FUNCTION taxmanagement.company_tax_proof_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.tenant_id='" + self.tenant_id + "'::uuid THEN RAISE EXCEPTION 'synthetic phase3 audit rejection'; END IF; RETURN NEW; END $$; CREATE CONSTRAINT TRIGGER company_tax_proof_reject AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.company_tax_proof_reject();")
        try:
            self.command(root, 'registrations/' + child['id'] + '/close', {'valid_to': self.today.isoformat()}, 500)
            self.assertEqual(self.read(root), root)
            self.assign(root, child, schedule=True, valid_from=self.future, expected=500)
            self.assertEqual(self.read(root), root)
            self.company_create(taxConfigurations=[self.payload([self.registration()])], expected=500)
            self.assertEqual(self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';"), count)
            self.assertEqual(self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';"), audits)
        finally:
            self.sql('DROP TRIGGER company_tax_proof_reject ON foundation.audit_event; DROP FUNCTION taxmanagement.company_tax_proof_reject();')
        closed = self.command(root, 'registrations/' + child['id'] + '/close', {'valid_to': self.today.isoformat()})
        self.assertEqual(closed['version'], root['version'] + 1)
        self.assertEqual(self.read(root), closed)

    def test_group_role_scope_enabled_role_and_live_group_revocation(self):
        root = self.create()
        actor, direct, _ = self.actor(['companies.read'])
        _, granted, _ = self.actor([PREFIX + 'read'])
        self.assign_companies(granted, [self.company])
        user = actor.request('/api/session')[1]['id']
        status, group = self.root.request(self.scope('/api/data/groups'), 'POST', {'name': 'Phase3 bounded group'})
        self.assertEqual(status, 201, group)
        for relation, owner, ids in (('group-users', group['id'], [user]), ('group-roles', group['id'], [granted['id']])):
            self.assertEqual(self.root.request(self.scope('/api/links/' + relation + '/' + owner), 'PUT', {'ids': ids})[0], 204)
        self.req(self.route(root), client=actor)
        self.assertEqual(self.root.request(self.scope('/api/data/roles/' + granted['id']), 'PUT', {'is_enabled': False})[0], 200)
        self.req(self.route(root), client=actor, expected=403)
        self.assertEqual(self.root.request(self.scope('/api/data/roles/' + granted['id']), 'PUT', {'is_enabled': True})[0], 200)
        self.req(self.route(root), client=actor)
        self.assertEqual(self.root.request(self.scope('/api/links/group-roles/' + group['id']), 'PUT', {'ids': []})[0], 204)
        self.req(self.route(root), client=actor, expected=403)

    def test_each_mutation_requires_own_action_not_read_union(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        actor, role, _ = self.actor(['companies.read', PREFIX + 'read'])
        self.assign_companies(role, [self.company])
        self.create(company=self.company_create(), client=actor, expected=403)
        commands = [('activate', None), ('suspend', None), ('registrations', self.registration(profiles=False)),
                    ('registrations/' + child['id'] + '/close', {'valid_to': self.future}),
                    ('registrations/' + child['id'] + '/regimes', {'values': self.profile()}),
                    ('registrations/' + child['id'] + '/regimes/schedule', {'values': self.profile(valid_from=self.future)})]
        for action, body in commands:
            self.command(root, action, body, 403, client=actor)
        self.assertEqual(self.read(root), root)

    def test_finite_it_de_fr_formal_only_and_foreign_registration_types(self):
        # Deliberately structural identifiers; no checksum or VIES assertion.
        for iso, number in (('IT', 'IT12345678901'), ('DE', 'DE123456789'), ('FR', 'FRAB123456789')):
            company = self.company_create()
            regime = next(x for x in self.refs['regimes'] if x['country_id'] == self.countries[iso]['id'] and x['is_supported'])
            reg = self.registration(country_id=self.countries[iso]['id'], tax_identifier=number)
            reg['profiles'] = [self.profile(tax_regime_id=regime['id'])]
            root = self.create([reg], company=company, establishment_country_id=self.countries[iso]['id'])
            self.assertEqual(root['registrations'][0]['tax_identifier'], number)
            # Same country cannot be declared foreign, independent of identifier format.
            self.command(root, 'registrations', self.registration(profiles=False, country_id=self.countries[iso]['id'], tax_identifier=self.identifier(iso), registration_type='DIRECT_IDENTIFICATION'), 400)
        company = self.company_create()
        # Fiscal lookups intentionally expose only the finite supported countries.
        # Select an actual enabled unsupported foundation country in our fixture.
        unsupported_home = {'id': self.sql("SELECT id FROM foundation.country WHERE is_enabled AND iso_code NOT IN ('IT','DE','FR') ORDER BY iso_code LIMIT 1;")}
        self.assertTrue(unsupported_home['id'], 'Unsupported foundation country fixture required')
        self.create(company=company, establishment_country_id=unsupported_home['id'], expected=400)
        home = self.countries['DE']
        root = self.create(company=company, establishment_country_id=home['id'])
        for iso in ('IT', 'FR'):
            reg = self.registration(profiles=False, country_id=self.countries[iso]['id'], tax_identifier=self.identifier(iso), registration_type='DIRECT_IDENTIFICATION')
            root = self.command(root, 'registrations', reg, 201)
            representative = self.registration(profiles=False, country_id=self.countries[iso]['id'], tax_identifier=self.identifier(iso), registration_type='FISCAL_REPRESENTATIVE')
            if iso == 'IT':
                root = self.command(root, 'registrations', representative, 201)
            else:
                self.command(root, 'registrations', representative, 400)
        self.command(root, 'registrations', self.registration(profiles=False, country_id=unsupported_home['id']), 400)
        self.assertEqual(self.read(root), root)

    def test_profile_before_implementation_snapshot_is_rejected(self):
        root = self.with_unprofiled_registration(valid_from='2026-11-25')
        child = next(r for r in root['registrations'] if r['country_id'] == self.country_id)
        self.assign(root, child, valid_from='2026-11-25', expected=400)
        self.assertEqual(self.read(root), root)
        self.assign(root, child, valid_from='2026-11-26')

    def test_registration_list_explicit_candidates_and_historical_inactive_catalog(self):
        root = self.create([self.registration()])
        child = root['registrations'][0]
        route = 'companies/' + self.company['id'] + '/registrations'
        query = {'date': self.today.isoformat(), 'tax_type_id': self.vat['id']}
        self.assertEqual(self.req(route, forNewUse='true', **query)['items'], [])
        self.assertEqual([x['id'] for x in self.req(route, forNewUse='false', **query)['items']], [child['id']])
        root = self.command(root, 'activate')
        self.assertEqual([x['id'] for x in self.req(route, forNewUse='true', **query)['items']], [child['id']])
        self.catalog_flag('is_active', False)
        try:
            self.resolve(child)
            self.resolve(child, new=True, expected=409)
            self.assertEqual(self.req(route, forNewUse='true', **query)['items'], [])
            self.assertEqual([x['id'] for x in self.req(route, forNewUse='false', **query)['items']], [child['id']])
        finally:
            self.catalog_flag('is_active', True)
