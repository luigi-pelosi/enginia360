"""Bounded Phase 2 acceptance against labelled, disposable candidate containers.

Never builds images, touches live resources, or treats skipped tests as acceptance.
Logical HTTPS cookies traverse loopback HTTP; this is not a TLS proof.
"""
import argparse
import json
import os
import unittest
import urllib.request
from tax_helpers import configure_fixture, install_transport

fixture = configure_fixture('enginia360-taxclassification-proof')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', required=True)
    parser.add_argument('--frontend-image')
    parser.add_argument('--schema', default=str(fixture.ROOT / 'database/foundation.sql'))
    parser.add_argument('--migration', action='append', default=[])
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--test', action='append', help='Exact unittest method, repeatable')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    args = parser.parse_args()
    if args.cleanup:
        fixture.cleanup()
        return 0
    if args.browser and not args.frontend_image:
        parser.error('--browser requires --frontend-image')
    # Fail before provisioning if a candidate is absent. Parent owns builds.
    for image in (args.backend_image, args.frontend_image):
        if image:
            fixture.docker('image', 'inspect', image)
    original = None
    try:
        state = json.loads((fixture.EVIDENCE / 'state.json').read_text()) if args.reuse else fixture.start(args)
        targets = [fixture.DB, fixture.API] + ([fixture.WEB] if args.browser else [])
        if state['scope'] != fixture.SCOPE or not all(fixture.verify_target(name) for name in targets):
            raise RuntimeError('Incomplete or incorrectly scoped TaxClassification fixture')
        image_ids = {}
        for name, image in ((fixture.API, args.backend_image), (fixture.WEB, args.frontend_image)):
            if image:
                actual = json.loads(fixture.docker('inspect', name).stdout)[0]['Image']
                expected = fixture.docker('image', 'inspect', image, '--format', '{{.Id}}').stdout.strip()
                if actual != expected:
                    raise RuntimeError('Candidate image mismatch: ' + name)
                image_ids[name] = actual
        original = install_transport(state)
        os.environ['ENGINIA360_TAXCLASSIFICATION_PROOF'] = '1'
        os.environ['ENGINIA360_TAX_STATE'] = str(fixture.EVIDENCE / 'state.json')
        module = 'browser_taxclassification_proof.TaxClassificationBrowser' if args.browser else 'test_taxclassification_http.TaxClassificationHttp'
        names = [module + '.' + method for method in args.test] if args.test else [module]
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                   'skipped': len(result.skipped), 'browser': args.browser, 'images': image_ids,
                   'failedTests': [str(test) for test, _ in result.failures + result.errors]}
        target = fixture.EVIDENCE / ('browser-result.json' if args.browser else 'http-result.json')
        target.write_text(json.dumps(summary, indent=2))
        print('Evidence:', target)
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
