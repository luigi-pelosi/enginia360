"""Prove HTTP Catalogo: solo runner isolato, nessun CatalogItem/Fase 2."""
import json
import os
from decimal import Decimal
import unittest
from urllib.parse import urlencode
import uuid

from catalog_helpers import configure_fixture, fixture_sql, login_root, reseed
from test_api import Client


@unittest.skipUnless(os.environ.get('ENGINIA360_CATALOG_PROOF') == '1', 'Richiede run_catalog_proof.py e fixture isolata')
class CatalogHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = configure_fixture()
        if not cls.fixture.verify_target(cls.fixture.DB) or not cls.fixture.verify_target(cls.fixture.API):
            raise RuntimeError('Database/API Catalogo fuori scope o assenti')
        cls.root, cls.credentials = login_root()

    def setUp(self):
        self.code = 'cat-' + uuid.uuid4().hex[:12]
        self.tenant = self.data_create('tenants', {'code': self.code, 'name': 'Catalogo sintetico'}, tenant=False)
        self.tenant_id = self.tenant['id']

    def data_create(self, resource, values, tenant=True):
        suffix = '?tenantId=' + self.tenant_id if tenant else ''
        status, body = self.root.request('/api/data/' + resource + suffix, 'POST', values)
        self.assertEqual(status, 201, (resource, status, body))
        return body

    def path(self, resource, ident=None, tenant=None, **query):
        return '/api/catalog/' + resource + ('/' + ident if ident else '') + '?' + urlencode({'tenantId': tenant or self.tenant_id, **query})

    def req(self, resource, ident=None, method='GET', body=None, expected=200, tenant=None, **query):
        status, value = self.root.request(self.path(resource, ident, tenant, **query), method, body)
        self.assertEqual(status, expected, (resource, ident, status, value))
        return value

    def create(self, resource, values, **kwargs):
        return self.req(resource, method='POST', body={'values': values}, expected=201, **kwargs)

    def update(self, resource, row, values, expected=200):
        return self.req(resource, row['id'], 'PUT', {'values': values, 'expectedVersion': row['version']}, expected)

    def listed(self, resource, **query):
        return self.req(resource, page=1, pageSize=100, **query)['items']

    def unit(self, **values):
        return self.create('units', {'code': 'U' + uuid.uuid4().hex[:8], 'name': 'Unità sintetica',
            'dimension': 'COUNT', 'factor_to_base': '1', 'decimal_places': 2,
            'is_base': False, 'is_active': True, **values})

    def category(self, name='Categoria', **values):
        return self.create('categories', {'name': name, 'code': None, 'description': None,
            'parent_id': None, 'sort_order': 0, 'is_active': True, **values})

    def type(self, **values):
        return self.create('types', {'name': 'Tipo sintetico', 'code': None, 'kind': 'GOOD',
            'default_sellable': True, 'default_purchasable': True,
            'default_track_stock': True, 'is_active': True, **values})

    def test_seed_is_tenant_scoped_exact_and_idempotent_without_overwrite(self):
        units, types, categories = (self.listed(resource) for resource in ('units', 'types', 'categories'))
        self.assertEqual((len(units), len(types), len(categories)), (11, 2, 0))
        self.assertEqual({x['dimension'] for x in units}, {'COUNT', 'MASS', 'LENGTH', 'VOLUME', 'TIME', 'AREA'})
        for dimension in {x['dimension'] for x in units}:
            bases = [x for x in units if x['dimension'] == dimension and x['is_base']]
            self.assertEqual(len(bases), 1, dimension)
            self.assertTrue(bases[0]['is_active'])
            self.assertEqual(Decimal(bases[0]['factor_to_base']), Decimal('1'))
        self.assertEqual({x['kind'] for x in types}, {'GOOD', 'SERVICE'})
        self.assertFalse(next(x for x in types if x['kind'] == 'SERVICE')['default_track_stock'])
        self.update('units', units[0], {'name': 'Personalizzata', 'is_active': False} if not units[0]['is_base'] else {'name': 'Personalizzata'})
        self.update('types', types[0], {'name': 'Tipo personalizzato', 'is_active': False})
        before = {r: self.listed(r) for r in ('units', 'types', 'categories')}
        reseed(self.tenant_id)
        reseed(self.tenant_id)
        self.assertEqual({r: self.listed(r) for r in before}, before)

    def test_tenant_isolation_cross_references_and_pagination(self):
        foreign = self.data_create('tenants', {'code': 'other-' + uuid.uuid4().hex[:10], 'name': 'Altro tenant'}, tenant=False)['id']
        for resource, row in (('units', self.unit()), ('categories', self.category()), ('types', self.type())):
            with self.subTest(resource=resource):
                self.req(resource, row['id'], tenant=foreign, expected=404)
                self.req(resource, row['id'], 'PUT', {'values': {'name': 'Intrusione'}, 'expectedVersion': row['version']}, 404, tenant=foreign)
                self.assertNotIn(row['id'], [r['id'] for r in self.listed(resource, tenant=foreign)])
                self.assertEqual(self.req(resource, row['id']), row)
        parent = self.category('Padre esterno')
        self.req('categories', method='POST', body={'values': {'name': 'Figlia non valida', 'parent_id': parent['id']}}, expected=400, tenant=foreign)
        existing = self.create('categories', {'name': 'Categoria esterna'}, tenant=foreign)
        self.req('categories', existing['id'], 'PUT', {'values': {'parent_id': parent['id']}, 'expectedVersion': existing['version']}, 400, tenant=foreign)
        source = self.unit()
        target = self.listed('units', tenant=foreign)[0]
        self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': target['id'], 'quantity': '1'}, 404)
        for i in range(5):
            self.category('Filtro isolato ' + str(i))
        first = self.req('categories', search='Filtro isolato', page=1, pageSize=2)
        second = self.req('categories', search='Filtro isolato', page=2, pageSize=2)
        self.assertEqual((first['total'], first['page'], first['pageSize'], len(first['items'])), (5, 1, 2, 2))
        self.assertEqual((second['total'], second['page'], second['pageSize'], len(second['items'])), (5, 2, 2, 2))
        self.assertFalse({x['id'] for x in first['items']} & {x['id'] for x in second['items']})

    def test_category_cycles_branch_move_and_leaf_delete(self):
        a, b = self.category('A'), self.category('B')
        child = self.category('Figlia', parent_id=a['id'])
        leaf = self.category('Foglia', parent_id=child['id'])
        for parent in (a['id'], child['id'], leaf['id']):
            self.update('categories', a, {'parent_id': parent}, expected=400)
            self.assertEqual(self.req('categories', a['id']), a)
        status, body = self.root.request(self.path('categories', a['id'], expectedVersion=a['version']), 'DELETE')
        self.assertIn(status, (400, 409), body)
        moved = self.update('categories', child, {'parent_id': b['id']})
        self.assertEqual(moved['parent_id'], b['id'])
        tree = self.req('categories/tree')['items']
        by_id = {node['id']: node for node in tree}
        self.assertEqual(by_id[child['id']]['parent_id'], b['id'])
        self.assertEqual(by_id[leaf['id']]['parent_id'], child['id'])
        self.assertIn(child['id'], {node['id'] for node in self.req('categories/tree', parentId=b['id'])['items']})
        self.req('categories', leaf['id'], 'DELETE', expected=409, expectedVersion=leaf['version'] + 1)
        self.req('categories', leaf['id'], 'DELETE', expected=204, expectedVersion=leaf['version'])
        self.req('categories', leaf['id'], expected=404)
        self.req('categories', child['id'], 'DELETE', expected=204, expectedVersion=moved['version'])
        self.assertNotIn(child['id'], {x['id'] for x in self.req('categories/tree')['items']})

    def test_conversion_exact_decimal_midpoints_and_rounding_flag(self):
        source, target = self.unit(decimal_places=12), self.unit(decimal_places=2)
        for quantity, rounded, unrounded, flag in (
            ('1.005', '1.01', '1.005', True), ('-1.005', '-1.01', '-1.005', True),
            ('0.1', '0.10', '0.1', False), ('0', '0', '0', False)):
            with self.subTest(quantity=quantity):
                result = self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': target['id'], 'quantity': quantity})
                self.assertIsInstance(result['quantity'], str)
                self.assertIsInstance(result['unroundedQuantity'], str)
                self.assertEqual(Decimal(result['quantity']), Decimal(rounded))
                self.assertEqual(Decimal(result['unroundedQuantity']), Decimal(unrounded))
                self.assertIs(result['rounded'], flag)
                self.assertEqual(result['decimalPlaces'], 2)
        tenth, fifth = self.unit(factor_to_base='0.1'), self.unit(factor_to_base='0.2')
        converted = self.req('units', tenth['id'] + '/convert', 'POST', {'targetUnitId': fifth['id'], 'quantity': '0.3'})
        self.assertEqual(Decimal(converted['quantity']), Decimal('0.15'))
        self.assertFalse(converted['rounded'])
        mass = next(x for x in self.listed('units') if x['dimension'] == 'MASS')
        self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': mass['id'], 'quantity': '1'}, 400)
        inactive = self.update('units', target, {'is_active': False})
        self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': inactive['id'], 'quantity': '1'}, 400)
        self.req('units', inactive['id'] + '/convert', 'POST', {'targetUnitId': source['id'], 'quantity': '1'}, 400)

    def test_precision_input_overflow_mandatory_code_and_structural_immutability(self):
        source, target = self.unit(decimal_places=12), self.unit()
        for quantity in ('0.1234567890123', '79228162514264337593543950336', '1e2', '1,2', 'NaN'):
            with self.subTest(quantity=quantity):
                self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': target['id'], 'quantity': quantity}, 400)
        self.req('units', source['id'] + '/convert', 'POST', {'targetUnitId': target['id'], 'quantity': '0.123456789012'})
        double = self.unit(factor_to_base='2')
        self.req('units', double['id'] + '/convert', 'POST', {'targetUnitId': target['id'], 'quantity': '79228162514264337593543950335'}, 400)
        template = {k: source[k] for k in ('code', 'name', 'dimension', 'factor_to_base', 'decimal_places', 'is_base', 'is_active')}
        mutations = [{'decimal_places': -1}, {'decimal_places': 13}, {'factor_to_base': '0'},
                     {'factor_to_base': '-1'}, {'factor_to_base': '0.1234567890123'},
                     {'factor_to_base': '79228162514264337593543950336'}, {'code': None}, {'code': ''}, {'code': '   '}]
        for change in mutations:
            with self.subTest(change=change):
                self.req('units', method='POST', body={'values': {**template, 'code': 'N' + uuid.uuid4().hex[:8], **change}}, expected=400)
        missing = {k: v for k, v in template.items() if k != 'code'}
        self.req('units', method='POST', body={'values': missing}, expected=400)
        for change in ({'dimension': 'MASS'}, {'factor_to_base': '2'}, {'is_base': True}, {'code': None}):
            with self.subTest(immutable=change):
                status, body = self.root.request(self.path('units', source['id']), 'PUT', {'values': change, 'expectedVersion': source['version']})
                self.assertIn(status, (400, 409), body)
                self.assertEqual(self.req('units', source['id']), source)
        base = next(x for x in self.listed('units') if x['dimension'] == 'COUNT' and x['is_base'])
        status, body = self.root.request(self.path('units'), 'POST', {'values': {**template, 'code': 'BASE2', 'is_base': True}})
        self.assertIn(status, (400, 409), body)
        self.assertEqual(sum(x['dimension'] == 'COUNT' and x['is_base'] for x in self.listed('units')), 1)
        status, body = self.root.request(self.path('units', base['id']), 'PUT', {'values': {'is_active': False}, 'expectedVersion': base['version']})
        self.assertIn(status, (400, 409), body)
        self.assertEqual(self.req('units', base['id']), base)

    def test_type_service_stock_and_unused_kind_editable(self):
        service = self.type(kind='SERVICE', default_track_stock=False)
        self.assertFalse(service['default_track_stock'])
        self.req('types', method='POST', body={'values': {'name': 'Servizio invalido', 'kind': 'SERVICE', 'default_track_stock': True}}, expected=400)
        self.update('types', service, {'default_track_stock': True}, 400)
        for row, kind in ((service, 'GOOD'), (self.type(), 'SERVICE')):
            changed = self.update('types', row, {'kind': kind, 'default_track_stock': False})
            self.assertEqual(changed['kind'], kind)
            self.assertTrue(changed['canChangeKind'])
            self.assertEqual(self.req('types', row['id']), changed)

    def test_optimistic_conflicts_for_all_three_resources(self):
        for resource, row in (('units', self.unit()), ('categories', self.category()), ('types', self.type())):
            with self.subTest(resource=resource):
                updated = self.update(resource, row, {'name': 'Versione nuova'})
                self.assertEqual(updated['version'], row['version'] + 1)
                self.update(resource, row, {'name': 'Versione obsoleta'}, 409)
                self.assertEqual(self.req(resource, row['id']), updated)
                self.req(resource, row['id'], 'PUT', {'values': {'name': 'Senza versione'}}, 400)
                self.assertEqual(self.req(resource, row['id']), updated)

    def test_audit_records_minimized_before_and_after(self):
        row = self.category('Nome iniziale')
        updated = self.update('categories', row, {'name': 'Nome aggiornato'})
        details = json.loads(fixture_sql(
            f"SELECT details::text FROM foundation.audit_event WHERE record_id='{row['id']}' "
            "AND resource='catalog-categories' AND action='update' ORDER BY created_at DESC LIMIT 1;"))
        self.assertEqual(details.get('before'), {'name': row['name']})
        self.assertEqual(details.get('after'), {'name': updated['name']})
        self.assertEqual(details.get('version'), updated['version'])

    def test_numbering_good_service_bp_are_independent(self):
        bp_path = '/api/business-partner-numbering?tenantId=' + self.tenant_id
        status, bp_before = self.root.request(bp_path)
        self.assertEqual(status, 200, bp_before)
        configs = {kind: self.req('numbering', kind=kind) for kind in ('GOOD', 'SERVICE')}
        for kind, number, prefix in (('GOOD', 17, 'G-'), ('SERVICE', 29, 'S-')):
            config = configs[kind]
            changed = self.req('numbering', method='PUT', kind=kind, body={**config, 'mode': 'AUTO', 'prefix': prefix, 'padding': 5, 'nextNumber': number})
            self.assertEqual((changed['nextNumber'], changed['prefix'], changed['version']), (number, prefix, config['version'] + 1))
            self.req('numbering', method='PUT', kind=kind, body={**config, 'nextNumber': 30}, expected=409)
            other = 'SERVICE' if kind == 'GOOD' else 'GOOD'
            self.assertEqual(self.req('numbering', kind=other), configs[other])
            configs[kind] = changed
            self.assertEqual(self.root.request(bp_path)[1], bp_before)
        status, bp_changed = self.root.request(bp_path, 'PUT', {**bp_before, 'prefix': 'PARTNER-', 'nextNumber': 43})
        self.assertEqual(status, 200, bp_changed)
        self.assertEqual({kind: self.req('numbering', kind=kind) for kind in configs}, configs)
        self.req('numbering', kind='CATALOG_ITEM', expected=400)
        # Nessuna allocazione CatalogItem: il kernel concorrente è coperto dalla suite backend.

    def actor(self, grants):
        username = 'actor-' + uuid.uuid4().hex[:10]
        user = self.data_create('users', {'username': username, 'first_name': 'Catalogo', 'last_name': 'Prova', 'email': username + '@example.invalid'})
        role = self.data_create('roles', {'name': 'Ruolo Catalogo'})
        permissions = []
        page = 1
        while True:
            status, catalog = self.root.request('/api/data/permissions?' + urlencode({'tenantId': self.tenant_id, 'page': page, 'pageSize': 100}))
            self.assertEqual(status, 200, catalog)
            permissions.extend(catalog['items'])
            if len(permissions) >= catalog['total']:
                break
            self.assertTrue(catalog['items'], 'Paginazione permessi non avanza')
            page += 1
        ids = [row['id'] for row in permissions if row['code'] in grants]
        self.assertEqual(len(ids), len(grants), (grants, ids))
        for relation, owner, targets in (('user-roles', user['id'], [role['id']]), ('role-permissions', role['id'], ids)):
            self.assertEqual(self.root.request('/api/links/' + relation + '/' + owner + '?tenantId=' + self.tenant_id, 'PUT', {'ids': targets})[0], 204)
        password = uuid.uuid4().hex + '-Initial!'
        self.assertEqual(self.root.request('/api/users/' + user['id'] + '/password?tenantId=' + self.tenant_id, 'PUT', {'newPassword': password})[0], 204)
        actor = Client()
        status, session = actor.login({'username': username, 'password': password}, self.code)
        self.assertEqual(status, 200, session)
        self.assertFalse(session['isSuperAdmin'])
        changed = uuid.uuid4().hex + '-Changed!'
        self.assertEqual(actor.request('/api/auth/password', 'PUT', {'currentPassword': password, 'newPassword': changed})[0], 204)
        actor.token = None
        return actor, role, {'username': username, 'password': changed}

    def test_exact_permissions_default_deny_and_live_revocation(self):
        actor, role, _ = self.actor([])
        paths = [self.path(resource) for resource in ('units', 'categories', 'types')] + [self.path('categories/tree'), self.path('numbering', kind='GOOD')]
        for path in paths:
            self.assertEqual(actor.request(path)[0], 403, path)
            self.assertEqual(Client().request(path)[0], 401, path)
        rows = {'units': self.unit(), 'categories': self.category(), 'types': self.type()}
        actions = [(r, a) for r in rows for a in ('read', 'create', 'update')] + [('categories', 'delete'), ('numbering', 'read'), ('numbering', 'update')]
        for resource, action in actions:
            with self.subTest(resource=resource, action=action):
                code = 'catalog-' + resource + '.' + action
                permitted, granted_role, _ = self.actor([code])
                row = rows.get(resource)
                path = self.path(resource, row['id'] if row and action in ('update', 'delete') else None, **({'kind': 'GOOD'} if resource == 'numbering' else {}))
                method = {'read': 'GET', 'create': 'POST', 'update': 'PUT', 'delete': 'DELETE'}[action]
                if resource == 'numbering' and action == 'update':
                    payload = {**self.req('numbering', kind='GOOD'), 'prefix': 'PERM-'}
                elif action == 'create':
                    values = {'name': 'Permesso esatto'}
                    if resource == 'units':
                        values.update(code='P' + uuid.uuid4().hex[:8], dimension='COUNT', factor_to_base='1', decimal_places=2, is_base=False, is_active=True)
                    elif resource == 'types':
                        values.update(kind='GOOD', default_sellable=True, default_purchasable=True, default_track_stock=False, is_active=True)
                    payload = {'values': values}
                else:
                    payload = {'values': {'name': 'Permesso esatto'}, 'expectedVersion': row['version']} if row else None
                # Ogni grant ha una prova positiva reale, prima della revoca.
                status, body = permitted.request(path + ('&expectedVersion=' + str(row['version']) if action == 'delete' else ''), method, payload)
                if action == 'read':
                    self.assertEqual(status, 200, body)
                elif resource == 'numbering':
                    self.assertEqual(status, 200, body)
                elif action == 'create':
                    self.assertEqual(status, 201, body)
                else:
                    self.assertIn(status, (200, 204), body)
                if action == 'update' and row:
                    rows[resource] = self.req(resource, row['id'])
                elif action == 'delete':
                    rows[resource] = self.category('Per altri controlli')
                for other in ('units', 'categories', 'types'):
                    if other != resource or action != 'read':
                        self.assertEqual(permitted.request(self.path(other))[0], 403)
                if action == 'read' and row:
                    self.assertEqual(permitted.request(self.path(resource), 'POST', {'values': {'name': 'Negato'}})[0], 403)
                    self.assertEqual(permitted.request(self.path(resource, row['id']), 'PUT', {'values': {'name': 'Negato'}, 'expectedVersion': row['version']})[0], 403)
                link = '/api/links/role-permissions/' + granted_role['id'] + '?tenantId=' + self.tenant_id
                self.assertEqual(self.root.request(link, 'PUT', {'ids': []})[0], 204)
                self.assertEqual(permitted.request(path, method, payload)[0], 403, 'Revoca nella sessione già aperta')
        self.assertEqual(actor.request(self.path('units', tenant=str(uuid.uuid4())))[0], 403)

    def test_csrf_and_foreign_origin_do_not_mutate(self):
        before = self.req('categories')['total']
        body = {'values': {'name': 'Non autorizzata'}}
        self.assertIn(self.root.request(self.path('categories'), 'POST', body, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(self.path('categories'), 'POST', body, origin='https://foreign.invalid')[0], 403)
        self.assertEqual(self.req('categories')['total'], before)

    def test_deferred_sql_audit_failure_rolls_back_http_mutations(self):
        rows = {'units': self.unit(), 'categories': self.category(), 'types': self.type()}
        before = {r: self.req(r, row['id']) for r, row in rows.items()}
        total = {r: self.req(r)['total'] for r in rows}
        count_sql = f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}'::uuid;"
        audit_before = fixture_sql(count_sql)
        fixture_sql("CREATE FUNCTION foundation.catalog_proof_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.tenant_id='{self.tenant_id}'::uuid THEN RAISE EXCEPTION 'Rifiuto audit fixture Catalogo'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER catalog_proof_reject_audit AFTER INSERT ON foundation.audit_event "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.catalog_proof_reject_audit();")
        try:
            for resource, row in rows.items():
                with self.subTest(resource=resource):
                    self.update(resource, row, {'name': 'Mai committata'}, 500)
                    self.assertEqual(self.req(resource, row['id']), before[resource])
                    values = {'name': 'Mai creata'}
                    if resource == 'units':
                        values.update(code='ROLLBACK', dimension='COUNT', factor_to_base='1', decimal_places=2, is_base=False, is_active=True)
                    elif resource == 'types':
                        values.update(kind='GOOD', default_track_stock=False)
                    self.req(resource, method='POST', body={'values': values}, expected=500)
                    self.assertEqual(self.req(resource)['total'], total[resource])
            row = rows['categories']
            self.req('categories', row['id'], 'DELETE', expected=500, expectedVersion=row['version'])
            self.assertEqual(self.req('categories', row['id']), before['categories'])
            config = self.req('numbering', kind='GOOD')
            self.req('numbering', method='PUT', kind='GOOD', body={**config, 'prefix': 'ROLLBACK-'}, expected=500)
            self.assertEqual(self.req('numbering', kind='GOOD'), config)
            self.assertEqual(fixture_sql(count_sql), audit_before)
        finally:
            fixture_sql('DROP TRIGGER catalog_proof_reject_audit ON foundation.audit_event; DROP FUNCTION foundation.catalog_proof_reject_audit();')

    def test_database_constraints_reject_synthetic_invalid_values(self):
        unit, service = self.unit(), self.type(kind='SERVICE', default_track_stock=False)
        # Individua le tabelle dal contratto delle colonne: nessuna dipendenza dal nome fisico.
        def relation(column):
            matches = fixture_sql("SELECT quote_ident(table_schema)||'.'||quote_ident(table_name) FROM information_schema.columns "
                "WHERE table_schema='masterdata' AND column_name='" + column + "';").splitlines()
            self.assertEqual(len(matches), 1, (column, matches))
            return matches[0]
        for table, row, assignment in ((relation('factor_to_base'), unit, 'factor_to_base=0'),
                                      (relation('factor_to_base'), unit, 'decimal_places=13'),
                                      (relation('default_track_stock'), service, 'default_track_stock=true')):
            with self.subTest(assignment=assignment):
                result = self.fixture.sql(f"\\set VERBOSITY verbose\nBEGIN; UPDATE {table} SET {assignment} WHERE id='{row['id']}'::uuid; ROLLBACK;", check=False)
                self.assertNotEqual(result.returncode, 0, 'Vincolo DB non applicato: ' + assignment)
                self.assertIn('23514', result.stderr, 'Attesa violazione SQL CHECK o guard equivalente')
        self.assertEqual(self.req('units', unit['id']), unit)
        self.assertEqual(self.req('types', service['id']), service)
        foreign = self.data_create('tenants', {'code': 'db-' + uuid.uuid4().hex[:10], 'name': 'Tenant vincolo DB'}, tenant=False)['id']
        parent = self.category('Padre SQL')
        child = self.create('categories', {'name': 'Figlia SQL'}, tenant=foreign)
        table = relation('parent_id')
        result = self.fixture.sql(f"BEGIN; UPDATE {table} SET parent_id='{parent['id']}'::uuid WHERE id='{child['id']}'::uuid; ROLLBACK;", check=False)
        self.assertNotEqual(result.returncode, 0, 'FK composta tenant/padre non applicata')
        self.assertIn('foreign key constraint', result.stderr.lower(), result.stderr)
        self.assertEqual(self.req('categories', child['id'], tenant=foreign), child)


if __name__ == '__main__':
    unittest.main()
