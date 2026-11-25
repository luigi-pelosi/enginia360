"""Prove isolate nature economiche; CATALOG_NATURES_DB_TESTS=1 per SQL e HTTP compilato."""
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

@unittest.skipUnless(os.environ.get('CATALOG_NATURES_DB_TESTS')=='1','Richiede PostgreSQL effimero esplicito')
class CatalogNaturesTests(unittest.TestCase):
    sql=classmethod(helpers.CatalogItemsDatabaseTests.sql.__func__)
    setUp=helpers.CatalogItemsDatabaseTests.setUp
    scalar=helpers.CatalogItemsDatabaseTests.scalar
    unit=helpers.CatalogItemsDatabaseTests.unit
    reject=helpers.CatalogItemsDatabaseTests.reject
    @classmethod
    def baseline(cls):
        return load_foundation_sql()
    @classmethod
    def setUpClass(cls):
        cls.container='enginia360-natures-'+uuid.uuid4().hex[:10]
        subprocess.run(['docker','run','--rm','-d','--name',cls.container,'--network','none','--tmpfs','/var/lib/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',str(ROOT/'database')+':/sql:ro','postgres:18.6-alpine3.24'],check=True,capture_output=True)
        try:
            for _ in range(80):
                if subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode==0:break
                time.sleep(.25)
            else:raise RuntimeError('PostgreSQL non pronto su TCP')
            cls.sql('CREATE ROLE enginia360_app NOLOGIN;CREATE DATABASE catalog_items;',database='postgres')
            cls.sql(cls.baseline())
        except BaseException:
            subprocess.run(['docker','rm','-f',cls.container],capture_output=True);raise
    @classmethod
    def tearDownClass(cls):subprocess.run(['docker','rm','-f',cls.container],check=True,capture_output=True)
    def test_four_natures_stock_physical_immutability_and_unique_codes(self):
        for kind in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            type_id=str(uuid.uuid4());item=str(uuid.uuid4())
            self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{type_id}','{self.t}','{kind}','{kind}');INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{kind}','{kind}','{type_id}','{self.category}','{self.pz}');")
            self.reject(f"UPDATE masterdata.catalog_item_type SET kind='{('SERVICE' if kind=='GOOD' else 'GOOD')}' WHERE id='{type_id}';",'Natura immutabile')
            if kind!='GOOD':
                self.reject(f"UPDATE masterdata.catalog_item_type SET default_track_stock=true WHERE id='{type_id}';",'catalog_item_type_check')
                self.reject(f"INSERT INTO masterdata.catalog_item_physical_data(tenant_id,item_id) VALUES('{self.t}','{item}');",'Dati fisici solo per beni')
                self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{self.t}','good','Duplicate','{type_id}','{self.category}','{self.pz}');")
            self.sql(f"INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding) VALUES('{self.t}','CATALOG_{kind}','AUTO','',6);")
        self.assertEqual(self.scalar('SELECT count(*) FROM masterdata.catalog_item_type'),'6')
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
    def test_final_discriminator_and_numbering_constraints_refuse_unknown_values(self):
        snapshot="SELECT count(*) FROM masterdata.catalog_item_type;SELECT count(*) FROM foundation.numbering_series;SELECT count(*) FROM foundation.numbering_counter;SELECT count(*) FROM foundation.role_permission;"
        before=self.sql(snapshot).stdout
        for kind in ('GOODS','UNKNOWN','good',''):
            self.reject(f"INSERT INTO masterdata.catalog_item_type(tenant_id,name,kind) VALUES('{self.t}','Invalid','{kind}');")
        for entity in ('CATALOG_UNKNOWN','CATALOG_GOODS','CATALOG','BUSINESS_PARTNER_COMPANY'):
            self.reject(f"INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding) VALUES('{self.t}','{entity}','AUTO','',6);")
        self.assertEqual(before,self.sql(snapshot).stdout)

    def test_fresh_no_data_no_seed_no_series(self):
        self.sql('CREATE DATABASE natures_fresh;',database='postgres')
        self.sql(self.baseline(),database='natures_fresh')
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item_type;SELECT count(*) FROM foundation.numbering_series;',database='natures_fresh').stdout,'0\n0\n')
    def test_mapped_http_compiled_backend(self):
        with tempfile.TemporaryDirectory(prefix='natures-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            proof=Path(folder)
            (proof/'Proof.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (proof/'Program.cs').write_text('await Enginia360.Verification.Catalog.CatalogNaturesTests.Run("Host=127.0.0.1;Database=catalog_items;Username=postgres;Maximum Pool Size=10");')
            result=subprocess.run(['docker','run','--rm','--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh',os.environ.get('CATALOG_NATURES_SDK_IMAGE','enginia360-backend:bp-phase2-sdk'),'-c','mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Proof.csproj -c Release /p:UseSharedCompilation=false /m:1'],capture_output=True,text=True,timeout=240)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS catalog natures mapped HTTP',result.stdout)
            print(result.stdout)
if __name__=='__main__':unittest.main()
