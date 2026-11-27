"""Real isolated PostgreSQL proof. COMPANY_TAX_DB_TESTS=1 python -m unittest tests.database.test_company_tax_runtime -v.
No live connections; disposable network-none tmpfs PostgreSQL, readonly source mount.
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

from database.sql_source import load_foundation_sql
from tests.database import test_taxmanagement_runtime as phase1

ROOT = Path(__file__).resolve().parents[2]
PERMISSIONS = ['tax-regimes.read'] + ['company-tax-configurations.' + a for a in
    ('read', 'create', 'activate', 'suspend', 'register', 'close', 'assign_regime', 'schedule_regime')]
TABLES = ('tax_regimes', 'company_tax_configurations', 'company_tax_registrations', 'company_tax_regime_profiles')


def insert(table, **values):
    return 'INSERT INTO taxmanagement.' + table + '(' + ','.join(values) + ') VALUES(' + ','.join(
        'NULL' if v is None else "'" + str(v).replace("'", "''") + "'" for v in values.values()) + ');'


@unittest.skipUnless(os.environ.get('COMPANY_TAX_DB_TESTS') == '1', 'Isolated PostgreSQL explicit opt-in required')
class CompanyTaxRuntimeTests(unittest.TestCase):
    sql = classmethod(phase1.TaxManagementRuntimeTests.sql.__func__)
    scalar = phase1.TaxManagementRuntimeTests.scalar
    reject = phase1.TaxManagementRuntimeTests.reject
    spawn = phase1.TaxManagementRuntimeTests.spawn
    wait_for = phase1.TaxManagementRuntimeTests.wait_for

    @classmethod
    def setUpClass(cls):
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)


    def setUp(self):
        self.tenant, self.other, self.actor, self.foreign_actor, self.global_actor, self.company, self.root, self.reg, self.profile = [str(uuid.uuid4()) for _ in range(9)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Proof'),('{self.other}','{self.other}','Other');"
            f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name,is_super_admin) VALUES"
            f"('{self.actor}','{self.tenant}','{self.actor}','sql@example.test','SQL','Proof',false),"
            f"('{self.foreign_actor}','{self.other}','{self.foreign_actor}','other@example.test','SQL','Other',false),"
            f"('{self.global_actor}',NULL,'{self.global_actor}','global@example.test','Global','Admin',true);"
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{self.company}','{self.tenant}','Proof');")
        self.country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='IT'")
        self.de = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.fr = self.scalar("SELECT id FROM foundation.country WHERE iso_code='FR'")
        self.type = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")
        self.regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.country}'")
        self.today = self.scalar("SELECT (statement_timestamp() AT TIME ZONE 'UTC')::date")
        # Same syntactically valid ID is safe across fresh test tenants.
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + self.initial_chain_sql() + 'COMMIT;')

    def root_sql(self, **overrides):
        v = dict(id=self.root, tenant_id=self.tenant, company_id=self.company, tax_type_id=self.type,
                 establishment_country_id=self.country, created_by=self.actor)
        v.update(overrides)
        return insert('company_tax_configurations', **v)

    def initial_chain_sql(self, **root):
        """A complete, historical foreign chain; new tests keep their own IDs.

        The final domain forbids committing an empty root. This valid one-day
        FR chain neither overlaps later IT registrations nor certifies ACTIVE
        coverage today, and does not invent an application revision increment.
        """
        registration, profile = str(uuid.uuid4()), str(uuid.uuid4())
        country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='FR'")
        regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{country}'")
        return (self.root_sql(**root) + self.registration_sql(id=registration,
            company_tax_configuration_id=root.get('id', self.root), country_id=country,
            tax_identifier='FR' + uuid.uuid4().hex[:2].upper().replace('I','A').replace('O','B') + ''.join(str(int(c,16) % 10) for c in uuid.uuid4().hex[:9]), registration_type='DIRECT_IDENTIFICATION',
            valid_from='2026-11-26', valid_to='2026-11-26') +
            self.profile_sql(id=profile, company_tax_registration_id=registration,
                tax_regime_id=regime, valid_from='2026-11-26', valid_to='2026-11-26'))

    def register_with_profile(self, registration=None, profile=None):
        """Persist a valid new registration atomically with its first regime."""
        registration = registration or {}
        profile = profile or {}
        country = registration.get('country_id', self.country)
        regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{country}'")
        defaults = dict(id=str(uuid.uuid4()),
            company_tax_registration_id=registration.get('id', self.reg), tax_regime_id=regime,
            valid_from=registration.get('valid_from', '2026-11-26'), valid_to=registration.get('valid_to'))
        defaults.update(profile)
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + self.registration_sql(**registration) +
            self.profile_sql(**defaults) + 'COMMIT;')

    def registration_sql(self, **overrides):
        v = dict(id=self.reg, tenant_id=self.tenant, company_tax_configuration_id=self.root, country_id=self.country,
            tax_identifier='IT00743110157', registration_type='DOMESTIC', valid_from='2026-11-26', valid_to=None, created_by=self.actor)
        v.update(overrides)
        return insert('company_tax_registrations', **v)

    def profile_sql(self, **overrides):
        v = dict(id=self.profile, tenant_id=self.tenant, company_tax_registration_id=self.reg, tax_regime_id=self.regime,
                 valid_from='2026-11-26', valid_to=None, created_by=self.actor)
        v.update(overrides)
        return insert('company_tax_regime_profiles', **v)

    def bump(self, status=None, expected=None):
        extra = '' if status is None else ",status='" + status + "'"
        where = '' if expected is None else ' AND version=' + str(expected)
        return f"UPDATE taxmanagement.company_tax_configurations SET version=version+1{extra} WHERE id='{self.root}'{where};"

    def chain(self, active=False):
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + self.registration_sql() + self.profile_sql() + self.bump('ACTIVE' if active else None) + 'COMMIT;')


    def test_02_fresh_schema_parity_without_automatic_company_data(self):
        db = 'fresh' + uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE ' + db + ';', database='postgres')
        self.sql(load_foundation_sql(), database=db)
        def dump(database):
            r = subprocess.run(['docker', 'exec', self.container, 'pg_dump', '-U', 'postgres', '--schema-only',
                '--schema=foundation', '--schema=masterdata', '--schema=taxmanagement', database], capture_output=True, text=True, timeout=40)
            self.assertEqual(r.returncode, 0, r.stderr)
            return '\n'.join(l for l in r.stdout.splitlines() if not l.startswith(('\\restrict ', '\\unrestrict ')))
        self.assertEqual(dump(db), dump('taxproof'))
        for t in TABLES[1:]:
            self.assertEqual(self.sql('SELECT count(*) FROM taxmanagement.' + t + ';', database=db).stdout, '0\n')


    def test_05_runtime_acl_readonly_catalog_insert_only_audit_no_ddl_or_truncate(self):
        self.assertEqual(self.scalar("SELECT has_table_privilege('enginia360_app','foundation.role_company','SELECT')"), 't')
        self.assertEqual(self.scalar("SELECT has_table_privilege('enginia360_app','foundation.audit_event','INSERT') AND NOT has_table_privilege('enginia360_app','foundation.audit_event','SELECT')"), 't')
        for t in TABLES:
            self.reject('SET ROLE enginia360_app;TRUNCATE taxmanagement.'+t+';', 'permission denied')
            self.reject('SET ROLE enginia360_app;ALTER TABLE taxmanagement.'+t+' ADD COLUMN attack text;', 'must be owner')
            self.reject('SET ROLE enginia360_app;DELETE FROM taxmanagement.'+t+';', 'permission denied')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_regimes SET is_active=false;', 'permission denied')
        self.reject('UPDATE taxmanagement.tax_regimes SET is_supported=false;', 'immutabile')
        self.reject('SET ROLE enginia360_app;SELECT * FROM foundation.audit_event;', 'permission denied')
        self.reject('SET ROLE enginia360_app;CREATE TABLE taxmanagement.attack(id int);', 'permission denied')
        self.reject("UPDATE foundation.country SET iso_code='XY' WHERE iso_code='IT';", 'immutabile')

    def test_06_root_identity_actor_version_status_and_safejs(self):
        for column, val in [('company_id', str(uuid.uuid4())), ('tenant_id', self.other), ('establishment_country_id', self.de), ('created_by', self.global_actor), ('tax_type_id', str(uuid.uuid4()))]:
            self.reject(f"UPDATE taxmanagement.company_tax_configurations SET {column}='{val}',version=version+1 WHERE id='{self.root}';", 'Identita configurazione')
        self.reject(f"UPDATE taxmanagement.company_tax_configurations SET version=version+2 WHERE id='{self.root}';", 'esattamente di uno')
        self.reject('BEGIN;'+self.bump('ACTIVE')+'COMMIT;', 'copertura fiscale')
        self.reject(self.root_sql(id=str(uuid.uuid4()), company_id=str(uuid.uuid4()), created_by=self.foreign_actor), 'Attore configurazione')
        self.reject(self.root_sql(id=str(uuid.uuid4()), company_id=str(uuid.uuid4()), version=0), 'versione uno')
        self.reject(self.root_sql(id=str(uuid.uuid4()), company_id=str(uuid.uuid4()), version=9007199254740992), 'versione uno')
        self.sql('SET ROLE enginia360_app;'+self.bump('SUSPENDED'))
        self.reject(self.bump('DRAFT'), 'DRAFT non ripristinabile')

    def test_07_identifier_policy_canonical_formal_only_and_unsupported(self):
        valid = [('IT','IT00743110157'), ('DE','DE136695976'), ('FR','FR40303265045'),
                 ('IT','IT00000000000'), ('DE','DE000000000'), ('FR','FRAB303265045')]
        for iso, identifier in valid:
            self.assertEqual(self.scalar(f"SET ROLE enginia360_app;SELECT taxmanagement.company_tax_identifier_valid('{iso}','{identifier}')"), 't')
        for iso, identifier in [('IT','it00743110157'), ('IT',' IT00743110157'), ('IT','IT00743110157 '), ('IT','IT007-43110157'), ('FR','FRIO303265045'), ('ES','ES123456789'), ('DE','DE1234')]:
            self.assertEqual(self.scalar(f"SELECT taxmanagement.company_tax_identifier_valid('{iso}','{identifier}')"), 'f')
        self.reject(self.registration_sql(tax_identifier='IT0074311015'), 'Identificativo IVA')
        self.reject(self.registration_sql(registration_type='DIRECT_IDENTIFICATION'), 'Tipo registrazione')
        self.reject(self.registration_sql(country_id=self.de, tax_identifier='DE136695976'), 'Tipo registrazione')
        self.reject(self.registration_sql(country_id=self.de, tax_identifier='DE136695976', registration_type='FISCAL_REPRESENTATIVE'), 'Rappresentante fiscale non supportato')
        self.register_with_profile(dict(country_id=self.de, tax_identifier='DE136695976', registration_type='DIRECT_IDENTIFICATION'))

    def test_08_registration_ownership_nonoverlap_immutability_and_finite_dates(self):
        self.reject(self.registration_sql(created_by=self.foreign_actor), 'Attore figlio')
        self.reject(self.registration_sql(tenant_id=self.other), 'Root fiscale fuori tenant')
        self.reject(self.registration_sql(valid_from='infinity'), 'check constraint')
        self.reject(self.registration_sql(valid_from='2026-12-02', valid_to='2026-12-01'), 'check constraint')
        self.register_with_profile(dict(valid_to='2026-12-31'))
        self.reject(self.registration_sql(id=str(uuid.uuid4()), valid_from='2026-12-31'), 'exclusion constraint')
        self.register_with_profile(dict(id=str(uuid.uuid4()), valid_from='2027-01-01'))
        self.reject(f"UPDATE taxmanagement.company_tax_registrations SET tax_identifier='IT12345678901' WHERE id='{self.reg}';", 'Payload figlio')
        self.reject(f"UPDATE taxmanagement.company_tax_registrations SET valid_to=NULL WHERE id='{self.reg}';", 'Solo chiusura')
        c, r = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{c}','{self.tenant}','Second');"+'BEGIN;'+self.initial_chain_sql(id=r, company_id=c)+'COMMIT;')
        self.reject(self.registration_sql(id=str(uuid.uuid4()), company_tax_configuration_id=r, valid_to='2026-12-30'), 'company_tax_identifier_no_overlap')

    def test_09_profiles_tenant_actor_bounds_regime_compatibility_and_no_overlap(self):
        self.register_with_profile(dict(valid_to='2027-12-31'), dict(valid_to='2026-11-26'))
        self.reject(self.profile_sql(created_by=self.foreign_actor), 'Attore figlio')
        self.reject(self.profile_sql(tenant_id=self.other), 'Root fiscale fuori tenant')
        de_regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.reject(self.profile_sql(tax_regime_id=de_regime), 'Regime incompatibile')
        self.reject(self.profile_sql(valid_from='2026-11-25', valid_to='2026-11-25'), 'Intervallo profilo')
        self.reject(self.profile_sql(valid_from='2026-11-27', valid_to='2028-01-01'), 'Intervallo profilo')
        self.sql('SET ROLE enginia360_app;'+self.profile_sql(valid_from='2026-11-27', valid_to='2027-12-31'))
        self.reject(self.profile_sql(id=str(uuid.uuid4()), valid_from='2027-12-31', valid_to='2027-12-31'), 'exclusion constraint')
        for active, supported in [(False, True), (True, False)]:
            prefix = 'BEGIN;ALTER TABLE taxmanagement.tax_regimes DISABLE TRIGGER tax_regimes_immutable;'
            prefix += f"UPDATE taxmanagement.tax_regimes SET is_active={str(active).lower()},is_supported={str(supported).lower()} WHERE id='{self.regime}';SET LOCAL ROLE enginia360_app;"
            self.reject(prefix+self.profile_sql(id=str(uuid.uuid4()), valid_from='2027-01-01')+'COMMIT;', 'Regime incompatibile')

    def test_10_deferred_atomic_closure_schedule_active_coverage_and_history(self):
        self.chain(active=True)
        tomorrow = self.scalar("SELECT ((statement_timestamp() AT TIME ZONE 'UTC')::date+1)")
        # Closing registration first creates intermediate invalid state, repaired in same transaction.
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.bump()+
            f"UPDATE taxmanagement.company_tax_registrations SET valid_to='{tomorrow}' WHERE id='{self.reg}';"
            f"UPDATE taxmanagement.company_tax_regime_profiles SET valid_to='{tomorrow}' WHERE id='{self.profile}';COMMIT;")
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"), '3')
        self.reject('BEGIN;'+self.bump()+f"UPDATE taxmanagement.company_tax_registrations SET valid_to='{self.today}' WHERE id='{self.reg}';COMMIT;", 'Intervallo profilo')
        # A catalogue deactivation is historically readable but ACTIVE mutation cannot certify coverage.
        self.reject('BEGIN;ALTER TABLE taxmanagement.tax_regimes DISABLE TRIGGER tax_regimes_immutable;'+
            f"UPDATE taxmanagement.tax_regimes SET is_active=false WHERE id='{self.regime}';"+
            self.bump()+'COMMIT;', 'copertura fiscale')
        self.sql('BEGIN;'+self.bump('SUSPENDED')+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE id='{self.profile}'"), '1')

    def test_11_concurrent_schedule_root_lock_stale_version_and_exclusion(self):
        self.chain(active=True)
        nextday = self.scalar("SELECT ((statement_timestamp() AT TIME ZONE 'UTC')::date+1)")
        # First session locks root then waits at a separate advisory gate. Second must block on root.
        key = int(uuid.uuid4().hex[:14], 16)
        gate = subprocess.Popen(['docker','exec','-i','-e','PGAPPNAME=company_gate',self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','taxproof'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup_gate():
            if gate.stdin is not None:
                gate.stdin.close(); gate.stdin = None
            if gate.poll() is None:
                gate.kill()
            gate.communicate(timeout=15)
        self.addCleanup(cleanup_gate)
        assert gate.stdin is not None
        gate.stdin.write(f'SELECT pg_advisory_lock({key});\n');gate.stdin.flush()
        self.wait_for('company_gate', event='ClientRead')
        where = f" WHERE id='{self.root}'"
        schedule = f"UPDATE taxmanagement.company_tax_regime_profiles SET valid_to='{self.today}' WHERE id='{self.profile}';"+self.profile_sql(id=str(uuid.uuid4()), valid_from=nextday)
        first = self.spawn('company_first', 'BEGIN;SET LOCAL ROLE enginia360_app;SELECT id FROM taxmanagement.company_tax_configurations'+where+' FOR UPDATE;'+f'SELECT pg_advisory_xact_lock({key});'+schedule+self.bump(expected=2)+'COMMIT;')
        self.wait_for('company_first', lock=True)
        close_command = f"""BEGIN;SET LOCAL ROLE enginia360_app;
