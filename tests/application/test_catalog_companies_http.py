"""Accettazione HTTP multi-company con cookie/CSRF e PostgreSQL isolato."""
from concurrent.futures import ThreadPoolExecutor
import uuid
from urllib.parse import urlencode
from test_catalog_items_http import CatalogItemsHttp
from catalog_items_helpers import Client,fixture_sql

HTTP_CASES=(
 'test_opt_in_defaults_copied_once_and_independent_companies',
 'test_all_natures_stock_capabilities_and_no_root_revision',
 'test_allowed_units_fallback_and_reverse_reference_guards',
 'test_global_and_company_lifecycle_effective_flags_preserve_configuration',
 'test_bulk_atomic_create_only_and_scoped_company_route',
 'test_same_role_company_scope_and_revocation_without_master_read',
 'test_cross_tenant_company_item_units_and_generic_bypass',
 'test_concurrent_enabling_and_stale_update',
 'test_audit_failure_rolls_back_single_and_bulk',
 'test_csrf_origin_readonly_fields_and_bounded_bulk_input',
 'test_maximum_revision_refuses_update_without_overflow',
)

class CatalogCompaniesHttp(CatalogItemsHttp):
    def setUp(self):
        super().setUp()
        self.a=self.data_create('companies',{'name':'Synthetic Company A','is_enabled':True})
        self.b=self.data_create('companies',{'name':'Synthetic Company B','is_enabled':True})
    def company_path(self,company,item=None,**query):
        return '/api/companies/'+company['id']+'/catalog/items'+('/'+item['id'] if item else '')+'?'+urlencode({'tenantId':self.tenant_id,**query})
    def config(self,company,item,values=None,version=0,method='PUT',expected=200,client=None):
        status,body=(client or self.root).request(self.company_path(company,item),method,{'values':values or {},'expectedVersion':version})
        self.assertIn(status,(200,201) if expected==200 else (expected,),body)
        return body
    def read_config(self,company,item,client=None,expected=200):
        status,body=(client or self.root).request(self.company_path(company,item));self.assertEqual(status,expected,body);return body
    def list_configs(self,company=None,client=None,**query):
        path=self.company_path(company,**query) if company else self.path('item-companies',**query)
        status,body=(client or self.root).request(path);self.assertEqual(status,200,body);return body
    def bulk(self,items,companies,expected=200):
        status,body=self.root.request(self.path('item-companies','bulk-enable'),'POST',{'itemIds':[x['id'] for x in items],'companyIds':[x['id'] for x in companies]})
        self.assertEqual(status,expected,body);return body
    def scoped_actor(self,grants,companies):
        actor,role,credentials=self.actor(grants)
        status,body=self.root.request('/api/roles/'+role['id']+'/companies?tenantId='+self.tenant_id,'PUT',{'companyIds':[x['id'] for x in companies]})
        self.assertEqual(status,200,body);return actor,role,credentials
    def test_opt_in_defaults_copied_once_and_independent_companies(self):
        type_row=self.create('types',{'name':'Company defaults','kind':'GOOD','default_sellable':True,'default_purchasable':False,'default_track_stock':True})
        item=self.item(item_type_id=type_row['id']);self.assertEqual(self.list_configs()['total'],0)
        self.read_config(self.a,item,expected=404)
        a=self.config(self.a,item);self.assertTrue(a['is_enabled']);self.assertTrue(a['is_sellable']);self.assertFalse(a['is_purchasable']);self.assertTrue(a['track_stock'])
        self.assertIsNone(a['default_sales_uom_id']);self.assertEqual(a['effective_sales_uom_id'],item['base_uom_id'])
        b=self.config(self.b,item,{'is_sellable':False,'is_purchasable':True,'track_stock':False})
        self.assertEqual(self.req('items',item['id']),item)
        self.update('types',type_row,{'default_sellable':False,'default_purchasable':True,'default_track_stock':False})
        self.assertEqual(self.read_config(self.a,item),a);self.assertEqual(self.read_config(self.b,item),b)
        updated=self.config(self.a,item,{'is_sellable':False},a['version'],'PATCH')
        self.assertFalse(updated['is_sellable']);self.assertEqual(self.read_config(self.b,item),b)
        same=self.config(self.a,item,{'is_sellable':False},updated['version']);self.assertEqual(same,updated)
        self.assertEqual(self.list_configs()['total'],2)
        self.assertEqual(self.req('items')['total'],1)
    def test_all_natures_stock_capabilities_and_no_root_revision(self):
        for kind in ('GOOD','INTANGIBLE','SERVICE','CHARGE'):
            ty=self.create('types',{'name':'Company '+kind,'kind':kind,'default_sellable':True,'default_purchasable':True,'default_track_stock':kind=='GOOD'})
            item=self.item(item_type_id=ty['id']);row=self.config(self.a,item)
            self.assertTrue(row['canSell']);self.assertTrue(row['canPurchase']);self.assertEqual(row['canTrackStock'],kind=='GOOD')
            if kind!='GOOD':
                self.config(self.a,item,{'track_stock':True},row['version'],'PATCH',400)
                self.assertEqual(self.read_config(self.a,item),row)
            self.assertEqual(self.req('items',item['id']),item)
    def test_allowed_units_fallback_and_reverse_reference_guards(self):
        item=self.item();pack=self.pack();item=self.child(item,'units',self.ratio(pack))
        row=self.config(self.a,item,{'default_purchase_uom_id':pack['id']})
        self.assertEqual(row['effective_sales_uom_id'],self.base['id']);self.assertEqual(row['effective_purchase_uom_id'],pack['id'])
        kg=next(unit for unit in self.refs['units'] if unit['code']=='KG')
        self.config(self.a,item,{'default_sales_uom_id':kg['id']},row['version'],'PATCH',400)
        same_dimension=self.create('units',{'name':'Not admitted count unit','code':'CNT'+uuid.uuid4().hex[:5],'dimension':'COUNT','conversion_scope':'UNIVERSAL','factor_to_base':'2','is_base':False,'decimal_places':0,'is_active':True})
        self.config(self.a,item,{'default_sales_uom_id':same_dimension['id']},row['version'],'PATCH',400)
        self.assertEqual(self.read_config(self.a,item),row)
        blocked=self.req('units',pack['id'],'PUT',{'values':{'is_active':False},'expectedVersion':pack['version']},expected=(400,409))
        self.assertEqual(blocked['code'],'company_default_unit_in_use')
        alternate=item['units'][0]
        blocked=self.req('items',item['id']+'/units/'+alternate['id'],'DELETE',expected=(400,409),expectedVersion=item['version'])
        self.assertEqual(blocked['code'],'company_default_unit_in_use')
        self.assertEqual(self.read_config(self.a,item),row)
        row=self.config(self.a,item,{'default_purchase_uom_id':None},row['version'],'PATCH')
        self.assertEqual(row['effective_purchase_uom_id'],item['base_uom_id'])
        self.child(item,'units',ident=alternate['id'],method='DELETE')
    def test_global_and_company_lifecycle_effective_flags_preserve_configuration(self):
        item=self.item();row=self.config(self.a,item)
        item=self.status(item,'SUSPENDED');suspended=self.read_config(self.a,item)
        self.assertFalse(suspended['canSell']);self.assertFalse(suspended['canPurchase']);self.assertFalse(suspended['canTrackStock']);self.assertTrue(suspended['is_enabled']);self.assertEqual(suspended['version'],row['version'])
        item=self.status(item,'ACTIVE');self.assertTrue(self.read_config(self.a,item)['canSell'])
        self.assertEqual(self.root.request('/api/data/companies/'+self.a['id']+'?tenantId='+self.tenant_id,'PUT',{'name':self.a['name'],'is_enabled':False})[0],200)
        disabled=self.read_config(self.a,item);self.assertFalse(disabled['canSell']);self.assertEqual(disabled['version'],row['version'])
        disabled=self.config(self.a,item,{'is_enabled':False},row['version'],'PATCH');self.assertFalse(disabled['is_enabled'])
        self.config(self.a,item,{'is_enabled':True},disabled['version'],'PATCH',409)
        b=self.config(self.b,item);item=self.status(item,'ARCHIVED');archived=self.read_config(self.b,item)
        self.assertFalse(archived['canSell']);self.assertTrue(archived['is_sellable']);self.assertFalse(archived['is_enabled']);self.assertEqual(archived['version'],b['version']+1)
        self.config(self.b,item,{'is_sellable':False},archived['version'],'PATCH',409)
        stopped=self.config(self.b,item,{'is_enabled':False},archived['version'],'PATCH');self.assertEqual(stopped,archived)
    def test_bulk_atomic_create_only_and_scoped_company_route(self):
        x=self.item();y=self.item();a=self.config(self.a,x,{'is_enabled':False,'is_sellable':False})
        result=self.bulk([x,y],[self.a,self.b]);self.assertEqual(result['created'],3);self.assertEqual(result['unchanged'],1)
        self.assertEqual(self.read_config(self.a,x),a)
        again=self.bulk([x,y],[self.a,self.b]);self.assertEqual(again['created'],0);self.assertEqual(again['unchanged'],4)
        self.assertEqual(self.list_configs(self.a)['total'],2)
        self.assertEqual(self.list_configs(self.a,enabled='DISABLED')['total'],1)
        z=self.item();status,body=self.root.request(self.company_path(self.a).split('?')[0]+'/bulk-enable?tenantId='+self.tenant_id,'POST',{'itemIds':[z['id']]});self.assertEqual(status,200,body)
        bad=self.item();bad=self.status(bad,'ARCHIVED');before=self.list_configs()['total']
        self.bulk([z,bad],[self.b],409);self.assertEqual(self.list_configs()['total'],before);self.read_config(self.b,z,expected=404)
    def test_same_role_company_scope_and_revocation_without_master_read(self):
        item=self.item();a=self.config(self.a,item);b=self.config(self.b,item)
        actor,role,_=self.scoped_actor(['catalog-item-companies.read','catalog-item-companies.update'],[self.a])
        self.assertEqual(self.list_configs(client=actor)['total'],1)
        self.assertEqual(actor.request(self.path('items'))[0],403)
        self.assertEqual(actor.request('/api/data/companies?tenantId='+self.tenant_id)[0],403)
        unassociated=self.item()
        self.assertEqual(actor.request(self.path('item-companies','item-options/'+unassociated['id']))[0],404)
        self.assertEqual(actor.request(self.path('item-companies','item-options/'+item['id']))[0],200)
        self.read_config(self.b,item,actor,403)
        self.config(self.b,item,{'is_sellable':False},b['version'],'PATCH',403,actor)
        self.config(self.a,item,{'is_sellable':False},a['version'],'PATCH',client=actor)
        role_b=self.data_create('roles',{'name':'Read B only'})
        user_id=fixture_sql(f"SELECT user_id FROM foundation.user_role WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}'")
        self.root.request('/api/links/role-permissions/'+role_b['id']+'?tenantId='+self.tenant_id,'PUT',{'ids':[self.permission_ids['catalog-item-companies.read']]})
        self.root.request('/api/roles/'+role_b['id']+'/companies?tenantId='+self.tenant_id,'PUT',{'companyIds':[self.b['id']]})
        self.root.request('/api/links/user-roles/'+user_id+'?tenantId='+self.tenant_id,'PUT',{'ids':[role['id'],role_b['id']]})
        self.assertEqual(self.list_configs(client=actor)['total'],2)
        self.config(self.b,item,{'is_sellable':False},b['version'],'PATCH',403,actor)
        self.assertEqual(self.root.request('/api/links/role-permissions/'+role['id']+'?tenantId='+self.tenant_id,'PUT',{'ids':[self.permission_ids['catalog-item-companies.'+action] for action in ('read','create','update')]})[0],204)
        status,body=actor.request(self.path('item-companies','bulk-enable'),'POST',{'itemIds':[unassociated['id']],'companyIds':[self.a['id'],self.b['id']]})
        self.assertEqual(status,403,body);self.read_config(self.a,unassociated,expected=404);self.read_config(self.b,unassociated,expected=404)
        self.root.request('/api/roles/'+role['id']+'/companies?tenantId='+self.tenant_id,'PUT',{'companyIds':[]})
        self.assertEqual(self.list_configs(client=actor)['total'],1)
        self.config(self.a,item,{'is_enabled':False},a['version']+1,'PATCH',403,actor)
    def test_cross_tenant_company_item_units_and_generic_bypass(self):
        item=self.item();other=self.data_create('tenants',{'code':'foreign-'+self.code,'name':'Foreign tenant'},tenant=False)
        status,company=self.root.request('/api/data/companies?tenantId='+other['id'],'POST',{'name':'Foreign company'});self.assertEqual(status,201,company)
        self.config(company,item,expected=404)
        self.assertEqual(self.list_configs()['total'],0)
        self.assertIn(self.root.request('/api/data/catalog-item-companies?tenantId='+self.tenant_id,'POST',{'item_id':item['id'],'company_id':self.a['id']})[0],(403,404))
        row=self.config(self.a,item)
        self.assertEqual(self.root.request(self.company_path(self.a,item),'DELETE')[0],404)
        self.assertEqual(self.read_config(self.a,item),row)
    def test_concurrent_enabling_and_stale_update(self):
        item=self.item()
        def enable(_):
            client=Client();self.assertEqual(client.login(self.credentials)[0],200)
            return client.request(self.company_path(self.a,item),'PUT',{'values':{},'expectedVersion':0})
        with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(enable,range(2)))
        self.assertEqual(sorted(x[0] for x in outcomes),[200,409] if all(x[0]!=201 for x in outcomes) else [201,409])
        row=self.read_config(self.a,item);self.assertEqual(self.list_configs()['total'],1)
        changed=self.config(self.a,item,{'is_sellable':False},row['version'],'PATCH')
        self.config(self.a,item,{'is_purchasable':False},row['version'],'PATCH',409);self.assertEqual(self.read_config(self.a,item),changed)
    def test_audit_failure_rolls_back_single_and_bulk(self):
        x=self.item();y=self.item()
        fixture_sql("CREATE FUNCTION foundation.reject_company_catalog_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='catalog-item-companies' THEN RAISE EXCEPTION 'company catalog audit proof'; END IF; RETURN NEW; END $$;CREATE CONSTRAINT TRIGGER reject_company_catalog_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_company_catalog_audit();")
        try:
            self.config(self.a,x,expected=500);self.assertEqual(self.list_configs()['total'],0)
            self.bulk([x,y],[self.a,self.b],500);self.assertEqual(self.list_configs()['total'],0)
        finally:fixture_sql('DROP TRIGGER reject_company_catalog_audit ON foundation.audit_event;DROP FUNCTION foundation.reject_company_catalog_audit()')
        self.config(self.a,x);self.assertEqual(self.list_configs()['total'],1)

    def test_csrf_origin_readonly_fields_and_bounded_bulk_input(self):
        item=self.item();path=self.company_path(self.a,item);body={'values':{},'expectedVersion':0}
        self.assertEqual(self.root.request(path,'PUT',body,csrf=False)[0],400)
        self.assertEqual(self.root.request(path,'PUT',body,origin='https://foreign.invalid')[0],403)
        self.config(self.a,item,{'canSell':True},expected=400)
        self.config(self.a,item,{'item_id':item['id']},expected=400)
        for payload in ({'itemIds':[],'companyIds':[self.a['id']]},{'itemIds':[item['id'],item['id']],'companyIds':[self.a['id']]},{'itemIds':[item['id']],'companyIds':[self.a['id'],self.a['id']]}):
            status,result=self.root.request(self.path('item-companies','bulk-enable'),'POST',payload);self.assertEqual(status,400,result)
        self.assertEqual(self.list_configs()['total'],0)

    def test_maximum_revision_refuses_update_without_overflow(self):
        item=self.item();row=self.config(self.a,item)
        fixture_sql(f"UPDATE masterdata.catalog_item_company SET version=9007199254740991 WHERE tenant_id='{self.tenant_id}' AND id='{row['id']}'")
        maximum=self.read_config(self.a,item)
        result=self.config(self.a,item,{'is_sellable':not maximum['is_sellable']},maximum['version'],'PATCH',409)
        self.assertEqual(result['code'],'version_exhausted');self.assertEqual(self.read_config(self.a,item),maximum)
