"""Prove SQL e HTTP isolate; abilitare con CATALOG_TYPE_NATURE_DB_TESTS=1.
Eseguire la classe esplicita, non la discovery dei moduli di supporto.
"""
from pathlib import Path
import os, subprocess, tempfile, time, unittest, uuid
from tests.database import test_catalog_natures_runtime as natures
from tests.database import test_catalog_items_runtime as items
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]
@unittest.skipUnless(os.environ.get('CATALOG_TYPE_NATURE_DB_TESTS')=='1','Explicit isolated PostgreSQL required')
class CatalogTypeNatureTests(unittest.TestCase):
    sql=classmethod(items.CatalogItemsDatabaseTests.sql.__func__)
    setUp=items.CatalogItemsDatabaseTests.setUp
    scalar=items.CatalogItemsDatabaseTests.scalar
    unit=items.CatalogItemsDatabaseTests.unit
    reject=items.CatalogItemsDatabaseTests.reject
    baseline=classmethod(natures.CatalogNaturesTests.baseline.__func__)
    tearDownClass=classmethod(natures.CatalogNaturesTests.tearDownClass.__func__)
    @classmethod
    def setUpClass(cls):
        natures.CatalogNaturesTests.setUpClass.__func__(cls)
    def test_final_baseline_fresh_install(self):
        database='fresh_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(load_foundation_sql(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.numbering_series;',database=database).stdout,'0\n0\n0\n0\n')
    def test_unused_all_nature_pairs(self):
        for old in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            for new in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
                if old==new:continue
                with self.subTest(old=old,new=new):
                    id=str(uuid.uuid4())
                    self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Unused','{old}');UPDATE masterdata.catalog_item_type SET kind='{new}',version=version+1 WHERE id='{id}';")
                    self.assertEqual(self.scalar(f"SELECT kind||':'||version FROM masterdata.catalog_item_type WHERE id='{id}'"),new+':2')
    def test_referenced_all_states_and_natures_name_edit_only(self):
        for kind in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            for status in ['ACTIVE','SUSPENDED','ARCHIVED']:
                with self.subTest(kind=kind,status=status):
                    id=str(uuid.uuid4());item=str(uuid.uuid4())
                    self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Used','{kind}');INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{item}','Used','{id}','{self.category}','{self.pz}');")
                    if status!='ACTIVE':self.sql(f"UPDATE masterdata.catalog_item SET status='{status}',version=version+1 WHERE id='{item}';")
                    before=self.sql(f"SELECT to_jsonb(i) FROM masterdata.catalog_item i WHERE id='{item}';").stdout
                    for target in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
                        if target!=kind:self.reject(f"SET ROLE enginia360_app;UPDATE masterdata.catalog_item_type SET kind='{target}',version=version+1 WHERE id='{id}';",'Natura immutabile')
                    self.sql(f"SET ROLE enginia360_app;UPDATE masterdata.catalog_item_type SET name='Renamed',kind='{kind}',version=version+1 WHERE id='{id}';")
                    self.assertEqual(self.scalar(f"SELECT name||':'||kind||':'||version FROM masterdata.catalog_item_type WHERE id='{id}'"),'Renamed:'+kind+':2')
                    self.assertEqual(before,self.sql(f"SELECT to_jsonb(i) FROM masterdata.catalog_item i WHERE id='{item}';").stdout)
                    self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_type WHERE id='{id}';",'Tipologia utilizzata')
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
    def test_preserved_unit_category_type_delete_and_stock_guards(self):
        self.reject(f"DELETE FROM masterdata.catalog_unit_of_measure WHERE id='{self.kg}';",'Disattivare il record')
        self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET factor_to_base=99 WHERE id='{self.kg}';",'Significato unita immutabile')
        self.reject(f"UPDATE masterdata.catalog_category SET parent_id=id WHERE id='{self.category}';",'Ciclo categorie')
        unused=str(uuid.uuid4())
        self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES('{unused}','{self.t}','Unused');DELETE FROM masterdata.catalog_category WHERE id='{unused}';")
        for kind in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            id=str(uuid.uuid4())
            self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Unused','{kind}');")
            if kind!='GOOD':self.reject(f"UPDATE masterdata.catalog_item_type SET default_track_stock=true WHERE id='{id}';",'catalog_item_type_check')
            self.sql(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_type WHERE id='{id}';")
    def test_actual_concurrent_insert_and_kind_update_both_orderings(self):
        def spawn(name,sql):
            p=subprocess.Popen(['docker','exec','-i','-e','PGAPPNAME='+name,self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','catalog_items'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p.stdin.write(sql);p.stdin.close();p.stdin=None
            return p
        def wait(name,event):
            for _ in range(100):
                if self.sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND wait_event='{event}';").stdout.strip()=='1':return
                time.sleep(.025)
            self.fail('SQL barrier not observed: '+name+' '+event)
        for insert_first in (True,False):
            with self.subTest(insert_first=insert_first):
                id=str(uuid.uuid4());item=str(uuid.uuid4())
                self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Race','GOOD');")
                insert=f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{item}','Race','{id}','{self.category}','{self.pz}');"
                # Stesso ordine di Save: advisory lock prima del FOR UPDATE.
                # Un UPDATE diretto potrebbe bloccare la radice prima di attendere
                # il lock acquisito dall'inserimento dell'articolo.
                update=f"SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||'{self.t}',0));SELECT id FROM masterdata.catalog_item_type WHERE id='{id}' FOR UPDATE;UPDATE masterdata.catalog_item_type SET kind='SERVICE',version=version+1 WHERE id='{id}';"
                winner=spawn('nature_winner','BEGIN;SET LOCAL ROLE enginia360_app;'+(insert if insert_first else update)+'SELECT pg_sleep(3);COMMIT;')
                try:
                    wait('nature_winner','PgSleep')
                    loser=spawn('nature_waiter','BEGIN;SET LOCAL ROLE enginia360_app;'+(update if insert_first else insert)+'COMMIT;')
                    try:
                        wait('nature_waiter','advisory')
                        out,err=winner.communicate(timeout=15);self.assertEqual(winner.returncode,0,out+err)
                        out,err=loser.communicate(timeout=15)
                        if insert_first:
                            self.assertNotEqual(loser.returncode,0,out+err);self.assertIn('Natura immutabile',err)
                        else:self.assertEqual(loser.returncode,0,out+err)
                        self.assertNotIn('deadlock detected',err)
                    finally:
                        if loser.poll() is None:loser.kill();loser.wait()
                finally:
                    if winner.poll() is None:winner.kill();winner.wait()
                self.assertEqual(self.scalar(f"SELECT kind||':'||version FROM masterdata.catalog_item_type WHERE id='{id}'"),'GOOD:1' if insert_first else 'SERVICE:2')
                self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item WHERE id='{item}'"),'1')
    def test_mapped_http_compiled_backend(self):
        artifacts=Path(os.environ.get('CATALOG_TYPE_NATURE_ARTIFACTS','/root/.hermes/cache/scratch/catalog-type-nature-proof'))
        artifacts.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='type-nature-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            proof=Path(folder)
            (proof/'Proof.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (proof/'Program.cs').write_text('await Enginia360.Verification.Catalog.CatalogTypeNatureTests.Run("Host=127.0.0.1;Database=catalog_items;Username=postgres;Maximum Pool Size=10");')
            name='enginia360-type-nature-sdk-'+uuid.uuid4().hex[:10]
            try:
                result=subprocess.run(['docker','run','--name',name,'--rm','--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh','enginia360-backend:bp-phase2-sdk','-c','mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Proof.csproj -c Release /p:UseSharedCompilation=false /m:1'],capture_output=True,text=True,timeout=240)
                (artifacts/'native-last.log').write_text(result.stdout+result.stderr+'\nexit='+str(result.returncode)+'\n')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('PASS catalog type nature mapped HTTP',result.stdout)
                print(result.stdout)
            finally:
                subprocess.run(['docker','rm','-f',name],capture_output=True)
if __name__=='__main__':unittest.main()
