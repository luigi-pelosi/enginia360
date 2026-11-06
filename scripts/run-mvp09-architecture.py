#!/usr/bin/env python3
"""Explicit exceptional final campaign adapter, not routine impact selection.
Runs the actual existing workflow commands serially per finite consumer group.
The historical full-architecture jobs remain unchanged and separately opt-in.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
# Finite seven-domain MVP consumers plus evidenced shared producers.
# This is not a requirement to repair every retained historical workflow.
GROUPS = (
    'impact',
    'affected-integrated-acceptance',
    'affected-document-development',
    'affected-documents',
    'affected-document-types',
    'affected-catalog-management',
    'affected-counterparty-management',
    'affected-federated-onboarding',
    'affected-membership-access',
    'affected-tenant-roles',
    'affected-platform-offline',
    'affected-platform-authority',
    'affected-organization-administration',
    'affected-authenticated-organization',
    'affected-frontend',
    'affected-frontend-runtime',
    'affected-mvp-offline',
    'affected-r05a2-offline',
    'affected-r05a3-offline',
    'affected-r06-offline',
    'affected-migrations',
    'affected-browser',
    'affected-r06-restore',
)
# API fast tests/build/audit have their own explicit final job (no impact filter).
SEPARATE_FINAL = {'affected-api'}
# Retained and available; not MVP final prerequisites absent a concrete impact.
RETAINED_LEGACY = {
    'affected-editor',
    'affected-r03a',
    'affected-r03a2',
    'affected-r03b',
    'affected-r03c',
    'affected-r04a',
    'affected-r04b2a',
    'affected-r04b2b1',
    'affected-r04b2b2',
    'affected-r04b2b3',
    'affected-r04c1',
    'affected-r04c2',
    'affected-r05a1-offline',
    'affected-r05a4-offline',
    'affected-r05a5-offline',
    'affected-r05a6-offline',
    'affected-r05a7-offline',
    'affected-r05a8-offline',
    'affected-r05b0',
    'affected-r05b1',
    'affected-r06-staging',
    'affected-ui',
}


def jobs(text):
    return dict(re.findall(r'^  ([a-z0-9-]+):\n(.*?)(?=^  [a-z0-9-]+:|\Z)', text, re.M | re.S))


def plan(text, group):
    if group not in GROUPS:
        raise ValueError('unmapped exceptional consumer group')
    blocks = jobs(text)
    if {name for name in blocks if name.startswith('affected-')} != set(GROUPS)-{'impact'} | SEPARATE_FINAL | RETAINED_LEGACY:
        raise ValueError('new or lost consumer: map explicitly, never silently skip')
    block = blocks[group]
    budget = re.search(r'^    timeout-minutes: ([1-9][0-9]*)$', block, re.M)
    if budget is None: raise ValueError('explicit original job budget required')
    deadline = int(budget.group(1))*60
    if re.search(r'^    (?:env|defaults|container):', block, re.M):
        raise ValueError('unsupported inherited execution configuration')
    steps = []
    for chunk in re.split(r'^      - ', block, flags=re.M)[1:]:
        if '\n        run:' not in chunk:
            if re.search(r'^(?:run:|        run\s*:)', chunk, re.M):
                raise ValueError('unsupported unnamed executable YAML step')
            if not re.search(r'^(?:uses:|        uses:)', chunk, re.M):
                raise ValueError('unsupported non-executable YAML step')
            continue  # checkout/artifact actions are owned by the enclosing CI job
        name = re.search(r'^name: (.+)$', chunk, re.M)
        if name is None:
            raise ValueError('named executable step required')
        for key, value in re.findall(r'^        ([a-z-]+): ?(.*)$', chunk, re.M):
            if key not in {'run', 'env', 'shell', 'id'} or (key == 'shell' and value != 'bash'):
                raise ValueError('unsupported executable YAML field: '+key)
        name = name.group(1)
        if group == 'impact' and name == 'Select exact changed-file impact':
            continue  # selection is not acceptance, and full mode has no impact output
        match = re.search(r'^        run: (.*)$', chunk, re.M)
        if match is None: raise ValueError('explicit executable command required')
        command = match.group(1)
        if command == '|':
            rest = chunk[match.end():].splitlines()
            lines = []
            for line in rest:
                if not line.strip():
                    lines.append(''); continue
                if not line.startswith('          '):
                    break
                lines.append(line[10:])
            command = '\n'.join(lines).strip()
        elif not command or command in ('>', '|-', '>-'):
            raise ValueError('unsupported executable YAML form')
        env = {}
        env_match = re.search(r'^        env:\n((?:          [^\n]*\n?)+)', chunk, re.M)
        if env_match:
            for line in env_match.group(1).splitlines():
                key, value = line.strip().split(': ', 1)
                if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or '${{' in value:
                    raise ValueError('explicit literal step environment required')
                env[key] = value.strip('\'"')
        if '${{' in command:
            raise ValueError('unresolved workflow expression in executable command')
        steps.append(dict(name=name, command=command, env=env))
    if not steps:
        raise ValueError('empty campaign consumer is not pass')
    return dict(group=group, deadlineSeconds=deadline, steps=steps)


def execute(prepared, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    envfile = evidence/'github-env.txt'
    envfile.touch()
    env = dict(os.environ, GITHUB_ENV=str(envfile))
    # Each original command keeps its original RUNNER_TEMP paths and bounds.
    # Fixture scratch is not copied wholesale into retained artifacts.
    assert env.get('TMPDIR') and env.get('RUNNER_TEMP')
    source_paths = subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=ROOT,text=True).split('\0')
    source_hashes = {path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in sorted(set(source_paths)) if path and (ROOT/path).is_file()}
    manifest = dict(status='RUNNING', plan=prepared, sourceHashes=source_hashes, sourceSha256=hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest(), head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), workflowSha256=hashlib.sha256((ROOT/'.github/workflows/ci.yml').read_bytes()).hexdigest(), steps=[], operationalReadiness=False)
    ledger = evidence/'execution.json'
    ledger.write_text(json.dumps(manifest, indent=2))
    deadline = time.monotonic()+prepared['deadlineSeconds']
    process = None
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        for index, step in enumerate(prepared['steps']):
            record = dict(index=index, name=step['name'], command=step['command'], status='RUNNING', started=time.time())
            manifest['steps'].append(record);ledger.write_text(json.dumps(manifest, indent=2))
            with (evidence/f'{index:02}.log').open('w') as log:
                process = subprocess.Popen(['bash','--noprofile','--norc','-e','-o','pipefail','-c',step['command']],cwd=ROOT,env=dict(env,**step['env']),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:
                    exit_code = process.wait(timeout=max(1, deadline-time.monotonic()))
                except BaseException:
                    os.killpg(process.pid,signal.SIGTERM)
                    try: process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                    record.update(status='NONPASS',exit=process.returncode,ended=time.time())
                    raise
            record.update(status='PASS' if exit_code==0 else 'NONPASS',exit=exit_code,ended=time.time())
            ledger.write_text(json.dumps(manifest,indent=2))
            if exit_code:
                raise RuntimeError('actual required step failed: '+step['name'])
            for line in envfile.read_text().splitlines():
                key, sep, value = line.partition('=')
                if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*',key):
                    raise ValueError('unsupported environment output')
                env[key] = value
        # Copy only the original jobs' explicit artifact directories after success.
        block=jobs((ROOT/'.github/workflows/ci.yml').read_text())[prepared['group']]
        for relative in re.findall(r'path: \$\{\{ runner.temp \}\}/([a-z0-9]+)\s*$',block,re.M):
            source=Path(os.environ['RUNNER_TEMP'])/relative
            if not source.is_dir(): raise ValueError('required original artifact missing')
            shutil.copytree(source,evidence/relative,dirs_exist_ok=True)
        manifest['status']='PASS'
    except BaseException:
        manifest['status']='NONPASS'
        raise
    finally:
        for record in manifest['steps']:
            logfile=evidence/f"{record['index']:02}.log"
            if logfile.is_file():
                record['logSha256']=hashlib.sha256(logfile.read_bytes()).hexdigest()
        for sig,handler in previous.items():signal.signal(sig,handler)
        ledger.write_text(json.dumps(manifest,indent=2))
        envfile.unlink(missing_ok=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',choices=GROUPS,required=True)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    args=parser.parse_args()
    if os.environ.get('MVP09_EXCEPTIONAL_FINAL')!='true':
        parser.error('explicit final-only authority required; routine selector never sets this')
    execute(plan((ROOT/'.github/workflows/ci.yml').read_text(),args.job),args.evidence_dir.resolve())
