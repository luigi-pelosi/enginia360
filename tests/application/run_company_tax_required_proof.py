"""Finite required-chain/CF acceptance; never build or touch live resources.

Owns only the existing allowlisted enginia360-company-tax-proof scope. Parent
must hand off that scope exclusively. --discover / --headless-smoke provision
nothing. Run HTTP with --frontend-image and --keep, then browser --reuse --keep.
"""
import os
from pathlib import Path
import unittest
import run_company_tax_proof as runner

BACKEND = 'enginia360-backend:company-tax-required-proof'
FRONTEND = 'enginia360-frontend:company-tax-required-proof'
EVIDENCE = Path(os.environ.get('ENGINIA360_COMPANY_TAX_EVIDENCE', '/root/.hermes/evidence/company-tax-required-proof'))


def suite(browser=False, tests=None):
    module = 'browser_company_tax_required.CompanyTaxRequiredBrowser' if browser else 'test_company_tax_required_http.CompanyTaxRequiredHttp'
    names = [module + '.' + name for name in tests] if tests else [module]
    return unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)


def main():
    runner.BACKEND, runner.FRONTEND, runner.EVIDENCE = BACKEND, FRONTEND, EVIDENCE
    runner.suite = suite
    return runner.main()


if __name__ == '__main__':
    raise SystemExit(main())
