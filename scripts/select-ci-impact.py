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
    'scripts/test-r04b1-supplier.py','scripts/owner-supplier-vendor-identity.py','scripts/test-r04b1-impact.py',
    'web/nginx.r00b-test.conf','web/runtime-access.html','web/runtime-access.js',
}
AUTH_TESTS = {'BrowserSessionTests','BoundedTicketStoreTests','BrowserAuthenticationBoundaryTests',
              'ExternalIdentityAuthenticationTests','AuthorizedContextContractTests','LimitedGrantAdministrationTests',
              'MasterAuthorityEnforcementTests','BootstrapTests','RuntimeMigrationPoolTests'}
UI01B_FILES = {'scripts/owner-master-authority.py','scripts/test-r02b-authority.py',
    'scripts/test-r04b1-supplier.py','scripts/owner-supplier-vendor-identity.py','scripts/test-r04b1-impact.py',
    'database/runtime/migrations/0027_supplier_role.sql',
    'src/Modules/Counterparties/Enginia360.Counterparties/SupplierEndpoints.cs',
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
R03B_FILES = {'scripts/run-r03b-tests.py','scripts/test-r03b-impact.py','scripts/test-r03b-migration.py','scripts/test-r03b-lifecycle.py','tests/browser/r03b-acceptance.cjs','compose.r03b-test.yaml','tests/Enginia360.Api.Tests/WorkshopOwnActualTimeTests.cs','database/runtime/migrations/0022_workshop_own_actual_time.sql'}
R03B_WEB = ('web/src/ui01/runtime/OwnActualTime','web/src/ui01/runtime/actualTimeContracts')
# R03.c closure panel: its own runner/acceptance/tests, plus the shared producers whose change alters the panel's direct runtime contracts.
R03C_FILES = {'scripts/run-r03c-tests.py','scripts/run-r03c-api-tests.py','scripts/test-r03c-impact.py','scripts/test-r03c-lifecycle.py','tests/browser/r03c-acceptance.cjs',
    'compose.r03c-test.yaml','r03c-api-test.Dockerfile','tests/Enginia360.Api.Tests/WorkshopClosureActionTests.cs','tests/Enginia360.Api.Tests/WorkshopClosureSnapshotTests.cs','tests/Enginia360.Api.Tests/WorkshopClosureContractTests.cs','simulator/administrative-simulator.py'}
R03C_WEB = ('web/src/ui01/runtime/AdministrativeWorkspace','web/src/ui01/runtime/administrative')
R03C_SHARED = {'src/Enginia360.Api/Program.cs','web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/workshopApi.ts','web/src/ui01/runtime/contracts.ts','web/src/ui01/runtime/editorContracts.ts'}
R03C_PREFIXES = ('src/Modules/Workshop/','src/Modules/Integrations/')
R03A_EXCLUDED = {'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs'}
WORKSHOP_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'WorkshopBoundaryTests','CommercialCalculationTests','CounterpartyArchitectureTests'))

R03A_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'WorkshopBoundaryTests','CommercialCalculationTests','CounterpartyArchitectureTests','WorkshopEditorTests','InstallationBoundaryTests','CarcassBoundaryTests',
    'InventoryArchitectureTests','AdministrationBoundaryTests','BillingBoundaryTests','AccountingBoundaryTests'))


R03C_FILTER = '|'.join('FullyQualifiedName~'+name for name in (
    'WorkshopClosure','AdministrationBoundaryTests','WorkshopEditorTests','WorkshopBoundaryTests','InstallationBoundaryTests','CarcassBoundaryTests','BillingBoundaryTests','AccountingBoundaryTests'))


R03C_MINIMAL = 'FullyQualifiedName~WorkshopClosure|FullyQualifiedName~AdministrationBoundaryTests'


# Finite documentation/offline authority contract, not a runtime setup validator.
R04_AUTHORITY_OFFLINE_FILES = {'AGENTS.md', 'docs/foundation/01-glossary-and-domain-boundaries.md',
    'scripts/test-r04-authority.py', 'scripts/test-r04-authority-impact.py', 'scripts/test-c00-consistency.py'}
