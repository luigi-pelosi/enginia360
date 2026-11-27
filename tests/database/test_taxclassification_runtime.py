"""Focused real PostgreSQL 18.6 proofs; never connects to the live stack.

TAXCLASSIFICATION_DB_TESTS=1 python -m unittest tests.database.test_taxclassification_runtime -v
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
PERMISSIONS = [f'tax-{kind}-classifications.{action}' for kind in ('item', 'partner')
               for action in ('read', 'create', 'update', 'deactivate', 'reactivate', 'install_templates')]
PERMISSIONS += [f'tax-{kind}-profiles.{action}' for kind in ('item', 'partner')
                for action in ('read', 'assign', 'schedule')]


@unittest.skipUnless(os.environ.get('TAXCLASSIFICATION_DB_TESTS') == '1', 'Explicit isolated PostgreSQL opt-in required')
class TaxClassificationRuntimeTests(unittest.TestCase):
    sql = classmethod(phase1.TaxManagementRuntimeTests.sql.__func__)
    scalar = phase1.TaxManagementRuntimeTests.scalar
    reject = phase1.TaxManagementRuntimeTests.reject
    spawn = phase1.TaxManagementRuntimeTests.spawn
    wait_for = phase1.TaxManagementRuntimeTests.wait_for

    @classmethod
    def setUpClass(cls):
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)


    def setUp(self):
        self.tenant, self.other, self.actor, self.foreign_actor, self.global_actor = [str(uuid.uuid4()) for _ in range(5)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Proof'),('{self.other}','{self.other}','Other');"
                 f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name,is_super_admin) VALUES"
                 f"('{self.actor}','{self.tenant}','{self.actor}','proof@example.test','SQL','Proof',false),"
                 f"('{self.foreign_actor}','{self.other}','{self.foreign_actor}','other@example.test','SQL','Other',false),"
                 f"('{self.global_actor}',NULL,'{self.global_actor}','global@example.test','Global','Admin',true);")
        self.country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.fr = self.scalar("SELECT id FROM foundation.country WHERE iso_code='FR'")
        self.type = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")
        self.item, self.partner, item_type = [str(uuid.uuid4()) for _ in range(3)]
        self.sql(f"INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES('{item_type}','{self.tenant}','Proof','GOOD');"
                 f"INSERT INTO masterdata.catalog_item(id,tenant_id,code,name,item_type_id,status) VALUES('{self.item}','{self.tenant}','proof','Proof','{item_type}','SUSPENDED');"
                 f"INSERT INTO masterdata.business_partner(id,tenant_id,code,kind,legal_name) VALUES('{self.partner}','{self.tenant}','proof','ORGANIZATION','Proof');")
        self.classes = {kind: self.classification(kind) for kind in ('item', 'partner')}

    def classification(self, kind='item', **overrides):
        values = dict(id=str(uuid.uuid4()), tenant_id=self.tenant, country_id=self.country,
                      tax_type_id=self.type, code=str(uuid.uuid4()), name='Proof')
        values.update(overrides)
        self.sql('SET ROLE enginia360_app;INSERT INTO taxmanagement.' + kind + '_tax_classifications('
                 + ','.join(values) + ') VALUES(' + ','.join("'" + str(v).replace("'", "''") + "'" for v in values.values()) + ');')
        return values['id']

    def profile(self, kind='item', revision=1, start='2026-01-01', end=None, **overrides):
        subject = 'item_id' if kind == 'item' else 'business_partner_id'
        values = dict(tenant_id=self.tenant, **{subject: getattr(self, kind)}, country_id=self.country,
                      tax_type_id=self.type, **{kind + '_tax_classification_id': self.classes[kind]},
                      valid_from=start, valid_to=end, revision=revision, created_by=self.actor)
        values.update(overrides)
        return 'INSERT INTO taxmanagement.' + kind + '_tax_profiles(' + ','.join(values) + ') VALUES(' + ','.join(
            'NULL' if v is None else "'" + str(v) + "'" for v in values.values()) + ');'

    def stream_where(self, kind='item'):
        subject = 'item_id' if kind == 'item' else 'business_partner_id'
        return f"tenant_id='{self.tenant}' AND {subject}='{getattr(self, kind)}'"

    def token(self, kind='item'):
        return self.scalar(f'SELECT coalesce(max(revision),0) FROM taxmanagement.{kind}_tax_profiles WHERE ' + self.stream_where(kind))

    def api_lock(self, kind='item'):
        return f"SELECT pg_advisory_xact_lock(hashtextextended('tax-profile:{kind}:{self.tenant}:{getattr(self, kind)}',0));"

    def hold_gate(self):
        """Deterministic server-side barrier: no timing-sensitive pg_sleep race."""
        key = int(uuid.uuid4().hex[:14], 16)
        process = subprocess.Popen(['docker', 'exec', '-i', '-e', 'PGAPPNAME=class_gate', self.container,
                                    'psql', '-U', 'postgres', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', 'taxproof'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert process.stdin is not None
        process.stdin.write(f'SELECT pg_advisory_lock({key});\n')
        process.stdin.flush()
        self.wait_for('class_gate', event='ClientRead')
        def cleanup():
            if process.poll() is None:
                if process.stdin is not None:
                    process.stdin.close()
                    process.stdin = None
                process.communicate(timeout=15)
        self.addCleanup(cleanup)
        return process, f'SELECT pg_advisory_xact_lock({key});'

    def release_gate(self, process):
        process.stdin.close()
        process.stdin = None
        out, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, out + err)


    def test_02_fresh_schema_parity_and_no_automatic_profiles(self):
        db = 'fresh' + uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE ' + db + ';', database='postgres')
        self.sql(load_foundation_sql(), database=db)
        def dump(database):
            result = subprocess.run(['docker', 'exec', self.container, 'pg_dump', '-U', 'postgres', '--schema-only',
                                     '--schema=foundation', '--schema=masterdata', '--schema=taxmanagement', database], capture_output=True, text=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr)
            return '\n'.join(line for line in result.stdout.splitlines() if not line.startswith(('\\restrict ', '\\unrestrict ')))
        self.assertEqual(dump(db), dump('taxproof'))
        self.assertEqual(self.sql('SELECT count(*) FROM taxmanagement.item_tax_classifications;SELECT count(*) FROM taxmanagement.partner_tax_classifications;SELECT count(*) FROM taxmanagement.item_tax_profiles;SELECT count(*) FROM taxmanagement.partner_tax_profiles;', database=db).stdout, '0\n0\n0\n0\n')
        self.assertEqual(self.token(), '0')


    def test_05_classification_immutable_identity_versions_case_scope_and_country_guard(self):
        for kind in ('item', 'partner'):
            root = self.classes[kind]
            where = f" WHERE id='{root}';"
            table = f'taxmanagement.{kind}_tax_classifications'
            for column, value in [('id', str(uuid.uuid4())), ('tenant_id', self.other), ('country_id', self.fr), ('tax_type_id', str(uuid.uuid4())), ('code', 'New'), ('created_at', '2000-01-01')]:
                self.reject(f"UPDATE {table} SET {column}='{value}',version=version+1" + where, 'Identita classificazione immutabile')
            self.reject(f"UPDATE {table} SET name='Changed'" + where, 'Incrementare versione')
            self.sql(f"SET ROLE enginia360_app;UPDATE {table} SET name='Changed',description='Correction',version=version+1" + where)
            self.reject('DELETE FROM ' + table + where, 'Disattivare')
            self.reject('SET ROLE enginia360_app;DELETE FROM ' + table + where, 'permission denied')
            self.classification(kind, code='MiXeD')
            with self.assertRaises(AssertionError):
                self.classification(kind, code='mixed')
            self.classification(kind, code='mixed', country_id=self.fr)
            self.classification(kind, code='mixed', tenant_id=self.other)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_codes WHERE country_id='{self.country}'"), '0')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_nature_codes WHERE country_id='{self.country}'"), '0')
        self.reject(f"UPDATE foundation.country SET iso_code='ZZ' WHERE id='{self.country}';", 'Identita paese Company Tax immutabile')

    def test_06_templates_explicit_idempotent_preserve_customizations_and_scoped(self):
        for kind, expected in [('item', 10), ('partner', 3)]:
            call = f"SELECT taxmanagement.install_{kind}_classification_templates('{self.tenant}','{self.country}','{self.type}')"
            self.assertEqual(self.scalar('SET ROLE enginia360_app;' + call), str(expected))
            code = 'GENERAL_GOODS' if kind == 'item' else 'TAXABLE_PERSON'
            self.sql(f"UPDATE taxmanagement.{kind}_tax_classifications SET name='Custom',is_active=false,version=version+1 WHERE tenant_id='{self.tenant}' AND code='{code}';")
            self.assertEqual(self.scalar(call), '0')
            self.assertEqual(self.scalar(f"SELECT name||':'||is_active::text||':'||version FROM taxmanagement.{kind}_tax_classifications WHERE tenant_id='{self.tenant}' AND code='{code}'"), 'Custom:false:2')
            self.assertEqual(self.scalar(call.replace(self.country, self.fr)), str(expected))
            self.assertEqual(self.scalar(call.replace(self.tenant, self.other)), str(expected))
        self.assertEqual(self.token('item'), '0')
        self.assertEqual(self.token('partner'), '0')

    def test_07_only_active_vat_finite_dates_lengths_and_safe_revisions(self):
        excise = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='EXCISE'")
        for kind in ('item', 'partner'):
            for overrides in [dict(tax_type_id=excise), dict(code=' '), dict(name=' '), dict(code='x'*51), dict(name='x'*151), dict(version=2), dict(version=9007199254740992)]:
                with self.assertRaises(AssertionError):
                    self.classification(kind, **overrides)
            for overrides in [dict(revision=0), dict(revision=9007199254740992), dict(start='infinity'), dict(end='infinity'), dict(start='2026-07-01', end='2026-06-30')]:
                self.reject(self.profile(kind, **overrides))
            self.reject(f"SELECT taxmanagement.install_{kind}_classification_templates('{self.tenant}','{self.country}','{excise}');", 'Solo VAT')

    def test_08_tenant_subject_country_type_actor_isolation_and_global_admin(self):
        for kind in ('item', 'partner'):
            subject = 'item_id' if kind == 'item' else 'business_partner_id'
            foreign = self.classification(kind, tenant_id=self.other)
            other_country = self.classification(kind, country_id=self.fr)
            for overrides, message in [({subject: str(uuid.uuid4())}, 'Soggetto profilo'),
                                       (dict(tenant_id=self.other), 'Soggetto profilo'),
                                       ({kind+'_tax_classification_id': foreign}, 'Classificazione incompatibile'),
                                       ({kind+'_tax_classification_id': other_country}, 'Classificazione incompatibile'),
                                       (dict(created_by=self.foreign_actor), 'Attore profilo')]:
                self.reject('SET ROLE enginia360_app;' + self.profile(kind, **overrides), message)
            self.sql('SET ROLE enginia360_app;' + self.profile(kind, created_by=self.global_actor))
            self.assertEqual(self.token(kind), '1')

    def test_09_stream_token_spans_countries_and_requires_strict_sequence(self):
        for kind in ('item', 'partner'):
            french = self.classification(kind, country_id=self.fr)
            self.sql('SET ROLE enginia360_app;' + self.profile(kind))
            self.reject(self.profile(kind, revision=1, country_id=self.fr, **{kind+'_tax_classification_id': french}), 'Sequenza revisione')
            self.reject(self.profile(kind, revision=3, country_id=self.fr, **{kind+'_tax_classification_id': french}), 'Sequenza revisione')
            self.sql(self.profile(kind, revision=2, country_id=self.fr, **{kind+'_tax_classification_id': french}))
            self.assertEqual(self.token(kind), '2')
            self.assertEqual(self.scalar(f'SELECT version FROM masterdata.' + ('catalog_item' if kind == 'item' else 'business_partner') + f" WHERE id='{getattr(self, kind)}'"), '1')

    def test_10_inclusive_overlap_adjacent_schedule_payload_acl_and_inactive_history(self):
        for kind in ('item', 'partner'):
            table = 'taxmanagement.' + kind + '_tax_profiles'
            where = ' WHERE ' + self.stream_where(kind)
            self.sql('SET ROLE enginia360_app;' + self.profile(kind))
            self.reject(self.profile(kind, revision=2, start='2026-06-30'), kind+'_tax_profiles_no_overlap')
            root = self.classes[kind]
            self.sql(f"UPDATE taxmanagement.{kind}_tax_classifications SET is_active=false,version=version+1 WHERE id='{root}';")
            self.sql(f"SET ROLE enginia360_app;UPDATE {table} SET valid_to='2026-06-30'" + where)
            self.assertEqual(self.token(kind), '1')
            self.reject(self.profile(kind, revision=2, start='2026-07-01'), 'inattiva')
            self.assertEqual(self.scalar(f"SELECT count(*) FROM {table} p JOIN taxmanagement.{kind}_tax_classifications c ON c.id=p.{kind}_tax_classification_id WHERE p.tenant_id='{self.tenant}' AND DATE '2026-06-30' <@ daterange(p.valid_from,p.valid_to,'[]')"), '1')
            self.reject(f"UPDATE {table} SET valid_to=NULL" + where, 'Solo chiusura')
            self.reject(f"UPDATE {table} SET valid_to='2026-07-01'" + where, 'Solo chiusura')
            for assignment in ["revision=2", "valid_from='2026-01-02'", "created_at='2000-01-01'", f"created_by='{self.global_actor}'", f"{kind}_tax_classification_id='{uuid.uuid4()}'"]:
                self.reject(f'UPDATE {table} SET ' + assignment + where, 'Payload profilo')
                self.reject(f'SET ROLE enginia360_app;UPDATE {table} SET ' + assignment + where, 'permission denied')
            self.reject('DELETE FROM ' + table + where, 'Profilo fiscale immutabile')
            self.reject('SET ROLE enginia360_app;DELETE FROM ' + table + where, 'permission denied')
            self.sql(f"UPDATE taxmanagement.{kind}_tax_classifications SET is_active=true,version=version+1 WHERE id='{root}';")
            self.reject(self.profile(kind, revision=2, start='2026-06-30'), kind+'_tax_profiles_no_overlap')
            self.sql('SET ROLE enginia360_app;' + self.profile(kind, revision=2, start='2026-07-01'))
            self.assertEqual(self.token(kind), '2')

    def test_11_atomic_schedule_and_audit_failure_rolls_back_closure_insert_token(self):
        for kind in ('item', 'partner'):
            self.sql(self.profile(kind))
            close = f"UPDATE taxmanagement.{kind}_tax_profiles SET valid_to='2026-06-30' WHERE " + self.stream_where(kind)
            audit = f"INSERT INTO foundation.audit_event(tenant_id,actor_id,resource,record_id,action,details) VALUES('{self.tenant}','{self.actor}','{kind}_tax_profile','{getattr(self, kind)}','schedule','[]');"
            self.reject('BEGIN;SET LOCAL ROLE enginia360_app;' + self.api_lock(kind) + close + ';' + self.profile(kind, revision=2, start='2026-07-01') + audit + 'COMMIT;', 'audit_event_details_check')
            self.assertEqual(self.token(kind), '1')
            self.assertEqual(self.scalar(f'SELECT valid_to IS NULL FROM taxmanagement.{kind}_tax_profiles WHERE ' + self.stream_where(kind)), 't')
            self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + self.api_lock(kind) + close + ';' + self.profile(kind, revision=2, start='2026-07-01') + audit.replace("'[]'", "'{}'") + 'COMMIT;')
            self.assertEqual(self.token(kind), '2')
        self.reject('SET ROLE enginia360_app;SELECT * FROM foundation.audit_event;', 'permission denied')
        self.reject("SET ROLE enginia360_app;UPDATE foundation.audit_event SET action='bad';", 'permission denied')
        self.reject('SET ROLE enginia360_app;DELETE FROM foundation.audit_event;', 'permission denied')

    def test_12_concurrent_assign_same_token_single_winner_all_isolations(self):
        for kind in ('item', 'partner'):
            for isolation in ('READ COMMITTED', 'REPEATABLE READ'):
                if self.token(kind) != '0':
                    # A new subject is needed because streams are never deleted.
                    self.setUp()
                gate, barrier = self.hold_gate()
                winner = self.spawn('class_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.profile(kind) + barrier + 'COMMIT;')
                self.wait_for('class_winner', lock=True)
                loser = self.spawn('class_waiter', 'BEGIN ISOLATION LEVEL ' + isolation + ';SET LOCAL ROLE enginia360_app;' + self.profile(kind) + 'COMMIT;')
                self.wait_for('class_waiter', lock=True)
                self.release_gate(gate)
                out, err = winner.communicate(timeout=12)
                self.assertEqual(winner.returncode, 0, out + err)
                out, err = loser.communicate(timeout=12)
                self.assertNotEqual(loser.returncode, 0, out + err)
                self.assertNotIn('deadlock', err)
                self.assertEqual(self.token(kind), '1')

    def test_13_concurrent_schedule_stale_loser_cannot_partially_close(self):
        for kind in ('item', 'partner'):
            self.sql(self.profile(kind))
            table = 'taxmanagement.' + kind + '_tax_profiles'
            close = f"UPDATE {table} SET valid_to='2026-06-30' WHERE " + self.stream_where(kind) + ' AND revision=1;'
            gate, barrier = self.hold_gate()
            winner = self.spawn('class_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.api_lock(kind) + close + self.profile(kind, revision=2, start='2026-07-01') + barrier + 'COMMIT;')
            self.wait_for('class_winner', lock=True)
            loser = self.spawn('class_waiter', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.api_lock(kind) + close.replace('2026-06-30', '2026-04-30') + self.profile(kind, revision=2, start='2026-05-01') + 'COMMIT;')
            self.wait_for('class_waiter', lock=True)
            self.release_gate(gate)
            out, err = winner.communicate(timeout=12)
            self.assertEqual(winner.returncode, 0, out + err)
            out, err = loser.communicate(timeout=12)
            self.assertNotEqual(loser.returncode, 0, out + err)
            self.assertNotIn('deadlock', err)
            self.assertEqual(self.scalar(f'SELECT valid_to FROM {table} WHERE ' + self.stream_where(kind) + ' AND revision=1'), '2026-06-30')
            self.assertEqual(self.token(kind), '2')

    def test_14_concurrent_nonoverlap_revision_allocation_and_abort_reuses_token(self):
        for kind in ('item', 'partner'):
            gate, barrier = self.hold_gate()
            winner = self.spawn('class_winner', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.profile(kind, end='2026-06-30') + barrier + 'COMMIT;')
            self.wait_for('class_winner', lock=True)
            next_revision = f"(SELECT coalesce(max(revision),0)+1 FROM taxmanagement.{kind}_tax_profiles WHERE " + self.stream_where(kind) + ')'
            insert = self.profile(kind, revision=2, start='2026-07-01', end='2027-12-31').replace("'2'", next_revision)
            loser = self.spawn('class_waiter', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.api_lock(kind) + insert + 'COMMIT;')
            self.wait_for('class_waiter', lock=True)
            self.release_gate(gate)
            for p in (winner, loser):
                out, err = p.communicate(timeout=12)
                self.assertEqual(p.returncode, 0, out + err)
            self.assertEqual(self.token(kind), '2')
            self.reject('BEGIN;' + self.profile(kind, revision=3, start='2028-01-01') + 'SELECT 1/0;COMMIT;', 'division by zero')
            self.assertEqual(self.token(kind), '2')
            self.sql(self.profile(kind, revision=3, start='2028-01-01'))
            self.assertEqual(self.token(kind), '3')

    def test_15_concurrent_deactivation_blocks_new_assignment_not_historical_resolution(self):
        for kind in ('item', 'partner'):
            root = self.classes[kind]
            gate, barrier = self.hold_gate()
            updater = self.spawn('class_winner', f"BEGIN;SET LOCAL ROLE enginia360_app;UPDATE taxmanagement.{kind}_tax_classifications SET is_active=false,version=version+1 WHERE id='{root}';" + barrier + 'COMMIT;')
            self.wait_for('class_winner', lock=True)
            assigner = self.spawn('class_waiter', 'BEGIN;SET LOCAL ROLE enginia360_app;' + self.profile(kind) + 'COMMIT;')
            self.wait_for('class_waiter', lock=True)
            self.release_gate(gate)
            out, err = updater.communicate(timeout=12)
            self.assertEqual(updater.returncode, 0, out + err)
            out, err = assigner.communicate(timeout=12)
            self.assertNotEqual(assigner.returncode, 0, out + err)
            self.assertIn('inattiva', err)
            self.assertEqual(self.token(kind), '0')


if __name__ == '__main__':
    unittest.main()
