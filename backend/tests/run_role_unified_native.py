"""Freeze recursive backend sources and run native proof in cached, offline SDK."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path('/root/.hermes/cache/scratch/enginia360-role-unified-save/backend')
PHASE = sys.argv[1] if len(sys.argv) > 1 else 'green'
TARGET = OUT / PHASE
TARGET.mkdir(parents=True, exist_ok=False)
src = TARGET / 'src'
sources = [p for p in (ROOT / 'backend').rglob('*') if p.is_file()
           and not set(p.relative_to(ROOT / 'backend').parts) & {'obj', 'bin', 'publish', '__pycache__'}
           and (p.suffix in {'.cs', '.csproj'} or p.name == 'packages.lock.json')]
manifest = {}
for p in sorted(sources):
    rel = p.relative_to(ROOT / 'backend')
    dest = src / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
    manifest[str(rel)] = hashlib.sha256(dest.read_bytes()).hexdigest()
(TARGET / 'source-hashes.json').write_text(json.dumps(manifest, indent=2) + '\n')
runner = TARGET / 'runner'
runner.mkdir()
(runner / 'Native.csproj').write_text('''<Project Sdk="Microsoft.NET.Sdk">
<PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings></PropertyGroup>
<ItemGroup><FrameworkReference Include="Microsoft.AspNetCore.App"/><Reference Include="Enginia360.Api"><HintPath>/proof/publish/Enginia360.Api.dll</HintPath></Reference></ItemGroup></Project>''')
(runner / 'Program.cs').write_text('''using Enginia360.Verification.AccessControl;
var passed=0; var failed=0;
RoleUnifiedSaveTests.RunNative((name,run)=>{try {run(); Console.WriteLine("PASS "+name); passed++;} catch(Exception e) {Console.WriteLine("FAIL "+name+": "+e); failed++;}});
Console.WriteLine($"native passed={passed} failed={failed}");
Environment.ExitCode=failed==0 ? 0 : 1;
''')
command = '''set -u
cp -a /src/obj /proof/src/obj || exit $?
dotnet publish /proof/src/Enginia360.Api.csproj -c Release --no-restore -o /proof/publish /p:UseSharedCompilation=false /m:1
rc=$?; printf '%s\\n' "$rc" > /proof/publish.exit; [ "$rc" = 0 ] || exit "$rc"
cd /proof/runner || exit $?
dotnet build -c Release -o out /p:UseSharedCompilation=false /m:1
rc=$?; printf '%s\\n' "$rc" > /proof/runner-build.exit; [ "$rc" = 0 ] || exit "$rc"
cp /proof/publish/*.dll out/ || exit $?
cp /proof/publish/Enginia360.Api.deps.json out/Native.deps.json || exit $?
dotnet out/Native.dll
rc=$?; printf '%s\\n' "$rc" > /proof/selftest.exit; exit "$rc"
'''
with (TARGET / 'native.log').open('w') as log:
    result = subprocess.run(['docker','run','--rm','--network=none','--read-only','--tmpfs','/tmp',
        '-e','DOTNET_CLI_HOME=/tmp/dotnet','-e','DOTNET_NOLOGO=1','-v',f'{TARGET}:/proof',
        '--entrypoint','sh','enginia360-role-unified-sdk:local','-c',command], stdout=log, stderr=subprocess.STDOUT)
    log.write(f'\nexit={result.returncode}\n')
(TARGET / 'exit.json').write_text(json.dumps({'native':result.returncode})+'\n')
assert manifest == {str(p.relative_to(src)):hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in src.rglob('*') if p.is_file() and p.suffix == '.cs' and not set(p.relative_to(src).parts) & {'obj','bin'}} | {k:v for k,v in manifest.items() if not k.endswith('.cs')}
print((TARGET / 'native.log').read_text())
sys.exit(result.returncode)
