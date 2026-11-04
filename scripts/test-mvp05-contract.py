#!/usr/bin/env python3
"""Final-phase MVP05 source/history contract; does not launch a service or migrate."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='03872078b2d77dcf6754700729e41fcf5567d051'
CURRENT=('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp-existing-code-assessment.md')
def original(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
class ContractTests(unittest.TestCase):
 def test_all_42_published_migrations_and_old_inventory_records_are_unchanged(self):
  old=json.loads(original('database/runtime/manifest.json'));new=json.loads((ROOT/'database/runtime/manifest.json').read_text())
  self.assertEqual(len(old),42);self.assertEqual(new[:42],old);self.assertEqual(len(new),44);self.assertEqual(new[42]['id'],'0043_catalog_management');self.assertEqual(new[43]['id'],'0044_document_types')
  for entry in old:
   path='database/runtime/'+entry['path'];self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  before=json.loads(original('docs/r06-migration-inventory.json'));after=json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
  self.assertEqual(after[:len(before)],before);self.assertEqual({row['table'] for row in after[len(before):len(before)+2]},{'catalog.authority_history','catalog.management_audit'});self.assertEqual({row['table'] for row in after[len(before)+2:]},{'document_types.definitions','document_types.versions','document_types.command_audit'})
  spec=importlib.util.spec_from_file_location('inventory',ROOT/'scripts/r06_inventory.py');assert spec and spec.loader
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.verify(ROOT,after)
 def test_existing_public_contract_and_old_price_writers_remain_byte_identical(self):
  for path in ('src/Modules/Catalog/Enginia360.Catalog.Contracts/Contracts.cs','src/Modules/Catalog/Enginia360.Catalog/PurchasePriceEndpoints.cs','src/Modules/Catalog/Enginia360.Catalog/MembershipOperation.cs','src/Modules/Workshop/Enginia360.Workshop/CommercialEndpoints.cs','src/Modules/Workshop/Enginia360.Workshop/WorkshopReservationLines.cs'):
   self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  typed=(ROOT/'src/Modules/Catalog/Enginia360.Catalog.Contracts/ManagementContracts.cs').read_text()
  for token in ('enum CatalogKind { Article, Service }','CatalogKind.Article => "Part"','"Part" => CatalogKind.Article','sealed record CatalogIdentity','sealed record CatalogManagementCommand'):self.assertIn(token,typed)
 def test_role_algorithm_only_adds_three_finite_tenant_actions_without_changing_older_scope_validation(self):
  old=original('database/runtime/migrations/0042_counterparty_management.sql').decode();new=(ROOT/'database/runtime/migrations/0043_catalog_management.sql').read_text()
  start='CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role';end='REVOKE ALL ON FUNCTION organization_access.apply_tenant_role(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";'
  expected=old[old.index(start):old.index(end)+len(end)].replace("'counterparties.business-roles.write') THEN","'counterparties.business-roles.write','catalog.shared.read','catalog.shared.create','catalog.shared.edit') THEN")
  self.assertEqual(new[new.index(start):new.index(end)+len(end)],expected)
  for token in ('pg_advisory_xact_lock(777036)','current_membership_access(NULL)','current_tenant_role_scopes_before_access()',"p.\"Data\"->'legalEntityId'='null'::jsonb",'immutable_management_audit','FOR UPDATE','previous."Request"=request','previous."After"','catalog-authority:'):
   self.assertIn(token,new)
  self.assertLess(new.index("organization_access.catalog_permission(action_name)"),new.index('SELECT * INTO previous FROM catalog.management_audit'))
  self.assertNotIn('GRANT ALL',new);self.assertNotIn('DISABLE ROW LEVEL SECURITY',new);self.assertNotIn('INSERT INTO inventory.',new)
 def test_standalone_composition_private_dynamic_ssr_and_frozen_uncertainty(self):
  program=(ROOT/'src/Enginia360.Api/Program.cs').read_text();self.assertIn('GetValue<bool>("Catalog:Enabled") ||',program);self.assertIn('CatalogModule.MapCatalogManagement(app)',program)
  page=(ROOT/'frontend/app/catalog/page.tsx').read_text();self.assertIn('dynamic = "force-dynamic"',page);self.assertIn('revalidate = 0',page);self.assertIn('Array.isArray(value)',page)
  ui=(ROOT/'frontend/components/catalog-workspace.tsx').read_text()
  for token in ('command.body','command.uncertain = true','fence.current','stopImmediatePropagation','Riprova stesso comando','catalogReadPath(currentQuery)','100 caratteri Unicode','pagina aperta'):
   self.assertIn(token,ui)
  self.assertNotIn('maxLength',ui);self.assertNotIn('name="itemId"',ui)
  api=(ROOT/'src/Modules/Catalog/Enginia360.Catalog/ManagementEndpoints.cs').read_text()
  for token in ('RequireAuthorization()','CacheControl = "private, no-store"','ValidJson','Deserialize<CatalogManagementCommand>','BeginTransactionAsync','enginia360:verified-issuer','enginia360:external-subject'):self.assertIn(token,api)
 def test_current_delivered_predecessor_and_historical_decision_blocks_with_negative_mutations(self):
  def check(root):
   data=json.loads((root/'docs/mvp-backlog.json').read_text());items={i['id']:i for i in data['items']};previous=items['MVP-04'];current=items['MVP-05']
   self.assertEqual(previous['status'],'done');self.assertIs(previous['runtimeDelivered'],True);self.assertEqual(previous['pr'],168);self.assertEqual(previous['mergedMain'],BASE);self.assertEqual(previous['prCi'],41780772823);self.assertEqual(previous['runtimeDispatch'],41780819337)
   self.assertEqual(current['status'],'done');self.assertIs(current['runtimeDelivered'],True);self.assertEqual(current['contract'],'docs/mvp05-catalog-contract.md');self.assertEqual(current['pr'],169);self.assertEqual(current['mergedMain'],'43a4ff836d67bf1b4f01eb27ccc318171ee45f8d');self.assertEqual(current['prCi'],41833394752);self.assertEqual(current['runtimeDispatch'],41833450699)
   for name in CURRENT:
    text=(root/name).read_text();self.assertIn('MVP-05/#144 COMPLETATO: PR #169',text);self.assertIn('41833394752',text);self.assertIn('41833450699',text);self.assertIn('MVP-06/#145 SORGENTI COMPLETI, NON VERIFICATO',text)
    for line in text.splitlines():
     if 'MVP-04/#143 COMPLETATO:' in line:
      for token in ('PR #168',BASE,'41780772823','41780819337','f7d9419348fc78463fe6e3bc5411a52d81beea8b'):self.assertIn(token,line)
    self.assertNotIn('MVP-04/#143 IN IMPLEMENTAZIONE',text)
  check(ROOT)
  for name in CURRENT:
   old=original(name).decode();new=(ROOT/name).read_text()
   for decision in ('d97','d98'):
    start=f'<!-- {decision}-current:start -->';end=f'<!-- {decision}-current:end -->'
    if start in old: self.assertEqual(new.split(start)[1].split(end)[0],old.split(start)[1].split(end)[0],name)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for name in (*CURRENT,'docs/mvp-backlog.json'):
    file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes((ROOT/name).read_bytes())
   for name in CURRENT:
    file=root/name;text=file.read_text();file.write_text(text.replace('41780819337','REMOVED'))
    with self.assertRaises(AssertionError):check(root)
    file.write_text(text)
   path=root/'docs/mvp-backlog.json';original_text=path.read_text()
   for item_id,key,value in [('MVP-04','status','in_progress'),('MVP-04','runtimeDelivered',False),('MVP-05','runtimeDelivered',False)]:
    data=json.loads(original_text);next(i for i in data['items'] if i['id']==item_id)[key]=value;path.write_text(json.dumps(data))
    with self.assertRaises(AssertionError):check(root)
    path.write_text(original_text)
 def test_owner_setup_remains_explicit_finite_tls_and_separate_from_business_roles(self):
  spec=importlib.util.spec_from_file_location('owner',ROOT/'scripts/owner-master-authority.py');assert spec and spec.loader
  owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
  import uuid
  payload={key:str(uuid.uuid4()) for key in owner.IDS};payload.update(domain='catalog',direction='Enginia360ToExternal',expectedVersion=0,companyIds=[str(uuid.uuid4())])
  self.assertEqual(owner.validate(payload),payload)
  for changes in ({'domain':'*'},{'domain':'inventory'},{'expectedVersion':True},{'companyIds':[]},{'extra':True}):
   with self.assertRaises((ValueError,TypeError)):owner.validate(dict(payload,**changes))
  source=(ROOT/'scripts/owner-master-authority.py').read_text();self.assertIn("PGSSLMODE')!='verify-full'",source);self.assertIn('exact readback failed',source);self.assertIn('catalog.establish_authority(',source)
 def test_owner_cli_cannot_report_success_from_old_history_after_current_refusal(self):
  from unittest.mock import patch
  import contextlib
  import io
  import uuid
  spec=importlib.util.spec_from_file_location('owner_readback',ROOT/'scripts/owner-master-authority.py');assert spec and spec.loader
  owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
  payload={key:str(uuid.uuid4()) for key in owner.IDS};payload.update(domain='catalog',direction='Enginia360ToExternal',expectedVersion=0,companyIds=[str(uuid.uuid4())])
  # Unit-only subprocess fixtures, not executed database evidence.
  for outcome in ('forbidden','conflict','missing','invalid'):
   fixture=subprocess.CompletedProcess(['psql'],0,stdout=payload['tenantId']+'\n'+outcome+'\n'+payload['tenantId']+'\n1\n',stderr='')
   with patch.dict('os.environ',{'PGSSLMODE':'verify-full','PGSSLROOTCERT':'/synthetic-ca.crt'}),patch.object(owner.subprocess,'run',return_value=fixture):
    with self.assertRaises(ValueError):owner.apply(payload)
  for outcome in ('applied','replayed'):
   fixture=subprocess.CompletedProcess(['psql'],0,stdout=payload['tenantId']+'\n'+outcome+'\n'+payload['tenantId']+'\n1\n',stderr='')
   with patch.dict('os.environ',{'PGSSLMODE':'verify-full','PGSSLROOTCERT':'/synthetic-ca.crt'}),patch.object(owner.subprocess,'run',return_value=fixture) as run,contextlib.redirect_stdout(io.StringIO()):
    owner.apply(payload);self.assertIn('catalog.establish_authority(',run.call_args.kwargs['input']);self.assertNotIn('organization_access.master_authority_history',run.call_args.kwargs['input'])
 def test_protected_inventory_retains_id_start_mount_guards_but_does_not_inspect_unrelated_projects(self):
  from unittest.mock import patch
  import contextlib,io
  spec=importlib.util.spec_from_file_location('inventory_guard',ROOT/'scripts/run-r00b-tests.py');assert spec and spec.loader
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  protected='a'*64;old='b'*64;added='c'*64
  row=dict(Id=protected,Name='/enginia360-api-1',StartedAt='synthetic-start',Mounts=[dict(Source='/synthetic/retained',Destination='/data',RW=False)])
  ps=lambda values:'\n'.join(json.dumps(dict(Id=id,Name=name)) for id,name in values)
  beforePs=ps([(protected,'enginia360-api-1'),(old,'unrelated-project-1')]);afterPs=ps([(protected,'enginia360-api-1'),(added,'unrelated-replacement-1')])
  # Unit-only Docker metadata fixtures; actual canonical runners remain required.
  with patch.object(module,'run',side_effect=[beforePs,json.dumps(row),afterPs,json.dumps(row)]) as run,contextlib.redirect_stdout(io.StringIO()):
   before=module.capture_protected_runtime();result=module.verify_protected_runtime(before)
   self.assertEqual(result['added'],[added]);self.assertEqual(result['removed'],[old])
   self.assertEqual(result['protectedBefore'],result['protectedAfter'])
   for call in run.call_args_list:
    args=call.args[0];self.assertIn(args[1],('ps','inspect'))
    if args[1]=='inspect':self.assertIn(protected,args);self.assertNotIn(old,args);self.assertNotIn(added,args);self.assertNotIn('.Config',str(args))
  for changed in [dict(row,StartedAt='restarted'),dict(row,Mounts=[]),dict(row,Name='/enginia360-replaced')]:
   with patch.object(module,'run',side_effect=[afterPs,json.dumps(changed)]),contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(AssertionError):module.verify_protected_runtime(before)
  for values in [[(added,'unrelated-1')],[(added,'enginia360-api-1')]]:
   replies=[ps(values)] + ([json.dumps(dict(row,Id=added))] if values[0][1].startswith('enginia360') else [])
   with patch.object(module,'run',side_effect=replies),contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(AssertionError):module.verify_protected_runtime(before)
  import ast
  for name in ('run-r00a-tests.py','run-r00b-tests.py','run-mvp02a-tests.py','run-mvp02b-tests.py','run-mvp02c-tests.py','run-mvp03b1-tests.py','run-mvp03b2a-tests.py','run-mvp03b2b-tests.py','run-mvp04-tests.py','run-mvp05-tests.py','test-r00b-lifecycle.py'):
   tree=ast.parse((ROOT/'scripts'/name).read_text());function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==('actual_term_probe' if name=='test-r00b-lifecycle.py' else 'main'))
   calls={n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,(ast.Attribute,ast.Name))}
   self.assertTrue({'capture_protected_runtime','verify_protected_runtime'}<=calls,name)
if __name__=='__main__':unittest.main()
