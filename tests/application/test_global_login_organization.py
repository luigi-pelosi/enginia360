"""Login reale del Super Admin globale con contesto distinto dall'identità."""
import secrets
import unittest
from unified_save_support import Case, Client, root_client, sql


class GlobalOrganizationLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()
    def setUp(self):
        sql('DELETE FROM foundation.login_limit;')
        self.case=Case(self.root)
    def tearDown(self):self.case.close()

    def test_global_with_code_keeps_global_identity_and_preselects_organization(self):
        client=Client();status,session=client.login(self.credentials,self.case.tenant['code'])
        self.assertEqual(status,200,session)
        self.assertTrue(session['isSuperAdmin']);self.assertIsNone(session['tenantId']);self.assertEqual(session['selectedTenantId'],self.case.tenant['id'])
        status,restored=client.request('/api/session');self.assertEqual(status,200);self.assertEqual(restored['selectedTenantId'],self.case.tenant['id']);self.assertIsNone(restored['tenantId'])
        other=Case(self.root)
        try:
            row=other.create('companies',{'name':'Altra organizzazione QA'})
            status,rows=client.request(other.path('companies'));self.assertEqual(status,200);self.assertIn(row['id'],[r['id'] for r in rows['items']])
        finally:other.close()

    def test_global_without_code_has_no_selection_and_old_cookie_remains_valid(self):
        client=Client();status,session=client.login(self.credentials)
        self.assertEqual(status,200);self.assertTrue(session['isSuperAdmin']);self.assertIsNone(session['tenantId']);self.assertIsNone(session.get('selectedTenantId'))
        status,session=self.root.request('/api/session');self.assertEqual(status,200);self.assertIsNone(session.get('selectedTenantId'))

    def test_unknown_or_disabled_organization_is_not_silently_ignored(self):
        for code in ('unknown-organization',self.case.tenant['code']):
            if code==self.case.tenant['code']:self.assertEqual(self.root.request('/api/data/tenants/'+self.case.tenant['id'],'PUT',{'is_enabled':False})[0],200)
            status,error=Client().login(self.credentials,code);self.assertEqual(status,401);self.assertEqual(error['code'],'invalid_organization_code')

    def test_ordinary_user_needs_exact_organization_and_never_gets_global_authority(self):
        _,_,_,credentials=self.case.actor([])
        for code in (None,'','unknown-organization'):
            status,error=Client().login(credentials,code);self.assertEqual(status,401);self.assertEqual(error['code'],'invalid_organization_code' if code else 'login_details_invalid')
        status,session=Client().login(credentials,self.case.tenant['code']);self.assertEqual(status,200);self.assertFalse(session['isSuperAdmin']);self.assertEqual(session['tenantId'],self.case.tenant['id']);self.assertIsNone(session.get('selectedTenantId'))

    def test_same_username_uses_verified_credentials_without_shadowing_or_elevation(self):
        _,user,_,credentials=self.case.actor([])
        self.assertEqual(self.root.request(self.case.path('users',user['id']),'PUT',{'username':self.credentials['username']})[0],200);credentials['username']=self.credentials['username']
        status,ordinary=Client().login(credentials,self.case.tenant['code']);self.assertEqual(status,200);self.assertEqual(ordinary['id'],user['id']);self.assertFalse(ordinary['isSuperAdmin'])
        status,global_user=Client().login(self.credentials,self.case.tenant['code']);self.assertEqual(status,200);self.assertEqual(global_user['id'],self.root.request('/api/session')[1]['id']);self.assertTrue(global_user['isSuperAdmin']);self.assertIsNone(global_user['tenantId'])
        status,error=Client().login({**self.credentials,'password':secrets.token_urlsafe(30)},self.case.tenant['code']);self.assertEqual(status,401);self.assertEqual(error['code'],'login_details_invalid')

    def test_global_password_lockout_is_enforced_with_an_organization_code(self):
        import uuid
        id=str(uuid.uuid4());username='global-lock-'+uuid.uuid4().hex
        actor=self.root.request('/api/session')[1]['id']
        sql(f'''INSERT INTO foundation."user"(id,tenant_id,username,first_name,last_name,email,password_hash,security_stamp,is_super_admin,is_enabled,must_change_password)
            SELECT '{id}',NULL,'{username}','QA','Lockout','lockout@example.invalid',password_hash,gen_random_uuid(),true,true,false FROM foundation."user" WHERE id='{actor}';''')
        try:
            for _ in range(5):self.assertEqual(Client().login({'username':username,'password':'incorrect-qa-password'},self.case.tenant['code'])[0],401)
            self.assertEqual(Client().login({'username':username,'password':self.credentials['password']},self.case.tenant['code'])[0],401)
            self.assertEqual(sql(f'''SELECT failed_attempts>=5 AND locked_until>now() FROM foundation."user" WHERE id='{id}';''').stdout.strip(),'t')
        finally:
            sql(f"DELETE FROM foundation.audit_event WHERE actor_id='{id}'; DELETE FROM foundation.\"user\" WHERE id='{id}';")

    def test_selected_organization_revocation_clears_preference_not_global_identity(self):
        client=Client();self.assertEqual(client.login(self.credentials,self.case.tenant['code'])[0],200)
        self.assertEqual(self.root.request('/api/data/tenants/'+self.case.tenant['id'],'PUT',{'is_enabled':False})[0],200)
        status,session=client.request('/api/session');self.assertEqual(status,200);self.assertTrue(session['isSuperAdmin']);self.assertIsNone(session['tenantId']);self.assertIsNone(session.get('selectedTenantId'))

if __name__=='__main__':unittest.main(verbosity=2)
