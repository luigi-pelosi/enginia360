"""PostgreSQL effimero: CATALOG_COMPANIES_DB_TESTS=1 python -m unittest
 tests.database.test_catalog_companies_runtime.CatalogCompaniesTests -v
Nessuna porta host, nessun volume dati persistente, nessun endpoint applicativo.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import re
import subprocess
import time
import unittest
import uuid
from tests.database import test_catalog_items_runtime as items
from tests.database import test_catalog_natures_runtime as natures

from database.sql_source import load_foundation_sql
ROOT = Path(__file__).resolve().parents[2]

@unittest.skipUnless(os.environ.get('CATALOG_COMPANIES_DB_TESTS') == '1', 'Richiede PostgreSQL effimero esplicito')
class CatalogCompaniesTests(unittest.TestCase):
    sql = classmethod(items.CatalogItemsDatabaseTests.sql.__func__)
    scalar = items.CatalogItemsDatabaseTests.scalar
    unit = items.CatalogItemsDatabaseTests.unit
    pack = items.CatalogItemsDatabaseTests.pack
    associate = items.CatalogItemsDatabaseTests.associate
    item = items.CatalogItemsDatabaseTests.item

    @classmethod
    def baseline(cls):
        return load_foundation_sql()

    @classmethod
    def setUpClass(cls):
        cls.container = 'enginia360-companies-sql-' + uuid.uuid4().hex[:10]
        subprocess.run(['docker','run','--rm','-d','--name',cls.container,'--network','none','--tmpfs','/var/lib/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',str(ROOT/'database')+':/sql:ro','postgres:18.6-alpine3.24'],check=True,capture_output=True)
        try:
            for _ in range(100):
                if subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode == 0:
                    break
                time.sleep(.25)
            else:
                raise RuntimeError('PostgreSQL finale non pronto su TCP')
            cls.sql('CREATE ROLE enginia360_app NOLOGIN;CREATE DATABASE catalog_items;',database='postgres')
            cls.sql(cls.baseline())
        except BaseException:
            subprocess.run(['docker','rm','-f',cls.container],capture_output=True)
            raise

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['docker','rm','-f',cls.container],check=True,capture_output=True)

    def setUp(self):
        items.CatalogItemsDatabaseTests.setUp(self)
        self.company = str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{self.company}','{self.t}','Societa');")

    def reject(self, text, state=None, database='catalog_items'):
        result = self.sql('\\set VERBOSITY verbose\nBEGIN;' + text + 'COMMIT;',check=False,database=database)
        self.assertNotEqual(result.returncode,0,result.stdout)
        if state:
            self.assertIn(state,result.stderr)
        self.assertNotIn('deadlock detected',result.stderr)
        return result

    def insert_sql(self, item, *, company=None, tenant=None, stock=False, sales='NULL', purchase='NULL', id=None):
        id = id or str(uuid.uuid4())
        return f"INSERT INTO masterdata.catalog_item_company(id,tenant_id,item_id,company_id,is_sellable,is_purchasable,track_stock,default_sales_uom_id,default_purchase_uom_id) VALUES('{id}','{tenant or self.t}','{item}','{company or self.company}',true,false,{str(stock).lower()},{sales},{purchase});"

    def configure(self,item,**kwargs):
        id = str(uuid.uuid4())
        self.sql('SET ROLE enginia360_app;' + self.insert_sql(item,id=id,**kwargs))
        return id

    def test_all_kinds_stock_and_independent_versions(self):
        for kind in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            with self.subTest(kind=kind):
                type_id = str(uuid.uuid4()); item = str(uuid.uuid4())
                self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{type_id}','{self.t}','{kind}','{kind}');INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{item}','{kind}','{type_id}','{self.category}','{self.pz}');")
                before = self.sql(f"SELECT to_jsonb(i) FROM masterdata.catalog_item i WHERE id='{item}';").stdout
                if kind != 'GOOD':
                    self.reject(self.insert_sql(item,stock=True),'23514')
                config = self.configure(item,stock=kind=='GOOD')
                if kind != 'GOOD':
                    self.reject(f"UPDATE masterdata.catalog_item_company SET track_stock=true WHERE id='{config}';",'23514')
                self.sql(f"SET ROLE enginia360_app;UPDATE masterdata.catalog_item_company SET is_sellable=false,is_purchasable=true,version=version+1 WHERE id='{config}';")
                self.assertEqual(self.scalar(f"SELECT version FROM masterdata.catalog_item_company WHERE id='{config}'"),'2')
                self.assertEqual(before,self.sql(f"SELECT to_jsonb(i) FROM masterdata.catalog_item i WHERE id='{item}';").stdout)

    def test_identity_delete_privileges_and_limits(self):
        item = self.item(); config = self.configure(item)
        for change in ["id=gen_random_uuid()","tenant_id=gen_random_uuid()","company_id=gen_random_uuid()","item_id=gen_random_uuid()","created_at=created_at+interval '1 second'"]:
            self.reject(f"UPDATE masterdata.catalog_item_company SET {change} WHERE id='{config}';",'23514')
        for change in ['version=0','version=9007199254740992','is_sellable=NULL','is_purchasable=NULL','track_stock=NULL','is_enabled=NULL']:
            self.reject(f"UPDATE masterdata.catalog_item_company SET {change} WHERE id='{config}';",'23502' if 'NULL' in change else '23514')
        self.reject(f"DELETE FROM masterdata.catalog_item_company WHERE id='{config}';",'23514')
        self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_company WHERE id='{config}';",'42501')
        self.reject('SET ROLE enginia360_app;TRUNCATE masterdata.catalog_item_company;','42501')
        self.reject('SET ROLE enginia360_app;ALTER TABLE masterdata.catalog_item_company ADD COLUMN bad text;','42501')
        self.assertEqual(self.sql("SELECT has_table_privilege('enginia360_app','masterdata.catalog_item_company','SELECT,INSERT,UPDATE'),has_table_privilege('enginia360_app','masterdata.catalog_item_company','DELETE'),has_function_privilege('public','masterdata.assert_catalog_company_unit(uuid,uuid,uuid,uuid)','EXECUTE');").stdout,'t|f|f\n')

    def test_tenant_boundaries_default_membership_and_uniqueness(self):
        item = self.item(); other_t = str(uuid.uuid4()); other_c = str(uuid.uuid4()); other_i = str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{other_t}','{other_t}','Altro');SELECT masterdata.seed_catalog('{other_t}',NULL);INSERT INTO foundation.company(id,tenant_id,name) VALUES('{other_c}','{other_t}','Altra');INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,base_uom_id,status) SELECT '{other_i}','{other_t}','Other','Other',t.id,u.id,'SUSPENDED' FROM masterdata.catalog_item_type t JOIN masterdata.catalog_unit_of_measure u ON u.tenant_id=t.tenant_id AND u.code='PZ' WHERE t.tenant_id='{other_t}' AND t.kind='GOOD';")
        other_u = self.sql(f"SELECT id FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{other_t}' AND code='PZ';").stdout.strip()
        for text in [self.insert_sql(item,company=other_c), self.insert_sql(other_i), self.insert_sql(item,sales=f"'{other_u}'"), self.insert_sql(item,purchase=f"'{other_u}'")]:
            self.reject(text,'23503')
        pack = self.pack(); other_item = self.item(); self.associate(other_item,pack)
        self.reject(self.insert_sql(item,sales=f"'{pack}'"),'23503')
        self.associate(item,pack)
        config = self.configure(item,sales=f"'{pack}'",purchase=f"'{self.pz}'")
        self.reject(self.insert_sql(item),'23505')
        self.sql(f"UPDATE masterdata.catalog_item_company SET is_enabled=false WHERE id='{config}';")
        self.reject(self.insert_sql(item),'23505')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_company WHERE item_id='{item}'"),'1')

    def test_suspended_config_archived_and_disabled_company_only_disable(self):
        for disabled_company in [False,True]:
            with self.subTest(disabled_company=disabled_company):
                item = self.item(); self.sql(f"UPDATE masterdata.catalog_item SET status='SUSPENDED' WHERE id='{item}';")
                config = self.configure(item,stock=True)
                if disabled_company:
                    self.sql(f"UPDATE foundation.company SET is_enabled=false WHERE id='{self.company}';")
                else:
                    self.sql(f"UPDATE masterdata.catalog_item SET status='ARCHIVED' WHERE id='{item}';")
                before = self.sql(f"SELECT is_sellable,is_purchasable,track_stock,default_sales_uom_id,default_purchase_uom_id FROM masterdata.catalog_item_company WHERE id='{config}';").stdout
                self.reject(f"UPDATE masterdata.catalog_item_company SET is_sellable=false WHERE id='{config}';",'23514')
                self.reject(f"UPDATE masterdata.catalog_item_company SET is_enabled=false,track_stock=false WHERE id='{config}';",'23514')
                self.reject(self.insert_sql(item),'23514')
                self.sql(f"SET ROLE enginia360_app;UPDATE masterdata.catalog_item_company SET is_enabled=false,version=version+1 WHERE id='{config}';")
                self.assertEqual(before,self.sql(f"SELECT is_sellable,is_purchasable,track_stock,default_sales_uom_id,default_purchase_uom_id FROM masterdata.catalog_item_company WHERE id='{config}';").stdout)
                self.reject(f"UPDATE masterdata.catalog_item_company SET is_enabled=true WHERE id='{config}';",'23514')
                if disabled_company:
                    self.sql(f"UPDATE foundation.company SET is_enabled=true WHERE id='{self.company}';")

    def test_reverse_units_explicit_and_base_fallback_include_disabled_history(self):
        item = self.item(); pack = self.pack(); association = self.associate(item,pack)
        config = self.configure(item,sales=f"'{pack}'")
        for command in [f"DELETE FROM masterdata.catalog_item_unit WHERE id='{association}';",f"UPDATE masterdata.catalog_item_unit SET is_active=false WHERE id='{association}';",f"UPDATE masterdata.catalog_item_unit SET uom_id='{self.g}' WHERE id='{association}';",f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{pack}';",f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{self.pz}';"]:
            self.reject('SET ROLE enginia360_app;'+command,'23503')
        self.sql(f"UPDATE masterdata.catalog_item_company SET is_enabled=false WHERE id='{config}';UPDATE masterdata.catalog_item SET status='ARCHIVED' WHERE id='{item}';")
        self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{pack}';",'23503')
        self.reject(f"DELETE FROM masterdata.catalog_item_unit WHERE id='{association}';",'23503')
        # Una configurazione non riferisce tutte le unità dell'articolo.
        another = self.item(); unused = self.pack('UNUSED'); association = self.associate(another,unused)
        self.configure(another)
        self.sql(f"DELETE FROM masterdata.catalog_item_unit WHERE id='{association}';UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{unused}';")

    def test_pre_activation_base_change_explicit_old_base_rejected_null_follows(self):
        item = str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id,status) VALUES('{item}','{self.t}','{item}','Draft','{self.good}','{self.category}','{self.pz}','SUSPENDED');")
        config = self.configure(item,sales=f"'{self.pz}'")
        self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id='{self.g}' WHERE id='{item}';",'23503')
        self.sql(f"UPDATE masterdata.catalog_item_company SET default_sales_uom_id=NULL WHERE id='{config}';UPDATE masterdata.catalog_item SET base_uom_id='{self.g}' WHERE id='{item}';")
        self.assertEqual(self.scalar(f"SELECT base_uom_id FROM masterdata.catalog_item WHERE id='{item}'"),self.g)
        self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id=NULL WHERE id='{item}';",'23503')
        self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{self.g}';",'23503')
        # Lo stesso cambio di tipologia/natura non altera le capacità memorizzate.
        type_id = str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{type_id}','{self.t}','Altro','GOOD');UPDATE masterdata.catalog_item SET item_type_id='{type_id}' WHERE id='{item}';")

    def test_missing_or_inactive_base_and_defaults_cannot_configure(self):
        item = str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,status) VALUES('{item}','{self.t}','{item}','Legacy','{self.good}','SUSPENDED');")
        self.reject(self.insert_sql(item),'23503')
        item = self.item(base=self.g)
        self.sql(f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{self.g}';")
        self.reject(self.insert_sql(item),'23503')
        item = self.item(); pack = self.pack(); association = self.associate(item,pack)
        self.sql(f"UPDATE masterdata.catalog_item_unit SET is_active=false WHERE id='{association}';")
        self.reject(self.insert_sql(item,sales=f"'{pack}'"),'23503')
        self.reject(self.insert_sql(item,purchase=f"'{pack}'"),'23503')

    def test_concurrent_duplicate_one_controlled_unique_failure(self):
        item = self.item()
        def create(_):
            return self.sql('\\set VERBOSITY verbose\nBEGIN;SET LOCAL ROLE enginia360_app;'+self.insert_sql(item)+'SELECT pg_sleep(.2);COMMIT;',check=False)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create,range(2)))
        self.assertEqual(sorted(r.returncode for r in results),[0,3])
        rejected = next(r for r in results if r.returncode)
        self.assertIn('23505',rejected.stderr)
        self.assertNotIn('deadlock detected',rejected.stderr)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_company WHERE item_id='{item}'"),'1')

    def test_concurrent_default_and_unit_removal_both_orderings(self):
        def spawn(name,text):
            p = subprocess.Popen(['docker','exec','-i','-e','PGAPPNAME='+name,self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','catalog_items'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p.stdin.write(text); p.stdin.close(); p.stdin = None
            return p
        def wait(name,event):
            for _ in range(100):
                if self.sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND wait_event='{event}';").stdout.strip()=='1':
                    return
                time.sleep(.025)
            self.fail('Barriera SQL non osservata: '+name+' '+event)
        for config_first in [True,False]:
            item = self.item(); pack = self.pack('RACE'+uuid.uuid4().hex[:8]); association = self.associate(item,pack)
            config = self.insert_sql(item,sales=f"'{pack}'")
            removal = f"DELETE FROM masterdata.catalog_item_unit WHERE id='{association}';"
            winner = spawn('company_winner','BEGIN;SET LOCAL ROLE enginia360_app;'+(config if config_first else removal)+'SELECT pg_sleep(2);COMMIT;')
            loser = None
            try:
                wait('company_winner','PgSleep')
                loser = spawn('company_waiter','BEGIN;SET LOCAL ROLE enginia360_app;'+(removal if config_first else config)+'COMMIT;')
                wait('company_waiter','advisory')
                out,err = winner.communicate(timeout=15); self.assertEqual(winner.returncode,0,out+err)
                out,err = loser.communicate(timeout=15); self.assertNotEqual(loser.returncode,0,out+err)
                self.assertIn('aziendale',err); self.assertNotIn('deadlock detected',err)
            finally:
                for process in [winner,loser]:
                    if process and process.poll() is None:
                        process.kill(); process.wait()
            self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_company WHERE item_id='{item}'"),'1' if config_first else '0')

    def test_fresh_empty_no_automatic_associations_or_grants(self):
        database = 'companies_fresh'
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(self.baseline(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM foundation.tenant;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM foundation.numbering_series;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.audit_event;',database=database).stdout,'0\n0\n0\n0\n0\n0\n')

    def test_final_baseline_fresh_install(self):
        database='fresh_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(load_foundation_sql(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.numbering_series;',database=database).stdout,'0\n0\n0\n0\n')

    def test_final_baseline_late_failure_rolls_back(self):
        database='rollback_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        source=load_foundation_sql()
        head,tail=source.rsplit('COMMIT;',1)
        result=self.sql(head+'SELECT 1/0;COMMIT;'+tail,check=False,database=database)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('division by zero',result.stderr)
        self.assertEqual(self.sql("SELECT count(*) FROM pg_namespace WHERE nspname IN ('foundation','masterdata');",database=database).stdout,'0\n')

    def test_final_baseline_reinstall_refused_without_changes(self):
        snapshot="SELECT oid,relname,relowner,relacl FROM pg_class WHERE relnamespace IN ('foundation'::regnamespace,'masterdata'::regnamespace) ORDER BY oid;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM masterdata.catalog_item;"
        before=self.sql(snapshot).stdout
        result=self.sql(load_foundation_sql(),check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,self.sql(snapshot).stdout)

    def test_runtime_cannot_replace_final_guards(self):
        snapshot="SELECT oid,prosrc,proacl,proconfig FROM pg_proc WHERE oid='masterdata.guard_catalog()'::regprocedure;"
        before=self.sql(snapshot).stdout
        result=self.sql("BEGIN;SET LOCAL ROLE enginia360_app;CREATE OR REPLACE FUNCTION masterdata.guard_catalog() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$;COMMIT;",check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(before,self.sql(snapshot).stdout)

    def test_two_companies_independent_and_finite_97_operations(self):
        item = self.item(); second = str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{second}','{self.t}','Seconda');")
        first = self.configure(item,stock=True)
        other = self.configure(item,company=second)
        self.sql(f"UPDATE masterdata.catalog_item_company SET is_sellable=false,is_enabled=false,version=version+1 WHERE id='{first}';")
        self.assertEqual(self.scalar(f"SELECT is_sellable||':'||is_enabled||':'||version FROM masterdata.catalog_item_company WHERE id='{other}'"),'true:true:1')
        source = load_foundation_sql().split('CREATE TABLE foundation.permission',1)[1].split('CREATE TABLE',1)[0]
        codes = {code for code in re.findall(r"'([a-z][a-z-]+\.[a-z_]+)'",source) if not code.startswith(('foundation.','masterdata.','pg_temp.'))}
        for resource in ['companies','sites','warehouse-types','warehouses','warehouse-locations','users','groups','roles','sales-organizations','purchasing-organizations']:
            codes.update(resource+'.'+action for action in ['read','create','update','delete'])
        self.assertEqual(len(codes),97)
        values = ','.join(f"('{self.t}','{code}','{code}',true)" for code in sorted(codes))
        self.sql('INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES '+values+' ON CONFLICT(tenant_id,code) DO NOTHING;')
        for code in ['catalog-item-companies.delete','catalog-item-companies.read.extra','catalog-item-companies.READ','catalog-item-company.read','companies.read.extra']:
            self.reject(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.t}','{code}','Bad',true);",'23514')
        self.sql(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.t}','custom.permission','Custom',false);")


if __name__ == '__main__':
    unittest.main()
