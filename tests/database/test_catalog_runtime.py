"""PostgreSQL effimero senza rete/porte/volumi dati: nessun accesso al DB applicativo.
Esecuzione esplicita: CATALOG_DB_TESTS=1 python -m unittest tests.database.test_catalog_runtime -v
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import tempfile
import time
import unittest
import uuid

from database.sql_source import load_foundation_sql
ROOT = Path(__file__).resolve().parents[2]

@unittest.skipUnless(os.environ.get('CATALOG_DB_TESTS') == '1', 'Richiede PostgreSQL effimero esplicito')
class CatalogDatabaseTests(unittest.TestCase):
    @classmethod
    def sql(cls, text, check=True, database='catalog_proof'):
        r = subprocess.run(['docker','exec','-i',cls.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d',database], input=text, capture_output=True, text=True, timeout=45)
        if check and r.returncode: raise AssertionError(r.stdout+r.stderr)
        return r

    @classmethod
    def setUpClass(cls):
        cls.container = 'enginia360-catalog-sql-' + uuid.uuid4().hex[:10]
        subprocess.run(['docker','run','--rm','-d','--name',cls.container,'--network','none','--tmpfs','/var/lib/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust','-v',str(ROOT / 'database')+':/sql:ro','postgres:18.6-alpine3.24'],check=True,capture_output=True,text=True)
        try:
            for _ in range(60):
                r = subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True)
                if not r.returncode: break
                time.sleep(.25)
            else:
                raise RuntimeError('PostgreSQL finale non pronto su TCP')
            cls.sql('CREATE ROLE enginia360_app NOLOGIN; CREATE DATABASE catalog_proof;', database='postgres')
            cls.sql(load_foundation_sql())
        except BaseException:
            subprocess.run(['docker','rm','-f',cls.container],capture_output=True)
            raise

    @classmethod
    def tearDownClass(cls):
        subprocess.run(['docker','rm','-f',cls.container],check=True,capture_output=True)

    def setUp(self):
        self.tenant=str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Prova');")

    def seed(self): self.sql(f"SELECT masterdata.seed_catalog('{self.tenant}',NULL);")
    def reject(self, statement, code=None):
        result=self.sql('BEGIN;'+statement+'COMMIT;',check=False)
        self.assertNotEqual(result.returncode,0,result.stdout)
        if code: self.assertIn(code,result.stderr)

    def test_seed_is_audited_idempotent_and_does_not_overwrite(self):
        self.seed()
        self.assertEqual(self.sql(f"SELECT count(*) FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{self.tenant}'; SELECT count(*) FROM masterdata.catalog_item_type WHERE tenant_id='{self.tenant}'; SELECT count(*) FROM masterdata.catalog_category WHERE tenant_id='{self.tenant}'; SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant}';").stdout.strip(),'11\n2\n0\n13')
        self.sql(f"UPDATE masterdata.catalog_unit_of_measure SET name='Personalizzato',decimal_places=7,is_active=false WHERE tenant_id='{self.tenant}' AND code='G'; UPDATE masterdata.catalog_item_type SET name='Speciale',is_active=false WHERE tenant_id='{self.tenant}' AND kind='GOOD';")
        self.seed()
        self.assertEqual(self.sql(f"SELECT name||':'||decimal_places||':'||is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{self.tenant}' AND code='G'; SELECT name||':'||is_active FROM masterdata.catalog_item_type WHERE tenant_id='{self.tenant}' AND kind='GOOD'; SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant}';").stdout.strip(),'Personalizzato:7:false\nSpeciale:false\n13')

    def test_seed_respects_preexisting_inactive_custom_base(self):
        t=self.tenant
        self.sql(f"INSERT INTO masterdata.catalog_unit_of_measure(tenant_id,code,name,dimension,factor_to_base,decimal_places,is_base,is_active) VALUES('{t}','CUSTOM_KG','Massa personalizzata','MASS',1,4,true,false);")
        self.seed()
        self.assertEqual(self.sql(f"SELECT code||':'||is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{t}' AND dimension='MASS' ORDER BY code;").stdout.strip(),'CUSTOM_KG:false\nG:false')

    def test_units_exact_scale_immutable_definition_and_base_guard(self):
        self.seed();t=self.tenant
        for change in ("factor_to_base=2", "dimension='LENGTH'", 'is_base=false'):
            self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET {change} WHERE tenant_id='{t}' AND code='KG';")
        self.reject(f"UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE tenant_id='{t}' AND code='KG';",'Base attiva richiesta')
        self.reject(f"INSERT INTO masterdata.catalog_unit_of_measure(tenant_id,code,name,dimension,factor_to_base,decimal_places) VALUES('{t}','BAD','Bad','MASS',0.0000000000001,2);")
        self.reject(f"DELETE FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{t}' AND code='G';")
        self.reject(f"INSERT INTO masterdata.catalog_unit_of_measure(tenant_id,code,name,dimension,factor_to_base,decimal_places) VALUES('{t}','kg','Duplicato','MASS',1,2);")
        self.sql(f"BEGIN; UPDATE masterdata.catalog_unit_of_measure SET is_active=false WHERE tenant_id='{t}' AND dimension='MASS'; COMMIT;")

    def test_unused_types_can_change_nature_and_delete_but_stock_is_good_only(self):
        self.seed();t=self.tenant
        self.reject(f"UPDATE masterdata.catalog_item_type SET default_track_stock=true WHERE tenant_id='{t}' AND kind='SERVICE';")
        self.sql(f"UPDATE masterdata.catalog_item_type SET kind='CHARGE' WHERE tenant_id='{t}' AND kind='SERVICE';")
        self.assertEqual(self.sql(f"SELECT count(*) FROM masterdata.catalog_item_type WHERE tenant_id='{t}' AND kind='CHARGE';").stdout.strip(),'1')
        self.sql(f"SET ROLE enginia360_app;DELETE FROM masterdata.catalog_item_type WHERE tenant_id='{t}';")

    def test_categories_cycle_cross_tenant_and_leaf_delete(self):
        t=self.tenant;a=str(uuid.uuid4());b=str(uuid.uuid4());foreign=str(uuid.uuid4())
        self.sql(f"INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES('{a}','{t}','Radice'); INSERT INTO masterdata.catalog_category(id,tenant_id,name,parent_id) VALUES('{b}','{t}','Figlio','{a}'); INSERT INTO foundation.tenant(id,code,name) VALUES('{foreign}','{foreign}','Altro');")
        self.reject(f"UPDATE masterdata.catalog_category SET parent_id='{b}' WHERE id='{a}';",'Ciclo categorie')
        self.reject(f"INSERT INTO masterdata.catalog_category(tenant_id,name,parent_id) VALUES('{foreign}','Estraneo','{a}');")
        self.reject(f"DELETE FROM masterdata.catalog_category WHERE id='{a}';")
        self.sql(f"DELETE FROM masterdata.catalog_category WHERE id='{b}';DELETE FROM masterdata.catalog_category WHERE id='{a}';")

    def test_deep_tree_has_no_artificial_depth_limit(self):
        t=self.tenant
        self.sql(f"DO $$ DECLARE p uuid; n uuid; BEGIN FOR i IN 1..180 LOOP n:=gen_random_uuid(); INSERT INTO masterdata.catalog_category(id,tenant_id,name,parent_id) VALUES(n,'{t}','Nodo '||i,p); p:=n; END LOOP; END $$;")
        self.assertEqual(self.sql(f"SELECT count(*) FROM masterdata.catalog_category WHERE tenant_id='{t}';").stdout.strip(),'180')

    def test_concurrent_moves_cannot_form_cycle(self):
        a=str(uuid.uuid4());b=str(uuid.uuid4());t=self.tenant
        self.sql(f"INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES('{a}','{t}','A'),('{b}','{t}','B');")
        with ThreadPoolExecutor(max_workers=2) as pool:
            x=pool.submit(self.sql,f"BEGIN; UPDATE masterdata.catalog_category SET parent_id='{b}' WHERE id='{a}'; SELECT pg_sleep(0.4);COMMIT;",False)
            time.sleep(.1)
            y=pool.submit(self.sql,f"BEGIN; UPDATE masterdata.catalog_category SET parent_id='{a}' WHERE id='{b}';COMMIT;",False)
            results=[x.result(),y.result()]
        self.assertEqual(sorted(r.returncode==0 for r in results),[False,True])
        self.assertTrue(any('Ciclo categorie' in r.stderr for r in results))

    def test_transaction_rollback_includes_seed_audit(self):
        t=self.tenant
        self.reject(f"SELECT masterdata.seed_catalog('{t}',NULL); SELECT 1/0;")
        self.assertEqual(self.sql(f"SELECT count(*) FROM masterdata.catalog_unit_of_measure WHERE tenant_id='{t}';SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{t}';").stdout.strip(),'0\n0')

    def test_numbering_five_series_discriminator_and_used_guards(self):
        t=self.tenant
        self.sql(f"WITH s AS (INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding) SELECT '{t}',e,'AUTO',e,6 FROM unnest(ARRAY['BUSINESS_PARTNER','CATALOG_GOOD','CATALOG_INTANGIBLE','CATALOG_SERVICE','CATALOG_CHARGE']) e RETURNING *) INSERT INTO foundation.numbering_counter(series_id,tenant_id,next_number) SELECT id,tenant_id,1 FROM s;")
        self.reject(f"UPDATE foundation.numbering_series SET entity_type='CATALOG_GOOD' WHERE tenant_id='{t}' AND entity_type='BUSINESS_PARTNER';",'Identita immutabile')
        self.sql(f"UPDATE foundation.numbering_counter c SET used=true,next_number=2 FROM foundation.numbering_series s WHERE c.series_id=s.id AND s.tenant_id='{t}' AND s.entity_type='BUSINESS_PARTNER';")
        self.reject(f"UPDATE foundation.numbering_series SET prefix='OTHER' WHERE tenant_id='{t}' AND entity_type='BUSINESS_PARTNER';")
        self.assertEqual(self.sql(f"SELECT next_number FROM foundation.numbering_counter c JOIN foundation.numbering_series s ON s.id=c.series_id WHERE s.tenant_id='{t}' ORDER BY s.entity_type;").stdout.strip(),'2\n1\n1\n1\n1')

    def test_runtime_permissions_no_delete_units_or_types(self):
        t=self.tenant;self.seed()
        self.assertEqual(self.sql("SELECT has_table_privilege('enginia360_app','masterdata.catalog_unit_of_measure','DELETE'),has_table_privilege('enginia360_app','masterdata.catalog_item_type','DELETE'),has_table_privilege('enginia360_app','masterdata.catalog_category','DELETE');").stdout.strip(),'f|t|t')
        self.sql(f"SET ROLE enginia360_app;SELECT masterdata.seed_catalog('{t}',NULL);")

    def test_real_numbering_kernel_runtime(self):
        with tempfile.TemporaryDirectory(prefix='catalog-kernel-',dir=os.environ.get('TMPDIR','/root/.hermes/cache/scratch')) as folder:
            p=Path(folder)
            (p/'Kernel.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App" /><Reference Include="/catalog-build/bin/Release/net10.0/*.dll" /></ItemGroup></Project>')
            (p/'Program.cs').write_text('await Enginia360.Verification.Catalog.CatalogNumberingTests.Run("Host=127.0.0.1;Database=catalog_proof;Username=postgres;Maximum Pool Size=10");')
            command='mkdir -p /catalog-build; cp -a /input/. /catalog-build/; cd /catalog-build; dotnet build --no-restore -c Release /p:UseSharedCompilation=false /m:1 && cd /proof && dotnet run --project Kernel.csproj -c Release /p:UseSharedCompilation=false /m:1'
            runner=self.container+'-kernel'
            try:
                r=subprocess.run(['docker','run','--rm','--name',runner,'--network','container:'+self.container,'-v',str(ROOT/'backend')+':/input:ro','-v',folder+':/proof','--entrypoint','sh','enginia360-backend:bp-phase2-sdk','-c',command],capture_output=True,text=True,timeout=180)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                self.assertIn('PASS numbering kernel:',r.stdout)
                print(r.stdout)
            finally:
                subprocess.run(['docker','rm','-f',runner],capture_output=True)

    def test_final_baseline_fresh_install(self):
        database='fresh_'+uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE '+database+';',database='postgres')
        self.sql(load_foundation_sql(),database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM masterdata.catalog_item;SELECT count(*) FROM masterdata.catalog_item_company;SELECT count(*) FROM foundation.role_permission;SELECT count(*) FROM foundation.numbering_series;',database=database).stdout,'0\n0\n0\n0\n')

if __name__ == '__main__': unittest.main()
