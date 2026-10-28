#!/usr/bin/env python3
"""R04.b.2a isolated TLS/OIDC/Chromium/API/PostgreSQL acceptance over the established R05 binding primitives.

Synthetic only: coherent local shared master + external Giobby stock/purchasing profile (D82/D88). The Giobby fake is
present solely to prove it receives no purchase traffic; there is no purchasing HTTP writer in this sub-slice."""
import importlib.util
import json
import os
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


sales = load('sales_order', 'scripts/run-r05b1-tests.py')
binding = sales.binding
binding.SPEC = 'r04b2a-acceptance.cjs'
binding.r00.CONFIG = ROOT/'compose.r04b2a-test.yaml'
original_r03b = binding.r03b.fixtures
# D82: the purchasing chain and stock share the external ERP; the local stock profile is never set here.
binding.r03b.fixtures = lambda state, secret, stock_setup=False: original_r03b(state, secret, stock_setup=False)
base = binding.fixtures


def fixtures(state, secret):
    sql = base(state, secret)
    browser = json.loads((state/'browser.json').read_text())
    ctx, member = browser['contexts'][0], browser['adminMembershipId']
    t, c, s, w = ctx['tenantId'], ctx['legalEntityId'], ctx['siteId'], ctx['warehouseId']
    stock_source, stock_profile, master_source, master_profile = [str(uuid.uuid4()) for _ in range(4)]
    supplier, unmapped, plain = [str(uuid.uuid4()) for _ in range(3)]
    host = json.loads((state/'giobby.json').read_text())
    host['ExternalAdministration']['Giobby'].update(PurchaseStockSourceId=stock_source, PurchaseStockProfileId=stock_profile)
    (state/'giobby.json').write_text(json.dumps(host))
    (state/'purchase-fixture.json').write_text(json.dumps(dict(supplier=supplier, unmapped=unmapped, plain=plain, stockSource=stock_source, stockProfile=stock_profile)))
    proof = str(uuid.uuid4())
    sql += f"""
SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{t}',true);
SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}','{member}','{proof}','ExternalToEnginia360','{stock_source}','{stock_profile}');
SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{t}','{member}','{proof}',0,'Enginia360ToExternal','{master_source}','{master_profile}',ARRAY(SELECT "Id" FROM organization_access.legal_entities WHERE "TenantId"='{t}'));
COMMIT; RESET ROLE;
INSERT INTO counterparties.counterparties VALUES ('{supplier}','{t}','Fornitore sintetico','SYNTH-SUP','Synthetic office'),('{unmapped}','{t}','Fornitore non mappato','SYNTH-UNM','Synthetic office'),('{plain}','{t}','Non fornitore','SYNTH-PLN','Synthetic office');
UPDATE counterparties.counterparties SET "IsSupplier"=true WHERE "Id" IN ('{supplier}','{unmapped}');
INSERT INTO counterparties.giobby_vendor_identity_history("CommandId","TenantId","LegalEntityId","CounterpartyId","Revision","VendorId","VendorName","ActorMembershipId","VerificationReference")
 VALUES ('{uuid.uuid4()}','{t}','{c}','{supplier}',1,'GBV-4711','Synthetic Supplier S.r.l.','{member}','{proof}');
INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{member}','{t}','{c}','inventory.purchase-intents.create','{s}','{w}'),('{uuid.uuid4()}','{member}','{t}','{c}','inventory.reservations.read','{s}','{w}');
"""
    return sql


binding.fixtures = fixtures
if __name__ == '__main__':
    binding.main()
