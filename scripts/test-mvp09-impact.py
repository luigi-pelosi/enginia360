#!/usr/bin/env python3
"""Final-phase finite MVP09 selector and explicit campaign tests; not run in source phase."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import hashlib
import os
from unittest import mock
import unittest
ROOT=Path(__file__).resolve().parents[1]
BASE='b00fdbafd3f91f6526caf18e75b79476ab02660f'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
m=load('impact','scripts/select-ci-impact.py')

class ImpactTests(unittest.TestCase):
    def test_every_new_executable_exact_path_has_integrated_and_direct_consumers(self):
        for path in m.INTEGRATED_FILES:
            result=m.selection([path])
            for key in ('integrated_acceptance','document_development','documents','document_types','counterparty_management','catalog_management','federated_onboarding','membership_access','tenant_roles','frontend','migrations','browser'):
                self.assertTrue(result[key],(path,key))
            self.assertFalse(result['full_architecture'])
            for name in ('DocumentDevelopmentTests','DocumentInventoryTests','DocumentTypeManagementTests','BusinessMembershipFenceTests'):
                self.assertIn('FullyQualifiedName~'+name,result['api_filter'])
    def test_full_point_plus_committed_or_dirty_overlay_preserves_scope(self):
        actual=set(subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        for paths in (actual,m.INTEGRATED_SCOPE):
            result=m.selection(sorted(paths));self.assertTrue(result['integrated_acceptance']);self.assertFalse(result['full_architecture'])
            for key in ('r03a','r03b','r03c','r04a','r04b2b3'):
                self.assertFalse(result.get(key),(key,sorted(paths)))
            self.assertEqual(result['r06b1'], bool(set(paths) & {'scripts/run-r06b1-tests.py','scripts/test-r06b1-guards.py','scripts/test-r06b1-lifecycle.py'}))
    def test_corrective_whole_point_keeps_new_consumers_without_unrelated_widening(self):
        committed=set(subprocess.check_output(['git','diff','--name-only',BASE,'6a4fc105f873a58fa21ad821d93bcfd736929e1e'],cwd=ROOT,text=True).splitlines())
        prior=m.selection(sorted(committed))
        corrected=m.selection(sorted(committed | m.INTEGRATED_CORRECTIVE_FILES))
        for key,value in prior.items():
            if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(corrected[key],key)
        for key in ('r06_offline','r05a2_offline','r05a3_offline','r06b1'):
            self.assertTrue(corrected[key],key)
        for key in ('r03a','r03b','r03c','r04a','r04b2b3'):
            self.assertFalse(corrected[key],key)
        for path in ('scripts/run-b04-copy.sh','tests/fixtures/b04-copy.sql','scripts/redact-fixture-copy.py'):
            with self.assertRaises(ValueError):m.selection(sorted(committed | {path}))
        producer='src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'
        original=m.selection([producer]);mixed=m.selection(sorted(committed | m.INTEGRATED_CORRECTIVE_FILES | {producer}))
        for key,value in original.items():
            if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(mixed.get(key),key)
        for token in original['api_filter'].split('|'):
            if token:self.assertIn(token,mixed['api_filter'])
    def test_negative_docs_only_and_unrelated_executable_do_not_create_integration(self):
        for paths in (['docs/mvp09-cleanup-trace.md'],['web/src/ui01/runtime/OwnActualTime.tsx']):
            self.assertFalse(m.selection(paths)['integrated_acceptance'])
    def test_unknown_near_prefix_missing_map_fail_closed_even_mixed(self):
        for anchor in m.INTEGRATED_FILES:
            for path in ('scripts/run-mvp09-copy.py','tests/browser/mvp09-unknown.cjs','src/Modules/Documents/Enginia360.Documents/Unknown.cs','frontend/app/unknown.tsx'):
                with self.assertRaises(ValueError):m.selection([anchor,path])
    def test_mixed_real_producers_retain_every_original_true_flag_and_filter(self):
        for path in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
            original=m.selection([path]);mixed=m.selection(sorted(m.INTEGRATED_SCOPE|{path}))
            for key,value in original.items():
                if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(mixed.get(key),(path,key))
            for token in original['api_filter'].split('|'):
                if token:self.assertIn(token,mixed['api_filter'])
            self.assertTrue(mixed['integrated_acceptance'])
    def test_actual_shared_helper_changes_select_integrated_consumer(self):
        for path in m.INTEGRATED_DIRECT:self.assertTrue(m.selection([path])['integrated_acceptance'],path)
    def test_pr_only_default_false_exact_head_runtime_and_no_skip_pass(self):
        source=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertNotIn('\n  push:',source)
        self.assertIn('default: false',source.split('full_architecture:',1)[1].split('concurrency:',1)[0])
        job=source.split('  affected-integrated-acceptance:',1)[1].split('  affected-document-development:',1)[0]
        for token in ("github.event_name == 'workflow_dispatch'","integrated_acceptance == 'true'",'ref: ${{ github.sha }}','MVP09_POOL_SIZE=4','MVP09_POOL_SIZE=1','timeout 1500','timeout-minutes: 60','set -o pipefail','if-no-files-found: error'):
            self.assertIn(token,job)
        final=source.split('  architecture-current-contracts:',1)[1].split('  runtime-migrations:',1)[0]
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.mvp_final && !inputs.full_architecture",final)
        self.assertNotIn('needs: impact',final)
        self.assertIn('fail-fast: false',final)
        self.assertIn("MVP09_EXCEPTIONAL_FINAL: 'true'",final)
    def test_architecture_plan_is_exhaustive_real_existing_steps_not_renamed_flags(self):
        a=load('architecture','scripts/run-mvp09-architecture.py');source=(ROOT/'.github/workflows/ci.yml').read_text();blocks=a.jobs(source)
        selected=set(a.GROUPS)-{'impact'}
        self.assertEqual(selected|a.SEPARATE_FINAL|a.RETAINED_LEGACY,{name for name in blocks if name.startswith('affected-')})
        self.assertEqual(a.SEPARATE_FINAL,{'affected-api'})
        self.assertEqual(a.GROUPS,('impact', 'affected-integrated-acceptance', 'affected-document-development', 'affected-documents', 'affected-document-types', 'affected-catalog-management', 'affected-counterparty-management', 'affected-federated-onboarding', 'affected-membership-access', 'affected-tenant-roles', 'affected-platform-offline', 'affected-platform-authority', 'affected-organization-administration', 'affected-authenticated-organization', 'affected-frontend', 'affected-frontend-runtime', 'affected-mvp-offline', 'affected-r05a2-offline', 'affected-r05a3-offline', 'affected-r06-offline', 'affected-migrations', 'affected-browser', 'affected-r06-restore'))
        self.assertTrue(selected.isdisjoint(a.RETAINED_LEGACY))
        self.assertIn('affected-ui',a.RETAINED_LEGACY)
        for group in ('affected-editor','affected-r03a','affected-r03b','affected-r03c','affected-r04a','affected-r04b2b3','affected-r06-staging'):
            self.assertIn(group,a.RETAINED_LEGACY)
            with self.assertRaises(ValueError):a.plan(source,group)
        self.assertEqual(len(a.GROUPS),len(set(a.GROUPS)))
        for group in a.GROUPS:
            prepared=a.plan(source,group);self.assertGreater(len(prepared['steps']),0);self.assertGreater(prepared['deadlineSeconds'],0)
            for step in prepared['steps']:
                for line in step['command'].splitlines():self.assertIn(line.strip(),blocks[group])
        with self.assertRaises(ValueError):a.plan(source,'verify-copy')
        with self.assertRaises(ValueError):a.plan(source+'\n  affected-unmapped:\n    steps: []\n','affected-documents')
        mutated=source.replace('        run: set -o pipefail; MVP09_POOL_SIZE=4','        run: >\n          set -o pipefail; MVP09_POOL_SIZE=4',1)
        with self.assertRaises(ValueError):a.plan(mutated,'affected-integrated-acceptance')
    def test_adapter_rejects_unsupported_execution_and_preserves_literal_env(self):
        a=load('architecture','scripts/run-mvp09-architecture.py');source=(ROOT/'.github/workflows/ci.yml').read_text()
        anchor='        run: set -o pipefail; MVP09_POOL_SIZE=4'
        for replacement in ('        if: false\n'+anchor,'        shell: pwsh\n'+anchor,'        working-directory: /other\n'+anchor,'        run: ${{ secrets.UNSUPPORTED }}', '        run: >\n          command', '        env:\n          TEST: ${{ github.sha }}\n'+anchor):
            with self.subTest(replacement=replacement),self.assertRaises(ValueError):a.plan(source.replace(anchor,replacement,1),'affected-integrated-acceptance')
        literal=source.replace(anchor,"        env:\n          CHECK_LITERAL: 'exact-value'\n"+anchor,1)
        self.assertEqual(a.plan(literal,'affected-integrated-acceptance')['steps'][1]['env'],{'CHECK_LITERAL':'exact-value'})
        empty=source.replace(a.jobs(source)['affected-integrated-acceptance'],'    timeout-minutes: 60\n    steps:\n      - uses: actions/checkout@v4\n')
        with self.assertRaises(ValueError):a.plan(empty,'affected-integrated-acceptance')
    def test_adapter_actual_pipefail_environment_deadline_and_failure_evidence(self):
        a=load('architecture','scripts/run-mvp09-architecture.py')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with mock.patch.dict(os.environ,{'TMPDIR':directory,'RUNNER_TEMP':directory}):
                for name,command,deadline,error in [('success','test "$LITERAL" = exact; printf captured',10,None),('pipeline','printf failure-captured; false | tee /dev/null',10,RuntimeError),('deadline','printf before-deadline; sleep 10',1,subprocess.TimeoutExpired)]:
                    evidence=root/name;prepared=dict(group='impact',deadlineSeconds=deadline,steps=[dict(name=name,command=command,env={'LITERAL':'exact'})])
                    if error:
                        with self.assertRaises(error):a.execute(prepared,evidence)
                    else:a.execute(prepared,evidence)
                    actual=json.loads((evidence/'execution.json').read_text());step=actual['steps'][0]
                    self.assertEqual(actual['status'],'NONPASS' if error else 'PASS')
                    self.assertEqual(step['status'],actual['status']);self.assertIsInstance(step['exit'],int)
                    self.assertIn('ended',step);self.assertIn('scripts/run-mvp09-architecture.py',actual['sourceHashes'])
                    self.assertEqual(step['logSha256'],hashlib.sha256((evidence/'00.log').read_bytes()).hexdigest())
                    self.assertFalse((evidence/'github-env.txt').exists())
                    if name=='deadline':self.assertIn('before-deadline',(evidence/'00.log').read_text())
    def test_mvp_final_is_separate_from_legacy_and_keeps_real_api_composition(self):
        source=(ROOT/'.github/workflows/ci.yml').read_text()
        a=load('architecture_scope','scripts/run-mvp09-architecture.py')
        blocks=a.jobs(source)
        for name in ('architecture-mvp-api','architecture-current-contracts'):
            self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.mvp_final && !inputs.full_architecture",blocks[name])
        self.assertIn('!inputs.full_architecture && !inputs.mvp_final',blocks['impact'])
        self.assertIn('default: false',source.split('mvp_final:',1)[1].split('full_architecture:',1)[0])
        self.assertIn('consumer: '+json.dumps(a.GROUPS),blocks['architecture-current-contracts'])
        api=blocks['architecture-mvp-api']
        for token in ('dotnet restore','--locked-mode','dotnet test','dotnet publish','--vulnerable --include-transitive','ref: ${{ github.sha }}','timeout-minutes: 10'):
            self.assertIn(token,api)
        self.assertNotIn('API_FILTER',api)
        self.assertNotIn('--filter',api)
        self.assertNotIn('scripts/run-b04-tests.sh',api)
        for name in ('verify','runtime-migrations'):
            self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.full_architecture",blocks[name])
            self.assertNotIn('inputs.mvp_final',blocks[name])
        # No new defaults/blanket acceptance for restored legacy-only paths.
        for path in ('tests/fixtures/b04-current-model.sql','scripts/redact-fixture-diagnostics.py'):
            self.assertFalse((ROOT/path).exists())
            with self.assertRaises(ValueError):m.selection([*m.INTEGRATED_FILES,path])

    def test_exceptional_adapter_never_removes_original_legacy_full_campaign(self):
        source=(ROOT/'.github/workflows/ci.yml').read_text()
        old=subprocess.check_output(['git','show',BASE+':.github/workflows/ci.yml'],cwd=ROOT,text=True)
        self.assertEqual(source.split('  runtime-migrations:',1)[1],old.split('  runtime-migrations:',1)[1])
        for path in ('compose.b04-test.yaml','scripts/test-b04-ci.py','web/vite.config.ts','web/src/ui01/Editor.acceptance.test.tsx',
                     *('scripts/run-b%02d-tests.sh' % number for number in range(4,15))):
            self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show','6a4fc105f873a58fa21ad821d93bcfd736929e1e:'+path],cwd=ROOT),path)
        a=load('architecture','scripts/run-mvp09-architecture.py')
        for group in a.GROUPS:
            if group in ('impact','affected-integrated-acceptance'):continue
            # Guard source commands and step env through actual finite parser,
            # not another invented list of successful historical outcomes.
            before=a.plan(old.replace('  runtime-migrations:', '  affected-integrated-acceptance:\n    timeout-minutes: 60\n    steps: []\n  runtime-migrations:',1),group)
            self.assertEqual(a.plan(source,group),before)

if __name__=='__main__':unittest.main()
