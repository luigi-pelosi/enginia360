"""Focused real HTTP ownership proof; synthetic labelled fixture only."""
import unittest
from test_company_tax_http import CompanyTaxHttp as Harness

ADDRESS = {'address': 'Via synthetic 17', 'city': 'Roma', 'province': 'RM', 'postal_code': '00100', 'country_code': 'IT'}


class CompanyIdentityHttp(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    setUp = Harness.setUp
    scope = Harness.scope
    req = Harness.req
    path = Harness.path
    sql = Harness.sql
    company_create = Harness.company_create
    company_read = Harness.company_read
    list_route = Harness.list_route
    route = Harness.route
    payload = Harness.payload
    create = Harness.create
    read = Harness.read
    registration = Harness.registration
    profile = Harness.profile
    identifier = Harness.identifier

    def save(self, resource, values, record=None, wrapped=True, expected=200):
        route = '/api/data/' + resource + ('/' + record if record else '') + ('/save' if wrapped else '')
        status, body = self.root.request(self.scope(route), 'PUT' if record else 'POST', {'values': values} if wrapped else values)
        if isinstance(expected, tuple):
            self.assertIn(status, expected, body)
        else:
            self.assertEqual(status, expected, body)
        return body

    def test_company_general_cf_rejected_on_both_routes_without_changes(self):
        self.assertNotIn('tax_code', self.company_read())
        for wrapped in (False, True):
            row = self.save('companies', {'name': 'Identity synthetic'}, wrapped=wrapped, expected=201)
            before = self.company_read(row)
            count = self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';")
            for value in ('  CF é漢😀  ', None, '', 'x' * 501, 123, [], {}):
                with self.subTest(wrapped=wrapped, value=value):
                    self.save('companies', {'tax_code': value, 'name': 'Must not persist'}, row['id'], wrapped, (400, 403))
                    self.save('companies', {'tax_code': value, 'name': 'Must not persist'}, wrapped=wrapped, expected=(400, 403))
                    self.assertEqual(self.company_read(row), before)
                    self.assertEqual(self.sql("SELECT count(*) FROM foundation.company WHERE tenant_id='" + self.tenant_id + "';"), count)
            self.save('companies', {'name': 'No CF supplied'}, wrapped=wrapped, expected=201)

    def test_metadata_company_cf_only_and_site_no_fiscal_fields(self):
        status, resources = self.root.request('/api/resources')
        self.assertEqual(status, 200)
        resources = {r['key']: {f['name']: f for f in r['fields']} for r in resources}
        self.assertNotIn('tax_code', resources['companies'])
        self.assertNotIn('vat_number', resources['companies'])
        for field in ('tax_code', 'vat_number'):
            self.assertNotIn(field, resources['sites'])
        for field in ADDRESS:
            self.assertTrue(resources['sites'][field]['required'])

    def test_site_no_fiscal_gate_address_invariants_and_legacy_payload_rejection(self):
        for wrapped in (False, True):
            values = {'company_id': self.company['id'], 'name': 'Synthetic site', **ADDRESS}
            row = self.save('sites', values, wrapped=wrapped, expected=201)
            self.assertNotIn('tax_code', row)
            self.assertNotIn('vat_number', row)
            row = self.save('sites', {'address': 'Via changed 23'}, row['id'], wrapped)
            self.assertEqual(row['address'], 'Via changed 23')
            self.assertEqual({k: row[k] for k in ADDRESS if k != 'address'}, {k: v for k, v in ADDRESS.items() if k != 'address'})
            for field in ADDRESS:
                self.save('sites', {field: '  '}, row['id'], wrapped, expected=400)
            for field in ('vat_number', 'tax_code'):
                for value in ('legacy', None):
                    self.save('sites', {**values, field: value}, wrapped=wrapped, expected=tuple(range(400, 500)))
                    self.save('sites', {field: value, 'address': 'Must not persist'}, row['id'], wrapped, tuple(range(400, 500)))
            status, page = self.root.request(self.scope('/api/data/sites?pageSize=100'))
            self.assertEqual(status, 200)
            persisted = next(item for item in page['items'] if item['id'] == row['id'])
            self.assertEqual(persisted['address'], 'Via changed 23')

    def test_company_tax_configuration_lookup_create_read_is_independent_of_cf(self):
        self.assertNotIn('tax_code', self.company_read())
        self.assertTrue(self.refs['types'])
        root = self.create(tax_code='Independent fiscal CF')
        self.assertEqual(root['status'], 'DRAFT')
        self.assertEqual(self.read(root)['id'], root['id'])
        self.assertEqual([item['id'] for item in self.req(self.list_route())['items']], [root['id']])
        self.save('companies', {'name': 'Independent general name'}, self.company['id'])
        self.assertEqual(self.read(root)['version'], root['version'])
        self.assertEqual(self.read(root)['tax_code'], 'Independent fiscal CF')
        self.assertNotIn('tax_code', self.company_read())
