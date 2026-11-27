"""Fase4 finite wrapper. Discovery/smoke never provision containers.

Runtime requires BOTH final images, an explicit scope handoff, and exact labels.
The old Phase3 runner remains immutable; context overrides are restored on exit.
"""
import argparse
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import unittest

import run_company_tax_proof as previous

SCOPE = 'enginia360-company-tax-proof'
BACKEND = 'enginia360-backend:tax-determination-proof'
FRONTEND = 'enginia360-frontend:tax-determination-proof'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.environ.get('ENGINIA360_TAX_DETERMINATION_EVIDENCE', '/root/.hermes/cache/scratch/tax-determination-acceptance'))


def suite(browser=False, tests=None):
    target = 'browser_tax_determination_proof.TaxDeterminationBrowser' if browser else 'test_tax_determination_http.TaxDeterminationHttp'
    names = [target+'.'+name for name in tests] if tests else [target]
    loaded = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    cases = list(previous.flatten(loaded))
    if not cases or any('_FailedTest' in case.id() or not case.id().startswith(target+'.') for case in cases):
        raise RuntimeError('Discovery not exact/disjoint: '+repr([case.id() for case in cases]))
    return unittest.TestSuite(cases)


def source_manifest():
    files = [Path(__file__), Path(__file__).with_name('test_tax_determination_http.py'), Path(__file__).with_name('browser_tax_determination_proof.py'),
             Path(__file__).with_name('tax_helpers.py'), Path(__file__).with_name('run_company_tax_proof.py')]
    files += sorted((ROOT/'backend/Modules/TaxManagement').glob('*.cs'))
    files += [p for p in (ROOT/'database').rglob('*.sql') if p.name in ('foundation.sql','taxmanagement.sql')]
    files += [p for pattern in ('tax-rules.*','tax-simulator.*','tax-determination.*') for p in (ROOT/'frontend').rglob(pattern) if 'node_modules' not in p.parts and '.next' not in p.parts]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}


@contextmanager
def candidate_context():
    attributes = {name: getattr(previous,name) for name in ('BACKEND','FRONTEND','EVIDENCE','suite')}
    env = {key: os.environ.get(key) for key in ('ENGINIA360_COMPANY_TAX_EVIDENCE','ENGINIA360_TAX_DETERMINATION_PROOF')}
    try:
        previous.BACKEND, previous.FRONTEND, previous.EVIDENCE, previous.suite = BACKEND, FRONTEND, EVIDENCE, suite
        os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'] = str(EVIDENCE)
        os.environ['ENGINIA360_TAX_DETERMINATION_PROOF'] = '1'
        yield
    finally:
        for name,value in attributes.items(): setattr(previous,name,value)
        for key,value in env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value


def setup_smoke():
    from tax_helpers import configure_fixture, install_transport, login_root
    from test_company_tax_http import CompanyTaxHttp
    from test_taxclassification_http import TaxClassificationHttp
    from test_tax_determination_http import TaxDeterminationHttp
    methods = {}
    for cls,names in ((CompanyTaxHttp,('setUpClass','setUp','req','payload','create','command','assign_companies')),
                      (TaxClassificationHttp,('subject_payload','subject_endpoint','subject','subject_read','profile')),
                      (TaxDeterminationHttp,('setUpClass','setUp','core','simulate','determine'))):
        for name in names:
            value=inspect.getattr_static(cls,name)
            methods[cls.__name__+'.'+name]={'classmethod':isinstance(value,classmethod),'signature':str(inspect.signature(getattr(cls,name)))}
    assert isinstance(inspect.getattr_static(TaxDeterminationHttp,'setUpClass'),classmethod)
    assert configure_fixture.__defaults__ == ('enginia360-tax-proof',)
    assert len(list(previous.flatten(suite()))) == len(unittest.defaultTestLoader.getTestCaseNames(TaxDeterminationHttp))
    return {'runtimeAcceptance':False,'authHelpers':'signatures checked; no login or credential read',
            'transport':str(inspect.signature(install_transport)), 'login':str(inspect.signature(login_root)), 'methods':methods}


def main():
    args=sys.argv[1:]
    safe=any(flag in args for flag in ('--discover','--headless-smoke','--setup-smoke','--help','-h'))
    if '--setup-smoke' in args:
        EVIDENCE.mkdir(parents=True,exist_ok=True,mode=0o700)
        report=setup_smoke(); (EVIDENCE/'setup-smoke.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2)); return 0
    authorized='--authorize-scope' in args
    if authorized: args.remove('--authorize-scope')
    if not safe and not authorized:
        raise SystemExit('Runtime/cleanup blocked: parent must hand off exclusive scope with --authorize-scope after BOTH final images exist')
    if not safe:
        from tax_helpers import configure_fixture
        fixture=configure_fixture(SCOPE)
        # Preflight BEFORE predecessor start/cleanup. HTTP also requires frontend.
        for image in (BACKEND,FRONTEND): fixture.docker('image','inspect',image)
        if '--frontend-image' not in args: args += ['--frontend-image',FRONTEND]
    EVIDENCE.mkdir(parents=True,exist_ok=True,mode=0o700)
    manifest=source_manifest()
    (EVIDENCE/'source-manifest.json').write_text(json.dumps(manifest,indent=2))
    argv=sys.argv
    try:
        sys.argv=[argv[0],*args]
        with candidate_context(): return previous.main()
    finally:
        sys.argv=argv
        if not safe and source_manifest()!=manifest:
            (EVIDENCE/'SOURCE-CHANGED-NONPASS.json').write_text(json.dumps(source_manifest(),indent=2))
            raise RuntimeError('Source changed during bounded proof; results are not release evidence')


if __name__=='__main__':
    raise SystemExit(main())
