#!/usr/bin/env python3
"""Synthetic, isolated PostgreSQL acceptance for the shared-master authority boundary."""
import importlib.util
import os
from pathlib import Path
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('migration_tests',ROOT/'scripts/test-r00-migrations.py')
legacy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

class OwnerInputTests(unittest.TestCase):
    def test_owner_tool_requires_every_explicit_source_profile_and_evidence_field(self):
        path=ROOT/'scripts/owner-master-authority.py'
        self.assertTrue(path.exists(),'bounded owner authority tool is absent')
        spec=importlib.util.spec_from_file_location('owner_authority',path)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        good={key:str(uuid.uuid4()) for key in ('commandId','tenantId','actorMembershipId','verificationReference','sourceId','profileId')}
        good.update(companyIds=[str(uuid.uuid4())],expectedVersion=0,direction='Enginia360ToExternal',domain='counterparties')
        self.assertEqual(module.validate(good),good)
        for bad in ({},dict(good,domain='stock'),dict(good,direction='bidirectional'),dict(good,companyIds=[]),dict(good,companyIds=good['companyIds']*2),dict(good,sourceId=str(uuid.UUID(int=0))),dict(good,expectedVersion=True),dict(good,actorMembershipId=None),dict(good,effectiveFrom='2026-10-01T00:00:00Z'),dict(good,identityVerified=True)):
            with self.subTest(bad=bad):
                with self.assertRaises((ValueError,TypeError)): module.validate(bad)

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL opt-in required')
class AuthoritySqlTests(unittest.TestCase):
    setUp=legacy.PostgreSqlTests.setUp
    tearDown=legacy.PostgreSqlTests.tearDown
    sql=legacy.PostgreSqlTests.sql
    start_migration=legacy.PostgreSqlTests.start_migration
    migrate=legacy.PostgreSqlTests.migrate

    def test_explicit_owner_profile_is_missing_until_setup_and_history_is_append_only(self):
        self.assertEqual(self.migrate()[0],0)
        self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.establish_master_authority(uuid,uuid,uuid,uuid,integer,text,uuid,uuid,uuid[])') IS NOT NULL"),'t','owner-only actual tenant-wide authority setup is missing')
        tenant,company,actor,member,source,profile,proof,command=[str(uuid.uuid4()) for _ in range(8)]
        self.sql(f'''INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic authority');
            INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company');
            INSERT INTO organization_access.external_identity_bindings VALUES ('{actor}','https://synthetic.test','actor');
            INSERT INTO organization_access.memberships VALUES ('{member}','{tenant}','{actor}');''')
        call=f"SELECT organization_access.establish_master_authority('{command}','{tenant}','{member}','{proof}',0,'Enginia360ToExternal','{source}','{profile}',ARRAY['{company}'::uuid]);"
        prefix=f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{tenant}',true);"
        self.assertEqual(self.sql(f"SELECT organization_access.read_master_authority('{company}')->>'state'",app=True),'forbidden')
        self.assertEqual(self.sql(prefix+call+'COMMIT;').splitlines()[-1],'applied')
        self.assertEqual(self.sql(prefix+call+'COMMIT;').splitlines()[-1],'replayed')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.master_authority_history'),'1')
        self.assertEqual(self.sql("SELECT to_jsonb(h)->>'Domain' FROM organization_access.master_authority_history h"),'counterparties','the supported shared-master domain must be explicit in immutable history')

    def test_local_edit_is_atomic_idempotent_and_absent_external_stale_authority_fail_closed(self):
        self.assertEqual(self.migrate()[0],0)
        self.assertEqual(self.sql("SELECT to_regprocedure('counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text)') IS NOT NULL"),'t','atomic authority-gated dependent edit is missing')
        tenant,company,actor,member,source,profile,proof,record=[str(uuid.uuid4()) for _ in range(8)]
        self.sql(f'''INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic authority');
            INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company');
            INSERT INTO organization_access.external_identity_bindings VALUES ('{actor}','https://synthetic.test','actor');
            INSERT INTO organization_access.memberships VALUES ('{member}','{tenant}','{actor}');
            INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{member}','{tenant}','{company}','counterparties.read',NULL,NULL);
            INSERT INTO organization_access.common_edit_permissions VALUES ('{member}','{tenant}');
            INSERT INTO counterparties.counterparties VALUES ('{record}','{tenant}','Before','SYNTHETIC','Synthetic office');''')
        prefix=f"BEGIN; SELECT set_config('app.tenant_id','{tenant}',true),set_config('app.identity_subject','{actor}',true);"
        def edit(version,revision=0,command=None,name='After'):
            return f"SELECT counterparties.edit_common('{company}','{record}','{command or uuid.uuid4()}',{version},{revision},'{name}','SYNTHETIC','Synthetic office')->>'state';"
        def setup(expected,direction):
            return f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{tenant}',true); SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{tenant}','{member}','{proof}',{expected},'{direction}','{source}','{profile}',ARRAY['{company}'::uuid]); COMMIT;"
        self.assertEqual(self.sql(prefix+edit(0)+'COMMIT;',app=True).splitlines()[-1],'missing')
        self.assertEqual(self.sql(setup(0,'Enginia360ToExternal')).splitlines()[-1],'applied')
        command=str(uuid.uuid4())
        self.assertEqual(self.sql(prefix+edit(1,command=command)+'ROLLBACK;',app=True).splitlines()[-1],'applied')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'),'0')
        self.assertEqual(self.sql(prefix+edit(1,command=command)+'COMMIT;',app=True).splitlines()[-1],'applied')
        self.assertEqual(self.sql(prefix+edit(1,command=command)+'COMMIT;',app=True).splitlines()[-1],'replayed')
        self.assertEqual(self.sql(prefix+edit(1,revision=2147483647,command=command)+'COMMIT;',app=True).splitlines()[-1],'conflict','oversized replay revision must not overflow or escape as a database error')
        self.assertEqual(self.sql(prefix+edit(1,command=command,name='Different')+'COMMIT;',app=True).splitlines()[-1],'conflict')
        self.assertEqual(self.sql(prefix+edit(1)+'COMMIT;',app=True).splitlines()[-1],'conflict')
        self.assertEqual(self.sql(setup(1,'ExternalToEnginia360')).splitlines()[-1],'applied')
        self.assertEqual(self.sql(prefix+edit(1,revision=1)+'COMMIT;',app=True).splitlines()[-1],'stale_authority')
        self.assertEqual(self.sql(prefix+edit(2,revision=1)+'COMMIT;',app=True).splitlines()[-1],'external')
        self.assertEqual(self.sql(f'SELECT "LegalName" FROM counterparties.counterparties WHERE "Id"=\'{record}\''),'After')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'),'1')
        foreign_tenant,foreign_company,foreign_actor,foreign_member,foreign_record=[str(uuid.uuid4()) for _ in range(5)]
        self.sql(f'''INSERT INTO organization_access.tenants VALUES ('{foreign_tenant}','Synthetic foreign');
            INSERT INTO organization_access.legal_entities VALUES ('{foreign_company}','{foreign_tenant}','Synthetic foreign company');
            INSERT INTO organization_access.external_identity_bindings VALUES ('{foreign_actor}','https://synthetic.test','foreign');
            INSERT INTO organization_access.memberships VALUES ('{foreign_member}','{foreign_tenant}','{foreign_actor}');
            INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{foreign_member}','{foreign_tenant}','{foreign_company}','counterparties.read',NULL,NULL);
            INSERT INTO organization_access.common_edit_permissions VALUES ('{foreign_member}','{foreign_tenant}');
            INSERT INTO counterparties.counterparties VALUES ('{foreign_record}','{foreign_tenant}','Foreign before','SYNTHETIC','Office');''')
        self.sql(f"BEGIN;SET LOCAL ROLE {self.owner};SELECT set_config('app.tenant_id','{foreign_tenant}',true);SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{foreign_tenant}','{foreign_member}','{proof}',0,'Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}',ARRAY['{foreign_company}'::uuid]);COMMIT;")
        foreign_prefix=f"BEGIN; SELECT set_config('app.tenant_id','{foreign_tenant}',true),set_config('app.identity_subject','{foreign_actor}',true);"
        self.assertEqual(self.sql(foreign_prefix+f"SELECT counterparties.edit_common('{foreign_company}','{foreign_record}','{command}',1,0,'Foreign after','SYNTHETIC','Office')->>'state';COMMIT;",app=True).splitlines()[-1],'conflict','foreign command collision must be a controlled conflict, never an exception or leaked row')
        self.assertEqual(self.sql(f'SELECT "LegalName" FROM counterparties.counterparties WHERE "Id"=\'{foreign_record}\''),'Foreign before')

    def test_exact_grants_rls_immutable_history_owner_boundary_and_concurrent_decision(self):
        import subprocess,time
        self.assertEqual(self.migrate()[0],0)
        tenant,company,other,actor,member,source,profile,proof,record,untrusted=[str(uuid.uuid4()) for _ in range(10)]
        self.sql(f'''INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic authority');
            INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company'),('{other}','{tenant}','Other company');
            INSERT INTO organization_access.external_identity_bindings VALUES ('{actor}','https://synthetic.test','actor');
            INSERT INTO organization_access.memberships VALUES ('{member}','{tenant}','{actor}'),('{untrusted}','{tenant}','unbound');
            INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{member}','{tenant}','{company}','counterparties.read',NULL,NULL);
            INSERT INTO organization_access.common_edit_permissions VALUES ('{member}','{tenant}');
            INSERT INTO counterparties.counterparties VALUES ('{record}','{tenant}','Before','SYNTHETIC','Synthetic office');''')
        app=os.environ['R00_APP_USER']
        env=dict(os.environ,PGDATABASE=self.database,PGUSER=app,PGPASSWORD=os.environ['R00_APP_PASSWORD'])
        owner_prefix=f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{tenant}',true);"
        prefix=f"BEGIN; SELECT set_config('app.tenant_id','{tenant}',true),set_config('app.identity_subject','{actor}',true);"
        def decision(version,direction='Enginia360ToExternal',actor_id=member,companies=None):
            return f"SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{tenant}','{actor_id}','{proof}',{version},'{direction}','{source}','{profile}',ARRAY['{companies or company}'::uuid]);"
        def edit(version,command=None):
            return f"SELECT counterparties.edit_common('{company}','{record}','{command or uuid.uuid4()}',{version},0,'After','SYNTHETIC','Synthetic office')->>'state';"
        def refused(sql,needle='permission denied',owner=False):
            result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=sql,env=dict(os.environ,PGDATABASE=self.database) if owner else env,text=True,capture_output=True,timeout=10)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(needle,result.stderr)
        refused(prefix+decision(0)+'COMMIT;')
        for table in ('organization_access.master_authority_history','counterparties.common_edit_history'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
        self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','counterparties.counterparties','UPDATE')"),'f')
        self.assertEqual(self.sql(owner_prefix+decision(0,actor_id=untrusted)+'COMMIT;').splitlines()[-1],'forbidden')
        self.assertEqual(self.sql(owner_prefix+decision(0,companies=str(uuid.uuid4()))+'COMMIT;').splitlines()[-1],'conflict')
        self.assertEqual(self.sql(owner_prefix+decision(0)+'COMMIT;').splitlines()[-1],'applied')
        self.assertEqual(self.sql(owner_prefix+decision(0,'ExternalToEnginia360')+'COMMIT;').splitlines()[-1],'conflict')
        refused(owner_prefix+decision(1,'bidirectional')+'COMMIT;','check constraint',owner=True)
        self.assertEqual(self.sql(prefix+edit(1).replace(company,other)+'COMMIT;',app=True).splitlines()[-1],'forbidden')
        for table in ('organization_access.master_authority_history','counterparties.common_edit_history'):
            for operation in ('DELETE FROM','TRUNCATE'):
                refused(operation+' '+table+';','append-only',owner=True)
            refused('UPDATE '+table+' SET "TenantId"="TenantId";','append-only',owner=True)
        self.assertEqual(self.sql(prefix+f"SELECT organization_access.read_master_authority('{other}')->>'state';COMMIT;",app=True).splitlines()[-1],'forbidden')
        self.assertEqual(self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{uuid.uuid4()}',true),set_config('app.identity_subject','{actor}',true);"+edit(1)+'COMMIT;',app=True).splitlines()[-1],'forbidden')
        # Owner change owns the exact advisory lock before the app write enters.
        process=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PGDATABASE=self.database,PGAPPNAME='r02b-controlled-owner'),text=True)
        process.stdin.write(owner_prefix+decision(1,'ExternalToEnginia360')+'SELECT pg_sleep(1.5);COMMIT;');process.stdin.close();process.stdin=None
        try:
            for _ in range(100):
                if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='r02b-controlled-owner' AND wait_event='PgSleep'")=='1': break
                time.sleep(.02)
            else: self.fail('controlled owner did not hold authority lock')
            self.assertEqual(self.sql(prefix+f"SELECT counterparties.common_edit_state('{company}','{record}')->'authority'->>'state';COMMIT;",app=True).splitlines()[-1],'external','edit read must serialize with an in-flight authority decision')
            self.assertEqual(self.sql(prefix+edit(1)+'COMMIT;',app=True).splitlines()[-1],'stale_authority')
            _,error=process.communicate(timeout=10); self.assertEqual(process.returncode,0,error)
        finally:
            if process.poll() is None: process.kill();process.communicate()
        self.assertEqual(self.sql(f'SELECT "LegalName" FROM counterparties.counterparties WHERE "Id"=\'{record}\''),'Before')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'),'0')
        # Reused SQL session commit/rollback cannot retain identity or tenant context.
        self.assertEqual(self.sql(prefix+f"SELECT organization_access.read_master_authority('{company}')->>'state';ROLLBACK;SELECT organization_access.read_master_authority('{company}')->>'state';",app=True).splitlines()[-2:],['external','forbidden'])
        self.assertEqual(self.sql(owner_prefix+decision(2)+'COMMIT;').splitlines()[-1],'applied')
        self.sql(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{member}','{tenant}','{other}','counterparties.read',NULL,NULL);")
        self.assertEqual(self.sql(prefix+f"SELECT organization_access.read_master_authority('{other}')->>'state';COMMIT;",app=True).splitlines()[-1],'missing','a company not explicitly mapped cannot inherit a default source')
        # Separate physical app connections concurrently replay the same command; no one-connection serialization fixture.
        duplicate=str(uuid.uuid4())
        processes=[]
        try:
            for _ in range(2):
                p=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
                p.stdin.write(prefix+edit(3,duplicate)+'COMMIT;');p.stdin.close();p.stdin=None;processes.append(p)
            outcomes=[]
            for p in processes:
                output,error=p.communicate(timeout=10); self.assertEqual(p.returncode,0,error); outcomes.append(output.splitlines()[-1])
            self.assertEqual(sorted(outcomes),['applied','replayed'])
        finally:
            for p in processes:
                if p.poll() is None: p.kill();p.communicate()
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'),'1')
        # Exact grant deletion commits before the dependent command can lock the same permission row.
        revoke=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,PGDATABASE=self.database,PGAPPNAME='r02b-controlled-revoke'),text=True)
        revoke.stdin.write(f'''BEGIN; DELETE FROM organization_access.common_edit_permissions WHERE "MembershipId"='{member}'; SELECT pg_sleep(1.5);COMMIT;''');revoke.stdin.close();revoke.stdin=None
        try:
            for _ in range(100):
                if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='r02b-controlled-revoke' AND wait_event='PgSleep'")=='1': break
                time.sleep(.02)
            else: self.fail('grant revoke did not reach lock barrier')
            self.assertEqual(self.sql(prefix+edit(3)+'COMMIT;',app=True).splitlines()[-1],'forbidden')
            _,error=revoke.communicate(timeout=10);self.assertEqual(revoke.returncode,0,error)
        finally:
            if revoke.poll() is None: revoke.kill();revoke.communicate()
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.common_edit_history'),'1')

if __name__=='__main__': unittest.main()
