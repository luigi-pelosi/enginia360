"""Real PostgreSQL 18 proof; opt in with COMPANY_TAX_REGISTRATION_DB_TESTS=1.
Only labelled network-none/tmpfs containers; never connects to a live database.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time
import unittest
import uuid

from tests.database import test_taxmanagement_runtime as phase1
from tests.database import test_company_tax_runtime as previous

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('COMPANY_TAX_REGISTRATION_DB_TESTS') == '1', 'Explicit isolated PostgreSQL opt-in required')
class RegistrationRequirementsTests(unittest.TestCase):
    sql = classmethod(previous.CompanyTaxRuntimeTests.sql.__func__)
    scalar = previous.CompanyTaxRuntimeTests.scalar
    reject = previous.CompanyTaxRuntimeTests.reject
    root_sql = previous.CompanyTaxRuntimeTests.root_sql
    registration_sql = previous.CompanyTaxRuntimeTests.registration_sql
    profile_sql = previous.CompanyTaxRuntimeTests.profile_sql
    bump = previous.CompanyTaxRuntimeTests.bump

    @classmethod
    def setUpClass(cls):
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)
        cls.legacy_tenant,cls.legacy_actor,cls.legacy_company,cls.legacy_root,cls.legacy_reg,cls.legacy_empty=[str(uuid.uuid4()) for _ in range(6)]
        # Imported legacy rows are synthesized on the FINAL schema, not by
        # replaying removed predecessors. Only INSERT completeness is disabled
        # during fixture creation; every final trigger is enabled for assertions.
        cls.sql("BEGIN;ALTER TABLE taxmanagement.company_tax_configurations DISABLE TRIGGER company_tax_root_require_initial_chain;ALTER TABLE taxmanagement.company_tax_registrations DISABLE TRIGGER company_tax_registration_require_initial_profile;" +
            f"INSERT INTO foundation.tenant(id,code,name) VALUES('{cls.legacy_tenant}','legacy','Legacy');"
            f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES('{cls.legacy_actor}','{cls.legacy_tenant}','legacy','legacy@example.test','Old','Actor');"
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{cls.legacy_company}','{cls.legacy_tenant}','Legacy');"
            f"INSERT INTO taxmanagement.company_tax_configurations(id,tenant_id,company_id,tax_type_id,establishment_country_id,created_by) SELECT '{cls.legacy_root}','{cls.legacy_tenant}','{cls.legacy_company}',t.id,c.id,'{cls.legacy_actor}' FROM taxmanagement.tax_types t CROSS JOIN foundation.country c WHERE t.code='VAT' AND c.iso_code='IT';"
            f"INSERT INTO taxmanagement.company_tax_registrations(id,tenant_id,company_tax_configuration_id,country_id,tax_identifier,registration_type,valid_from,created_by) SELECT '{cls.legacy_reg}','{cls.legacy_tenant}','{cls.legacy_root}',id,'IT00743110157','DOMESTIC','2026-11-26','{cls.legacy_actor}' FROM foundation.country WHERE iso_code='IT';"
            f"INSERT INTO taxmanagement.company_tax_regime_profiles(tenant_id,company_tax_registration_id,tax_regime_id,valid_from,created_by) SELECT '{cls.legacy_tenant}','{cls.legacy_reg}',r.id,'2026-11-26','{cls.legacy_actor}' FROM taxmanagement.tax_regimes r JOIN foundation.country c ON c.id=r.country_id WHERE c.iso_code='IT';"
            f"INSERT INTO taxmanagement.company_tax_registrations(id,tenant_id,company_tax_configuration_id,country_id,tax_identifier,registration_type,valid_from,created_by) SELECT '{cls.legacy_empty}','{cls.legacy_tenant}','{cls.legacy_root}',id,'DE136695976','DIRECT_IDENTIFICATION','2026-11-26','{cls.legacy_actor}' FROM foundation.country WHERE iso_code='DE';COMMIT;ALTER TABLE taxmanagement.company_tax_registrations ENABLE TRIGGER company_tax_registration_require_initial_profile;ALTER TABLE taxmanagement.company_tax_configurations ENABLE TRIGGER company_tax_root_require_initial_chain;")
        cls.sql(f"UPDATE foundation.\"user\" SET password_hash='synthetic-preserved-hash' WHERE id='{cls.legacy_actor}';"
            f"INSERT INTO foundation.role(tenant_id,code,name) VALUES('{cls.legacy_tenant}','preserve','Preserved role');"
            f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{cls.legacy_tenant}','company-tax-configurations.register','Preserved permission',true);"
            f"INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT '{cls.legacy_tenant}',r.id,p.id FROM foundation.role r CROSS JOIN foundation.permission p WHERE r.tenant_id='{cls.legacy_tenant}' AND p.tenant_id=r.tenant_id;"
            f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{cls.legacy_actor}','{cls.legacy_tenant}','create','company-tax-configurations','{cls.legacy_root}','{{\"preserve\":true}}');")


    @classmethod
    def data_snapshot(cls, database):
        tables=cls.sql("SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') AND c.relkind='r' ORDER BY 1;",database=database).stdout.splitlines()
        assert len(tables)==65, tables
        return cls.sql(''.join("SELECT '"+t+"',coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM "+t+' x;' for t in tables),database=database).stdout

    @classmethod
    def metadata_snapshot(cls, database):
        return cls.sql("""SELECT 'table',c.oid,c.relname,c.relowner,c.relacl,c.relrowsecurity,c.relforcerowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') AND c.relkind IN ('r','i','S') ORDER BY c.oid;
