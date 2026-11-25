"""Currency revision contract over isolated authenticated HTTP and PostgreSQL."""
import json, os, unittest, uuid
from test_api import Client
import run_business_partner_proof as fixture

@unittest.skipUnless(os.environ.get('ENGINIA360_PAYMENTS_PROOF') == '1', 'isolated fixture required')
class CurrencyVersionHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=Client()
        credentials=json.load(open(os.environ['ENGINIA360_TEST_CREDENTIALS']))
        status,session=cls.client.login(credentials)
        assert status==200
        if session['mustChangePassword']:
            new_password=uuid.uuid4().hex+'-Test!'
            assert cls.client.request('/api/auth/password','PUT',{'currentPassword':credentials['password'],'newPassword':new_password})[0]==204
            cls.client.token=None
            credentials['password']=new_password
        cls.credentials=credentials

    def test_currency_conditional_update_and_audit(self):
        path='/api/data/currencies'
        status,created=self.client.request(path,'POST',{'code':'ZZZ','numeric_code':'998','name':'Proof','minor_units':2})
        self.assertEqual(status,201,created)
        self.assertEqual(created['version'],1)
        ident=created['id']
        status,listed=self.client.request(path+'?search=ZZZ')
        self.assertEqual(next(x for x in listed['items'] if x['id']==ident)['version'],1)
        status,updated=self.client.request(path+'/'+ident,'PUT',{'name':'Winner','expectedVersion':1})
        self.assertEqual(status,200,updated)
        self.assertEqual(updated['version'],2)
        status,conflict=self.client.request(path+'/'+ident+'/save','PUT',{'values':{'name':'Loser'},'expectedVersion':1})
        self.assertEqual(status,409,conflict)
        self.assertEqual(conflict['code'],'version_conflict')
        audit=json.loads(fixture.sql("SELECT json_agg(details ORDER BY created_at) FROM foundation.audit_event WHERE resource='currencies' AND record_id='"+ident+"' AND action='update';").stdout)
        self.assertEqual(len(audit),1)
        self.assertEqual(audit[0]['before']['version'],1)
        self.assertEqual(audit[0]['after']['version'],2)
        status,legacy=self.client.request(path+'/'+ident,'PUT',{'name':'Legacy'})
        self.assertEqual(status,200,legacy)
        self.assertEqual(legacy['version'],3)
        status,conflict=self.client.request(path+'/'+ident,'PUT',{'name':'Stale','expectedVersion':2})
        self.assertEqual(status,409,conflict)

    def test_concurrent_writers_and_validation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        path='/api/data/currencies'
        status,created=self.client.request(path+'/save','POST',{'values':{'code':'ZZY','numeric_code':'991','name':'Race'}})
        self.assertEqual(status,201,created)
        ident=created['id']
        for value in (None,0,-1,1.2,'1',9007199254740992):
            status,result=self.client.request(path+'/'+ident,'PUT',{'name':'Invalid','expectedVersion':value})
            self.assertEqual(status,400,result)
        status,result=self.client.request(path,'POST',{'code':'ZZX','numeric_code':'996','name':'Invalid','expectedVersion':1})
        self.assertEqual(status,400,result)
        clients=[Client(),Client()]
        for client in clients:
            self.assertEqual(client.login(self.credentials)[0],200)
            client.request('/api/auth/csrf')
        barrier=Barrier(2)
        def update(i):
            barrier.wait()
            return clients[i].request(path+'/'+ident+'/save','PUT',{'values':{'name':'Writer '+str(i)},'expectedVersion':1})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(update,range(2)))
        self.assertEqual(sorted(x[0] for x in results),[200,409],results)
        self.assertEqual(next(x[1]['version'] for x in results if x[0]==200),2)
        self.assertEqual(fixture.sql("SELECT count(*) FROM foundation.audit_event WHERE resource='currencies' AND action='update' AND record_id='"+ident+"';").stdout.strip(),'1')
        status,company=self.client.request('/api/data/tenants','POST',{'name':'Other resource','code':str(uuid.uuid4())})
        self.assertEqual(status,201,company)
        status,company=self.client.request('/api/data/tenants/'+company['id'],'PUT',{'name':'Still works'})
        self.assertEqual(status,200,company)
        self.assertNotIn('version',company)