R06_OFFLINE_FILES = R04_AUTHORITY_OFFLINE_FILES | {'scripts/r06_inventory.py', 'scripts/r06_synthetic.py', 'scripts/r06_reconcile.py',
    'scripts/test-r06-inventory.py', 'scripts/test-r06-reconcile.py', 'scripts/test-r06-impact.py',
    'docs/r06-migration-inventory.json', 'docs/r06-migration-inventory.md',
    'scripts/r06_readiness.py', 'scripts/test-r06-readiness.py', 'scripts/test-r06b2-impact.py',
    'docs/r06-readiness-registry.json', 'docs/r06-recovery-runbook.md',
    'docs/r06-restore-rehearsal.md', 'docs/productization-plan.md', 'docs/productization-backlog.json',
    'docs/foundation/12-costs-and-operations.md'}
# The existing changed-path guard must not assume every later increment is R03.a.
# Its standalone changes still use R03.a acceptance; only this finite offline set is exempt.
R06_WIRING = {'scripts/select-ci-impact.py', '.github/workflows/ci.yml', 'scripts/test-r03a-impact.py'}
R06_COMMAND_SOURCES = {
    'src/Modules/'+module+'/Enginia360.'+module+'/'+file
    for module, files in (
        ('Workshop', ('WorkshopModule.cs', 'CommercialEndpoints.cs', 'EditorEndpoints.cs', 'InstallationEndpoints.cs',
                      'AdministrativeEndpoints.cs', 'ActualTimeEndpoints.cs')),
        ('Inventory', ('InventoryModule.cs', 'PickingEndpoints.cs', 'CarcassReturnEndpoints.cs')),
        ('Billing', ('BillingModule.cs',)), ('Accounting', ('AccountingModule.cs',)),
        ('Counterparties', ('CounterpartiesModule.cs',))) for file in files}


R04C1_FILES = {'scripts/test-r04c1-impact.py','scripts/test-r04c1-guard-mutation.py','scripts/run-r04c1-tests.py','scripts/test-r04c1-lifecycle.py','tests/browser/r04c1-acceptance.cjs','compose.r04c1-test.yaml','database/runtime/migrations/0023_reservation_releases.sql'}

R04C2_FILES = {'scripts/test-r04c2-impact.py','scripts/test-r04c2-guard-mutation.py','scripts/run-r04c2-tests.py','scripts/test-r04c2-lifecycle.py','tests/browser/r04c2-acceptance.cjs','compose.r04c2-test.yaml','database/runtime/migrations/0024_new_part_returns.sql'}

# R06.b.1 ephemeral restore rehearsal: its own files, plus the direct producers it composes at runtime.
R06B1_FILES = {'scripts/run-r06b1-tests.py','scripts/r06b1_restore.py','scripts/test-r06b1-impact.py','scripts/test-r06b1-guards.py',
    'scripts/test-r06b1-lifecycle.py','tests/browser/r06b1-acceptance.cjs','compose.r06b1-test.yaml'}
R06B1_DEPENDENCIES = {'scripts/run-r00b-tests.py','scripts/run-r03b-tests.py','compose.r00b-test.yaml','compose.r03b-test.yaml',
    'scripts/apply-runtime-migrations.py','postgres.runtime.Dockerfile','migrator.runtime.Dockerfile','browser.runtime.Dockerfile',
    'src/Modules/Workshop/Enginia360.Workshop/ActualTimeEndpoints.cs'}
R06B1_PREFIXES = ('database/runtime/', 'src/Modules/Inventory/')


R05A1_OFFLINE_FILES = {'docs/r05a1-giobby-read-contract.md', 'docs/r05a1-evidence.json',
    'docs/r05a1-provider-questions.md', 'scripts/r05a1_evidence.py',
    'scripts/test-r05a1-evidence.py', 'scripts/test-r05a1-impact.py'}

