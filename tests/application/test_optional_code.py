"""Codici anagrafici facoltativi: API reali isolate, senza modificare l'accesso tenant."""
import os
os.environ['ENGINIA360_VALIDATION_DIR']='/root/.config/enginia360/optional-code'
os.environ['ENGINIA360_VALIDATION_DB_CONTAINER']='enginia360-optional-code-db'
import unittest
from unified_save_support import Case, root_client

BUSINESS=('companies','sites','warehouse-types','warehouses','warehouse-locations','groups','roles')


def references(case):
    rows={}
    for key in BUSINESS:
        values=body_for(key,rows,'Riferimento '+key)
        values['code']='ref-'+key
        rows[key]=case.create(key,values)
    return rows


def body_for(key,rows,name):
    result={'name':name}
    if key=='sites':result['company_id']=rows['companies']['id']
    if key=='warehouses':result.update(site_id=rows['sites']['id'],warehouse_type_id=rows['warehouse-types']['id'])
    if key=='warehouse-locations':result['warehouse_id']=rows['warehouses']['id']
    return result


class OptionalCodeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()

    def setUp(self):
        self.case=Case(self.root)
        self.refs=references(self.case)

    def tearDown(self):self.case.close()

    def test_create_without_code_through_legacy_and_unified_routes(self):
        for key in BUSINESS:
            for unified in (False,True):
                with self.subTest(resource=key,unified=unified):
                    body=body_for(key,self.refs,'Senza codice '+key)
                    status,row=self.root.request(self.case.path(key,save=unified),'POST',{'values':body} if unified else body)
                    self.assertEqual(status,201,'Il codice deve essere facoltativo anche se omesso')
                    self.assertIsNone(row['code'],'Non generare codici automatici')
                    self.assertTrue(row['id'])

    def test_explicit_null_blank_and_whitespace_are_stored_as_null(self):
        for key in BUSINESS:
            for code in (None,'',' \t\n '):
                with self.subTest(resource=key,code=code):
                    body={**body_for(key,self.refs,'Codice vuoto '+key),'code':code}
                    status,row=self.root.request(self.case.path(key,save=True),'POST',{'values':body})
                    self.assertEqual(status,201)
                    self.assertIsNone(row['code'])

    def test_clear_existing_code_and_keep_it_when_omitted_on_update(self):
        for key,row in self.refs.items():
            with self.subTest(resource=key):
                status,updated=self.root.request(self.case.path(key,row['id'],save=True),'PUT',{'values':{'name':'Aggiornato '+key}})
                self.assertEqual(status,200)
                self.assertEqual(updated['code'],row['code'])
                status,updated=self.root.request(self.case.path(key,row['id']),'PUT',{'code':None})
                self.assertEqual(status,200)
                self.assertIsNone(updated['code'])

    def test_nonempty_codes_are_trimmed_and_uniqueness_is_preserved(self):
        for key in BUSINESS:
            body=body_for(key,self.refs,'Codice valorizzato '+key)
            status,row=self.root.request(self.case.path(key,save=True),'POST',{'values':{**body,'code':' business-'+key+' '}})
            self.assertEqual(status,201)
            self.assertEqual(row['code'],'business-'+key)
            self.assertEqual(self.root.request(self.case.path(key,save=True),'POST',{'values':{**body,'code':'business-'+key}})[0],409)

    def test_metadata_name_precedes_optional_code_with_explicit_technical_exceptions(self):
        status,resources=self.root.request('/api/resources')
        self.assertEqual(status,200)
        for resource in resources:
            fields=resource['fields'];names=[field['name'] for field in fields]
            if 'code' not in names:continue
            self.assertLess(names.index('name'),names.index('code'),'Codice non deve precedere Nome')
            code=next(f for f in fields if f['name']=='code')
            self.assertEqual(code['required'],resource['key'] in ('tenants','permissions'))
        catalog=next(r for r in resources if r['key']=='permissions')
        self.assertTrue(catalog['readOnly'])

    def test_name_and_references_remain_required(self):
        for key in BUSINESS:
            body=body_for(key,self.refs,' ')
            self.assertEqual(self.root.request(self.case.path(key,save=True),'POST',{'values':body})[0],400)
        for key in ('sites','warehouses','warehouse-locations'):
            self.assertEqual(self.root.request(self.case.path(key,save=True),'POST',{'values':{'name':'Senza riferimento'}})[0],400)

    def test_codeless_roles_and_groups_still_grant_and_revoke_exact_permissions(self):
        actor,user,_,_=self.case.actor([])
        status,role=self.root.request(self.case.path('roles',save=True),'POST',{
            'values':{'name':'Ruolo senza codice'},'links':{'role-permissions':[self.case.catalog['companies.read']]}})
        self.assertEqual(status,201);self.assertIsNone(role['code'])
        status,group=self.root.request(self.case.path('groups',save=True),'POST',{
            'values':{'name':'Gruppo senza codice'},'links':{'group-users':[user['id']],'group-roles':[role['id']]}})
        self.assertEqual(status,201);self.assertIsNone(group['code'])
        self.assertEqual(actor.request('/api/session')[1]['permissions'],['companies.read'])
        self.assertEqual(actor.request(self.case.path('companies'))[0],200)
        self.assertEqual(actor.request(self.case.path('companies',save=True),'POST',{'values':{'name':'Non autorizzata'}})[0],403)
        self.assertEqual(self.root.request(self.case.path('groups',group['id'],save=True),'PUT',{'values':{'is_enabled':False}})[0],200)
        self.assertEqual(actor.request('/api/session')[1]['permissions'],[])
        self.assertEqual(actor.request(self.case.path('companies'))[0],403)

    def test_organization_code_remains_required_and_login_still_uses_it(self):
        for code in (None,'',' '):
            self.assertEqual(self.root.request('/api/data/tenants/save','POST',{'values':{'name':'Senza identificativo','code':code}})[0],400)
        self.assertEqual(self.root.request('/api/data/tenants/save','POST',{'values':{'name':'Senza identificativo'}})[0],400)
        actor,_,_,_=self.case.actor(['companies.read'])
        status,session=actor.request('/api/session')
        self.assertEqual(status,200)
        self.assertEqual(session['tenantId'],self.case.tenant['id'])


if __name__=='__main__':unittest.main(verbosity=2)
