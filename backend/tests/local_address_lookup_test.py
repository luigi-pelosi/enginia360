"""Regressione statica del perimetro locale; nessuna connessione o segreto."""
from pathlib import Path
import unittest

BACKEND = Path(__file__).resolve().parents[1]


class LocalAddressLookupContract(unittest.TestCase):
    def test_provider_code_and_routes_are_absent(self):
        sources = list((p for p in BACKEND.rglob('*.cs') if not {'obj', 'bin', 'publish'}.intersection(p.relative_to(BACKEND).parts)))
        forbidden = 'geo' + 'apify'
        self.assertFalse([p.name for p in sources if forbidden in p.name.lower() or forbidden in p.read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.').lower()])
        program = (BACKEND / 'Program.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('AddressLookup.Prepare(ctx,db)', program)
        self.assertIn('AddressLookup.Map(app)', program)

    def test_lookup_has_no_remote_transport_or_provider_state(self):
        lookup = BACKEND / 'Modules/Geography/AddressLookup.cs'
        self.assertTrue(lookup.exists(), 'Local AddressLookup implementation missing')
        source = lookup.read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        for token in ('HttpClient', 'Cryptograph', 'DataProtection', 'Cache', 'SemaphoreSlim', 'ApplyRate', 'apiKey'):
            self.assertNotIn(token, source)
        for token in ('record Query(', 'record Item(', 'record Reply(', 'Task Prepare(', 'Task<IResult> Handle('):
            self.assertIn(token, source)

    def test_country_options_are_only_enabled_database_rows(self):
        source = (BACKEND / 'Modules/Geography/Geography.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        countries = source.split('Task<IResult> Countries(', 1)[1].split('public static ImportRow[]', 1)[0]
        self.assertNotIn('CountryCodes.All', countries)
        self.assertIn('provider="catalog"', countries)
        self.assertIn('foundation.country WHERE is_enabled', countries)


if __name__ == '__main__':
    unittest.main()
