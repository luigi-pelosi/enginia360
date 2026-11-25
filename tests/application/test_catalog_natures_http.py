"""Accettazione cookie/CSRF delle quattro nature, senza copie di API o dati live."""
from test_catalog_items_http import CatalogItemsHttp

KINDS=('GOOD','INTANGIBLE','SERVICE','CHARGE')
PREFIXES={'GOOD':'ART-','INTANGIBLE':'IMM-','SERVICE':'SRV-','CHARGE':'ONR-'}
HTTP_CASES=('test_four_kinds_options_automatic_numbering_and_filters',
            'test_independent_manual_configuration_and_global_reserved_codes',
            'test_only_goods_physical_stock_and_immutable_nature',
            'test_new_natures_required_fields_permissions_and_rollback')

class CatalogNaturesHttp(CatalogItemsHttp):
    def nature_type(self,kind,**extra):
        return self.create('types',{'name':'Synthetic '+kind,'kind':kind,'is_active':True,
                                   'default_sellable':True,'default_purchasable':True,'default_track_stock':False,**extra})

    def test_four_kinds_options_automatic_numbering_and_filters(self):
        before=self.req('numbering',kind='GOOD');service_before=self.req('numbering',kind='SERVICE')
        types={'GOOD':self.good,'SERVICE':self.service,**{k:self.nature_type(k) for k in ('INTANGIBLE','CHARGE')}}
        options=self.req('item-options')
        self.assertEqual(set(options['numbering']),set(KINDS))
        rows={}
        for kind in KINDS:
            config=self.req('numbering',kind=kind)
            self.assertEqual(config['prefix'],PREFIXES[kind]);self.assertEqual(config['nextNumber'],1)
            row=self.item(item_type_id=types[kind]['id']);rows[kind]=row
            self.assertEqual(row['kind'],kind);self.assertEqual(row['code'],PREFIXES[kind]+'000001')
            self.assertEqual(row['status'],'ACTIVE');self.assertIsNotNone(row['activated_at'])
            filtered=self.req('items',kind=kind)
            self.assertEqual(filtered['total'],1);self.assertEqual(filtered['items'][0]['id'],row['id'])
            self.assertEqual(self.req('numbering',kind=kind)['nextNumber'],2)
        self.assertEqual(before['nextNumber'],service_before['nextNumber'])
        self.assertEqual(self.req('numbering',kind='GOOD')['nextNumber'],2)
        self.req('items',kind='GOODS',expected=400);self.req('numbering',kind='GOODS',expected=400)
        self.req('types',method='POST',body={'values':{'name':'Wrong plural','kind':'GOODS','is_active':True}},expected=400)

    def test_independent_manual_configuration_and_global_reserved_codes(self):
        kinds={kind:self.nature_type(kind) for kind in ('INTANGIBLE','CHARGE')}
        good=self.req('numbering',kind='GOOD');service=self.req('numbering',kind='SERVICE')
        for kind in kinds:
            config=self.req('numbering',kind=kind)
            saved=self.req('numbering',method='PUT',kind=kind,body={**config,'mode':'MANUAL','prefix':kind+'-','padding':4,'nextNumber':9})
            self.assertEqual(saved['mode'],'MANUAL')
        row=self.item(item_type_id=kinds['INTANGIBLE']['id'],code='SHAREDRESERVED')
        self.req('items',method='POST',body={'values':self.values(item_type_id=kinds['CHARGE']['id'],code=row['code'])},expected=409)
        charge=self.item(item_type_id=kinds['CHARGE']['id'],code='CHARGEMANUAL')
        self.assertEqual(charge['code'],'CHARGEMANUAL')
        self.assertEqual(self.req('numbering',kind='GOOD'),good);self.assertEqual(self.req('numbering',kind='SERVICE'),service)
        self.assertEqual(self.req('numbering',kind='INTANGIBLE')['nextNumber'],9)
        self.assertEqual(self.req('numbering',kind='CHARGE')['nextNumber'],9)

    def test_only_goods_physical_stock_and_immutable_nature(self):
        for kind in ('INTANGIBLE','SERVICE','CHARGE'):
            kind_type=self.nature_type(kind)
            self.req('types',method='POST',body={'values':{'name':'Forbidden stock '+kind,'kind':kind,'is_active':True,'default_track_stock':True}},expected=400)
            row=self.item(item_type_id=kind_type['id'])
            self.req('items',row['id']+'/physical-data','PUT',{'values':self.physical(),'expectedVersion':row['version']},400)
            self.req('items',row['id'],'PUT',{'values':{'item_type_id':self.good['id']},'expectedVersion':row['version']},409)
            self.update('types',kind_type,{'kind':'GOOD'},expected=409)
            self.assertEqual(self.req('items',row['id']),row)
            self.assertIsNone(row['physicalData'])
            before=self.req('numbering',kind=kind)
            self.req('items',method='POST',body={'values':self.values(item_type_id=kind_type['id']),'physicalData':self.physical()},expected=400)
            self.assertEqual(self.req('numbering',kind=kind),before)
        good=self.item();physical=self.req('items',good['id']+'/physical-data','PUT',{'values':self.physical(),'expectedVersion':good['version']})
        self.assertIsNotNone(physical['physicalData']);self.full(physical)

    def test_new_natures_required_fields_permissions_and_rollback(self):
        reader,_,_=self.actor(['catalog-items.read'])
        for kind in ('INTANGIBLE','CHARGE'):
            kind_type=self.nature_type(kind);config=self.req('numbering',kind=kind)
            values=self.values(item_type_id=kind_type['id'])
            for field in ('name','item_type_id','category_id','base_uom_id'):
                self.req('items',method='POST',body={'values':values|{field:None},'status':'SUSPENDED'},expected=400)
            self.assertEqual(reader.request(self.path('items'),'POST',{'values':values})[0],403)
            self.assertEqual(self.req('numbering',kind=kind),config)
            row=self.req('items',method='POST',body={'values':values,'status':'SUSPENDED'},expected=201)
            row=self.req('items',row['id'],'PUT',{'values':{'name':'Valid '+kind},'status':'ACTIVE','expectedVersion':row['version']})
            self.assertEqual(row['kind'],kind);self.full(row)