SELECT 'column',a.attrelid,a.attnum,to_jsonb(a) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') ORDER BY a.attrelid,a.attnum;
SELECT 'constraint',to_jsonb(c) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') ORDER BY c.oid;
SELECT 'function',to_jsonb(p) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') ORDER BY p.oid;
SELECT 'trigger',to_jsonb(t) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') ORDER BY t.oid;""",database=database).stdout


    def schema_dump(self, database):
        result=subprocess.run(['docker','exec',self.container,'pg_dump','-U','postgres','--schema-only',database],capture_output=True,text=True,check=True)
        return '\n'.join(line for line in result.stdout.splitlines() if not line.startswith(('\\restrict ','\\unrestrict ')))

    def setUp(self):
        self.tenant,self.actor,self.company,self.root,self.reg,self.profile=[str(uuid.uuid4()) for _ in range(6)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Proof');"
            f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES('{self.actor}','{self.tenant}','{self.actor}','proof@example.test','SQL','Proof');"
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{self.company}','{self.tenant}','Proof');")
        self.country=self.scalar("SELECT id FROM foundation.country WHERE iso_code='IT'")
        self.de=self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.type=self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")
        self.regime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.country}'")
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.root_sql()+self.registration_sql()+self.profile_sql()+'COMMIT;')

    def extra(self, **kw):
        return self.registration_sql(id=self.extra_id,country_id=self.de,tax_identifier='DE136695976',registration_type='DIRECT_IDENTIFICATION',**kw)

    def test_01_new_registration_without_profile_rejected_at_commit(self):
        self.extra_id=str(uuid.uuid4())
        audit=f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{self.actor}','{self.tenant}','register','company-tax-configurations','{self.root}','{{}}');"
        r=self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+self.bump()+audit+"SELECT 'precommit';COMMIT;",'Nuova registrazione richiede almeno un profilo')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant}'"),'0')
        self.assertIn('precommit',r.stdout)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE id='{self.extra_id}'"),'0')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'1')

    def test_02_atomic_success_multiple_temporal_profiles_and_one_application_revision(self):
        self.extra_id=str(uuid.uuid4())
        regime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        profiles=self.profile_sql(id=str(uuid.uuid4()),company_tax_registration_id=self.extra_id,tax_regime_id=regime,valid_from='2026-12-01',valid_to='2026-12-31')+self.profile_sql(id=str(uuid.uuid4()),company_tax_registration_id=self.extra_id,tax_regime_id=regime,valid_from='2027-01-01')
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+profiles+self.bump()+"SELECT 'precommit';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.extra_id}'"),'2')
        self.assertEqual(self.scalar(f"SELECT status||':'||version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'DRAFT:2')
        # Trigger locks but does NOT invent a version increment without an application bump.
        newprofile=str(uuid.uuid4())
        # Existing root: another foreign identifier has no domestic overlap.
        self.extra_id=str(uuid.uuid4())
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra().replace('DE136695976','DE123456789')+self.profile_sql(id=newprofile,company_tax_registration_id=self.extra_id,tax_regime_id=regime)+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'2')

    def test_03_grandfather_legacy_without_profile_update_and_later_assignment(self):
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.legacy_empty}'"),'0')
        # A valid NEW sibling must not force completion of the old empty one.
        fr=self.scalar("SELECT id FROM foundation.country WHERE iso_code='FR'")
        frregime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{fr}'")
        sibling=str(uuid.uuid4())
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.registration_sql(id=sibling,tenant_id=self.legacy_tenant,company_tax_configuration_id=self.legacy_root,country_id=fr,tax_identifier='FR40303265045',registration_type='DIRECT_IDENTIFICATION',created_by=self.legacy_actor)+self.profile_sql(id=str(uuid.uuid4()),tenant_id=self.legacy_tenant,company_tax_registration_id=sibling,tax_regime_id=frregime,created_by=self.legacy_actor)+f"UPDATE taxmanagement.company_tax_configurations SET version=version+1 WHERE id='{self.legacy_root}';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.legacy_empty}'"),'0')
        self.sql(f"BEGIN;SET LOCAL ROLE enginia360_app;UPDATE taxmanagement.company_tax_registrations SET valid_to='2027-12-31' WHERE id='{self.legacy_empty}';UPDATE taxmanagement.company_tax_configurations SET tax_code='Legacy remains editable',version=version+1 WHERE id='{self.legacy_root}';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.legacy_empty}'"),'0')
        regime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.profile_sql(id=str(uuid.uuid4()),tenant_id=self.legacy_tenant,company_tax_registration_id=self.legacy_empty,tax_regime_id=regime,valid_to='2027-12-31',created_by=self.legacy_actor)+f"UPDATE taxmanagement.company_tax_configurations SET version=version+1 WHERE id='{self.legacy_root}';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.legacy_empty}'"),'1')

    def test_04_fresh_final_schema_parity(self):
        from database.sql_source import load_foundation_sql
        db='fresh'+uuid.uuid4().hex[:12]
        self.sql('CREATE DATABASE '+db+';',database='postgres')
        self.sql(load_foundation_sql(),database=db)
        self.assertEqual(self.schema_dump(db),self.schema_dump('taxproof'))
        self.assertEqual(self.sql("SELECT count(*) FROM taxmanagement.company_tax_configurations;SELECT count(*) FROM taxmanagement.company_tax_registrations;SELECT count(*) FROM taxmanagement.company_tax_regime_profiles;",database=db).stdout,'0\n0\n0\n')


    def test_05_runtime_acl_trigger_and_no_privilege_broadening(self):
        self.assertEqual(self.scalar("SELECT has_function_privilege('enginia360_app','taxmanagement.require_company_tax_registration_initial_profile()','EXECUTE')"),'f')
        self.assertEqual(self.scalar("SELECT prosecdef FROM pg_proc WHERE oid='taxmanagement.require_company_tax_registration_initial_profile()'::regprocedure"),'f')
        self.assertEqual(self.scalar("SELECT tgtype||':'||tgdeferrable||':'||tginitdeferred||':'||tgenabled::text FROM pg_trigger WHERE tgrelid='taxmanagement.company_tax_registrations'::regclass AND tgname='company_tax_registration_require_initial_profile'"),'5:true:true:O')
        self.sql('SET ROLE enginia360_app;SELECT count(*) FROM taxmanagement.tax_regimes;')
        self.reject('SET ROLE enginia360_app;SELECT taxmanagement.require_company_tax_registration_initial_profile();','permission denied')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_regimes SET is_active=false;','permission denied')
        self.reject('SET ROLE enginia360_app;SELECT * FROM foundation.audit_event;','permission denied')
        self.reject(f"SET ROLE enginia360_app;DELETE FROM taxmanagement.company_tax_registrations WHERE id='{self.reg}';",'permission denied')

    def test_06_final_state_explicit_rollback_and_early_constraint_check(self):
        self.extra_id=str(uuid.uuid4())
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+self.bump()+'ROLLBACK;')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE id='{self.extra_id}'"),'0')
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+'SET CONSTRAINTS taxmanagement.company_tax_registration_require_initial_profile IMMEDIATE;','Nuova registrazione richiede almeno un profilo')
        # A coherent profile inserted later in the same transaction satisfies COMMIT.
        regime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+self.profile_sql(id=str(uuid.uuid4()),company_tax_registration_id=self.extra_id,tax_regime_id=regime)+self.bump()+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE id='{self.extra_id}'"),'1')


    def test_09_deferred_function_itself_locks_root_as_runtime_role(self):
        # A TEMP trigger harness bypasses the predecessor BEFORE guard, so a
        # lock timeout at COMMIT is attributable to the NEW deferred function.
        self.extra_id=str(uuid.uuid4())
        name='registration-root-lock-'+uuid.uuid4().hex[:8]
        holder=subprocess.Popen(['docker','exec','-i',self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','taxproof'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            holder.stdin.write(f"SET application_name='{name}';BEGIN;SET LOCAL ROLE enginia360_app;SELECT id FROM taxmanagement.company_tax_configurations WHERE id='{self.root}' FOR UPDATE;\n")
            holder.stdin.flush()
            for _ in range(100):
                if self.scalar(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND state='idle in transaction'")=='1': break
                time.sleep(.05)
            else: self.fail('root holder did not reach the barrier')
            probe="BEGIN;SET LOCAL lock_timeout='500ms';CREATE TEMP TABLE registration_probe (LIKE taxmanagement.company_tax_registrations INCLUDING DEFAULTS);GRANT INSERT ON registration_probe TO enginia360_app;CREATE CONSTRAINT TRIGGER registration_probe_check AFTER INSERT ON registration_probe DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.require_company_tax_registration_initial_profile();SET LOCAL ROLE enginia360_app;"
            rejected=self.reject(probe+self.extra().replace('taxmanagement.company_tax_registrations','pg_temp.registration_probe')+"SELECT 'precommit';COMMIT;",'lock timeout')
            self.assertIn('precommit',rejected.stdout)
            self.assertIn('require_company_tax_registration_initial_profile()',rejected.stderr)
            self.assertIn('FOR UPDATE',rejected.stderr)
        finally:
            out,err=holder.communicate('ROLLBACK;\n',timeout=15)
            self.assertEqual(holder.returncode,0,out+err)


    def test_final_invalid_registration_preserves_all_rows_metadata_and_application_version(self):
        before=self.data_snapshot('taxproof')
        metadata=self.metadata_snapshot('taxproof')
        self.extra_id=str(uuid.uuid4())
        audit=f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{self.actor}','{self.tenant}','register','company-tax-configurations','{self.root}','{{}}');"
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+self.extra()+self.bump()+audit+'COMMIT;', 'Nuova registrazione richiede almeno un profilo')
        self.assertEqual(self.data_snapshot('taxproof'),before)
        self.assertEqual(self.metadata_snapshot('taxproof'),metadata)
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'1')
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_trigger WHERE tgname IN ('company_tax_root_require_initial_chain','company_tax_registration_require_initial_profile') AND tgenabled='O' AND tgdeferrable AND tginitdeferred"),'2')


if __name__=='__main__': unittest.main()
