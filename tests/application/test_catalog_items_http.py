"""Finite phase-2 HTTP/SQL acceptance. No skips, mocks, live DB or fallback routes."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, ROUND_HALF_UP
import json
import unittest
from urllib.parse import urlencode
import uuid
from catalog_items_helpers import Client, fixture, fixture_sql, login_root, require_fixture


def gtin(payload):
    """GS1 modulo-10 check digit; payload length 7/11/12/13."""
    if len(payload) not in (7, 11, 12, 13) or not payload.isdigit():
        raise ValueError('Invalid GTIN payload')
    total = sum(int(value) * (3 if index % 2 == 0 else 1) for index, value in enumerate(reversed(payload)))
    return payload + str((-total) % 10)


class CatalogItemsHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_fixture()
        cls.root, cls.credentials = login_root()

    def setUp(self):
        self.code = 'items-' + uuid.uuid4().hex[:12]
        self.tenant = self.data_create('tenants', {'code': self.code, 'name': 'Synthetic ITEMS proof'}, tenant=False)
        self.tenant_id = self.tenant['id']
        self.refs = {kind: self.listed(kind) for kind in ('units', 'types')}
        self.good = next(row for row in self.refs['types'] if row['kind'] == 'GOOD')
        self.service = next(row for row in self.refs['types'] if row['kind'] == 'SERVICE')
        self.base = next(row for row in self.refs['units'] if row['dimension'] == 'COUNT' and row['is_base'])
        self.category = self.create('categories', {'name': 'Synthetic category', 'is_active': True})

    def data_create(self, resource, values, tenant=True):
        path = '/api/data/' + resource + ('?tenantId=' + self.tenant_id if tenant else '')
        status, body = self.root.request(path, 'POST', values)
        self.assertEqual(status, 201, (path, status, body))
        return body

    def path(self, resource, ident=None, tenant=None, **query):
        return '/api/catalog/' + resource + ('/' + ident if ident else '') + '?' + urlencode({'tenantId': tenant or self.tenant_id, **query})

    def req(self, resource, ident=None, method='GET', body=None, expected=200, tenant=None, **query):
        status, result = self.root.request(self.path(resource, ident, tenant, **query), method, body)
        if isinstance(expected, (tuple, list)):
            self.assertIn(status, expected, (resource, ident, method, status, result))
        else:
            self.assertEqual(status, expected, (resource, ident, method, status, result))
        return result

    def listed(self, resource, **query):
        return self.req(resource, page=1, pageSize=100, **query)['items']

    def create(self, resource, values, **kw):
        return self.req(resource, method='POST', body={'values': values}, expected=201, **kw)

    def update(self, resource, row, values, expected=200):
        return self.req(resource, row['id'], 'PUT', {'values': values, 'expectedVersion': row['version']}, expected)

    def values(self, **changes):
        return {'name': 'Synthetic item ' + uuid.uuid4().hex[:8], 'item_type_id': self.good['id'],
                'category_id': self.category['id'], 'base_uom_id': self.base['id'], **changes}

    def item(self, **changes):
        row = self.create('items', self.values(**changes))
        self.full(row)
        return row

    def full(self, row):
        for key in ('id', 'code', 'name', 'kind', 'status', 'activated_at', 'version', 'identifiers', 'units', 'physicalData'):
            self.assertIn(key, row)
        self.assertIsInstance(row['identifiers'], list)
        self.assertIsInstance(row['units'], list)
        self.assertIsInstance(row['version'], int)
        self.assertEqual(self.req('items', row['id']), row, 'Full root must equal authoritative readback')
        return row

    def child(self, row, resource, values=None, ident=None, method=None, expected=None):
        method = method or ('PUT' if ident else 'POST')
        expected = expected if expected is not None else 200
        suffix = row['id'] + '/' + resource + ('/' + ident if ident else '')
        if method == 'DELETE':
            result = self.req('items', suffix, 'DELETE', expected=expected, expectedVersion=row['version'])
        else:
            result = self.req('items', suffix, method, {'values': values, 'expectedVersion': row['version']}, expected)
        if expected < 300:
            self.full(result)
            self.assertEqual(result['id'], row['id'])
            self.assertEqual(result['version'], row['version'] + 1)
        return result

    def status(self, row, status, expected=200):
        result = self.req('items', row['id'] + '/status', 'PUT', {'status': status, 'expectedVersion': row['version']}, expected)
        if expected == 200:
            self.full(result)
            self.assertEqual(result['version'], row['version'] + 1)
        return result

    def test_item_type_filter_pagination_and_isolation(self):
        other_type = self.create('types', {'name': 'Second good type', 'kind': 'GOOD', 'is_active': True})
        a = self.item(name='Filter A')
        b = self.item(name='Filter B')
        self.item(name='Filter C', item_type_id=other_type['id'])
        page = self.req('items', itemTypeId=self.good['id'], page=1, pageSize=1, status='ACTIVE')
        self.assertEqual(page['total'], 2)
        self.assertEqual([r['id'] for r in page['items']], [a['id']])
        page = self.req('items', itemTypeId=self.good['id'], page=2, pageSize=1, status='ACTIVE')
        self.assertEqual(page['total'], 2)
        self.assertEqual([r['id'] for r in page['items']], [b['id']])
        self.assertEqual(self.req('items', itemTypeId=other_type['id'], kind='SERVICE')['total'], 0)
        self.assertEqual(self.req('items', itemTypeId=str(uuid.uuid4()))['total'], 0)
        foreign = self.data_create('tenants', {'code': 'foreign-' + uuid.uuid4().hex[:8], 'name': 'Foreign'}, tenant=False)
        foreign_types = self.req('types', tenant=foreign['id'], page=1, pageSize=100)['items']
        self.assertEqual(self.req('items', itemTypeId=foreign_types[0]['id'])['total'], 0)
        b = self.status(b, 'SUSPENDED')
        self.assertEqual(self.req('items', itemTypeId=self.good['id'], status='SUSPENDED')['total'], 1)
        b = self.status(b, 'ARCHIVED')
        self.assertEqual(self.req('items', itemTypeId=self.good['id'], status='ARCHIVED')['total'], 1)
        self.assertEqual(self.req('items', itemTypeId=self.good['id'], status='ACTIVE', search='Filter A')['total'], 1)
        self.assertEqual(self.req('items', itemTypeId='', kind='GOOD')['total'], 3)
        self.req('items', itemTypeId='not-a-uuid', expected=400)
        self.req('items', itemTypeId=str(uuid.UUID(int=0)), expected=400)
        actor, _, _ = self.actor([])
        self.assertEqual(actor.request(self.path('items', itemTypeId=self.good['id']))[0], 403)
        reader, _, _ = self.actor(['catalog-items.read'])
        status, filtered = reader.request(self.path('items', itemTypeId=self.good['id'], status='ACTIVE'))
        self.assertEqual(status, 200)
        self.assertEqual(filtered['total'], 1)

    def manual(self, kind='GOOD'):
        config = self.req('numbering', kind=kind)
        return self.req('numbering', method='PUT', kind=kind, body={**config, 'mode': 'MANUAL'})

    def pack(self, code=None):
        return self.create('units', {'code': code or 'CF' + uuid.uuid4().hex[:6], 'name': 'Confezione',
            'dimension': 'COUNT', 'conversion_scope': 'ITEM', 'factor_to_base': None,
            'is_base': False, 'decimal_places': 0, 'is_active': True})

    def ratio(self, unit, numerator='12', denominator='1'):
        return {'uom_id': unit['id'], 'conversion_numerator': numerator, 'conversion_denominator': denominator, 'is_active': True}

    def identifier(self, value='OEM-1', kind='OEM', **changes):
        return {'identifier_type': kind, 'value': value, 'is_primary': False, 'uom_id': None, **changes}

    def actor(self, grants):
        username = 'items-actor-' + uuid.uuid4().hex[:10]
        user = self.data_create('users', {'username': username, 'first_name': 'Synthetic', 'last_name': 'Items', 'email': username + '@example.invalid'})
        role = self.data_create('roles', {'name': 'Synthetic ITEMS role'})
        rows, page = [], 1
        while True:
            status, data = self.root.request('/api/data/permissions?' + urlencode({'tenantId': self.tenant_id, 'page': page, 'pageSize': 100}))
            self.assertEqual(status, 200, data)
            rows.extend(data['items'])
            if len(rows) == data['total']:
                break
            self.assertLess(len(rows), data['total'])
            self.assertTrue(data['items'])
            page += 1
        self.permission_ids = {row['code']: row['id'] for row in rows}
        ids = [row['id'] for row in rows if row['code'] in grants]
        self.assertEqual(len(ids), len(grants), (grants, ids))
        for relation, owner, targets in (('user-roles', user['id'], [role['id']]), ('role-permissions', role['id'], ids)):
            self.assertEqual(self.root.request('/api/links/' + relation + '/' + owner + '?tenantId=' + self.tenant_id, 'PUT', {'ids': targets})[0], 204)
        password = uuid.uuid4().hex + '-Initial!'
        self.assertEqual(self.root.request('/api/users/' + user['id'] + '/password?tenantId=' + self.tenant_id, 'PUT', {'newPassword': password})[0], 204)
        actor = Client()
        status, session = actor.login({'username': username, 'password': password}, self.code)
        self.assertEqual(status, 200, session)
        changed = uuid.uuid4().hex + '-Changed!'
        self.assertEqual(actor.request('/api/auth/password', 'PUT', {'currentPassword': password, 'newPassword': changed})[0], 204)
        actor.token = None
        return actor, role, {'username': username, 'password': changed}

    def revoke(self, role):
        path = '/api/links/role-permissions/' + role['id'] + '?tenantId=' + self.tenant_id
        self.assertEqual(self.root.request(path, 'PUT', {'ids': []})[0], 204)
        self.assertEqual(self.root.request(path)[1]['ids'], [])

    def denied_unchanged(self, row, values):
        self.update('items', row, values, (400, 409))
        self.assertEqual(self.req('items', row['id']), row)

    def test_inline_status_create_and_update_atomic(self):
        created = self.req('items', method='POST', body={'values': self.values(), 'status': 'ACTIVE'}, expected=201)
        self.assertEqual(created['status'], 'ACTIVE')
        self.assertIsNotNone(created['activated_at'])
        self.full(created)
        updated = self.req('items', created['id'], 'PUT', {'values': {'name': 'Inline inactive'}, 'status': 'INACTIVE', 'expectedVersion': created['version']})
        self.assertEqual(updated['status'], 'INACTIVE')
        self.assertEqual(updated['version'], created['version'] + 1)
        self.full(updated)

    def test_inline_status_guards_and_rollback(self):
        creator, _, _ = self.actor(['catalog-items.create'])
        updater, _, _ = self.actor(['catalog-items.update'])
        before_number = self.req('numbering', kind='GOOD')
        self.assertEqual(creator.request(self.path('items'), 'POST', {'values': self.values(), 'status': 'ACTIVE'})[0], 403)
        self.assertEqual(self.req('numbering', kind='GOOD'), before_number)
        row = self.item()
        payload = {'values': {'name': 'Must roll back'}, 'status': 'ACTIVE', 'expectedVersion': row['version']}
        self.assertEqual(updater.request(self.path('items', row['id']), 'PUT', payload)[0], 403)
        self.assertEqual(self.req('items', row['id']), row)
        self.req('items', row['id'], 'PUT', payload | {'values': {'category_id': None}}, 400)
        self.assertEqual(self.req('items', row['id']), row)
        self.req('items', row['id'], 'PUT', payload | {'status': 'INACTIVE'}, 409)
        self.assertEqual(self.req('items', row['id']), row)
        self.req('items', row['id'], 'PUT', payload | {'expectedVersion': row['version'] + 1}, 409)
        self.assertEqual(self.req('items', row['id']), row)
        archived = self.req('items', row['id'], 'PUT', payload | {'status': 'ARCHIVED'})
        self.assertEqual(archived['status'], 'ARCHIVED')
        self.req('items', row['id'], 'PUT', {'values': {'name': 'No'}, 'status': 'ACTIVE', 'expectedVersion': archived['version']}, 409)
        self.assertEqual(self.req('items', row['id']), archived)

    def test_atomic_create_full_root_and_child_version_identity(self):
        pack = self.pack()
        payload = {'values': self.values(), 'units': [self.ratio(pack)],
                   'identifiers': [self.identifier('ATOMIC-OEM', uom_id=pack['id'])]}
        row = self.req('items', method='POST', body=payload, expected=201)
        self.full(row)
        self.assertEqual((row['status'], row['activated_at'], row['kind']), ('DRAFT', None, 'GOOD'))
        self.assertEqual((len(row['units']), len(row['identifiers'])), (1, 1))
        child_id = row['identifiers'][0]['id']
        changed = self.child(row, 'identifiers', self.identifier('CHANGED-OEM'), child_id)
        self.assertEqual(changed['identifiers'][0]['id'], child_id)
        self.assertEqual(changed['units'], row['units'])
        self.child(row, 'identifiers', self.identifier('STALE'), child_id, expected=409)
        self.assertEqual(self.req('items', row['id']), changed)
        latest = self.child(changed, 'identifiers', ident=child_id, method='DELETE', expected=200)
        self.assertEqual(latest['identifiers'], [])
        unit_id = latest['units'][0]['id']
        latest = self.child(latest, 'units', self.ratio(pack, '24'), unit_id)
        self.assertEqual(latest['units'][0]['id'], unit_id)
        latest = self.child(latest, 'units', ident=unit_id, method='DELETE', expected=200)
        self.assertEqual(latest['units'], [])
        count = self.req('items')['total']
        self.req('items', method='POST', body={'values': self.values(), 'identifiers': [self.identifier('BAD', 'GTIN')]}, expected=400)
        self.assertEqual(self.req('items')['total'], count)

    def test_numbering_manual_reservations_and_cross_kind_collision(self):
        self.manual('GOOD'); self.manual('SERVICE')
        row = self.item(code='RESERVED-A')
        row = self.update('items', row, {'code': 'RESERVED-B'})
        for code in ('RESERVED-A', 'reserved-a', 'reserved-b'):
            self.req('items', method='POST', body={'values': self.values(code=code, item_type_id=self.service['id'])}, expected=409)
        self.denied_unchanged(row, {'code': 'RESERVED-A'})
        archived = self.status(row, 'ARCHIVED')
        self.req('items', method='POST', body={'values': self.values(code=archived['code'])}, expected=409)
        self.assertEqual(fixture_sql(f"SELECT count(*) FROM masterdata.catalog_item_code WHERE tenant_id='{self.tenant_id}' AND item_id='{row['id']}';"), '2')

    def test_numbering_auto_concurrent_and_rollback_counter(self):
        for kind in ('GOOD', 'SERVICE'):
            config = self.req('numbering', kind=kind)
            self.req('numbering', method='PUT', kind=kind, body={**config, 'mode': 'AUTO', 'prefix': 'SAME-', 'padding': 4, 'nextNumber': 1})
        before = self.req('numbering', kind='GOOD')
        self.req('items', method='POST', body={'values': self.values(), 'identifiers': [self.identifier('bad', 'GTIN')]}, expected=400)
        self.assertEqual(self.req('numbering', kind='GOOD'), before)
        # Each worker uses its own real authenticated cookie jar.
        def create_one(index):
            client = Client()
            self.assertEqual(client.login(self.credentials)[0], 200)
            return client.request(self.path('items'), 'POST', {'values': self.values(name='Concurrent ' + str(index))})
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(create_one, range(8)))
        self.assertEqual([status for status, _ in results], [201] * 8, results)
        self.assertEqual(len({row['code'].casefold() for _, row in results}), 8)
        self.assertEqual(self.req('numbering', kind='GOOD')['nextNumber'], before['nextNumber'] + 8)
        # Cross-nature sequence collision must never create a duplicate code.
        service_before = self.req('numbering', kind='SERVICE')
        status, body = self.root.request(self.path('items'), 'POST', {'values': self.values(item_type_id=self.service['id'])})
        self.assertIn(status, (201, 409), body)
        if status == 201:
            self.assertNotIn(body['code'].casefold(), {row['code'].casefold() for _, row in results})
        else:
            self.assertEqual(self.req('numbering', kind='SERVICE'), service_before)
        row = results[0][1]
        status, _ = self.root.request(self.path('items', row['id']), 'PUT', {'values': {'code': 'CALLER-CODE'}, 'expectedVersion': row['version']})
        self.assertIn(status, (400, 409))
        self.assertEqual(self.req('items', row['id']), row)

    def test_lifecycle_activation_nature_base_and_terminal_archive(self):
        row = self.create('items', {'name': 'Minimal DRAFT', 'item_type_id': self.good['id']})
        self.assertEqual(row['status'], 'DRAFT')
        self.status(row, 'ACTIVE', 400)
        row = self.update('items', row, {'category_id': self.category['id'], 'base_uom_id': self.base['id']})
        self.denied_unchanged(row, {'item_type_id': self.service['id']})
        same_kind = self.create('types', {'name': 'Replacement GOOD', 'kind': 'GOOD', 'default_track_stock': False, 'is_active': True})
        row = self.update('items', row, {'item_type_id': same_kind['id']})
        self.assertEqual((row['item_type_id'], row['kind']), (same_kind['id'], 'GOOD'))
        row = self.status(row, 'ACTIVE')
        activated = row['activated_at']
        self.assertIsNotNone(activated)
        row = self.status(row, 'INACTIVE')
        self.denied_unchanged(row, {'code': 'POST-FIRST-ACTIVATION'})
        other_base = next(unit for unit in self.refs['units'] if unit['dimension'] == 'MASS' and unit['is_base'])
        self.denied_unchanged(row, {'base_uom_id': other_base['id']})
        self.status(row, 'DRAFT', 400)
        row = self.status(row, 'ACTIVE')
        self.assertEqual(row['activated_at'], activated)
        row = self.status(row, 'ARCHIVED')
        for target in ('DRAFT', 'ACTIVE', 'INACTIVE'):
            self.status(row, target, 400 if target == 'DRAFT' else 409)
        self.denied_unchanged(row, {'name': 'No archive writes'})
        self.child(row, 'identifiers', self.identifier(), expected=409)
        self.child(row, 'physical-data', None, method='PUT', expected=409)
        self.req('items', row['id'], 'DELETE', expected=404, expectedVersion=row['version'])
        status, created = self.root.request(self.path('items'), 'POST', {'values': self.values(status='ACTIVE')})
        self.assertIn(status, (201, 400), created)
        if status == 201:
            self.assertEqual((created['status'], created['activated_at']), ('DRAFT', None), 'Create must never bypass activation')

    def test_inactive_reference_grace_activation_revalidation(self):
        brand = self.create('brands', {'name': 'Synthetic brand', 'is_active': True})
        row = self.item(brand_id=brand['id'])
        self.update('brands', brand, {'is_active': False})
        row = self.update('items', row, {'name': 'Keep existing inactive brand'})
        self.assertEqual(row['brand_id'], brand['id'])
        self.req('items', method='POST', body={'values': self.values(brand_id=brand['id'])}, expected=400)
        self.status(row, 'ACTIVE', 400)
        row = self.update('items', row, {'brand_id': None})
        category = self.update('categories', self.category, {'is_active': False})
        row = self.update('items', row, {'description': 'Inactive category remains attached'})
        self.assertEqual(row['category_id'], category['id'])
        self.status(row, 'ACTIVE', 400)
        self.update('categories', category, {'is_active': True})
        self.status(row, 'ACTIVE')

    def test_identifiers_checksum_canonical_uniqueness_primary_search(self):
        row, other = self.item(), self.item()
        for length in (8, 12, 13, 14):
            value = gtin(('1234567890123')[:length - 1])
            changed = self.child(row, 'identifiers', self.identifier(value, 'GTIN'))
            inserted = next(entry for entry in changed['identifiers'] if entry['value'] == value)
            self.assertEqual(inserted['normalized_value'], value.zfill(14))
            self.child(other, 'identifiers', self.identifier(value.zfill(14), 'GTIN'), expected=409)
            invalid = value[:-1] + str((int(value[-1]) + 1) % 10)
            self.child(changed, 'identifiers', self.identifier(invalid, 'GTIN'), expected=400)
            row = changed
        for kind in ('OEM', 'MPN', 'LEGACY'):
            row = self.child(row, 'identifiers', self.identifier('Shared-A-1', kind))
            other = self.child(other, 'identifiers', self.identifier('Shared-A-1', kind))
        row = self.child(row, 'identifiers', self.identifier('UNIQUE-BAR', 'BARCODE'))
        self.child(other, 'identifiers', self.identifier('UNIQUE-BAR', 'BARCODE'), expected=409)
        self.child(row, 'identifiers', self.identifier('Shared-A-1', 'OEM'), expected=409)
        row = self.child(row, 'identifiers', self.identifier('Primary-A', is_primary=True))
        self.child(row, 'identifiers', self.identifier('Primary-B', is_primary=True), expected=409)
        # Multiple matching identifiers on one root cannot multiply total/page rows.
        row = self.child(row, 'identifiers', self.identifier('SearchNeedle-one'))
        row = self.child(row, 'identifiers', self.identifier('SearchNeedle-two', 'MPN'))
        other = self.child(other, 'identifiers', self.identifier('SearchNeedle-other'))
        pages = [self.req('items', search='SearchNeedle', page=page, pageSize=1) for page in (1, 2)]
        self.assertEqual([page['total'] for page in pages], [2, 2])
        self.assertEqual({entry['id'] for page in pages for entry in page['items']}, {row['id'], other['id']})

    def test_tenant_child_and_reference_isolation(self):
        foreign = self.data_create('tenants', {'code': 'foreign-' + uuid.uuid4().hex[:10], 'name': 'Foreign synthetic'}, tenant=False)['id']
        row = self.item()
        for resource, reference in (('item_type_id', self.good), ('category_id', self.category), ('base_uom_id', self.base)):
            values = {'name': 'Cross tenant', 'item_type_id': self.good['id'], resource: reference['id']}
            self.req('items', method='POST', body={'values': values}, expected=400, tenant=foreign)
        self.req('items', row['id'], tenant=foreign, expected=404)
        row = self.child(row, 'identifiers', self.identifier())
        other = self.item()
        self.child(other, 'identifiers', self.identifier('Wrong parent'), row['identifiers'][0]['id'], expected=404)
        pack = self.pack()
        other = self.child(other, 'units', self.ratio(pack))
        self.child(row, 'identifiers', self.identifier('Wrong unit', uom_id=pack['id']), expected=400)
        self.child(other, 'units', ident=other['units'][0]['id'], method='DELETE')
        other = self.req('items', other['id'])
        other = self.child(other, 'units', self.ratio(pack))
        other = self.child(other, 'identifiers', self.identifier('Unit-linked', uom_id=pack['id']))
        self.child(other, 'units', ident=other['units'][0]['id'], method='DELETE', expected=400)
        self.child(other, 'units', self.ratio(pack) | {'is_active': False}, other['units'][0]['id'], expected=400)
        self.denied_unchanged(other, {'base_uom_id': self.refs['units'][1]['id']})

    def test_item_units_exact_contextual_conversion_and_universal_consistency(self):
        pack = self.pack('CF')
        self.assertEqual((pack['conversion_scope'], pack['factor_to_base'], pack['is_base']), ('ITEM', None, False))
        self.req('units', pack['id'] + '/convert', 'POST', {'targetUnitId': self.base['id'], 'quantity': '1'}, 400)
        self.req('items', method='POST', body={'values': self.values(base_uom_id=pack['id'])}, expected=400)
        for field, value in (('conversion_scope', 'UNIVERSAL'), ('factor_to_base', '1'), ('is_base', True)):
            self.update('units', pack, {field: value}, 400)
        rows = [self.child(self.item(), 'units', self.ratio(pack, str(n))) for n in (12, 24)]
        for row, expected in zip(rows, ('12', '24')):
            converted = self.req('items', row['id'] + '/convert', 'POST', {'sourceUnitId': pack['id'], 'targetUnitId': self.base['id'], 'quantity': '1'})
            self.assertEqual(Decimal(converted['quantity']), Decimal(expected))
            self.assertFalse(converted['rounded'])
        for numerator, denominator in (('0', '1'), ('1', '0'), ('-1', '1'), ('1.0000000000001', '1')):
            self.child(self.item(), 'units', self.ratio(pack, numerator, denominator), expected=400)
        mass = next(unit for unit in self.refs['units'] if unit['dimension'] == 'MASS' and unit['is_base'])
        grams = next(unit for unit in self.refs['units'] if unit['dimension'] == 'MASS' and Decimal(unit['factor_to_base']) == Decimal('0.001'))
        row = self.item(base_uom_id=grams['id'])
        self.child(row, 'units', self.ratio(mass, '1'), expected=400)
        row = self.child(row, 'units', self.ratio(mass, '1000'))
        self.child(row, 'units', self.ratio(self.base), expected=400)
        # Products exceed Decimal intermediate capacity but cancel exactly using BigInteger rationals.
        huge = '9999999999999999.999999999999'
        tiny = self.pack('EXACT')
        exact = self.child(self.item(), 'units', self.ratio(tiny, huge, huge))
        result = self.req('items', exact['id'] + '/convert', 'POST', {'sourceUnitId': tiny['id'], 'targetUnitId': self.base['id'], 'quantity': '0.123456789012'})
        self.assertEqual(Decimal(result['unroundedQuantity']), Decimal('0.123456789012'))
        expected = Decimal('0.123456789012').quantize(Decimal(1).scaleb(-self.base['decimal_places']), rounding=ROUND_HALF_UP)
        self.assertEqual(Decimal(result['quantity']), expected)
        self.assertEqual(result['decimalPlaces'], self.base['decimal_places'])
        self.assertEqual(result['rounded'], expected != Decimal('0.123456789012'))

    def physical(self):
        mass = next(unit for unit in self.refs['units'] if unit['dimension'] == 'MASS' and unit['is_base'])
        length = next(unit for unit in self.refs['units'] if unit['dimension'] == 'LENGTH' and unit['is_base'])
        return {'net_weight': '1.25', 'gross_weight': '1.5', 'weight_uom_id': mass['id'],
                'length': '1', 'width': '2', 'height': '3', 'dimension_uom_id': length['id']}

    def test_physical_validation_good_only_and_versioned_removal(self):
        row = self.item()
        values = self.physical()
        item_mass = self.create('units', {'code': 'IMASS', 'name': 'Item-specific mass', 'dimension': 'MASS',
            'conversion_scope': 'ITEM', 'factor_to_base': None, 'is_base': False, 'decimal_places': 2, 'is_active': True})
        self.child(row, 'physical-data', values | {'weight_uom_id': item_mass['id']}, method='PUT', expected=400)
        for change in ({'net_weight': '-1'}, {'net_weight': '2'}, {'gross_weight': '0.0000000000001'},
                       {'weight_uom_id': self.base['id']}, {'dimension_uom_id': self.base['id']},
                       {'weight_uom_id': None}, {'dimension_uom_id': None}):
            self.child(row, 'physical-data', values | change, method='PUT', expected=400)
            self.assertEqual(self.req('items', row['id']), row)
        row = self.child(row, 'physical-data', values, method='PUT')
        self.assertEqual(Decimal(row['physicalData']['net_weight']), Decimal('1.25'))
        service = self.item(item_type_id=self.service['id'])
        self.child(service, 'physical-data', values, method='PUT', expected=400)
        row = self.child(row, 'physical-data', None, method='PUT')
        self.assertIsNone(row['physicalData'])
        self.req('items', method='POST', body={'values': self.values(item_type_id=self.service['id']), 'physicalData': values}, expected=400)

    def test_exact_crud_permissions_options_grants_revocation_and_bypass(self):
        actor, empty_role, _ = self.actor([])
        row, brand = self.item(), self.create('brands', {'name': 'Permission brand'})
        for resource in ('items', 'brands', 'item-options'):
            self.assertEqual(actor.request(self.path(resource))[0], 403)
            self.assertEqual(Client().request(self.path(resource))[0], 401)
        link = '/api/links/role-permissions/' + empty_role['id'] + '?tenantId=' + self.tenant_id
        granted = [self.permission_ids['catalog-items.read']]
        self.assertEqual(self.root.request(link, 'PUT', {'ids': granted})[0], 204)
        self.assertEqual(self.root.request(link)[1]['ids'], granted)
        self.assertEqual(actor.request(self.path('items'))[0], 200, 'New grant must apply to already-open session')
        self.revoke(empty_role)
        self.assertEqual(actor.request(self.path('items'))[0], 403)
        for resource, actions in (('items', ('read', 'create', 'update')), ('brands', ('read', 'create', 'update'))):
            for action in actions:
                with self.subTest(resource=resource, action=action):
                    permitted, role, _ = self.actor(['catalog-' + resource + '.' + action])
                    record = self.req(resource, (row if resource == 'items' else brand)['id'])
                    method = {'read': 'GET', 'create': 'POST', 'update': 'PUT'}[action]
                    path = self.path(resource, record['id'] if action == 'update' else None)
                    payload = {'values': self.values()} if resource == 'items' else {'values': {'name': 'Exact permission'}}
                    if action == 'update':
                        payload = {'values': {'name': 'Permitted update'}, 'expectedVersion': record['version']}
                    self.assertEqual(permitted.request(path, method, payload if method != 'GET' else None)[0], 201 if action == 'create' else 200)
                    if resource == 'items':
                        status, options = permitted.request(self.path('item-options'))
                        self.assertEqual(status, 200, options)
                        self.assertEqual(set(options), {'types', 'categories', 'units', 'brands', 'numbering'})
                        self.assertEqual(set(options['numbering']), {'GOOD', 'SERVICE'})
                        for value in options['numbering'].values():
                            self.assertEqual(set(value), {'mode'})
                            self.assertIn(value['mode'], ('AUTO', 'MANUAL'))
                    self.assertEqual(permitted.request(self.path('types'))[0], 403)
                    self.assertEqual(permitted.request(self.path('numbering', kind='GOOD'))[0], 403)
                    if resource == 'items':
                        current = self.req('items', row['id'])
                        child_path = self.path('items', row['id'] + '/identifiers')
                        child_payload = {'values': self.identifier('PERMISSION-' + action), 'expectedVersion': current['version']}
                        status, value = permitted.request(child_path, 'POST', child_payload)
                        self.assertEqual(status, 200 if action == 'update' else 403, value)
                        if action == 'update':
                            self.full(value)
                            self.assertEqual(value['version'], current['version'] + 1)
                    self.revoke(role)
                    self.assertEqual(permitted.request(path, method, payload if method != 'GET' else None)[0], 403)
        for resource in ('catalog-items', 'catalog-brands'):
            self.assertIn(self.root.request('/api/data/' + resource + '?tenantId=' + self.tenant_id, 'POST', {'name': 'Bypass'})[0], (400, 404, 405))
        reader, _, _ = self.actor(['catalog-items.read'])
        self.assertEqual(reader.request(self.path('items'), 'POST', {'values': self.values()})[0], 403)
        self.assertEqual(reader.request(self.path('items', row['id']), 'PUT', {'values': {'name': 'Denied'}, 'expectedVersion': row['version']})[0], 403)

    def test_exact_status_permissions_grants_revocation_separate_from_update(self):
        updater, _, _ = self.actor(['catalog-items.read', 'catalog-items.update'])
        for action, initial, target in (('activate', 'DRAFT', 'ACTIVE'), ('deactivate', 'ACTIVE', 'INACTIVE'), ('archive', 'DRAFT', 'ARCHIVED')):
            row = self.item()
            if initial == 'ACTIVE':
                row = self.status(row, 'ACTIVE')
            path = self.path('items', row['id'] + '/status')
            payload = {'status': target, 'expectedVersion': row['version']}
            self.assertEqual(updater.request(path, 'PUT', payload)[0], 403)
            self.assertEqual(self.req('items', row['id']), row)
            actor, role, _ = self.actor([])
            self.assertEqual(actor.request(path, 'PUT', payload)[0], 403)
            link = '/api/links/role-permissions/' + role['id'] + '?tenantId=' + self.tenant_id
            ids = [self.permission_ids['catalog-items.' + action]]
            self.assertEqual(self.root.request(link, 'PUT', {'ids': ids})[0], 204)
            self.assertEqual(self.root.request(link)[1]['ids'], ids)
            status, changed = actor.request(path, 'PUT', payload)
            self.assertEqual(status, 200, changed)
            self.assertEqual(self.req('items', row['id'])['status'], target)
            self.assertEqual(actor.request(self.path('items', row['id']), 'PUT', {'values': {'name': 'No CRUD grant'}, 'expectedVersion': changed['version']})[0], 403)
            self.revoke(role)
            self.assertEqual(actor.request(path, 'PUT', {'status': target, 'expectedVersion': changed['version']})[0], 403)
        row = self.item()
        self.assertEqual(updater.request(self.path('items', row['id']), 'PUT', {'values': {'status': 'ACTIVE'}, 'expectedVersion': row['version']})[0], 400)
        self.assertEqual(self.req('items', row['id']), row)

    def test_csrf_origin_and_all_mutations_require_version(self):
        row = self.item()
        payload = {'values': self.values()}
        self.assertIn(self.root.request(self.path('items'), 'POST', payload, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(self.path('items'), 'POST', payload, origin='https://foreign.invalid')[0], 403)
        row = self.child(row, 'identifiers', self.identifier())
        pack = self.pack()
        row = self.child(row, 'units', self.ratio(pack))
        requests = [(row['id'], 'PUT', {'values': {'name': 'Missing version'}}),
                    (row['id'] + '/status', 'PUT', {'status': 'ACTIVE'}),
                    (row['id'] + '/physical-data', 'PUT', {'values': self.physical()})]
        for resource in ('identifiers', 'units'):
            values = self.identifier('NEW') if resource == 'identifiers' else self.ratio(self.pack())
            suffix = row['id'] + '/' + resource
            requests += [(suffix, 'POST', {'values': values}), (suffix + '/' + row[resource][0]['id'], 'PUT', {'values': values}),
                         (suffix + '/' + row[resource][0]['id'], 'DELETE', None)]
        for suffix, method, body in requests:
            self.req('items', suffix, method, body, 400)
            self.assertEqual(self.req('items', row['id']), row)
        self.req('items', row['id'] + '/status', 'PUT', {'status': 'ACTIVE', 'expectedVersion': row['version'] - 1}, 409)
        self.child(row | {'version': row['version'] - 1}, 'physical-data', self.physical(), method='PUT', expected=409)

    def test_deferred_audit_failure_rolls_back_root_children_codes_and_status(self):
        row = self.item()
        pack = self.pack()
        row = self.child(row, 'identifiers', self.identifier())
        row = self.child(row, 'units', self.ratio(pack))
        row = self.child(row, 'physical-data', self.physical(), method='PUT')
        second_pack = self.pack()
        before_number = self.req('numbering', kind='GOOD')
        count_sql = f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}';"
        audit_count = fixture_sql(count_sql)
        root_count = self.req('items')['total']
        codes = fixture_sql(f"SELECT count(*) FROM masterdata.catalog_item_code WHERE tenant_id='{self.tenant_id}';")
        fixture_sql("CREATE FUNCTION foundation.catalog_items_proof_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.tenant_id='{self.tenant_id}'::uuid THEN RAISE EXCEPTION 'Catalog ITEMS fixture deferred audit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER catalog_items_proof_reject_audit AFTER INSERT ON foundation.audit_event "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.catalog_items_proof_reject_audit();")
        try:
            self.req('items', method='POST', body={'values': self.values(), 'status': 'ACTIVE'}, expected=500)
            self.req('items', row['id'], 'PUT', {'values': {'name': 'Never committed inline'}, 'status': 'ACTIVE', 'expectedVersion': row['version']}, 500)
            self.req('items', method='POST', body={'values': self.values(), 'units': [self.ratio(pack)], 'identifiers': [self.identifier('ROLLBACK')], 'physicalData': self.physical()}, expected=500)
            self.update('items', row, {'name': 'Never committed'}, 500)
            self.status(row, 'ACTIVE', 500)
            self.child(row, 'identifiers', self.identifier('Never inserted'), expected=500)
            self.child(row, 'units', self.ratio(second_pack), expected=500)
            self.child(row, 'identifiers', self.identifier('Never committed'), row['identifiers'][0]['id'], expected=500)
            self.child(row, 'identifiers', ident=row['identifiers'][0]['id'], method='DELETE', expected=500)
            self.child(row, 'units', self.ratio(pack, '24'), row['units'][0]['id'], expected=500)
            self.child(row, 'units', ident=row['units'][0]['id'], method='DELETE', expected=500)
            self.child(row, 'physical-data', self.physical() | {'net_weight': '1.3'}, method='PUT', expected=500)
            self.child(row, 'physical-data', None, method='PUT', expected=500)
            self.assertEqual(self.req('items', row['id']), row)
            self.assertEqual(self.req('items')['total'], root_count)
            self.assertEqual(self.req('numbering', kind='GOOD'), before_number)
            self.assertEqual(fixture_sql(count_sql), audit_count)
            self.assertEqual(fixture_sql(f"SELECT count(*) FROM masterdata.catalog_item_code WHERE tenant_id='{self.tenant_id}';"), codes)
        finally:
            fixture_sql('DROP TRIGGER catalog_items_proof_reject_audit ON foundation.audit_event; DROP FUNCTION foundation.catalog_items_proof_reject_audit();')
        # Prove recovery after failed commit instead of reporting a dead API as rollback success.
        self.status(row, 'ACTIVE')

    def test_sql_crossrefs_invariants_append_only_and_runtime_privileges(self):
        row = self.item()
        pack = self.pack()
        row = self.child(row, 'units', self.ratio(pack))
        row = self.child(row, 'identifiers', self.identifier('SQL-OWNED-UNIT', uom_id=pack['id']))
        service = self.item(item_type_id=self.service['id'])
        foreign = self.data_create('tenants', {'code': 'sql-' + uuid.uuid4().hex[:8], 'name': 'SQL synthetic'}, tenant=False)['id']
        foreign_category = self.create('categories', {'name': 'Foreign category'}, tenant=foreign)
        statements = [
            (f"UPDATE masterdata.catalog_item SET category_id='{foreign_category['id']}' WHERE id='{row['id']}'", ('23503', '23514')),
            (f"UPDATE masterdata.catalog_item_identifier SET tenant_id='{foreign}' WHERE id='{row['identifiers'][0]['id']}'", ('23503', '23514')),
            (f"UPDATE masterdata.catalog_item_identifier SET item_id='{service['id']}' WHERE id='{row['identifiers'][0]['id']}'", ('23503', '23514', 'P0001')),
            (f"INSERT INTO masterdata.catalog_item_physical_data(tenant_id,item_id,net_weight,weight_uom_id) VALUES ('{self.tenant_id}','{row['id']}',1,'{self.base['id']}')", ('23514', 'P0001')),
            (f"UPDATE masterdata.catalog_item_unit SET conversion_numerator=0 WHERE item_id='{row['id']}'", ('23514',)),
            (f"UPDATE masterdata.catalog_unit_of_measure SET factor_to_base=1 WHERE id='{pack['id']}'", ('23514',)),
            (f"UPDATE masterdata.catalog_item SET item_type_id='{self.service['id']}' WHERE id='{row['id']}'", ('23514', 'P0001')),
            (f"DELETE FROM masterdata.catalog_item WHERE id='{row['id']}'", ('23514', '23503', 'P0001')),
            (f"DELETE FROM masterdata.catalog_item_code WHERE item_id='{row['id']}'", ('23514', 'P0001')),
            (f"INSERT INTO masterdata.catalog_item_physical_data(tenant_id,item_id) VALUES ('{self.tenant_id}','{service['id']}')", ('23514', 'P0001')),
        ]
        for statement, codes in statements:
            result = fixture.sql('\\set VERBOSITY verbose\nBEGIN; ' + statement + '; SET CONSTRAINTS ALL IMMEDIATE; ROLLBACK;', check=False)
            self.assertNotEqual(result.returncode, 0, 'Missing SQL invariant: ' + statement)
            self.assertTrue(any(code in result.stderr for code in codes), 'Not the intended SQL constraint: ' + result.stderr)
        # Runtime authorization is tested with real SET ROLE, not inferred only from grant metadata.
        for statement in (f"DELETE FROM masterdata.catalog_item WHERE id='{row['id']}'",
                          f"UPDATE masterdata.catalog_item_code SET code='FORBIDDEN' WHERE item_id='{row['id']}'"):
            result = fixture.sql('\\set VERBOSITY verbose\nBEGIN; SET LOCAL ROLE enginia360_app; ' + statement + '; ROLLBACK;', check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('42501', result.stderr, result.stderr)
        self.assertEqual(self.req('items', row['id']), row)
        self.assertEqual(self.req('items', service['id']), service)
        privileges = json.loads(fixture_sql("SELECT json_build_object('superuser',rolsuper,'createRole',rolcreaterole,'createDb',rolcreatedb,"
            "'schemaCreate',has_schema_privilege('enginia360_app','masterdata','CREATE'),"
            "'auditDelete',has_table_privilege('enginia360_app','foundation.audit_event','DELETE'),"
            "'itemDelete',has_table_privilege('enginia360_app','masterdata.catalog_item','DELETE'),"
            "'codeUpdate',has_table_privilege('enginia360_app','masterdata.catalog_item_code','UPDATE'),"
            "'codeDelete',has_table_privilege('enginia360_app','masterdata.catalog_item_code','DELETE'))::text FROM pg_roles WHERE rolname='enginia360_app';"))
        self.assertTrue(privileges)
        self.assertTrue(all(value is False for value in privileges.values()), privileges)
        for table in ('catalog_item', 'catalog_item_code', 'catalog_item_identifier', 'catalog_item_unit', 'catalog_item_physical_data', 'catalog_brand'):
            self.assertEqual(fixture_sql(f"SELECT has_table_privilege('enginia360_app','masterdata.{table}','TRUNCATE');"), 'f')


if __name__ == '__main__':
    unittest.main()
