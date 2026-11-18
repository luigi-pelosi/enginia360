"""Prova ripetibile della baseline in un nuovo cluster PG18 effimero.

python3 tests/database/prove_foundation.py --oracle /percorso/live-schema.sql \
  --output /root/.hermes/cache/scratch/enginia360-foundation-close/sql
L'oracolo deve essere un pg_dump --schema-only --schema=foundation, acquisito
in sola lettura. Questo programma non si collega mai al database live.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from dbbaseline import CONTAINER, SCOPE, sql, dump_schema, normalize_dump, normalize_product_dump, personal_grant_lines, require_isolated
from test_foundation import TABLES

ROOT=Path(__file__).resolve().parents[2]
IMAGE='postgres:18.6-alpine3.24@sha256:123b17998ccaf47e53b502e8c6a1e79afd8f579c6f3eec83c563da026f957395'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    oracle=args.oracle.read_text()
    if 'CREATE SCHEMA foundation;' not in oracle or oracle.count('CREATE TABLE foundation.')!=23:
        raise RuntimeError('Oracolo incompleto o non conforme: attese 23 tabelle foundation')
    args.output.mkdir(parents=True,exist_ok=True)
    baseline=(ROOT/'database/foundation.sql').read_text()
    (args.output/'foundation.sql').write_text(baseline)
    report={'image':IMAGE,'container':CONTAINER,'scope':SCOPE,
            'foundation_sha256':hashlib.sha256(baseline.encode()).hexdigest(),
            'oracle_sha256':hashlib.sha256(oracle.encode()).hexdigest(), 'checks':[]}
    owned_id=None

    def record(name,passed,**details):
        report['checks'].append(dict(name=name,passed=bool(passed),**details))
        (args.output/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
        if not passed:raise AssertionError(name+': '+json.dumps(details))

    def execute(name,statement,database='enginia360',success=True,contains=None):
        result=sql(statement,database=database,check=False)
        (args.output/(name+'.log')).write_text(result.stdout+result.stderr)
        good=(result.returncode==0)==success and (contains is None or contains in result.stderr)
        record(name,good,returncode=result.returncode)
        return result

    def zero_rows(name):
        names=json.loads(sql("SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='foundation'").stdout)
        record(name+'-inventory',names==sorted(TABLES),tables=names,count=len(names))
        counts=json.loads(sql('SELECT json_build_object('+','.join("'"+t+"',(SELECT count(*) FROM foundation.\""+t+'\")' for t in names)+')').stdout)
        record(name,len(counts)==23 and all(v==0 for v in counts.values()),rows=counts)

    def terminate(signum,frame):
        raise SystemExit('Segnale di arresto '+str(signum))

    signal.signal(signal.SIGTERM,terminate)
    try:
        existing=subprocess.run(['docker','inspect',CONTAINER],capture_output=True,text=True)
        if existing.returncode==0:raise RuntimeError('Nome container già occupato: non viene adottato o eliminato')
        command=['docker','run','--detach','--name',CONTAINER,'--label','enginia360.scope='+SCOPE,
                 '--network','none','--read-only','--user','postgres','--cap-drop','ALL',
                 '--security-opt','no-new-privileges','--memory','512m','--cpus','1','--pids-limit','128',
                 '--shm-size','64m','--tmpfs','/var/lib/postgresql:rw,noexec,nosuid,size=256m,uid=70,gid=70',
                 '--tmpfs','/var/run/postgresql:rw,noexec,nosuid,size=8m,uid=70,gid=70',
                 '--tmpfs','/tmp:rw,noexec,nosuid,size=32m,uid=70,gid=70',
                 '--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=1',
                 '-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=enginia360',IMAGE]
        owned_id=subprocess.check_output(command,text=True,timeout=60).strip()
        os.environ['ENGINIA360_BASELINE_PROOF']='1'
        for _ in range(160):
            ready=subprocess.run(['docker','exec',CONTAINER,'pg_isready','-U','postgres'],capture_output=True)
            logs=subprocess.run(['docker','logs',CONTAINER],capture_output=True,text=True)
            if ready.returncode==0 and 'PostgreSQL init process complete; ready for start up.' in logs.stdout:break
            time.sleep(.25)
        else:raise RuntimeError('PostgreSQL non pronto')
        require_isolated()
        info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
        (args.output/'container.json').write_text(json.dumps(info,indent=2)+'\n')
        record('isolated-cluster',info['HostConfig']['ReadonlyRootfs']
               and info['HostConfig']['Memory']==512*1024*1024
               and info['HostConfig']['PidsLimit']==128
               and info['HostConfig']['NetworkMode']=='none'
               and not info['HostConfig']['PortBindings']
               and all(m['Type']=='tmpfs' for m in info['Mounts']))
        execute('missing-roles-fail-closed',baseline,success=False,contains='Ruoli prerequisiti mancanti')
        record('missing-roles-no-schema',sql("SELECT to_regnamespace('foundation') IS NULL").stdout.strip()=='t')
        execute('prerequisite-roles','CREATE ROLE enginia360_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS; CREATE ROLE enginia360_proof_login LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS IN ROLE enginia360_app;')
        record('personal-role-absent-before-install',sql("SELECT NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='luigi_pelosi')").stdout.strip()=='t')
        execute('unsafe-role-create-db','CREATE DATABASE enginia360_proof_unsafe;')
        execute('unsafe-role-setup','ALTER ROLE enginia360_app CREATEDB;')
        execute('unsafe-role-refused',baseline,database='enginia360_proof_unsafe',success=False,contains='privo di privilegi elevati')
        execute('unsafe-role-reset','ALTER ROLE enginia360_app NOCREATEDB; CREATE ROLE enginia360_proof_group NOLOGIN; GRANT enginia360_proof_group TO enginia360_app;')
        execute('unsafe-membership-refused',baseline,database='enginia360_proof_unsafe',success=False,contains='privo di privilegi elevati')
        execute('unsafe-membership-reset','REVOKE enginia360_proof_group FROM enginia360_app;')
        record('unsafe-role-no-schema',sql("SELECT to_regnamespace('foundation') IS NULL",database='enginia360_proof_unsafe').stdout.strip()=='t')
        execute('atomic-create-db','CREATE DATABASE enginia360_proof_atomic;')
        faulty=baseline.rsplit('COMMIT;',1)
        execute('atomic-injected-failure',faulty[0]+"SELECT 1/0;\nCOMMIT;\n",database='enginia360_proof_atomic',success=False,contains='division by zero')
        record('atomic-no-partial-schema',sql("SELECT to_regnamespace('foundation') IS NULL",database='enginia360_proof_atomic').stdout.strip()=='t')
        execute('atomic-retry-success',baseline,database='enginia360_proof_atomic')
        execute('existing-schema-create-db','CREATE DATABASE enginia360_proof_existing;')
        execute('existing-empty-schema-setup','CREATE SCHEMA foundation;',database='enginia360_proof_existing')
        execute('existing-empty-schema-refused',baseline,database='enginia360_proof_existing',success=False,contains='foundation esiste già')
        record('existing-empty-schema-unchanged',sql("SELECT count(*) FROM pg_class WHERE relnamespace='foundation'::regnamespace",database='enginia360_proof_existing').stdout.strip()=='0')
        # Il lock deve appartenere al backend che applica tutto il file SQL.
        lock_probe="""DO $probe$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid()
                AND locktype='advisory' AND classid=0 AND objid=3607902026 AND granted) THEN
                RAISE EXCEPTION 'lock applicazione assente';
            END IF;
        END $probe$;"""
        execute('first-apply',faulty[0]+lock_probe+'\nCOMMIT;\n')
        zero_rows('baseline-zero-rows')
        fresh=dump_schema()
        (args.output/'fresh-schema.sql').write_text(fresh)
        left,right=normalize_product_dump(oracle),normalize_product_dump(fresh)
        delta=''.join(difflib.unified_diff(left.splitlines(True),right.splitlines(True),fromfile='live',tofile='fresh'))
        (args.output/'schema.diff').write_text(delta)
        record('canonical-schema-equal',left==right,normalization='intestazione versioni/nonce + esclusivamente GRANT foundation TO luigi_pelosi; nessuna altra riga omessa')
        strict_left,strict_right=normalize_dump(oracle),normalize_dump(fresh)
        edits=[]
        for tag,i,j,k,l in difflib.SequenceMatcher(None,strict_left.splitlines(True),strict_right.splitlines(True),autojunk=False).get_opcodes():
            if tag!='equal':
                edits.append(dict(operation=tag,removed=strict_left.splitlines(True)[i:j],added=strict_right.splitlines(True)[k:l]))
        approved=personal_grant_lines(oracle)
        exact=bool(approved) and not personal_grant_lines(fresh) and all(e['operation']=='delete' and not e['added'] and all(line in approved for line in e['removed']) for e in edits)
        delta_report=dict(exact_approved_delta=approved,personal_grants_removed=len(approved),
            edits=edits,no_other_line_omitted=exact,
            scope='Nuove installazioni soltanto; oracolo live salvato, nessuna connessione live; ACL live non modificate',
            technical_normalization='Solo righe -- Dumped from/by e nonce restrict/unrestrict preesistenti')
        (args.output/'approved-delta.json').write_text(json.dumps(delta_report,indent=2)+'\n')
        (args.output/'personal-acl-only.diff').write_text(''.join(difflib.unified_diff(strict_left.splitlines(True),strict_right.splitlines(True),fromfile='saved-live',tofile='portable-fresh')))
        record('exact-approved-delta-no-other-lines-omitted',exact,removed=len(approved))
        record('personal-role-still-absent',sql("SELECT NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='luigi_pelosi')").stdout.strip()=='t')
        before=sql("SELECT json_agg(json_build_array(oid,relname) ORDER BY oid) FROM pg_class WHERE relnamespace='foundation'::regnamespace").stdout
        execute('second-apply-refused',baseline,success=False,contains='foundation esiste già')
        after=sql("SELECT json_agg(json_build_array(oid,relname) ORDER BY oid) FROM pg_class WHERE relnamespace='foundation'::regnamespace").stdout
        record('second-apply-no-change',before==after and normalize_dump(dump_schema())==right)
        zero_rows('second-apply-zero-rows')
        modules=['test_foundation','test_optional_code_schema','test_commercial_organizations',
                 'test_required_site_addresses','test_site_classification','test_site_addresses','test_dbbaseline']
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'tests/database')
        tests=subprocess.run([sys.executable,'-m','unittest','-v',*modules],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
        (args.output/'database-tests.log').write_text(tests.stdout+tests.stderr)
        count=re.search(r'Ran (\d+) tests',tests.stderr)
        record('current-invariant-tests',tests.returncode==0 and count is not None and int(count[1])==39,
               returncode=tests.returncode,executed=int(count[1]) if count else None,
               skipped=tests.stderr.count('... skipped'))
        zero_rows('post-tests-zero-rows')
        record('schema-still-canonical-after-tests',normalize_dump(dump_schema())==right)
        extra=subprocess.run([sys.executable,'-m','unittest','-v','test_portable_baseline'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
        (args.output/'portable-tests.log').write_text(extra.stdout+extra.stderr)
        record('portable-normalization-regressions',extra.returncode==0 and 'Ran 2 tests' in extra.stderr,executed=2,returncode=extra.returncode)
        execute('concurrent-create-db','CREATE DATABASE enginia360_proof_concurrent;')
        cmd=['docker','exec','-i',CONTAINER,'psql','-U','postgres','-d','enginia360_proof_concurrent','-X','-qAt','-v','ON_ERROR_STOP=1']
        runners=[]
        try:
            first=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            runners.append(first)
            first.stdin.write(baseline.replace('SELECT pg_catalog.pg_advisory_xact_lock(3607902026);','SELECT pg_catalog.pg_advisory_xact_lock(3607902026); SELECT pg_sleep(4);',1));first.stdin.close();first.stdin=None
            for _ in range(80):
                if sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objid=3607902026 AND granted",database='enginia360_proof_concurrent').stdout.strip()=='1':break
                time.sleep(.05)
            else:raise AssertionError('Primo installatore senza lock')
            second=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            runners.append(second)
            second.stdin.write(baseline);second.stdin.close();second.stdin=None
            waiting=False
            for _ in range(60):
                if sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objid=3607902026 AND NOT granted",database='enginia360_proof_concurrent').stdout.strip()=='1':
                    waiting=True;break
                time.sleep(.05)
            out1,err1=first.communicate(timeout=30);out2,err2=second.communicate(timeout=30)
            (args.output/'concurrent-first.log').write_text(out1+err1)
            (args.output/'concurrent-second.log').write_text(out2+err2)
            record('concurrent-install-serialized',waiting and first.returncode==0 and second.returncode!=0 and 'foundation esiste già' in err2,waiter_observed=waiting,returncodes=[first.returncode,second.returncode])
            counts=sql("SELECT count(*) FROM pg_tables WHERE schemaname='foundation'",database='enginia360_proof_concurrent').stdout.strip()
            record('concurrent-installed-exactly-once',counts=='23',tables=counts)
        finally:
            for process in runners:
                if process.poll() is None:process.kill();process.wait(timeout=10)
        report['passed']=True
    except BaseException as error:
        report['passed']=False
        report['error']=str(error)
        raise
    finally:
        if owned_id:
            info=json.loads(subprocess.check_output(['docker','inspect',CONTAINER],text=True))[0]
            if info['Id']!=owned_id or info['Config']['Labels'].get('enginia360.scope')!=SCOPE:
                raise RuntimeError('Identità cambiata: cleanup rifiutato')
            (args.output/'container.log').write_text(subprocess.check_output(['docker','logs',CONTAINER],text=True,stderr=subprocess.STDOUT))
            subprocess.run(['docker','rm','--force',owned_id],capture_output=True,text=True,check=True,timeout=30)
            check=subprocess.run(['docker','inspect',CONTAINER],capture_output=True,text=True)
            report['cleanup_absent']=check.returncode!=0 and 'no such object' in check.stderr.lower()
            if not report['cleanup_absent']:report['passed']=False
        (args.output/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report.get('passed') or not report.get('cleanup_absent'):
        raise RuntimeError('Prova o cleanup non completati: consultare proof.json')


if __name__=='__main__':
    main()
