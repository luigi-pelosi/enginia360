#!/usr/bin/env python3
"""Owned synthetic facts only; never a Giobby verification or provider contract proof."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('supplier', ROOT/'scripts/test-r04b1-supplier.py')
assert spec and spec.loader
supplier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supplier)
SIGNATURE = 'counterparties.project_external_supplier_role(jsonb)'


class OwnerInputTests(unittest.TestCase):
    def good(self):
        value = {key:str(uuid.uuid4()) for key in ('commandId','tenantId','legalEntityId','counterpartyId',
                 'actorMembershipId','verificationReference','sourceFactReference','sourceId','profileId')}
        return dict(value, authorityVersion=1, expectedRevision=0, sourceSystem='Giobby', isSupplier=True)

    def tool(self):
        path = ROOT/'scripts/owner-external-supplier-role.py'
        # Capture the missing owner projection contract, not an import/compile error.
        if not path.exists():
            path = ROOT/'scripts/owner-supplier-vendor-identity.py'
        spec = importlib.util.spec_from_file_location('owner_projection', path)
        assert spec and spec.loader
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def test_duplicate_json_oversize_and_process_errors_are_closed_and_redacted(self):
        import tempfile
        tool = self.tool()
        with self.assertRaises(ValueError):
            tool.closed_object([('commandId','a'),('commandId','b')])
        secret = 'D95-TEST-DO-NOT-LOG'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'request.json'
            for raw in ('{"commandId":"a","commandId":"b"}', 'x'*4097, json.dumps(self.good())):
                path.write_text(raw)
                result = subprocess.run(['python3',str(ROOT/'scripts/owner-external-supplier-role.py'),str(path)],
                    env=dict(os.environ, PGSSLMODE='verify-full', PGSSLROOTCERT='/nonexistent-d95-ca',
                             PGHOST='/nonexistent-d95-socket', PGCONNECT_TIMEOUT='1', PGPASSWORD=secret),
                    text=True, capture_output=True, timeout=8)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Supplier projection refused.', result.stderr)
                self.assertNotIn(secret, result.stdout+result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_tls_failure_never_starts_psql_and_success_requires_exact_receipt(self):
        from unittest.mock import patch
        tool = self.tool()
        good = self.good()
        with patch.dict(os.environ, {'PGSSLMODE':'require', 'PGSSLROOTCERT':'/ca'}, clear=False), patch.object(subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                tool.apply(good)
            run.assert_not_called()
        snapshot = dict(counterpartyId=good['counterpartyId'], isSupplier=True, revision=1, authorityVersion=1)
        lines = 'D95_RESULT|'+json.dumps(dict(state='applied', snapshot=snapshot))+'\nD95_RECEIPT|'+json.dumps(dict(request=good, snapshot=snapshot, revision=1, isSupplier=True))+'\n'
        with patch.dict(os.environ, {'PGSSLMODE':'verify-full', 'PGSSLROOTCERT':'/ca'}, clear=False), patch.object(subprocess, 'run') as run:
            run.return_value = subprocess.CompletedProcess([],0,lines,'')
            tool.apply(good)
            self.assertIn("PGSSLMODE", os.environ)
            self.assertIn('COMMIT;', run.call_args.kwargs['input'])
            run.return_value = subprocess.CompletedProcess([],0,lines.replace(good['sourceFactReference'],str(uuid.uuid4())),'')
            with self.assertRaises(ValueError):
                tool.apply(good)
            run.return_value = subprocess.CompletedProcess([],1,'','credential-that-must-not-escape')
            with self.assertRaisesRegex(ValueError, '^projection refused or exact immutable readback failed$'):
                tool.apply(good)

    def test_owner_projection_accepts_only_explicit_positive_fact_envelope(self):
        tool = self.tool()
        good = self.good()
        try:
            accepted = tool.validate(good) == good
        except ValueError:
            accepted = False
        self.assertTrue(accepted, 'owner CLI cannot project a verified positive external fact')
        for bad in ({}, dict(good, vendorId='NEVER-SHARED'), dict(good, isSupplier=False),
                    dict(good, isSupplier=1), dict(good, authorityVersion=True),
                    dict(good, expectedRevision=0.0), dict(good, expectedRevision=2147483648),
                    dict(good, sourceSystem='Other'), dict(good, sourceFactReference='x'*10000)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    tool.validate(bad)


@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated PostgreSQL opt-in')
class ProjectionSqlTests(unittest.TestCase):
    setUp = supplier.SupplierSqlTests.setUp
    tearDown = supplier.SupplierSqlTests.tearDown
    sql = supplier.SupplierSqlTests.sql
    start_migration = supplier.SupplierSqlTests.start_migration
    migrate = supplier.SupplierSqlTests.migrate
    world = supplier.SupplierSqlTests.world
    authority = supplier.SupplierSqlTests.authority
    app_prefix = supplier.SupplierSqlTests.app_prefix
    role = supplier.SupplierSqlTests.role
    vendor = supplier.SupplierSqlTests.vendor
    read_identity = supplier.SupplierSqlTests.read_identity

    def request(self, ids, **changes):
        value = dict(commandId=str(uuid.uuid4()), tenantId=ids['tenant'],
                     legalEntityId=ids['companies'][0], counterpartyId=ids['record'],
                     actorMembershipId=ids['member'], verificationReference=str(uuid.uuid4()),
                     sourceFactReference=str(uuid.uuid4()), sourceSystem='Giobby',
                     sourceId=ids['source'], profileId=ids['profile'], authorityVersion=1,
                     expectedRevision=0, isSupplier=True)
        return dict(value, **changes)

    def project(self, value, commit=True):
        # Before D95 the only existing role command refuses the valid external fact.
        # This fallback proves a real missing behavior, not a missing function/SQL error.
        exists = self.sql(f"SELECT to_regprocedure('{SIGNATURE}') IS NOT NULL") == 't'
        prefix = (f"BEGIN; SELECT set_config('app.tenant_id','{value.get('tenantId', '')}',true),"
                  f"set_config('app.legal_entity_id','{value.get('legalEntityId', '')}',true);")
        if exists:
            statement = f"SELECT counterparties.project_external_supplier_role('{json.dumps(value)}'::jsonb)::text;"
        else:
            prefix += f"SELECT set_config('app.identity_subject',(SELECT \"IdentitySubject\" FROM organization_access.memberships WHERE \"Id\"='{value['actorMembershipId']}'),true);"
            statement = (f"SELECT counterparties.set_supplier_role('{value['legalEntityId']}',"
                         f"'{value['counterpartyId']}','{value['commandId']}',{value['authorityVersion']},"
                         f"{value['expectedRevision']},true)::text;")
        result = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'],
                                input=prefix+statement+('COMMIT;' if commit else 'ROLLBACK;'),
                                env=dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner,
                                         PGPASSWORD=os.environ['R00_OWNER_PASSWORD']),
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def spawn(self, sql, name, owner=False):
        env = dict(os.environ, PGDATABASE=self.database, PGAPPNAME=name)
        if owner:
            env.update(PGUSER=self.owner, PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
        p = subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
        p.stdin.write("SET statement_timeout='10s'; SET lock_timeout='8s';"+sql)
        p.stdin.close()
        p.stdin = None
        self.addCleanup(self.reap, p)
        return p

    @staticmethod
    def reap(p):
        if p.poll() is None:
            p.kill()
        p.communicate(timeout=5)

    def wait_for(self, query, expected):
        import time
        deadline = time.monotonic()+5
        while time.monotonic() < deadline:
            if self.sql(query) == expected:
                return
            time.sleep(.02)
        self.fail('physical PostgreSQL barrier not observed: '+query)

    def projection_sql(self, good):
        return (f"SELECT set_config('app.tenant_id','{good['tenantId']}',true),set_config('app.legal_entity_id','{good['legalEntityId']}',true);"
                f"SELECT counterparties.project_external_supplier_role('{json.dumps(good)}'::jsonb)::text;")

    def finish(self, p):
        out, error = p.communicate(timeout=12)
        self.assertEqual(p.returncode, 0, error)
        return out.splitlines()

    def test_physical_source_binding_membership_and_shared_revision_races_both_orders(self):
        self.assertEqual(self.migrate()[0], 0)
        for kind in ('authority','binding','membership','revision'):
            for projection_first in (False, True):
                with self.subTest(kind=kind, projection_first=projection_first):
                    ids = self.world(local=False)
                    self.authority(ids, 0, 'ExternalToEnginia360')
                    good = self.request(ids)
                    tenant, company, record = ids['tenant'], ids['companies'][0], ids['record']
                    if kind == 'authority':
                        mutation = (f"SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{tenant}',true);"
                                    f"SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{tenant}','{ids['member']}','{ids['proof']}',1,'Enginia360ToExternal','{ids['source']}','{ids['profile']}',ARRAY['{company}'::uuid]);")
                        refusal = 'stale_authority'
                    elif kind == 'binding':
                        mutation = f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';'''
                        refusal = 'forbidden'
                    elif kind == 'membership':
                        mutation = f'''UPDATE organization_access.memberships SET "IdentitySubject"='revoked-{ids['actor']}' WHERE "Id"='{ids['member']}';'''
                        refusal = 'forbidden'
                    else:
                        # Fixture-only owner edit, using the exact shared authority/revision serialization contract.
                        revision = 2 if projection_first else 1
                        mutation = (f"SELECT pg_advisory_xact_lock(hashtextextended('master-authority:{tenant}',0));"
                                    f'''INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After")
                                    VALUES ('{uuid.uuid4()}','{tenant}','{record}','{company}','{ids['member']}',1,{revision},'{{}}','{{"fixtureEdit":true}}');
                                    UPDATE counterparties.counterparties SET "LegalName"='Fixture edited' WHERE "Id"='{record}';''')
                        refusal = 'conflict'
                    projection = self.projection_sql(good)
                    first = projection if projection_first else mutation
                    second = mutation if projection_first else projection
                    holder = self.spawn('BEGIN;'+first+'SELECT pg_sleep(2); COMMIT;', 'd95-holder', owner=projection_first)
                    self.wait_for("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='d95-holder' AND wait_event='PgSleep'", '1')
                    waiter = self.spawn('BEGIN;'+second+'COMMIT;', 'd95-waiter', owner=not projection_first)
                    self.wait_for("SELECT count(DISTINCT pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name IN ('d95-holder','d95-waiter')", '2')
                    self.wait_for("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='d95-waiter' AND wait_event_type='Lock'", '1')
                    first_out, second_out = self.finish(holder), self.finish(waiter)
                    projected = [json.loads(line) for line in (first_out if projection_first else second_out) if line.startswith('{')]
                    self.assertEqual(len(projected), 1)
                    self.assertEqual(projected[0]['state'], 'applied' if projection_first else refusal)
                    self.assertEqual(self.sql(f'''SELECT "IsSupplier" FROM counterparties.counterparties WHERE "Id"='{record}';'''), 't' if projection_first else 'f')
                    self.assertEqual(self.sql(f'''SELECT count(*) FROM counterparties.external_supplier_projection_history WHERE "TenantId"='{tenant}';'''), '1' if projection_first else '0')

    def test_same_uuid_and_new_uuid_races_use_distinct_physical_sessions(self):
        self.assertEqual(self.migrate()[0], 0)
        for same in (True, False):
            ids = self.world(local=False)
            self.authority(ids, 0, 'ExternalToEnginia360')
            good = self.request(ids)
            blocker = self.spawn(f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('master-authority:{ids['tenant']}',0)); SELECT pg_sleep(2); COMMIT;", 'd95-blocker')
            self.wait_for("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='d95-blocker' AND wait_event='PgSleep'", '1')
            requests = [good, good if same else dict(good,commandId=str(uuid.uuid4()))]
            processes = [self.spawn('BEGIN;'+self.projection_sql(value)+'COMMIT;', 'd95-racer', owner=True) for value in requests]
            self.wait_for("SELECT count(DISTINCT pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name='d95-racer' AND wait_event_type='Lock'", '2')
            self.finish(blocker)
            states = [json.loads(self.finish(p)[-1])['state'] for p in processes]
            self.assertEqual(sorted(states), ['applied','replayed' if same else 'conflict'])
            self.assertEqual(self.sql(f'''SELECT count(*) FROM counterparties.external_supplier_projection_history WHERE "TenantId"='{ids['tenant']}';'''), '1')

    def test_company_vendor_binding_bootstraps_after_projection_but_does_not_leak_into_shared_state(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        self.assertEqual(self.sql(self.vendor(ids)).splitlines()[-1], 'not_supplier')
        good = self.request(ids)
        self.assertEqual(self.project(good)['state'], 'applied')
        self.assertEqual(self.sql(self.vendor(ids, vendor_id='D95-COMPANY-A', name='Company vendor hint')).splitlines()[-1], 'applied')
        self.assertEqual(self.read_identity(ids)['vendor']['vendorId'], 'D95-COMPANY-A')
        self.assertIsNone(self.read_identity(ids, company=ids['companies'][1])['vendor'])
        self.assertEqual(self.sql(self.vendor(ids, company=ids['companies'][1], vendor_id='D95-COMPANY-B', name='Independent hint')).splitlines()[-1], 'applied')
        self.assertEqual(self.read_identity(ids, company=ids['companies'][1])['vendor']['vendorId'], 'D95-COMPANY-B')
        shared = self.sql(self.app_prefix(ids)+f"SELECT counterparties.common_edit_state('{ids['companies'][0]}','{ids['record']}')::text; COMMIT;", app=True).splitlines()[-1]
        self.assertNotIn('D95-COMPANY', shared)
        self.assertNotIn('vendor hint', shared)
        self.assertEqual(json.loads(shared)['counterparty']['legalName'], 'Supplier candidate')
        # Purchasing's separately delivered external-master gate is not silently broadened by role projection.
        chooser = self.sql(self.app_prefix(ids, ids['companies'][0])+f"SELECT counterparties.purchase_suppliers('{ids['companies'][0]}')::text; COMMIT;", app=True).splitlines()[-1]
        self.assertEqual(json.loads(chooser), {'state':'master_external'})

    def test_fixture_insert_and_deferred_commit_failures_roll_back_role_and_provenance_together(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        self.sql("CREATE FUNCTION public.d95_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'owned fixture failure'; END $$;")
        for deferred in (False, True):
            good = self.request(ids)
            trigger = ("CREATE CONSTRAINT TRIGGER d95_fault AFTER INSERT ON counterparties.external_supplier_projection_history DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.d95_fault();" if deferred else
                       "CREATE TRIGGER d95_fault BEFORE INSERT ON counterparties.external_supplier_projection_history FOR EACH ROW EXECUTE FUNCTION public.d95_fault();")
            self.sql(trigger)
            try:
                failed = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], input='BEGIN;'+self.projection_sql(good)+'COMMIT;',
                                        env=dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner, PGPASSWORD=os.environ['R00_OWNER_PASSWORD']),
                                        text=True, capture_output=True, timeout=15)
                self.assertNotEqual(failed.returncode, 0)
                self.assertIn('owned fixture failure', failed.stderr)
                for table in ('common_edit_history','external_supplier_projection_history'):
                    self.assertEqual(self.sql('SELECT count(*) FROM counterparties.'+table), '0')
                self.assertEqual(self.sql(f'''SELECT "IsSupplier" FROM counterparties.counterparties WHERE "Id"='{ids['record']}';'''), 'f')
            finally:
                self.sql('DROP TRIGGER d95_fault ON counterparties.external_supplier_projection_history;')

    def test_current_authority_trust_and_company_guards_are_fail_closed_without_user_grants(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        good = self.request(ids)
        self.assertEqual(self.project(good), {'state':'missing'})
        self.authority(ids, 0, 'Enginia360ToExternal')
        self.assertEqual(self.project(good), {'state':'stale_authority'})
        self.authority(ids, 1, 'ExternalToEnginia360')
        good['authorityVersion'] = 2
        for change, state in [({'sourceId':str(uuid.uuid4())}, 'stale_authority'),
                              ({'profileId':str(uuid.uuid4())}, 'stale_authority'),
                              ({'authorityVersion':1}, 'stale_authority'),
                              ({'legalEntityId':str(uuid.uuid4())}, 'conflict'),
                              ({'actorMembershipId':str(uuid.uuid4())}, 'forbidden'),
                              ({'counterpartyId':str(uuid.uuid4())}, 'not_found'),
                              ({'tenantId':str(uuid.uuid4())}, 'forbidden')]:
            with self.subTest(change=change):
                self.assertEqual(self.project(dict(good, **change)), {'state':state})
        untrusted = str(uuid.uuid4())
        self.sql(f'''INSERT INTO organization_access.memberships VALUES ('{untrusted}','{ids['tenant']}','unbound');''')
        self.assertEqual(self.project(dict(good, actorMembershipId=untrusted)), {'state':'forbidden'})
        # Browser grants are neither authority nor a prerequisite of the owner-only offline path.
        self.sql(f'''DELETE FROM organization_access.common_edit_permissions WHERE "MembershipId"='{ids['member']}';
                     DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{ids['member']}';''')
        self.assertEqual(self.project(good)['state'], 'applied')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.common_edit_permissions'), '0')

    def test_max_revision_and_transaction_rollback_preserve_role_and_both_audits(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        good = self.request(ids)
        self.assertEqual(self.project(good, commit=False)['state'], 'applied')
        for table in ('common_edit_history','external_supplier_projection_history'):
            self.assertEqual(self.sql('SELECT count(*) FROM counterparties.'+table), '0')
        self.sql(f'''INSERT INTO counterparties.common_edit_history("CommandId","TenantId","CounterpartyId","LegalEntityId","ActorMembershipId","AuthorityVersion","Revision","Before","After")
                  VALUES ('{uuid.uuid4()}','{ids['tenant']}','{ids['record']}','{ids['companies'][0]}','{ids['member']}',1,2147483647,'{{}}','{{"isSupplier":false}}');''')
        self.assertEqual(self.project(dict(good, expectedRevision=2147483647)), {'state':'conflict'})
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.external_supplier_projection_history'), '0')
        self.assertEqual(self.sql(f'''SELECT "IsSupplier" FROM counterparties.counterparties WHERE "Id"='{ids['record']}';'''), 'f')

    def test_projection_privileges_force_rls_and_immutable_audit(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        good = self.request(ids)
        self.assertEqual(self.project(good)['state'], 'applied')
        app = os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','{SIGNATURE}','EXECUTE')"), 'f')
        self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','counterparties.external_supplier_projection_history','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"), 'f')
        self.assertEqual(self.sql("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='counterparties.external_supplier_projection_history'::regclass"), 't')
        for sql in ('SELECT count(*) FROM counterparties.external_supplier_projection_history;',
                    f"SELECT counterparties.project_external_supplier_role('{json.dumps(good)}'::jsonb);"):
            denied = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], input=sql,
                                    env=dict(os.environ, PGDATABASE=self.database, PGUSER=app, PGPASSWORD=os.environ['R00_APP_PASSWORD']),
                                    text=True, capture_output=True, timeout=10)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn('permission denied', denied.stderr)
        for sql in ('DELETE FROM counterparties.external_supplier_projection_history;',
                    'UPDATE counterparties.external_supplier_projection_history SET "Snapshot"=\'{}\';',
                    'TRUNCATE counterparties.external_supplier_projection_history;'):
            denied = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], input=sql,
                                    env=dict(os.environ, PGDATABASE=self.database), text=True, capture_output=True, timeout=10)
            self.assertNotEqual(denied.returncode, 0)
            self.assertIn('append-only', denied.stderr)
        hidden = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], input='SELECT count(*) FROM counterparties.external_supplier_projection_history;',
                                env=dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner, PGPASSWORD=os.environ['R00_OWNER_PASSWORD']),
                                text=True, capture_output=True, timeout=10)
        self.assertEqual((hidden.returncode, hidden.stdout.strip()), (0,'0'))

    def test_closed_json_refuses_forbidden_fields_noncanonical_references_and_transport_types(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        good = self.request(ids)
        cases = [dict(good, legalName='Not authorized'), dict(good, vendorId='COMPANY-ONLY'),
                 dict(good, vendorName='Not shared'), dict(good, isSupplier=False),
                 dict(good, isSupplier='true'), dict(good, expectedRevision=True),
                 dict(good, expectedRevision='0'), dict(good, expectedRevision=0.0),
                 dict(good, expectedRevision=-1), dict(good, expectedRevision=2147483648),
                 dict(good, authorityVersion='1'), dict(good, authorityVersion=0),
                 dict(good, sourceSystem='Other'), dict(good, sourceSystem='giobby')]
        for key in ('commandId','tenantId','legalEntityId','counterpartyId','actorMembershipId',
                    'verificationReference','sourceFactReference','sourceId','profileId'):
            cases += [dict(good, **{key: value}) for value in (None, '', '0'*32,
                      str(uuid.UUID(int=0)), good[key].upper(), good[key].replace('-', ''))]
        cases += [{k:v for k,v in good.items() if k != key} for key in good]
        for bad in cases:
            with self.subTest(bad=bad):
                self.assertEqual(self.project(bad), {'state':'invalid'})
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '0')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.external_supplier_projection_history'), '0')
        self.assertEqual(self.sql(f'''SELECT "IsSupplier" FROM counterparties.counterparties WHERE "Id"='{ids['record']}';'''), 'f')

    def test_exact_replay_retains_original_snapshot_after_later_projection_and_rejects_collision(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        request = self.request(ids)
        applied = self.project(request)
        self.assertEqual(applied['state'], 'applied')
        later = self.project(self.request(ids, expectedRevision=1))
        self.assertEqual(later['state'], 'applied', 'already true records a fresh verified positive observation')
        replay = self.project(request)
        self.assertEqual(replay, dict(applied, state='replayed'), 'replay must return the original immutable snapshot')
        self.assertEqual(self.project(dict(request, sourceFactReference=str(uuid.uuid4())))['state'], 'conflict')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.external_supplier_projection_history'), '2')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'), '2')
        other = self.world(local=False)
        self.authority(other, 0, 'ExternalToEnginia360')
        collision = self.project(self.request(other, commandId=request['commandId']))
        self.assertEqual(collision, {'state': 'conflict'}, 'foreign hidden UUID must not disclose snapshot')
        self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';''')
        self.assertEqual(self.project(request), {'state': 'forbidden'}, 'replay rechecks current trust')

    def test_verified_existing_external_positive_fact_projects_without_changing_common_identity_or_vendor(self):
        self.assertEqual(self.migrate()[0], 0)
        ids = self.world(local=False)
        self.authority(ids, 0, 'ExternalToEnginia360')
        before = self.sql(f'''SELECT "LegalName","FiscalIdentifier","RegisteredOffice" FROM counterparties.counterparties WHERE "Id"='{ids['record']}';''')
        business_tables = self.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('catalog','inventory','integrations','workshop','billing','accounting') ORDER BY 1").splitlines()
        counts_sql = ' UNION ALL '.join(f"SELECT '{table}:'||count(*)::text FROM {table}" for table in business_tables)
        business_before = self.sql(counts_sql)
        result = self.project(self.request(ids))
        self.assertEqual(self.sql(counts_sql), business_before, 'no catalog/price/stock/order/receipt/outbox mutations')
        self.assertEqual(result['state'], 'applied', 'owner-offline positive external projection is not implemented')
        self.assertEqual(result['snapshot']['isSupplier'], True)
        self.assertEqual(result['snapshot']['revision'], 1)
        self.assertEqual(self.sql(f'''SELECT "LegalName","FiscalIdentifier","RegisteredOffice" FROM counterparties.counterparties WHERE "Id"='{ids['record']}';'''), before)
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.giobby_vendor_identity_history'), '0')
        state = json.loads(self.sql(self.app_prefix(ids)+f"SELECT counterparties.common_edit_state('{ids['companies'][0]}','{ids['record']}')::text; COMMIT;", app=True).splitlines()[-1])
        self.assertEqual((state['revision'], state['counterparty']['isSupplier'], state['authority']['state']), (1, True, 'external'))
        self.assertEqual(self.sql(self.app_prefix(ids)+self.role(ids, 1, 1, supplier=False)+'COMMIT;', app=True).splitlines()[-1], 'external')


if __name__ == '__main__':
    unittest.main()
