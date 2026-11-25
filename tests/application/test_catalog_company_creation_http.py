"""Atomic new-item company commands: real isolated cookie/CSRF HTTP acceptance."""
import uuid
from test_catalog_companies_http import CatalogCompaniesHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES = (
    'test_item_options_exposes_company_type_defaults_without_mutating',
    'test_new_item_company_opt_in_defaults_overrides_and_new_units',
    'test_new_item_company_invalid_selection_rolls_back_aggregate',
    'test_new_item_company_exact_same_role_create_without_read',
    'test_new_item_company_create_only_bounds_and_lifecycle',
    'test_new_item_company_deferred_audit_failure_rolls_back_everything',
)


class CatalogCompanyCreationHttp(CatalogCompaniesHttp):
    def test_item_options_exposes_company_type_defaults_without_mutating(self):
        row=self.create('types',{'name':'Options company defaults','kind':'GOOD','default_sellable':False,'default_purchasable':True,'default_track_stock':True})
        snapshot=self.creation_snapshot()
        actual=next(option for option in self.req('item-options')['types'] if option['id']==row['id'])
        for field in ('default_sellable','default_purchasable','default_track_stock'):
            self.assertIn(field,actual);self.assertEqual(actual[field],row[field])
        self.assertEqual(self.creation_snapshot(),snapshot)

    def selection(self, company, **values):
        return {'company_id': company['id'], 'values': values}

    def new_company_item(self, companies, *, expected=201, client=None, **parts):
        body = {'values': self.values(), 'companies': companies, **parts}
        status, result = (client or self.root).request(self.path('items'), 'POST', body)
        self.assertEqual(status, expected, result)
        if expected == 201:
            self.full(result)
        return result

    def creation_snapshot(self, kind='GOOD'):
        tables = ('masterdata.catalog_item', 'masterdata.catalog_item_unit',
                  'masterdata.catalog_item_identifier', 'masterdata.catalog_item_physical_data',
                  'masterdata.catalog_item_code', 'masterdata.catalog_item_company',
                  'foundation.audit_event')
        return (self.req('numbering', kind=kind), tuple(fixture_sql(
            f"SELECT count(*) FROM {table} WHERE tenant_id='{self.tenant_id}'") for table in tables))

    def test_new_item_company_opt_in_defaults_overrides_and_new_units(self):
        # Deliberately first: old backend rejects companies=[] with HTTP 400.
        empty = self.new_company_item([])
        self.read_config(self.a, empty, expected=404)
        omitted = self.item()
        self.read_config(self.a, omitted, expected=404)
        ty = self.create('types', {'name': 'Atomic snapshot defaults', 'kind': 'GOOD',
            'default_sellable': True, 'default_purchasable': False, 'default_track_stock': True})
        pack = self.pack()
        item = self.new_company_item([
            self.selection(self.a, default_sales_uom_id=pack['id']),
            self.selection(self.b, is_enabled=False, is_sellable=False, is_purchasable=True,
                           track_stock=False, default_purchase_uom_id=None)],
            values=self.values(item_type_id=ty['id']), units=[self.ratio(pack)],
            identifiers=[self.identifier('ATOMIC-' + uuid.uuid4().hex, uom_id=pack['id'])])
        a = self.read_config(self.a, item)
        b = self.read_config(self.b, item)
        self.assertTrue(a['is_sellable']); self.assertFalse(a['is_purchasable']); self.assertTrue(a['track_stock'])
        self.assertEqual(a['effective_sales_uom_id'], pack['id'])
        self.assertFalse(b['is_enabled']); self.assertFalse(b['is_sellable']); self.assertTrue(b['is_purchasable'])
        self.assertFalse(b['track_stock']); self.assertEqual(b['effective_purchase_uom_id'], self.base['id'])
        self.assertEqual(a['version'], 1); self.assertEqual(b['version'], 1)
        self.update('types', ty, {'default_sellable': False, 'default_purchasable': True, 'default_track_stock': False})
        self.assertEqual(self.read_config(self.a, item), a)
        self.assertEqual(self.read_config(self.b, item), b)
        self.assertEqual(self.req('items', item['id']), item)

    def test_new_item_company_invalid_selection_rolls_back_aggregate(self):
        pack = self.pack()
        foreign = self.data_create('tenants', {'code': 'atomic-foreign-' + uuid.uuid4().hex[:8], 'name': 'Foreign'}, tenant=False)
        status, foreign_company = self.root.request('/api/data/companies?tenantId=' + foreign['id'], 'POST', {'name': 'Foreign'})
        self.assertEqual(status, 201, foreign_company)
        other_unit = next(x for x in self.refs['units'] if x['code'] == 'KG')
        cases = [([self.selection(self.a), self.selection(self.a)], 400),
                 ([self.selection(self.a), self.selection(foreign_company)], 404),
                 ([self.selection(self.a), self.selection(self.b, default_sales_uom_id=other_unit['id'])], 400)]
        for companies, expected in cases:
            before = self.creation_snapshot()
            self.new_company_item(companies, expected=expected, units=[self.ratio(pack)],
                identifiers=[self.identifier('ROLLBACK-' + uuid.uuid4().hex, uom_id=pack['id'])], physicalData=self.physical())
            self.assertEqual(self.creation_snapshot(), before)
        for kind in ('SERVICE', 'INTANGIBLE', 'CHARGE'):
            ty = self.create('types', {'name': 'Atomic no stock ' + kind, 'kind': kind})
            before = self.creation_snapshot(kind)
            self.new_company_item([self.selection(self.a), self.selection(self.b, track_stock=True)],
                values=self.values(item_type_id=ty['id']), expected=400)
            self.assertEqual(self.creation_snapshot(kind), before)

    def test_new_item_company_exact_same_role_create_without_read(self):
        grants = ['catalog-items.create', 'catalog-items.activate', 'catalog-item-companies.create']
        actor, role, _ = self.scoped_actor(grants, [self.a])
        # No root read or company read is needed to execute the command.
        status, item = actor.request(self.path('items'), 'POST', {'values': self.values(), 'companies': [self.selection(self.a)]})
        self.assertEqual(status, 201, item)
        self.read_config(self.a, item)
        self.read_config(self.a, item, actor, 403)
        scope_only = self.data_create('roles', {'name': 'Atomic B scope without create'})
        user_id = fixture_sql(f"SELECT user_id FROM foundation.user_role WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}'")
        self.assertEqual(self.root.request('/api/roles/' + scope_only['id'] + '/companies?tenantId=' + self.tenant_id,
            'PUT', {'companyIds': [self.b['id']]})[0], 200)
        self.assertEqual(self.root.request('/api/links/user-roles/' + user_id + '?tenantId=' + self.tenant_id,
            'PUT', {'ids': [role['id'], scope_only['id']]})[0], 204)
        before = self.creation_snapshot()
        self.new_company_item([self.selection(self.a), self.selection(self.b)], client=actor, expected=403)
        self.assertEqual(self.creation_snapshot(), before)
        for denied_grants in (['catalog-items.create', 'catalog-item-companies.create'],
                              ['catalog-items.activate', 'catalog-item-companies.create'],
                              ['catalog-items.create', 'catalog-items.activate']):
            denied, _, _ = self.scoped_actor(denied_grants, [self.a])
            before = self.creation_snapshot()
            self.new_company_item([self.selection(self.a)], client=denied, expected=403)
            self.assertEqual(self.creation_snapshot(), before)

    def test_new_item_company_create_only_bounds_and_lifecycle(self):
        item = self.item()
        self.req('items', item['id'], 'PUT', {'values': {}, 'expectedVersion': item['version'], 'companies': []}, expected=400)
        self.assertEqual(self.req('items', item['id']), item)
        for companies in (None, {}, [None], [{'company_id': self.a['id']}],
                          [self.selection(self.a, canSell=True)],
                          [{'company_id': str(uuid.uuid4()), 'values': {}, 'expectedVersion': 0}],
                          [{'company_id': str(uuid.uuid4()), 'values': {}} for _ in range(101)]):
            before = self.creation_snapshot()
            self.new_company_item(companies, expected=400)
            self.assertEqual(self.creation_snapshot(), before)
        before = self.creation_snapshot()
        self.new_company_item([self.selection(self.a)], status='ARCHIVED', expected=400)
        self.assertEqual(self.creation_snapshot(), before)
        status, response = self.root.request('/api/data/companies/' + self.b['id'] + '?tenantId=' + self.tenant_id,
            'PUT', {'name': self.b['name'], 'is_enabled': False})
        self.assertEqual(status, 200, response)
        before = self.creation_snapshot()
        self.new_company_item([self.selection(self.a), self.selection(self.b, is_enabled=False)], expected=409)
        self.assertEqual(self.creation_snapshot(), before)
        suspended = self.new_company_item([self.selection(self.a)], status='SUSPENDED')
        self.assertFalse(self.read_config(self.a, suspended)['canSell'])
        # Existing-item independent handlers retain their contract.
        self.config(self.a, item)

    def test_new_item_company_deferred_audit_failure_rolls_back_everything(self):
        pack = self.pack()
        before = self.creation_snapshot()
        fixture_sql("CREATE FUNCTION foundation.reject_atomic_company_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.tenant_id='{self.tenant_id}'::uuid AND NEW.resource='catalog-item-companies' THEN RAISE EXCEPTION 'atomic company audit proof'; END IF; RETURN NEW; END $$;"
            "CREATE CONSTRAINT TRIGGER reject_atomic_company_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_atomic_company_audit();")
        try:
            self.new_company_item([self.selection(self.a), self.selection(self.b)], expected=500,
                units=[self.ratio(pack)], identifiers=[self.identifier('ATOMIC-AUDIT', uom_id=pack['id'])], physicalData=self.physical())
            self.assertEqual(self.creation_snapshot(), before)
        finally:
            fixture_sql('DROP TRIGGER reject_atomic_company_audit ON foundation.audit_event; DROP FUNCTION foundation.reject_atomic_company_audit()')
        recovered = self.new_company_item([self.selection(self.a), self.selection(self.b)],
            units=[self.ratio(pack)], identifiers=[self.identifier('ATOMIC-AUDIT', uom_id=pack['id'])], physicalData=self.physical())
        self.read_config(self.a, recovered); self.read_config(self.b, recovered)
