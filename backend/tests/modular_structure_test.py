"""Contratto statico dei confini backend, senza dipendenze esterne."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = {
    'Modules/Identity': ['User', 'AuthEndpoints', 'Security'],
    'Modules/AccessControl': ['PermissionCatalog'],
    'Modules/Organizations': ['PurchasingCoverage'],
    'Modules/Geography': ['Geography', 'AddressLookup', 'CountryCodes'],
    'Infrastructure/Persistence': ['AppDb', 'SqlNames'],
    'Shared/Validation': ['Check', 'ApiException'],
    'Api/Resources': ['DataEndpoints', 'Resources'],
}

class ModularStructureTests(unittest.TestCase):
    def test_domain_sources_have_matching_namespaces(self):
        for folder, names in LAYOUT.items():
            for name in names:
                with self.subTest(source=name):
                    path = ROOT / folder / (name + '.cs')
                    self.assertTrue(path.is_file(), f'Missing domain source: {folder}/{name}.cs')
                    self.assertIn('namespace Enginia360.' + folder.replace('/', '.') + ';', path.read_text())
                    self.assertFalse((ROOT / (name + '.cs')).exists(), 'Stale flat source')

    def test_verification_is_compiled_and_domain_scoped(self):
        sources = [p for p in ROOT.rglob('*.cs') if not {'obj', 'bin', 'publish'}.intersection(p.relative_to(ROOT).parts)]
        tests = [p for p in sources if re.search(r'public static class \w*(?:SelfTests|Tests)\b', p.read_text())]
        self.assertGreaterEqual(len(tests), 13)
        for path in tests:
            self.assertEqual(path.relative_to(ROOT).parts[0], 'Verification', str(path))
            self.assertIn('namespace Enginia360.Verification.', path.read_text())
        self.assertNotIn('Compile Remove=', (ROOT / 'Enginia360.Api.csproj').read_text())

    def test_single_assembly_no_domain_global_imports(self):
        self.assertEqual(len(list(ROOT.glob('*.csproj'))), 1)
        self.assertEqual([p.name for p in ROOT.glob('*.cs')], ['Program.cs'])
        for path in ROOT.rglob('*.cs'):
            if {'obj', 'bin', 'publish'}.intersection(path.relative_to(ROOT).parts):
                continue
            self.assertNotRegex(path.read_text(), r'global using Enginia360\.')
        self.assertIn('WebApplication.CreateBuilder', (ROOT / 'Program.cs').read_text())

if __name__ == '__main__':
    unittest.main()
