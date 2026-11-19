"""Real Program.cs HTTP/secure-cookie/CSRF proof against phase2 isolated API.
Run only with BP_PHASE2_HTTP_PROOF=1 and the dedicated loopback target from runner.
"""
import http.client
import json
import os
from pathlib import Path
import sys
import unittest
import urllib.request
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/application'))

@unittest.skipUnless(os.environ.get('BP_PHASE2_HTTP_PROOF')=='1','dedicated phase2 HTTP fixture required')
class Phase2HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        port=int(os.environ['BP_PHASE2_HTTP_PORT'])
        os.environ['ENGINIA360_TEST_BASE']='https://phase2-backend.invalid'
        os.environ['ENGINIA360_TEST_ORIGIN']='https://phase2-backend.invalid'
        class LocalTransport(urllib.request.HTTPSHandler):
            def https_open(self,request):
                if request.host!='phase2-backend.invalid':raise RuntimeError('non-fixture destination')
                return self.do_open(lambda host,**kw:http.client.HTTPConnection('127.0.0.1',port,**kw),request)
        original=urllib.request.build_opener
        urllib.request.build_opener=lambda *handlers:original(LocalTransport(),*handlers)
        from test_api import Client
        cls.root=Client();credential_file=Path(os.environ['BP_PHASE2_HTTP_CREDENTIALS'])
        credentials=json.loads(credential_file.read_text());status,session=cls.root.login(credentials)
        if status!=200:raise AssertionError('Isolated bootstrap login failed')
        if session['mustChangePassword']:
            replacement=uuid.uuid4().hex+'-Phase2!'
            status,_=cls.root.request('/api/auth/password','PUT',{'currentPassword':credentials['password'],'newPassword':replacement})
            if status!=204:raise AssertionError('Fixture password change failed')
            credentials['password']=replacement;credential_file.write_text(json.dumps(credentials));cls.root.token=None
    def test_01_patch_requires_csrf_and_canonical_origin_and_preserves_state(self):
        status,t=self.root.request('/api/data/tenants','POST',{'name':'Phase2 HTTP','code':str(uuid.uuid4())});self.assertEqual(status,201)
        suffix='?tenantId='+t['id']
        status,c=self.root.request('/api/data/companies'+suffix,'POST',{'name':'HTTP company'});self.assertEqual(status,201)
        status,b=self.root.request('/api/data/business-partners/save'+suffix,'POST',{'values':{'kind':'ORGANIZATION','legal_name':'HTTP partner','status':'ACTIVE'}});self.assertEqual(status,201)
        root='/api/companies/'+c['id']+'/business-partners'
        status,relation=self.root.request(root+suffix,'POST',{'businessPartnerId':b['id'],'roles':['CUSTOMER']});self.assertEqual(status,201)
        path=root+'/'+b['id']+suffix
        payload={'status':'BLOCKED','expectedVersion':1}
        self.assertIn(self.root.request(path,'PATCH',payload,csrf=False)[0],(400,403),'PATCH bypassed CSRF')
        self.assertEqual(self.root.request(path)[1],relation)
        self.assertEqual(self.root.request(path,'PATCH',payload,origin='https://foreign.invalid')[0],403,'PATCH bypassed origin')
        self.assertEqual(self.root.request(path)[1],relation)
        self.assertEqual(self.root.request(path,'PATCH',payload)[0],200)

if __name__=='__main__':unittest.main(verbosity=2)
