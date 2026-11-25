"""Verifiche pure C# eseguite con SDK locale in container senza rete."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class CatalogBackendTests(unittest.TestCase):
    def test_exact_conversion_runtime(self):
        scratch = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch'))
        with tempfile.TemporaryDirectory(prefix='catalog-math-', dir=scratch) as folder:
            folder = Path(folder)
            links = ['Modules/Catalog/CatalogConversion.cs', 'Shared/Validation/Check.cs',
                     'Shared/Validation/ApiException.cs', 'Verification/Catalog/CatalogSelfTests.cs']
            (folder / 'Math.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable><TreatWarningsAsErrors>true</TreatWarningsAsErrors></PropertyGroup><ItemGroup>' + ''.join('<Compile Include="/repo/backend/' + p + '" />' for p in links) + '</ItemGroup></Project>')
            (folder / 'Program.cs').write_text('int count=0; Enginia360.Verification.Catalog.CatalogSelfTests.Run((name,test)=>{test(); count++;System.Console.WriteLine("PASS "+name);});if(count!=2)throw new System.Exception("Missing tests");')
            result = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '-v', str(ROOT)+':/repo:ro', '-v', str(folder)+':/proof', '-w', '/proof', '--entrypoint', 'dotnet', 'mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24', 'run', '--project', 'Math.csproj', '-c', 'Release'], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS catalog conversion uses exact ratio', result.stdout)
            print(result.stdout)

if __name__ == '__main__': unittest.main()
