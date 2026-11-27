"""Mandatory profile on EVERY registration; parent-owned disposable scope only.

Discovery and Chromium launch smoke provision nothing. Runtime requires explicit
parent authorization/exclusive scope ownership and the final local candidate
images. Never build, touch live resources, or treat smoke as HTTP/UI acceptance.
"""
import os
from pathlib import Path
import run_company_tax_required_proof as required

BACKEND = 'enginia360-backend:company-tax-registration-required-proof'
FRONTEND = 'enginia360-frontend:company-tax-registration-required-proof'
EVIDENCE = Path(os.environ.get('ENGINIA360_COMPANY_TAX_EVIDENCE',
    '/root/.hermes/evidence/company-tax-registration-required-proof'))


def main():
    required.BACKEND, required.FRONTEND, required.EVIDENCE = BACKEND, FRONTEND, EVIDENCE
    return required.main()


if __name__ == '__main__':
    raise SystemExit(main())
