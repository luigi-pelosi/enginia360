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
    'scripts/run-r00a-tests.sh','scripts/run-r00a-tests.py','scripts/run-r00b-tests.py',
    'scripts/test-r00a-ci.py','scripts/test-r00a-lifecycle.py','scripts/test-r00-migrations.py',
    'scripts/test-r00b-lifecycle.py','scripts/test-r00b-migration-tls.py','scripts/test-r00b-bindings.py',
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
    'docs/r04b3-receipt-runtime.md', 'scripts/test-productization-consistency.py',
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

R05A8_OFFLINE_FILES = {'docs/r05a9-isolated-receipt-contract.md', 'docs/r05a9-evidence.json',
    'tests/fixtures/r05a9-owned-captures.json', 'scripts/test-r05a9-evidence.py',
    'docs/r05a8-sandbox-receipt-contract.md', 'docs/r05a8-evidence.json',
    'tests/fixtures/r05a8-owned-captures.json', 'scripts/r05a8_receipt.py',
    'scripts/test-r05a8-evidence.py', 'scripts/test-r05a8-impact.py'}

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
    'tests/browser/r04b2b3-acceptance.cjs','tests/browser/r04b2b3-readout.cjs','tests/browser/r04b2b3-giobby.py','compose.r04b2b3-test.yaml','database/runtime/migrations/0031_purchase_dispatch.sql',
    'tests/Enginia360.Api.Tests/GiobbyPurchaseOrderTests.cs','database/runtime/migrations/0032_purchase_dispatch_readout.sql'}
R04B2B3_FILES |= {'scripts/test-r04b3-migration-selection.py','scripts/test-r04b3-lifecycle.py','scripts/run-r04b3-tests.py','scripts/owner-receipt-grant.py','tests/browser/r04b3-acceptance.cjs','tests/browser/r04b3-giobby.py','compose.r04b3-test.yaml',
    'scripts/test-r04b3-impact.py','scripts/test-r04b3-receipts.py','database/runtime/migrations/0033_receipt_intents.sql',
    'src/Modules/Inventory/Enginia360.Inventory/ReceiptIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory/ReceiptDispatchOutbox.cs',
    'src/Modules/Inventory/Enginia360.Inventory.Contracts/ReceiptContracts.cs','src/Modules/Integrations/Enginia360.Integrations/ReceiptDispatcher.cs',
    'src/Modules/Integrations/Enginia360.Integrations/GiobbyReceiptConnector.cs','src/Modules/Integrations/Enginia360.Integrations/ReceiptDestination.cs',
    'tests/Enginia360.Api.Tests/GiobbyReceiptTests.cs'}
# PR2 readout: selected for the dispatch acceptance in addition to (never instead of) their existing purchase/generic consumers.
R04B2B3_FILES |= {'web/src/ui01/runtime/ReceiptReceiving.tsx','web/src/ui01/runtime/ReceiptReceiving.test.tsx','database/runtime/migrations/0034_receipt_sources.sql'}
R04B2B3_READOUT = {'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchReadout.cs',
    'web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx'}
R04B2B3_DIRECT = {INTEGRATIONS_SRC+name for name in ('Enginia360.Integrations.csproj','GiobbyHost.cs','GiobbyPurchaseOrderConnector.cs','GiobbySalesOrderConnector.cs',
    'GiobbyWire.cs','IntegrationsDbContext.cs','IntegrationsModule.cs','PurchaseDestination.cs','PurchaseConnector.cs','PurchaseDispatcher.cs','SimulatorConnector.cs','packages.lock.json')} | {
    'src/Modules/Integrations/module.json','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchContracts.cs',
    'src/Modules/Inventory/Enginia360.Inventory/PurchaseDispatchOutbox.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
    'src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json','tests/Enginia360.Api.Tests/AdministrationBoundaryTests.cs',
    'scripts/test-r00-migrations.py','scripts/test-r04b2a-purchase.py','tests/Enginia360.Api.Tests/PurchaseIntentTests.cs','tests/browser/r04b2b1-acceptance.cjs','tests/browser/r04b2a-acceptance.cjs','tests/browser/r04b2b2-acceptance.cjs'}
# Only this finite purchase-order connector slice may narrow historical runners; any other real producer keeps the generic direct-consumer selection.
R04B2B3_SCOPE = R04B2B3_FILES | R04B2B3_DIRECT | R04B2B3_READOUT | {'scripts/test-r04-authority.py','docs/r04b3-receipt-runtime.md','src/Modules/Inventory/module.json','src/Modules/Inventory/Enginia360.Inventory/TechnicalAuditFilter.cs','database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py',
    'scripts/select-ci-impact.py','scripts/test-r03a-impact.py','.github/workflows/ci.yml','docs/r04b2b3-giobby-purchase-order-connector.md','docs/productization-plan.md','docs/productization-backlog.json',
    'docs/r06-migration-inventory.json','docs/r06-migration-inventory.md','web/src/ui01/runtime/MaterialOperations.tsx','web/src/ui01/runtime/MaterialOperations.test.tsx'}


D95_FILES = {'scripts/owner-external-supplier-role.py', 'scripts/test-d95-projection.py',
             'scripts/test-d95-impact.py', 'database/runtime/migrations/0035_external_supplier_projection.sql',
             'tests/browser/d95-projection.cjs'}
AUTH_FILES |= D95_FILES
UI01B_FILES |= D95_FILES
R04B2A_DIRECT |= D95_FILES
D95_SCOPE = D95_FILES | {'scripts/run-r00a-tests.py','scripts/run-ui01b-tests.py',
    'migrator.runtime.Dockerfile','scripts/select-ci-impact.py','.github/workflows/ci.yml',
    'database/runtime/manifest.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md',
    'docs/r02-d95-external-supplier-projection.md','docs/r04b1-supplier-role.md',
    'scripts/test-r04b3-migration-selection.py',
    'docs/productization-plan.md','docs/productization-backlog.json'}


# Finite D96 reset exception. Shared wiring alone retains its historical
# runtime contract; a reset-specific document/guard must anchor the exception.
MVP_OFFLINE_FILES = {
    'AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
    'docs/mvp-existing-code-assessment.md', 'docs/mvp-delivery-plan.md',
    'docs/mvp-backlog.json', 'docs/productization-plan.md',
    'scripts/test-mvp-baseline.py', 'scripts/test-mvp-impact.py',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
}
MVP_ANCHORS = MVP_OFFLINE_FILES - {'AGENTS.md', 'docs/productization-plan.md',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}
MVP_GUARDS = {'scripts/test-mvp-baseline.py', 'scripts/test-mvp-impact.py'}

