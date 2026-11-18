"""Integrità organizzazioni commerciali: solo PostgreSQL effimero di questa task."""
import json
import subprocess
import unittest
import uuid

from dbbaseline import CONTAINER, sql, require_isolated
TABLES={'sales_organization','purchasing_organization','purchasing_organization_company','purchasing_organization_site'}


def fixture():
    ids={key:str(uuid.uuid4()) for key in ('tenant','other','a','b','s1','s2','org')}
    q=f"""INSERT INTO foundation.tenant(id,code,name) VALUES('{ids['tenant']}','proof-{ids['tenant']}','Verifica');
    INSERT INTO foundation.tenant(id,code,name) VALUES('{ids['other']}','proof-{ids['other']}','Altro tenant');
    INSERT INTO foundation.company(id,tenant_id,name) VALUES('{ids['a']}','{ids['tenant']}','A'),('{ids['b']}','{ids['tenant']}','B');
    INSERT INTO foundation.site(id,tenant_id,company_id,name,tax_code,address,city,province,postal_code,country_code) VALUES('{ids['s1']}','{ids['tenant']}','{ids['a']}','Sede A','CF','Via prova','Roma','RM','00100','IT'),('{ids['s2']}','{ids['tenant']}','{ids['b']}','Sede B','CF','Via prova','Roma','RM','00100','IT');
    INSERT INTO foundation.purchasing_organization(id,tenant_id,name) VALUES('{ids['org']}','{ids['tenant']}','Acquisti');"""
    return ids,q


