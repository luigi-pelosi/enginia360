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
            for key in ('r03a','r03b','r03c','r04a','r04b2b3','r06b1'):
                self.assertFalse(result.get(key),(key,sorted(paths)))
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
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.full_architecture",final)
        self.assertNotIn('needs: impact',final)
        self.assertIn('fail-fast: false',final)
        self.assertIn("MVP09_EXCEPTIONAL_FINAL: 'true'",final)
    def test_architecture_plan_is_exhaustive_real_existing_steps_not_renamed_flags(self):
        a=load('architecture','scripts/run-mvp09-architecture.py');source=(ROOT/'.github/workflows/ci.yml').read_text();blocks=a.jobs(source)
        selected=set(a.GROUPS)-{'impact'}
        self.assertEqual(selected|a.EXCLUDED,{name for name in blocks if name.startswith('affected-')})
        self.assertEqual(a.EXCLUDED,{'affected-api','affected-ui'})
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
    def test_exceptional_adapter_never_removes_original_legacy_full_campaign(self):
        source=(ROOT/'.github/workflows/ci.yml').read_text()
        old=subprocess.check_output(['git','show',BASE+':.github/workflows/ci.yml'],cwd=ROOT,text=True)
        self.assertEqual(source.split('  runtime-migrations:',1)[1],old.split('  runtime-migrations:',1)[1])
        a=load('architecture','scripts/run-mvp09-architecture.py')
        for group in a.GROUPS:
            if group in ('impact','affected-integrated-acceptance'):continue
            # Guard source commands and step env through actual finite parser,
            # not another invented list of successful historical outcomes.
            before=a.plan(old.replace('  runtime-migrations:', '  affected-integrated-acceptance:\n    timeout-minutes: 60\n    steps: []\n  runtime-migrations:',1),group)
            self.assertEqual(a.plan(source,group),before)

if __name__=='__main__':unittest.main()
