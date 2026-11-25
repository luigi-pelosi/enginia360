"""Effective capability filtering through real HTTP, scoped authorization and SQL."""
from itertools import product
from test_catalog_companies_http import CatalogCompaniesHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES = (
    'test_effective_capability_compositions_and_lifecycle',
    'test_capability_pagination_search_enabled_and_company_route',
    'test_capability_exact_role_scope_invalid_queries_and_no_writes',
)
FLAGS = ('canSell', 'canPurchase', 'canTrackStock')

class CatalogCompanyCapabilitiesHttp(CatalogCompaniesHttp):
    def snapshot(self):
        return fixture_sql(f"SELECT jsonb_build_object('configs',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM masterdata.catalog_item_company x WHERE tenant_id='{self.tenant_id}'),'audit',(SELECT jsonb_agg(to_jsonb(a) ORDER BY id) FROM foundation.audit_event a WHERE tenant_id='{self.tenant_id}'))")

    def assert_filter(self, baseline, company=None, client=None, **query):
        expected = [r for r in baseline if all(query.get(k, 'ALL') in ('', 'ALL') or r[k] == (query[k] == 'YES') for k in FLAGS)]
        result = self.list_configs(company, client, pageSize=100, **query)
        self.assertEqual(result['total'], len(expected), query)
        self.assertEqual({r['id'] for r in result['items']}, {r['id'] for r in expected}, query)
        return result

    def test_effective_capability_compositions_and_lifecycle(self):
        for sell, purchase, stock in product((False, True), repeat=3):
            self.config(self.a, self.item(), {'is_sellable':sell, 'is_purchasable':purchase, 'track_stock':stock})
        for state in ('SUSPENDED', 'ARCHIVED'):
            item = self.item(); self.config(self.a, item); self.status(item, state)
        self.config(self.a, self.item(), {'is_enabled':False})
        disabled_item = self.item(); self.config(self.b, disabled_item)
        status, body = self.root.request('/api/data/companies/'+self.b['id']+'?tenantId='+self.tenant_id, 'PUT', {'name':self.b['name'], 'is_enabled':False})
        self.assertEqual(status, 200, body)
        for kind in ('INTANGIBLE', 'SERVICE', 'CHARGE'):
            ty = self.create('types', {'name':'Capability '+kind, 'kind':kind, 'default_sellable':True, 'default_purchasable':True, 'default_track_stock':False})
            self.config(self.a, self.item(item_type_id=ty['id']))
        baseline = self.list_configs(pageSize=100)['items']
        for row in baseline:
            active = row['item_status']=='ACTIVE' and row['company_is_enabled'] and row['is_enabled']
            self.assertEqual(row['canSell'], active and row['is_sellable'])
            self.assertEqual(row['canPurchase'], active and row['is_purchasable'])
            self.assertEqual(row['canTrackStock'], active and row['track_stock'] and row['kind']=='GOOD')
        before = self.snapshot()
        for values in product(('ALL', 'YES', 'NO'), repeat=3):
            with self.subTest(values=values):
                self.assert_filter(baseline, **dict(zip(FLAGS, values)))
        self.assert_filter(baseline, **dict.fromkeys(FLAGS, ''))
        self.assertEqual(self.snapshot(), before)

    def test_capability_pagination_search_enabled_and_company_route(self):
        for index in range(6):
            item = self.item(name='Capability needle '+str(index))
            self.config(self.a, item, {'is_sellable':index%2==0, 'is_purchasable':True, 'track_stock':index%3==0})
            self.config(self.b, item, {'is_sellable':False, 'is_enabled':index%2==0})
        self.config(self.a, self.item(name='Other search'), {'is_sellable':True})
        before = self.snapshot()
        for company in (None, self.a, self.b):
            baseline = self.list_configs(company, search='needle', enabled='ENABLED', pageSize=100)['items']
            for flag in FLAGS:
                for value in ('YES', 'NO', 'ALL'):
                    query = {flag:value, 'search':'needle', 'enabled':'ENABLED'}
                    expected = self.assert_filter(baseline, company, **query)
                    collected = []
                    for page in range(1, expected['total']+2):
                        result = self.list_configs(company, page=page, pageSize=1, **query)
                        self.assertEqual(result['total'], expected['total'])
                        self.assertEqual(result['page'], page); self.assertEqual(result['pageSize'], 1)
                        collected.extend(result['items'])
                    self.assertEqual([r['id'] for r in collected], [r['id'] for r in expected['items']])
            self.assert_filter(baseline, company, search='needle', enabled='ENABLED', canSell='YES', canPurchase='YES', canTrackStock='NO')
        self.assertEqual(self.list_configs(kind='GOOD')['total'], 13)
        self.assertEqual(self.snapshot(), before)

    def test_capability_exact_role_scope_invalid_queries_and_no_writes(self):
        item = self.item(); self.config(self.a, item); self.config(self.b, item)
        actor, role, _ = self.scoped_actor(['catalog-item-companies.read'], [self.a])
        # A company scope on a different role cannot expand this read grant.
        extra = self.data_create('roles', {'name':'Scope without company catalog read'})
        user = fixture_sql(f"SELECT user_id FROM foundation.user_role WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}'")
        for path, payload in (
            ('/api/roles/'+extra['id']+'/companies', {'companyIds':[self.b['id']]}),
            ('/api/links/user-roles/'+user, {'ids':[role['id'], extra['id']]}),
        ):
            status, body = self.root.request(path+'?tenantId='+self.tenant_id, 'PUT', payload)
            self.assertIn(status, (200,204), body)
        before = self.snapshot()
        for flag in FLAGS:
            self.assertEqual(self.list_configs(client=actor, **{flag:'YES'})['total'], 1)
            self.assertEqual(self.list_configs(client=actor, **{flag:'NO'})['total'], 0)
            self.assertEqual(actor.request(self.company_path(self.b, **{flag:'YES'}))[0], 403)
            for company in (None, self.a):
                path = self.company_path(company) if company else self.path('item-companies')
                for suffix, code, field in (
                    (flag+'=YES&'+flag+'=NO', 'invalid_query', flag),
                    (flag.lower()+'=YES', 'invalid_query', flag.lower()),
                    (flag+'=yes', 'invalid_capability_filter', flag),
                    (flag+'=TRUE', 'invalid_capability_filter', flag),
                    (flag+'=%20', 'invalid_capability_filter', flag),
                ):
                    with self.subTest(company=company, suffix=suffix):
                        status, body = actor.request(path+'&'+suffix)
                        self.assertEqual(status, 400, body)
                        self.assertEqual(body['code'], code); self.assertEqual(body['field'], field)
        self.assertEqual(actor.request(self.path('items'))[0], 403)
        self.assertEqual(actor.request('/api/data/companies?tenantId='+self.tenant_id)[0], 403)
        self.assertEqual(self.snapshot(), before)