class CommercialOrganizationSchemaTests(unittest.TestCase):
    def test_new_tables_exist(self):
        tables=set(json.loads(sql("SELECT json_agg(tablename) FROM pg_tables WHERE schemaname='foundation'").stdout))
        self.assertTrue(TABLES.issubset(tables),'Mancano le nuove identità organizzative e le assegnazioni vincolate')

    def test_catalog_contains_new_actions_without_implicit_grants(self):
        codes=['sales-organizations.'+action for action in ('read','create','update','delete')]
        codes += ['purchasing-organizations.'+action for action in ('read','create','update','delete','assign_scope')]
        literal=','.join("'"+code+"'" for code in codes)
        missing=int(sql("SELECT count(*) FROM foundation.tenant t CROSS JOIN unnest(ARRAY["+literal+"]::text[]) c(code) WHERE NOT EXISTS(SELECT 1 FROM foundation.permission p WHERE p.tenant_id=t.id AND p.code=c.code AND p.is_system)").stdout)
        self.assertEqual(missing,0,'Nuovi permessi applicativi mancanti per i tenant esistenti')
        grants=int(sql('SELECT count(*) FROM foundation.role_permission rp JOIN foundation.permission p ON p.id=rp.permission_id WHERE p.code IN ('+literal+')').stdout)
        self.assertEqual(grants,0)

    def test_selected_and_all_scope_validate_final_transaction_state(self):
        ids,base=fixture()
        statements=base+f"""
        INSERT INTO foundation.purchasing_organization_company VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','selected_sites',now());
        INSERT INTO foundation.purchasing_organization_site VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{ids['s1']}',now());
        SET CONSTRAINTS ALL IMMEDIATE;
        SET CONSTRAINTS ALL DEFERRED;
        DELETE FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}';
        UPDATE foundation.purchasing_organization_company SET site_scope='all_sites' WHERE purchasing_organization_id='{ids['org']}';
        SET CONSTRAINTS ALL IMMEDIATE;"""
        result=sql('BEGIN;'+statements+'ROLLBACK;',role='enginia360_app',check=False)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_empty_selected_and_contradictory_all_fail_at_commit(self):
        for mode,with_site in [('selected_sites',False),('all_sites',True)]:
            ids,base=fixture()
            statement=base+f"INSERT INTO foundation.purchasing_organization_company VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{mode}',now());"
            if with_site:statement+=f"INSERT INTO foundation.purchasing_organization_site VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{ids['s1']}',now());"
            result=sql('BEGIN;'+statement+'COMMIT;',role='enginia360_app',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('23514',result.stderr)
            self.assertEqual(sql(f"SELECT count(*) FROM foundation.tenant WHERE id='{ids['tenant']}'").stdout.strip(),'0')

    def test_parent_scope_foreign_company_and_cross_tenant_are_rejected(self):
        for attack in ('wrong_company','cross_tenant','duplicate_company'):
            ids,base=fixture()
            assignment=f"INSERT INTO foundation.purchasing_organization_company VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','all_sites',now());"
            if attack=='wrong_company':extra=f"INSERT INTO foundation.purchasing_organization_site VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{ids['s2']}',now());"
            elif attack=='cross_tenant':extra=f"INSERT INTO foundation.sales_organization(tenant_id,company_id,name) VALUES('{ids['other']}','{ids['a']}','Vendita');"
            else:extra=assignment
            result=sql('BEGIN;'+base+assignment+extra+'COMMIT;',role='enginia360_app',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('23505' if attack=='duplicate_company' else '23503',result.stderr)

    def test_concurrent_site_removals_keep_selected_scope_nonempty(self):
        import time
        ids,base=fixture();second=str(uuid.uuid4())
        setup=base+f"INSERT INTO foundation.site(id,tenant_id,company_id,name,tax_code,address,city,province,postal_code,country_code) VALUES('{second}','{ids['tenant']}','{ids['a']}','Seconda sede A','CF','Via prova','Roma','RM','00100','IT'); INSERT INTO foundation.purchasing_organization_company VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','selected_sites',now()); INSERT INTO foundation.purchasing_organization_site VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{ids['s1']}',now()),('{ids['tenant']}','{ids['org']}','{ids['a']}','{second}',now());"
        sql('BEGIN;'+setup+'COMMIT;')
        processes=[]
        try:
            for position,site in enumerate((ids['s1'],second)):
                marker='coverage-'+ids['org']+'-'+str(position)
                require_isolated()
                process=subprocess.Popen(['docker','exec','-i',CONTAINER,'psql','-U','enginia360_proof_login','-d','enginia360','-X','-qAt','-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
                processes.append(process)
                process.stdin.write(f"SET ROLE enginia360_app;SET application_name='{marker}';BEGIN;DELETE FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}' AND site_id='{site}';SET CONSTRAINTS ALL IMMEDIATE;\n");process.stdin.flush()
                for _ in range(100):
                    state=sql(f"SELECT state||':'||coalesce(wait_event_type,'') FROM pg_stat_activity WHERE application_name='{marker}'").stdout.strip()
                    if state.startswith('idle in transaction:') or state.endswith(':Lock'):break
                    time.sleep(.02)
                else:self.fail('Barriera di verifica non raggiunta')
            errors=[]
            for process in processes:
                # Il perdente può avere già ricevuto 23514 ed essere uscito:
                # non confondere il pipe chiuso con un errore dell'orchestratore.
                try:
                    process.stdin.write('COMMIT;\n');process.stdin.close()
                except BrokenPipeError:
                    pass
                process.wait(timeout=10)
                errors.append(process.stderr.read())
            self.assertTrue(any('23514' in error for error in errors),errors)
            count=int(sql(f"SELECT count(*) FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}'").stdout)
            self.assertEqual(count,1,'Due rimozioni concorrenti non devono lasciare una copertura selezionata vuota')
            self.assertEqual(sorted(p.returncode==0 for p in processes),[False,True])
        finally:
            for process in processes:
                if not process.stdin.closed:process.stdin.close()
                if process.poll() is None:process.wait(timeout=10)
                process.stderr.close()
            sql('BEGIN;'+''.join(f"DELETE FROM foundation.{table} WHERE tenant_id='{ids['tenant']}';" for table in ['purchasing_organization_site','purchasing_organization_company','purchasing_organization','site','company'])+f"DELETE FROM foundation.tenant WHERE id IN ('{ids['tenant']}','{ids['other']}');COMMIT;")

    def test_delete_selected_site_alone_is_rejected_but_whole_composition_is_removable(self):
        ids,base=fixture()
        setup=base+f"""
        INSERT INTO foundation.purchasing_organization_company VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','selected_sites',now());
        INSERT INTO foundation.purchasing_organization_site VALUES('{ids['tenant']}','{ids['org']}','{ids['a']}','{ids['s1']}',now());
        """
        try:
            sql('BEGIN;'+setup+'COMMIT;')
            failed=sql(f"BEGIN; DELETE FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}'; COMMIT;",role='enginia360_app',check=False)
            self.assertNotEqual(failed.returncode,0);self.assertIn('23514',failed.stderr)
            result=sql(f"BEGIN; DELETE FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}'; DELETE FROM foundation.purchasing_organization_company WHERE purchasing_organization_id='{ids['org']}'; DELETE FROM foundation.purchasing_organization WHERE id='{ids['org']}'; COMMIT;",role='enginia360_app',check=False)
            self.assertEqual(result.returncode,0,result.stderr)
        finally:
            sql(f"DELETE FROM foundation.purchasing_organization_site WHERE purchasing_organization_id='{ids['org']}'; DELETE FROM foundation.purchasing_organization_company WHERE purchasing_organization_id='{ids['org']}'; DELETE FROM foundation.purchasing_organization WHERE id='{ids['org']}'; DELETE FROM foundation.site WHERE tenant_id='{ids['tenant']}'; DELETE FROM foundation.company WHERE tenant_id='{ids['tenant']}'; DELETE FROM foundation.tenant WHERE id IN ('{ids['tenant']}','{ids['other']}');")


if __name__=='__main__':unittest.main(verbosity=2)
