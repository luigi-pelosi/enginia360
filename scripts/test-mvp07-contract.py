#!/usr/bin/env python3
"""MVP07 source/decision preservation guards, to execute only in final validation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='6ca378d94435eb78ff4955128e3646cc64ef1ece'
CURRENT=('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp-existing-code-assessment.md')
TABLES={'documents.'+t for t in ('headers','lines','versions','policy_versions','balances','ledger','command_audit','snapshot_fence')}
def original(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def current_status(root):
 items={i['id']:i for i in json.loads((root/'docs/mvp-backlog.json').read_text())['items']}
 before=items['MVP-06'];now=items['MVP-07']
 assert (before['status'],before['runtimeDelivered'],before['pr'],before['mergedMain'],before['prCi'],before['runtimeDispatch'])==('done',True,170,BASE,41881635998,41881398306)
 assert (now['status'],now['runtimeDelivered'],now['pr'],now['mergedMain'],now['prCi'],now['runtimeDispatch'])==('done',True,171,'7d505db049880ef6fc4a2307dcd4575165c08923',41945630168,41945650853)
 assert now['negativeStockPolicy']==dict(decision='D99',ownerAnswer='Configurabile per società, con blocco predefinito',scope='company',defaultAllowNegative=False)
 assert items['MVP-08']['status']=='done' and items['MVP-08']['runtimeDelivered'] is True
 assert items['MVP-09']['status']=='done' and items['MVP-09']['runtimeDelivered'] is True
 assert items['MVP-09']['pr']==173 and items['MVP-09']['finalMvpRun']==42194906237
 assert items['MVP-10']['status']=='in_progress' and items['MVP-10']['operationalReady'] is False
 for path in CURRENT:
  text=(root/path).read_text()
  for token in ('7d505db049880ef6fc4a2307dcd4575165c08923','41945630168','41945650853','5a58e881d71e5d4b12fdb42ea1829d49790b7e0e'):
   assert token in text,(path,token)
 for path in CURRENT[:-1]:
  text=(root/path).read_text();start='<!-- d99-current:start -->';end='<!-- d99-current:end -->'
  assert text.count(start)==text.count(end)==1
  block=text.split(start)[1].split(end)[0]
  for token in ('D99:','Configurabile per società, con blocco predefinito','versionata','audit immutabile','D34','ERP'):assert token in block,(path,token)
class ContractTests(unittest.TestCase):
 def test_all44_published_sql_and_every_previous_inventory_entry_unchanged(self):
  before=json.loads(original('database/runtime/manifest.json'));after=json.loads((ROOT/'database/runtime/manifest.json').read_text())
  self.assertEqual(len(before),44);self.assertEqual(after[:44],before);self.assertEqual(len(after),46);self.assertEqual(after[44]['id'],'0045_documents_inventory');self.assertEqual(after[45]['id'],'0046_document_development')
  for row in before:
   path='database/runtime/'+row['path'];self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  old=json.loads(original('docs/r06-migration-inventory.json'));new=json.loads((ROOT/'docs/r06-migration-inventory.json').read_text());self.assertEqual(new[:len(old)],old);self.assertEqual({r['table'] for r in new[len(old):]},TABLES|{'document_types.passages','document_types.passage_versions','documents.origins'})
  spec=importlib.util.spec_from_file_location('inventory',ROOT/'scripts/r06_inventory.py');assert spec and spec.loader
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.verify(ROOT,new)
 def test_first_boot_retains_every_original_assertion_with_one_exact_new_technical_witness(self):
  path='scripts/test-r00-migrations.py';before=original(path).decode();after=(ROOT/path).read_text()
  changed="if table in ('organization_access.membership_access_snapshot_fence', 'documents.snapshot_fence'):"
  self.assertEqual(after.count(changed),1)
  normalized=after.replace(changed,"if table == 'organization_access.membership_access_snapshot_fence':")
  self.assertEqual(normalized,before,'only the exact new technical singleton exception is allowed; all inventory, zero-row, RLS and noop assertions remain byte-exact')
 def test_private_browser_first_boot_preserves_all_other_zero_row_and_security_guards(self):
  path='scripts/run-r00b-tests.py';before=original(path).decode();after=(ROOT/path).read_text()
  extra="            assert run(query+['-c','SELECT row_to_json(f) FROM documents.snapshot_fence f']).strip() == '{\"Singleton\":true,\"Token\":false}'\n            assert run(query+['-c','SELECT count(*) FROM documents.snapshot_fence']).strip() == '1'\n"
  self.assertEqual(after.count(extra),1)
  normalized=after.replace(extra,'').replace('# Only the two named rows are private technical MVCC witnesses, not','# The only seeded row is the private technical MVCC witness, not').replace("(schemaname,tablename) NOT IN (('organization_access','membership_access_snapshot_fence'),('documents','snapshot_fence'))","(schemaname,tablename)<>('organization_access','membership_access_snapshot_fence')")
  self.assertEqual(normalized,before,'only the named exact new technical witness can differ; no schema-wide emptiness waiver or security/lifecycle change')
 def test_historical_inventory_workshop_billing_integrations_and_canonical_catalog_unmodified(self):
  for directory in ('src/Modules/Inventory','src/Modules/Workshop','src/Modules/Billing','src/Modules/Integrations','src/Modules/Catalog','src/Modules/DocumentTypes'):
   for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,directory],cwd=ROOT,text=True).splitlines():
    if path in {'src/Modules/DocumentTypes/Enginia360.DocumentTypes/ManagementEndpoints.cs','src/Modules/DocumentTypes/Enginia360.DocumentTypes.Contracts/Contracts.cs'}:continue  # MVP08 finite path command ingress
    self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  sql=(ROOT/'database/runtime/migrations/0045_documents_inventory.sql').read_text()
  for bad in ('INSERT INTO inventory.','UPDATE inventory.','INSERT INTO workshop.','UPDATE catalog.items','GRANT ALL','DISABLE ROW LEVEL SECURITY'):
   self.assertNotIn(bad,sql)
  for required in ('catalog.document_item','catalog.document_choices','document_types.for_document','document_types.document_choices','SECURITY DEFINER SET search_path=pg_catalog','FORCE ROW LEVEL SECURITY','pg_advisory_xact_lock(777036)','current_membership_access(NULL)','current_tenant_role_scopes_before_access()','snapshot_fence','ORDER BY warehouse,item_id','current_balance-pool.outgoing<0','previous."Request"=request','previous."After"','quantity_overflow','insufficient_stock','already_confirmed','config_changed'):
   self.assertIn(required,sql)
  self.assertLess(sql.index("organization_access.document_permission('documents.read',company,site,NULL)"),sql.index('SELECT * INTO previous FROM documents.command_audit'))
 def test_d99_is_one_new_decision_with_exact_answer_and_literal_d97_d98_history(self):
  register=(ROOT/'docs/foundation/01-glossary-and-domain-boundaries.md').read_bytes();self.assertTrue(register.startswith(original('docs/foundation/01-glossary-and-domain-boundaries.md')))
  self.assertEqual(register.count('### D99 —'.encode()),1)
  self.assertIn('«Nel nuovo inventario, con 2 pezzi in giacenza e un documento che ne scarica 3, quale regola deve valere alla conferma?»'.encode(),register)
  self.assertIn('«Configurabile per società, con blocco predefinito»'.encode(),register)
  for path in CURRENT:
   old=original(path).decode();new=(ROOT/path).read_text()
   for decision in ('d97','d98'):
    start=f'<!-- {decision}-current:start -->';end=f'<!-- {decision}-current:end -->'
    if start in old:self.assertEqual(old.split(start)[1].split(end)[0],new.split(start)[1].split(end)[0])
 def test_current_summary_and_negative_mutations(self):
  current_status(ROOT)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for path in (*CURRENT,'docs/mvp-backlog.json'):
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/path).read_bytes())
   for path in CURRENT:
    p=root/path;text=p.read_text()
    for token in ('41945630168','41945650853','7d505db049880ef6fc4a2307dcd4575165c08923'):
     p.write_text(text.replace(token,'REMOVED'))
     with self.assertRaises(AssertionError):current_status(root)
     p.write_text(text)
   p=root/'docs/mvp-backlog.json';text=p.read_text()
   for id,key,value in [('MVP-06','runtimeDelivered',False),('MVP-07','status','in_progress'),('MVP-07','runtimeDelivered',False),('MVP-07','prCi',0),('MVP-08','status','in_progress')]:
    data=json.loads(text);next(i for i in data['items'] if i['id']==id)[key]=value;p.write_text(json.dumps(data))
    with self.assertRaises(AssertionError):current_status(root)
    p.write_text(text)
 def test_external_package_hashes_pins_and_only_actual_new_project_edges(self):
  for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines():
   if path.endswith('packages.lock.json'):
    before=json.loads(original(path));after=json.loads((ROOT/path).read_text())
    for framework,packages in before['dependencies'].items():
     for name,package in packages.items():
      if package['type']!='Project':self.assertEqual(after['dependencies'][framework][name],package,(path,name))
   elif path.endswith(('package-lock.json','Dockerfile')):self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  for path in ('src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json'):
   self.assertIn('enginia360.documents',json.loads((ROOT/path).read_text())['dependencies']['net10.0'])
 def test_real_sources_cover_entire_document_and_policy_journey_not_backend_stub(self):
  ui=(ROOT/'frontend/components/documents-workspace.tsx').read_text();api=(ROOT/'src/Modules/Documents/Enginia360.Documents/DocumentEndpoints.cs').read_text();page=(ROOT/'frontend/app/documents/page.tsx').read_text();browser=(ROOT/'tests/browser/mvp07-documents-inventory.cjs').read_text()
  for token in ('Società autorizzata','Sede autorizzata','Nuovo documento','Salva bozza','Conferma documento e applica quantità','Quantità per magazzino','Movimenti e provenienza','Consenti quantità negative','command.body','fence.current','stopImmediatePropagation','disabled={locked','inputMode="decimal"','expectedTypeRevision','expectedPolicyRevision'):
   self.assertIn(token,ui)
  for bad in ('parseFloat(', 'parseInt(line.quantity','Number(line.quantity','maxLength'):self.assertNotIn(bad,ui)
  for token in ('RequireAuthorization()','ValidJson','262145','MaxDepth = 6','BeginTransactionAsync','enginia360:verified-issuer','enginia360:external-subject','await tx.CommitAsync'):self.assertIn(token,api)
  for token in ('force-dynamic','revalidate = 0','Array.isArray(value)','finiteDocumentsRead','privateRead'):self.assertIn(token,page)
  ingress=(ROOT/'tests/fixtures/nginx.mvp02c.conf').read_text()
  self.assertIn('~^/documents(?:/|$) "private, no-store";',ingress)
  for token in ('javaScriptEnabled:false','width:390','width:1366','width:1920','page-*.js','csrf_invalid','new Set(bodies).size,1','runtime-bearer-proof','documents-readback'):self.assertIn(token,browser)
 def test_d97_prior_role_algorithm_is_byte_exact_after_removing_only_new_scope_branches(self):
  old=original('database/runtime/migrations/0044_document_types.sql').decode();new=(ROOT/'database/runtime/migrations/0045_documents_inventory.sql').read_text()
  start='CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role';end='REVOKE ALL ON FUNCTION organization_access.apply_tenant_role(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";'
  before=old[old.index(start):old.index(end)+len(end)];after=new[new.index(start):new.index(end)+len(end)]
  first=after.index("  ELSIF request->>'action' IN ('documents.read'")
  last=after.index("  ELSIF request->>'action' IN ('counterparties.extensions.read'",first)
  inserted=after[first:last]
  for token in ("'documents.read','documents.save','documents.confirm'","'inventory.document-effects.apply','inventory.quantities.read'",'organization_access.sites','organization_access.warehouses',"request->'warehouseId'<>'null'::jsonb","request->'warehouseId'='null'::jsonb"):
   self.assertIn(token,inserted)
  normalized=(after[:first]+after[last:]).replace(",'inventory.policy.read','inventory.policy.manage'",'')
  self.assertEqual(normalized,before)
if __name__=='__main__':unittest.main()