DO $close$ DECLARE actual bigint; BEGIN
 SELECT version INTO actual FROM taxmanagement.company_tax_configurations WHERE id='{self.root}' FOR UPDATE;
 IF actual<>2 THEN RAISE EXCEPTION 'stale root version'; END IF;
 UPDATE taxmanagement.company_tax_registrations SET valid_to='{nextday}' WHERE id='{self.reg}';
 UPDATE taxmanagement.company_tax_regime_profiles SET valid_to='{nextday}' WHERE company_tax_registration_id='{self.reg}' AND (valid_to IS NULL OR valid_to>'{nextday}');
 UPDATE taxmanagement.company_tax_configurations SET version=version+1 WHERE id='{self.root}';
END $close$;COMMIT;"""
        second = self.spawn('company_second', close_command)
        self.wait_for('company_second', lock=True)
        gate.stdin.close();gate.stdin=None
        out, err = gate.communicate(timeout=15)
        self.assertEqual(gate.returncode, 0, out+err)
        a, ae = first.communicate(timeout=15); b, be = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, a+ae)
        self.assertNotEqual(second.returncode, 0, b+be)
        self.assertIn('stale root version', be)
        self.assertEqual(self.scalar(f"SELECT valid_to IS NULL FROM taxmanagement.company_tax_registrations WHERE id='{self.reg}'"), 't')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"), '3')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.reg}'"), '2')
        self.reject(self.profile_sql(id=str(uuid.uuid4()), valid_from=nextday), 'exclusion constraint')


    def test_13_finite_establishment_policy_foreign_only_activation_and_seed_snapshot(self):
        self.assertEqual(self.scalar("SELECT count(*) FROM taxmanagement.tax_regimes WHERE valid_from='2026-11-26' AND legal_reference IS NULL AND code='ORDINARY' AND is_supported AND is_active"), '3')
        country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='US'")
        if not country:
            country = str(uuid.uuid4())
            self.sql(f"INSERT INTO foundation.country(id,name,iso_code) VALUES('{country}','United States','US');")
        self.reject(self.root_sql(id=str(uuid.uuid4()), establishment_country_id=country), 'Paese stabilimento non supportato')
        self.reject('BEGIN;'+f"UPDATE foundation.country SET is_enabled=false WHERE id='{self.de}';"+
            self.root_sql(id=str(uuid.uuid4()), establishment_country_id=self.de)+'COMMIT;', 'Paese stabilimento non supportato')
        regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+
            self.registration_sql(country_id=self.de,tax_identifier='DE136695976',registration_type='DIRECT_IDENTIFICATION')+
            self.profile_sql(tax_regime_id=regime)+self.bump('ACTIVE')+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT status FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"), 'ACTIVE')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE company_tax_configuration_id='{self.root}' AND registration_type='DOMESTIC'"), '0')

    def test_14_future_profile_blocks_early_close_and_historical_inactive_close_allowed(self):
        self.chain()
        future = '2027-01-01'
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.bump()+
            f"UPDATE taxmanagement.company_tax_regime_profiles SET valid_to='2026-12-31' WHERE id='{self.profile}';"+
            self.profile_sql(id=str(uuid.uuid4()),valid_from=future)+'COMMIT;')
        self.reject('BEGIN;'+self.bump()+f"UPDATE taxmanagement.company_tax_registrations SET valid_to='2026-12-31' WHERE id='{self.reg}';COMMIT;", 'Intervallo profilo')
        # Catalog deactivation cannot erase history or prevent lawful shortening on DRAFT/SUSPENDED.
        self.sql('BEGIN;ALTER TABLE taxmanagement.tax_regimes DISABLE TRIGGER tax_regimes_immutable;'+
            f"UPDATE taxmanagement.tax_regimes SET is_active=false,is_supported=false WHERE id='{self.regime}';"+
            'SET LOCAL ROLE enginia360_app;'+self.bump('SUSPENDED')+
            f"UPDATE taxmanagement.company_tax_registrations SET valid_to='2027-12-31' WHERE id='{self.reg}';"+
            f"UPDATE taxmanagement.company_tax_regime_profiles SET valid_to='2027-12-31' WHERE company_tax_registration_id='{self.reg}' AND valid_from='{future}';RESET ROLE;"+
            f"UPDATE taxmanagement.tax_regimes SET is_active=true,is_supported=true WHERE id='{self.regime}';"+
            'ALTER TABLE taxmanagement.tax_regimes ENABLE TRIGGER tax_regimes_immutable;COMMIT;')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_regime_profiles WHERE company_tax_registration_id='{self.reg}'"), '2')

    def test_15_audit_failure_rolls_back_root_children_and_success_is_insert_only(self):
        event = str(uuid.uuid4())
        audit = f"INSERT INTO foundation.audit_event(id,actor_id,tenant_id,action,resource,record_id,details) VALUES('{event}','{self.actor}','{self.tenant}','create','company-tax-configurations','{self.root}',"
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+self.registration_sql()+self.profile_sql()+self.bump()+audit+"'[]'::jsonb);COMMIT;", 'audit_event_details_check')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"), '1')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE id='{self.reg}'"), '0')
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.registration_sql()+self.profile_sql()+self.bump()+audit+"'{}'::jsonb);COMMIT;")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM foundation.audit_event WHERE id='{event}'"), '1')
        self.reject(f"SET ROLE enginia360_app;SELECT * FROM foundation.audit_event WHERE id='{event}';", 'permission denied')


if __name__ == '__main__':
    unittest.main()
