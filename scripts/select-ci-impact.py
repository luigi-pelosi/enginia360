#!/usr/bin/env python3
"""Finite R00.b/UI change-impact contract. Unknown executable paths require an explicit mapping, never a blanket run."""
import argparse
import json
from pathlib import PurePosixPath
import re
import subprocess
import sys

AUTH_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'BrowserSessionTests','BoundedTicketStoreTests','BrowserAuthenticationBoundaryTests',
    'ExternalIdentityAuthenticationTests','AuthorizedContextContractTests','LimitedGrantAdministrationTests',
    'MasterAuthorityEnforcementTests','BootstrapTests'))
AUTH_FILES = {
    'src/Enginia360.Api/Program.cs','src/Enginia360.Api/Enginia360.Api.csproj',
    'src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json',
    'src/Enginia360.Api/Dockerfile','compose.r00b-test.yaml','compose.r00a-test.yaml',
    'browser.runtime.Dockerfile','keycloak.runtime.Dockerfile','postgres.runtime.Dockerfile',
    'migrator.runtime.Dockerfile','runtime-pool-test.Dockerfile',
    'scripts/apply-runtime-migrations.py','scripts/validate-runtime-config.py',
    'scripts/select-ci-impact.py','scripts/test-ci-impact.py','.github/workflows/ci.yml',
    'scripts/test-productization-consistency.py','scripts/owner-operative-mandate.py','scripts/test-r01b-grants.py',
    'scripts/test-r02b-authority.py','scripts/owner-master-authority.py',
    'web/nginx.r00b-test.conf','web/runtime-access.html','web/runtime-access.js',
}
AUTH_TESTS = {'BrowserSessionTests','BoundedTicketStoreTests','BrowserAuthenticationBoundaryTests',
              'ExternalIdentityAuthenticationTests','AuthorizedContextContractTests','LimitedGrantAdministrationTests',
              'MasterAuthorityEnforcementTests','BootstrapTests','RuntimeMigrationPoolTests'}
UI01B_FILES = {'scripts/owner-master-authority.py','scripts/test-r02b-authority.py',
    'database/runtime/migrations/0017_master_authority_profile.sql',
    'src/Enginia360.Api/OrganizationAccess/CounterpartyAccessAdapter.cs','web/ui01-runtime.html','web/vite.ui01-runtime.config.ts','web/nginx.ui01b-test.conf',
    'src/Modules/Vehicles/Enginia360.Vehicles/VehiclesModule.cs',
    'src/Modules/Vehicles/Enginia360.Vehicles.Contracts/Contracts.cs',
    'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs',
    'src/Modules/Catalog/Enginia360.Catalog.Contracts/Contracts.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/CommonEndpoints.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties.Contracts/Contracts.cs',
    'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs',
    'compose.ui01b-test.yaml','scripts/run-ui01b-tests.py','scripts/test-ui01b-wiring.py','scripts/test-ui01b-impact.py','scripts/test-ui01b-fixture.py',
    'tests/browser/ui01b-acceptance.cjs','web/package.json','web/package-lock.json',
    'scripts/select-ci-impact.py','scripts/test-ci-impact.py','.github/workflows/ci.yml','browser.runtime.Dockerfile'}
R03A_FILES = {'database/runtime/migrations/0020_material_structure_fence.sql','scripts/run-r03a2-tests.py','scripts/test-r03a2-impact.py','scripts/test-r03a2-lifecycle.py','tests/browser/r03a2-acceptance.cjs','compose.r03a2-test.yaml','database/runtime/migrations/0018_workshop_order_workspace.sql','scripts/run-r03a-tests.py',
    'scripts/test-r03a-impact.py','scripts/test-r03a-contract.py','scripts/test-r03a-migration.py','tests/browser/r03a-acceptance.cjs',
    'compose.r03a-test.yaml','tests/Enginia360.Api.Tests/WorkshopEditorTests.cs','web/nginx.r03a-test.conf'}
