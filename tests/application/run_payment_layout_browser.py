"""Isolated payment layout/window browser acceptance; HTTPS is loopback-routed, not TLS."""
import argparse
import unittest
from pathlib import Path
import run_business_partner_proof as fixture

fixture.SCOPE = 'enginia360-payment-layout-browser'
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
        names = ('test_installments_compact_table', 'test_select_label_spacing', 'test_payment_switch_persistence', 'test_list_geometry_methods_and_terms', 'test_method_window', 'test_term_window', 'test_shared_window', 'test_mobile_window_bounds', 'test_overflow_grip_and_touch')
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('browser_payment_layout.PaymentLayout.' + name) for name in names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and not result.skipped else 1
    finally:
        fixture.cleanup()

if __name__ == '__main__':
    raise SystemExit(main())
