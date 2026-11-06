#!/usr/bin/env python3
"""MVP09 final-phase preservation/status/real-harness guards. Source phase: UNEXECUTED."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='b00fdbafd3f91f6526caf18e75b79476ab02660f'
CURRENT=('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp-existing-code-assessment.md')

def original(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)

def current_status(root):
    data=json.loads((root/'docs/mvp-backlog.json').read_text());items={row['id']:row for row in data['items']}
    assert all(items[f'MVP-{n:02}']['status']=='done' for n in range(9))
    previous=items['MVP-08'];current=items['MVP-09']
    assert (previous['runtimeDelivered'],previous['pr'],previous['mergedMain'],previous['prCi'],previous['runtimeDispatch'])==(True,172,BASE,42060851414,42060851802)
    assert previous['validationStatus']=='verified_parent_exact_head_artifacts'
    assert current['status']=='in_progress' and current['runtimeDelivered'] is False
    assert current['implementationStatus']=='source_complete' and current['validationStatus']=='UNEXECUTED'
    assert current['contract']=='docs/mvp09-integrated-acceptance-contract.md'
    assert items['MVP-10']['status']=='backlog'
    assert items['MVP-03']['userAdministrationPolicy']['runtimeDelivered'] is False
    assert items['MVP-03']['userOnboardingPolicy']['runtimeDelivered'] is False
    for path in CURRENT:
        text=(root/path).read_text();start='<!-- mvp09-current:start -->';end='<!-- mvp09-current:end -->'
        assert text.count(start)==text.count(end)==1,path
        block=text.split(start)[1].split(end)[0]
        for token in ('MVP00–08 completati','MVP-09/#148 IN CORSO','SOURCE_COMPLETE_UNVERIFIED','MVP-10/#149 Backlog',BASE,'42060851414','42060851802','5 job/62 step','18 job/166 step','420 eseguiti/passati','46 migrazioni','mvp_final=true','full_architecture=true','full_architecture=false','Nessun deployment/readiness operativo'):
            assert token in block,(path,token)
        assert 'MVP-08/#147 IN CORSO' not in block

class ContractTests(unittest.TestCase):
    def test_current_status_and_independent_negative_mutations(self):
        current_status(ROOT)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for path in (*CURRENT,'docs/mvp-backlog.json'):
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/path).read_bytes())
            for path in CURRENT:
                p=root/path;text=p.read_text()
                for token in ('MVP00–08 completati','42060851414','42060851802','mvp_final=true','Nessun deployment/readiness operativo'):
                    start=text.index('<!-- mvp09-current:start -->');end=text.index('<!-- mvp09-current:end -->')
                    p.write_text(text[:start]+text[start:end].replace(token,'REMOVED')+text[end:])
                    with self.assertRaises(AssertionError):current_status(root)
                    p.write_text(text)
            p=root/'docs/mvp-backlog.json';text=p.read_text()
            for id,key,value in [('MVP-08','status','in_progress'),('MVP-08','runtimeDelivered',False),('MVP-08','prCi',0),('MVP-09','status','done'),('MVP-09','runtimeDelivered',True),('MVP-09','validationStatus','PASSED'),('MVP-10','status','done')]:
                data=json.loads(text);next(row for row in data['items'] if row['id']==id)[key]=value;p.write_text(json.dumps(data))
                with self.assertRaises(AssertionError):current_status(root)
                p.write_text(text)
    def test_every46_published_migration_manifest_and_inventory_is_byte_exact(self):
        before=json.loads(original('database/runtime/manifest.json'));self.assertEqual(len(before),46)
        self.assertEqual((ROOT/'database/runtime/manifest.json').read_bytes(),original('database/runtime/manifest.json'))
        for row in before:
            path='database/runtime/'+row['path'];self.assertEqual((ROOT/path).read_bytes(),original(path),path)
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),row['sha256'])
        self.assertEqual((ROOT/'docs/r06-migration-inventory.json').read_bytes(),original('docs/r06-migration-inventory.json'))
    def test_decisions_d97_d98_d99_d100_d101_are_literal_not_reopened(self):
        for path in CURRENT[:4]:
            before=original(path).decode();after=(ROOT/path).read_text()
            for decision in ('d97','d98','d99','d100','d101'):
                start=f'<!-- {decision}-current:start -->';end=f'<!-- {decision}-current:end -->'
                self.assertEqual(after.split(start)[1].split(end)[0],before.split(start)[1].split(end)[0],(path,decision))
        for path in ('docs/foundation/01-glossary-and-domain-boundaries.md','docs/foundation/01a-commercial-document-model.md'):
            self.assertEqual((ROOT/path).read_bytes(),original(path))
    def test_no_business_runtime_module_price_fiscal_schema_or_dependency_change(self):
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
        for path in paths:
            if path.startswith('src/') or path.endswith(('packages.lock.json','package-lock.json','Dockerfile')):
                self.assertEqual((ROOT/path).read_bytes(),original(path),path)
        self.assertEqual((ROOT/'scripts/run-r00b-tests.py').read_bytes(),original('scripts/run-r00b-tests.py'))
        self.assertEqual((ROOT/'scripts/test-d97-policy.py').read_bytes(),original('scripts/test-d97-policy.py'))
        self.assertEqual((ROOT/'scripts/test-d98-policy.py').read_bytes(),original('scripts/test-d98-policy.py'))
    def test_existing_browser_journey_body_is_reused_with_all_assertions(self):
        before=original('tests/browser/mvp08-document-development.cjs').decode();after=(ROOT/'tests/browser/mvp08-document-development.cjs').read_text()
        start=' const catalog=[];';end=" fs.writeFileSync('/evidence/mvp08-browser.json'"
        expected=before[before.index(start):before.index(end)]
        actual=after[after.index(start):after.index('\n return {article,service,types')]
        actual=actual.replace('fixture.users[operatorIndex].username','fixture.users[5].username').replace('fixture.users[operatorIndex].password','fixture.users[5].password')
        self.assertEqual(actual,expected)
        self.assertIn('if(require.main===module)',after)
    def test_prepared_integrated_source_is_one_real_generated_chain_not_seven_flags(self):
        browser=(ROOT/'tests/browser/mvp09-integrated-acceptance.cjs').read_text();runner=(ROOT/'scripts/run-mvp09-tests.py').read_text()
        for token in ('chromium.launch({headless:true})','documentDevelopmentJourney({browser,owner,operator,ctx,roles,permissions,role,rolePayload,operatorIndex:3})','register-trusted','create(\'tenant\'','organization delegation alone cannot administer users','Approva associazione senza abilitare o assegnare ruoli','member.accessEnabled,false','Abilita accesso al tenant','Salva permesso','counterparty-master-setup','Fornitore (ruolo aziendale)','MVP09 company-only address',"['Transfer','1']",'Draft changes no stock','javaScriptEnabled:false','integrated-readback'):
            self.assertIn(token,browser)
        for token in ('prepare_fixture','fixtureOnly=True','operativeGrants=[]','validate_journey','mvp09-integrated-sql.json','SET LOCAL ROLE runtime_app','verified_fixture_settings','mvp09-app-role-rls.json','expected[\'hopId\']','facts[\'origins\']','Decimal'):
            self.assertIn(token,runner)
        self.assertNotIn('route.fulfill',browser,'new integration must not synthesize business responses')
        self.assertNotIn('headless:false',browser)
        self.assertIn('acceptance.handle_control', (ROOT/'scripts/run-mvp08-tests.py').read_text())
    def test_cleanup_has_exact_replacement_and_preserves_still_consumed_history(self):
        source=(ROOT/'docs/mvp09-cleanup-trace.md').read_text()
        for token in ('frontend/components/shell.tsx','frontend/components/documents-workspace.tsx','src/Enginia360.Api/Program.cs','.github/workflows/ci.yml','B02–B14','R00–R06','46','NO deletion quota','archive/mvp08-checkpoints.md'):
            self.assertIn(token,source)
        archived=(ROOT/'docs/archive/mvp08-checkpoints.md').read_text()
        for path in CURRENT:
            for line in original(path).decode().splitlines():
                if line.startswith(('MVP-03/#142 e #166 COMPLETATI:','Stato corrente: MVP-03/#142 e #166 COMPLETATI:')):self.assertIn(line,archived)
    def test_owner_scope_correction_has_evidenced_dependencies_and_no_legacy_prerequisite(self):
        contract=(ROOT/'docs/mvp09-integrated-acceptance-contract.md').read_text()
        trace=(ROOT/'docs/mvp09-cleanup-trace.md').read_text()
        for token in ('Non puoi bypassare questa trafila inutile?','mvp_final=true','full_architecture=false','B04–B14','42116253372','FAILED'):
            self.assertIn(token,contract)
        for token in ('DocumentsModule.cs','DocumentEndpoints.cs','private-backend.ts','documents.snapshot_fence','membership_access_snapshot_fence','test-r05a2-evidence.py','test-r05a3-evidence.py'):
            self.assertIn(token,trace)
        data=json.loads((ROOT/'docs/mvp-backlog.json').read_text())
        criterion=next(row for row in data['items'] if row['id']=='MVP-09')['acceptance'][3]
        self.assertIn('sette domini',criterion)
        self.assertIn('dipendenze dirette',criterion)
        self.assertNotIn('intero repository',criterion)

    def test_final_campaign_limits_and_original_deadlines_resources_preserved(self):
        runner=(ROOT/'scripts/run-mvp08-tests.py').read_text()
        for token in ('timeout=240','timeout=360','time.monotonic() + 420','r00.cleanup(command, project)','capture_protected_runtime','verify_protected_runtime','before_volumes','candidate_source_hashes','46 if acceptance is not None else 45'):
            self.assertIn(token,runner)
        a=(ROOT/'scripts/run-mvp09-architecture.py').read_text()
        for token in ('NONPASS','start_new_session=True','os.killpg','pipefail','MVP09_EXCEPTIONAL_FINAL','new or lost consumer','empty campaign consumer is not pass'):
            self.assertIn(token,a)
        limits=(ROOT/'docs/mvp09-final-acceptance.md').read_text()
        for token in ('UNEXECUTED','42060851414','mvp_final=true','full_architecture=true','full_architecture=false','MVP10','RPO/RTO','NONPASS','42116253372','FAILED','42112432604','42112473729'):
            self.assertIn(token,limits)

if __name__=='__main__':unittest.main()
