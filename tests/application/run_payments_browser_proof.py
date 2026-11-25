"""Run the BP payment-default Chromium regression against disposable containers.

Requires built frontend/backend images and Playwright Chromium. Logical HTTPS is
routed to loopback HTTP; this does not verify TLS.
"""
import argparse
import unittest
from pathlib import Path
import run_business_partner_proof as fixture

fixture.SCOPE = 'enginia360-payment-default-browser-regression'
fixture.DB = fixture.SCOPE + '-db'
fixture.API = fixture.SCOPE + '-api'
fixture.WEB = fixture.SCOPE + '-web'
fixture.NETWORK = fixture.SCOPE
fixture.INGRESS = fixture.SCOPE + '-ingress'
fixture.EVIDENCE = Path('/root/.hermes/cache/scratch') / fixture.SCOPE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend-image', required=True)
    parser.add_argument('--frontend-image', required=True)
    args = parser.parse_args()
    args.schema = str(fixture.ROOT / 'database/foundation.sql')
    args.migration = []
    try:
        fixture.start(args)
        suite = unittest.defaultTestLoader.loadTestsFromName('browser_payments_defaults.Proof.test_payments')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and not result.skipped else 1
    finally:
        fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
