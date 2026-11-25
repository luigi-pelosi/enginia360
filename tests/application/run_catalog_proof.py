"""Accettazione HTTP Catalogo su immagini candidate e PostgreSQL effimero.

Non usa volumi/dati reali e non prova TLS. Nessuna build o migrazione live.
"""
import argparse
import json
import os
import unittest
import urllib.request
from catalog_helpers import configure_fixture, install_transport

fixture = configure_fixture()


def parser(browser=False):
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--backend-image', required=True)
    result.add_argument('--frontend-image', required=browser)
    result.add_argument('--schema', default=str(fixture.ROOT / 'database/foundation.sql'))
    result.add_argument('--migration', action='append', default=[])
    result.add_argument('--keep', action='store_true')
    result.add_argument('--reuse', action='store_true')
    result.add_argument('--cleanup', action='store_true')
    return result


def run(browser=False):
    args = parser(browser).parse_args()
    if args.cleanup:
        fixture.cleanup()
        return 0
    original = None
    try:
        state = json.loads((fixture.EVIDENCE / 'state.json').read_text()) if args.reuse else fixture.start(args)
        if state['scope'] != fixture.SCOPE:
            raise RuntimeError('Stato appartenente a un altro progetto')
        targets = [fixture.DB, fixture.API] + ([fixture.WEB] if browser else [])
        if not all(fixture.verify_target(target) for target in targets):
            raise RuntimeError('Fixture Catalogo incompleta')
        original = install_transport(state)
        os.environ['ENGINIA360_CATALOG_STATE'] = str(fixture.EVIDENCE / 'state.json')
        module = 'browser_catalog_proof' if browser else 'test_catalog_http'
        suite = unittest.defaultTestLoader.loadTestsFromName(module)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures),
                   'errors': len(result.errors), 'skipped': len(result.skipped),
                   'scope': fixture.SCOPE, 'browser': browser}
        (fixture.EVIDENCE / ('browser-result.json' if browser else 'http-result.json')).write_text(json.dumps(summary, indent=2))
        return 0 if result.testsRun > 0 and result.wasSuccessful() and not result.skipped else 1
    finally:
        if original:
            urllib.request.build_opener = original
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (fixture.EVIDENCE / ('browser-api.log' if browser else 'http-api.log')).write_text(log.stdout + log.stderr)
        if not args.keep:
            fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(run())
