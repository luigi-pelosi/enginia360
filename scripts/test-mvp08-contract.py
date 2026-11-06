#!/usr/bin/env python3
"""Final-phase MVP08 decision/immutability/source contract guards. NOT executed in source phase."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='7d505db049880ef6fc4a2307dcd4575165c08923'
CURRENT=('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/foundation/01a-commercial-document-model.md','docs/foundation/01-glossary-and-domain-boundaries.md','docs/mvp08-document-development-contract.md')
ANSWERS={'d100':'La quantità viene prenotata alla conferma della bozza','d101':'Usare soltanto sorgenti confermate, anche di tipi diversi se tutti abilitati verso la destinazione'}
def original(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def decisions(root):
 for rel in CURRENT:
  text=(root/rel).read_text()
  for id,answer in ANSWERS.items():
   start=f'<!-- {id}-current:start -->';end=f'<!-- {id}-current:end -->'
   assert text.count(start)==text.count(end)==1,(rel,id)
   block=text.split(start)[1].split(end)[0]
   assert id.upper()+':' in block and '«'+answer+'»' in block,(rel,id)
   for token in (('Draft','atomicamente','409','Non è una prenotazione fisica') if id=='d100' else ('Confirmed','Tipi sorgente differenti','D14/D17','solo societario')):assert token in block,(rel,token)
def current_status(root):
 items={i['id']:i for i in json.loads((root/'docs/mvp-backlog.json').read_text())['items']}
 assert items['MVP-07']['status']=='done' and items['MVP-07']['pr']==171 and items['MVP-07']['mergedMain']==BASE
 now=items['MVP-08'];assert now['status']=='done' and now['runtimeDelivered'] is True
 assert now['developmentPolicy']=={'commitDecision':'D100','commitAt':'destination_confirmation','sourcesDecision':'D101','confirmedSourcesOnly':True,'mixedSourceTypesIfEveryPathEnabled':True,'draftReservesCapacity':False}
 assert items['MVP-09']['status']=='done' and items['MVP-09']['runtimeDelivered'] is True
 assert items['MVP-09']['pr']==173 and items['MVP-09']['finalMvpRun']==42194906237
 assert items['MVP-10']['status']=='in_progress' and items['MVP-10']['operationalReady'] is False
class ContractTests(unittest.TestCase):
 def test_exact_owner_answers_before_dependent_code_and_negative_mutations(self):
  decisions(ROOT)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for rel in CURRENT:
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
   for rel in CURRENT:
    p=root/rel;text=p.read_text()
    for id in ANSWERS:
     p.write_text(text.replace(id.upper()+':','REMOVED:',1))
     with self.assertRaises(AssertionError):decisions(root)
     p.write_text(text)
 def test_parent_closure_and_future_gates_current_not_waived(self):
  current_status(ROOT)
  for rel in ('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp-existing-code-assessment.md','docs/mvp07-implementation.md'):
   text=(ROOT/rel).read_text()
   for token in (BASE,'41945630168','41945650853','5a58e881d71e5d4b12fdb42ea1829d49790b7e0e'):self.assertIn(token,text,(rel,token))
 def test_all45_published_sql_previous_inventory_and_locked_external_packages_preserved(self):
  before=json.loads(original('database/runtime/manifest.json'));after=json.loads((ROOT/'database/runtime/manifest.json').read_text());self.assertEqual(len(before),45);self.assertEqual(after[:45],before);self.assertEqual(len(after),46)
  for row in before:
   path='database/runtime/'+row['path'];self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  row=after[45];self.assertEqual(row['id'],'0046_document_development');self.assertEqual(row['sha256'],hashlib.sha256((ROOT/'database/runtime'/row['path']).read_bytes()).hexdigest())
  old=json.loads(original('docs/r06-migration-inventory.json'));new=json.loads((ROOT/'docs/r06-migration-inventory.json').read_text());self.assertEqual(new[:len(old)],old);self.assertEqual({i['table'] for i in new[len(old):]},{'document_types.passages','document_types.passage_versions','documents.origins'})
  for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines():
   if path.endswith(('packages.lock.json','package-lock.json','Dockerfile')):self.assertEqual((ROOT/path).read_bytes(),original(path),path)
 def test_historical_decision_blocks_and_all_earlier_security_assertions_literal(self):
  for rel in CURRENT[:4]:
   old=original(rel).decode();new=(ROOT/rel).read_text()
   for id in ('d97','d98','d99'):
    start=f'<!-- {id}-current:start -->';end=f'<!-- {id}-current:end -->';self.assertEqual(old.split(start)[1].split(end)[0],new.split(start)[1].split(end)[0])
  for rel in ('scripts/test-d97-policy.py','scripts/test-d98-policy.py','scripts/test-r00-migrations.py','scripts/run-r00b-tests.py'):
   self.assertEqual((ROOT/rel).read_bytes(),original(rel),rel)
 def test_register_guard_retains_every_old_security_assertion_with_only_two_exact_ids(self):
  path='scripts/test-c00-consistency.py';text=(ROOT/path).read_text()
  normalized=text.replace('set(range(1, 96)) | {99, 100, 101}','set(range(1, 96)) | {99}').replace('append unique D99/D100/D101;','append unique D99;')
  self.assertEqual(normalized,original(path).decode())
 def test_finite_d97_algorithm_adds_only_two_actual_exact_scope_actions(self):
  old=original('database/runtime/migrations/0045_documents_inventory.sql').decode();new=(ROOT/'database/runtime/migrations/0046_document_development.sql').read_text();start='CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role';end='REVOKE ALL ON FUNCTION organization_access.apply_tenant_role(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";'
  previous=old[old.index(start):old.index(end)+len(end)];current=new[new.index(start):new.index(end)+len(end)]
  self.assertEqual(current.replace(",'documents.develop'",'').replace(",'document-types.paths.manage'",''),previous)
 def test_owning_atomic_pipeline_no_physical_draft_reservation_or_rule_identity_reset(self):
  sql=(ROOT/'database/runtime/migrations/0046_document_development.sql').read_text();command=sql.split('CREATE OR REPLACE FUNCTION documents.command(request jsonb)',1)[1].split('END $$;',1)[0]
  for token in ('pg_advisory_xact_lock(777036)','current_membership_access(NULL)','FOR SHARE','FOR UPDATE','documents.check_origins(record_id,false)','documents.check_origins(record_id,true)','documents.prepare_plan','documents.origins','development_plan_required','insufficient_residual','origin_quantity_mismatch','ORDER BY warehouse,item_id','previous."Request"=request','previous."After"','documents.command_audit','documents.versions'):
   self.assertIn(token,sql)
  self.assertLess(command.index('documents.check_origins(record_id,false)'),command.index('SELECT * INTO previous'))
  self.assertLess(command.index('SELECT * INTO previous'),command.index('documents.check_origins(record_id,true)'))
  self.assertIn('"SourceTypeId","DestinationTypeId"',sql)
  for bad in ('INSERT INTO inventory.','UPDATE inventory.','UPDATE catalog.items','DELETE FROM document_types.passages','GRANT ALL','DISABLE ROW LEVEL SECURITY','CREATE SCHEMA workflow'):
   self.assertNotIn(bad,sql)
 def test_full_italian_owning_journey_and_exact_decimal_wire_not_stub(self):
  ui=(ROOT/'frontend/components/documents-workspace.tsx').read_text();types=(ROOT/'frontend/components/document-types-workspace.tsx').read_text();wire=(ROOT/'frontend/lib/documents.ts').read_text();api=(ROOT/'src/Modules/Documents/Enginia360.Documents/DocumentEndpoints.cs').read_text()
  for token in ('Sviluppa da sorgenti confermate','Salva piano di sviluppo','Quota origine','Unisci righe','Residui per passaggio','proposta non riservata','warehouseId:null','command.body','fence.current','stopImmediatePropagation','expectedPathRevision','refreshPlanRules'):
   self.assertIn(token,ui)
  for token in ('Salva percorso versionato','Consenti sedi diverse nella stessa società','expectedRevision','command.body'):self.assertIn(token,types)
  for token in ('BigInt','1000000n','999999999999999999999999n'):self.assertIn(token,wire)
  for bad in ('parseFloat(', 'Number(line.quantity','maxLength'):self.assertNotIn(bad,ui)
  for token in ('DevelopDocumentCommand','262145','MaxDepth = 6','ValidJson','BeginTransactionAsync','await tx.CommitAsync'):self.assertIn(token,api)
 def test_prepared_acceptance_has_real_physical_races_deferred_rollback_and_headless_nojs(self):
  sql=(ROOT/'scripts/test-mvp08-document-development.py').read_text();browser=(ROOT/'tests/browser/mvp08-document-development.cjs').read_text();runner=(ROOT/'scripts/run-mvp08-tests.py').read_text()
  for token in ('barrier_race','REPEATABLE READ','DEFERRABLE INITIALLY DEFERRED','additional_site','source_not_confirmed','incompatible_origins','owned_facts','insufficient_residual'):self.assertIn(token,sql)
  for token in ('headless:true','javaScriptEnabled:false','width:390','width:1366','width:1920','page-*.js','new Set(bodies).size,1','runtime-bearer-proof','development-readback','26.1','keyboardNext:true'):self.assertIn(token,browser)
  self.assertNotIn('headless:false',browser)
  for token in ('assert len(hashes)==45','timeout=240','timeout=360','time.monotonic() + 420','r00.cleanup(command, project)','verify_protected_runtime','capacity[key]','target_sums','development-quantity-provenance-readback.json'):self.assertIn(token,runner)
 def test_historical_role_sql_fixture_preserves_every_assertion_and_exact_catalog(self):
  rel='scripts/test-mvp03b1-roles.py';current=(ROOT/rel).read_text()
  self.assertEqual(current.replace(",'documents.develop','document-types.paths.manage']",']'),original(rel).decode())
 def test_historical_browser_catalogs_retain_all_old_actions_then_append_exact_two(self):
  import re
  for rel in ('tests/browser/mvp04-counterparties.cjs','tests/browser/mvp05-catalog.cjs','tests/browser/mvp06-document-types.cjs'):
   pattern=r'assert\.deepEqual\([^,\n]*\.actions,(\[[^\n]*?\])\)'
   previous=ast.literal_eval(re.search(pattern,original(rel).decode()).group(1))
   current=ast.literal_eval(re.search(pattern,(ROOT/rel).read_text()).group(1))
   self.assertEqual(len(previous),21)
   self.assertEqual(current,previous+['documents.develop','document-types.paths.manage'],rel)
if __name__=='__main__':unittest.main()