R05A2_OFFLINE_FILES = {'docs/r05a2-sandbox-contract.md', 'docs/r05a2-evidence.json',
    'scripts/test-r05a2-evidence.py', 'scripts/test-r05a2-impact.py'}

R05A7_OFFLINE_FILES = {'docs/r05a7-sandbox-purchase-order-contract.md', 'docs/r05a7-evidence.json',
    'tests/fixtures/r05a7-owned-captures.json', 'scripts/r05a7_purchase_order.py',
    'scripts/test-r05a7-evidence.py', 'scripts/test-r05a7-impact.py'}

R05A6_OFFLINE_FILES = {'docs/r05a6-order-vs-proforma.md', 'docs/r05a6-evidence.json',
    'tests/fixtures/r05a6-owned-captures.json', 'scripts/r05a6_document_type.py',
    'scripts/test-r05a6-evidence.py', 'scripts/test-r05a6-impact.py'}

R05A5_OFFLINE_FILES = {'docs/r05a5-sandbox-closure.md', 'docs/r05a5-evidence.json',
    'tests/fixtures/r05a5-owned-captures.json', 'scripts/r05a5_closure.py',
    'scripts/test-r05a5-evidence.py', 'scripts/test-r05a5-impact.py'}

R05A4_OFFLINE_FILES = {'docs/r05a4-sandbox-recovery-contract.md', 'docs/r05a4-evidence.json',
    'tests/fixtures/r05a4-owned-captures.json', 'scripts/r05a4_recovery.py',
    'scripts/test-r05a4-evidence.py', 'scripts/test-r05a4-impact.py'}

R05A3_OFFLINE_FILES = {'docs/r05a3-sandbox-business-contract.md', 'docs/r05a3-evidence.json',
    'tests/fixtures/r05a3-owned-captures.json', 'scripts/r05a3_captures.py',
    'scripts/test-r05a3-evidence.py', 'scripts/test-r05a3-impact.py'}


R05B0_FILES = {'compose.r05b0-test.yaml', 'scripts/run-r05b0-tests.py', 'scripts/test-r05b0-impact.py',
    'scripts/test-r05b0-lifecycle.py', 'tests/browser/r05b0-acceptance.cjs', 'tests/browser/r05b0-gaps.cjs', 'tests/browser/r05b0-simulator.py',
    'database/runtime/migrations/0025_administrative_bindings.sql',
    'src/Modules/Workshop/Enginia360.Workshop/AdministrativeBinding.cs'}
R05B0_DIRECT = {'src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs',
    'src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs',
    'src/Modules/Workshop/Enginia360.Workshop.Contracts/AdministrativeContracts.cs',
    'src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs',
    'src/Modules/Integrations/Enginia360.Integrations/AdministrativeDispatcher.cs',
    'src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs',
    'src/Enginia360.Api/Program.cs', 'database/runtime/manifest.json',
    'web/src/ui01/runtime/AdministrativeWorkspace.tsx', 'web/src/ui01/runtime/AdministrativeWorkspace.test.tsx',
    'web/src/ui01/runtime/administrativeContracts.ts'}


R05B1_FILES = {'scripts/test-r05b1-impact.py', 'scripts/run-r05b1-tests.py', 'tests/browser/r05b1-acceptance.cjs',
    'tests/browser/r05b1-giobby.py', 'compose.r05b1-test.yaml', 'scripts/test-r05b1-lifecycle.py',
    'tests/Enginia360.Api.Tests/GiobbySalesOrderTests.cs',
    'src/Modules/Integrations/Enginia360.Integrations/GiobbySalesOrderConnector.cs',
    'src/Modules/Integrations/Enginia360.Integrations/GiobbyHost.cs',
    'database/runtime/migrations/0026_giobby_binding_kind.sql'}
R05B1_DIRECT = R05B0_DIRECT | {'src/Modules/Integrations/Enginia360.Integrations/SimulatorConnector.cs',
    'src/Modules/Workshop/Enginia360.Workshop.Contracts/ClosureActionContracts.cs',
    'scripts/run-r05b0-tests.py', 'compose.r05b0-test.yaml', 'web/src/ui01/runtime/administrativeContracts.test.ts'}

