"""HTTP autenticato: natura modificabile soltanto senza articoli collegati."""
from test_catalog_items_http import CatalogItemsHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES=('test_unused_types_change_all_natures_without_touching_numbering','test_references_in_every_status_block_nature_but_not_name',
            'test_exact_update_permission_stale_version_and_new_reference','test_kind_update_audit_rollback_and_stock_validation')
KINDS=('GOOD','INTANGIBLE','SERVICE','CHARGE')

class CatalogTypeNatureHttp(CatalogItemsHttp):
    def new_type(self,kind='GOOD',stock=False):return self.create('types',{'name':'Type nature '+kind,'kind':kind,'default_track_stock':stock,'is_active':True})
    def test_unused_types_change_all_natures_without_touching_numbering(self):
        configs={kind:self.req('numbering',kind=kind) for kind in KINDS}
        for old in KINDS:
            for target in KINDS:
                row=self.new_type(old);self.assertTrue(row['canChangeKind'])
                changed=self.update('types',row,{'kind':target})
                self.assertEqual(changed['kind'],target);self.assertTrue(changed['canChangeKind']);self.assertEqual(changed['version'],row['version']+1)
                self.assertEqual(self.req('types',row['id']),changed)
        self.assertEqual({kind:self.req('numbering',kind=kind) for kind in KINDS},configs)

    def test_references_in_every_status_block_nature_but_not_name(self):
        for status in ('ACTIVE','SUSPENDED','ARCHIVED'):
            row=self.new_type();item=self.req('items',method='POST',body={'values':self.values(item_type_id=row['id']),'status':'SUSPENDED' if status=='SUSPENDED' else 'ACTIVE'},expected=201)
            if status=='ARCHIVED':item=self.status(item,'ARCHIVED')
            current=self.req('types',row['id']);self.assertFalse(current['canChangeKind']);self.assertEqual(current['version'],row['version'])
            error=self.update('types',current,{'kind':'CHARGE'},409);self.assertEqual(error['code'],'immutable_item_kind')
            self.assertEqual(self.req('types',row['id']),current);self.full(item)
            changed=self.update('types',current,{'name':'Renamed '+status})
            self.assertEqual(changed['kind'],'GOOD');self.assertFalse(changed['canChangeKind']);self.full(item)

    def test_exact_update_permission_stale_version_and_new_reference(self):
        row=self.new_type();actor,_,_=self.actor(['catalog-types.read','catalog-types.update'])
        self.assertEqual(actor.request(self.path('types',row['id'])),(200,row))
        status,changed=actor.request(self.path('types',row['id']),'PUT',{'values':{'kind':'CHARGE'},'expectedVersion':row['version']})
        self.assertEqual(status,200,changed);self.assertEqual(changed['kind'],'CHARGE')
        self.assertEqual(self.update('types',row,{'kind':'SERVICE'},409)['code'],'stale_version')
        self.assertEqual(actor.request(self.path('types',row['id']+'/deletion-check'))[0],403)
        reader,_,_=self.actor(['catalog-types.read'])
        self.assertTrue(reader.request(self.path('types',row['id']))[1]['canChangeKind'])
        self.assertEqual(reader.request(self.path('types',row['id']),'PUT',{'values':{'kind':'SERVICE'},'expectedVersion':changed['version']})[0],403)
        item=self.item(item_type_id=row['id']);self.assertFalse(self.req('types',row['id'])['canChangeKind'])
        self.assertEqual(self.update('types',changed,{'kind':'SERVICE'},409)['code'],'immutable_item_kind');self.full(item)
        foreign=self.data_create('tenants',{'code':'foreign-'+self.code,'name':'Synthetic foreign tenant'},tenant=False)
        self.req('types',row['id'],tenant=foreign['id'],expected=404)

    def test_kind_update_audit_rollback_and_stock_validation(self):
        row=self.new_type(stock=True)
        self.update('types',row,{'kind':'CHARGE'},400);self.assertEqual(self.req('types',row['id']),row)
        fixture_sql("CREATE FUNCTION foundation.reject_type_nature_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                    f"IF NEW.record_id='{row['id']}'::uuid AND NEW.action='update' THEN RAISE EXCEPTION 'type nature proof'; END IF; RETURN NEW; END $$; "
                    "CREATE CONSTRAINT TRIGGER reject_type_nature_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_type_nature_audit();")
        try:self.update('types',row,{'kind':'CHARGE','default_track_stock':False},500);self.assertEqual(self.req('types',row['id']),row)
        finally:fixture_sql('DROP TRIGGER reject_type_nature_audit ON foundation.audit_event;DROP FUNCTION foundation.reject_type_nature_audit()')
        changed=self.update('types',row,{'kind':'CHARGE','default_track_stock':False});self.assertEqual(changed['kind'],'CHARGE');self.assertFalse(changed['default_track_stock'])
        self.assertEqual(fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE record_id='{row['id']}' AND action='update' AND details->'before'->>'kind'='GOOD' AND details->'after'->>'kind'='CHARGE'"),'1')
