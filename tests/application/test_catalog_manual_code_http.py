"""Codici manuali ASCII: accettazione HTTP autenticata su database isolato."""
from test_catalog_items_http import CatalogItemsHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES=(
    'test_manual_code_creation_refuses_invalid_input_without_side_effects',
    'test_manual_code_edit_has_same_validation_and_preserves_reservations',
    'test_manual_limits_do_not_restrict_automatic_or_unchanged_historical_codes',
)
INVALID=('AB CD','AB-CD','AB_CD','AB.CD','AB/CD','èABC','AΩ','ＡBC','A１２',' ABC','ABC ','AB\tCD','ABC\n','A'*41)
class CatalogManualCodeHttp(CatalogItemsHttp):
    def snapshot(self,kind='GOOD'):
        tables=('masterdata.catalog_item','masterdata.catalog_item_code','masterdata.catalog_item_unit','masterdata.catalog_item_identifier','masterdata.catalog_item_physical_data','masterdata.catalog_item_company','foundation.audit_event')
        counts=fixture_sql('SELECT '+','.join(f"(SELECT count(*) FROM {table} WHERE tenant_id='{self.tenant_id}')" for table in tables))
        return self.req('numbering',kind=kind),counts
    def suspended(self,code,**values):
        return self.req('items',method='POST',body={'values':self.values(code=code,**values),'status':'SUSPENDED'},expected=201)
    def invalid(self,code,row=None,status='SUSPENDED',item_type=None):
        body={'values':{'code':code} if row else self.values(code=code,**({'item_type_id':item_type['id']} if item_type else {})),'status':status}
        if row:body['expectedVersion']=row['version']
        result=self.req('items',row['id'] if row else None,'PUT' if row else 'POST',body,400)
        self.assertEqual(result['code'],'catalog_item_manual_code_invalid',result)
        self.assertEqual(result['field'],'code',result)
    def test_manual_code_creation_refuses_invalid_input_without_side_effects(self):
        self.manual();before=self.snapshot()
        for status in ('ACTIVE','SUSPENDED'):
            for code in INVALID:
                with self.subTest(status=status,code=repr(code)):self.invalid(code,status=status)
        self.assertEqual(self.snapshot(),before)
        for kind in ('INTANGIBLE','SERVICE','CHARGE'):
            ty=self.service if kind=='SERVICE' else self.create('types',{'name':'Manual '+kind,'kind':kind})
            self.manual(kind);before=self.snapshot(kind);self.invalid('Invalid-Code',item_type=ty)
            self.assertEqual(self.snapshot(kind),before)
        for code in ('a','9','Az09','Ab09'*10):
            row=self.suspended(code);self.assertEqual(row['code'],code);self.full(row)
    def test_manual_code_edit_has_same_validation_and_preserves_reservations(self):
        self.manual();row=self.suspended('Original01');before=self.snapshot()
        for code in INVALID:
            with self.subTest(code=repr(code)):self.invalid(code,row)
        self.assertEqual(self.snapshot(),before);self.full(row)
        changed=self.update('items',row,{'code':'aB09'*10});self.assertEqual(changed['code'],'aB09'*10)
        self.req('items',method='POST',body={'values':self.values(code='original01')},expected=409)
        self.assertEqual(fixture_sql(f"SELECT count(*) FROM masterdata.catalog_item_code WHERE tenant_id='{self.tenant_id}' AND item_id='{row['id']}'"),'2')
        active=self.status(changed,'ACTIVE');self.update('items',active,{'code':'BAD-CODE'},expected=409);self.full(active)
    def test_manual_limits_do_not_restrict_automatic_or_unchanged_historical_codes(self):
        config=self.req('numbering',kind='SERVICE');prefix='P'*31+'-'
        self.req('numbering',method='PUT',kind='SERVICE',body={**config,'prefix':prefix,'padding':15})
        auto=self.item(item_type_id=self.service['id']);self.assertEqual(auto['code'],prefix+'000000000000001')
        self.assertGreater(len(auto['code']),40);self.full(self.update('items',auto,{'description':'Automatic code preserved'}))
        self.manual();legacy=self.suspended('Seed01')
        # Dato storico sintetico: non è una creazione consentita dalla nuova API.
        fixture_sql(f"UPDATE masterdata.catalog_item SET code='Legacy-01',version=version+1 WHERE tenant_id='{self.tenant_id}' AND id='{legacy['id']}'")
        legacy=self.req('items',legacy['id']);self.assertEqual(legacy['code'],'Legacy-01')
        same=self.update('items',legacy,{'code':'Legacy-01','name':'Historical code retained'});self.assertEqual(same['code'],'Legacy-01');self.full(same)
        self.invalid('Legacy-02',same);valid=self.update('items',same,{'code':'Legacy02'});self.full(valid)
