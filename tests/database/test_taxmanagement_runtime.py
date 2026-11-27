"""SQL reale su PostgreSQL Docker isolato, nessun volume o database esistente.

TAXMANAGEMENT_DB_TESTS=1 python -m unittest tests.database.test_taxmanagement_runtime -v
"""
from pathlib import Path
import os
import subprocess
import time
import unittest
import uuid

from database.sql_source import load_foundation_sql

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get('TAXMANAGEMENT_DB_TESTS') == '1', 'Richiede PostgreSQL Docker isolato esplicito')
class TaxManagementRuntimeTests(unittest.TestCase):
    @classmethod
    def sql(cls, statement, check=True, database='taxproof'):
        result = subprocess.run(['docker', 'exec', '-i', cls.container, 'psql', '-U', 'postgres', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', database], input=statement, text=True, capture_output=True, timeout=45)
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    @classmethod
    def setUpClass(cls):
        cls.container = 'enginia360-tax-sql-' + uuid.uuid4().hex[:12]
        subprocess.run(['docker', 'run', '-d', '--pull=never', '--name', cls.container, '--label', 'enginia360.scope=taxmanagement-sql-proof', '--network', 'none', '--tmpfs', '/var/lib/postgresql', '--tmpfs', '/var/run/postgresql', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-v', str(ROOT / 'database') + ':/schema:ro', os.environ.get('TAXMANAGEMENT_POSTGRES_IMAGE', 'postgres:18.6-alpine3.24')], check=True, capture_output=True)
        cls.addClassCleanup(lambda: subprocess.run(['docker', 'rm', '-f', cls.container], capture_output=True))
        logs = subprocess.CompletedProcess([], 0, '', '')
        for _ in range(200):
            logs = subprocess.run(['docker', 'logs', cls.container], capture_output=True, text=True)
            if 'PostgreSQL init process complete; ready for start up.' in logs.stdout:
                ready = subprocess.run(['docker', 'exec', cls.container, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'], capture_output=True)
                if ready.returncode == 0:
                    break
            time.sleep(.1)
        else:
            raise AssertionError('PostgreSQL isolato non pronto: ' + logs.stdout + logs.stderr)
        cls.sql('CREATE ROLE enginia360_app NOLOGIN; CREATE DATABASE taxproof;', database='postgres')
        cls.fresh_source = load_foundation_sql()
        cls.sql(cls.fresh_source)
        cls.legacy_tenant = str(uuid.uuid4())
        cls.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{cls.legacy_tenant}','existing','Existing'); INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{cls.legacy_tenant}','users.read','Old permission',true);")

    def setUp(self):
        self.tenant, self.other, self.actor, self.foreign_actor, self.global_actor = [str(uuid.uuid4()) for _ in range(5)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Proof'),('{self.other}','{self.other}','Other'); INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name,is_super_admin) VALUES('{self.actor}','{self.tenant}','{self.actor}','proof@example.test','SQL','Proof',false),('{self.foreign_actor}','{self.other}','{self.foreign_actor}','other@example.test','SQL','Other',false),('{self.global_actor}',NULL,'{self.global_actor}','global@example.test','Global','Admin',true);")
        self.country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='IT'")
        self.type = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")

    def scalar(self, sql):
        return self.sql(sql + ';').stdout.strip()

    def reject(self, sql, message=None):
        result = self.sql(sql, check=False)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        if message:
            self.assertIn(message, result.stderr)
        return result

    def root_sql(self, root=None, country=None, tax_type=None):
        root = root or str(uuid.uuid4())
        return root, f"INSERT INTO taxmanagement.tax_codes(id,tenant_id,tax_type_id,country_id,code,name) VALUES('{root}','{self.tenant}','{tax_type or self.type}','{country or self.country}','{root}','Proof');"

    def version_sql(self, root, start='2026-01-01', end=None, rate='22', treatment='TAXABLE', nature=None, actor=None, tenant=None):
        end_sql = 'NULL' if end is None else "'" + end + "'"
        nature_sql = 'NULL' if nature is None else "'" + nature + "'"
        return f"INSERT INTO taxmanagement.tax_code_versions(tenant_id,tax_code_id,rate,treatment,tax_nature_code_id,valid_from,valid_to,created_by) VALUES('{tenant or self.tenant}','{root}',{rate},'{treatment}',{nature_sql},'{start}',{end_sql},'{actor or self.actor}');"

    def create(self, **kwargs):
        root, insert = self.root_sql(country=kwargs.pop('country', None))
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + insert + self.version_sql(root, **kwargs) + 'COMMIT;')
        return root

    def test_fresh_baseline_world_countries_idempotent_seed_and_schema_parity(self):
        database = 'taxfresh_' + uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE ' + database + ';', database='postgres')
        seed = (ROOT / 'database/seeds/countries.sql').read_text()
        self.sql(load_foundation_sql(), database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM foundation.tenant;SELECT count(*) FROM foundation.country;SELECT count(*) FROM taxmanagement.tax_nature_codes;SELECT count(*) FROM taxmanagement.tax_codes;SELECT count(*) FROM foundation.role_permission;', database=database).stdout, '0\n249\n21\n0\n0\n')
        before = self.sql('SELECT row_to_json(c) FROM foundation.country c ORDER BY iso_code;', database=database).stdout
        self.sql(seed, database=database)
        self.assertEqual(self.sql('SELECT row_to_json(c) FROM foundation.country c ORDER BY iso_code;', database=database).stdout, before)
        self.assertEqual(self.sql('SELECT count(*) FROM taxmanagement.tax_nature_codes;', database=database).stdout, '21\n')
        self.sql("SELECT taxmanagement.seed_italian_natures(id) FROM foundation.country WHERE iso_code='IT';", database=database)
        self.assertEqual(self.sql('SELECT count(*) FROM taxmanagement.tax_nature_codes;', database=database).stdout, '21\n')
        def dump(db):
            result = subprocess.run(['docker','exec',self.container,'pg_dump','-U','postgres','--schema-only','--schema=foundation','--schema=masterdata','--schema=taxmanagement',db], text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return '\n'.join(line for line in result.stdout.splitlines() if not line.startswith(('\\restrict ', '\\unrestrict ')))
        self.assertEqual(dump(database), dump('taxproof'))


    def test_permission_catalog_stays_finite(self):
        for code in ['tax-codes.read','tax-codes.create','tax-codes.update','tax-codes.schedule','tax-codes.deactivate','tax-codes.reactivate','tax-codes.install_templates','tax-types.read','tax-nature-codes.read']:
            self.sql(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.tenant}','{code}','Proof',true);")
        for code in ['tax-codes.delete','tax-types.create','tax-nature-codes.update','tax-codes.anything','users.custom_action','catalog-items.delete']:
            with self.subTest(code=code):
                self.reject(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.tenant}','{code}','Proof',true);", 'permission_system_code_check')
        # I permessi personalizzati non di sistema restano ammessi, come prima.
        self.sql(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.tenant}','custom.operation','Custom',false);")

    def test_global_seed_without_implicit_tenant_permissions(self):
        self.assertEqual(self.scalar('SELECT count(*) FROM taxmanagement.tax_types'), '5')
        self.assertEqual(self.scalar('SELECT count(*) FROM taxmanagement.tax_types WHERE is_active'), '1')
        self.assertEqual(self.scalar("SELECT count(*) FROM taxmanagement.tax_nature_codes WHERE scheme='FATTURAPA'"), '21')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM foundation.permission WHERE tenant_id='{self.legacy_tenant}' AND code LIKE 'tax-%' AND is_system"), '0')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission'), '0')
        self.assertEqual(self.scalar(f"SELECT name FROM foundation.permission WHERE tenant_id='{self.legacy_tenant}' AND code='users.read'"), 'Old permission')

    def test_root_requires_version_at_commit_and_late_failure_rolls_back(self):
        root, insert = self.root_sql()
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;' + insert + 'COMMIT;', 'almeno una versione')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_codes WHERE id='{root}'"), '0')
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;' + insert + self.version_sql(root) + 'SELECT 1/0;COMMIT;', 'division by zero')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}'"), '0')

    def test_inclusive_overlap_and_adjacent_schedule(self):
        root = self.create(end='2026-06-30')
        self.reject('SET ROLE enginia360_app;' + self.version_sql(root, start='2026-06-30'), 'tax_code_versions_no_overlap')
        self.sql('SET ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01'))
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}'"), '2')

    def test_only_valid_to_can_shorten_no_payload_mutation_or_delete(self):
        root = self.create()
        where = f" WHERE tax_code_id='{root}';"
        self.sql("SET ROLE enginia360_app;UPDATE taxmanagement.tax_code_versions SET valid_to='2026-06-30'" + where)
        self.reject("SET ROLE enginia360_app;UPDATE taxmanagement.tax_code_versions SET valid_to='2026-12-31'" + where, 'soltanto la chiusura')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_code_versions SET valid_to=NULL' + where, 'soltanto la chiusura')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_code_versions SET rate=10' + where, 'permission denied')
        self.reject('UPDATE taxmanagement.tax_code_versions SET rate=10' + where, 'Payload versione fiscale immutabile')
        self.reject('SET ROLE enginia360_app;DELETE FROM taxmanagement.tax_code_versions' + where, 'permission denied')
        self.reject('DELETE FROM taxmanagement.tax_code_versions' + where, 'Versione fiscale immutabile')
        self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.tax_codes SET name='Renamed',is_active=false,version=version+1 WHERE id='{root}';")
        self.reject(f"UPDATE taxmanagement.tax_codes SET code='changed',version=version+1 WHERE id='{root}';", 'Identita fiscale immutabile')
        self.reject(f"UPDATE taxmanagement.tax_codes SET name='Again' WHERE id='{root}';", 'Incrementare la revisione')
        self.reject(f"DELETE FROM taxmanagement.tax_codes WHERE id='{root}';", 'Disattivare')

    def test_tenant_scope_actor_scope_and_global_admin(self):
        root = self.create(end='2026-06-30')
        self.reject('SET ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01', tenant=self.other), 'Radice fiscale del tenant mancante')
        self.reject('SET ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01', actor=self.foreign_actor), 'Attore fiscale fuori tenant')
        self.sql('SET ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01', actor=self.global_actor))
        for actor in [self.actor, self.global_actor]:
            self.sql(f"SET ROLE enginia360_app;INSERT INTO taxmanagement.tax_audit_events(tenant_id,tax_code_id,actor_id,action) VALUES('{self.tenant}','{root}','{actor}','scheduled');")
        self.reject(f"SET ROLE enginia360_app;INSERT INTO taxmanagement.tax_audit_events(tenant_id,tax_code_id,actor_id,action) VALUES('{self.tenant}','{root}','{self.foreign_actor}','bad');", 'Attore audit fuori tenant')
        self.reject(f"SET ROLE enginia360_app;INSERT INTO taxmanagement.tax_audit_events(tenant_id,tax_code_id,actor_id,action) VALUES('{self.other}','{root}','{self.foreign_actor}','bad');", 'foreign key')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_audit_events SET action=action;', 'permission denied')
        self.reject('UPDATE taxmanagement.tax_audit_events SET action=action;', 'immutabile')
        self.reject('SET ROLE enginia360_app;DELETE FROM taxmanagement.tax_audit_events;', 'permission denied')
        self.reject('DELETE FROM taxmanagement.tax_audit_events;', 'immutabile')
        self.reject('SET ROLE enginia360_app;SELECT * FROM foundation.audit_event;', 'permission denied')

    def test_all_italian_natures_exact_treatment_mapping(self):
        rows = self.sql('SELECT id,code FROM taxmanagement.tax_nature_codes ORDER BY code;').stdout.splitlines()
        for row in rows:
            nature, code = row.split('|')
            treatment = ('EXCLUDED' if code == 'N1' else 'OUT_OF_SCOPE' if code.startswith('N2.') else 'NON_TAXABLE' if code.startswith('N3.') else 'EXEMPT' if code == 'N4' else 'MARGIN' if code == 'N5' else 'REVERSE_CHARGE' if code.startswith('N6.') else 'OTHER_EU')
            with self.subTest(code=code):
                self.create(rate='0', treatment=treatment, nature=nature)
                root, insert = self.root_sql()
                self.reject('BEGIN;SET LOCAL ROLE enginia360_app;' + insert + self.version_sql(root, rate='0', treatment='ZERO_RATED', nature=nature) + 'COMMIT;')
        root, insert = self.root_sql()
        self.reject('BEGIN;' + insert + self.version_sql(root, rate='0', treatment='ZERO_RATED') + 'COMMIT;', 'FatturaPA incoerenti')
        self.reject('BEGIN;' + insert + self.version_sql(root, rate='0', treatment='EXEMPT') + 'COMMIT;', 'FatturaPA incoerenti')

    def test_catalog_runtime_readonly_and_seed_function_not_executable(self):
        self.reject("SET ROLE enginia360_app;UPDATE taxmanagement.tax_types SET name='Tampered';", 'permission denied')
        self.reject("SET ROLE enginia360_app;UPDATE taxmanagement.tax_nature_codes SET description='Tampered';", 'permission denied')
        self.reject("SET ROLE enginia360_app;INSERT INTO taxmanagement.tax_types(code,name) VALUES('NEW','New');", 'permission denied')
        self.reject(f"SET ROLE enginia360_app;SELECT taxmanagement.seed_italian_natures('{self.country}');", 'permission denied')
        self.assertEqual(self.scalar("SELECT has_schema_privilege('enginia360_app','taxmanagement','CREATE')"), 'f')
        self.reject(f"BEGIN;UPDATE foundation.country SET iso_code='VA' WHERE id='{self.country}';ROLLBACK;", 'Identita paese Company Tax immutabile')

    def test_code_uniqueness_is_case_insensitive_within_country_and_type(self):
        self.sql("INSERT INTO foundation.country(name,iso_code) VALUES('Germania','DE') ON CONFLICT DO NOTHING;")
        de = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        roots = []
        for country, code, duplicate in [(self.country, 'ScopedCode', False),
                                         (self.country, 'scopedcode', True),
                                         (de, 'scopedcode', False)]:
            root, insert = self.root_sql(country=country)
            insert = insert.replace("'" + root + "','Proof'", "'" + code + "','Proof'")
            statement = 'BEGIN;SET LOCAL ROLE enginia360_app;' + insert + self.version_sql(root) + 'COMMIT;'
            if duplicate:
                self.reject(statement, 'tax_codes_tenant_code_key')
                self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_codes WHERE id='{root}'"), '0')
            else:
                self.sql(statement)
                roots.append(root)
        self.assertEqual(self.scalar(f"SELECT count(DISTINCT country_id) FROM taxmanagement.tax_codes WHERE tenant_id='{self.tenant}' AND lower(code)='scopedcode'"), '2')

    def test_other_country_nature_period_and_rates(self):
        self.sql("INSERT INTO foundation.country(name,iso_code) VALUES('Germania','DE') ON CONFLICT DO NOTHING;")
        de = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.create(country=de, rate='0', treatment='ZERO_RATED')
        nature = str(uuid.uuid4())
        self.sql(f"INSERT INTO taxmanagement.tax_nature_codes(id,country_id,scheme,code,description,valid_from,valid_to) VALUES('{nature}','{de}','PROOF','P','Proof','2026-03-01','2026-09-30');")
        self.create(country=de, rate='0', treatment='EXEMPT', nature=nature, start='2026-03-01', end='2026-09-30')
        for country,start,end in [(self.country,'2026-03-01','2026-09-30'),(de,'2026-01-01','2026-09-30'),(de,'2026-03-01',None),(de,'2026-03-01','2026-10-01')]:
            root, insert = self.root_sql(country=country)
            self.reject('BEGIN;' + insert + self.version_sql(root, rate='0', treatment='EXEMPT', nature=nature, start=start, end=end) + 'COMMIT;', 'Natura fiscale incompatibile')
        self.create(country=de, rate='999.999999')
        for rate,treatment in [('0','TAXABLE'),('1','EXEMPT'),('-1','TAXABLE'),('1000','TAXABLE')]:
            root, insert = self.root_sql(country=de)
            self.reject('BEGIN;' + insert + self.version_sql(root, rate=rate, treatment=treatment) + 'COMMIT;')
        inactive = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='EXCISE'")
        root, insert = self.root_sql(tax_type=inactive)
        self.reject('BEGIN;' + insert + self.version_sql(root) + 'COMMIT;', 'Tipo fiscale non attivo')

    def spawn(self, name, sql):
        process = subprocess.Popen(['docker','exec','-i','-e','PGAPPNAME='+name,self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','taxproof'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert process.stdin is not None
        process.stdin.write(sql)
        process.stdin.close()
        process.stdin = None
        def cleanup():
            if process.poll() is None:
                process.kill()
                process.wait()
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
        self.addCleanup(cleanup)
        return process

    def wait_for(self, name, event=None, lock=False):
        condition = "wait_event_type='Lock'" if lock else f"wait_event='{event}'"
        for _ in range(150):
            if self.scalar(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND {condition}") == '1':
                return
            time.sleep(.02)
        self.fail('Barriera SQL non osservata: ' + name)

    def test_concurrent_overlap_distinct_connections_read_committed_and_repeatable_read(self):
        for isolation in ('READ COMMITTED', 'REPEATABLE READ'):
            with self.subTest(isolation=isolation):
                root = self.create(end='2026-06-30')
                winner = self.spawn('tax_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01') + 'SELECT pg_sleep(3);COMMIT;')
                self.wait_for('tax_winner', event='PgSleep')
                loser = self.spawn('tax_waiter', 'BEGIN ISOLATION LEVEL ' + isolation + ';SET LOCAL ROLE enginia360_app;' + self.version_sql(root, start='2026-08-01') + 'COMMIT;')
                self.wait_for('tax_waiter', lock=True)
                out, err = winner.communicate(timeout=15)
                self.assertEqual(winner.returncode, 0, out + err)
                out, err = loser.communicate(timeout=15)
                self.assertNotEqual(loser.returncode, 0, out + err)
                self.assertIn('tax_code_versions_no_overlap', err)
                self.assertNotIn('deadlock', err)
                self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}'"), '2')

    def test_concurrent_nonoverlap_commits_and_rolled_back_overlap_is_reusable(self):
        for rollback in (False, True):
            with self.subTest(rollback=rollback):
                root = self.create(end='2026-06-30')
                winner_end = None if rollback else '2026-12-31'
                loser_start = '2026-08-01' if rollback else '2027-01-01'
                winner = self.spawn('tax_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.version_sql(root, start='2026-07-01', end=winner_end) + 'SELECT pg_sleep(3);' + ('ROLLBACK;' if rollback else 'COMMIT;'))
                self.wait_for('tax_winner', event='PgSleep')
                loser = self.spawn('tax_waiter', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.version_sql(root, start=loser_start) + 'COMMIT;')
                self.wait_for('tax_waiter', lock=True)
                for process in (winner, loser):
                    out, err = process.communicate(timeout=15)
                    self.assertEqual(process.returncode, 0, out + err)
                self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}'"), '2' if rollback else '3')
                self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}' AND valid_from='{loser_start}'"), '1')

    def test_concurrent_schedule_loser_cannot_leave_partial_predecessor_closure(self):
        root = self.create()
        close = f"UPDATE taxmanagement.tax_code_versions SET valid_to='2026-06-30' WHERE tax_code_id='{root}' AND valid_from='2026-01-01';"
        winner = self.spawn('tax_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + close + self.version_sql(root, start='2026-07-01') + 'SELECT pg_sleep(3);COMMIT;')
        self.wait_for('tax_winner', event='PgSleep')
        close_loser = f"UPDATE taxmanagement.tax_code_versions SET valid_to='2026-04-30' WHERE tax_code_id='{root}' AND valid_from='2026-01-01';"
        loser = self.spawn('tax_waiter', 'BEGIN;SET LOCAL ROLE enginia360_app;' + close_loser + self.version_sql(root, start='2026-05-01') + 'COMMIT;')
        self.wait_for('tax_waiter', lock=True)
        out, err = winner.communicate(timeout=15)
        self.assertEqual(winner.returncode, 0, out + err)
        out, err = loser.communicate(timeout=15)
        self.assertNotEqual(loser.returncode, 0, out + err)
        self.assertIn('tax_code_versions_no_overlap', err)
        self.assertEqual(self.scalar(f"SELECT valid_to FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}' AND valid_from='2026-01-01'"), '2026-06-30')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tax_code_id='{root}'"), '2')


if __name__ == '__main__':
    unittest.main()
