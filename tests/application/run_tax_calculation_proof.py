"""Wrapper F5 finito: discovery/setup inerti, runtime soltanto dopo handoff.

Nessun build e nessuna pulizia implicita prima dell'autorizzazione dello scope.
Le costanti del runner storico sono sostituite solo nel contesto e poi ripristinate.
"""
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
BACKEND = 'enginia360-backend:tax-calculation-proof'
FRONTEND = 'enginia360-frontend:tax-calculation-proof'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.environ.get('ENGINIA360_TAX_CALCULATION_EVIDENCE',
    '/root/.config/enginia360/releases/taxcalculation-20261127/acceptance-preflight'))
TARGETS = {
    False: 'test_tax_calculation_http.TaxCalculationHttp',
    True: 'browser_tax_calculation_proof.TaxCalculationBrowser',
}


def suite(browser=False, tests=None):
    target = TARGETS[bool(browser)]
    names = [target + '.' + name for name in tests] if tests else [target]
    loaded = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    cases = list(previous.flatten(loaded))
    if not cases or any('_FailedTest' in case.id() or not case.id().startswith(target + '.') for case in cases):
        raise RuntimeError('Discovery non esatta/disgiunta: ' + repr([case.id() for case in cases]))
    return unittest.TestSuite(cases)


def source_manifest():
    files = [Path(__file__), ROOT / 'backend/Program.cs']
    files += [ROOT / 'tests/application' / name for name in (
        'test_tax_calculation_http.py', 'browser_tax_calculation_proof.py',
        'test_tax_determination_http.py', 'browser_tax_determination_proof.py',
        'test_company_tax_http.py', 'test_taxclassification_http.py', 'test_tax_http.py',
        'browser_company_tax_proof.py', 'browser_taxclassification_proof.py',
        'browser_tax_proof.py', 'test_api.py', 'tax_helpers.py', 'run_company_tax_proof.py')]
    files += sorted((ROOT / 'backend/Modules/TaxManagement').glob('*.cs'))
    files += [p for p in (ROOT / 'database').rglob('*.sql') if 'tax' in p.name or p.name == 'foundation.sql']
    for directory in ('frontend/components', 'frontend/lib', 'frontend/messages'):
        files += [p for p in (ROOT / directory).rglob('*') if p.is_file()
                  and (p.name.startswith('tax-') or p.suffix == '.json')]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(files))}


