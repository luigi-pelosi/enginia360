"""Company/Site identity acceptance. No builds; exact candidate images only.

Reuses the explicitly authorized, finite company-tax-proof disposable scope.
Never run concurrently with another owner of that scope. HTTP loopback transport
uses logical HTTPS cookies and is not a TLS deployment proof.
"""
import os
from pathlib import Path
import unittest
import run_company_tax_proof as runner


def suite(browser=False, tests=None):
    target = 'browser_company_identity.CompanyIdentityBrowser' if browser else 'test_company_identity_http.CompanyIdentityHttp'
    return unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(target + '.' + name) for name in tests) if tests else unittest.defaultTestLoader.loadTestsFromName(target)


if __name__ == '__main__':
    runner.BACKEND = 'enginia360-backend:company-identity-proof'
    runner.FRONTEND = 'enginia360-frontend:company-identity-proof'
    runner.EVIDENCE = Path(os.environ.get('ENGINIA360_COMPANY_IDENTITY_EVIDENCE', '/root/.hermes/evidence/company-identity-proof'))
    runner.suite = suite
    raise SystemExit(runner.main())
