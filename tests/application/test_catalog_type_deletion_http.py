"""Accettazione cookie/CSRF eliminazione tipologie, solo su fixture isolata."""
from test_catalog_items_http import CatalogItemsHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES=('test_unused_all_natures_preflight_delete_and_audit','test_any_article_status_blocks_and_no_side_effects',
            'test_stale_version_concurrent_link_and_tenant_isolation','test_exact_delete_permission_revocation_and_audit_rollback')

class CatalogTypeDeletionHttp(CatalogItemsHttp):
    def new_type(self,kind='GOOD'):
        return self.create('types',{'name':'Disposable '+kind,'kind':kind,'is_active':True,'default_sellable':True,'default_purchasable':True,'default_track_stock':False})
    def check(self,row,expected=200):return self.req('types',row['id']+'/deletion-check',expected=expected)
    def delete(self,row,expected=204):return self.req('types',row['id'],'DELETE',expected=expected,expectedVersion=row['version'])

    def test_unused_all_natures_preflight_delete_and_audit(self):
        for kind in ('GOOD','INTANGIBLE','SERVICE','CHARGE'):
            row=self.new_type(kind)
            audit_before=fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}' AND resource='catalog-types'")
            self.assertEqual(self.check(row),{'canDelete':True})
            self.assertEqual(fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}' AND resource='catalog-types'"),audit_before)
            self.assertEqual(self.req('types',row['id']),row)
            self.delete(row);self.req('types',row['id'],expected=404);self.check(row,404)
            self.assertEqual(fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}' AND resource='catalog-types' AND action='delete' AND record_id='{row['id']}' AND details->'before'->>'name'='Disposable {kind}' AND details->'after'='null'::jsonb"),'1')

    def test_any_article_status_blocks_and_no_side_effects(self):
        for status in ('ACTIVE','SUSPENDED','ARCHIVED'):
            row=self.new_type();item=self.req('items',method='POST',body={'values':self.values(item_type_id=row['id']),'status':'SUSPENDED' if status=='SUSPENDED' else 'ACTIVE'},expected=201)
            if status=='ARCHIVED':item=self.status(item,'ARCHIVED')
            self.assertEqual(self.check(row),{'canDelete':False})
            error=self.delete(row,409);self.assertEqual(error['code'],'item_type_in_use')
            self.assertEqual(self.req('types',row['id']),{**row,'canChangeKind':False});self.full(item)
            self.assertEqual(fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE resource='catalog-types' AND action='delete' AND record_id='{row['id']}'"),'0')

    def test_stale_version_concurrent_link_and_tenant_isolation(self):
        stale=self.new_type();self.assertTrue(self.check(stale)['canDelete'])
        current=self.update('types',stale,{'name':'Changed elsewhere'})
        self.assertEqual(self.delete(stale,409)['code'],'stale_version');self.assertEqual(self.req('types',stale['id']),current)
        row=self.new_type();self.assertTrue(self.check(row)['canDelete'])
        item=self.item(item_type_id=row['id'])
        self.assertEqual(self.delete(row,409)['code'],'item_type_in_use');self.full(item)
        other=self.data_create('tenants',{'code':'foreign-'+self.code,'name':'Other synthetic tenant'},tenant=False)
        self.req('types',row['id']+'/deletion-check',tenant=other['id'],expected=404)
        self.req('types',row['id'],'DELETE',tenant=other['id'],expected=404,expectedVersion=row['version'])
        self.assertEqual(self.req('types',row['id']),{**row,'canChangeKind':False})

    def test_exact_delete_permission_revocation_and_audit_rollback(self):
        row=self.new_type();updater,_,_=self.actor(['catalog-types.read','catalog-types.update'])
        self.assertEqual(updater.request(self.path('types',row['id']+'/deletion-check'))[0],403)
        self.assertEqual(updater.request(self.path('types',row['id'],expectedVersion=row['version']),'DELETE')[0],403)
        deleter,role,user=self.actor(['catalog-types.read','catalog-types.delete'])
        self.assertEqual(deleter.request(self.path('types',row['id']+'/deletion-check')),(200,{'canDelete':True}))
        disposable=self.new_type('INTANGIBLE')
        self.assertEqual(deleter.request(self.path('types',disposable['id'],expectedVersion=disposable['version']),'DELETE')[0],204)
        self.req('types',disposable['id'],expected=404)
        fixture_sql(f"DELETE FROM foundation.role_permission WHERE tenant_id='{self.tenant_id}' AND role_id='{role['id']}' AND permission_id IN (SELECT id FROM foundation.permission WHERE tenant_id='{self.tenant_id}' AND code='catalog-types.delete')")
        self.assertEqual(deleter.request(self.path('types',row['id'],expectedVersion=row['version']),'DELETE')[0],403)
        fixture_sql("CREATE FUNCTION foundation.reject_type_deletion_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                    f"IF NEW.record_id='{row['id']}'::uuid AND NEW.action='delete' THEN RAISE EXCEPTION 'type delete proof'; END IF; RETURN NEW; END $$; "
                    "CREATE CONSTRAINT TRIGGER reject_type_deletion_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_type_deletion_audit();")
        try:self.delete(row,500);self.assertEqual(self.req('types',row['id']),row)
        finally:fixture_sql('DROP TRIGGER reject_type_deletion_audit ON foundation.audit_event;DROP FUNCTION foundation.reject_type_deletion_audit()')
        self.delete(row);self.req('types',row['id'],expected=404)