@contextmanager
def candidate_context():
    if previous.SCOPE != SCOPE:
        raise RuntimeError('Lo scope storico non coincide con quello autorizzabile F5')
    names = ('BACKEND', 'FRONTEND', 'EVIDENCE', 'suite')
    attributes = {name: getattr(previous, name) for name in names}
    keys = ('ENGINIA360_COMPANY_TAX_EVIDENCE', 'ENGINIA360_TAX_CALCULATION_PROOF',
            'ENGINIA360_TAX_DETERMINATION_PROOF', 'ENGINIA360_COMPANY_TAX_PROOF', 'ENGINIA360_TAX_STATE')
    environment = {key: os.environ.get(key) for key in keys}
    try:
        previous.BACKEND = BACKEND
        previous.FRONTEND = FRONTEND
        previous.EVIDENCE = EVIDENCE
        previous.suite = suite
        os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'] = str(EVIDENCE)
        os.environ['ENGINIA360_TAX_CALCULATION_PROOF'] = '1'
        os.environ['ENGINIA360_TAX_DETERMINATION_PROOF'] = '1'
        yield
    finally:
        for name, value in attributes.items():
            setattr(previous, name, value)
        for key, value in environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def setup_smoke():
    from tax_helpers import configure_fixture, install_transport, login_root
    from test_tax_determination_http import TaxDeterminationHttp
    from test_tax_calculation_http import TaxCalculationHttp, REFERENCE_CASES
    from browser_tax_calculation_proof import TaxCalculationBrowser, STATIC_UI_IDS, DYNAMIC_UI_PREFIXES
    methods = {}
    for cls, names in (
        (TaxDeterminationHttp, ('setUpClass', 'setUp', 'core', 'new_rule', 'transition', 'fingerprint')),
        (TaxCalculationHttp, ('setUpClass', 'setUp', 'line', 'document', 'calculate', 'raw_post')),
        (TaxCalculationBrowser, ('setUpClass', 'setUp', 'fill_context', 'fill_facts', 'append_scenario')),
    ):
        for name in names:
            value = inspect.getattr_static(cls, name)
            methods[cls.__name__ + '.' + name] = {
                'classmethod': isinstance(value, classmethod),
                'signature': str(inspect.signature(getattr(cls, name))),
            }
    assert isinstance(inspect.getattr_static(TaxCalculationHttp, 'setUpClass'), classmethod)
    assert isinstance(inspect.getattr_static(TaxCalculationBrowser, 'setUpClass'), classmethod)
    assert TaxCalculationHttp.__bases__ == (unittest.TestCase,)
    assert TaxCalculationBrowser.__bases__ == (unittest.TestCase,)
    inventory = {}
    for browser, cls in ((False, TaxCalculationHttp), (True, TaxCalculationBrowser)):
        target = TARGETS[browser]
        module = __import__(target.rsplit('.', 1)[0])
        module_ids = [x.id() for x in previous.flatten(unittest.defaultTestLoader.loadTestsFromModule(module))]
        class_ids = [x.id() for x in previous.flatten(unittest.defaultTestLoader.loadTestsFromTestCase(cls))]
        wrapper_ids = [x.id() for x in previous.flatten(suite(browser))]
        assert module_ids == class_ids == wrapper_ids
        assert len(wrapper_ids) == len(set(wrapper_ids))
        inventory['browser' if browser else 'http'] = wrapper_ids
    assert not set(inventory['http']) & set(inventory['browser'])
    assert len(REFERENCE_CASES) == len(set(REFERENCE_CASES)) == 13
    ui_paths = (ROOT / 'frontend/components/tax-simulator.tsx',
                ROOT / 'frontend/components/tax-calculation-panel.tsx')
    ui = '\n'.join(path.read_text() for path in ui_paths)
    for identifier in STATIC_UI_IDS:
        if identifier == 'tax-calc-document-add':
            # ID composto realmente dal prefisso del documento e dal suffisso add.
            assert "'tax-calc-document'" in ui and "prefix + '-add'" in ui
        else:
            assert identifier in ui, 'Selettore UI assente: ' + identifier
    for prefix in DYNAMIC_UI_PREFIXES:
        if prefix.startswith('tax-calc-document-'):
            suffix = prefix.removeprefix('tax-calc-document')
            assert "prefix + '" + suffix + "'" in ui
        else:
            assert prefix in ui, 'Prefisso UI assente: ' + prefix
    before = {name: getattr(previous, name) for name in ('BACKEND', 'FRONTEND', 'EVIDENCE', 'suite')}
    env_before = dict(os.environ)
    with candidate_context():
        assert previous.BACKEND == BACKEND and previous.FRONTEND == FRONTEND
        assert previous.suite is suite
    assert before == {name: getattr(previous, name) for name in before}
    assert env_before == dict(os.environ)
    return {'runtimeAcceptance': False, 'fixtureProvisioned': False,
            'counts': {key: len(ids) for key, ids in inventory.items()},
            'inventory': inventory, 'references': REFERENCE_CASES,
            'authHelpers': 'Solo firme; nessun login né lettura credenziali',
            'fixture': str(inspect.signature(configure_fixture)),
            'transport': str(inspect.signature(install_transport)),
            'login': str(inspect.signature(login_root)), 'methods': methods,
            'contextRestoreVerified': True,
            'uiSelectorContracts': {'static': STATIC_UI_IDS, 'dynamicPrefixes': DYNAMIC_UI_PREFIXES},
            'uiSourceHashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in ui_paths}}


def main():
    args = list(sys.argv[1:])
    inert = any(flag in args for flag in ('--discover', '--headless-smoke', '--setup-smoke', '--help', '-h'))
    authorized = '--authorize-scope' in args
    if authorized:
        args.remove('--authorize-scope')
    if not inert and not authorized:
        raise SystemExit('Runtime/cleanup vietati: handoff parent e --authorize-scope obbligatori dopo ENTRAMBI i tag F5')
    if '--setup-smoke' in args:
        if set(args) != {'--setup-smoke'}:
            raise SystemExit('--setup-smoke è isolato e non accetta opzioni runtime')
        EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
        report = setup_smoke()
        (EVIDENCE / 'setup-smoke.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 0
    if not inert:
        from tax_helpers import configure_fixture
        fixture = configure_fixture(SCOPE)
        # Prima di start, reuse O cleanup: entrambi i tag devono essere presenti.
        for image in (BACKEND, FRONTEND):
            fixture.docker('image', 'inspect', image)
        if '--frontend-image' not in args:
            args += ['--frontend-image', FRONTEND]
    EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    EVIDENCE.chmod(0o700)
    manifest = source_manifest()
    manifest_name = 'preflight-source-manifest.json' if inert else 'runtime-source-manifest.json'
    (EVIDENCE / manifest_name).write_text(json.dumps(manifest, indent=2))
    argv = sys.argv
    try:
        sys.argv = [argv[0], *args]
        with candidate_context():
            return previous.main()
    finally:
        sys.argv = argv
        if not inert and source_manifest() != manifest:
            (EVIDENCE / 'SOURCE-CHANGED-NONPASS.json').write_text(json.dumps(source_manifest(), indent=2))
            raise RuntimeError('Sorgenti cambiate durante runtime: campagna non valida per rilascio')


if __name__ == '__main__':
    raise SystemExit(main())
