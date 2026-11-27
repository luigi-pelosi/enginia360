"""Prove PostgreSQL 18 reali, solo fixture sintetiche isolate.
TAX_DETERMINATION_DB_TESTS=1 python -m unittest tests.database.test_tax_determination -v
Nessuna connessione live; ogni gruppo usa un cluster etichettato senza rete/volumi.
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
from tests.database import test_taxmanagement_runtime as previous

ROOT = Path(__file__).resolve().parents[2]
PERMISSIONS = ['tax-rules.' + a for a in ('read', 'create', 'update', 'validate', 'publish', 'withdraw', 'install_templates')] + [
    'tax-determination.' + a for a in ('read', 'simulate', 'determine')]


@unittest.skipUnless(os.environ.get('TAX_DETERMINATION_DB_TESTS') == '1', 'Opt-in PostgreSQL isolato richiesto')
class TaxDeterminationTests(unittest.TestCase):
    sql = classmethod(previous.TaxManagementRuntimeTests.sql.__func__)
    scalar = previous.TaxManagementRuntimeTests.scalar
    reject = previous.TaxManagementRuntimeTests.reject

    @classmethod
    def setUpClass(cls):
        previous.TaxManagementRuntimeTests.setUpClass.__func__(cls)


    def dump(self, db):
        result = subprocess.run(['docker', 'exec', self.container, 'pg_dump', '-U', 'postgres', '--schema-only', db], capture_output=True, text=True, check=True, timeout=45)
        return '\n'.join(l for l in result.stdout.splitlines() if not l.startswith(('\\restrict ', '\\unrestrict ')))

    def setUp(self):
        self.tenant, self.other, self.actor, self.foreign_actor, self.global_actor, self.company, self.foreign_company = [str(uuid.uuid4()) for _ in range(7)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Prova'),('{self.other}','{self.other}','Altro');"
                 f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name,is_super_admin) VALUES('{self.actor}','{self.tenant}','{self.actor}','proof@example.test','SQL','Proof',false),('{self.foreign_actor}','{self.other}','{self.foreign_actor}','other@example.test','SQL','Other',false),('{self.global_actor}',NULL,'{self.global_actor}','global@example.test','Global','Admin',true);"
                 f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{self.company}','{self.tenant}','Prova'),('{self.foreign_company}','{self.other}','Altra');")
        self.country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='IT'")
        self.de = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.type = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")
        self.code = str(uuid.uuid4())
        self.sql(f"BEGIN;SET LOCAL ROLE enginia360_app;INSERT INTO taxmanagement.tax_codes(id,tenant_id,country_id,tax_type_id,code,name) VALUES('{self.code}','{self.tenant}','{self.country}','{self.type}','{self.code}','Prova');INSERT INTO taxmanagement.tax_code_versions(tenant_id,tax_code_id,rate,treatment,valid_from,created_by) VALUES('{self.tenant}','{self.code}',22,'TAXABLE','2026-11-26','{self.actor}');COMMIT;")
        self.root, self.ver = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql('SET ROLE enginia360_app;' + self.root_sql() + self.version_sql())

    def root_sql(self, root=None, **kw):
        data = dict(id=root or self.root, tenant_id=self.tenant, company_id=None, country_id=self.country,
                    tax_type_id=self.type, code=root or self.root, name='Regola')
        data.update(kw)
        return self.insert('tax_rules', data)

    @staticmethod
    def insert(table, data):
        return 'INSERT INTO taxmanagement.' + table + '(' + ','.join(data) + ') VALUES(' + ','.join(
            'NULL' if v is None else "'" + str(v).replace("'", "''") + "'" for v in data.values()) + ');'

    def version_sql(self, ver=None, root=None, **kw):
        data = dict(id=ver or self.ver, tenant_id=self.tenant, tax_rule_id=root or self.root, version_number=1,
                    tax_code_id=self.code, priority=100, operation_type='SALE', status='DRAFT',
                    legal_reference='DPR 633/1972 art. 7-bis', valid_from='2026-11-27', valid_to=None, created_by=self.actor)
        data.update(kw)
        return self.insert('tax_rule_versions', data)

    def condition_sql(self, field='item.nature', operator='EQUALS', value: object = 'GOOD', ver=None, **kw):
        data = dict(id=str(uuid.uuid4()), tenant_id=self.tenant, tax_rule_version_id=ver or self.ver,
                    field=field, operator=operator, value=json.dumps(value))
        data.update(kw)
        return self.insert('tax_rule_conditions', data)

    def publish(self, ver=None, actor=None):
        return f"UPDATE taxmanagement.tax_rule_versions SET status='PUBLISHED',published_by='{actor or self.actor}' WHERE id='{ver or self.ver}';"

    def withdraw(self, ver=None):
        return f"UPDATE taxmanagement.tax_rule_versions SET status='WITHDRAWN',withdrawn_by='{self.actor}' WHERE id='{ver or self.ver}';"

    def runtime(self, statement):
        return self.sql('BEGIN;SET LOCAL ROLE enginia360_app;' + statement + 'COMMIT;')

    def runtime_reject(self, statement, message=None):
        return self.reject('BEGIN;SET LOCAL ROLE enginia360_app;' + statement + 'COMMIT;', message)

    def another(self, **kw):
        root, ver = str(uuid.uuid4()), str(uuid.uuid4())
        self.runtime(self.root_sql(root) + self.version_sql(ver, root, **kw))
        return root, ver


    def test_02_fresh_final_schema_parity(self):
        fresh = 'fresh' + uuid.uuid4().hex[:10]
        self.sql('CREATE DATABASE ' + fresh + ';', database='postgres')
        self.sql(load_foundation_sql(), database=fresh)
        self.assertEqual(self.dump(fresh), self.dump('taxproof'))
        self.assertEqual(self.sql("SELECT count(*) FROM taxmanagement.tax_rules;SELECT count(*) FROM taxmanagement.tax_rule_versions;SELECT count(*) FROM taxmanagement.tax_rule_conditions;",database=fresh).stdout, '0\n0\n0\n')


    def test_03_acl_nonadmin_no_audit_select_no_delete_truncate_ddl(self):
        self.assertEqual(self.scalar("SELECT rolsuper||':'||rolcreatedb||':'||rolcreaterole FROM pg_roles WHERE rolname='enginia360_app'"), 'false:false:false')
        self.runtime_reject('SELECT * FROM foundation.audit_event;', 'permission denied')
        for stmt in (f"DELETE FROM taxmanagement.tax_rules WHERE id='{self.root}';", f"DELETE FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}';", 'TRUNCATE taxmanagement.tax_rule_conditions;', 'ALTER TABLE taxmanagement.tax_rules ADD COLUMN forbidden int;', 'UPDATE taxmanagement.tax_types SET is_active=false;'):
            with self.subTest(stmt=stmt): self.runtime_reject(stmt, 'permission denied' if not stmt.startswith('ALTER') else 'must be owner')
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_proc WHERE pronamespace='taxmanagement'::regnamespace AND proname LIKE 'guard_tax_rule%' AND prosecdef"), '0')

    def test_04_null_company_case_insensitive_uniqueness_and_scope(self):
        self.runtime_reject(self.root_sql(str(uuid.uuid4()), code=self.root.upper()), 'duplicate key')
        scoped = str(uuid.uuid4())
        self.runtime(self.root_sql(scoped, code=self.root, company_id=self.company))
        self.runtime_reject(self.root_sql(str(uuid.uuid4()), company_id=self.foreign_company), 'foreign key')
        self.runtime_reject(self.version_sql(str(uuid.uuid4()), tenant_id=self.other, version_number=2))
        self.runtime_reject(self.condition_sql(tenant_id=self.other))

    def test_05_root_identity_revision_and_draft_mutation(self):
        self.runtime(f"UPDATE taxmanagement.tax_rules SET name='Nuovo',version=2 WHERE id='{self.root}';")
        self.runtime_reject(f"UPDATE taxmanagement.tax_rules SET name='Stale',version=2 WHERE id='{self.root}';", 'root version')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rules WHERE id='{self.root}' AND version=1"), '0')
        for col, value in [('company_id', self.company), ('country_id', self.de), ('code', 'changed')]:
            self.runtime_reject(f"UPDATE taxmanagement.tax_rules SET {col}='{value}',version=3 WHERE id='{self.root}';", 'Identita regola')
        self.runtime(self.condition_sql() + f"DELETE FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id='{self.ver}';" + self.condition_sql(value='SERVICE') + f"UPDATE taxmanagement.tax_rule_versions SET priority=-2147483648 WHERE id='{self.ver}';")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id='{self.ver}'"), '1')

    def test_06_typed_registry_rejects_malformed_unknown_and_duplicates(self):
        cases = [('unknown.field','EQUALS','GOOD'), ('item.nature','LIKE','GOOD'), ('item.nature','EQUALS','NO'),
                 ('item.nature','EQUALS',True), ('item.nature','IN',[]), ('item.nature','IN',['GOOD','GOOD']),
                 ('item.nature','IN',['GOOD',True]), ('item.nature','IN','GOOD'), ('item.nature','IS_TRUE',None),
                 ('partner.actingAsTaxablePerson','EQUALS','true'), ('partner.actingAsTaxablePerson','IN',[True]),
                 ('partner.actingAsTaxablePerson','IS_TRUE',True), ('company.registrationCountry','EQUALS','bad'),
                 ('item.nature','EQUALS',{}), ('item.nature','EQUALS',None)]
        for field, op, value in cases:
            with self.subTest(field=field, op=op, value=value): self.runtime_reject(self.condition_sql(field,op,value))
        self.runtime(self.condition_sql() + self.condition_sql('partner.actingAsTaxablePerson','IS_TRUE',None))
        self.runtime_reject(self.condition_sql(), 'duplicate key')
        self.runtime_reject(self.condition_sql('item.nature','IN',['GOOD']*101))

    def test_07_reference_tenant_country_type_and_actor(self):
        other_class = str(uuid.uuid4())
        self.sql(self.insert('item_tax_classifications',dict(id=other_class,tenant_id=self.other,country_id=self.country,tax_type_id=self.type,code='OTHER',name='Altro')))
        self.runtime_reject(self.condition_sql('item.taxClassification','EQUALS',other_class), 'Riferimento condizione')
        self.runtime_reject(self.condition_sql('company.registrationCountry','EQUALS',str(uuid.uuid4())), 'Riferimento condizione')
        regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.runtime_reject(self.condition_sql('company.taxRegime','EQUALS',regime), 'Riferimento condizione')
        self.runtime_reject(self.version_sql(str(uuid.uuid4()), version_number=2, created_by=self.foreign_actor), 'Attore regola')
        self.runtime(self.version_sql(str(uuid.uuid4()), version_number=2, created_by=self.global_actor))
        foreign_code = str(uuid.uuid4())
        self.sql('BEGIN;' + self.insert('tax_codes',dict(id=foreign_code,tenant_id=self.tenant,country_id=self.de,tax_type_id=self.type,code='DE',name='DE')) + f"INSERT INTO taxmanagement.tax_code_versions(tenant_id,tax_code_id,rate,treatment,valid_from,created_by) VALUES('{self.tenant}','{foreign_code}',19,'TAXABLE','2026-11-26','{self.actor}');COMMIT;")
        self.runtime_reject(f"UPDATE taxmanagement.tax_rule_versions SET tax_code_id='{foreign_code}' WHERE id='{self.ver}';", 'TaxCode regola')
        self.runtime_reject(self.publish(actor=self.foreign_actor), 'Attore regola')

    def test_08_published_withdrawn_payload_conditions_and_history_immutable(self):
        self.runtime(self.condition_sql() + self.publish())
        for stmt in (f"UPDATE taxmanagement.tax_rule_versions SET priority=3 WHERE id='{self.ver}';", self.condition_sql(),
                     f"DELETE FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id='{self.ver}';",
                     f"UPDATE taxmanagement.tax_rule_conditions SET value='\"SERVICE\"' WHERE tax_rule_version_id='{self.ver}';"):
            with self.subTest(stmt=stmt): self.runtime_reject(stmt)
        before = self.scalar(f"SELECT (to_jsonb(v)-ARRAY['status','withdrawn_at','withdrawn_by'])::text FROM taxmanagement.tax_rule_versions v WHERE id='{self.ver}'")
        self.runtime(self.withdraw())
        self.assertEqual(before,self.scalar(f"SELECT (to_jsonb(v)-ARRAY['status','withdrawn_at','withdrawn_by'])::text FROM taxmanagement.tax_rule_versions v WHERE id='{self.ver}'"))
        self.runtime_reject(self.publish(), 'ritirata immutabile')
        self.runtime_reject(self.condition_sql(), 'ritirate immutabili')
        self.runtime_reject(f"UPDATE taxmanagement.tax_rule_versions SET valid_to='2026-12-31' WHERE id='{self.ver}';", 'ritirata immutabile')
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}' AND status='PUBLISHED' AND valid_from<='2026-11-27'"),'0')

    def test_09_controlled_predecessor_closure_deferred_and_no_partial_overlap(self):
        self.runtime(self.publish())
        successor = str(uuid.uuid4())
        self.runtime(self.version_sql(successor, version_number=2,valid_from='2027-01-01'))
        close = f"UPDATE taxmanagement.tax_rule_versions SET valid_to='2026-12-31' WHERE id='{self.ver}';"
        self.runtime_reject(close, 'richiede successore pubblicato')
        self.runtime_reject(self.publish(successor), 'Conflitto conservativo')
        self.runtime(close + self.publish(successor))
        self.assertEqual(self.scalar(f"SELECT valid_to FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}'"), '2026-12-31')
        self.runtime_reject(f"UPDATE taxmanagement.tax_rule_versions SET valid_to='2027-01-02' WHERE id='{self.ver}';", 'chiusura controllata')
        # Priorita diversa non elude l'esclusione per la stessa radice.
        overlap = str(uuid.uuid4())
        self.runtime(self.version_sql(overlap,version_number=3,priority=200,valid_from='2026-12-15',valid_to='2027-01-02'))
        self.runtime_reject(self.publish(overlap), 'exclusion constraint')

    def test_10_logical_and_exact_field_pointsets_and_negative_domains(self):
        self.runtime(self.condition_sql('item.nature','IN',['GOOD','SERVICE']) + self.condition_sql('item.nature','NOT_EQUALS','SERVICE') + self.publish())
        _, other = self.another()
        self.runtime(self.condition_sql('item.nature','EQUALS','SERVICE',ver=other) + self.publish(other))
        _, third = self.another()
        self.runtime(self.condition_sql('item.nature','EQUALS','GOOD',ver=third))
        self.runtime_reject(self.publish(third), 'Conflitto conservativo')
        _, bad = self.another(priority=101)
        self.runtime(self.condition_sql('item.nature','EQUALS','GOOD',ver=bad) + self.condition_sql('item.nature','NOT_IN',['GOOD'],ver=bad))
        self.runtime_reject(self.publish(bad), 'contraddittorie')
        # Due condizioni su campi diversi non provano disgiunzione.
        _, conservative = self.another()
        self.runtime(self.condition_sql('partner.actingAsTaxablePerson','IS_TRUE',None,ver=conservative))
        self.runtime_reject(self.publish(conservative), 'Conflitto conservativo')

    def test_11_same_priority_scope_company_shared_date_operation_and_priority(self):
        self.runtime(self.publish())
        scoped, ver = str(uuid.uuid4()), str(uuid.uuid4())
        self.runtime(self.root_sql(scoped,company_id=self.company) + self.version_sql(ver,scoped))
        self.runtime_reject(self.publish(ver), 'Conflitto conservativo')
        self.runtime(f"UPDATE taxmanagement.tax_rule_versions SET priority=101 WHERE id='{ver}';" + self.publish(ver))
        _, purchase = self.another(operation_type='PURCHASE')
        self.runtime(self.publish(purchase))
        _, future = self.another(valid_from='2027-01-01',valid_to='2027-01-31',priority=102)
        self.runtime(self.publish(future))
        _, adjacent = self.another(valid_from='2027-02-01',priority=102)
        self.runtime(self.publish(adjacent))
        _, inclusive = self.another(valid_from='2027-01-31',priority=102)
        self.runtime_reject(self.publish(inclusive), 'Conflitto conservativo')

    def test_12_unavailable_field_draft_allowed_publish_refused(self):
        self.runtime(self.condition_sql('partner.vatValidationStatus','EQUALS','VALID'))
        self.runtime_reject(self.publish(), 'non disponibile')
        self.assertEqual(self.scalar(f"SELECT status FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}'"),'DRAFT')

    def test_13_max_100_conditions_sequential_version_identity(self):
        # Campi reference validi, UUID tutti distinti, stesso campo negativo.
        countries = self.sql('SELECT id FROM foundation.country ORDER BY id LIMIT 101;').stdout.splitlines()
        self.assertEqual(len(countries),101)
        self.runtime(''.join(self.condition_sql('transaction.destinationCountry','NOT_EQUALS',v) for v in countries[:100]))
        self.runtime_reject(self.condition_sql('transaction.destinationCountry','NOT_EQUALS',countries[100]), 'Massimo 100')
        self.runtime_reject(self.version_sql(str(uuid.uuid4()),version_number=3), 'sequenziale')
        self.runtime_reject(f"UPDATE taxmanagement.tax_rule_versions SET version_number=2 WHERE id='{self.ver}';", 'Identita versione')

    def test_14_country_json_only_reference_guards_and_atomic_audit_failure(self):
        country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='AX'")
        self.runtime(self.condition_sql('transaction.destinationCountry','IN',[country]))
        for statement in (f"DELETE FROM foundation.country WHERE id='{country}';",f"UPDATE foundation.country SET iso_code='DE' WHERE id='{country}';",f"UPDATE foundation.country SET id='{uuid.uuid4()}' WHERE id='{country}';"):
            self.reject(statement, 'Identita paese')
        self.runtime_reject(self.publish() + f"UPDATE taxmanagement.tax_rules SET version=2 WHERE id='{self.root}';" +
                            f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{self.foreign_actor}','{self.tenant}',NULL,'tax-rules','{self.root}','{{}}');")
        self.assertEqual(self.scalar(f"SELECT status FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}'"),'DRAFT')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.tax_rules WHERE id='{self.root}'"),'1')


    def session(self, name, statement):
        proc = subprocess.Popen(['docker','exec','-i',self.container,'psql','-U','postgres','-X','-qAt','-v','ON_ERROR_STOP=1','-d','taxproof'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        proc.stdin.write(f"SET application_name='{name}';BEGIN;SET LOCAL ROLE enginia360_app;" + statement + '\n')
        proc.stdin.flush()
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def await_state(self,name,blocked=False):
        for _ in range(120):
            state = self.scalar(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{name}' AND " + ("wait_event_type='Lock'" if blocked else "state='idle in transaction'"))
            if state == '1': return
            time.sleep(.05)
        self.fail('Barrier SQL non raggiunta: ' + name)

    def release(self,proc):
        out,err = proc.communicate('COMMIT;\n',timeout=15)
        self.assertEqual(proc.returncode,0,out+err)
        return out

    def test_16_concurrent_equal_priority_publish_guard_without_application(self):
        _, second = self.another()
        a,b = 'publisher-a-'+uuid.uuid4().hex[:8], 'publisher-b-'+uuid.uuid4().hex[:8]
        holder = self.session(a,self.publish())
        self.await_state(a)
        contender = self.session(b,self.publish(second))
        self.await_state(b,blocked=True)
        self.release(holder)
        out,err = contender.communicate('COMMIT;\n',timeout=15)
        self.assertNotEqual(contender.returncode,0,out+err)
        self.assertIn('Conflitto conservativo',err)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rule_versions WHERE id IN ('{self.ver}','{second}') AND status='PUBLISHED'"),'1')

    def test_17_shared_ruleset_read_blocks_publish_and_withdraw_then_fresh_revocation(self):
        key = f"tax-determination:rules:{self.tenant}:{self.country}:{self.type}:SALE"
        for operation in ('publish','withdraw'):
            with self.subTest(operation=operation):
                a,b = 'reader-'+uuid.uuid4().hex[:8], 'writer-'+uuid.uuid4().hex[:8]
                reader = self.session(a,f"SELECT pg_advisory_xact_lock_shared(hashtextextended('{key}',0));SELECT id FROM taxmanagement.tax_rules WHERE id='{self.root}' FOR SHARE;")
                self.await_state(a)
                writer = self.session(b,self.publish() if operation=='publish' else self.withdraw())
                self.await_state(b,blocked=True)
                expected = 'DRAFT' if operation=='publish' else 'PUBLISHED'
                self.assertEqual(self.scalar(f"SELECT status FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}'"),expected)
                self.release(reader); self.release(writer)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rule_versions WHERE tax_rule_id='{self.root}' AND status='PUBLISHED'"),'0')

    def test_18_reference_pointset_negatives_and_bool_contradictions(self):
        self.runtime(self.condition_sql('company.registrationCountry','IN',[self.country,self.de]) + self.condition_sql('company.registrationCountry','NOT_EQUALS',self.de) + self.publish())
        _, second = self.another()
        self.runtime(self.condition_sql('company.registrationCountry','EQUALS',self.de,ver=second) + self.publish(second))
        _, negative = self.another(priority=101)
        self.runtime(self.condition_sql('company.registrationCountry','NOT_IN',[self.country,self.de],ver=negative) + self.publish(negative))
        _, another_negative = self.another(priority=101)
        self.runtime(self.condition_sql('company.registrationCountry','NOT_EQUALS',self.de,ver=another_negative))
        self.runtime_reject(self.publish(another_negative),'Conflitto conservativo')
        _, bad = self.another(priority=102)
        self.runtime(self.condition_sql('partner.actingAsTaxablePerson','IS_TRUE',None,ver=bad) + self.condition_sql('partner.actingAsTaxablePerson','NOT_EQUALS',True,ver=bad))
        self.runtime_reject(self.publish(bad),'contraddittorie')
    def test_19_uuid_canonicalization_strict_bounds_and_stale_snapshot_refusal(self):
        self.runtime(self.condition_sql('transaction.dispatchCountry','EQUALS',self.country.upper()))
        self.assertEqual(self.scalar(f"SELECT value#>>'{{}}' FROM taxmanagement.tax_rule_conditions WHERE tax_rule_version_id='{self.ver}'"),self.country)
        self.runtime_reject(self.condition_sql('transaction.dispatchCountry','IN',[self.country,self.country.upper()]),'duplicato')
        self.runtime_reject(self.condition_sql('transaction.dispatchCountry','EQUALS',self.country),'duplicate key')
        for value in ('infinity','-infinity'):
            self.runtime_reject(f"UPDATE taxmanagement.tax_rule_versions SET valid_from='{value}' WHERE id='{self.ver}';")
        for stmt in (f"UPDATE taxmanagement.tax_rule_versions SET legal_reference=E'\\t\\n' WHERE id='{self.ver}';",
                     f"UPDATE taxmanagement.tax_rule_versions SET priority=2147483648 WHERE id='{self.ver}';",
                     f"UPDATE taxmanagement.tax_rule_versions SET valid_to='2026-11-26' WHERE id='{self.ver}';"):
            self.runtime_reject(stmt)
        result=self.reject('BEGIN ISOLATION LEVEL REPEATABLE READ;SET LOCAL ROLE enginia360_app;'+self.publish()+'COMMIT;','READ COMMITTED')
        self.assertIn('TaxDetermination richiede',result.stderr)

    def test_20_audit_success_and_stale_expected_revision_atomicity(self):
        audit=f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{self.actor}','{self.tenant}','publish','tax-rules','{self.root}','{{\"version\":2}}');"
        self.runtime(self.publish()+f"UPDATE taxmanagement.tax_rules SET version=version+1 WHERE id='{self.root}' AND version=1;"+audit)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant}'"),'1')
        self.assertEqual(self.scalar(f"SELECT version FROM taxmanagement.tax_rules WHERE id='{self.root}'"),'2')
        # La revisione attesa e controllata PRIMA dei comandi figli sotto lock.
        self.assertEqual(self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.tax_rules SET name='Non deve cambiare',version=version+1 WHERE id='{self.root}' AND version=1 RETURNING id;").stdout.strip(),'')
        self.assertEqual(self.scalar(f"SELECT name FROM taxmanagement.tax_rules WHERE id='{self.root}'"),'Regola')
        self.runtime_reject(f"UPDATE foundation.audit_event SET details='{{}}' WHERE tenant_id='{self.tenant}';",'permission denied')
        self.runtime_reject(f"DELETE FROM foundation.audit_event WHERE tenant_id='{self.tenant}';",'permission denied')

    def test_21_concurrent_nonoverlapping_publish_and_company_disjointness(self):
        self.runtime(self.condition_sql('item.nature','EQUALS','GOOD'))
        _, second=self.another()
        self.runtime(self.condition_sql('item.nature','EQUALS','SERVICE',ver=second))
        a,b='disjoint-a-'+uuid.uuid4().hex[:8],'disjoint-b-'+uuid.uuid4().hex[:8]
        holder=self.session(a,self.publish());self.await_state(a)
        contender=self.session(b,self.publish(second));self.await_state(b,blocked=True)
        self.release(holder);self.release(contender)
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.tax_rule_versions WHERE id IN ('{self.ver}','{second}') AND status='PUBLISHED'"),'2')
        company2=str(uuid.uuid4())
        self.sql(f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{company2}','{self.tenant}','Altra propria');")
        for company in (self.company,company2):
            r,v=str(uuid.uuid4()),str(uuid.uuid4())
            self.runtime(self.root_sql(r,company_id=company)+self.version_sql(v,r,priority=200)+self.publish(v))
        for statement in (f"DELETE FROM taxmanagement.tax_rules WHERE id='{self.root}';",f"DELETE FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}';"):
            self.reject(statement,'non eliminabile')

    def test_22_closure_publish_failure_restores_predecessor_and_no_editor_lock_inversion(self):
        self.runtime(self.publish())
        successor=str(uuid.uuid4())
        self.runtime(self.version_sql(successor,version_number=2,valid_from='2027-01-01'))
        _, conflict=self.another(valid_from='2027-01-01',priority=101)
        self.runtime(self.publish(conflict))
        self.runtime(f"UPDATE taxmanagement.tax_rule_versions SET priority=101 WHERE id='{successor}';")
        close=f"UPDATE taxmanagement.tax_rule_versions SET valid_to='2026-12-31' WHERE id='{self.ver}';"
        self.runtime_reject(close+self.publish(successor),'Conflitto conservativo')
        self.assertEqual(self.scalar(f"SELECT valid_to IS NULL FROM taxmanagement.tax_rule_versions WHERE id='{self.ver}'"),'t')
        self.assertEqual(self.scalar(f"SELECT status FROM taxmanagement.tax_rule_versions WHERE id='{successor}'"),'DRAFT')
        # Un editor DRAFT che gia possiede il lock root non attende il ruleset
        # condiviso di una simulazione che poi vuole leggere la stessa radice.
        key=f"tax-determination:rules:{self.tenant}:{self.country}:{self.type}:SALE"
        name='shared-reader-'+uuid.uuid4().hex[:8]
        reader=self.session(name,f"SELECT pg_advisory_xact_lock_shared(hashtextextended('{key}',0));")
        self.await_state(name)
        self.runtime(f"SET LOCAL lock_timeout='500ms';SELECT id FROM taxmanagement.tax_rules WHERE id='{self.root}' FOR UPDATE;UPDATE taxmanagement.tax_rule_versions SET legal_reference='Modifica DRAFT' WHERE id='{successor}';")
        self.release(reader)
    def test_23_publication_requires_active_code_and_classification(self):
        classification=str(uuid.uuid4())
        self.runtime(self.insert('item_tax_classifications',dict(id=classification,tenant_id=self.tenant,country_id=self.country,tax_type_id=self.type,code='INACTIVE',name='Inattiva',is_active='false')) + self.condition_sql('item.taxClassification','EQUALS',classification))
        self.runtime_reject(self.publish(),'Riferimento condizione')
        self.runtime(f"UPDATE taxmanagement.item_tax_classifications SET is_active=true,version=version+1 WHERE id='{classification}';UPDATE taxmanagement.tax_codes SET is_active=false,version=version+1 WHERE id='{self.code}';")
        self.runtime_reject(self.publish(),'TaxCode regola fuori ambito o inattivo')
        self.runtime(f"UPDATE taxmanagement.tax_codes SET is_active=true,version=version+1 WHERE id='{self.code}';"+self.publish())
        # Il ritiro resta sempre possibile anche quando il riferimento e inattivo.
        self.runtime(f"UPDATE taxmanagement.tax_codes SET is_active=false,version=version+1 WHERE id='{self.code}';"+self.withdraw())


if __name__ == '__main__':
    unittest.main(verbosity=2)
