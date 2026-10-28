#!/usr/bin/env python3
"""D91/D92 isolated real quote/freeze acceptance, no provider traffic."""
import importlib.util
import json
from pathlib import Path
import re
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prices',ROOT/'scripts/run-r04b2b1-tests.py');assert spec and spec.loader
prices=importlib.util.module_from_spec(spec);spec.loader.exec_module(prices)
binding=prices.binding
binding.SPEC='r04b2b2-acceptance.cjs'
binding.r00.CONFIG=ROOT/'compose.r04b2b2-test.yaml'
def control(action,state,query,fixture,holders):
 if not action.startswith('freeze-'):return prices.control(action,state,query,fixture,holders)
 ctx=fixture['contexts'][0];t,c=ctx['tenantId'],ctx['legalEntityId'];m=fixture['adminMembershipId'];s=fixture['purchasePrices']['supplierId'];item=fixture['purchasePrices']['catalogItemId']
 def sql(text):return binding.run(query+['-c',text]).strip()
 if action.startswith('freeze-list:'):
  price=action.split(':')[1];assert re.fullmatch(r'[0-9]{1,6}(\.[0-9]{1,6})?',price)
  sql(f'''BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('master-authority:{t}',0));
   INSERT INTO catalog.supplier_purchase_price_history("CommandId","TenantId","LegalEntityId","SupplierId","CatalogItemId","Revision","UnitPurchasePrice","ActorMembershipId","SupplierRevision","CatalogVersion","AuthorityVersion","Payload") SELECT '{uuid.uuid4()}','{t}','{c}','{s}','{item}',coalesce(max("Revision"),0)+1,'{price}','{m}',0,8,1,'{{}}' FROM catalog.supplier_purchase_price_history WHERE "TenantId"='{t}' AND "LegalEntityId"='{c}' AND "SupplierId"='{s}' AND "CatalogItemId"='{item}'; COMMIT;''')
 elif action.startswith('freeze-row:'):
  command=str(uuid.UUID(action.split(':')[1]))
  (state/'control/freeze-row.json').write_text(sql(f'''SELECT to_jsonb(p)||jsonb_build_object('AcceptedUnitPurchasePrice',"AcceptedUnitPurchasePrice"::text) FROM inventory.purchase_intent_prices p WHERE "IntentId"='{command}';'''))
 elif action=='freeze-counts':
  (state/'control/freeze-counts.json').write_text(sql('''SELECT json_build_object('intents',(SELECT count(*) FROM inventory.purchase_intents),'prices',(SELECT count(*) FROM inventory.purchase_intent_prices),'outbox',(SELECT count(*) FROM inventory.purchase_intent_outbox),'sales',(SELECT count(*) FROM workshop.administrative_outbox))'''))
 elif action=='freeze-capture-layout':
  import os,shutil
  target=Path(os.environ['TMPDIR'])/'r04b2b2-logs'/('evidence-pool'+binding.POOL);target.mkdir(parents=True,exist_ok=True)
  for image in (state/'control').glob('freeze-layout-*.png'):shutil.copyfile(image,target/image.name)
 else:raise ValueError('unknown frozen-price fixture control')
 return True
binding.EXTRA_CONTROL=control
if __name__=='__main__':binding.main()
