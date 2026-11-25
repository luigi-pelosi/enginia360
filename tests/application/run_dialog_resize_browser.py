"""Run resize regressions against an isolated authenticated application."""
import argparse
import unittest
from pathlib import Path
import run_business_partner_proof as fixture

fixture.SCOPE = 'enginia360-dialog-resize-browser'
fixture.DB = fixture.SCOPE + '-db'
fixture.API = fixture.SCOPE + '-api'
fixture.WEB = fixture.SCOPE + '-web'
fixture.NETWORK = fixture.SCOPE
fixture.INGRESS = fixture.SCOPE + '-ingress'
fixture.EVIDENCE = Path('/root/.hermes/cache/scratch') / fixture.SCOPE

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend-image', required=True)
    parser.add_argument('--frontend-image', required=True)
    args=parser.parse_args()
    args.schema=str(fixture.ROOT / 'database/foundation.sql'); args.migration=[]
    try:
        fixture.start(args)
        names=('test_organization_flex_desktop_mobile','test_grid_scroll_desktop','test_grid_scroll_touch')
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName('browser_dialog_resize.DialogResize.'+n) for n in names)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() and not result.skipped else 1
    finally:
        fixture.cleanup()

if __name__=='__main__':
    raise SystemExit(main())
