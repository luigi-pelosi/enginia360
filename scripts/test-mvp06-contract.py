#!/usr/bin/env python3
"""MVP06 final-phase finite contract/history guards. Never import this as acceptance evidence."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='43a4ff836d67bf1b4f01eb27ccc318171ee45f8d'
CURRENT=('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp-existing-code-assessment.md')
def original(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def current_status(root):
 items={i['id']:i for i in json.loads((root/'docs/mvp-backlog.json').read_text())['items']}
 assert items['MVP-05']['status']=='done' and items['MVP-05']['runtimeDelivered'] is True
 assert (items['MVP-05']['pr'],items['MVP-05']['mergedMain'],items['MVP-05']['prCi'],items['MVP-05']['runtimeDispatch'])==(169,BASE,41833394752,41833450699)
 assert items['MVP-06']['status']=='in_progress' and items['MVP-06']['runtimeDelivered'] is False
 assert items['MVP-06']['contract']=='docs/mvp06-document-types-contract.md'
 assert all(items[f'MVP-{n:02}']['status']=='backlog' for n in range(7,11))
 for name in CURRENT:
  text=(root/name).read_text()
  for token in ('MVP-05/#144 COMPLETATO: PR #169',BASE,'41833394752','41833450699','2d5c06ae8c83e744a88e20abdcc0c34f0066ad81','MVP-06/#145 SORGENTI COMPLETI, NON VERIFICATO'):
   assert token in text,(name,token)
  assert 'MVP-05/#144 IN VALIDAZIONE FINALE' not in text
class ContractTests(unittest.TestCase):
 def test_all_43_published_bytes_and_all_old_inventory_records_preserved(self):
  old=json.loads(original('database/runtime/manifest.json'));new=json.loads((ROOT/'database/runtime/manifest.json').read_text())
  self.assertEqual(len(old),43);self.assertEqual(new[:43],old);self.assertEqual(len(new),44);self.assertEqual(new[-1]['id'],'0044_document_types')
  for entry in old:
   path='database/runtime/'+entry['path'];self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  before=json.loads(original('docs/r06-migration-inventory.json'));after=json.loads((ROOT/'docs/r06-migration-inventory.json').read_text());self.assertEqual(after[:len(before)],before)
  self.assertEqual({r['table'] for r in after[len(before):]},{'document_types.definitions','document_types.versions','document_types.command_audit'})
  spec=importlib.util.spec_from_file_location('inventory',ROOT/'scripts/r06_inventory.py');assert spec and spec.loader
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.verify(ROOT,after)
 def test_historical_specialized_producers_and_facts_have_no_new_canonical_writer(self):
  for directory in ('src/Modules/Workshop','src/Modules/Billing','src/Modules/Inventory','src/Modules/Integrations'):
   for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,directory],cwd=ROOT,text=True).splitlines():self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  sql=(ROOT/'database/runtime/migrations/0044_document_types.sql').read_text()
  for token in ('INSERT INTO inventory.','INSERT INTO workshop.','INSERT INTO billing.','ALTER TABLE workshop.','ALTER TABLE billing.'):
   self.assertNotIn(token,sql)
  text=(ROOT/'docs/mvp06-document-types-contract.md').read_text()
  for token in ('non congelamento indiscriminato','#146','#147','non una falsa cronologia','famiglie storiche specializzate'):
   self.assertIn(token,text)
 def test_d97_preserves_entire_prior_algorithm_except_three_new_company_actions(self):
  old=original('database/runtime/migrations/0043_catalog_management.sql').decode();new=(ROOT/'database/runtime/migrations/0044_document_types.sql').read_text()
  start='CREATE OR REPLACE FUNCTION organization_access.apply_tenant_role';end='REVOKE ALL ON FUNCTION organization_access.apply_tenant_role(uuid,jsonb,jsonb) FROM PUBLIC, :"app_user";'
  expected=old[old.index(start):old.index(end)+len(end)].replace("('counterparties.extensions.read','counterparties.extensions.write')","('counterparties.extensions.read','counterparties.extensions.write','document-types.read','document-types.create','document-types.edit')")
  self.assertEqual(new[new.index(start):new.index(end)+len(end)],expected)
  for token in ('pg_advisory_xact_lock(777036)','current_membership_access(NULL)','current_tenant_role_scopes_before_access()',"p.\"Data\"->'legalEntityId'=to_jsonb(company)","p.\"Data\"->'siteId'='null'::jsonb","p.\"Data\"->'warehouseId'='null'::jsonb",'FOR SHARE','FOR UPDATE','immutable_versions','immutable_command_audit','DEFERRABLE INITIALLY DEFERRED','previous."Request"=request','previous."After"'):
   self.assertIn(token,new)
  self.assertLess(new.index("organization_access.document_type_permission('document-types.'||operation,company)"),new.index('SELECT * INTO previous FROM document_types.command_audit'))
  for bad in ('GRANT ALL','DISABLE ROW LEVEL SECURITY','establish_authority','authorityVersion'):
   self.assertNotIn(bad,new)
 def test_current_summary_negative_mutations_and_exact_historical_d97_d98_blocks(self):
  current_status(ROOT)
  for name in CURRENT:
   old=original(name).decode();new=(ROOT/name).read_text()
   for d in ('d97','d98'):
    start=f'<!-- {d}-current:start -->';end=f'<!-- {d}-current:end -->'
    if start in old:self.assertEqual(new.split(start)[1].split(end)[0],old.split(start)[1].split(end)[0])
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for name in (*CURRENT,'docs/mvp-backlog.json'):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/name).read_bytes())
   for name in CURRENT:
    p=root/name;text=p.read_text()
    for token in ('41833394752','41833450699',BASE,'MVP-06/#145 SORGENTI COMPLETI, NON VERIFICATO'):
     p.write_text(text.replace(token,'REMOVED'))
     with self.assertRaises(AssertionError):current_status(root)
     p.write_text(text)
   p=root/'docs/mvp-backlog.json';text=p.read_text()
   for item,key,value in [('MVP-05','status','in_progress'),('MVP-05','runtimeDelivered',False),('MVP-06','runtimeDelivered',True),('MVP-07','status','in_progress')]:
    data=json.loads(text);next(i for i in data['items'] if i['id']==item)[key]=value;p.write_text(json.dumps(data))
    with self.assertRaises(AssertionError):current_status(root)
    p.write_text(text)
 def test_packages_have_no_new_external_dependency_versions_and_project_edges_are_explicit(self):
  for path in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines():
   if path.endswith('packages.lock.json'):
    before=json.loads(original(path));after=json.loads((ROOT/path).read_text())
    for framework,packages in before['dependencies'].items():
     for name,package in packages.items():
      if package['type']!='Project':self.assertEqual(after['dependencies'][framework][name],package,(path,name))
   elif path.endswith(('package-lock.json','Dockerfile')):self.assertEqual((ROOT/path).read_bytes(),original(path),path)
  for path in ('src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json'):
   dependencies=json.loads((ROOT/path).read_text())['dependencies']['net10.0'];self.assertIn('enginia360.documenttypes',dependencies);self.assertIn('enginia360.documenttypes.contracts',dependencies)
 def test_real_dynamic_ssr_finite_transport_and_frozen_company_command(self):
  page=(ROOT/'frontend/app/document-types/page.tsx').read_text();api=(ROOT/'src/Modules/DocumentTypes/Enginia360.DocumentTypes/ManagementEndpoints.cs').read_text();ui=(ROOT/'frontend/components/document-types-workspace.tsx').read_text()
  for token in ('force-dynamic','revalidate = 0','Array.isArray(value)','finiteDocumentTypesRead','privateRead'):self.assertIn(token,page)
  for token in ('RequireAuthorization()','private, no-store','ValidJson','8193','MaxDepth = 3','BeginTransactionAsync','enginia360:verified-issuer','enginia360:external-subject','Deserialize<DocumentTypeCommand>'):self.assertIn(token,api)
  for token in ('command.body','fence.current','stopImmediatePropagation','command.uncertain = true','Riprova stesso comando','pagina aperta','disabled={!hydrated','Società autorizzata','Storico delle versioni','Versione selezionata'):
   self.assertIn(token,ui)
  self.assertNotIn('maxLength',ui);self.assertNotIn('name="documentTypeId"',ui)
 def test_existing_runtime_classifiers_keep_exact_sets_with_only_two_new_executable_ingresses(self):
  for name in ('run-mvp03b2a-tests.py','run-mvp03b2b-tests.py','run-mvp04-tests.py','run-mvp05-tests.py'):
   old=original('scripts/'+name).decode();new=(ROOT/'scripts'/name).read_text()
   expected=old.replace("'catalog.management_command(jsonb)'}","'catalog.management_command(jsonb)',\n                'document_types.read(uuid,text,uuid,uuid,integer,integer)',\n                'document_types.command(jsonb)'}")
   expected=expected.replace("'billing','accounting','integrations'","'billing','accounting','integrations','document_types'")
   self.assertEqual(new,expected,name)
if __name__=='__main__':unittest.main()
