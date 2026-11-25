"""Prove isolate SQL + endpoint mappati (identita fixture, non cookie/CSRF).
CATALOG_ITEM_STATES_DB_TESTS=1 python -m unittest tests.database.test_catalog_item_states_runtime -v
"""
from pathlib import Path
import os
import subprocess
import tempfile
import time
import unittest
import uuid
from tests.database import test_catalog_items_runtime as helpers
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]

@unittest.skipUnless(os.environ.get('CATALOG_ITEM_STATES_DB_TESTS')=='1','Richiede PostgreSQL effimero esplicito')
class CatalogItemStatesTests(unittest.TestCase):
    sql=classmethod(helpers.CatalogItemsDatabaseTests.sql.__func__)
    setUp=helpers.CatalogItemsDatabaseTests.setUp
    scalar=helpers.CatalogItemsDatabaseTests.scalar
    unit=helpers.CatalogItemsDatabaseTests.unit
    reject=helpers.CatalogItemsDatabaseTests.reject
    pack=helpers.CatalogItemsDatabaseTests.pack
    associate=helpers.CatalogItemsDatabaseTests.associate
    identifier=helpers.CatalogItemsDatabaseTests.identifier
    @classmethod
    def setUpClass(cls):
        cls.container='enginia360-item-states-'+uuid.uuid4().hex[:10]
        subprocess.run(['docker','run','--rm','-d','--name',cls.container,'--network','none','--tmpfs','/var/lib/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',str(ROOT/'database')+':/sql:ro','postgres:18.6-alpine3.24'],check=True,capture_output=True)
        try:
            for _ in range(80):
                if subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode==0:break
                time.sleep(.25)
            else:raise RuntimeError('PostgreSQL non pronto')
            cls.sql('CREATE ROLE enginia360_app NOLOGIN;CREATE DATABASE catalog_items;',database='postgres')
            cls.sql(load_foundation_sql())
        except BaseException:
            subprocess.run(['docker','rm','-f',cls.container],capture_output=True);raise
    @classmethod
    def tearDownClass(cls):subprocess.run(['docker','rm','-f',cls.container],check=True,capture_output=True)

    def insert(self,status=None,complete=True,code=None):
        i=str(uuid.uuid4());code=code or i
        columns=',status' if status is not None else '';value=f",'{status}'" if status is not None else ''
        refs=f",'{self.category}','{self.pz}'" if complete else ',NULL,NULL'
        self.sql(f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id{columns}) VALUES('{i}','{self.t}','{code}','Articolo','{self.good}'{refs}{value});")
        return i
    def test_default_active_and_first_activation(self):
        i=self.insert()
        self.assertEqual(self.scalar(f"SELECT status||':'||(activated_at IS NOT NULL)::text||':'||version FROM masterdata.catalog_item WHERE id='{i}'"),'ACTIVE:true:1')
        self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id) VALUES('{self.t}','Incomplete','Incomplete','{self.good}');")
    def test_final_baseline_fresh_install(self):
        database='fresh_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(load_foundation_sql(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.numbering_series;',database=database).stdout,'0\n0\n0\n0\n')
    def test_suspended_optional_manual_code_and_terminal_archive(self):
        i=self.insert('SUSPENDED',False,'OLD')
        self.assertEqual(self.scalar(f"SELECT (activated_at IS NULL)::text FROM masterdata.catalog_item WHERE id='{i}'"),'true')
        self.sql(f"INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding) VALUES('{self.t}','CATALOG_GOOD','MANUAL','',6);UPDATE masterdata.catalog_item SET code='NEW' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET code='OLD' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET status='ACTIVE' WHERE id='{i}';")
        self.sql(f"UPDATE masterdata.catalog_item SET category_id='{self.category}',base_uom_id='{self.pz}',status='ACTIVE' WHERE id='{i}';UPDATE masterdata.catalog_item SET status='SUSPENDED' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET code='THIRD' WHERE id='{i}';")
        self.sql(f"UPDATE masterdata.catalog_item SET status='ARCHIVED' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET status='ACTIVE' WHERE id='{i}';")
        for state in ('DRAFT','INACTIVE','ARCHIVED'):self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,status) VALUES('{self.t}','{state}','Invalid','{self.good}','{state}');")
    def test_active_staged_children_and_fresh_validation(self):
        i=str(uuid.uuid4());cf=self.pack()
        self.sql(f"BEGIN;INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id,status) VALUES('{i}','{self.t}','{i}','Staged','{self.good}','{self.category}','{self.pz}','ACTIVE');INSERT INTO masterdata.catalog_item_unit(tenant_id,item_id,uom_id,conversion_numerator,conversion_denominator) VALUES('{self.t}','{i}','{cf}',6,1);INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value,uom_id) VALUES('{self.t}','{i}','OEM','PACK','PACK','{cf}');COMMIT;")
        self.assertEqual(self.scalar(f"SELECT version FROM masterdata.catalog_item WHERE id='{i}'"),'1')
        self.sql(f"UPDATE masterdata.catalog_item SET status='SUSPENDED' WHERE id='{i}';UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE id='{cf}';")
        self.reject(f"UPDATE masterdata.catalog_item SET status='ACTIVE' WHERE id='{i}';",'Attivazione')
        self.sql(f"UPDATE masterdata.catalog_item SET name='Suspended incomplete allowed' WHERE id='{i}';")
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
    def test_mapped_http_compiled_backend(self):
        with tempfile.TemporaryDirectory(prefix='item-states-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            proof=Path(folder)
            (proof/'Proof.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (proof/'Program.cs').write_text('Enginia360.Verification.Catalog.CatalogItemSelfTests.Run((name,test)=>{test();System.Console.WriteLine("PASS "+name);}); await Enginia360.Verification.Catalog.CatalogItemStatesTests.Run("Host=127.0.0.1;Database=catalog_items;Username=postgres;Maximum Pool Size=10");')
            result=subprocess.run(['docker','run','--rm','--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh',os.environ.get('CATALOG_STATES_SDK_IMAGE','enginia360-backend:bp-phase2-sdk'),'-c','mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Proof.csproj -c Release /p:UseSharedCompilation=false /m:1'],capture_output=True,text=True,timeout=240)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS catalog item states mapped HTTP',result.stdout)
            print(result.stdout)
if __name__=='__main__':unittest.main()