# D97 adds only its finite documentary contract/guards, not a runtime ceiling.
# Keep the D96 set/assertions intact and shared wiring's default consumers.
D97_FILES = {'docs/mvp03b-user-administration.md', 'scripts/test-d97-policy.py',
             'scripts/test-d97-impact.py'}
D97_SCOPE = D97_FILES | {'AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
    'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}


# D98 is an exact-path documentary gate, not an invitation/runtime exemption.
D98_FILES = {'docs/mvp03b2-user-onboarding.md', 'scripts/test-d98-policy.py',
             'scripts/test-d98-impact.py'}
D98_SCOPE = D98_FILES | {'AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
    'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
    'docs/mvp03b-user-administration.md',
    'docs/mvp03b1-tenant-role-contract.md', 'docs/mvp03b1-progress.md'}


# MVP-01 owns only these explicit paths. New routes/scripts require a tested mapping.
FRONTEND_FILES = {
    'frontend/' + path for path in (
        '.gitignore', 'package.json', 'package-lock.json', 'tsconfig.json', 'next-env.d.ts',
        'next.config.ts', 'postcss.config.mjs', 'components.json', 'shadcn-LICENSE.txt',
        'app/layout.tsx', 'app/page.tsx', 'app/globals.css', 'app/not-found.tsx',
        'app/domains/[domain]/page.tsx', 'components/shell.tsx',
        'components/ui/button.tsx', 'components/ui/card.tsx', 'components/ui/badge.tsx',
        'lib/domains.ts', 'lib/utils.ts', 'tests/shell.test.tsx',
        'tests/acceptance.spec.ts', 'playwright.config.ts', 'Dockerfile', '.dockerignore',
    )
} | {'scripts/run-mvp01-tests.py', 'scripts/test-mvp01-impact.py', 'docs/mvp01-frontend.md'}
FRONTEND_WIRING = {'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}
FRONTEND_CHECKPOINTS = {'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md'}


PLATFORM_FILES = {
    'src/Enginia360.Api/PlatformAdministration/PlatformAuthority.cs',
    'scripts/owner-platform-authority.py', 'scripts/test-mvp02a-authority.py',
    'scripts/run-mvp02a-tests.py', 'scripts/test-mvp02a-impact.py',
    'tests/browser/mvp02a-authority.cjs', 'database/runtime/migrations/0036_platform_authority.sql',
}
PLATFORM_WIRING = {'src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs',
    'migrator.runtime.Dockerfile', 'database/runtime/manifest.json',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
    'tests/Enginia360.Api.Tests/ExternalIdentityAuthenticationTests.cs',
    'docs/mvp02a-platform-authority.md', 'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md',
    'docs/mvp01-frontend.md', 'docs/productization-plan.md', 'docs/r06-migration-inventory.json', 'docs/r06-migration-inventory.md'}


ORGANIZATION_FILES = {
    'src/Enginia360.Api/PlatformAdministration/OrganizationAdministration.cs',
    'scripts/test-mvp02b-impact.py', 'scripts/test-mvp02b-organization.py',
    'scripts/run-mvp02b-tests.py', 'tests/browser/mvp02b-organization.cjs',
    'database/runtime/migrations/0037_organization_administration.sql',
    'database/runtime/migrations/0038_organization_delegation.sql',
}
ORGANIZATION_WIRING = PLATFORM_FILES | PLATFORM_WIRING | {'docs/mvp02b-organization-administration.md', 'src/Enginia360.Api/Program.cs', 'docs/mvp03a-organization-delegation.md', 'docs/mvp03a-progress.md'}


# Authenticated UI owns an explicit finite surface; its backend consumers remain selected.
AUTHENTICATED_ORGANIZATION_FILES = {
    'frontend/app/organization/page.tsx', 'frontend/components/organization-workspace.tsx',
    'frontend/lib/organization.ts', 'frontend/lib/private-backend.ts',
    'frontend/tests/organization.test.tsx', 'frontend/tests/private-backend.test.ts',
    'scripts/run-mvp02c-tests.py', 'scripts/test-mvp02c-impact.py',
    'tests/browser/mvp02c-organization.cjs', 'compose.mvp02c-test.yaml',
    'tests/fixtures/nginx.mvp02c.conf', 'docs/mvp02c-authenticated-organization.md',
}

AUTHENTICATED_ORGANIZATION_DIRECT = {
    'frontend/' + path for path in (
        'app/layout.tsx', 'app/globals.css', 'app/domains/[domain]/page.tsx',
        'components/shell.tsx', 'components/ui/button.tsx', 'components/ui/card.tsx',
        'lib/utils.ts', 'package.json', 'package-lock.json', 'Dockerfile',
        'next.config.ts', 'tsconfig.json', 'postcss.config.mjs',
    )
} | {
    'src/Enginia360.Api/BrowserAuthentication/' + name + '.cs' for name in (
        'BrowserSessionModule', 'BoundedTicketStore', 'ExternalIdentityResolver',
        'HttpsOidcConfigurationManager',
    )
} | {
    'src/Enginia360.Api/PlatformAdministration/PlatformAuthority.cs',
    'src/Enginia360.Api/PlatformAdministration/OrganizationAdministration.cs',
    'src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs',
    'src/Enginia360.Api/Program.cs', 'src/Enginia360.Api/Enginia360.Api.csproj',
    'src/Enginia360.Api/packages.lock.json', 'src/Enginia360.Api/Dockerfile',
    'database/runtime/migrations/0036_platform_authority.sql',
    'database/runtime/migrations/0037_organization_administration.sql',
    'database/runtime/migrations/0038_organization_delegation.sql',
    'database/runtime/manifest.json', 'scripts/apply-runtime-migrations.py',
    'scripts/owner-platform-authority.py', 'scripts/run-r00b-tests.py',
    'browser.runtime.Dockerfile', 'postgres.runtime.Dockerfile',
    'migrator.runtime.Dockerfile', 'keycloak.runtime.Dockerfile',
}

TENANT_ROLE_FILES = {
    'database/runtime/migrations/0039_tenant_roles.sql',
    'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs',
    'scripts/test-mvp03b1-roles.py', 'scripts/run-mvp03b1-tests.py', 'scripts/test-mvp03b1-impact.py',
    'frontend/app/users/page.tsx', 'frontend/components/tenant-role-workspace.tsx',
    'frontend/lib/tenant-roles.ts', 'frontend/tests/tenant-roles.test.tsx',
    'tests/browser/mvp03b1-roles.cjs',
}
TENANT_ROLE_DIRECT = AUTHENTICATED_ORGANIZATION_DIRECT | AUTHENTICATED_ORGANIZATION_FILES | {
    'src/Enginia360.Api/OrganizationAccess/LimitedGrantAdministration.cs',
}
TENANT_ROLE_SCOPE = TENANT_ROLE_FILES | ORGANIZATION_FILES | ORGANIZATION_WIRING | AUTHENTICATED_ORGANIZATION_FILES | FRONTEND_FILES | {
    'docs/mvp03b1-tenant-role-contract.md', 'docs/mvp03b1-progress.md',
    # Exact service fixture consumes the changed verified-identity fence. Its
    # foundation SQL/pool and AUTH_FILTER consumers remain selected below.
    'tests/Enginia360.Api.Tests/LimitedGrantAdministrationTests.cs',
}

# Newly edited owning contexts/ports were not standalone producers in the old
# selector. Map these exact files to existing auth/workshop consumers as well as
# the membership runner; do not create a whole-directory exception.
MEMBERSHIP_OWNING_FILES = {
    'src/Modules/Billing/Enginia360.Billing/BillingDbContext.cs',
    'src/Modules/Billing/Enginia360.Billing/BillingModule.cs',
    'src/Modules/Billing/Enginia360.Billing/ConfirmedInvoices.cs',
    'src/Modules/Accounting/Enginia360.Accounting/AccountingDbContext.cs',
    'src/Modules/Accounting/Enginia360.Accounting/AccountingModule.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/Infrastructure/CounterpartiesDbContext.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/TechnicalAuditFilter.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/WorkshopCounterparties.cs',
    'src/Modules/Counterparties/Enginia360.Counterparties/DestinationEndpoints.cs',
}
UI01B_FILES |= MEMBERSHIP_OWNING_FILES
AUTH_FILES |= MEMBERSHIP_OWNING_FILES

# MVP03.b.2a: finite new ingress, never a prefix exemption. Existing mixed
# producers retain their own consumer jobs in the recursive selection below.
MEMBERSHIP_ACCESS_FILES = {'scripts/test-mvp03b2a-membership.py', 'src/Enginia360.Api/OrganizationAccess/CompanyAccessIdentity.cs', 'tests/Enginia360.Api.Tests/CounterpartyMembershipFenceTests.cs', 'src/Modules/Accounting/Enginia360.Accounting/MembershipOperation.cs', 'src/Modules/Inventory/Enginia360.Inventory/MembershipOperation.cs', 'src/Modules/Vehicles/Enginia360.Vehicles/MembershipOperation.cs', 'tests/Enginia360.Api.Tests/WorkshopMembershipFenceTests.cs', 'src/Modules/Integrations/Enginia360.Integrations/MembershipOperation.cs', 'tests/Enginia360.Api.Tests/MembershipAccessTests.cs', 'src/Modules/Billing/Enginia360.Billing/MembershipOperation.cs', 'scripts/test-mvp03b2a-impact.py', 'src/Modules/Catalog/Enginia360.Catalog/MembershipOperation.cs', 'tests/browser/mvp03b2a-membership.cjs', 'tests/Enginia360.Api.Tests/BusinessMembershipFenceTests.cs', 'scripts/run-mvp03b2a-tests.py', 'database/runtime/migrations/0040_membership_access.sql'}
MEMBERSHIP_ACCESS_DIRECT = {'src/Modules/Accounting/Enginia360.Accounting/MembershipOperation.cs', 'src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs', 'src/Enginia360.Api/OrganizationAccess/CounterpartyAccessAdapter.cs', 'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs', 'src/Enginia360.Api/BrowserAuthentication/ExternalIdentityResolver.cs', 'src/Modules/Billing/Enginia360.Billing/BillingDbContext.cs', 'src/Modules/Integrations/Enginia360.Integrations/MembershipOperation.cs', 'src/Modules/Counterparties/Enginia360.Counterparties/TechnicalAuditFilter.cs', 'frontend/components/tenant-role-workspace.tsx', 'src/Modules/Counterparties/Enginia360.Counterparties/DestinationEndpoints.cs', 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs', 'src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs', 'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs', 'src/Modules/Workshop/Enginia360.Workshop/ActualTimeEndpoints.cs', 'src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs', 'src/Modules/Inventory/Enginia360.Inventory/InstallationStockEffects.cs', 'database/runtime/manifest.json', 'src/Modules/Accounting/Enginia360.Accounting/AccountingModule.cs', 'src/Modules/Inventory/Enginia360.Inventory/NewPartReturnEndpoints.cs', 'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs', 'tests/Enginia360.Api.Tests/WorkshopMembershipFenceTests.cs', 'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs', 'src/Modules/Billing/Enginia360.Billing/MembershipOperation.cs', 'frontend/lib/tenant-roles.ts', 'src/Modules/Inventory/Enginia360.Inventory/PickingEndpoints.cs', 'scripts/test-mvp03b2a-impact.py', 'src/Modules/Catalog/Enginia360.Catalog/MembershipOperation.cs', 'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs', 'src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs', 'tests/Enginia360.Api.Tests/RuntimeMigrationPoolTests.cs', 'tests/Enginia360.Api.Tests/BusinessMembershipFenceTests.cs', 'src/Enginia360.Api/OrganizationAccess/BillingAccessAdapter.cs', 'src/Modules/Accounting/Enginia360.Accounting/AccountingDbContext.cs', 'database/runtime/migrations/0040_membership_access.sql', 'src/Modules/Counterparties/Enginia360.Counterparties/Infrastructure/CounterpartiesDbContext.cs', 'src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs', 'src/Modules/Integrations/Enginia360.Integrations/IntegrationsDbContext.cs', 'frontend/lib/private-backend.ts', 'src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs', 'src/Modules/Catalog/Enginia360.Catalog/PurchasePriceEndpoints.cs', 'tests/Enginia360.Api.Tests/MembershipAccessTests.cs', 'src/Enginia360.Api/OrganizationAccess/WorkshopAccessAdapter.cs', 'src/Modules/Workshop/Enginia360.Workshop/CommercialEndpoints.cs', 'src/Enginia360.Api/OrganizationAccess/InventoryAccessAdapter.cs', 'src/Modules/Workshop/Enginia360.Workshop/WorkshopReservationLines.cs', 'src/Modules/Counterparties/Enginia360.Counterparties/WorkshopCounterparties.cs', 'tests/browser/mvp03b2a-membership.cjs', 'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs', 'src/Modules/Vehicles/Enginia360.Vehicles/VehiclesModule.cs', 'src/Modules/Workshop/Enginia360.Workshop/TechnicalAuditFilter.cs', 'src/Modules/Inventory/Enginia360.Inventory/CarcassReturnEndpoints.cs', 'scripts/test-mvp03b2a-membership.py', 'src/Enginia360.Api/OrganizationAccess/CompanyAccessIdentity.cs', 'src/Modules/Workshop/Enginia360.Workshop/InstallationEndpoints.cs', 'tests/Enginia360.Api.Tests/CounterpartyMembershipFenceTests.cs', 'src/Modules/Billing/Enginia360.Billing/ConfirmedInvoices.cs', 'src/Enginia360.Api/OrganizationAccess/AccountingAccessAdapter.cs', 'src/Modules/Billing/Enginia360.Billing/BillingModule.cs', 'src/Modules/Inventory/Enginia360.Inventory/MembershipOperation.cs', 'src/Modules/Vehicles/Enginia360.Vehicles/MembershipOperation.cs', 'src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs', 'src/Modules/Inventory/Enginia360.Inventory/TechnicalAuditFilter.cs', 'frontend/app/users/page.tsx', 'src/Modules/Workshop/Enginia360.Workshop/WorkshopBillingSources.cs', 'scripts/run-mvp03b2a-tests.py', 'src/Modules/Inventory/Enginia360.Inventory/ReceiptIntentEndpoints.cs'}

MEMBERSHIP_ACCESS_DIRECT |= {'frontend/tests/tenant-roles.test.tsx', 'scripts/test-r04b2b1-prices.py'}

FEDERATED_ONBOARDING_FILES = {
    'src/Enginia360.Api/BrowserAuthentication/PendingOnboarding.cs',
    'database/runtime/migrations/0041_federated_onboarding.sql',
    'frontend/app/onboarding/page.tsx', 'frontend/app/onboarding-admin/page.tsx',
    'frontend/components/onboarding-workspace.tsx', 'frontend/lib/onboarding.ts',
    'frontend/tests/onboarding.test.tsx', 'tests/Enginia360.Api.Tests/FederatedOnboardingTests.cs',
    'scripts/test-mvp03b2b-onboarding.py', 'scripts/test-mvp03b2b-impact.py',
    'scripts/run-mvp03b2b-tests.py', 'tests/browser/mvp03b2b-onboarding.cjs',
}
FEDERATED_ONBOARDING_DIRECT = AUTHENTICATED_ORGANIZATION_DIRECT | {
    'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs',
    'frontend/lib/private-backend.ts', 'frontend/components/tenant-role-workspace.tsx',
    'database/runtime/migrations/0039_tenant_roles.sql', 'database/runtime/migrations/0040_membership_access.sql',
    'scripts/run-mvp03b2a-tests.py', 'scripts/run-mvp02b-tests.py',
    'tests/fixtures/nginx.mvp02c.conf', 'compose.mvp02c-test.yaml',
}


COUNTERPARTY_MANAGEMENT_FILES = {
    'database/runtime/migrations/0042_counterparty_management.sql',
    'frontend/app/counterparties/page.tsx',
    'frontend/components/counterparty-workspace.tsx',
    'frontend/lib/counterparties.ts',
    'frontend/tests/counterparties.test.tsx',
    'scripts/run-mvp04-tests.py',
    'scripts/test-mvp04-counterparties.py',
    'scripts/test-mvp04-impact.py',
    'src/Modules/Counterparties/Enginia360.Counterparties/ManagementEndpoints.cs',
    'tests/Enginia360.Api.Tests/CounterpartyManagementTests.cs',
    'tests/browser/mvp04-counterparties.cjs',
}
COUNTERPARTY_MANAGEMENT_SHARED = {
    '.github/workflows/ci.yml',
    'AGENTS.md',
    'PROJECT_CHARTER.md',
    'database/runtime/manifest.json',
    'docs/mvp-backlog.json',
    'docs/mvp-baseline.md',
    'docs/mvp-delivery-plan.md',
    'docs/mvp-existing-code-assessment.md',
    'docs/mvp03b-user-administration.md',
    'docs/mvp03b1-progress.md',
    'docs/mvp03b1-tenant-role-contract.md',
    'docs/mvp03b2-user-onboarding.md',
    'docs/mvp03b2a-final-validation.md',
    'docs/mvp03b2b-federated-onboarding.md',
    'docs/mvp04-counterparties-contract.md',
    'docs/mvp04-implementation.md',
    'docs/r06-migration-inventory.json',
    'docs/r06-migration-inventory.md',
    'frontend/app/domains/[domain]/page.tsx',
    'frontend/components/shell.tsx',
    'frontend/components/tenant-role-workspace.tsx',
    'frontend/lib/private-backend.ts',
    'frontend/lib/tenant-roles.ts',
    'frontend/next.config.ts',
    'frontend/tests/shell.test.tsx',
    'scripts/run-mvp03b2a-tests.py',
    'scripts/run-mvp03b2b-tests.py',
    'scripts/select-ci-impact.py',
    'scripts/test-mvp03b1-roles.py',
    'scripts/test-mvp03b2b-impact.py',
    'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs',
    'tests/fixtures/nginx.mvp02c.conf',
}
COUNTERPARTY_MANAGEMENT_SHARED |= {"frontend/tests/acceptance.spec.ts", "scripts/test-d97-policy.py", "scripts/test-d98-policy.py", "src/Modules/Counterparties/Enginia360.Counterparties/WorkshopCounterparties.cs"}
COUNTERPARTY_MANAGEMENT_SCOPE = COUNTERPARTY_MANAGEMENT_FILES | COUNTERPARTY_MANAGEMENT_SHARED

CATALOG_MANAGEMENT_FILES = {
    'database/runtime/migrations/0043_catalog_management.sql',
    'src/Modules/Catalog/Enginia360.Catalog/ManagementEndpoints.cs',
    'src/Modules/Catalog/Enginia360.Catalog.Contracts/ManagementContracts.cs',
    'frontend/app/catalog/page.tsx', 'frontend/components/catalog-workspace.tsx',
    'frontend/lib/catalog.ts', 'frontend/tests/catalog.test.tsx',
    'scripts/run-mvp05-tests.py', 'scripts/test-mvp05-catalog.py',
    'scripts/test-mvp05-impact.py', 'scripts/test-mvp05-contract.py',
    'tests/browser/mvp05-catalog.cjs',
    'tests/Enginia360.Api.Tests/CatalogManagementTests.cs',
}
CATALOG_MANAGEMENT_SHARED = COUNTERPARTY_MANAGEMENT_SCOPE | {
    'src/Enginia360.Api/Program.cs', 'scripts/owner-master-authority.py',
    'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs',
    'scripts/run-mvp04-tests.py', 'scripts/test-mvp04-impact.py',
    'tests/browser/mvp04-counterparties.cjs',
    'docs/mvp05-catalog-contract.md', 'docs/mvp05-implementation.md',
    # Exact read-only protected-inventory fixture composition. These runners
    # preserve identity/start/mounts and report unrelated host lifecycle; their
    # standalone/mixed producer selection remains unchanged below.
    'scripts/run-r00a-tests.py', 'scripts/run-r00b-tests.py', 'scripts/test-r00b-lifecycle.py',
    'scripts/run-mvp02a-tests.py', 'scripts/run-mvp02b-tests.py',
    'scripts/run-mvp02c-tests.py', 'scripts/run-mvp03b1-tests.py',
}
CATALOG_MANAGEMENT_SCOPE = CATALOG_MANAGEMENT_FILES | CATALOG_MANAGEMENT_SHARED
CATALOG_MANAGEMENT_DIRECT = {
    'scripts/run-r00b-tests.py',
    'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs',
    'src/Enginia360.Api/Program.cs',
    'src/Modules/Catalog/Enginia360.Catalog.Contracts/Contracts.cs',
    'src/Modules/Catalog/Enginia360.Catalog/MembershipOperation.cs',
    'frontend/lib/private-backend.ts', 'frontend/components/tenant-role-workspace.tsx',
    'src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs',
    'src/Enginia360.Api/BrowserAuthentication/ExternalIdentityResolver.cs',
    'database/runtime/migrations/0039_tenant_roles.sql',
    'database/runtime/migrations/0040_membership_access.sql',
    'database/runtime/migrations/0042_counterparty_management.sql',
    'scripts/owner-master-authority.py', 'tests/fixtures/nginx.mvp02c.conf',
}

DOCUMENT_TYPES_FILES = {
    'database/runtime/migrations/0044_document_types.sql',
    'frontend/app/document-types/page.tsx',
    'frontend/components/document-types-workspace.tsx',
    'frontend/lib/document-types.ts',
    'frontend/tests/document-types.test.tsx',
    'scripts/run-mvp06-tests.py',
    'scripts/test-mvp06-contract.py',
    'scripts/test-mvp06-document-types.py',
    'scripts/test-mvp06-impact.py',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes.Contracts/Contracts.cs',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes.Contracts/Enginia360.DocumentTypes.Contracts.csproj',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes.Contracts/packages.lock.json',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes/DocumentTypesModule.cs',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes/Enginia360.DocumentTypes.csproj',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes/ManagementEndpoints.cs',
    'src/Modules/DocumentTypes/Enginia360.DocumentTypes/packages.lock.json',
    'tests/Enginia360.Api.Tests/DocumentTypeManagementTests.cs',
    'tests/browser/mvp06-document-types.cjs',
}
_DOCUMENT_TYPES_ADDITIONAL_SHARED = {
    'docs/mvp06-document-types-contract.md',
    'docs/mvp06-implementation.md',
    'scripts/run-mvp05-tests.py',
    'scripts/test-mvp03b1-roles.py',
    'scripts/test-mvp05-contract.py',
    'scripts/test-mvp05-impact.py',
    'src/Enginia360.Api/Enginia360.Api.csproj',
    'src/Enginia360.Api/packages.lock.json',
    'tests/Enginia360.Api.Tests/packages.lock.json',
    'tests/browser/mvp05-catalog.cjs',
}
DOCUMENT_TYPES_SHARED = CATALOG_MANAGEMENT_SCOPE | _DOCUMENT_TYPES_ADDITIONAL_SHARED
DOCUMENT_TYPES_SCOPE = DOCUMENT_TYPES_FILES | DOCUMENT_TYPES_SHARED
DOCUMENT_TYPES_DIRECT = {
    'browser.runtime.Dockerfile',
    'compose.mvp02c-test.yaml',
    'frontend/components/shell.tsx',
    'frontend/lib/organization.ts',
    'frontend/next.config.ts',
    'scripts/run-mvp02b-tests.py',
    'src/Enginia360.Api/packages.lock.json',
    'tests/Enginia360.Api.Tests/packages.lock.json',
    'database/runtime/migrations/0039_tenant_roles.sql',
    'database/runtime/migrations/0040_membership_access.sql',
    'database/runtime/migrations/0043_catalog_management.sql',
    'frontend/components/tenant-role-workspace.tsx',
    'frontend/lib/private-backend.ts',
    'scripts/run-r00b-tests.py',
    'src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs',
    'src/Enginia360.Api/BrowserAuthentication/ExternalIdentityResolver.cs',
    'src/Enginia360.Api/Enginia360.Api.csproj',
    'src/Enginia360.Api/Program.cs',
    'tests/fixtures/nginx.mvp02c.conf',
}

DOCUMENTS_FILES = {'frontend/app/documents/page.tsx', 'frontend/tests/documents.test.tsx', 'tests/browser/mvp07-documents-inventory.cjs', 'database/runtime/migrations/0045_documents_inventory.sql', 'scripts/test-mvp07-impact.py', 'src/Modules/Documents/Enginia360.Documents/Contracts.cs', 'tests/Enginia360.Api.Tests/DocumentInventoryTests.cs', 'frontend/lib/documents.ts', 'scripts/test-mvp07-contract.py', 'src/Modules/Documents/Enginia360.Documents/DocumentEndpoints.cs', 'scripts/run-mvp07-tests.py', 'src/Modules/Documents/Enginia360.Documents/DocumentsModule.cs', 'src/Modules/Documents/Enginia360.Documents/Enginia360.Documents.csproj', 'scripts/test-mvp07-documents-inventory.py', 'frontend/components/documents-workspace.tsx', 'src/Modules/Documents/Enginia360.Documents/packages.lock.json'}
DOCUMENTS_SHARED = DOCUMENT_TYPES_SCOPE | {'scripts/test-mvp06-contract.py', 'scripts/run-mvp06-tests.py', 'frontend/lib/tenant-roles.ts', 'tests/browser/mvp05-catalog.cjs', 'docs/mvp07-documents-inventory-contract.md', 'scripts/test-mvp03b1-roles.py', 'scripts/run-mvp03b2a-tests.py', 'scripts/run-mvp03b2b-tests.py', 'scripts/test-mvp06-impact.py', 'docs/mvp07-implementation.md', 'scripts/run-mvp04-tests.py', 'tests/browser/mvp06-document-types.cjs'}
DOCUMENTS_SHARED |= {'frontend/app/page.tsx','frontend/app/layout.tsx','frontend/app/globals.css','tests/browser/mvp04-counterparties.cjs','frontend/tests/shell.test.tsx','frontend/tests/acceptance.spec.ts','docs/foundation/01-glossary-and-domain-boundaries.md'}
DOCUMENTS_SHARED |= {'scripts/test-c00-consistency.py', 'scripts/test-r00-migrations.py'}  # exact D99 register guard; mixed producers retain original consumers
DOCUMENTS_SCOPE = DOCUMENTS_FILES | DOCUMENTS_SHARED
DOCUMENTS_DIRECT = DOCUMENT_TYPES_DIRECT | {'database/runtime/migrations/0044_document_types.sql', 'frontend/lib/tenant-roles.ts'}

DOCUMENTS_DIRECT |= {'frontend/app/globals.css'}

DEVELOPMENT_FILES = {
 'database/runtime/migrations/0046_document_development.sql',
 'scripts/test-mvp08-document-development.py','scripts/test-mvp08-contract.py','scripts/test-mvp08-impact.py',
 'scripts/run-mvp08-tests.py','tests/browser/mvp08-document-development.cjs',
 'tests/Enginia360.Api.Tests/DocumentDevelopmentTests.cs','frontend/tests/document-development.test.tsx',
}
DEVELOPMENT_SHARED = DOCUMENTS_SCOPE | {'docs/mvp08-document-development-contract.md','docs/mvp08-implementation.md','docs/foundation/01a-commercial-document-model.md','scripts/test-mvp07-contract.py','scripts/test-mvp07-impact.py'}
DEVELOPMENT_SCOPE = DEVELOPMENT_FILES | DEVELOPMENT_SHARED
DEVELOPMENT_DIRECT = DOCUMENTS_FILES | DOCUMENTS_DIRECT | DOCUMENT_TYPES_FILES

# MVP09 is a finite composition, not a new business-domain producer.
INTEGRATED_FILES = {
 'scripts/run-mvp09-tests.py','scripts/run-mvp09-architecture.py',
 'scripts/test-mvp09-contract.py','scripts/test-mvp09-impact.py',
 'tests/browser/mvp09-integrated-acceptance.cjs',
}
INTEGRATED_SHARED = DEVELOPMENT_SCOPE | {
 'docs/mvp09-integrated-acceptance-contract.md','docs/mvp09-implementation.md',
 'docs/mvp09-cleanup-trace.md','docs/mvp09-final-acceptance.md',
 'docs/archive/mvp08-checkpoints.md',
 'scripts/test-mvp08-contract.py','scripts/test-mvp06-contract.py',
 'scripts/test-mvp07-contract.py',
}
INTEGRATED_SCOPE = INTEGRATED_FILES | INTEGRATED_SHARED
INTEGRATED_DIRECT = DEVELOPMENT_FILES | DEVELOPMENT_DIRECT | {
 'scripts/run-mvp02b-tests.py','scripts/run-r00b-tests.py',
 'src/Enginia360.Api/BrowserAuthentication/PendingOnboarding.cs',
 'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs',
 'frontend/components/tenant-role-workspace.tsx','frontend/components/shell.tsx',
 'frontend/lib/private-backend.ts',
}

def _selection(paths):
    paths = sorted(set(paths))
    if set(paths) & INTEGRATED_FILES:
        remaining = set(paths) - INTEGRATED_FILES
        if set(paths) <= INTEGRATED_SCOPE:
            remaining -= INTEGRATED_SHARED
        result = selection(sorted(remaining | {'scripts/test-mvp08-impact.py'}))
        result.update(changed_paths=paths, integrated_acceptance=True)
        return result
    if set(paths) & DEVELOPMENT_FILES:
        remaining = set(paths) - DEVELOPMENT_FILES
        if set(paths) <= DEVELOPMENT_SCOPE:
            remaining -= DEVELOPMENT_SHARED
        result = selection(sorted(remaining | {'scripts/test-mvp07-impact.py'}))
        result.update(changed_paths=paths,document_development=True,documents=True,document_types=True,frontend=True,migrations=True,browser=True,tenant_roles=True,membership_access=True)
        token='FullyQualifiedName~DocumentDevelopmentTests'
        if token not in result['api_filter'].split('|'):result['api_filter']+=('|' if result['api_filter'] else '')+token
        return result
    if set(paths) & DOCUMENTS_FILES:
        remaining = set(paths) - DOCUMENTS_FILES
        if set(paths) <= DOCUMENTS_SCOPE:
            remaining -= DOCUMENTS_SHARED
        result = selection(sorted(remaining | {'scripts/test-mvp06-impact.py'}))
        result.update(changed_paths=paths, documents=True, document_types=True, frontend=True,
                      migrations=True, browser=True, tenant_roles=True,
                      membership_access=True, catalog_management=True, counterparty_management=True,
                      federated_onboarding=True, authenticated_organization=True)
        for name in ('DocumentInventoryTests','DocumentTypeManagementTests','BusinessMembershipFenceTests'):
            token='FullyQualifiedName~'+name
            if token not in result['api_filter'].split('|'):
                result['api_filter'] += ('|' if result['api_filter'] else '')+token
        return result
    if set(paths) & DOCUMENT_TYPES_FILES:
        remaining = set(paths) - DOCUMENT_TYPES_FILES
        if set(paths) <= DOCUMENT_TYPES_SCOPE:
            remaining -= DOCUMENT_TYPES_SHARED
        result = selection(sorted(remaining | {'scripts/test-mvp05-impact.py'}))
        result.update(changed_paths=paths, document_types=True, frontend=True,
                      migrations=True, browser=True, tenant_roles=True,
                      membership_access=True, counterparty_management=True,
                      catalog_management=True, federated_onboarding=True,
                      authenticated_organization=True)
        for name in ('DocumentTypeManagementTests','BusinessMembershipFenceTests'):
            token='FullyQualifiedName~'+name
            if token not in result['api_filter'].split('|'):
                result['api_filter'] += ('|' if result['api_filter'] else '')+token
        return result
    if set(paths) & CATALOG_MANAGEMENT_FILES:
        remaining = set(paths) - CATALOG_MANAGEMENT_FILES
        finite = set(paths) <= CATALOG_MANAGEMENT_SCOPE
        if finite:
            remaining -= CATALOG_MANAGEMENT_SHARED
        # Direct producer consumers remain mandatory. Mixed unrelated producers
        # recursively retain their original selection; no prefix exemptions.
        result = selection(sorted(remaining | {'scripts/test-mvp04-impact.py'}))
        result.update(changed_paths=paths, catalog_management=True, frontend=True,
                      migrations=True, browser=True, tenant_roles=True,
                      membership_access=True, counterparty_management=True,
                      federated_onboarding=True, authenticated_organization=True)
        for name in ('CatalogManagementTests','BusinessMembershipFenceTests','SupplierPurchasePriceTests','WorkshopBoundaryTests','CommercialCalculationTests','CounterpartyArchitectureTests'):
            token='FullyQualifiedName~'+name
            if token not in result['api_filter'].split('|'):
                result['api_filter'] += ('|' if result['api_filter'] else '')+token
        return result
    if set(paths) & COUNTERPARTY_MANAGEMENT_FILES:
        remaining = set(paths) - COUNTERPARTY_MANAGEMENT_FILES
        finite = set(paths) <= COUNTERPARTY_MANAGEMENT_SCOPE
        if finite:
            remaining -= COUNTERPARTY_MANAGEMENT_SHARED
        # Finite new composition plus its actual identity/role/access consumers.
        # A mixed unrelated producer is still recursively selected in full.
        result = selection(sorted(remaining | {'scripts/test-mvp03b2b-impact.py','scripts/test-mvp03b1-impact.py'}))
        result.update(changed_paths=paths,counterparty_management=True,frontend=True,browser=True,migrations=True,
                      tenant_roles=True,membership_access=True,federated_onboarding=True,authenticated_organization=True)
        return result
    if set(paths) & FEDERATED_ONBOARDING_FILES:
        result = selection(sorted(set(paths) - FEDERATED_ONBOARDING_FILES))
        result.update(changed_paths=paths, federated_onboarding=True, browser=True, migrations=True, frontend=True)
        return result
    if set(paths) & MEMBERSHIP_ACCESS_FILES:
        result = selection(sorted(set(paths) - MEMBERSHIP_ACCESS_FILES))
        result.update(changed_paths=paths, membership_access=True, browser=True, migrations=True, frontend=True)
        return result
    if set(paths) & D98_FILES:
        remaining = set(paths) - D98_FILES
        if set(paths) <= D98_SCOPE:
            remaining -= D98_SCOPE
        result = selection(sorted(remaining))
        result.update(changed_paths=paths, mvp_offline=True)
        return result
    if set(paths) & TENANT_ROLE_FILES:
        remaining = set(paths) - TENANT_ROLE_FILES
        finite = set(paths) <= TENANT_ROLE_SCOPE
        if finite:
            remaining -= TENANT_ROLE_SCOPE
        result = selection(sorted(remaining | {'scripts/test-mvp02b-impact.py', 'scripts/test-mvp01-impact.py'}))
        result.update(changed_paths=paths, tenant_roles=True, authenticated_organization=True,
                      platform_foundation_only=finite)
        return result
    if set(paths) & D97_FILES:
        remaining = set(paths) - D97_FILES
        if set(paths) <= D97_SCOPE:
            remaining -= {'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}
        result = selection(sorted(remaining))
        result.update(changed_paths=paths, mvp_offline=True)
        return result
    if set(paths) & AUTHENTICATED_ORGANIZATION_FILES:
        remaining = set(paths) - AUTHENTICATED_ORGANIZATION_FILES
        if remaining <= FRONTEND_FILES | FRONTEND_WIRING | FRONTEND_CHECKPOINTS:
            remaining -= FRONTEND_WIRING
        result = selection(sorted(remaining | {'scripts/test-mvp02b-impact.py', 'scripts/test-mvp01-impact.py'}))
        result.update(changed_paths=paths, authenticated_organization=True)
        if set(paths) <= AUTHENTICATED_ORGANIZATION_FILES | FRONTEND_FILES | FRONTEND_WIRING | FRONTEND_CHECKPOINTS:
            result['platform_foundation_only'] = True
        return result
    if set(paths) & ORGANIZATION_FILES:
        remaining = set(paths) - ORGANIZATION_FILES
        finite = remaining <= ORGANIZATION_WIRING | FRONTEND_FILES
        if finite:
            remaining -= ORGANIZATION_WIRING
        result = selection(sorted(remaining | {'scripts/test-mvp02a-impact.py'}))
        result.update(changed_paths=paths, organization_administration=True,
                      platform_foundation_only=finite)
        return result
    platform = bool(set(paths) & PLATFORM_FILES)
    if platform:
        remaining = set(paths) - PLATFORM_FILES
        if remaining <= PLATFORM_WIRING:
            remaining -= PLATFORM_WIRING
        result = selection(sorted(remaining))
        result.update(changed_paths=paths, platform_authority=True, browser=True, migrations=True,
                      mvp_offline=True,
                      platform_foundation_only=set(paths) <= PLATFORM_FILES | PLATFORM_WIRING)
        if result['platform_foundation_only']:
            # Dedicated inventory/readiness checks replace no unrelated ERP policy suite.
            result['r06_offline'] = False
        if not result['api_filter']:
            result['api_filter'] = AUTH_FILTER
        return result
    frontend = bool(set(paths) & FRONTEND_FILES)
    if frontend:
        remaining = set(paths) - FRONTEND_FILES
        # Only this bounded shell + wiring + status checkpoint may avoid the
        # historical runtime wiring consumers. Mixed real producers never do.
        if remaining <= FRONTEND_WIRING | FRONTEND_CHECKPOINTS:
            remaining -= FRONTEND_WIRING
        result = selection(sorted(remaining))
        result.update(changed_paths=paths, frontend=True)
        return result
    mvp_offline = bool(set(paths) & MVP_ANCHORS)
    if mvp_offline and set(paths) <= MVP_OFFLINE_FILES:
        result = selection([])
        result.update(changed_paths=paths, mvp_offline=True)
        return result
    r06a2 = bool(set(paths) & (R06A2_FILES | R06A2_DEPENDENCIES))
    staging_only = r06a2 and set(paths) <= R06A2_FILES | R06_OFFLINE_FILES | R06_WIRING | {'docs/r06a2-synthetic-import-export.md'}
    r05a8_offline = bool(set(paths) & R05A8_OFFLINE_FILES)
    r05a8_only = r05a8_offline and set(paths) <= R05A8_OFFLINE_FILES | R06_OFFLINE_FILES | R06_WIRING
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
    r04b2b3 = bool(set(paths) & (R04B2B3_FILES | R04B2B3_DIRECT | R04B2B3_READOUT))
    if r04b2b3: auth = ui = ui01b = r06_offline = True
    unknown = []
    for path in paths:
        parsed = PurePosixPath(path)
        if not path or parsed.is_absolute() or '..' in parsed.parts or '\\' in path or str(parsed) != path:
            raise ValueError('invalid changed path')
        if path in MVP_GUARDS:
            continue
        if path in R04B2B3_FILES or path in R04B2B3_DIRECT:
            if path.startswith('src/Modules/Integrations/'): r03c = r03c_full = r03a = r05b1 = True
            continue
        if path in R04B2B2_FILES or path in R04B2A_FILES or path in R04B2B1_FILES or path == 'src/Modules/Catalog/Enginia360.Catalog/Enginia360.Catalog.csproj':
            continue
        if path in R06A2_FILES or (staging_only and path in R06_WIRING):
            continue
        if path in R05A8_OFFLINE_FILES or (r05a8_only and path in R06_WIRING):
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
                'src/Enginia360.Api/OrganizationAccess/','database/runtime/','tests/browser/'))
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
    if set(paths) & R04B2B3_FILES and set(paths) <= R04B2B3_SCOPE and set(paths) & {'web/src/ui01/runtime/MaterialOperations.tsx','web/src/ui01/runtime/MaterialOperations.test.tsx'}:
        # The receiving freeze is composed into the existing material siblings: execute their real regressions.
        for key in ('r04a','r04c1','r04c2'):
            result[key] = True
    # Earlier bounded producer slices may replace their API filter; never discard an already selected purchase consumer.
    if result['r04b2b3']:
        for consumer in ('GiobbyReceiptTests','GiobbyPurchaseOrderTests','GiobbySalesOrderTests','AdministrationBoundaryTests'):
            if consumer not in result['api_filter']:
                result['api_filter'] += '|FullyQualifiedName~'+consumer
    if set(paths) & D95_FILES and set(paths) <= D95_SCOPE:
        # Only the bounded offline projector and its existing read/role consumers, not D76 ingestion.
        for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r06b1','r06a2','r05b0','r05b1','r04b2b1','r04b2b2','r04b2b3'):
            result[key] = False
        for key in ('browser','migrations','ui01b','r04b2a','ui_build','ui_tests','r06_offline'):
            result[key] = True
        result['api_filter'] = AUTH_FILTER+'|'+WORKSHOP_FILTER+'|FullyQualifiedName~InventoryArchitectureTests|FullyQualifiedName~PurchaseIntentTests|FullyQualifiedName~SupplierPurchasePriceTests'
    result['r05a8_offline'] = r05a8_offline
    result['mvp_offline'] = mvp_offline
    return result



def selection(paths):
    # Historical browser-prefix mapping is not authority for new MVP09 fixtures.
    unknown_integrated = [path for path in paths if path.startswith('tests/browser/mvp09-') and path not in INTEGRATED_FILES]
    if unknown_integrated:
        raise ValueError('extend and test direct-dependency impact mapping for: '+', '.join(unknown_integrated))
    # Add the new direct consumer without suppressing any existing producer flags.
    result = _selection(paths)
    if set(paths) & AUTHENTICATED_ORGANIZATION_DIRECT:
        result['authenticated_organization'] = True
    if set(paths) & TENANT_ROLE_DIRECT:
        result['tenant_roles'] = True
    if set(paths) & MEMBERSHIP_ACCESS_DIRECT:
        result['membership_access'] = True
        consumers = ['MembershipAccessTests','CounterpartyMembershipFenceTests','WorkshopMembershipFenceTests','BusinessMembershipFenceTests','RuntimeMigrationPoolTests']
        # Keep each historical producer's own filter above. Only the new shared
        # fence and newly mapped owning contexts need this cross-domain expansion;
        # a Vehicles/Catalog/browser-only edit must not select unrelated accounting.
        shared_owning = MEMBERSHIP_ACCESS_FILES | {
            'src/Modules/Billing/Enginia360.Billing/BillingDbContext.cs',
            'src/Modules/Billing/Enginia360.Billing/ConfirmedInvoices.cs',
            'src/Modules/Accounting/Enginia360.Accounting/AccountingDbContext.cs',
            'src/Modules/Accounting/Enginia360.Accounting/AccountingModule.cs',
            'src/Modules/Counterparties/Enginia360.Counterparties/Infrastructure/CounterpartiesDbContext.cs',
        }
        if set(paths) & shared_owning:
            consumers += ['AuthorizedContextContractTests','LimitedGrantAdministrationTests','WorkshopBoundaryTests','AdministrationBoundaryTests','BillingBoundaryTests','AccountingBoundaryTests','PurchaseIntentTests','SupplierPurchasePriceTests']
        for consumer in consumers:
            token='FullyQualifiedName~'+consumer
            if token not in result['api_filter'].split('|'):
                result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('membership_access',False)
    if set(paths) & (FEDERATED_ONBOARDING_FILES | FEDERATED_ONBOARDING_DIRECT):
        result['federated_onboarding'] = True
        result['frontend'] = True
        token='FullyQualifiedName~FederatedOnboardingTests'
        if token not in result['api_filter'].split('|'):
            result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('federated_onboarding',False)
    if set(paths) & (COUNTERPARTY_MANAGEMENT_FILES | {'frontend/components/tenant-role-workspace.tsx','frontend/lib/tenant-roles.ts','frontend/lib/private-backend.ts','src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs'}):
        result['counterparty_management'] = True
        token='FullyQualifiedName~CounterpartyManagementTests'
        if token not in result['api_filter'].split('|'): result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('counterparty_management',False)
    if set(paths) & (CATALOG_MANAGEMENT_FILES | CATALOG_MANAGEMENT_DIRECT):
        result['catalog_management'] = True
        for name in ('CatalogManagementTests','SupplierPurchasePriceTests','BusinessMembershipFenceTests'):
            token='FullyQualifiedName~'+name
            if token not in result['api_filter'].split('|'): result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('catalog_management',False)
    if set(paths) & (DOCUMENT_TYPES_FILES | DOCUMENT_TYPES_DIRECT):
        result['document_types'] = True
        token='FullyQualifiedName~DocumentTypeManagementTests'
        if token not in result['api_filter'].split('|'): result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('document_types',False)
    if set(paths) & (DOCUMENTS_FILES | DOCUMENTS_DIRECT):
        result['documents'] = True
        token='FullyQualifiedName~DocumentInventoryTests'
        if token not in result['api_filter'].split('|'): result['api_filter'] += ('|' if result['api_filter'] else '')+token
    result.setdefault('documents',False)
    if set(paths) & (DEVELOPMENT_FILES | DEVELOPMENT_DIRECT):
        result['document_development']=True
        token='FullyQualifiedName~DocumentDevelopmentTests'
        if token not in result['api_filter'].split('|'):result['api_filter']+=('|' if result['api_filter'] else '')+token
    result.setdefault('document_development',False)
    if set(paths) & INTEGRATED_DIRECT:
        result['integrated_acceptance'] = True
    result.setdefault('integrated_acceptance',False)
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
