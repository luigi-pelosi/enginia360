"""Prove SQL su PostgreSQL effimero, mai sul database applicativo.
CATALOG_ITEMS_DB_TESTS=1 python -m unittest tests.database.test_catalog_items_runtime -v
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import time
import unittest
import uuid

from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]

@unittest.skipUnless(os.environ.get('CATALOG_ITEMS_DB_TESTS')=='1','Richiede PostgreSQL effimero esplicito')
class CatalogItemsDatabaseTests(unittest.TestCase):
    @classmethod
    def sql(cls,text,check=True,database='catalog_items'):
        result=subprocess.run(['docker','exec','-i',cls.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d',database],input=text,capture_output=True,text=True,timeout=60)
        if check and result.returncode: raise AssertionError(result.stdout+result.stderr)
        return result

    @classmethod
    def setUpClass(cls):
        cls.container='enginia360-catalog-items-sql-'+uuid.uuid4().hex[:10]
        subprocess.run(['docker','run','--rm','-d','--name',cls.container,'--network','none','--tmpfs','/var/lib/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',str(ROOT/'database')+':/sql:ro','postgres:18.6-alpine3.24'],check=True,capture_output=True)
        try:
            for _ in range(80):
                if subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode==0: break
                time.sleep(.25)
            else:
                raise RuntimeError('PostgreSQL finale non pronto su TCP')
            cls.sql('CREATE ROLE enginia360_app NOLOGIN;CREATE DATABASE catalog_items;',database='postgres')
            cls.sql(load_foundation_sql())
        except BaseException:
            subprocess.run(['docker','rm','-f',cls.container],capture_output=True)
            raise

    @classmethod
    def tearDownClass(cls): subprocess.run(['docker','rm','-f',cls.container],check=True,capture_output=True)

    def setUp(self):
        self.t=str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.t}','{self.t}','Prova');SELECT masterdata.seed_catalog('{self.t}',NULL);")
        self.good=self.scalar("SELECT id FROM masterdata.catalog_item_type WHERE kind='GOOD'")
        self.service=self.scalar("SELECT id FROM masterdata.catalog_item_type WHERE kind='SERVICE'")
        self.pz=self.unit('PZ');self.g=self.unit('G');self.kg=self.unit('KG');self.cm=self.unit('CM')
        self.category=str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES('{self.category}','{self.t}','Categoria');")

    def scalar(self,q):
        return self.sql(q+(' AND ' if 'WHERE' in q else ' WHERE ')+f"tenant_id='{self.t}';").stdout.strip()
    def unit(self,code): return self.scalar(f"SELECT id FROM masterdata.catalog_unit_of_measure WHERE code='{code}'")
    def reject(self,q,needle=None):
        result=self.sql('BEGIN;'+q+'COMMIT;',check=False)
        self.assertNotEqual(result.returncode,0,result.stdout)
        if needle:self.assertIn(needle,result.stderr)
    def item(self,code=None,service=False,base=None):
        i=str(uuid.uuid4());code=code or i
        self.sql(f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id,status) VALUES('{i}','{self.t}','{code}','Articolo','{self.service if service else self.good}','{self.category}','{base or self.pz}','SUSPENDED');")
        return i
    def pack(self,code='CF'):
        u=str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_unit_of_measure(id,tenant_id,code,name,dimension,conversion_scope,factor_to_base,decimal_places) VALUES('{u}','{self.t}','{code}','Confezione','COUNT','ITEM',NULL,3);")
        return u
    def associate(self,i,u,n='6',d='1'):
        a=str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_item_unit(id,tenant_id,item_id,uom_id,conversion_numerator,conversion_denominator) VALUES('{a}','{self.t}','{i}','{u}',{n},{d});")
        return a
    def identifier(self,i,value,type='OEM',u=None,primary=False):
        a=str(uuid.uuid4());unit='NULL' if u is None else f"'{u}'"
        self.sql(f"INSERT INTO masterdata.catalog_item_identifier(id,tenant_id,item_id,identifier_type,value,normalized_value,uom_id,is_primary) VALUES('{a}','{self.t}','{i}','{type}','{value}','not trusted',{unit},{str(primary).lower()});")
        return a
    def active(self,i):
        self.sql(f"UPDATE masterdata.catalog_item SET status='ACTIVE',activated_at=coalesce(activated_at,now()) WHERE tenant_id='{self.t}' AND id='{i}';")

    def test_item_scope_nullable_factor_and_structural_immutability(self):
        u=self.pack()
        self.assertEqual(self.scalar(f"SELECT conversion_scope||':'||(factor_to_base IS NULL)::text||':'||is_base FROM masterdata.catalog_unit_of_measure WHERE id='{u}'"),'ITEM:true:false')
        for change in ("conversion_scope='UNIVERSAL',factor_to_base=1","factor_to_base=1","is_base=true"):
            self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET {change} WHERE id='{u}';")
        self.reject(f"INSERT INTO masterdata.catalog_unit_of_measure(tenant_id,code,name,dimension,conversion_scope,factor_to_base,decimal_places) VALUES('{self.t}','BAD','Bad','COUNT','UNIVERSAL',NULL,0);")
        self.assertEqual(self.scalar("SELECT count(*) FROM masterdata.catalog_unit_of_measure WHERE conversion_scope='UNIVERSAL'"),'11')

    def test_code_append_only_no_reuse_even_same_item(self):
        i=self.item('OLD')
        self.sql(f"INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding) VALUES('{self.t}','CATALOG_GOOD','MANUAL','',6);UPDATE masterdata.catalog_item SET code='NEW' WHERE id='{i}';")
        self.assertEqual(self.scalar(f"SELECT string_agg(code,',' ORDER BY code) FROM masterdata.catalog_item_code WHERE item_id='{i}'"),'NEW,OLD')
        self.reject(f"UPDATE masterdata.catalog_item SET code='old' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item_code SET code='FREE' WHERE item_id='{i}';")
        self.reject(f"DELETE FROM masterdata.catalog_item_code WHERE item_id='{i}';")
        self.reject(f"DELETE FROM masterdata.catalog_item WHERE id='{i}';")
        self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,status) VALUES('{self.t}','OLD','Collisione','{self.service}','SUSPENDED');")

    def test_automatic_code_change_and_nature_forbidden(self):
        i=self.item()
        self.reject(f"UPDATE masterdata.catalog_item SET code='X' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET item_type_id='{self.service}' WHERE id='{i}';")
        t=str(uuid.uuid4());self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{t}','{self.t}','Altro','GOOD');UPDATE masterdata.catalog_item SET item_type_id='{t}' WHERE id='{i}';")

    def test_lifecycle_activation_and_archive_terminal(self):
        i=self.item();self.active(i)
        self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id='{self.g}' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET activated_at=NULL WHERE id='{i}';")
        self.sql(f"UPDATE masterdata.catalog_item SET status='SUSPENDED' WHERE id='{i}';")
        self.active(i)
        self.sql(f"UPDATE masterdata.catalog_item SET status='ARCHIVED' WHERE id='{i}';")
        for change in ("name='Changed'","status='ACTIVE'","status='DRAFT'"):
            self.reject(f"UPDATE masterdata.catalog_item SET {change} WHERE id='{i}';")
        self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value) VALUES('{self.t}','{i}','OEM','X','X');")

    def test_draft_optional_and_activation_revalidates_inactive_references(self):
        i=str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,status) VALUES('{i}','{self.t}','DRAFT','Bozza','{self.good}','SUSPENDED');")
        self.reject(f"UPDATE masterdata.catalog_item SET status='ACTIVE',activated_at=now() WHERE id='{i}';")
        self.sql(f"UPDATE masterdata.catalog_item SET category_id='{self.category}',base_uom_id='{self.g}' WHERE id='{i}';UPDATE masterdata.catalog_category SET is_active=false WHERE id='{self.category}';UPDATE masterdata.catalog_item SET name='Conserva riferimento' WHERE id='{i}';")
        self.reject(f"UPDATE masterdata.catalog_item SET status='ACTIVE',activated_at=now() WHERE id='{i}';",'Attivazione')
        self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,category_id) VALUES('{self.t}','INACTIVE','Bozza','{self.good}','{self.category}');",'Categoria non attiva')

    def test_gtin_canonical_check_digit_and_uniqueness(self):
        i=self.item();j=self.item()
        self.identifier(i,'96385074','GTIN')
        self.assertEqual(self.scalar(f"SELECT normalized_value FROM masterdata.catalog_item_identifier WHERE item_id='{i}'"),'00000096385074')
        self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value) VALUES('{self.t}','{j}','GTIN','00000096385074','fake');")
        for value in ('96385075','123','abcdefgh','123456789012345'):
            self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value) VALUES('{self.t}','{j}','GTIN','{value}','fake');",'GTIN')

    def test_oem_shared_primary_unique_and_barcode_tenant_unique(self):
        i=self.item();j=self.item()
        self.identifier(i,'OE-M 1',primary=True);self.identifier(j,'OE-M 1',primary=True)
        self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value,is_primary) VALUES('{self.t}','{i}','OEM','OTHER','OTHER',true);")
        self.identifier(i,'Internal-1','BARCODE')
        self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value) VALUES('{self.t}','{j}','BARCODE','internal-1','fake');")

    def test_unit_ratios_non_dimension_base_and_identifier_dependencies(self):
        i=self.item(base=self.g)
        self.associate(i,self.kg,'1000','1')
        self.reject(f"UPDATE masterdata.catalog_item_unit SET conversion_numerator=1 WHERE item_id='{i}';",'Rapporto')
        cf=self.pack();a=self.associate(i,cf,'6','1');ident=self.identifier(i,'PACK','OEM',cf)
        self.reject(f"DELETE FROM masterdata.catalog_item_unit WHERE id='{a}';",'Identificativo')
        self.reject(f"UPDATE masterdata.catalog_item_unit SET is_active=false WHERE id='{a}';",'Identificativo')
        self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id='{self.kg}' WHERE id='{i}';",'Base utilizzata')
        self.sql(f"DELETE FROM masterdata.catalog_item_identifier WHERE id='{ident}';DELETE FROM masterdata.catalog_item_unit WHERE id='{a}';")
        j=self.item();self.associate(j,cf,'24','1')

    def test_draft_base_blocked_by_implicit_identifier_or_physical_data(self):
        i=self.item();self.identifier(i,'BASE-IMPLICIT','OEM')
        for base in (f"'{self.g}'",'NULL'):
            self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id={base} WHERE id='{i}';",'Base utilizzata')
        j=self.item()
        self.sql(f"INSERT INTO masterdata.catalog_item_physical_data(tenant_id,item_id,net_weight,weight_uom_id) VALUES('{self.t}','{j}',1,'{self.kg}');")
        self.reject(f"UPDATE masterdata.catalog_item SET base_uom_id='{self.g}' WHERE id='{j}';",'Base utilizzata')
        self.sql(f"DELETE FROM masterdata.catalog_item_physical_data WHERE item_id='{j}';UPDATE masterdata.catalog_item SET base_uom_id='{self.g}' WHERE id='{j}';UPDATE masterdata.catalog_item SET base_uom_id=NULL WHERE id='{j}';")

    def test_child_version_and_stable_identity(self):
        i=self.item();u=self.pack();a=self.associate(i,u)
        self.assertEqual(self.scalar(f"SELECT version FROM masterdata.catalog_item WHERE id='{i}'"),'2')
        self.sql(f"BEGIN;UPDATE masterdata.catalog_item_unit SET conversion_numerator=7 WHERE id='{a}';UPDATE masterdata.catalog_item_unit SET conversion_numerator=8 WHERE id='{a}';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT version||':'||name FROM masterdata.catalog_item WHERE id='{i}'"),'4:Articolo')
        self.reject(f"UPDATE masterdata.catalog_item_unit SET id=gen_random_uuid() WHERE id='{a}';",'Identita')

    def test_physical_goods_only_correct_dimensions_and_exact_decimals(self):
        i=self.item();j=self.item(service=True)
        q=f"INSERT INTO masterdata.catalog_item_physical_data(tenant_id,item_id,net_weight,gross_weight,weight_uom_id,length,dimension_uom_id) VALUES('{self.t}','{i}',1.000000000001,2,'{self.kg}',3,'{self.cm}');"
        self.sql(q)
        for change in ('net_weight=-1','gross_weight=0','net_weight=0.0000000000001',f"weight_uom_id='{self.cm}'",f"dimension_uom_id='{self.kg}'"):
            self.reject(f"UPDATE masterdata.catalog_item_physical_data SET {change} WHERE item_id='{i}';")
        self.reject(q.replace(i,j),'solo per beni')
        self.sql(f"DELETE FROM masterdata.catalog_item_physical_data WHERE item_id='{i}';")

    def test_cross_tenant_and_cross_item_child_references_rejected(self):
        i=self.item();u=self.pack();self.associate(i,u);j=self.item()
        self.reject(f"INSERT INTO masterdata.catalog_item_identifier(tenant_id,item_id,identifier_type,value,normalized_value,uom_id) VALUES('{self.t}','{j}','OEM','PACK','PACK','{u}');",'non associata')
        foreign=str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{foreign}','{foreign}','Estraneo');")
        self.reject(f"INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,status) VALUES('{foreign}','FOREIGN','Estraneo','{self.good}','SUSPENDED');")

    def test_concurrent_code_reservations_unique(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            def attempt(delay):
                return self.sql(f"BEGIN;INSERT INTO masterdata.catalog_item(tenant_id,code,name,item_type_id,status) VALUES('{self.t}','SAME','Concorrenza','{self.good}','SUSPENDED');SELECT pg_sleep({delay});COMMIT;",False)
            first=pool.submit(attempt,.4);time.sleep(.1);second=pool.submit(attempt,0)
            results=[first.result(),second.result()]
        self.assertEqual(sorted(r.returncode==0 for r in results),[False,True])
        self.assertEqual(self.scalar("SELECT count(*) FROM masterdata.catalog_item_code WHERE code='SAME'"),'1')

    def test_runtime_role_writes_trigger_reservations_and_no_delete_root(self):
        i=str(uuid.uuid4())
        self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,status) VALUES('{i}','{self.t}','ROLE','Ruolo','{self.good}','SUSPENDED');")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_code WHERE item_id='{i}'"),'1')
        self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item WHERE id='{i}';")
        self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_code WHERE item_id='{i}';")

    def test_backend_http_runtime(self):
        import tempfile
        with tempfile.TemporaryDirectory(prefix='catalog-items-dotnet-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            proof=Path(folder)
            (proof/'Proof.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (proof/'Program.cs').write_text('Enginia360.Verification.Catalog.CatalogSelfTests.Run((name,test)=>{test();System.Console.WriteLine("PASS "+name);}); Enginia360.Verification.Catalog.CatalogItemSelfTests.Run((name,test)=>{test();System.Console.WriteLine("PASS "+name);}); await Enginia360.Verification.Catalog.CatalogItemRuntimeTests.Run("Host=127.0.0.1;Database=catalog_items;Username=postgres;Maximum Pool Size=10");')
            command='mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Proof.csproj -c Release /p:UseSharedCompilation=false /m:1'
            result=subprocess.run(['docker','run','--rm','--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh','enginia360-backend:bp-phase2-sdk','-c',command],capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS catalog items HTTP runtime:',result.stdout)
            print(result.stdout)

    def test_final_baseline_fresh_install(self):
        database='fresh_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(load_foundation_sql(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.numbering_series;',database=database).stdout,'0\n0\n0\n0\n')

if __name__=='__main__':unittest.main()