R06A2_FILES = {'scripts/r06a2_transfer.py', 'scripts/r06a2_storage.py', 'scripts/run-r06a2-tests.py',
    'scripts/test-r06a2-transfer.py', 'scripts/test-r06a2-storage.py', 'scripts/test-r06a2-impact.py', 'scripts/test-r06a2-lifecycle.py'}
R06A2_DEPENDENCIES = {'scripts/r06_synthetic.py', 'scripts/r06_reconcile.py', 'scripts/r06b1_restore.py', 'postgres.runtime.Dockerfile'}

R04B2A_FILES = {
    'scripts/test-r04b2a-impact.py','scripts/test-r04b2a-purchase.py','scripts/run-r04b2a-tests.py','scripts/test-r04b2a-lifecycle.py',
    'tests/browser/r04b2a-acceptance.cjs','compose.r04b2a-test.yaml','database/runtime/migrations/0028_purchase_intents.sql',
    'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs',
    'src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseIntentContracts.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/PurchaseSuppliers.cs',
    'src/Modules/Integrations/Enginia360.Integrations/PurchaseDestination.cs',
    'web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx',
    'tests/Enginia360.Api.Tests/PurchaseIntentTests.cs'}
R04B2A_DIRECT = {'web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css',
    'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','database/runtime/manifest.json',
    'src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs'}

R04B2B1_FILES = {
    'scripts/test-r04b2b1-impact.py','scripts/test-r04b2b1-prices.py','scripts/run-r04b2b1-tests.py','scripts/test-r04b2b1-lifecycle.py',
    'scripts/owner-purchase-price-grant.py','tests/browser/r04b2b1-acceptance.cjs','compose.r04b2b1-test.yaml',
    'database/runtime/migrations/0029_supplier_purchase_prices.sql',
    'src/Modules/Catalog/Enginia360.Catalog/PurchasePriceEndpoints.cs',
    'tests/Enginia360.Api.Tests/SupplierPurchasePriceTests.cs',
    'web/src/ui01/runtime/SupplierPurchasePrices.tsx','web/src/ui01/runtime/SupplierPurchasePrices.test.tsx'}
R04B2B1_DIRECT = {'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs',
    'src/Modules/Catalog/Enginia360.Catalog/Enginia360.Catalog.csproj','src/Enginia360.Api/Program.cs',
    'database/runtime/manifest.json','web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css',
    'scripts/run-r05b0-tests.py','scripts/run-r00a-tests.py','migrator.runtime.Dockerfile'}

R04B2B2_FILES = {'scripts/test-r04b2b2-impact.py','scripts/test-r04b2b2-freeze.py','scripts/run-r04b2b2-tests.py','scripts/test-r04b2b2-lifecycle.py',
    'tests/browser/r04b2b2-acceptance.cjs','compose.r04b2b2-test.yaml','database/runtime/migrations/0030_purchase_price_freeze.sql'}
