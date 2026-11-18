"""Organizzazioni commerciali: API con cookie e CSRF, esclusivamente nel clone."""
import os
os.environ['ENGINIA360_VALIDATION_DIR']='/root/.config/enginia360/commercial-organizations'
os.environ['ENGINIA360_VALIDATION_DB_CONTAINER']='enginia360-commercial-organizations-db'
import concurrent.futures
import json
import subprocess
import time
import unittest
import uuid
from unified_save_support import Case, Client, root_client, sql


def canonical(entries):
    return sorted([{**entry,'siteIds':sorted(entry['siteIds'])} for entry in entries],key=lambda entry:entry['companyId'])


class CommercialOrganizationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()

    def setUp(self):
        self.case=Case(self.root)
        self.a=self.case.create('companies',{'name':'Azienda Alfa'})
        self.b=self.case.create('companies',{'name':'Azienda Beta'})
        self.a1=self.case.create('sites',{'company_id':self.a['id'],'name':'Sede Alfa Uno'})
        self.a2=self.case.create('sites',{'company_id':self.a['id'],'name':'Sede Alfa Due'})
        self.b1=self.case.create('sites',{'company_id':self.b['id'],'name':'Sede Beta Uno'})

    def tearDown(self):self.case.close()

    def coverage(self,org):
        status,data=self.root.request(self.case.path('purchasing-organizations',org['id']+'/coverage'))
        self.assertEqual(status,200)
        return canonical(data['coverage'])

    def full_scope(self):
        return [{'companyId':self.a['id'],'siteScope':'all_sites','siteIds':[]},
                {'companyId':self.b['id'],'siteScope':'selected_sites','siteIds':[self.b1['id']]}]

    def create_purchasing(self,coverage=None):
        body={'values':{'name':'Acquisti di gruppo'}}
        if coverage is not None:body['coverage']=coverage
        status,org=self.root.request(self.case.path('purchasing-organizations',save=True),'POST',body)
        self.assertEqual(status,201,'La nuova anagrafica acquisti deve supportare il salvataggio composito')
        return org

    def audit_count(self):
        return int(sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.case.tenant['id']}'").stdout)

    def test_sales_crud_requires_company_and_keeps_code_optional(self):
        path=self.case.path('sales-organizations',save=True)
        status,org=self.root.request(path,'POST',{'values':{'company_id':self.a['id'],'name':'Vendita Alfa'}})
        self.assertEqual(status,201,'Organizzazione vendita mancante nel CRUD')
        self.assertIsNone(org['code']);self.assertEqual(org['company_id'],self.a['id'])
        self.assertEqual(self.root.request(path,'POST',{'values':{'name':'Senza azienda'}})[0],400)
        status,updated=self.root.request(self.case.path('sales-organizations',org['id'],save=True),'PUT',{'values':{'description':'Nuova descrizione'}})
        self.assertEqual(status,200);self.assertEqual(updated['description'],'Nuova descrizione')
        self.assertEqual(self.root.request(self.case.path('sales-organizations',org['id']),'DELETE')[0],204)

    def test_purchasing_create_profile_and_both_company_scopes_commit_together(self):
        scope=self.full_scope();org=self.create_purchasing(scope)
        self.assertIsNone(org['code']);self.assertNotIn('company_id',org)
        self.assertEqual(self.coverage(org),canonical(scope))
        xmins=json.loads(sql(f"SELECT json_agg(x) FROM (SELECT xmin::text x FROM foundation.purchasing_organization WHERE id='{org['id']}' UNION ALL SELECT xmin::text FROM foundation.purchasing_organization_company WHERE purchasing_organization_id='{org['id']}' UNION ALL SELECT xmin::text FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{org['id']}' UNION ALL SELECT xmin::text FROM foundation.audit_event WHERE record_id='{org['id']}') q").stdout)
        self.assertEqual(len(set(xmins)),1,'Anagrafica, copertura e audit devono appartenere a un solo commit')

    def test_unassigned_then_coverage_only_and_explicit_clear(self):
        org=self.create_purchasing();self.assertEqual(self.coverage(org),[])
        assigner,_,_,_=self.case.actor(['purchasing-organizations.assign_scope'])
        status,result=assigner.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'coverage':self.full_scope()})
        self.assertEqual(status,200);self.assertEqual(result,{'id':org['id']})
        self.assertEqual(self.coverage(org),canonical(self.full_scope()))
        status,result=assigner.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'coverage':[]})
        self.assertEqual(status,200);self.assertEqual(result,{'id':org['id']});self.assertEqual(self.coverage(org),[])
        self.assertEqual(assigner.request(self.case.path('purchasing-organizations',org['id']+'/coverage'))[0],403)

    def test_all_requested_authorities_gate_before_changes_and_no_implicit_user_grants(self):
        org=self.create_purchasing(self.full_scope())
        editor,_,_,_=self.case.actor(['purchasing-organizations.update'])
        before=self.audit_count()
        status,_=editor.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{
            'values':{'name':'Non consentito'},'coverage':[]})
        self.assertEqual(status,403);self.assertEqual(self.audit_count(),before)
        self.assertEqual(self.coverage(org),canonical(self.full_scope()))
        row=json.loads(sql(f"SELECT row_to_json(t) FROM foundation.purchasing_organization t WHERE id='{org['id']}'").stdout)
        self.assertEqual(row['name'],'Acquisti di gruppo')
        assigner,_,_,_=self.case.actor(['purchasing-organizations.assign_scope'])
        self.assertEqual(assigner.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'values':{'name':'Negato'},'coverage':[]})[0],403)
        actor,_,_,_=self.case.actor([])
        self.assertEqual(actor.request('/api/session')[1]['permissions'],[])
        self.assertEqual(actor.request(self.case.path('purchasing-organizations'))[0],403)

    def test_invalid_scope_rolls_back_name_and_preserves_original_assignments(self):
        org=self.create_purchasing(self.full_scope());before=self.audit_count()
        invalid=[None,[{'companyId':self.a['id'],'siteScope':'selected_sites','siteIds':[]}],
            [{'companyId':self.a['id'],'siteScope':'all_sites','siteIds':[self.a1['id']]}],
            [{'companyId':self.a['id'],'siteScope':'selected_sites','siteIds':[self.b1['id']]}],
            [{'companyId':self.a['id'],'siteScope':'unknown','siteIds':[]}],
            [self.full_scope()[0],self.full_scope()[0]],
            [{'companyId':str(uuid.uuid4()),'siteScope':'all_sites','siteIds':[]}],
            [{'companyId':self.a['id'],'siteScope':'selected_sites','siteIds':[self.a1['id'],self.a1['id']]}],
            [{'companyId':self.a['id'],'siteScope':'all_sites','siteIds':[],'unknown':True}],
            [{'companyId':str(uuid.UUID(int=0)),'siteScope':'all_sites','siteIds':[]}]]
        for scope in invalid:
            with self.subTest(scope=scope):
                status,_=self.root.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'values':{'name':'Non persistito'},'coverage':scope})
                self.assertEqual(status,400)
        self.assertEqual(self.coverage(org),canonical(self.full_scope()));self.assertEqual(self.audit_count(),before)
        self.assertEqual(sql(f"SELECT name FROM foundation.purchasing_organization WHERE id='{org['id']}'").stdout.strip(),'Acquisti di gruppo')

    def test_cross_tenant_scope_and_wrong_resource_coverage_refused(self):
        foreign=Case(self.root)
        try:
            company=foreign.create('companies',{'name':'Esterna'})
            org=self.create_purchasing()
            self.assertEqual(self.root.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'coverage':[{'companyId':company['id'],'siteScope':'all_sites','siteIds':[]}]})[0],400)
            self.assertEqual(self.root.request(self.case.path('companies',self.a['id'],save=True),'PUT',{'coverage':[]})[0],400)
            actor,_,_,_=self.case.actor(['purchasing-organizations.assign_scope'])
            self.assertEqual(actor.request(foreign.path('purchasing-organizations',org['id'],save=True),'PUT',{'coverage':[]})[0],403)
        finally:foreign.close()

    def test_all_sites_does_not_materialize_current_sites_and_selected_is_explicit(self):
        org=self.create_purchasing(self.full_scope())
        self.case.create('sites',{'company_id':self.a['id'],'name':'Nuova sede Alfa'})
        self.case.create('sites',{'company_id':self.b['id'],'name':'Nuova sede Beta'})
        self.assertEqual(self.coverage(org),canonical(self.full_scope()))
        self.assertEqual(int(sql(f"SELECT count(*) FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{org['id']}'").stdout),1)
        # La funzione applicativa di eleggibilità è esercitata dai self-test backend, non simulata da un endpoint fittizio.

    def test_deferred_audit_failure_rolls_back_profile_coverage_and_response(self):
        org=self.create_purchasing(self.full_scope());before=self.audit_count()
        sql("CREATE FUNCTION foundation.commercial_reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='purchasing-organization-coverage' AND NEW.record_id='{org['id']}'::uuid THEN RAISE EXCEPTION 'Fixture deferred audit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER commercial_reject_commit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.commercial_reject_commit();")
        try:
            status,error=self.root.request(self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'values':{'name':'Rollback'},'coverage':[]})
            self.assertEqual(status,500);self.assertEqual(error,{'code':'server_error'})
            self.assertEqual(self.coverage(org),canonical(self.full_scope()));self.assertEqual(self.audit_count(),before)
            self.assertEqual(sql(f"SELECT name FROM foundation.purchasing_organization WHERE id='{org['id']}'").stdout.strip(),'Acquisti di gruppo')
        finally:sql('DROP TRIGGER commercial_reject_commit ON foundation.audit_event;DROP FUNCTION foundation.commercial_reject_commit();')

    def test_delete_cleans_owned_coverage_but_external_reference_prevents_entire_delete(self):
        org=self.create_purchasing(self.full_scope())
        sql('CREATE TABLE foundation.commercial_delete_guard(id uuid PRIMARY KEY,owner_id uuid REFERENCES foundation.purchasing_organization(id));'+f"INSERT INTO foundation.commercial_delete_guard VALUES(gen_random_uuid(),'{org['id']}');")
        before=self.audit_count()
        try:
            self.assertEqual(self.root.request(self.case.path('purchasing-organizations',org['id']),'DELETE')[0],409)
            self.assertEqual(self.coverage(org),canonical(self.full_scope()));self.assertEqual(self.audit_count(),before)
        finally:sql('DROP TABLE foundation.commercial_delete_guard;')
        deleter,_,_,_=self.case.actor(['purchasing-organizations.delete'])
        self.assertEqual(deleter.request(self.case.path('purchasing-organizations',org['id']),'DELETE')[0],204)
        self.assertEqual(int(sql(f"SELECT count(*) FROM foundation.purchasing_organization_company WHERE purchasing_organization_id='{org['id']}'").stdout),0)

    def test_catalog_seed_finite_fifty_and_csrf_unchanged(self):
        self.assertEqual(len(self.case.catalog),50)
        self.assertIn('purchasing-organizations.assign_scope',self.case.catalog)
        self.assertNotIn('sales-organizations.write',self.case.catalog)
        self.assertEqual(self.root.request(self.case.path('purchasing-organizations',save=True),'POST',{'values':{'name':'Negato'}},csrf=False)[0],400)
        self.assertEqual(self.root.request(self.case.path('purchasing-organizations',save=True),'POST',{'values':{'name':'Negato'}},origin='https://foreign.invalid')[0],403)

    def test_waiting_scope_save_uses_revoked_authority_without_partial_profile_write(self):
        org=self.create_purchasing(self.full_scope())
        actor,_,role,_=self.case.actor(['purchasing-organizations.update','purchasing-organizations.assign_scope'])
        marker='commercial-barrier-'+uuid.uuid4().hex
        process=subprocess.Popen(['docker','exec','-i','enginia360-commercial-organizations-db','psql','-U','postgres','-d','enginia360','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        try:
            process.stdin.write(f"SET application_name='{marker}';BEGIN;SELECT pg_advisory_xact_lock(3607902026);DELETE FROM foundation.role_permission WHERE role_id='{role['id']}' AND permission_id='{self.case.catalog['purchasing-organizations.assign_scope']}';\n");process.stdin.flush()
            for _ in range(100):
                if sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{marker}' AND state='idle in transaction'").stdout.strip()=='1':break
                time.sleep(.03)
            else:self.fail('Barriera non raggiunta')
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(actor.request,self.case.path('purchasing-organizations',org['id'],save=True),'PUT',{'values':{'name':'Non persistito'},'coverage':[]})
                try:
                    for _ in range(100):
                        if sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted").stdout.strip()!='0':break
                        time.sleep(.03)
                    else:self.fail('La richiesta non attende la revoca')
                    self.assertFalse(pending.done())
                finally:process.stdin.write('COMMIT;\n');process.stdin.close()
                self.assertEqual(pending.result(timeout=20)[0],403)
            self.assertEqual(self.coverage(org),canonical(self.full_scope()))
        finally:
            if not process.stdin.closed:process.stdin.close()
            if process.poll() is None:process.wait(timeout=10)
            errors=process.stderr.read();process.stderr.close();self.assertEqual(process.returncode,0,errors)


if __name__=='__main__':unittest.main(verbosity=2)
