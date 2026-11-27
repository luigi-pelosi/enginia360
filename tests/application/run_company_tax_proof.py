"""Bounded Phase 3 proof. Never build, use live resources, or count skips as proof.

Run --discover and --headless-smoke without provisioning. Runtime uses only the
parent's exact candidate tags and the allowlisted disposable fixture scope.
Logical HTTPS cookies over loopback HTTP do NOT constitute a TLS proof.
"""
import argparse
import json
import os
from pathlib import Path
import unittest
import urllib.request

SCOPE = 'enginia360-company-tax-proof'
BACKEND = 'enginia360-backend:company-tax-proof'
FRONTEND = 'enginia360-frontend:company-tax-proof'
EVIDENCE = Path(os.environ.get('ENGINIA360_COMPANY_TAX_EVIDENCE', '/root/.hermes/evidence/company-tax-proof'))


def suite(browser=False, tests=None):
    module = 'browser_company_tax_proof.CompanyTaxBrowser' if browser else 'test_company_tax_http.CompanyTaxHttp'
    names = [module + '.' + name for name in tests] if tests else [module]
    return unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)


def flatten(tests):
    for test in tests:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-image', default=BACKEND, choices=[BACKEND])
    parser.add_argument('--frontend-image', choices=[FRONTEND])
    parser.add_argument('--schema', default=str(Path(__file__).resolve().parents[2] / 'database/foundation.sql'))
    parser.add_argument('--migration', action='append', default=[])
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--test', action='append')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--keep', action='store_true')
    parser.add_argument('--cleanup', action='store_true')
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--headless-smoke', action='store_true')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVIDENCE.chmod(0o700)
    if args.discover:
        ids = [test.id() for test in flatten(suite(args.browser, args.test))]
        if not ids or any('_FailedTest' in name for name in ids):
            raise RuntimeError('Acceptance discovery failed: ' + repr(ids))
        print(json.dumps({'discovered': len(ids), 'tests': ids}, indent=2))
        (EVIDENCE / ('browser-discovery.json' if args.browser else 'http-discovery.json')).write_text(json.dumps(ids, indent=2))
        return 0
    if args.headless_smoke:
        from playwright.sync_api import sync_playwright
        chrome = os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome')
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chrome, headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            page.set_content('<title>Phase3 launch smoke</title><h1>Chromium launched</h1>')
            assert page.title() == 'Phase3 launch smoke'
            page.screenshot(path=str(EVIDENCE / 'headless-launch.png'))
            summary = {'launched': True, 'version': browser.version, 'executable': chrome, 'runtimeAcceptance': False}
            browser.close()
        (EVIDENCE / 'headless-launch.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary))
        return 0
    from tax_helpers import configure_fixture, install_transport
    fixture = configure_fixture(SCOPE)  # Parent owns the shared helper allowlist.
    fixture.EVIDENCE = EVIDENCE
    os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'] = str(EVIDENCE)
    if args.cleanup:
        fixture.cleanup()
        return 0
    if args.browser and not args.frontend_image:
        parser.error('--browser requires --frontend-image ' + FRONTEND)
    # Check all required local images before creating/removing any resource.
    for image in (args.backend_image, args.frontend_image, 'postgres:18.6-alpine3.24'):
        if image:
            fixture.docker('image', 'inspect', image)
    original = None
    try:
        state = json.loads((EVIDENCE / 'state.json').read_text()) if args.reuse else fixture.start(args)
        targets = [fixture.DB, fixture.API] + ([fixture.WEB] if args.browser else [])
        if state['scope'] != SCOPE or state['origin'] != fixture.ORIGIN or not all(fixture.verify_target(name) for name in targets):
            raise RuntimeError('Missing or incorrectly scoped CompanyTax fixture')
        image_ids = {}
        for name, image in ((fixture.API, args.backend_image), (fixture.WEB, args.frontend_image)):
            if image:
                actual = json.loads(fixture.docker('inspect', name).stdout)[0]['Image']
                expected = fixture.docker('image', 'inspect', image, '--format', '{{.Id}}').stdout.strip()
                if actual != expected:
                    raise RuntimeError('Candidate image mismatch: ' + name)
                image_ids[name] = actual
        original = install_transport(state)
        os.environ['ENGINIA360_COMPANY_TAX_PROOF'] = '1'
        os.environ['ENGINIA360_TAX_STATE'] = str(EVIDENCE / 'state.json')
        result = unittest.TextTestRunner(verbosity=2).run(suite(args.browser, args.test))
        summary = {'testsRun': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                   'skipped': len(result.skipped), 'browser': args.browser, 'images': image_ids,
                   'failedTests': [str(test) for test, _ in result.failures + result.errors]}
        target = EVIDENCE / ('browser-result.json' if args.browser else 'http-result.json')
        target.write_text(json.dumps(summary, indent=2))
        print('Evidence:', target)
        return 0 if result.testsRun and result.wasSuccessful() and not result.skipped else 1
    finally:
        if original:
            urllib.request.build_opener = original
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (EVIDENCE / 'api.log').write_text(log.stdout + log.stderr)
        if not args.keep:
            fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
