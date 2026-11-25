"""Atomic global archive consequences through real HTTP and isolated PostgreSQL."""
import json
from test_catalog_companies_http import CatalogCompaniesHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES=(
    'test_status_archive_without_company_authority_preserves_configuration',
    'test_general_put_archive_disables_all_and_suspension_is_unchanged',
    'test_archive_maximum_config_version_rolls_back_everything',
    'test_archive_deferred_audit_failure_rolls_back_everything',
)

class CatalogCompanyArchiveHttp(CatalogCompaniesHttp):
    def archive(self,item,inline=False,client=None,expected=200):
        body={'status':'ARCHIVED','expectedVersion':item['version']}
        if inline:body['values']={}
        status,result=(client or self.root).request(self.path('items',item['id']+('' if inline else '/status')),'PUT',body)
        self.assertEqual(status,expected,result)
        return result

    def persisted(self,item):
        return json.loads(fixture_sql(f"SELECT jsonb_build_object('root',(SELECT to_jsonb(i) FROM masterdata.catalog_item i WHERE tenant_id='{self.tenant_id}' AND id='{item['id']}'),'configs',(SELECT jsonb_agg(to_jsonb(c) ORDER BY c.company_id) FROM masterdata.catalog_item_company c WHERE tenant_id='{self.tenant_id}' AND item_id='{item['id']}'),'audits',(SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY a.id),'[]') FROM foundation.audit_event a WHERE tenant_id='{self.tenant_id}'))"))

    def prepared(self):
        status,result=self.root.request('/api/data/companies/'+self.b['id']+'?tenantId='+self.tenant_id,'PUT',{'name':self.b['name'],'is_enabled':True})
        self.assertEqual(status,200,result)
        item=self.item();pack=self.pack();item=self.child(item,'units',self.ratio(pack))
        c=self.data_create('companies',{'name':'Already disabled configuration','is_enabled':True})
        a=self.config(self.a,item,{'is_sellable':False,'is_purchasable':True,'track_stock':False,'default_sales_uom_id':pack['id'],'default_purchase_uom_id':self.base['id']})
        b=self.config(self.b,item,{'is_sellable':True,'is_purchasable':False,'track_stock':True,'default_purchase_uom_id':pack['id']})
        disabled=self.config(c,item,{'is_enabled':False,'is_sellable':False})
        status,result=self.root.request('/api/data/companies/'+self.b['id']+'?tenantId='+self.tenant_id,'PUT',{'name':self.b['name'],'is_enabled':False})
        self.assertEqual(status,200,result)
        return item,[(self.a,a),(self.b,b),(c,disabled)]

    def assert_archived(self,item,configs,before,actor):
        after=self.persisted(item)
        self.assertEqual(after['root']['status'],'ARCHIVED')
        self.assertEqual(after['root']['version'],item['version']+1)
        old={row['id']:row for row in before['configs']}
        new_audits=[row for row in after['audits'] if row['id'] not in {a['id'] for a in before['audits']}]
        for row in after['configs']:
            prior=old[row['id']];changed=prior['is_enabled']
            expected={**prior,'is_enabled':False,'version':prior['version']+int(changed)}
            if changed:expected['updated_at']=row['updated_at']
            self.assertEqual(row,expected)
            events=[a for a in new_audits if a['resource']=='catalog-item-companies' and a['record_id']==row['id']]
            self.assertEqual(len(events),int(changed))
            if changed:
                event=events[0];self.assertEqual(event['actor_id'],actor);self.assertEqual(event['action'],'update')
                self.assertEqual(event['details']['version'],row['version'])
                self.assertTrue(event['details']['before']['is_enabled']);self.assertFalse(event['details']['after']['is_enabled'])
                for key in ('is_sellable','is_purchasable','track_stock','default_sales_uom_id','default_purchase_uom_id'):
                    self.assertEqual(event['details']['before'][key],event['details']['after'][key])
        archives=[a for a in new_audits if a['resource']=='catalog-items' and a['action']=='archive']
        self.assertEqual(len(archives),1);self.assertEqual(archives[0]['actor_id'],actor)
        for company,prior in configs:
            row=self.read_config(company,item);self.assertFalse(row['is_enabled'])
            for flag in ('canSell','canPurchase','canTrackStock'):self.assertFalse(row[flag])
            if prior['is_enabled']:self.config(company,item,{'is_enabled':True},row['version'],'PATCH',409)
            else:self.assertEqual(self.config(company,item,{'is_enabled':False},row['version'],'PATCH'),row)

    def test_status_archive_without_company_authority_preserves_configuration(self):
        item,configs=self.prepared();other=self.item();other_config=self.config(self.a,other)
        actor,role,_=self.scoped_actor(['catalog-items.archive'],[])
        self.assertEqual(actor.request(self.company_path(self.a,item))[0],403)
        actor_id=fixture_sql(f"SELECT user_id FROM foundation.user_role WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}'")
        before=self.persisted(item);self.archive(item,client=actor)
        self.assert_archived(item,configs,before,actor_id)
        self.assertEqual(self.read_config(self.a,other),other_config)

    def test_general_put_archive_disables_all_and_suspension_is_unchanged(self):
        item,configs=self.prepared();before=self.persisted(item)
        item=self.status(item,'SUSPENDED');suspended=self.persisted(item)
        self.assertEqual(suspended['configs'],before['configs'])
        actor,role,_=self.scoped_actor(['catalog-items.update','catalog-items.archive'],[])
        actor_id=fixture_sql(f"SELECT user_id FROM foundation.user_role WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}'")
        self.archive(item,inline=True,client=actor);self.assert_archived(item,configs,suspended,actor_id)

    def test_archive_maximum_config_version_rolls_back_everything(self):
        for inline in (False,True):
            with self.subTest(inline=inline):
                item,configs=self.prepared()
                enabled=sorted((row for _,row in configs if row['is_enabled']),key=lambda row:row['company_id'])
                fixture_sql(f"UPDATE foundation.company SET is_enabled=true WHERE tenant_id='{self.tenant_id}' AND id='{self.b['id']}'; UPDATE masterdata.catalog_item_company SET version=9007199254740991 WHERE tenant_id='{self.tenant_id}' AND id='{enabled[-1]['id']}'; UPDATE foundation.company SET is_enabled=false WHERE tenant_id='{self.tenant_id}' AND id='{self.b['id']}'")
                before=self.persisted(item)
                self.assertEqual(self.archive(item,inline=inline,expected=409)['code'],'version_exhausted')
                self.assertEqual(self.persisted(item),before)

    def test_archive_deferred_audit_failure_rolls_back_everything(self):
        for inline in (False,True):
            with self.subTest(inline=inline):
                item,configs=self.prepared();before=self.persisted(item)
                fixture_sql("CREATE FUNCTION foundation.reject_archive_company_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='catalog-item-companies' AND NEW.action='update' THEN RAISE EXCEPTION 'archive audit rollback proof'; END IF; RETURN NEW; END $$;CREATE CONSTRAINT TRIGGER reject_archive_company_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_archive_company_audit();")
                try:
                    self.archive(item,inline=inline,expected=500)
                    self.assertEqual(self.persisted(item),before)
                finally:fixture_sql('DROP TRIGGER reject_archive_company_audit ON foundation.audit_event;DROP FUNCTION foundation.reject_archive_company_audit()')
