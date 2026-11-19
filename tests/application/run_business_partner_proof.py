"""Ambiente BP effimero: nessun volume o credenziale dell'installazione attuale.

Origine HTTPS logica e trasporto loopback HTTP: non è una prova TLS.
Le fixture restano soltanto nei tmpfs del progetto di prova.
"""
import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCOPE = 'enginia360-business-partner-proof'
DB = SCOPE+'-db'
API = SCOPE+'-api'
WEB = SCOPE+'-web'
NETWORK = SCOPE
INGRESS = SCOPE+'-ingress'
ORIGIN = 'https://business-partner.invalid'
EVIDENCE = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) / SCOPE


def docker(*args, input=None, check=True):
    return subprocess.run(['docker', *args], input=input, text=True, capture_output=True, check=check, timeout=120)


def verify_target(name):
    response = docker('inspect', name, check=False)
    if response.returncode:
        return False
    info = json.loads(response.stdout)[0]
    if info['Config']['Labels'].get('enginia360.scope') != SCOPE:
        raise RuntimeError('Risorsa non appartenente alla prova BP: '+name)
    if any(mount['Type'] not in ('tmpfs', 'bind') for mount in info['Mounts']):
        raise RuntimeError('Mount persistente non ammesso per la prova BP')
    return True


def cleanup():
    for name in (WEB, API, DB):
        if verify_target(name):
            docker('rm', '-f', name)
    for name in (NETWORK, INGRESS):
        network = docker('network', 'inspect', name, check=False)
        if not network.returncode:
            info = json.loads(network.stdout)[0]
            if info['Labels'].get('enginia360.scope') != SCOPE:
                raise RuntimeError('Rete fuori scope')
            docker('network', 'rm', name)


def sql(statement, check=True):
    if not verify_target(DB):
        raise RuntimeError('Database isolato non disponibile')
    return docker('exec', '-i', DB, 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'enginia360', '-v', 'ON_ERROR_STOP=1', input=statement, check=check)


def port(name, internal):
    info = json.loads(docker('inspect', name).stdout)[0]
    return int(info['NetworkSettings']['Ports'][f'{internal}/tcp'][0]['HostPort'])


def start(args):
    cleanup()
    EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVIDENCE.chmod(0o700)
    credentials = {'username': 'bp-proof-admin', 'firstName': 'Amministratore', 'lastName': 'Prova',
                   'email': 'bp-proof@example.invalid', 'password': secrets.token_urlsafe(30)}
    credential_file = EVIDENCE / 'bootstrap.json'
    credential_file.write_text(json.dumps(credentials))
    credential_file.chmod(0o600)
    docker('network', 'create', '--internal', '--label', 'enginia360.scope='+SCOPE, NETWORK)
    docker('network', 'create', '--label', 'enginia360.scope='+SCOPE, INGRESS)
    docker('run', '-d', '--name', DB, '--label', 'enginia360.scope='+SCOPE, '--network', NETWORK,
           '--network-alias', 'database', '--tmpfs', '/var/lib/postgresql', '--tmpfs', '/var/run/postgresql',
           '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-e', 'POSTGRES_DB=enginia360', 'postgres:18.6-alpine3.24')
    for _ in range(60):
        logs = docker('logs', DB)
        initialized = 'PostgreSQL init process complete; ready for start up.' in logs.stdout + logs.stderr
        if initialized and docker('exec', DB, 'pg_isready', '-U', 'postgres', '-d', 'enginia360', check=False).returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError('PostgreSQL di prova non pronto')
    sql('CREATE ROLE enginia360_app LOGIN;')
    sql(Path(args.schema).read_text())
    for migration in args.migration or []:
        sql(Path(migration).read_text())
    app_uid = docker('run', '--rm', '--entrypoint', 'id', args.backend_image, '-u').stdout.strip()
    app_gid = docker('run', '--rm', '--entrypoint', 'id', args.backend_image, '-g').stdout.strip()
    # Il file bootstrap viene passato da stdin, senza mount di segreti o log delle credenziali.
    bootstrap = docker('run', '--rm', '-i', '--network', NETWORK,
           '--tmpfs', f'/app/keys:uid={app_uid},gid={app_gid},mode=0700',
           '-e', 'ConnectionStrings__Database=Host=database;Database=enginia360;Username=enginia360_app',
           '--entrypoint', '/bin/sh', args.backend_image, '-c',
           'umask 077; cat > /tmp/bp-bootstrap.json; dotnet Enginia360.Api.dll bootstrap /tmp/bp-bootstrap.json',
           input=json.dumps(credentials))
    (EVIDENCE / 'bootstrap.log').write_text(bootstrap.stdout+bootstrap.stderr)
    docker('create', '--name', API, '--label', 'enginia360.scope='+SCOPE,
           '--network', INGRESS, '-p', '127.0.0.1::8080',
           '--tmpfs', f'/app/keys:uid={app_uid},gid={app_gid},mode=0700',
           '-e', 'ConnectionStrings__Database=Host=database;Database=enginia360;Username=enginia360_app',
           '-e', 'App__Origin='+ORIGIN, args.backend_image)
    docker('network', 'connect', '--alias', 'backend', NETWORK, API)
    docker('start', API)
    api_port = port(API, 8080)
    for _ in range(60):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{api_port}/api/health', timeout=2).status == 200:
                break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError('API di prova non pronta')
    state = {'apiPort': api_port, 'origin': ORIGIN, 'credentials': str(credential_file), 'scope': SCOPE}
    if args.frontend_image:
        docker('create', '--name', WEB, '--label', 'enginia360.scope='+SCOPE,
               '--network', INGRESS, '-p', '127.0.0.1::3000', '-e', 'API_URL=http://backend:8080',
               '-e', 'HOSTNAME=0.0.0.0', '-e', 'PORT=3000', args.frontend_image)
        docker('network', 'connect', NETWORK, WEB)
        docker('start', WEB)
        state['webPort'] = port(WEB, 3000)
    (EVIDENCE / 'state.json').write_text(json.dumps(state))
    return state


def run_tests(state):
    os.environ.update(ENGINIA360_BP_PROOF='1', ENGINIA360_TEST_BASE=ORIGIN,
                      ENGINIA360_TEST_ORIGIN=ORIGIN, ENGINIA360_TEST_CREDENTIALS=state['credentials'])
    class IsolatedTransport(urllib.request.HTTPSHandler):
        def https_open(self, request):
            if request.host != 'business-partner.invalid':
                raise RuntimeError('Destinazione esterna rifiutata dalla prova BP')
            return self.do_open(lambda host, **kwargs: http.client.HTTPConnection('127.0.0.1', state['apiPort'], **kwargs), request)
    original = urllib.request.build_opener
    urllib.request.build_opener = lambda *handlers: original(IsolatedTransport(), *handlers)
    suite = unittest.defaultTestLoader.loadTestsFromName('test_business_partners')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        raise RuntimeError('Accettazione richiesta non eseguita')
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', default='enginia360-backend:bp-masterdata-schema')
    parser.add_argument('--frontend-image')
    parser.add_argument('--schema', default=str(ROOT/'database/foundation.sql'))
    parser.add_argument('--migration', action='append', help='Migrazione ordinata; opzione ripetibile')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if args.cleanup:
        cleanup()
        return 0
    try:
        state = json.loads((EVIDENCE/'state.json').read_text()) if args.reuse else start(args)
        if not verify_target(API) or not verify_target(DB):
            raise RuntimeError('Risorse BP isolate mancanti')
        return run_tests(state)
    finally:
        if not args.keep:
            cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
