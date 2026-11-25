"""Run targeted native HTTP/transaction proof on a fresh tmpfs-only PostgreSQL.
No live database, shared volumes, published ports, clone, auth-cookie or browser proof.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = Path('/root/.hermes/cache/scratch/enginia360-role-unified-save/backend')
PHASE = sys.argv[1] if len(sys.argv)>1 else 'green-expanded'
proof = BASE / PHASE
out = proof / (sys.argv[2] if len(sys.argv)>2 else 'runtime')
out.mkdir(exist_ok=False)
socket = out / 'socket'
socket.mkdir(mode=0o777)
socket.chmod(0o777)
schema = out / 'schema'
schema_input=Path(sys.argv[3]) if len(sys.argv)>3 else ROOT / 'database'
for p in schema_input.rglob('*.sql'):
    dst = schema / p.relative_to(schema_input)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p,dst)
(out / 'schema-hashes.json').write_text(json.dumps({str(p.relative_to(schema)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(schema.rglob('*.sql'))},indent=2)+'\n')
runner = out / 'runner'
runner.mkdir()
(runner / 'Runtime.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup><ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App"/><Reference Include="Enginia360.Api"><HintPath>/proof/publish/Enginia360.Api.dll</HintPath></Reference></ItemGroup></Project>''')
(runner / 'Program.cs').write_text('''using Enginia360.Verification.AccessControl;
var pass=0; var fail=0;
RoleUnifiedSaveRuntimeTests.Run("Host=/sockets;Database=enginia360;Username=postgres",(name,run)=>{try{run();Console.WriteLine("PASS "+name);pass++;}catch(Exception ex){Console.WriteLine("FAIL "+name+": "+ex);fail++;}});
Console.WriteLine($"runtime passed={pass} failed={fail}"); Environment.ExitCode=fail==0 ? 0 : 1;
''')
name = 'enginia360-role-unified-native-' + uuid.uuid4().hex[:10]
log = (out / 'runtime.log').open('w')
results = {}
def run(cmd, **kw):
    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, **kw)
    log.flush()
    return proc
try:
    run(['docker','run','-d','--name',name,'--label','enginia360.scope=role-unified-save','--network=none',
         '--tmpfs','/var/lib/postgresql','--tmpfs','/var/run/postgresql',
         '-v',f'{socket}:/sockets','-v',f'{schema}:/schema:ro','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','PGHOST=/sockets',
         '-e','POSTGRES_DB=enginia360','postgres:18.6-alpine3.24','-c','unix_socket_directories=/sockets,/var/run/postgresql']).check_returncode()
    info=json.loads(subprocess.check_output(['docker','inspect',name],text=True))[0]
    assert info['HostConfig']['NetworkMode']=='none' and not info['HostConfig']['PortBindings']
    assert info['Config']['Labels']['enginia360.scope']=='role-unified-save'
    assert all(m['Type'] in {'tmpfs','bind'} for m in info['Mounts'])
    (out/'isolation.json').write_text(json.dumps({'name':name,'image':info['Image'],'network':info['HostConfig']['NetworkMode'],'ports':info['HostConfig']['PortBindings'],'mounts':info['Mounts']},indent=2)+'\n')
    for _ in range(90):
        if subprocess.check_output(['docker','inspect','--format','{{.State.Running}}',name],text=True).strip()!='true':
            raise RuntimeError('Isolated PostgreSQL exited during initialization.')
        logs=subprocess.run(['docker','logs',name],capture_output=True,text=True)
        if 'PostgreSQL init process complete' in logs.stdout and run(['docker','exec',name,'pg_isready','-U','postgres','-d','enginia360','-h','/sockets']).returncode==0:
            break
        time.sleep(1)
    else:
        raise RuntimeError('Isolated PostgreSQL did not become ready.')
    run(['docker','exec',name,'psql','-h','/sockets','-U','postgres','-d','enginia360','-X','-v','ON_ERROR_STOP=1','-c','CREATE ROLE enginia360_app NOLOGIN']).check_returncode()
    results['schema']=run(['docker','exec',name,'psql','-h','/sockets','-U','postgres','-d','enginia360','-X','-v','ON_ERROR_STOP=1','-f','/schema/foundation.sql']).returncode
    if results['schema']:
        raise RuntimeError('Schema initialization failed.')
    command='''set -u
cd /proof/RUNTIME_DIR/runner || exit $?
dotnet build -c Release -o out /p:UseSharedCompilation=false /m:1
rc=$?; printf '%s\\n' "$rc" > /proof/RUNTIME_DIR/runner-build.exit; [ "$rc" = 0 ] || exit "$rc"
cp /proof/publish/*.dll out/ || exit $?
cp /proof/publish/Enginia360.Api.deps.json out/Runtime.deps.json || exit $?
dotnet out/Runtime.dll
rc=$?; printf '%s\\n' "$rc" > /proof/RUNTIME_DIR/selftest.exit; exit "$rc"
'''.replace('RUNTIME_DIR',out.name)
    results['runtime']=run(['docker','run','--rm','--network=none','--read-only','--tmpfs','/tmp',
        '-e','DOTNET_CLI_HOME=/tmp/dotnet','-e','DOTNET_NOLOGO=1','-e','ENGINIA360_ROLE_UNIFIED_ISOLATED=1',
        '-v',f'{proof}:/proof','-v',f'{socket}:/sockets:ro','--entrypoint','sh','enginia360-role-unified-sdk:local','-c',command],timeout=180).returncode
finally:
    run(['docker','logs',name])
    results['cleanup']=run(['docker','rm','-f',name]).returncode
    (out/'exit.json').write_text(json.dumps(results,indent=2)+'\n')
    log.close()
print((out/'runtime.log').read_text())
sys.exit(0 if results.get('runtime')==0 and results.get('cleanup')==0 else 1)
