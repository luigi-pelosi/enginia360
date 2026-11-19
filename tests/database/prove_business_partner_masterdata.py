"""Prova PostgreSQL isolata della separazione masterdata/foundation.

Richiede --previous con la baseline BP già rilasciata, prima del trasferimento.
Nessuna connessione, volume o credenziale dell'installazione attuale.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
CONTAINER='enginia360-masterdata-schema-proof'
SCOPE='business-partner-masterdata-proof'
TABLES=('business_partner','business_partner_tax_identifier','business_partner_address',
        'business_partner_address_usage','business_partner_contact_channel')
MIGRATION=ROOT/'database/migrations/20261119_business_partner_masterdata.sql'
FIXTURE="""
INSERT INTO foundation.tenant(id,code,name) VALUES('a1000000-0000-0000-0000-000000000001','masterdata-proof','Verifica');
INSERT INTO foundation.company(id,tenant_id,name) VALUES('a1000000-0000-0000-0000-000000000002','a1000000-0000-0000-0000-000000000001','Azienda conservata');
INSERT INTO foundation.numbering_series(id,tenant_id,mode,prefix,padding) VALUES('a1000000-0000-0000-0000-000000000003','a1000000-0000-0000-0000-000000000001','AUTO','BP-',6);
INSERT INTO foundation.numbering_counter(series_id,tenant_id,next_number,used) VALUES('a1000000-0000-0000-0000-000000000003','a1000000-0000-0000-0000-000000000001',8,true);
INSERT INTO foundation.business_partner(id,tenant_id,kind,code,legal_name) VALUES('a1000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000001','ORGANIZATION','BP-000007','Soggetto conservato');
INSERT INTO foundation.business_partner_tax_identifier(tenant_id,business_partner_id,country_code,identifier_type,value,normalized_value) VALUES('a1000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000004','IT','VAT','12345678901','12345678901');
INSERT INTO foundation.business_partner_address(id,tenant_id,business_partner_id,street,city,postal_code,country_code) VALUES('a1000000-0000-0000-0000-000000000005','a1000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000004','Via Roma','Roma','00100','IT');
INSERT INTO foundation.business_partner_address_usage(tenant_id,business_partner_id,address_id,usage,is_default) VALUES('a1000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000004','a1000000-0000-0000-0000-000000000005','BILLING',true);
INSERT INTO foundation.business_partner_contact_channel(tenant_id,business_partner_id,channel_type,value,is_primary) VALUES('a1000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000004','EMAIL','proof@example.invalid',true);
INSERT INTO foundation.audit_event(tenant_id,action,resource) VALUES('a1000000-0000-0000-0000-000000000001','proof','business-partners');
"""


def docker(*args,input=None,check=True):
    return subprocess.run(['docker',*args],input=input,text=True,capture_output=True,check=check,timeout=120)


def require_isolated():
    info=json.loads(docker('inspect',CONTAINER).stdout)[0]
    if (info['Config']['Labels'].get('enginia360.scope')!=SCOPE
        or info['HostConfig']['NetworkMode']!='none' or info['HostConfig']['PortBindings']
        or any(m['Type']!='tmpfs' for m in info['Mounts'])):
        raise RuntimeError('Cluster di prova non isolato')


def sql(statement,database='bp_upgraded',role='postgres',check=True):
    require_isolated()
    if not database.startswith('bp_') or role not in ('postgres','enginia360_app'):
        raise ValueError('Ambito SQL di prova non valido')
    login='postgres' if role=='postgres' else 'enginia360_proof_login'
    return docker('exec','-i',CONTAINER,'psql','-X','-qAt','-U',login,'-d',database,
                  '-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose',input=('SET ROLE enginia360_app;\n' if role!='postgres' else '')+statement,check=check)


def snapshot(database):
    relations=json.loads(sql("SELECT json_agg(json_build_array(c.oid,c.relname,c.relkind,c.relowner,c.relacl,c.relfilenode) ORDER BY c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata') AND c.relkind IN ('r','i')",database).stdout)
    constraints=json.loads(sql("SELECT json_agg(json_build_array(oid,conname,conrelid,confrelid,conkey,confkey,contype) ORDER BY oid) FROM pg_constraint WHERE connamespace IN (SELECT oid FROM pg_namespace WHERE nspname IN ('foundation','masterdata'))",database).stdout)
    triggers=json.loads(sql("SELECT json_agg(json_build_array(t.oid,t.tgrelid,t.tgfoid,t.tgname,t.tgenabled) ORDER BY t.oid) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata')",database).stdout)
    data={}
    tables=json.loads(sql("SELECT json_agg(json_build_array(schemaname,tablename) ORDER BY tablename) FROM pg_tables WHERE schemaname IN ('foundation','masterdata')",database).stdout)
    for schema,table in tables:
        data[table]=sql(f'SELECT md5(coalesce(string_agg(v::text,E\'\\n\' ORDER BY v::text),\'\')) FROM (SELECT to_jsonb(t) v FROM {schema}."{table}" t) x',database).stdout.strip()
    return {'relations':relations,'constraints':constraints,'triggers':triggers,'data':data}


def dump(database):
    require_isolated()
    raw=docker('exec',CONTAINER,'pg_dump','-U','postgres','-d',database,'--schema-only','--schema=foundation','--schema=masterdata').stdout
    return ''.join(line for line in raw.splitlines(keepends=True) if not line.startswith(('\\restrict ','\\unrestrict ')))


class MasterdataProof(unittest.TestCase):
    def test_01_transfer_preserves_data_oids_fks_indexes_triggers_and_acls(self):
        self.assertEqual(snapshot('bp_upgraded'),self.before)
        self.assertEqual(sql("SELECT string_agg(schemaname||'.'||tablename,',' ORDER BY tablename) FROM pg_tables WHERE tablename LIKE 'business_partner%'",'bp_upgraded').stdout.strip(),','.join('masterdata.'+t for t in sorted(TABLES)))
        self.assertEqual(sql("SELECT count(*) FROM pg_tables WHERE schemaname='foundation' AND tablename IN ('numbering_series','numbering_counter')",'bp_upgraded').stdout.strip(),'2')

    def test_02_fresh_and_upgraded_schema_and_acls_are_identical(self):
        self.assertEqual(dump('bp_fresh'),dump('bp_upgraded'))

    def test_03_runtime_access_and_cross_schema_integrity(self):
        self.assertEqual(sql('SELECT count(*) FROM masterdata.business_partner','bp_upgraded','enginia360_app').stdout.strip(),'1')
        for statement in ('CREATE TABLE masterdata.forbidden(id int)','DELETE FROM masterdata.business_partner',
                          'DELETE FROM foundation.numbering_series','TRUNCATE masterdata.business_partner CASCADE'):
            result=sql('BEGIN;'+statement+';ROLLBACK;','bp_upgraded','enginia360_app',False)
            self.assertNotEqual(result.returncode,0,statement);self.assertIn('42501',result.stderr)
        result=sql("BEGIN;INSERT INTO masterdata.business_partner_contact_channel(tenant_id,business_partner_id,channel_type,value) VALUES('a2000000-0000-0000-0000-000000000001','a1000000-0000-0000-0000-000000000004','PHONE','123');ROLLBACK;",check=False)
        self.assertNotEqual(result.returncode,0);self.assertIn('23503',result.stderr)
        result=sql("BEGIN;UPDATE masterdata.business_partner SET code='CHANGED';ROLLBACK;",check=False)
        self.assertNotEqual(result.returncode,0);self.assertIn('23514',result.stderr)

    def test_04_second_application_is_refused_without_changes(self):
        before=snapshot('bp_upgraded');result=sql(MIGRATION.read_text(),check=False)
        self.assertNotEqual(result.returncode,0);self.assertEqual(snapshot('bp_upgraded'),before)

    def test_05_late_failure_rolls_back_schema_move(self):
        before=snapshot('bp_rollback')
        source=MIGRATION.read_text();self.assertIn('COMMIT;',source)
        bad=source.rsplit('COMMIT;',1)[0]+'SELECT 1/0;\nCOMMIT;'
        result=sql(bad,'bp_rollback',check=False)
        self.assertNotEqual(result.returncode,0);self.assertIn('division by zero',result.stderr)
        self.assertEqual(snapshot('bp_rollback'),before)
        self.assertEqual(sql("SELECT count(*) FROM pg_tables WHERE schemaname='foundation' AND tablename LIKE 'business_partner%'",'bp_rollback').stdout.strip(),'5')
        sql(source,'bp_rollback')
        self.assertEqual(snapshot('bp_rollback'),before)

    def test_06_collision_refuses_without_partial_changes(self):
        sql('CREATE SCHEMA masterdata; CREATE TABLE masterdata.business_partner(id integer);','bp_collision')
        before=snapshot('bp_collision');result=sql(MIGRATION.read_text(),'bp_collision',check=False)
        self.assertNotEqual(result.returncode,0);self.assertEqual(snapshot('bp_collision'),before)

    def test_07_fresh_installation_has_no_seed_data(self):
        counts=sql("SELECT (SELECT count(*) FROM masterdata.business_partner)+(SELECT count(*) FROM foundation.numbering_series)+(SELECT count(*) FROM foundation.tenant)",'bp_fresh').stdout.strip()
        self.assertEqual(counts,'0')
        result=sql("SELECT has_schema_privilege('enginia360_app','masterdata','USAGE'),has_schema_privilege('enginia360_app','masterdata','CREATE'),EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) a WHERE n.nspname='masterdata' AND a.grantee=0),has_table_privilege('enginia360_app','masterdata.business_partner','DELETE')",'bp_fresh').stdout.strip()
        self.assertEqual(result,'t|f|f|f')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if docker('inspect',CONTAINER,check=False).returncode==0:raise RuntimeError('Container gia presente: non adottato')
    args.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    owned=docker('run','-d','--name',CONTAINER,'--label','enginia360.scope='+SCOPE,'--network','none',
                 '--tmpfs','/var/lib/postgresql','--tmpfs','/var/run/postgresql','-e','POSTGRES_HOST_AUTH_METHOD=trust',
                 '-e','POSTGRES_DB=bp_upgraded','postgres:18.6-alpine3.24').stdout.strip()
    try:
        for _ in range(100):
            logs=docker('logs',CONTAINER);ready=docker('exec',CONTAINER,'pg_isready','-U','postgres',check=False)
            if ready.returncode==0 and 'PostgreSQL init process complete; ready for start up.' in logs.stdout+logs.stderr:break
            time.sleep(.3)
        else:raise RuntimeError('PostgreSQL non pronto')
        sql('CREATE ROLE enginia360_app NOLOGIN; CREATE ROLE enginia360_proof_login LOGIN IN ROLE enginia360_app;')
        old=args.previous.read_text()
        for db in ('bp_upgraded','bp_rollback','bp_collision'):
            if db!='bp_upgraded':docker('exec',CONTAINER,'createdb','-U','postgres',db)
            sql(old,db);sql(FIXTURE,db)
        MasterdataProof.before=snapshot('bp_upgraded')
        sql(MIGRATION.read_text())
        docker('exec',CONTAINER,'createdb','-U','postgres','bp_fresh')
        sql((ROOT/'database/foundation.sql').read_text(),'bp_fresh')
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MasterdataProof))
        report={'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                'migrationSha256':hashlib.sha256(MIGRATION.read_bytes()).hexdigest()}
        (args.output/'proof.json').write_text(json.dumps(report,indent=2))
        return 0 if result.wasSuccessful() else 1
    finally:
        require_isolated();info=json.loads(docker('inspect',CONTAINER).stdout)[0]
        if info['Id']!=owned:raise RuntimeError('Identita container cambiata')
        docker('rm','-f',CONTAINER)


if __name__=='__main__':
    raise SystemExit(main())
