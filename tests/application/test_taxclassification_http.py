"""Real HTTP Phase 2 proof. All writes require the isolated labelled fixture."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import unittest
from urllib.parse import urlencode
import uuid

from tax_helpers import configure_fixture, login_root
from test_api import Client
from test_tax_http import TaxHttp

KINDS = ('item', 'partner')
ITEM_TEMPLATES = {'GENERAL_GOODS', 'GENERAL_SERVICES', 'FOOD', 'BOOKS', 'MEDICAL_GOODS', 'DIGITAL_SERVICES', 'REPAIR_SERVICES', 'TRANSPORT_SERVICES', 'INTELLECTUAL_PROPERTY', 'ANCILLARY_CHARGES'}
PARTNER_TEMPLATES = {'TAXABLE_PERSON', 'NON_TAXABLE_PERSON', 'UNKNOWN'}


class TaxClassificationHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('ENGINIA360_TAXCLASSIFICATION_PROOF') != '1':
            raise RuntimeError('Run only through run_taxclassification_proof.py')
        cls.fixture = configure_fixture('enginia360-taxclassification-proof')
        if not all(cls.fixture.verify_target(x) for x in (cls.fixture.DB, cls.fixture.API)):
            raise RuntimeError('TaxClassification fixture unavailable')
        cls.root, cls.credentials = login_root()
        status, countries = cls.root.request('/api/data/countries?pageSize=100&search=Italia')
        assert status == 200, countries
        italy = next((x for x in countries['items'] if x['iso_code'] == 'IT'), None)
        if italy is None:
            status, italy = cls.root.request('/api/data/countries', 'POST', {'name': 'Italia', 'iso_code': 'IT'})
            assert status == 201, italy
        cls.country_id = italy['id']

    def setUp(self):
        self.code = 'class-' + uuid.uuid4().hex[:12]
        status, tenant = self.root.request('/api/data/tenants', 'POST', {'code': self.code, 'name': 'Tax classification isolated proof'})
        self.assertEqual(status, 201, tenant)
        self.tenant_id = tenant['id']
        self.refs = self.req('classification-lookups', kind='item')
        self.vat = next(t for t in self.refs['types'] if t['code'] == 'VAT')

    # Reuse only the finite account/role provisioning helper, not Phase 1 tests/setup.
    actor = TaxHttp.actor

    def path(self, route, tenant=None, **query):
        return '/api/tax/' + route + '?' + urlencode({'tenantId': tenant or self.tenant_id, **query})

    def req(self, route, method='GET', body=None, expected=200, tenant=None, client=None, **query):
        status, response = (client or self.root).request(self.path(route, tenant, **query), method, body)
        self.assertEqual(status, expected, (route, method, status, response))
        return response

    def sql(self, statement):
        return self.fixture.sql(statement).stdout.strip()

    def scope(self, path):
        return path + ('&' if '?' in path else '?') + 'tenantId=' + self.tenant_id

    def values(self, **changes):
        return {'code': 'CLASS_' + uuid.uuid4().hex[:12], 'name': 'Synthetic classification',
                'description': 'No tax determination', 'country_id': self.country_id, 'tax_type_id': self.vat['id'], **changes}

    def classification(self, kind, **changes):
        return self.req(kind + '-classifications', 'POST', {'values': self.values(**changes)}, 201)

    def profiles(self, kind, subject):
        return ('items' if kind == 'item' else 'partners') + '/' + subject['id'] + '/profiles'

    def profile(self, kind, classification, **changes):
        return {'country_id': classification['country_id'], 'tax_type_id': classification['tax_type_id'],
                kind + '_tax_classification_id': classification['id'], 'valid_from': '2026-01-01', 'valid_to': None, **changes}

    def subject_payload(self, kind, **extra):
        if kind == 'partner':
            return {'values': {'kind': 'ORGANIZATION', 'legal_name': 'Synthetic partner ' + uuid.uuid4().hex[:8], 'status': 'ACTIVE'}, **extra}
        if not hasattr(self, 'item_refs'):
            self.item_refs = {}
            for resource in ('types', 'units'):
                status, body = self.root.request(self.scope('/api/catalog/' + resource + '?pageSize=100'))
                self.assertEqual(status, 200, body)
                self.item_refs[resource] = body['items']
            status, category = self.root.request(self.scope('/api/catalog/categories'), 'POST', {'values': {'name': 'Tax proof category', 'is_active': True}})
            self.assertEqual(status, 201, category)
            self.item_refs['category'] = category
        good = next(t for t in self.item_refs['types'] if t['kind'] == 'GOOD')
        unit = next(t for t in self.item_refs['units'] if t['dimension'] == 'COUNT' and t['is_base'])
        return {'values': {'name': 'Synthetic item ' + uuid.uuid4().hex[:8], 'item_type_id': good['id'],
                           'category_id': self.item_refs['category']['id'], 'base_uom_id': unit['id']}, **extra}

    def subject_endpoint(self, kind, subject=None, write=False):
        path = '/api/catalog/items' if kind == 'item' else '/api/data/business-partners'
        if subject:
            path += '/' + subject['id']
        if kind == 'partner' and write:
            path += '/save'
        return self.scope(path)

    def subject(self, kind, expected=201, client=None, **extra):
        status, body = (client or self.root).request(self.subject_endpoint(kind, write=True), 'POST', self.subject_payload(kind, **extra))
        self.assertEqual(status, expected, (kind, status, body))
        return body

    def subject_read(self, kind, subject):
        status, body = self.root.request(self.subject_endpoint(kind, subject))
        self.assertEqual(status, 200, body)
        return body

    def subject_update(self, kind, subject, name):
        values = {'name' if kind == 'item' else 'legal_name': name}
        status, body = self.root.request(self.subject_endpoint(kind, subject, True), 'PUT', {'values': values, 'expectedVersion': subject['version']})
        self.assertEqual(status, 200, body)
        return body

    def write_profile(self, kind, subject, classification, version=0, schedule=False, expected=None, **changes):
        return self.req(self.profiles(kind, subject) + ('/schedule' if schedule else ''), 'POST',
                        {'values': self.profile(kind, classification, **changes), 'expectedVersion': version},
                        expected if expected is not None else (200 if schedule else 201))

    def resolve(self, kind, subject, date='2026-06-01', expected=200, **query):
        return self.req(self.profiles(kind, subject) + '/resolve', expected=expected,
                        country_id=self.country_id, tax_type_id=self.vat['id'], date=date, **query)

    def lifecycle(self, kind):
        route = kind + '-classifications'
        self.assertEqual(self.req(route)['total'], 0, 'No implicit tenant templates')
        created = self.classification(kind)
        self.assertEqual(created['version'], 1)
        self.assertEqual(self.req(route + '/' + created['id']), created)
        self.req(route, 'POST', {'values': self.values(code=created['code'].lower())}, 409)
        self.req(route + '/' + created['id'], 'PUT', {'values': {'code': 'CHANGED'}, 'expectedVersion': 1}, 400)
        changed = self.req(route + '/' + created['id'], 'PUT', {'values': {'name': 'Changed', 'description': None}, 'expectedVersion': 1})
        self.assertEqual(changed['version'], 2)
        self.req(route + '/' + created['id'], 'PUT', {'values': {'name': 'Stale'}, 'expectedVersion': 1}, 409)
        disabled = self.req(route + '/' + created['id'] + '/deactivate', 'POST', {'expectedVersion': 2})
        self.assertFalse(disabled['is_active'])
        self.req(route + '/' + created['id'] + '/reactivate', 'POST', {'expectedVersion': 2}, 409)
        enabled = self.req(route + '/' + created['id'] + '/reactivate', 'POST', {'expectedVersion': disabled['version']})
        self.assertTrue(enabled['is_active'])
        self.assertEqual(enabled['version'], 4)
        events = self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "' AND record_id='" + created['id'] + "' AND resource='tax-" + kind + "-classifications';")
        self.assertEqual(events, '4')
        self.req(route + '/' + created['id'], 'DELETE', expected=404)
        self.assertEqual(self.req(route, search=created['code'], pageSize=1)['total'], 1)

    def templates(self, kind):
        route = kind + '-classifications'
        expected = ITEM_TEMPLATES if kind == 'item' else PARTNER_TEMPLATES
        body = {'country_id': self.country_id, 'tax_type_id': self.vat['id']}
        first = self.req(route + '/templates/install', 'POST', body)
        self.assertEqual(first, {'installed': len(expected), 'skipped': 0})
        rows = self.req(route, pageSize=100)['items']
        self.assertEqual({r['code'] for r in rows}, expected)
        row = rows[0]
        customized = self.req(route + '/' + row['id'], 'PUT', {'values': {'name': 'Custom template'}, 'expectedVersion': row['version']})
        self.assertEqual(self.req(route + '/templates/install', 'POST', body), {'installed': 0, 'skipped': len(expected)})
        self.assertEqual(self.req(route + '/' + row['id']), customized)
        other = next((c for c in self.refs['countries'] if c['id'] != self.country_id), None)
        if other is None:
            status, other = self.root.request('/api/data/countries', 'POST', {'name': 'Germany proof', 'iso_code': 'DE'})
            self.assertEqual(status, 201, other)
        self.assertEqual(self.req(route + '/templates/install', 'POST', {**body, 'country_id': other['id']})['installed'], len(expected))
        self.assertEqual(self.req(route)['total'], 2 * len(expected))

    def temporal(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        route = self.profiles(kind, subject)
        empty = self.req(route)
        self.assertEqual(empty, {'items': [], 'total': 0, 'page': 1, 'pageSize': 25, 'version': 0})
        missing = self.resolve(kind, subject, expected=404)
        self.assertEqual(missing['code'], 'tax_profile_not_found', 'No implicit UNKNOWN/latest fallback')
        first = self.write_profile(kind, subject, classification)
        self.assertEqual((first['version'], first['total']), (1, 1))
        self.assertEqual(self.subject_read(kind, subject)['version'], subject['version'])
        self.write_profile(kind, subject, classification, version=1, expected=409)
        self.assertEqual(self.req(route), first)
        self.write_profile(kind, subject, classification, version=0, schedule=True, valid_from='2027-01-01', expected=409)
        future = self.write_profile(kind, subject, classification, version=1, schedule=True, valid_from='2027-01-01')
        self.assertEqual((future['version'], future['total']), (2, 2))
        self.assertEqual([p['valid_to'] for p in future['items']], ['2026-12-31', None])
        for date, start in (('2026-01-01', '2026-01-01'), ('2026-12-31', '2026-01-01'), ('2027-01-01', '2027-01-01')):
            self.assertEqual(self.resolve(kind, subject, date)['valid_from'], start)
        self.resolve(kind, subject, '2025-12-31', 404)
        self.resolve(kind, subject, '2026-02-30', 400)
        self.resolve(kind, subject, '2026-1-01', 400)
        disabled = self.req(kind + '-classifications/' + classification['id'] + '/deactivate', 'POST', {'expectedVersion': 1})
        self.assertFalse(disabled['is_active'])
        self.assertEqual(self.resolve(kind, subject)['classification_is_active'], False)
        self.write_profile(kind, subject, classification, version=2, schedule=True, valid_from='2028-01-01', expected=409)
        self.assertEqual(self.req(route), future | {'items': [p | {'classification_is_active': False} for p in future['items']]})
        page = self.req(route, pageSize=1, page=2)
        self.assertEqual((page['version'], page['total'], len(page['items'])), (2, 2, 1))
        self.assertEqual(self.subject_read(kind, subject), subject)

    def initial_atomicity(self, kind):
        classification = self.classification(kind)
        profile = self.profile(kind, classification)
        subject = self.subject(kind, taxProfiles=[profile | {'valid_to': '2026-12-31'}, profile | {'valid_from': '2027-01-01'}])
        history = self.req(self.profiles(kind, subject))
        self.assertEqual((history['version'], history['total']), (2, 2))
        before = self.sql('SELECT count(*) FROM masterdata.' + ('catalog_item' if kind == 'item' else 'business_partner') + " WHERE tenant_id='" + self.tenant_id + "';")
        self.subject(kind, expected=409, taxProfiles=[profile, profile | {'valid_from': '2027-01-01'}])
        self.subject(kind, expected=400, taxProfiles=[profile | {'valid_from': '2026-02-30'}])
        self.subject(kind, expected=404, taxProfiles=[profile | {kind + '_tax_classification_id': str(uuid.uuid4())}])
        after = self.sql('SELECT count(*) FROM masterdata.' + ('catalog_item' if kind == 'item' else 'business_partner') + " WHERE tenant_id='" + self.tenant_id + "';")
        self.assertEqual(after, before, 'Failed initial profiles must roll back the entire aggregate')

    def independent_versions(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        self.write_profile(kind, subject, classification, schedule=True)
        # Scheduling empty history is legal and starts the independent stream at 1.
        self.assertEqual(self.req(self.profiles(kind, subject))['version'], 1)
        general = self.subject_update(kind, subject, 'General draft after fiscal update')
        self.assertEqual(general['version'], subject['version'] + 1)
        self.assertEqual(self.req(self.profiles(kind, subject))['version'], 1)
        self.write_profile(kind, subject, classification, version=1, schedule=True, valid_from='2027-01-01')
        self.assertEqual(self.subject_read(kind, subject), general)
        self.write_profile(kind, subject, classification, version=1, schedule=True, valid_from='2028-01-01', expected=409)

    def concurrent(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        self.write_profile(kind, subject, classification)
        def schedule(date):
            return self.root.request(self.path(self.profiles(kind, subject) + '/schedule'), 'POST',
                                     {'values': self.profile(kind, classification, valid_from=date), 'expectedVersion': 1})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(schedule, ('2027-01-01', '2028-01-01')))
        self.assertEqual(sorted(status for status, _ in responses), [200, 409], responses)
        page = self.req(self.profiles(kind, subject))
        self.assertEqual((page['version'], page['total']), (2, 2))
        self.assertEqual(self.subject_read(kind, subject), subject)

    def security(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        route = kind + '-classifications'
        base_read = 'catalog-items.read' if kind == 'item' else 'business-partners.read'
        prefix = 'tax-' + kind
        actor, role, _ = self.actor([prefix + '-profiles.read', base_read])
        self.req(self.profiles(kind, subject), client=actor)
        self.req('classification-lookups', client=actor, kind=kind)
        self.req(route, client=actor, expected=403)
        self.req(route, 'POST', {'values': self.values()}, 403, client=actor)
        self.req(self.profiles(kind, subject), 'POST', {'values': self.profile(kind, classification), 'expectedVersion': 0}, 403, client=actor)
        status, other = self.root.request('/api/data/tenants', 'POST', {'code': 'other-' + uuid.uuid4().hex[:10], 'name': 'Other isolated tenant'})
        self.assertEqual(status, 201, other)
        self.req(route + '/' + classification['id'], tenant=other['id'], expected=404)
        self.req(self.profiles(kind, subject), tenant=other['id'], expected=404)
        self.req(self.profiles(kind, subject), tenant=other['id'], client=actor, expected=403)
        self.assertEqual(self.root.request('/api/links/role-permissions/' + role['id'] + '?tenantId=' + self.tenant_id, 'PUT', {'ids': []})[0], 204)
        self.req(self.profiles(kind, subject), client=actor, expected=403)
        self.req(route, client=Client(), expected=401)
        self.assertIn(self.root.request(self.path(route), 'POST', {'values': self.values()}, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(self.path(route), 'POST', {'values': self.values()}, origin='https://foreign.invalid')[0], 403)
        # The classifier reader must not inherit profile or other-kind authority.
        reader, _, _ = self.actor([prefix + '-classifications.read'])
        self.req(route, client=reader)
        self.req('classification-lookups', client=reader, kind=kind)
        self.req(self.profiles(kind, subject), client=reader, expected=403)
        self.req(('partner' if kind == 'item' else 'item') + '-classifications', client=reader, expected=403)
        self.req(route + '/' + classification['id'] + '/deactivate', 'POST', {'expectedVersion': 1}, 403, client=reader)

    def audit_rollback(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        self.write_profile(kind, subject, classification)
        before = self.req(self.profiles(kind, subject))
        prefix = 'tax-' + kind + '-profiles'
        audit_count = lambda: self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';")
        count = audit_count()
        self.sql("CREATE FUNCTION taxmanagement.classification_proof_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.tenant_id='" + self.tenant_id + "'::uuid THEN RAISE EXCEPTION 'synthetic classification audit rejection'; END IF; RETURN NEW; END $$; CREATE CONSTRAINT TRIGGER classification_proof_reject AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.classification_proof_reject();")
        try:
            self.write_profile(kind, subject, classification, version=1, schedule=True, valid_from='2027-01-01', expected=500)
            self.assertEqual(self.req(self.profiles(kind, subject)), before)
            self.classification_failure(kind)
            self.subject(kind, expected=500, taxProfiles=[self.profile(kind, classification)])
            self.assertEqual(audit_count(), count)
            self.assertEqual(self.subject_read(kind, subject), subject)
        finally:
            self.sql('DROP TRIGGER classification_proof_reject ON foundation.audit_event; DROP FUNCTION taxmanagement.classification_proof_reject();')
        self.write_profile(kind, subject, classification, version=1, schedule=True, valid_from='2027-01-01')
        events = self.sql("SELECT json_agg(json_build_object('action',action,'details',details)) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "' AND resource='" + prefix + "';")
        # Public/profile audit ownership is verified by persisted aggregate events.
        self.assertTrue(events)

    def validation(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        route = kind + '-classifications'
        for values in ({'code': 'X' * 51}, {'name': 'X' * 151}, {'code': ' BAD_CODE'},
                       {'country_id': str(uuid.uuid4())}, {'tax_type_id': str(uuid.uuid4())}):
            self.req(route, 'POST', {'values': self.values(**values)}, 400)
        inactive = next(t for t in self.refs['types'] if not t['is_active'])
        self.req(route, 'POST', {'values': self.values(tax_type_id=inactive['id'])}, 400)
        for changes in ({'valid_from': '2026-02-30'}, {'valid_from': '2026-1-01'},
                        {'valid_to': '2025-12-31'}, {'country_id': str(uuid.uuid4())}):
            self.write_profile(kind, subject, classification, expected=400, **changes)
        self.assertEqual(self.req(self.profiles(kind, subject))['total'], 0)
        self.write_profile(kind, subject, classification, valid_to='2026-01-31')
        # Legal gaps stay explicit; no latest-profile fallback.
        self.write_profile(kind, subject, classification, version=1, valid_from='2026-03-01', valid_to='2026-03-31')
        self.resolve(kind, subject, '2026-02-01', 404)
        self.resolve(kind, subject, '2026-04-01', 404)
        self.assertEqual(self.resolve(kind, subject, '2026-03-31')['valid_to'], '2026-03-31')
        for params in ({'page': 0}, {'pageSize': 101}, {'country_id': 'not-a-guid'}):
            self.req(self.profiles(kind, subject), expected=400, **params)
        self.assertEqual(self.req(route)['total'], 1)

    def granular_permissions(self, kind):
        classification = self.classification(kind)
        subject = self.subject(kind)
        base = 'catalog-items' if kind == 'item' else 'business-partners'
        fiscal = 'tax-' + kind + '-profiles'
        # Ordinary base creation is allowed without profile assignment grants.
        creator, _, _ = self.actor([base + '.read', base + '.create'] + (['catalog-items.activate'] if kind == 'item' else []))
        plain = self.subject(kind, client=creator)
        self.assertTrue(plain['id'])
        self.subject(kind, client=creator, expected=403, taxProfiles=[self.profile(kind, classification)])
        no_base, _, _ = self.actor([fiscal + '.read'])
        self.req(self.profiles(kind, subject), client=no_base, expected=403)
        scheduler, _, _ = self.actor([base + '.read', fiscal + '.read', fiscal + '.schedule'])
        self.req(self.profiles(kind, subject) + '/schedule', 'POST',
                 {'values': self.profile(kind, classification), 'expectedVersion': 0}, 200, client=scheduler)
        self.req(self.profiles(kind, subject), 'POST',
                 {'values': self.profile(kind, classification, valid_from='2027-01-01'), 'expectedVersion': 1}, 403, client=scheduler)
        assigner, _, _ = self.actor([base + '.read', fiscal + '.read', fiscal + '.assign'])
        self.req(self.profiles(kind, subject) + '/schedule', 'POST',
                 {'values': self.profile(kind, classification, valid_from='2027-01-01'), 'expectedVersion': 1}, 403, client=assigner)
        self.assertEqual(self.req(self.profiles(kind, subject))['version'], 1)
        route = kind + '-classifications'
        reader, _, _ = self.actor(['tax-' + kind + '-classifications.read'])
        for suffix, body in (('/templates/install', {'country_id': self.country_id, 'tax_type_id': self.vat['id']}),
                             ('/' + classification['id'] + '/reactivate', {'expectedVersion': 1})):
            self.req(route + suffix, 'POST', body, 403, client=reader)

    def classification_failure(self, kind):
        before = self.req(kind + '-classifications')['total']
        self.req(kind + '-classifications', 'POST', {'values': self.values()}, 500)
        self.assertEqual(self.req(kind + '-classifications')['total'], before)


# Each resource gets an independent bounded unittest result (no hidden nested suites).
for _kind in KINDS:
    for _scenario in ('lifecycle', 'templates', 'temporal', 'initial_atomicity', 'independent_versions', 'concurrent', 'security', 'audit_rollback', 'validation', 'granular_permissions'):
        def _test(self, kind=_kind, scenario=_scenario):
            getattr(self, scenario)(kind)
        setattr(TaxClassificationHttp, 'test_' + _kind + '_' + _scenario, _test)
