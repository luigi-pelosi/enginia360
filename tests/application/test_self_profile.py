"""Profilo proprio: diritti intrinseci, campi limitati e salvataggio atomico su copia isolata."""
import json,secrets,unittest
from unified_save_support import Case,Client,root_client,sql


class SelfProfileApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()
    def setUp(self):
        sql('DELETE FROM foundation.login_limit;');self.case=Case(self.root);self.actor,self.user,self.role,self.user_credentials=self.case.actor([])
    def tearDown(self):self.case.close()
    def snapshot(self,id):return sql(f'''SELECT row_to_json(t) FROM foundation."user" t WHERE id='{id}';''').stdout.strip()
    def audit_count(self):return sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.case.tenant['id']}';").stdout.strip()

    def test_own_profile_is_available_without_user_management_permissions(self):
        status,profile=self.actor.request('/api/profile');self.assertEqual(status,200,profile);self.assertEqual(profile['id'],self.user['id'])
        self.assertEqual(set(profile),{'id','username','first_name','last_name','email','date_of_birth','phone_number','preferred_language'})
        self.assertEqual(self.actor.request(self.case.path('users'))[0],403)
        self.assertEqual(Client().request('/api/profile')[0],401)

    def test_global_profile_ignores_selected_tenant_without_enabling_tenant_user_admin_edits(self):
        status,profile=self.root.request('/api/profile');self.assertEqual(status,200);before=self.snapshot(profile['id'])
        status,changed=self.root.request('/api/profile','PUT',{'values':{'first_name':'Profilo globale','last_name':'Verifica','email':'global-profile@example.invalid'}})
        self.assertEqual(status,200);self.assertEqual(changed['first_name'],'Profilo globale');after=json.loads(self.snapshot(profile['id']));old=json.loads(before)
        for key in ('username','tenant_id','is_super_admin','is_enabled','password_hash','security_stamp'):self.assertTrue(after[key]==old[key],key+' invariato')
        session=self.root.request('/api/session')[1];self.assertTrue(session['isSuperAdmin']);self.assertIsNone(session['tenantId']);self.assertEqual(session['displayName'],'Profilo globale Verifica')

    def test_personal_fields_reuse_validation_and_preserve_omitted_fields(self):
        status,p=self.actor.request('/api/profile','PUT',{'values':{'first_name':'  Nome  QA  ','last_name':' Cognome QA ','email':'profile@example.invalid','date_of_birth':'1990-01-02','phone_number':'+39 000','preferred_language':'en'}})
        self.assertEqual(status,200,p);self.assertEqual(p['first_name'],'Nome QA');self.assertEqual(p['date_of_birth'],'1990-01-02');self.assertEqual(p['preferred_language'],'en')
        status,p=self.actor.request('/api/profile','PUT',{'values':{'phone_number':None}});self.assertEqual(status,200);self.assertIsNone(p['phone_number']);self.assertEqual(p['email'],'profile@example.invalid')
        before=self.snapshot(self.user['id'])
        for values in ({'first_name':'   '},{'email':'bad'},{'date_of_birth':'2999-01-01'},{'preferred_language':'zz'}):
            self.assertEqual(self.actor.request('/api/profile','PUT',{'values':values})[0],400)
            self.assertTrue(self.snapshot(self.user['id'])==before,'Dati invariati su input invalido')

    def test_no_self_escalation_or_foreign_record_selection(self):
        before=self.snapshot(self.user['id'])
        for key,value in [('id',self.root.request('/api/session')[1]['id']),('username','renamed'),('tenant_id',self.case.tenant['id']),('is_enabled',False),('is_super_admin',True),('password_hash','x'),('security_stamp','x'),('roles',[])]:
            self.assertEqual(self.actor.request('/api/profile','PUT',{'values':{key:value}})[0],400)
            self.assertTrue(self.snapshot(self.user['id'])==before,'Nessuna scrittura fuori whitelist')
        self.assertEqual(self.actor.request('/api/profile/'+self.root.request('/api/session')[1]['id'],'PUT',{'values':{'first_name':'No'}})[0],404)
        status,p=self.actor.request('/api/profile?tenantId='+self.case.tenant['id']);self.assertEqual(status,200);self.assertEqual(p['id'],self.user['id'])

    def test_wrong_password_or_invalid_new_password_rolls_back_profile_and_audit(self):
        before=self.snapshot(self.user['id']);audit=self.audit_count()
        for body in ({'values':{'first_name':'Non salvare'},'currentPassword':'wrong','newPassword':secrets.token_urlsafe(28)},{'values':{'first_name':'Non salvare'},'currentPassword':self.user_credentials['password'],'newPassword':'short'}):
            status,error=self.actor.request('/api/profile','PUT',body);self.assertEqual(status,400)
            if body['currentPassword']=='wrong':self.assertEqual(error['code'],'current_password_invalid')
            self.assertTrue(self.snapshot(self.user['id'])==before,'Profilo/hash invariati');self.assertEqual(self.audit_count(),audit)

    def test_combined_profile_and_password_save_keeps_current_session_revokes_old_and_hides_secrets(self):
        old=Client();self.assertEqual(old.login(self.user_credentials,self.case.tenant['code'])[0],200)
        password=secrets.token_urlsafe(30);before=json.loads(self.snapshot(self.user['id']))
        status,p=self.actor.request('/api/profile','PUT',{'values':{'first_name':'Nome aggiornato'},'currentPassword':self.user_credentials['password'],'newPassword':password})
        self.assertEqual(status,200,p);self.assertEqual(p['first_name'],'Nome aggiornato');self.assertNotIn(password,json.dumps(p))
        after=json.loads(self.snapshot(self.user['id']));self.assertTrue(after['password_hash']!=before['password_hash']);self.assertTrue(after['security_stamp']!=before['security_stamp'])
        self.assertEqual(self.actor.request('/api/session')[0],200);self.assertEqual(old.request('/api/session')[0],401)
        client=Client();self.assertEqual(client.login({**self.user_credentials,'password':password},self.case.tenant['code'])[0],200)
        audits=sql(f"SELECT coalesce(json_agg(details),'[]') FROM foundation.audit_event WHERE tenant_id='{self.case.tenant['id']}';").stdout
        self.assertNotIn(password,audits);self.assertNotIn(self.user_credentials['password'],audits);self.assertNotIn('password_hash',audits)

    def test_profile_writes_require_csrf_and_canonical_origin(self):
        before=self.snapshot(self.user['id']);body={'values':{'first_name':'Non salvare'}}
        self.assertEqual(self.actor.request('/api/profile','PUT',body,csrf=False)[0],400)
        self.assertEqual(self.actor.request('/api/profile','PUT',body,origin='https://untrusted.example.invalid')[0],403)
        self.assertTrue(self.snapshot(self.user['id'])==before,'Nessuna modifica senza protezioni richieste')

    def test_disabled_identity_cannot_use_intrinsic_profile_right(self):
        self.assertEqual(self.root.request(self.case.path('users',self.user['id']),'PUT',{'is_enabled':False})[0],200)
        before=self.snapshot(self.user['id'])
        self.assertEqual(self.actor.request('/api/profile')[0],401)
        self.assertEqual(self.actor.request('/api/profile','PUT',{'values':{'first_name':'Non salvare'}})[0],401)
        self.assertTrue(self.snapshot(self.user['id'])==before,'Identità disabilitata sempre rifiutata')

    def test_existing_whitespace_password_can_still_pass_mandatory_change(self):
        legacy=' '*14
        self.assertEqual(self.root.request('/api/users/'+self.user['id']+'/password?tenantId='+self.case.tenant['id'],'PUT',{'newPassword':legacy})[0],204)
        client=Client();status,session=client.login({**self.user_credentials,'password':legacy},self.case.tenant['code']);self.assertEqual(status,200);self.assertTrue(session['mustChangePassword'])
        self.assertEqual(client.request('/api/auth/password','PUT',{'currentPassword':legacy,'newPassword':secrets.token_urlsafe(30)})[0],204,'La password attuale esistente non deve essere reinterpretata')

    def test_deferred_audit_failure_rolls_back_combined_save_and_cookie(self):
        before=self.snapshot(self.user['id']);audit=self.audit_count();uid=self.user['id']
        sql(f"""CREATE FUNCTION foundation.qa_profile_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'QA deferred failure'; END $$;
        CREATE CONSTRAINT TRIGGER qa_profile_audit_failure AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.record_id='{uid}'::uuid) EXECUTE FUNCTION foundation.qa_profile_audit_failure();""")
        try:
            status,_=self.actor.request('/api/profile','PUT',{'values':{'first_name':'Non salvare'},'currentPassword':self.user_credentials['password'],'newPassword':secrets.token_urlsafe(30)})
            self.assertGreaterEqual(status,400);self.assertTrue(self.snapshot(uid)==before,'Rollback profilopassword al commit');self.assertEqual(self.audit_count(),audit)
            self.assertEqual(self.actor.request('/api/session')[0],200,'Cookie precedente ancora valido dopo rollback')
        finally:sql('DROP TRIGGER qa_profile_audit_failure ON foundation.audit_event; DROP FUNCTION foundation.qa_profile_audit_failure();')

    def test_password_payload_requires_both_fields_and_rejects_same_password(self):
        before=self.snapshot(self.user['id'])
        for body in ({},{'values':{}},{'newPassword':secrets.token_urlsafe(28)},{'currentPassword':self.user_credentials['password']},{'currentPassword':None,'newPassword':secrets.token_urlsafe(28)},{'currentPassword':self.user_credentials['password'],'newPassword':self.user_credentials['password']},{'values':{'first_name':'No'},'unexpected':True}):
            self.assertEqual(self.actor.request('/api/profile','PUT',body)[0],400)
            self.assertTrue(self.snapshot(self.user['id'])==before,'Input rifiutato senza effetti')

if __name__=='__main__':unittest.main(verbosity=2)
