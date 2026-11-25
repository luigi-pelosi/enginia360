"""Accettazione Catalogo con Chromium reale, limitata alla fixture di prova."""
import json
import os
import unittest
import urllib.request

from run_catalog_proof import fixture, parser, install_transport

CASES = (
    'test_italiano_navigation_editors_refresh_conflict_reset',
    'test_english_navigation_editors_refresh_conflict_reset',
    'test_ordinary_child_only_navigation',
    'test_units_only_system_navigation',
)


def run():
    args = parser(browser=True).parse_args()
    if args.cleanup:
        fixture.cleanup()
        return 0
    original = None
    try:
        state = json.loads((fixture.EVIDENCE / 'state.json').read_text()) if args.reuse else fixture.start(args)
        if state['scope'] != fixture.SCOPE or not all(fixture.verify_target(n) for n in (fixture.DB, fixture.API, fixture.WEB)):
            raise RuntimeError('Catalog browser fixture absent or outside owned scope')
        original = install_transport(state)
        os.environ['ENGINIA360_CATALOG_STATE'] = str(fixture.EVIDENCE / 'state.json')
        from browser_catalog_proof import CatalogBrowserProof
        # Casi finiti espliciti: nessuna discovery dei test HTTP ereditati.
        suite = unittest.TestSuite(CatalogBrowserProof(name) for name in CASES)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures),
                   'errors': len(result.errors), 'skipped': len(result.skipped),
                   'scope': fixture.SCOPE, 'browser': True, 'cases': list(CASES)}
        (fixture.EVIDENCE / 'browser-result.json').write_text(json.dumps(summary, indent=2))
        return 0 if result.testsRun == len(CASES) and result.wasSuccessful() and not result.skipped else 1
    finally:
        if original:
            urllib.request.build_opener = original
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (fixture.EVIDENCE / 'browser-api.log').write_text(log.stdout + log.stderr)
        if not args.keep:
            fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(run())
