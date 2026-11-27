"""Accettazione TaxManagement con cookie/CSRF e ruolo runtime su fixture effimera.

Non usa volumi o credenziali reali. HTTPS logico su HTTP loopback, non prova TLS.
"""
import argparse
import json
import os
import unittest
import urllib.request
from tax_helpers import configure_fixture, install_transport

fixture = configure_fixture()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', required=True)
    parser.add_argument('--frontend-image')
    parser.add_argument('--schema', default=str(fixture.ROOT / 'database/foundation.sql'))
    parser.add_argument('--migration', action='append', default=[])
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if args.cleanup:
        fixture.cleanup()
        return 0
    original = None
    try:
        if args.browser and not args.frontend_image:
            parser.error('--browser richiede --frontend-image')
        state = json.loads((fixture.EVIDENCE / 'state.json').read_text()) if args.reuse else fixture.start(args)
        targets = [fixture.DB, fixture.API] + ([fixture.WEB] if args.browser else [])
        if state['scope'] != fixture.SCOPE or not all(fixture.verify_target(name) for name in targets):
            raise RuntimeError('Fixture TaxManagement incompleta o fuori scope')
        for name, image in ((fixture.API, args.backend_image), (fixture.WEB, args.frontend_image)):
            if image:
                actual = json.loads(fixture.docker('inspect', name).stdout)[0]['Image']
                expected = fixture.docker('image', 'inspect', image, '--format', '{{.Id}}').stdout.strip()
                if actual != expected:
                    raise RuntimeError('Immagine candidata non corrispondente: ' + name)
        original = install_transport(state)
        os.environ['ENGINIA360_TAX_STATE'] = str(fixture.EVIDENCE / 'state.json')
        module = 'browser_tax_proof.TaxBrowser' if args.browser else 'test_tax_http.TaxHttp'
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(module))
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures),
                   'errors': len(result.errors), 'skipped': len(result.skipped), 'browser': args.browser}
        (fixture.EVIDENCE / ('browser-result.json' if args.browser else 'http-result.json')).write_text(json.dumps(summary, indent=2))
        return 0 if result.testsRun and result.wasSuccessful() and not result.skipped else 1
    finally:
        if original:
            urllib.request.build_opener = original
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (fixture.EVIDENCE / 'api.log').write_text(log.stdout + log.stderr)
        if not args.keep:
            fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
