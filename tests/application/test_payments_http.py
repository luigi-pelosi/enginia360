"""Real payment HTTP integration against the isolated BP proof fixture (not TLS)."""
import json, os, unittest, uuid
from test_api import Client

@unittest.skipUnless(os.environ.get('ENGINIA360_PAYMENTS_PROOF')=='1','isolated payments fixture required')
class PaymentsHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=Client()
        status, session=cls.client.login(json.load(open(os.environ['ENGINIA360_TEST_CREDENTIALS'])))
        assert status==200, (status,session)
        if session['mustChangePassword']:
            credentials=json.load(open(os.environ['ENGINIA360_TEST_CREDENTIALS']))
            new=uuid.uuid4().hex+'-Pay!'
            assert cls.client.request('/api/auth/password','PUT',{'currentPassword':credentials['password'],'newPassword':new})[0]==204
            cls.client.token=None
        status,tenant=cls.client.request('/api/data/tenants','POST',{'name':'Payment test','code':str(uuid.uuid4())}); assert status==201,(status,tenant)
        cls.tenant_code=tenant['code']
        cls.suffix='?tenantId='+tenant['id']
        status,company=cls.client.request('/api/data/companies'+cls.suffix,'POST',{'name':'Payment company'}); assert status==201,(status,company)
        cls.base='/api/companies/'+company['id']
    def test_currency_crud_and_disabled_preview(self):
        path='/api/data/currencies'
        body={'name':'Synthetic','code':'ZZZ','numeric_code':'998','minor_units':4,'is_enabled':True}
        status,created=self.client.request(path,'POST',body)
        self.assertEqual(status,201,created)
        ident=created['id']
        status,other=self.client.request('/api/data/tenants','POST',{'name':'Other currency tenant','code':str(uuid.uuid4())})
        self.assertEqual(status,201,other)
        status,other_catalog=self.client.request(path+'?tenantId='+other['id']+'&search=ZZZ')
        self.assertEqual(status,200,other_catalog)
        self.assertTrue(any(item['id']==ident and item['minor_units']==4 for item in other_catalog['items']))
        status,updated=self.client.request(path+'/'+ident,'PUT',{'minor_units':None,'is_enabled':False})
        self.assertEqual(status,200,updated)
        self.assertIsNone(updated['minor_units'])
        status,listed=self.client.request(path+'?search=ZZZ')
        self.assertEqual(status,200,listed)
        self.assertFalse(next(x for x in listed['items'] if x['id']==ident)['is_enabled'])
        row={'sequence':1,'percentage':100,'offsetMonths':0,'offsetDays':0,'dateRule':'EXACT','offsetBase':'REFERENCE_DATE','fixedDay':None,'methodId':None}
        term={'referenceDateType':'DOCUMENT_DATE','isActive':True,'installments':[row]}
        status,_=self.client.request(self.base+'/payment-schedule/preview'+self.suffix,'POST',{'paymentTerm':term,'amountDue':1,'currency':'ZZZ','referenceDate':'2024-01-15'})
        self.assertEqual(status,400)
        self.assertEqual(self.client.request(path+'/'+ident,'DELETE')[0],204)

    def test_currency_catalog_drives_preview(self):
        status, catalog=self.client.request('/api/data/currencies'+self.suffix+'&search=CLF')
        self.assertEqual(status,200,catalog)
        clf=next(item for item in catalog['items'] if item['code']=='CLF')
        self.assertEqual(clf['minor_units'],4)
        row={'sequence':1,'percentage':100,'offsetMonths':0,'offsetDays':0,'dateRule':'EXACT','offsetBase':'REFERENCE_DATE','fixedDay':None,'methodId':None}
        term={'referenceDateType':'DOCUMENT_DATE','isActive':True,'installments':[row]}
        payload={'paymentTerm':term,'amountDue':'1.2345','currency':'CLF','referenceDate':'2024-01-15'}
        status,reply=self.client.request(self.base+'/payment-schedule/preview'+self.suffix,'POST',payload)
        self.assertEqual(status,200,reply)
        self.assertEqual(reply['items'][0]['amount'],1.2345)
        for currency in ('XAU','ZZZ'):
            status,reply=self.client.request(self.base+'/payment-schedule/preview'+self.suffix,'POST',{**payload,'currency':currency})
            self.assertEqual(status,400,reply)

    def test_methods_list_route(self):
        status,body=self.client.request(self.base+'/payment-methods'+self.suffix)
        self.assertEqual(status,200,body)
        self.assertEqual(body['items'],[])

    def test_payment_lifecycle_preview_and_defaults(self):
        def req(path,method='GET',body=None,expected=200):
            status,value=self.client.request(self.base+path+self.suffix,method,body)
            self.assertEqual(status,expected,(path,status,value)); return value
        method={'code':'BANK','name':'Bank','category':'BANK_TRANSFER','direction':'BOTH','requiresBankAccount':True,'isActive':True,'sortOrder':1}
        created=req('/payment-methods','POST',method,201)
        self.assertEqual(len(req('/payment-methods')['items']),1)
        mid=created['id']
        updated=req('/payment-methods/'+mid,'PATCH',{'name':'Updated','expectedVersion':created['version']})
        self.assertEqual(updated['name'],'Updated')
        req('/payment-methods/'+mid,'PATCH',{'name':'Stale','expectedVersion':created['version']},409)
        self.assertEqual(req('/payment-methods')['items'][0]['name'],'Updated')
        row={'sequence':1,'percentage':100,'offsetMonths':1,'offsetDays':0,'dateRule':'END_OF_MONTH','offsetBase':'REFERENCE_DATE','fixedDay':None,'methodId':None}
        term={'code':'NET','name':'Net','defaultMethodId':mid,'referenceDateType':'DOCUMENT_DATE','isActive':True,'installments':[row]}
        saved=req('/payment-terms','POST',term,201); tid=saved['id']
        self.assertEqual(len(req('/payment-terms')['items']),1)
        changed=req('/payment-terms/'+tid,'PUT',{**term,'name':'Net updated','expectedVersion':saved['version']})
        self.assertEqual(changed['name'],'Net updated')
        req('/payment-terms/'+tid,'PUT',{**term,'expectedVersion':saved['version']},409)
        preview=req('/payment-schedule/preview','POST',{'paymentTerm':term,'amountDue':100,'currency':'EUR','referenceDate':'2024-01-15'})
        self.assertEqual(preview['items'][0]['dueDate'],'2024-02-29')
        self.assertEqual(preview['items'][0]['amount'],100)
        settings={'defaultSalesTermId':tid,'defaultPurchaseTermId':None,'defaultSalesMethodId':mid,'defaultPurchaseMethodId':None,'expectedVersion':0}
        self.assertEqual(req('/payment-settings')['version'],0)
        self.assertEqual(req('/payment-settings','PUT',settings)['version'],1)
        req('/payment-settings','PUT',settings,409)
        self.assertEqual(req('/payment-settings')['defaultSalesTermId'],tid)
        status,bp=self.client.request('/api/data/business-partners/save'+self.suffix,'POST',{'values':{'kind':'ORGANIZATION','legal_name':'Payment partner','status':'ACTIVE'}})
        self.assertEqual(status,201,bp)
        path='/business-partners/'+bp['id']
        req('/business-partners','POST',{'businessPartnerId':bp['id'],'roles':['CUSTOMER']},201)
        defaults=path+'/payment-defaults/CUSTOMER'
        self.assertEqual(req(defaults)['version'],0)
        payload={'paymentTermId':tid,'paymentMethodId':mid,'expectedVersion':0}
        self.assertEqual(req(defaults,'PUT',payload)['version'],1)
        req(defaults,'PUT',payload,409)
        self.assertEqual(req(defaults)['paymentTermId'],tid)
        resolved=req(defaults+'/resolve','POST',{'paymentTermId':None,'paymentMethodId':None})
        self.assertEqual(resolved['term']['id'],tid)
        self.assertEqual(resolved['method']['id'],mid)
        outbound=req('/payment-methods','POST',{**method,'code':'OUT','direction':'OUTBOUND'},201)
        for field in ('defaultMethodId','installment'):
            candidate={**term,'expectedVersion':changed['version']}
            if field=='installment': candidate['installments']=[{**row,'methodId':outbound['id']}]
            else: candidate['defaultMethodId']=outbound['id']
            with self.subTest(field=field):
                req('/payment-terms/'+tid,'PUT',candidate,400)
        self.assertEqual(req('/payment-terms')['items'][0]['version'],changed['version'])
        for amount,expected in (('79228162514264337593543950335',200),('79228162514264337593543950336',400)):
            with self.subTest(amount=amount):
                req('/payment-schedule/preview','POST',{'paymentTerm':{**term, 'installments':[{**row,'percentage':50},{**row,'percentage':50,'sequence':2}]},'amountDue':amount,'currency':'EUR','referenceDate':'2024-01-15'},expected)

    def test_y_each_default_direction_and_inactive_references(self):
        for usage,direction in [('sales','OUTBOUND'),('purchase','INBOUND'),('CUSTOMER','OUTBOUND'),('SUPPLIER','INBOUND')]:
            with self.subTest(usage=usage):
                status,company=self.client.request('/api/data/companies'+self.suffix,'POST',{'name':'Direction '+usage})
                self.assertEqual(status,201,company)
                base='/api/companies/'+company['id']
                def req(path,method='GET',body=None,expected=200):
                    status,value=self.client.request(base+path+self.suffix,method,body)
                    self.assertEqual(status,expected,(usage,path,status,value)); return value
                method={'code':'WRONG','name':'Wrong','category':'CASH','direction':direction,'requiresBankAccount':False,'isActive':True,'sortOrder':1}
                wrong=req('/payment-methods','POST',method,201)
                row={'sequence':1,'percentage':100,'offsetMonths':0,'offsetDays':0,'dateRule':'EXACT','offsetBase':'REFERENCE_DATE','fixedDay':None,'methodId':None}
                term={'code':'TERM','name':'Term','defaultMethodId':None,'referenceDateType':'DOCUMENT_DATE','isActive':True,'installments':[row]}
                saved=req('/payment-terms','POST',term,201); tid=saved['id']
                if usage in ('sales','purchase'):
                    settings={'defaultSalesTermId':tid if usage=='sales' else None,'defaultPurchaseTermId':tid if usage=='purchase' else None,'defaultSalesMethodId':None,'defaultPurchaseMethodId':None,'expectedVersion':0}
                    req('/payment-settings','PUT',settings)
                else:
                    status,bp=self.client.request('/api/data/business-partners/save'+self.suffix,'POST',{'values':{'kind':'ORGANIZATION','legal_name':'Partner '+usage,'status':'ACTIVE'}})
                    self.assertEqual(status,201,bp)
                    req('/business-partners','POST',{'businessPartnerId':bp['id'],'roles':[usage]},201)
                    req('/business-partners/'+bp['id']+'/payment-defaults/'+usage,'PUT',{'paymentTermId':tid,'paymentMethodId':None,'expectedVersion':0})
                for field in ('default','installment'):
                    edit={**term,'expectedVersion':saved['version']}
                    if field=='default': edit['defaultMethodId']=wrong['id']
                    else: edit['installments']=[{**row,'methodId':wrong['id']}]
                    req('/payment-terms/'+tid,'PUT',edit,400)
                self.assertEqual(req('/payment-terms')['items'][0]['version'],saved['version'])
                inactive=req('/payment-methods/'+wrong['id'],'PATCH',{'isActive':False,'expectedVersion':wrong['version']})
                req('/payment-terms/'+tid,'PUT',{**term,'defaultMethodId':inactive['id'],'expectedVersion':saved['version']},400)
                req('/payment-terms/'+tid,'PUT',{**term,'name':'Valid','expectedVersion':saved['version']})
                compatible=req('/payment-methods','POST',{**method,'code':'COMPATIBLE','direction':'BOTH'},201)
                historical=req('/payment-terms','POST',{**term,'code':'HISTORICAL','defaultMethodId':compatible['id']},201)
                req('/payment-methods/'+compatible['id'],'PATCH',{'isActive':False,'expectedVersion':compatible['version']})
                req('/payment-terms/'+historical['id'],'PUT',{**term,'code':'HISTORICAL','defaultMethodId':compatible['id'],'expectedVersion':historical['version']},400)
                req('/payment-terms/'+historical['id'],'PUT',{**term,'code':'HISTORICAL','expectedVersion':historical['version']})

    def test_method_direction_preserves_indirect_defaults(self):
        for usage,good,bad in [('sales','INBOUND','OUTBOUND'),('purchase','OUTBOUND','INBOUND'),('CUSTOMER','INBOUND','OUTBOUND'),('SUPPLIER','OUTBOUND','INBOUND')]:
            for reference in ('default','installment'):
                with self.subTest(usage=usage,reference=reference):
                    status,company=self.client.request('/api/data/companies'+self.suffix,'POST',{'name':'Indirect '+usage+' '+reference})
                    self.assertEqual(status,201,company)
                    base='/api/companies/'+company['id']
                    def req(path,method='GET',body=None,expected=200):
                        status,value=self.client.request(base+path+self.suffix,method,body)
                        self.assertEqual(status,expected,(usage,reference,path,status,value)); return value
                    method=req('/payment-methods','POST',{'code':'M','name':'Method','category':'CASH','direction':'BOTH','requiresBankAccount':False,'isActive':True,'sortOrder':1},201)
                    row={'sequence':1,'percentage':100,'offsetMonths':0,'offsetDays':0,'dateRule':'EXACT','offsetBase':'REFERENCE_DATE','fixedDay':None,'methodId':method['id'] if reference=='installment' else None}
                    term=req('/payment-terms','POST',{'code':'T','name':'Term','defaultMethodId':method['id'] if reference=='default' else None,'referenceDateType':'DOCUMENT_DATE','isActive':True,'installments':[row]},201)
                    if usage in ('sales','purchase'):
                        path='/payment-settings'
                        payload={'defaultSalesTermId':term['id'] if usage=='sales' else None,'defaultPurchaseTermId':term['id'] if usage=='purchase' else None,'defaultSalesMethodId':None,'defaultPurchaseMethodId':None,'expectedVersion':0}
                    else:
                        status,bp=self.client.request('/api/data/business-partners/save'+self.suffix,'POST',{'values':{'kind':'ORGANIZATION','legal_name':'Indirect partner','status':'ACTIVE'}})
                        self.assertEqual(status,201,bp)
                        req('/business-partners','POST',{'businessPartnerId':bp['id'],'roles':[usage]},201)
                        path='/business-partners/'+bp['id']+'/payment-defaults/'+usage
                        payload={'paymentTermId':term['id'],'paymentMethodId':None,'expectedVersion':0}
                    defaults=req(path,'PUT',payload)
                    req('/payment-methods/'+method['id'],'PATCH',{'direction':bad,'expectedVersion':method['version']},400)
                    self.assertEqual(req('/payment-methods')['items'][0],method)
                    self.assertEqual(req('/payment-terms')['items'][0],term)
                    self.assertEqual(req(path),defaults)
                    changed=req('/payment-methods/'+method['id'],'PATCH',{'direction':good,'expectedVersion':method['version']})
                    self.assertEqual(changed['direction'],good)
                    self.assertEqual(changed['version'],method['version']+1)
                    self.assertEqual(req('/payment-terms')['items'][0],term)
                    self.assertEqual(req(path),defaults)

    def test_z_exact_company_authorization_and_revocation(self):
        def create(resource,payload):
            status,value=self.client.request('/api/data/'+resource+self.suffix,'POST',payload)
            self.assertEqual(status,201,value);return value
        username='payment-'+uuid.uuid4().hex[:8]
        user=create('users',{'username':username,'first_name':'Pay','last_name':'Test','email':'pay@example.invalid'})
        role=create('roles',{'name':'Payment reader'})
        catalog=self.client.request('/api/data/permissions'+self.suffix+'&pageSize=100')[1]['items']
        permission=next(x['id'] for x in catalog if x['code']=='payment-methods.read')
        for relation,owner,ids in [('user-roles',user['id'],[role['id']]),('role-permissions',role['id'],[permission])]:
            self.assertEqual(self.client.request('/api/links/'+relation+'/'+owner+self.suffix,'PUT',{'ids':ids})[0],204)
        company=self.base.rsplit('/',1)[1]
        self.assertEqual(self.client.request('/api/roles/'+role['id']+'/companies'+self.suffix,'PUT',{'companyIds':[company]})[0],200)
        initial=uuid.uuid4().hex+'-Initial!'
        self.assertEqual(self.client.request('/api/users/'+user['id']+'/password'+self.suffix,'PUT',{'newPassword':initial})[0],204)
        actor=Client(); self.assertEqual(actor.login({'username':username,'password':initial},self.tenant_code)[0],200)
        self.assertEqual(actor.request('/api/auth/password','PUT',{'currentPassword':initial,'newPassword':uuid.uuid4().hex+'-Changed!'})[0],204)
        actor.token=None
        self.assertEqual(actor.request('/api/data/currencies'+self.suffix)[0],200)
        currencies='/api/data/currencies'
        status,created=self.client.request(currencies,'POST',{'name':'Authorization fixture','code':'ZZZ','numeric_code':'998','minor_units':4,'is_enabled':True})
        self.assertEqual(status,201,created)
        currency_id=created['id']
        try:
            self.assertEqual(actor.request(currencies+self.suffix,'POST',{'name':'Forbidden','code':'ZZY','numeric_code':'997','minor_units':2})[0],403)
            self.assertEqual(actor.request(currencies+'/'+currency_id+self.suffix,'PUT',{'name':'Forbidden update'})[0],403)
            self.assertEqual(actor.request(currencies+'/'+currency_id+self.suffix,'DELETE')[0],403)
            status,visible=actor.request(currencies+self.suffix+'&search=ZZZ')
            self.assertEqual(status,200,visible)
            self.assertTrue(any(item['id']==currency_id and item['name']=='Authorization fixture' for item in visible['items']))
        finally:
            self.assertEqual(self.client.request(currencies+'/'+currency_id,'DELETE')[0],204)
        path=self.base+'/payment-methods'+self.suffix
        self.assertEqual(actor.request(path)[0],200)
        self.assertEqual(actor.request(path,'POST',{})[0],403)
        self.assertEqual(actor.request(self.base+'/payment-terms'+self.suffix)[0],403)
        status,companies=actor.request('/api/payment-companies'+self.suffix)
        self.assertEqual(status,200)
        self.assertEqual(companies['items'][0]['code'],None)
        self.assertEqual(companies['items'][0]['permissions'],['payment-methods.read'])
        self.assertEqual(self.client.request('/api/roles/'+role['id']+'/companies'+self.suffix,'PUT',{'companyIds':[]})[0],200)
        self.assertEqual(actor.request(path)[0],403)

    def test_anonymous_and_csrf_denied(self):
        path=self.base+'/payment-methods'+self.suffix
        self.assertEqual(Client().request(path)[0],401)
        self.assertIn(self.client.request(path,'POST',{},csrf=False)[0],(400,403))
        self.assertEqual(self.client.request(path,'POST',{},origin='https://foreign.invalid')[0],403)
