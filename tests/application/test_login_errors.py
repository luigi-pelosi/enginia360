"""Errori di login contestuali senza distinguere utente inesistente e password errata."""
import secrets
import unittest
from unified_save_support import Case,Client,root_client,sql


class LoginErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()
    def setUp(self):
        sql('DELETE FROM foundation.login_limit;');self.case=Case(self.root)
    def tearDown(self):self.case.close()

    def test_invalid_or_inactive_organization_points_to_the_organization_code(self):
        status,error=Client().login(self.credentials,'unknown-organization');self.assertEqual(status,401);self.assertEqual(error['code'],'invalid_organization_code')
        self.assertEqual(self.root.request('/api/data/tenants/'+self.case.tenant['id'],'PUT',{'is_enabled':False})[0],200)
        status,error=Client().login(self.credentials,self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'invalid_organization_code')

    def test_other_failures_do_not_falsely_blame_only_username_or_password(self):
        _,user,_,credentials=self.case.actor([])
        for data,code in [({**credentials,'password':secrets.token_urlsafe(28)},self.case.tenant['code']),({'username':'unknown-qa-user','password':secrets.token_urlsafe(28)},self.case.tenant['code']),(credentials,None)]:
            status,error=Client().login(data,code);self.assertEqual(status,401);self.assertEqual(error['code'],'login_details_invalid')

    def test_account_status_is_only_disclosed_after_correct_password_verification(self):
        _,user,_,credentials=self.case.actor([])
        self.assertEqual(self.root.request(self.case.path('users',user['id']),'PUT',{'is_enabled':False})[0],200)
        status,error=Client().login(credentials,self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'account_disabled')
        status,error=Client().login({**credentials,'password':secrets.token_urlsafe(28)},self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'login_details_invalid')
        self.assertEqual(self.root.request(self.case.path('users',user['id']),'PUT',{'is_enabled':True})[0],200)
        sql(f"UPDATE foundation.\"user\" SET locked_until=now()+interval '15 minutes' WHERE id='{user['id']}';")
        status,error=Client().login(credentials,self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'account_temporarily_locked')
        status,error=Client().login({**credentials,'password':secrets.token_urlsafe(28)},self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'login_details_invalid')

if __name__=='__main__':unittest.main(verbosity=2)