R04B2B2_DIRECT = R04B2A_FILES | R04B2A_DIRECT | R04B2B1_FILES | R04B2B1_DIRECT
# Only this finite quote/freeze vertical slice may narrow historical shared-runner matches.
# Changes to any other real producer retain the generic direct-consumer selection below.
R04B2B2_SCOPE = R04B2B2_FILES | {
    'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs',
    'src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseIntentContracts.cs',
    'tests/Enginia360.Api.Tests/PurchaseIntentTests.cs','web/src/ui01/runtime/PurchaseIntent.tsx',
    'web/src/ui01/runtime/PurchaseIntent.test.tsx','tests/browser/r04b2a-acceptance.cjs',
    'scripts/test-r04b2a-purchase.py','database/runtime/manifest.json','migrator.runtime.Dockerfile',
    'scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','scripts/select-ci-impact.py','.github/workflows/ci.yml',
    'docs/r04b2b2-purchase-price-freeze.md','docs/productization-plan.md','docs/productization-backlog.json',
    'docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}

INTEGRATIONS_SRC = 'src/Modules/Integrations/Enginia360.Integrations/'
R04B2B3_FILES = {'scripts/test-r04b2b3-impact.py','scripts/test-r04b2b3-dispatch.py','scripts/run-r04b2b3-tests.py','scripts/test-r04b2b3-lifecycle.py',
    'tests/browser/r04b2b3-acceptance.cjs','tests/browser/r04b2b3-giobby.py','compose.r04b2b3-test.yaml','database/runtime/migrations/0031_purchase_dispatch.sql',
    'tests/Enginia360.Api.Tests/GiobbyPurchaseOrderTests.cs'}
R04B2B3_DIRECT = {INTEGRATIONS_SRC+name for name in ('Enginia360.Integrations.csproj','GiobbyHost.cs','GiobbyPurchaseOrderConnector.cs','GiobbySalesOrderConnector.cs',
    'GiobbyWire.cs','IntegrationsDbContext.cs','IntegrationsModule.cs','PurchaseDestination.cs','PurchaseConnector.cs','PurchaseDispatcher.cs','SimulatorConnector.cs','packages.lock.json')} | {
    'src/Modules/Integrations/module.json','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchContracts.cs',
    'src/Modules/Inventory/Enginia360.Inventory/PurchaseDispatchOutbox.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
    'src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json','tests/Enginia360.Api.Tests/AdministrationBoundaryTests.cs',
    'scripts/test-r00-migrations.py','scripts/test-r04b2a-purchase.py','tests/Enginia360.Api.Tests/PurchaseIntentTests.cs'}
# Only this finite purchase-order connector slice may narrow historical runners; any other real producer keeps the generic direct-consumer selection.
R04B2B3_SCOPE = R04B2B3_FILES | R04B2B3_DIRECT | {'database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py',
    'scripts/select-ci-impact.py','scripts/test-r03a-impact.py','.github/workflows/ci.yml','docs/r04b2b3-giobby-purchase-order-connector.md','docs/productization-plan.md','docs/productization-backlog.json',
    'docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}


def selection(paths):
    paths = sorted(set(paths))
    r06a2 = bool(set(paths) & (R06A2_FILES | R06A2_DEPENDENCIES))
    staging_only = r06a2 and set(paths) <= R06A2_FILES | R06_OFFLINE_FILES | R06_WIRING | {'docs/r06a2-synthetic-import-export.md'}
    r05a7_offline = bool(set(paths) & R05A7_OFFLINE_FILES)
    r05a7_only = r05a7_offline and set(paths) <= R05A7_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05a6_offline = bool(set(paths) & R05A6_OFFLINE_FILES)
    r05a6_only = r05a6_offline and set(paths) <= R05A6_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05a5_offline = bool(set(paths) & R05A5_OFFLINE_FILES)
    r05a5_only = r05a5_offline and set(paths) <= R05A5_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05a4_offline = bool(set(paths) & R05A4_OFFLINE_FILES)
    r05a4_only = r05a4_offline and set(paths) <= R05A4_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05a3_offline = bool(set(paths) & R05A3_OFFLINE_FILES)
    r05a3_only = r05a3_offline and set(paths) <= R05A3_OFFLINE_FILES | R05A2_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05a2_offline = bool(set(paths) & R05A2_OFFLINE_FILES)
    r05a2_only = r05a2_offline and set(paths) <= R05A2_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
    r05b1 = bool(set(paths) & (R05B1_FILES | R05B1_DIRECT))
    r05b0 = bool(set(paths) & (R05B0_FILES | R05B0_DIRECT))
    r05a1_offline = bool(set(paths) & R05A1_OFFLINE_FILES)
    r05a1_only = r05a1_offline and set(paths) <= R05A1_OFFLINE_FILES | R06_WIRING
    r06b1 = bool(set(paths) & (R06B1_FILES | R06B1_DEPENDENCIES)) or any(path.startswith(R06B1_PREFIXES) for path in paths)
    r06_offline = bool(set(paths) & (R06_OFFLINE_FILES | R06B1_FILES | R06_COMMAND_SOURCES | {'scripts/apply-runtime-migrations.py'})) or any(
        path.startswith('database/runtime/') for path in paths)
    offline_only = r06_offline and set(paths) <= R06_OFFLINE_FILES | R06B1_FILES | R06_WIRING
    r04c1 = bool(set(paths) & R04C1_FILES) or any(path.startswith(('src/Modules/Inventory/','web/src/ui01/runtime/MaterialRelease')) for path in paths)
    r04c2 = bool(set(paths) & (R04C2_FILES | {'web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css'})) or any(path.startswith(('src/Modules/Inventory/','web/src/ui01/runtime/Material')) for path in paths) or 'src/Modules/Workshop/Enginia360.Workshop/InstallationEndpoints.cs' in paths
    auth = ui = ui01b = r03a = r04a = r04c1 or r04c2
    r03b = r03c = r03c_full = False
    r06_offline = r06_offline or r04c1 or r04c2 or r05b0 or r05b1 or r06a2
    r06b1 = r06b1 or r05b0
    if r05b0 or r05b1: auth = ui = ui01b = r03c = True
    r04b2a = bool(set(paths) & (R04B2A_FILES | R04B2A_DIRECT))
    if r04b2a: auth = ui = ui01b = r06_offline = True
    r04b2b1 = bool(set(paths) & (R04B2B1_FILES | R04B2B1_DIRECT))
    if r04b2b1: auth = ui = ui01b = r06_offline = True
    r04b2b2 = bool(set(paths) & (R04B2B2_FILES | R04B2B2_DIRECT))
    if r04b2b2: auth = ui = ui01b = r06_offline = True
    r04b2b3 = bool(set(paths) & (R04B2B3_FILES | R04B2B3_DIRECT))
    if r04b2b3: auth = ui = ui01b = r06_offline = True
    unknown = []
    for path in paths:
        parsed = PurePosixPath(path)
        if not path or parsed.is_absolute() or '..' in parsed.parts or '\\' in path or str(parsed) != path:
            raise ValueError('invalid changed path')
        if path in R04B2B3_FILES or path in R04B2B3_DIRECT:
            if path.startswith('src/Modules/Integrations/'): r03c = r03c_full = r03a = r05b1 = True
            continue
        if path in R04B2B2_FILES or path in R04B2A_FILES or path in R04B2B1_FILES or path == 'src/Modules/Catalog/Enginia360.Catalog/Enginia360.Catalog.csproj':
            continue
        if path in R06A2_FILES or (staging_only and path in R06_WIRING):
            continue
        if path in R05A7_OFFLINE_FILES or (r05a7_only and path in R06_WIRING):
            continue
        if path in R05A6_OFFLINE_FILES or (r05a6_only and path in R06_WIRING):
            continue
        if path in R05A5_OFFLINE_FILES or (r05a5_only and path in R06_WIRING):
            continue
        if path in R05A4_OFFLINE_FILES or (r05a4_only and path in R06_WIRING):
            continue
        if path in R05A3_OFFLINE_FILES or (r05a3_only and path in R06_WIRING):
            continue
        if path in R05A2_OFFLINE_FILES or (r05a2_only and path in R06_WIRING):
            continue
        if path in R05B0_FILES or path in R05B1_FILES:
            continue
        if path in R05A1_OFFLINE_FILES or (r05a1_only and path in R06_WIRING):
            continue
        if path in R04C2_FILES or path in R04C1_FILES or path in R06_OFFLINE_FILES or path in R06B1_FILES or (offline_only and path in R06_WIRING):
            continue
        if path.startswith('docs/') and parsed.suffix in {'.py', '.sh', '.js', '.cjs', '.ts', '.cs'}:
            unknown.append(path)
            continue
        if path in R03C_FILES or path.startswith(R03C_WEB):
            r03c = r03c_full = auth = ui = ui01b = True
            continue
        if path.startswith('src/Modules/Integrations/'):
            # Connector code is consumed by the closure panel through the real worker and by the administration boundary tests.
            r03c = r03c_full = auth = ui = ui01b = r03a = True
            continue
        if path in R03C_SHARED or path.startswith(R03C_PREFIXES):
            r03c = True
            # Composition/registration and shared transport files need only the administration boundary; producers need all direct consumers.
            if path not in R03C_SHARED and path not in R03A_EXCLUDED: r03c_full = True
        if path in R03B_FILES or path.startswith(R03B_WEB) or path.startswith('src/Modules/Workshop/'):
            r03b = auth = ui = ui01b = True
            if path not in R03A_EXCLUDED:
                r03a = True
            if path in R03B_FILES or path.startswith(R03B_WEB):
                continue
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
    if r03b: filters.append('FullyQualifiedName~WorkshopOwnActualTimeTests')
    if r03c: filters.append(R03C_FILTER if r03c_full else R03C_MINIMAL)
    if r05b1: filters.append('FullyQualifiedName~GiobbySalesOrderTests')
    if r04b2b2: filters.append('FullyQualifiedName~PurchaseIntentTests|FullyQualifiedName~SupplierPurchasePriceTests')
    if r04b2a: filters.append('FullyQualifiedName~PurchaseIntentTests')
    if r04b2b1: filters.append('FullyQualifiedName~SupplierPurchasePriceTests')
    if r04b2b3: filters.append('FullyQualifiedName~GiobbyPurchaseOrderTests|FullyQualifiedName~GiobbySalesOrderTests|FullyQualifiedName~AdministrationBoundaryTests')
    result = {'r04b2b3':r04b2b3,'r04b2b2':r04b2b2,'r04b2b1':r04b2b1,'r04b2a':r04b2a,'changed_paths':paths,'api_filter':'|'.join(filters),'r06_offline':r06_offline,'r05a1_offline':r05a1_offline,'r05a2_offline':r05a2_offline,'r05a3_offline':r05a3_offline,'r05a4_offline':r05a4_offline,'r05a5_offline':r05a5_offline,'r05a6_offline':r05a6_offline,'r05a7_offline':r05a7_offline,'r05b0':r05b0,
            'browser':auth,'ui01b':ui01b,'r03a':r03a,'r03a2':r03a,'r04a':r04a,'r04c1':r04c1,'r04c2':r04c2,'r06b1':r06b1,'r03b':r03b,'r03c':r03c,'migrations':auth or ui01b,'ui_build':auth or ui,'ui_tests':ui,
            'r05b1':r05b1, 'r06a2':r06a2, 'full_architecture':False}
    if set(paths) & R04B2B2_FILES and set(paths) <= R04B2B2_SCOPE:
        for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r05b1','r06b1','r06a2'):
            result[key] = False
        for key in ('browser','migrations','ui01b','r04b2a','r04b2b1','r04b2b2','ui_build','ui_tests','r06_offline'):
            result[key] = True
        result['api_filter'] = AUTH_FILTER+'|'+WORKSHOP_FILTER+'|FullyQualifiedName~InventoryArchitectureTests|FullyQualifiedName~PurchaseIntentTests|FullyQualifiedName~SupplierPurchasePriceTests'
    if set(paths) & R04B2B3_FILES and set(paths) <= R04B2B3_SCOPE:
        for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r06b1','r06a2'):
            result[key] = False
        for key in ('browser','migrations','ui01b','r04b2a','r04b2b2','r04b2b3','r05b1','ui_build','r06_offline'):
            result[key] = True
        result['ui_tests'] = False
        result['api_filter'] = AUTH_FILTER+'|'+WORKSHOP_FILTER+'|FullyQualifiedName~InventoryArchitectureTests|FullyQualifiedName~PurchaseIntentTests|FullyQualifiedName~SupplierPurchasePriceTests|FullyQualifiedName~GiobbySalesOrderTests|FullyQualifiedName~GiobbyPurchaseOrderTests|FullyQualifiedName~AdministrationBoundaryTests'
    return result



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