R03A_PREFIXES = ('src/Modules/Workshop/','src/Modules/Inventory/')
R03A_WEB = ('web/src/ui01/runtime/OrderWorkspace','web/src/ui01/runtime/OrderList','web/src/ui01/runtime/editor')
R04A_WEB = ('web/src/ui01/runtime/Material','web/src/ui01/runtime/material')
R04A_FILES = {'scripts/test-r04a-impact.py','scripts/run-r04a-tests.py','scripts/test-r04a-stock-profile.py',
    'web/src/ui01/runtime/WorkshopRuntime.tsx','src/Enginia360.Api/OrganizationAccess/InventoryAccessAdapter.cs','database/runtime/manifest.json',
    'scripts/owner-stock-profile.py','scripts/test-r04a-lifecycle.py','tests/browser/r04a-acceptance.cjs','compose.r04a-test.yaml',
    'database/runtime/migrations/0021_company_stock_profile.sql'}
R03A_EXCLUDED = {'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs'}
WORKSHOP_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'WorkshopBoundaryTests','CommercialCalculationTests','CounterpartyArchitectureTests'))

R03A_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'WorkshopBoundaryTests','CommercialCalculationTests','CounterpartyArchitectureTests','WorkshopEditorTests','InstallationBoundaryTests','CarcassBoundaryTests',
    'InventoryArchitectureTests','AdministrationBoundaryTests','BillingBoundaryTests','AccountingBoundaryTests'))


def selection(paths):
    paths = sorted(set(paths))
    auth = ui = ui01b = r03a = r04a = False
    unknown = []
    for path in paths:
        parsed = PurePosixPath(path)
        if not path or parsed.is_absolute() or '..' in parsed.parts or '\\' in path or str(parsed) != path:
            raise ValueError('invalid changed path')
        if path in R04A_FILES or path.startswith(R04A_WEB) or (path.startswith(R03A_PREFIXES) and path not in R03A_EXCLUDED):
            r04a = True
            r03a = ui01b = ui = True
        if path in R04A_FILES:
            r03a = ui01b = ui = True
            if path.startswith(('database/runtime/','src/Enginia360.Api/OrganizationAccess/')):
                auth = True
            continue
        if path.startswith(R04A_WEB):
            ui01b = ui = True
            continue
        if path in R03A_FILES or (path.startswith(R03A_PREFIXES) and path not in R03A_EXCLUDED):
            r03a = ui01b = True
            if path not in UI01B_FILES and not path.startswith('database/runtime/'):
                continue
        if path.startswith(R03A_WEB):
            r03a = True
        if path in UI01B_FILES or path.startswith('web/src/ui01/runtime/'):
            ui01b = ui = True
            if path not in AUTH_FILES and not path.startswith(('src/Enginia360.Api/OrganizationAccess/','database/runtime/')):
                continue
        if (path in AUTH_FILES or path.startswith(('src/Enginia360.Api/BrowserAuthentication/',
                'src/Enginia360.Api/OrganizationAccess/','database/runtime/','tests/browser/',
                'scripts/run-r00','scripts/test-r00'))
                or (path.startswith('tests/Enginia360.Api.Tests/') and parsed.stem in AUTH_TESTS)):
            auth = True
        elif path.startswith('web/'):
            ui = True
        elif path.endswith('.md') or path.startswith('docs/') or path in ('.gitignore', 'scripts/test-c00-consistency.py'):
            pass
        else:
            unknown.append(path)
    if unknown:
        raise ValueError('extend and test direct-dependency impact mapping for: '+', '.join(unknown))
    filters = ([AUTH_FILTER] if auth or ui01b else []) + ([R03A_FILTER if r03a else WORKSHOP_FILTER] if ui01b else [])
    return {'changed_paths':paths,'api_filter':'|'.join(filters),
            'browser':auth,'ui01b':ui01b,'r03a':r03a,'r03a2':r03a,'r04a':r04a,'migrations':auth or ui01b,'ui_build':auth or ui,'ui_tests':ui,
            'full_architecture':False}


def changed_paths(base, head):
    for value in (base, head):
        if not re.fullmatch(r'[0-9a-f]{40}',value):
            raise ValueError('comparison commits must be exact 40-character lowercase SHAs')
    return subprocess.check_output(['git','diff','--name-only','-z',base,head],text=True).rstrip('\0').split('\0') if base != head else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--paths-json')
    parser.add_argument('--base')
    parser.add_argument('--head')
    args = parser.parse_args()
    if args.paths_json is not None:
        paths = json.loads(args.paths_json)
        if not isinstance(paths,list) or any(not isinstance(path,str) for path in paths):
            raise ValueError('changed paths must be a string array')
    else:
        paths = changed_paths(args.base or '',args.head or '')
        paths = [path for path in paths if path]
    print(json.dumps(selection(paths),sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)
