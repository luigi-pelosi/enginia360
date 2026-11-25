"""Run disposable draft regression using supplied candidate images; not TLS proof."""
import argparse
import unittest
from pathlib import Path
import run_business_partner_proof as fixture

fixture.SCOPE='enginia360-draft-browser-regression'
fixture.DB=fixture.SCOPE+'-db'
fixture.API=fixture.SCOPE+'-api'
fixture.WEB=fixture.SCOPE+'-web'
fixture.NETWORK=fixture.SCOPE
fixture.INGRESS=fixture.SCOPE+'-ingress'
fixture.EVIDENCE=Path('/root/.hermes/cache/scratch')/fixture.SCOPE

def main():
    p=argparse.ArgumentParser(); p.add_argument('--backend-image',required=True); p.add_argument('--frontend-image',required=True)
    args=p.parse_args(); args.schema=str(fixture.ROOT/'database/foundation.sql'); args.migration=[]
    try:
        fixture.start(args)
        suite=unittest.defaultTestLoader.loadTestsFromNames(['browser_draft_regression.DraftProof.test_currency_create_edit_conflict_and_pending','browser_draft_regression.DraftProof.test_payment_create_edit_refresh_and_menu_reset','browser_draft_regression.DraftProof.test_payments_effective_tenant_refresh'])
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and not result.skipped else 1
    finally: fixture.cleanup()

if __name__=='__main__': raise SystemExit(main())
