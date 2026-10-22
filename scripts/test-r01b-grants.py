#!/usr/bin/env python3
"""Bounded real SQL security/race/rollback acceptance for D77 operative grants."""
import importlib.util
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
legacy=load('migration_grant_tests',ROOT/'scripts/test-r00-migrations.py')
owner=load('owner_mandate',ROOT/'scripts/owner-operative-mandate.py')

class OwnerInputTests(unittest.TestCase):
    def test_no_implicit_owner_mandate_defaults_or_identity_proof(self):
        good={key:str(uuid.uuid4()) for key in owner.FIELDS-{'operation','action','validFrom','validUntil'}}
        good.update(operation='create',action='organization-context.read',validFrom='2026-10-22T00:00:00Z',validUntil='2026-10-23T00:00:00Z')
        self.assertEqual(owner.validate(good),good)
        for mutation in ({},dict(good,action='admin'),dict(good,tenantId=str(uuid.UUID(int=0))),dict(good,validUntil=good['validFrom']),dict(good,validFrom='2026-10-22T00:00:00'),dict(good,validFrom=None),dict(good,identityVerified=True)):
            with self.subTest(mutation=mutation):
                with self.assertRaises((ValueError,TypeError)):
                    owner.validate(mutation)

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL opt-in required')
class GrantSqlTests(unittest.TestCase):
    database: str
    setUp=legacy.PostgreSqlTests.setUp
    tearDown=legacy.PostgreSqlTests.tearDown
    sql=legacy.PostgreSqlTests.sql
    start_migration=legacy.PostgreSqlTests.start_migration
    migrate=legacy.PostgreSqlTests.migrate

    def test_privilege_boundary_validity_serialized_revoke_and_transaction_rollback(self):
        self.assertEqual(self.migrate()[0],0)
        self.assertEqual(self.sql("SELECT to_regclass('organization_access.delegation_mandates') IS NOT NULL"),'t')
        ids=[str(uuid.uuid4()) for _ in range(12)]
        tenant,company,site,warehouse,actor,target,am,tm,mandate,root,untrusted,expired=ids
        self.sql(f'''SELECT set_config('app.owner_actor','{root}',false);
            INSERT INTO organization_access.external_identity_bindings VALUES ('{actor}','https://synthetic.test','actor'),('{target}','https://synthetic.test','target');
            INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic SQL grants');
            INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company');
            INSERT INTO organization_access.sites VALUES ('{site}','{company}','{tenant}','Synthetic site');
            INSERT INTO organization_access.warehouses VALUES ('{warehouse}','{site}','{company}','{tenant}','Synthetic warehouse');
            INSERT INTO organization_access.memberships VALUES ('{am}','{tenant}','{actor}'),('{tm}','{tenant}','{target}'),('{untrusted}','{tenant}','unbound');
            INSERT INTO organization_access.delegation_mandates VALUES ('{mandate}','{tenant}','{am}','{company}','{site}','{warehouse}','organization-context.read',clock_timestamp()-interval '1 hour',clock_timestamp()+interval '1 hour',NULL),
            ('{expired}','{tenant}','{am}','{company}','{site}','{warehouse}','organization-context.read',clock_timestamp()-interval '2 hour',clock_timestamp()-interval '1 hour',NULL);''')
        prefix=f"BEGIN; SELECT set_config('app.identity_subject','{actor}',true),set_config('app.tenant_id','{tenant}',true);"
        def call(command=None,mandate_id=mandate,target_id=tm,action='organization-context.read',operation='grant'):
            return f"SELECT organization_access.command_operative_grant('{command or uuid.uuid4()}','{mandate_id}','{target_id}','{tenant}','{company}','{site}','{warehouse}','{action}','{operation}');"
        app=os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname='{app}'"),'f')
        for table in ('memberships','external_identity_bindings','membership_scopes','delegation_mandates','delegated_scopes','grant_commands','delegation_audit'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','organization_access.{table}','INSERT,UPDATE,DELETE,TRUNCATE')"),'f',table)
        # Even database owner functions are NOBYPASSRLS; fixed search_path and no PUBLIC execute.
        self.assertEqual(self.sql("SELECT bool_and(p.prosecdef AND NOT r.rolsuper AND NOT r.rolbypassrls AND p.proconfig=ARRAY['search_path=pg_catalog, organization_access']) FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid IN ('organization_access.grant_administration()'::regprocedure,'organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)'::regprocedure)"),'t')
        self.assertEqual(self.sql("SELECT count(*) FROM organization_access.effective_membership_scopes",app=True),'0')
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) a WHERE p.pronamespace='organization_access'::regnamespace AND p.proname IN ('grant_administration','command_operative_grant') AND a.grantee=0"),'0','PUBLIC execute must be revoked')
        for args in ({'mandate_id':expired},{'target_id':am},{'target_id':untrusted},{'action':'master.common-edit'},{'operation':'revoke','mandate_id':expired}):
            self.assertEqual(self.sql(prefix+call(**args)+'COMMIT;',app=True).splitlines()[-1],'forbidden')
        command=str(uuid.uuid4())
        self.assertEqual(self.sql(prefix+call(command)+'ROLLBACK;',app=True).splitlines()[-1],'applied')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.delegated_scopes'),'0')
        self.assertEqual(self.sql(f'SELECT count(*) FROM organization_access.grant_commands WHERE "CommandId"=\'{command}\''),'0')
        # Direct arbitrary write is rejected by SQL privileges, not just endpoint checks.
        env=dict(os.environ,PGDATABASE=self.database,PGUSER=app,PGPASSWORD=os.environ['R00_APP_PASSWORD'])
        attempted=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=prefix+'DELETE FROM organization_access.membership_scopes;COMMIT;',env=env,text=True,capture_output=True,timeout=10)
        self.assertNotEqual(attempted.returncode,0)
        self.assertIn('permission denied',attempted.stderr)
        # Root revocation holds mandate lock before command takes it: command must wait then deny.
        revoke_env=dict(os.environ,PGDATABASE=self.database)
        revoke_sql=f"BEGIN; SELECT set_config('app.owner_actor','{root}',true); UPDATE organization_access.delegation_mandates SET \"RevokedAt\"=clock_timestamp() WHERE \"Id\"='{mandate}'; SELECT pg_sleep(1.5); COMMIT;"
        process=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=revoke_env,text=True)
        assert process.stdin is not None
        process.stdin.write(revoke_sql);process.stdin.close();process.stdin=None
        try:
            # Wait for the server's actual sleep state: no assumed scheduling delay.
            for _ in range(60):
                if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event='PgSleep'")=='1': break
                time.sleep(.025)
            else: self.fail('revocation transaction did not reach controlled lock barrier')
            self.assertEqual(self.sql(prefix+call()+'COMMIT;',app=True).splitlines()[-1],'forbidden')
            out,error=process.communicate(timeout=10)
            self.assertEqual(process.returncode,0,error)
        finally:
            if process.poll() is None: process.kill();process.communicate()
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.delegated_scopes'),'0')
        self.assertEqual(self.sql("SELECT count(*) FROM organization_access.delegation_audit WHERE \"Result\"='applied' AND \"Operation\"='grant'"),'0')
        immutable=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='DELETE FROM organization_access.delegation_audit;',env=revoke_env,text=True,capture_output=True,timeout=10)
        self.assertNotEqual(immutable.returncode,0)
        self.assertIn('append-only',immutable.stderr)
        # Removal of a binding must NEVER prevent the owner's later mandate revocation.
        self.sql(f"SELECT set_config('app.owner_actor','{root}',false); DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\"='{actor}'; UPDATE organization_access.delegation_mandates SET \"RevokedAt\"=clock_timestamp() WHERE \"Id\"='{expired}';")

if __name__=='__main__':
    unittest.main()
