"""Solo PostgreSQL effimero: CATALOG_TYPE_DELETION_DB_TESTS=1."""
from pathlib import Path
import os, re, subprocess, tempfile, time, unittest, uuid
from tests.database.test_catalog_natures_runtime import CatalogNaturesTests
from tests.database.test_catalog_items_runtime import CatalogItemsDatabaseTests
from database.sql_source import load_foundation_sql
ROOT=Path(__file__).resolve().parents[2]
# Frozen pg_get_constraintdef snapshot of published base84 + items9 + geography3.
# Deliberately independent of both the candidate SQL and the live target.
HISTORICAL_PERMISSION_CHECK = """CHECK (((NOT is_system) OR (code = ANY (ARRAY['permissions.read'::text, 'users.reset_password'::text, 'roles.assign'::text, 'groups.assign_users'::text, 'roles.assign_permissions'::text, 'purchasing-organizations.assign_scope'::text, 'business-partners.read'::text, 'business-partners.create'::text, 'business-partners.update'::text, 'business-partner-numbering.read'::text, 'business-partner-numbering.update'::text, 'roles.assign_companies'::text, 'business-partner-companies.read'::text, 'business-partner-companies.create'::text, 'business-partner-companies.update'::text, 'business-partner-companies.use_customer'::text, 'business-partner-companies.use_supplier'::text, 'payment-methods.read'::text, 'payment-methods.create'::text, 'payment-methods.update'::text, 'payment-terms.read'::text, 'payment-terms.create'::text, 'payment-terms.update'::text, 'payment-settings.read'::text, 'payment-settings.update'::text, 'payment-partner-defaults.read'::text, 'payment-partner-defaults.update'::text, 'payment-schedule.preview'::text, 'payment-resolution.read'::text, 'catalog-units.read'::text, 'catalog-units.create'::text, 'catalog-units.update'::text, 'catalog-categories.read'::text, 'catalog-categories.create'::text, 'catalog-categories.update'::text, 'catalog-categories.delete'::text, 'catalog-types.read'::text, 'catalog-types.create'::text, 'catalog-types.update'::text, 'catalog-numbering.read'::text, 'catalog-numbering.update'::text])) OR ((split_part(code, '.'::text, 1) = ANY (ARRAY['companies'::text, 'sites'::text, 'warehouse-types'::text, 'warehouses'::text, 'warehouse-locations'::text, 'users'::text, 'groups'::text, 'roles'::text, 'sales-organizations'::text, 'purchasing-organizations'::text])) AND (split_part(code, '.'::text, 2) = ANY (ARRAY['read'::text, 'create'::text, 'update'::text, 'delete'::text])) AND (code = ((split_part(code, '.'::text, 1) || '.'::text) || split_part(code, '.'::text, 2)))) OR (is_system AND (code = ANY (ARRAY['catalog-items.read'::text, 'catalog-items.create'::text, 'catalog-items.update'::text, 'catalog-items.activate'::text, 'catalog-items.deactivate'::text, 'catalog-items.archive'::text, 'catalog-brands.read'::text, 'catalog-brands.create'::text, 'catalog-brands.update'::text]))) OR (code = ANY (ARRAY['countries.read'::text, 'cities.read'::text, 'currencies.read'::text]))))"""
@unittest.skipUnless(os.environ.get('CATALOG_TYPE_DELETION_DB_TESTS')=='1','Database isolato esplicito')
class CatalogTypeDeletionTests(unittest.TestCase):
    sql=classmethod(CatalogItemsDatabaseTests.sql.__func__)
    setUp=CatalogItemsDatabaseTests.setUp
    scalar=CatalogItemsDatabaseTests.scalar
    unit=CatalogItemsDatabaseTests.unit
    reject=CatalogItemsDatabaseTests.reject
    @classmethod
    def setUpClass(cls):
        CatalogNaturesTests.setUpClass.__func__(cls)
    baseline=classmethod(CatalogNaturesTests.baseline.__func__)
    tearDownClass=classmethod(CatalogNaturesTests.tearDownClass.__func__)
    def test_unused_all_natures_and_all_status_relations(self):
        for kind in ['GOOD','INTANGIBLE','SERVICE','CHARGE']:
            id=str(uuid.uuid4())
            self.sql(f"SET ROLE enginia360_app;INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Unused','{kind}');DELETE FROM masterdata.catalog_item_type WHERE id='{id}';")
            self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_type WHERE id='{id}'"),'0')
        for status in ['ACTIVE','SUSPENDED','ARCHIVED']:
            id=str(uuid.uuid4());item=str(uuid.uuid4())
            self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Used','GOOD');INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{item}','Used','{id}','{self.category}','{self.pz}');UPDATE masterdata.catalog_item SET status='{status}',version=version+1 WHERE id='{item}';")
            self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_type WHERE id='{id}';",'Tipologia utilizzata')
        self.reject(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_unit_of_measure WHERE id='{self.kg}';",'permission denied')
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
    def test_concurrent_relation_both_orderings(self):
        def spawn(name,sql):
            p=subprocess.Popen(['docker','exec','-i','-e','PGAPPNAME='+name,self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','catalog_items'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            p.stdin.write(sql);p.stdin.close();p.stdin=None
            return p
        def wait(name,event):
            for _ in range(80):
                if self.sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND wait_event='{event}';").stdout.strip()=='1':return
                time.sleep(.025)
            self.fail('Barriera SQL non osservata: '+name+' '+event)
        for insert_first in (True,False):
            id=str(uuid.uuid4());item=str(uuid.uuid4())
            self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{id}','{self.t}','Race','GOOD');")
            insert=f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,category_id,base_uom_id) VALUES('{item}','{self.t}','{item}','Race','{id}','{self.category}','{self.pz}');"
            delete=f"SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||'{self.t}',0));SELECT id FROM masterdata.catalog_item_type WHERE id='{id}' FOR UPDATE;DELETE FROM masterdata.catalog_item_type WHERE id='{id}';"
            winner=spawn('deletion_winner','BEGIN;SET LOCAL ROLE enginia360_app;'+(insert if insert_first else delete)+'SELECT pg_sleep(3);COMMIT;')
            try:
                wait('deletion_winner','PgSleep')
                loser=spawn('deletion_loser','BEGIN;SET LOCAL ROLE enginia360_app;'+(delete if insert_first else insert)+'COMMIT;')
                try:
                    wait('deletion_loser','advisory')
                    out,err=winner.communicate(timeout=15);self.assertEqual(winner.returncode,0,out+err)
                    out,err=loser.communicate(timeout=15);self.assertNotEqual(loser.returncode,0,out+err)
                    self.assertIn('Tipologia utilizzata' if insert_first else 'Tipologia non attiva',err)
                finally:
                    if loser.poll() is None:loser.kill();loser.wait()
            finally:
                if winner.poll() is None:winner.kill();winner.wait()
            self.assertEqual(self.scalar(f"SELECT count(*) FROM masterdata.catalog_item_type WHERE id='{id}'"),'1' if insert_first else '0')
    def test_mapped_http_compiled_backend(self):
        with tempfile.TemporaryDirectory(prefix='type-deletion-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            proof=Path(folder)
            (proof/'Proof.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (proof/'Program.cs').write_text('await Enginia360.Verification.Catalog.CatalogTypeDeletionTests.Run("Host=127.0.0.1;Database=catalog_items;Username=postgres;Maximum Pool Size=10");')
            name='enginia360-type-deletion-sdk-'+uuid.uuid4().hex[:8]
            try:
                result=subprocess.run(['docker','run','--name',name,'--rm','--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh','enginia360-backend:bp-phase2-sdk','-c','mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Proof.csproj -c Release /p:UseSharedCompilation=false /m:1'],capture_output=True,text=True,timeout=240)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('PASS catalog type deletion mapped HTTP',result.stdout)
                print(result.stdout)
            finally:subprocess.run(['docker','rm','-f',name],capture_output=True)
if __name__=='__main__':unittest.main()
