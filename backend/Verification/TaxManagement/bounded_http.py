"""Real-cookie TaxManagement gap proof on its own ephemeral Docker scope."""
import argparse
import json
from pathlib import Path
import sys
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests' / 'application'))
import tax_helpers

tax_helpers.SCOPE = 'enginia360-tax-bounded-http'
fixture = tax_helpers.configure_fixture()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', required=True)
    args = parser.parse_args()
    args.frontend_image = None
    args.schema = str(ROOT / 'database' / 'foundation.sql')
    args.migration = []
    original = None
    try:
        state = fixture.start(args)
        original = tax_helpers.install_transport(state)
        from test_tax_http import TaxHttp

        class BoundedHttp(TaxHttp):
            def test_bounded_lookups_or_permissions(self):
                expected = self.req('lookups')
                self.assertEqual(set(expected), {'countries', 'types', 'natureCodes'})
                self.assertEqual(len(expected['types']), 5)
                self.assertEqual(len(expected['natureCodes']), 21)
                self.assertIn(self.country_id, {c['id'] for c in expected['countries']})
                self.assertTrue(all('is_enabled' in c for c in expected['countries']))
                for grant in ['read', 'create', 'update', 'schedule']:
                    with self.subTest(grant=grant):
                        actor, _, _ = self.actor(['tax-codes.' + grant])
                        status, actual = actor.request(self.path('lookups'))
                        self.assertEqual(status, 200, actual)
                        self.assertEqual(actual, expected)
                        for route in ['types', 'nature-codes']:
                            self.assertEqual(actor.request(self.path(route))[0], 403)
                actor, _, _ = self.actor(['tax-types.read'])
                self.assertEqual(actor.request(self.path('lookups'))[0], 403)

            def test_bounded_metadata_and_schedule_audit(self):
                row = self.create()
                changed = self.update(row, {'name': 'Nome stabile'})
                event = self.req('codes/' + row['id'] + '/audit')['items'][0]['details']
                self.assertEqual(event, {'before': {'version': 1, 'name': row['name']},
                                         'after': {'version': 2, 'name': 'Nome stabile'}})
                scheduled = self.schedule(changed)
                event = self.req('codes/' + row['id'] + '/audit')['items'][0]['details']
                self.assertEqual(set(event), {'before', 'after'})
                self.assertEqual(event['before'], {'version': 2, 'predecessor': {'id': row['versions'][0]['id'], 'valid_to': None}})
                self.assertEqual(event['after']['version'], 3)
                self.assertEqual(event['after']['predecessor'], {'id': row['versions'][0]['id'], 'valid_to': '2026-12-31'})
                self.assertEqual(event['after']['fiscalVersion']['rate'], '23.000000')
                self.assertEqual(event['after']['fiscalVersion']['id'], scheduled['versions'][1]['id'])
                self.assertNotIn('versions', event['after'])
                self.assertNotIn('name', event['after'])

            def test_bounded_template_country_scope_and_stable_identifier(self):
                self.sql("INSERT INTO foundation.country(name,iso_code) VALUES('United States','US') ON CONFLICT DO NOTHING")
                country = self.sql("SELECT id FROM foundation.country WHERE iso_code='US'")
                payload = self.payload()
                payload['values'].update(code='VAT_STANDARD', country_id=country)
                foreign = self.req('codes', 'POST', payload, 201)
                result = self.req('codes/templates/install', 'POST', {'validFrom': '2026-01-01'})
                self.assertEqual(result['installed'], 14)
                self.assertIn('VAT_STANDARD', {row['code'] for row in result['items']})
                standard = next(row for row in result['items'] if row['code'] == 'VAT_STANDARD')
                self.assertEqual(standard['name'], 'IVA ordinaria')
                self.assertEqual(standard['country_id'], self.country_id)
                self.assertNotIn('VAT_STANDARD22', {row['code'] for row in result['items']})
                self.assertEqual(self.req('codes/' + foreign['id']), foreign)
                repeated = self.req('codes/templates/install', 'POST', {'validFrom': '2028-01-01'})
                self.assertEqual((repeated['installed'], repeated['skipped']), (0, 14))
                self.assertEqual(self.req('codes/' + standard['id']), standard)

            def test_bounded_z_overflow_refuses_incomplete_lookup(self):
                self.sql("INSERT INTO taxmanagement.tax_nature_codes(country_id,scheme,code,description,valid_from) "
                         f"SELECT '{self.country_id}'::uuid,'PROOF','BOUND_'||n,'Synthetic bounded proof','2021-01-01'::date FROM generate_series(1,10001) n")
                body = self.req('lookups', expected=409)
                self.assertEqual(body['code'], 'tax_lookup_limit_exceeded')

        names = sorted(name for name in dir(BoundedHttp) if name.startswith('test_bounded_'))
        suite = unittest.TestSuite(BoundedHttp(name) for name in names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped)}
        (fixture.EVIDENCE / 'result.json').write_text(json.dumps(summary, indent=2))
        return 0 if result.testsRun == 4 and result.wasSuccessful() and not result.skipped else 1
    finally:
        if original:
            urllib.request.build_opener = original
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (fixture.EVIDENCE / 'api.log').write_text(log.stdout + log.stderr)
        fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
