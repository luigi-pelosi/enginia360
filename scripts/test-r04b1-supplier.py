#!/usr/bin/env python3
"""R04.b.1 isolated PostgreSQL acceptance: supplier role in the shared master, Giobby vendor identity in a company extension.

Synthetic data only. No ERP traffic, no purchase request, no new delegable grant.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration_tests', ROOT/'scripts/test-r00-migrations.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
MIGRATION = ROOT/'database/runtime/migrations/0027_supplier_role.sql'
OWNER_TOOL = ROOT/'scripts/owner-supplier-vendor-identity.py'


def load_tool():
    tool = importlib.util.spec_from_file_location('owner_vendor', OWNER_TOOL)
    module = importlib.util.module_from_spec(tool)
    tool.loader.exec_module(module)
    return module


class OwnerInputTests(unittest.TestCase):
    def good(self):
        value = {key: str(uuid.uuid4()) for key in ('commandId', 'tenantId', 'legalEntityId', 'counterpartyId', 'actorMembershipId', 'verificationReference')}
        value.update(expectedRevision=0, vendorId='4711', vendorName='Synthetic Supplier S.r.l.')
        return value

    def test_owner_tool_requires_the_exact_closed_input(self):
        module = load_tool()
        good = self.good()
        self.assertEqual(module.validate(good), good)
        for bad in ({}, dict(good, extra='x'), dict(good, vendorId=''), dict(good, vendorId=' 4711'), dict(good, vendorId='a b'), dict(good, vendorId='x'*65),
                    dict(good, vendorName='   '), dict(good, vendorName='x'*201), dict(good, vendorName='bad\nname'), dict(good, expectedRevision=True),
                    dict(good, expectedRevision=-1), dict(good, legalEntityId=str(uuid.UUID(int=0))), dict(good, counterpartyId=None),
                    dict(good, actorMembershipId='not-a-uuid'), dict(good, vendorId=4711), dict(good, tenantId=good['tenantId'].upper())):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError, TypeError)):
                    module.validate(bad)

    def test_owner_tool_accepts_only_the_opaque_id_and_exact_name_hint(self):
        module = load_tool()
        self.assertEqual(set(self.good()), module.FIELDS)

    def test_migration_is_append_only_and_declares_no_app_write_path_to_extension(self):
        self.assertTrue(MIGRATION.exists(), 'migration 0027 is absent')
        text = MIGRATION.read_text()
        self.assertNotIn('GRANT INSERT', text)
        self.assertNotIn('GRANT UPDATE', text)
        self.assertNotIn('common_edit_permissions VALUES', text)


@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated PostgreSQL opt-in required')
class SupplierSqlTests(unittest.TestCase):
    setUp = legacy.PostgreSqlTests.setUp
    tearDown = legacy.PostgreSqlTests.tearDown
    sql = legacy.PostgreSqlTests.sql
    start_migration = legacy.PostgreSqlTests.start_migration
    migrate = legacy.PostgreSqlTests.migrate

    def world(self, companies=2, local=True):
        ids = {key: str(uuid.uuid4()) for key in ('tenant', 'actor', 'member', 'source', 'profile', 'proof', 'record', 'other_record')}
        ids['companies'] = [str(uuid.uuid4()) for _ in range(companies)]
        grants = ''.join(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{ids['member']}','{ids['tenant']}','{c}','counterparties.read',NULL,NULL);" for c in ids['companies'])
        values = ','.join(f"('{c}','{ids['tenant']}','Company {i}')" for i, c in enumerate(ids['companies']))
        self.sql(f'''INSERT INTO organization_access.tenants VALUES ('{ids['tenant']}','Synthetic supplier');
            INSERT INTO organization_access.legal_entities VALUES {values};
            INSERT INTO organization_access.external_identity_bindings VALUES ('{ids['actor']}','https://synthetic.test','subject-{ids['actor']}');
            INSERT INTO organization_access.memberships VALUES ('{ids['member']}','{ids['tenant']}','{ids['actor']}');
            {grants}
            INSERT INTO organization_access.common_edit_permissions VALUES ('{ids['member']}','{ids['tenant']}');
            INSERT INTO counterparties.counterparties VALUES ('{ids['record']}','{ids['tenant']}','Supplier candidate','SYNTHETIC-1','Synthetic office');
            INSERT INTO counterparties.counterparties VALUES ('{ids['other_record']}','{ids['tenant']}','Second candidate','SYNTHETIC-2','Synthetic office');''')
        if local:
            self.authority(ids, 0, 'Enginia360ToExternal')
        return ids

    def authority(self, ids, expected, direction):
        companies = ','.join(f"'{c}'::uuid" for c in ids['companies'])
        out = self.sql(f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{ids['tenant']}',true); SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{ids['tenant']}','{ids['member']}','{ids['proof']}',{expected},'{direction}','{ids['source']}','{ids['profile']}',ARRAY[{companies}]); COMMIT;")
        self.assertEqual(out.splitlines()[-1], 'applied')

    def app_prefix(self, ids, company=None, subject=None):
        company_setting = f",set_config('app.legal_entity_id','{company}',true)" if company else ''
        return f"BEGIN; SELECT set_config('app.tenant_id','{ids['tenant']}',true),set_config('app.identity_subject','{subject or ids['actor']}',true){company_setting};"

    def role(self, ids, version, revision, supplier=True, command=None, company=None, record=None):
        return f"SELECT counterparties.set_supplier_role('{company or ids['companies'][0]}','{record or ids['record']}','{command or uuid.uuid4()}',{version},{revision},{'true' if supplier else 'false'})->>'state';"

    def vendor(self, ids, expected=0, vendor_id='4711', name='Synthetic Supplier S.r.l.', command=None, company=None, record=None, actor=None, tenant=None):
        return (f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{tenant or ids['tenant']}',true),set_config('app.legal_entity_id','{company or ids['companies'][0]}',true);"
                f"SELECT counterparties.establish_giobby_vendor_identity('{command or uuid.uuid4()}','{tenant or ids['tenant']}','{company or ids['companies'][0]}','{record or ids['record']}','{actor or ids['member']}','{ids['proof']}',{expected},'{vendor_id}','{name}'); COMMIT;")

    def read_identity(self, ids, company=None, record=None, subject=None):
        c = company or ids['companies'][0]
        out = self.sql(self.app_prefix(ids, c, subject) + f"SELECT counterparties.read_giobby_vendor_identity('{c}','{record or ids['record']}')::text; COMMIT;", app=True)
        import json
        return json.loads(out.splitlines()[-1])

    # ---- shared-master role -------------------------------------------------
    def test_supplier_role_follows_master_authority_and_is_atomic_idempotent_and_revisioned(self):
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql("SELECT to_regprocedure('counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean)') IS NOT NULL"), 't', 'supplier role command is missing')
        ids = self.world(local=False)
        prefix = self.app_prefix(ids)
        self.assertEqual(self.sql(prefix + self.role(ids, 0, 0) + 'COMMIT;', app=True).splitlines()[-1], 'missing')
        self.authority(ids, 0, 'Enginia360ToExternal')
        command = str(uuid.uuid4())
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, command=command) + 'ROLLBACK;', app=True).splitlines()[-1], 'applied')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '0')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, command=command) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, command=command) + 'COMMIT;', app=True).splitlines()[-1], 'replayed')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, supplier=False, command=command) + 'COMMIT;', app=True).splitlines()[-1], 'conflict')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 2147483647, command=command) + 'COMMIT;', app=True).splitlines()[-1], 'conflict')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'conflict', 'stale revision must conflict')
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\" FROM counterparties.counterparties WHERE \"Id\"='{ids['record']}'"), 't')
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\" FROM counterparties.counterparties WHERE \"Id\"='{ids['other_record']}'"), 'f', 'default is not a supplier')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '1')
        # Same optimistic revision sequence as the identity edit: the role change is revision 1.
        state = self.sql(prefix + f"SELECT counterparties.common_edit_state('{ids['companies'][0]}','{ids['record']}')::text; COMMIT;", app=True).splitlines()[-1]
        import json
        state = json.loads(state)
        self.assertEqual((state['revision'], state['counterparty']['isSupplier']), (1, True))
        self.assertEqual(self.sql(prefix + f"SELECT counterparties.edit_common('{ids['companies'][0]}','{ids['record']}','{uuid.uuid4()}',1,1,'Renamed','SYNTHETIC-1','Synthetic office')->>'state'; COMMIT;", app=True).splitlines()[-1], 'applied')
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\",\"LegalName\" FROM counterparties.counterparties WHERE \"Id\"='{ids['record']}'"), 't|Renamed', 'identity edit must not clear the role')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 2, supplier=False) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\" FROM counterparties.counterparties WHERE \"Id\"='{ids['record']}'"), 'f')
        history = self.sql(f"SELECT \"Revision\"||':'||(\"After\"->>'isSupplier') FROM counterparties.common_edit_history WHERE \"CounterpartyId\"='{ids['record']}' AND \"After\" ? 'isSupplier' ORDER BY \"Revision\"")
        self.assertEqual(history.splitlines(), ['1:true', '3:false'])
        self.assertEqual(self.sql(f"SELECT \"Before\"->>'isSupplier' FROM counterparties.common_edit_history WHERE \"CounterpartyId\"='{ids['record']}' AND \"Revision\"=3"), 'true')
        # External authority and stale authority refuse the role exactly as they refuse the identity edit.
        self.authority(ids, 1, 'ExternalToEnginia360')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 3) + 'COMMIT;', app=True).splitlines()[-1], 'stale_authority')
        self.assertEqual(self.sql(prefix + self.role(ids, 2, 3) + 'COMMIT;', app=True).splitlines()[-1], 'external')
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\" FROM counterparties.counterparties WHERE \"Id\"='{ids['record']}'"), 'f')

    def test_role_command_rejects_invalid_input_and_unknown_records_without_history(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world()
        prefix = self.app_prefix(ids)
        c = ids['companies'][0]
        self.assertEqual(self.sql(prefix + f"SELECT counterparties.set_supplier_role('{c}','{ids['record']}',NULL,1,0,true)->>'state'; COMMIT;", app=True).splitlines()[-1], 'invalid')
        self.assertEqual(self.sql(prefix + f"SELECT counterparties.set_supplier_role('{c}','{ids['record']}','{uuid.uuid4()}',1,0,NULL)->>'state'; COMMIT;", app=True).splitlines()[-1], 'invalid')
        self.assertEqual(self.sql(prefix + f"SELECT counterparties.set_supplier_role('{c}','{ids['record']}','{uuid.uuid4()}',1,-1,true)->>'state'; COMMIT;", app=True).splitlines()[-1], 'invalid')
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, record=str(uuid.uuid4())) + 'COMMIT;', app=True).splitlines()[-1], 'not_found')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '0')

    def test_role_command_needs_exact_company_read_and_tenant_common_edit_and_isolates_tenants(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world()
        prefix = self.app_prefix(ids)
        stranger = str(uuid.uuid4())
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0, company=str(uuid.uuid4())) + 'COMMIT;', app=True).splitlines()[-1], 'forbidden')
        self.assertEqual(self.sql(self.app_prefix(ids, subject=stranger) + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'forbidden')
        self.assertEqual(self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{uuid.uuid4()}',true),set_config('app.identity_subject','{ids['actor']}',true);" + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'forbidden')
        self.sql(f"DELETE FROM organization_access.common_edit_permissions WHERE \"MembershipId\"='{ids['member']}'")
        self.assertEqual(self.sql(prefix + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'forbidden', 'company read alone is not the common-edit action')
        self.sql(f"INSERT INTO organization_access.common_edit_permissions VALUES ('{ids['member']}','{ids['tenant']}')")
        other = self.world()
        self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 0, record=other['record']) + 'COMMIT;', app=True).splitlines()[-1], 'not_found', 'a foreign tenant record is invisible')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '0')

    def test_role_privilege_boundary_and_concurrent_identical_commands(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world()
        app = os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean)','EXECUTE')"), 't')
        self.assertEqual(self.sql(f"SELECT has_column_privilege('{app}','counterparties.counterparties','IsSupplier','UPDATE')"), 'f', 'the role is written only through the gated command')
        self.assertEqual(self.sql(f"SELECT has_column_privilege('{app}','counterparties.counterparties','IsSupplier','SELECT')"), 't')
        env = dict(os.environ, PGDATABASE=self.database, PGUSER=app, PGPASSWORD=os.environ['R00_APP_PASSWORD'])
        direct = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], input=self.app_prefix(ids) + f"UPDATE counterparties.counterparties SET \"IsSupplier\"=true WHERE \"Id\"='{ids['record']}'; COMMIT;", env=env, text=True, capture_output=True, timeout=10)
        self.assertNotEqual(direct.returncode, 0)
        self.assertIn('permission denied', direct.stderr)
        duplicate = str(uuid.uuid4())
        processes = []
        try:
            for _ in range(2):
                p = subprocess.Popen(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
                p.stdin.write(self.app_prefix(ids) + self.role(ids, 1, 0, command=duplicate) + 'COMMIT;'); p.stdin.close(); p.stdin = None; processes.append(p)
            outcomes = []
            for p in processes:
                output, error = p.communicate(timeout=10); self.assertEqual(p.returncode, 0, error); outcomes.append(output.splitlines()[-1])
            self.assertEqual(sorted(outcomes), ['applied', 'replayed'])
        finally:
            for p in processes:
                if p.poll() is None: p.kill(); p.communicate()
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '1')
        # An in-flight owner authority decision serializes the role command: it must see the new authority.
        holder = subprocess.Popen(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ, PGDATABASE=self.database, PGAPPNAME='r04b1-owner-hold'), text=True)
        companies = ','.join(f"'{c}'::uuid" for c in ids['companies'])
        holder.stdin.write(f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{ids['tenant']}',true); SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{ids['tenant']}','{ids['member']}','{ids['proof']}',1,'ExternalToEnginia360','{ids['source']}','{ids['profile']}',ARRAY[{companies}]); SELECT pg_sleep(1.5); COMMIT;"); holder.stdin.close(); holder.stdin = None
        try:
            for _ in range(100):
                if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='r04b1-owner-hold' AND wait_event='PgSleep'") == '1': break
                time.sleep(.02)
            else: self.fail('controlled owner did not hold the authority lock')
            self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 1, supplier=False) + 'COMMIT;', app=True).splitlines()[-1], 'stale_authority')
            _, error = holder.communicate(timeout=10); self.assertEqual(holder.returncode, 0, error)
        finally:
            if holder.poll() is None: holder.kill(); holder.communicate()
        self.assertEqual(self.sql(f"SELECT \"IsSupplier\" FROM counterparties.counterparties WHERE \"Id\"='{ids['record']}'"), 't')

    # ---- company extension: Giobby vendor identity -------------------------
    def test_vendor_identity_is_owner_setup_only_for_a_supplier_and_is_immutable_revisioned_history(self):
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql("SELECT to_regprocedure('counterparties.establish_giobby_vendor_identity(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text)') IS NOT NULL"), 't', 'owner vendor identity setup is missing')
        ids = self.world()
        c0, c1 = ids['companies']
        app = os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','counterparties.establish_giobby_vendor_identity(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text)','EXECUTE')"), 'f', 'no web/app path writes the mapping')
        self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','counterparties.giobby_vendor_identity_history','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"), 'f')
        # Not a supplier yet.
        self.assertEqual(self.sql(self.vendor(ids)).splitlines()[-1], 'not_supplier')
        self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        # Untrusted/unknown actor, foreign company, unknown record.
        untrusted = str(uuid.uuid4())
        self.sql(f"INSERT INTO organization_access.memberships VALUES ('{untrusted}','{ids['tenant']}','unbound-subject')")
        self.assertEqual(self.sql(self.vendor(ids, actor=untrusted)).splitlines()[-1], 'forbidden')
        self.assertEqual(self.sql(self.vendor(ids, company=str(uuid.uuid4()))).splitlines()[-1], 'conflict')
        self.assertEqual(self.sql(self.vendor(ids, record=str(uuid.uuid4()))).splitlines()[-1], 'conflict')
        self.assertEqual(self.sql(self.vendor(ids, tenant=str(uuid.uuid4()))).splitlines()[-1], 'forbidden')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.giobby_vendor_identity_history'), '0')
        command = str(uuid.uuid4())
        self.assertEqual(self.sql(self.vendor(ids, command=command)).splitlines()[-1], 'applied')
        self.assertEqual(self.sql(self.vendor(ids, command=command)).splitlines()[-1], 'replayed')
        self.assertEqual(self.sql(self.vendor(ids, command=command, vendor_id='9999')).splitlines()[-1], 'conflict')
        self.assertEqual(self.sql(self.vendor(ids, expected=0)).splitlines()[-1], 'conflict', 'stale expected revision')
        identity = self.read_identity(ids)
        self.assertEqual((identity['state'], identity['isSupplier'], identity['vendor']['vendorId'], identity['vendor']['vendorName'], identity['vendor']['revision']),
                         ('ready', True, '4711', 'Synthetic Supplier S.r.l.', 1))
        # Revision 2 supersedes without mutating revision 1.
        self.assertEqual(self.sql(self.vendor(ids, expected=1, vendor_id='4712', name='Renamed Supplier')).splitlines()[-1], 'applied')
        identity = self.read_identity(ids)
        self.assertEqual((identity['vendor']['vendorId'], identity['vendor']['revision']), ('4712', 2))
        self.assertEqual(self.sql("SELECT count(*) FROM counterparties.giobby_vendor_identity_history"), '2')
        # A vendor ID maps to one counterparty per company; another company is independent.
        self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 0, record=ids['other_record']) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        self.assertEqual(self.sql(self.vendor(ids, record=ids['other_record'], vendor_id='4712')).splitlines()[-1], 'conflict', 'one vendor ID per company must not map two counterparties')
        self.assertEqual(self.sql(self.vendor(ids, company=c1, record=ids['other_record'], vendor_id='4712')).splitlines()[-1], 'applied', 'separate company extension may reuse an ID')
        # Per-company isolation of the extension: the other company sees only its own mapping.
        self.assertIsNone(self.read_identity(ids, company=c1)['vendor'], 'company 1 must not read the company 0 mapping for the first record')
        self.assertEqual(self.read_identity(ids, company=c1, record=ids['other_record'])['vendor']['vendorId'], '4712')
        self.assertIsNone(self.read_identity(ids, company=c0, record=ids['other_record'])['vendor'])
        # Role cleared: the mapping is not served for a non-supplier, history is retained.
        self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 1, supplier=False) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        cleared = self.read_identity(ids)
        self.assertEqual((cleared['isSupplier'], cleared['vendor']), (False, None))
        self.assertEqual(self.sql("SELECT count(*) FROM counterparties.giobby_vendor_identity_history"), '3')
        # Append-only, including for the database owner.
        for statement in ('DELETE FROM counterparties.giobby_vendor_identity_history', 'TRUNCATE counterparties.giobby_vendor_identity_history',
                          'UPDATE counterparties.giobby_vendor_identity_history SET "VendorId"="VendorId"'):
            result = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], input=statement + ';', env=dict(os.environ, PGDATABASE=self.database), text=True, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('append-only', result.stderr)

    def test_vendor_identity_input_bounds_and_read_permissions(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world()
        self.assertEqual(self.sql(self.app_prefix(ids) + self.role(ids, 1, 0) + 'COMMIT;', app=True).splitlines()[-1], 'applied')
        for vendor_id, name in (('', 'Name'), (' 4711', 'Name'), ('a b', 'Name'), ('x'*65, 'Name'), ('4711', ''), ('4711', '   '), ('4711', 'x'*201)):
            with self.subTest(vendor_id=vendor_id, name=name):
                self.assertEqual(self.sql(self.vendor(ids, vendor_id=vendor_id, name=name)).splitlines()[-1], 'invalid')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.giobby_vendor_identity_history'), '0')
        self.assertEqual(self.sql(self.vendor(ids, vendor_id='4711', name='  Padded Name  ')).splitlines()[-1], 'applied')
        self.assertEqual(self.read_identity(ids)['vendor']['vendorName'], 'Padded Name')
        # Reads need exact company counterparties.read; membership alone, another company and a stranger are forbidden.
        c1 = ids['companies'][1]
        self.sql(f"DELETE FROM organization_access.company_permissions WHERE \"MembershipId\"='{ids['member']}' AND \"LegalEntityId\"='{c1}'")
        self.assertEqual(self.read_identity(ids, company=c1)['state'], 'forbidden')
        self.assertEqual(self.read_identity(ids, subject=str(uuid.uuid4()))['state'], 'forbidden')
        self.assertEqual(self.read_identity(ids, record=str(uuid.uuid4()))['state'], 'not_found')
        # A foreign tenant cannot see this mapping even with a forged company/record pair.
        other = self.world()
        foreign = self.sql(self.app_prefix(other, ids['companies'][0], other['actor']) + f"SELECT counterparties.read_giobby_vendor_identity('{ids['companies'][0]}','{ids['record']}')::text; COMMIT;", app=True).splitlines()[-1]
        self.assertIn('"state": "forbidden"', foreign)


if __name__ == '__main__':
    unittest.main()
