#!/usr/bin/env python3
"""FINAL-only MVP10 explicit packaging scope, status and negative/mixed guards."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = '9326d19abc97d1eb249d0a1abecdc1ffd4cd3289'
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ImpactTests(unittest.TestCase):
    def offline(self, paths):
        result=m.selection(sorted(paths))
        self.assertTrue(result['mvp_offline'])
        self.assertEqual(result['api_filter'],'')
        for key,value in result.items():
            if isinstance(value,bool) and key!='mvp_offline':self.assertFalse(value,(key,paths))
        return result

    def test_explicit_source_paths_and_whole_agreed_point_are_offline_only(self):
        self.assertEqual(m.RELEASE_FILES,{
            'scripts/mvp10_release.py','scripts/test-mvp10-release.py','scripts/test-mvp10-impact.py',
            'docs/mvp10-release-contract.md','docs/mvp10-source-release.md',
            'docs/mvp10-source-policy.json','docs/mvp10-functional-baseline.json','docs/mvp10-readiness.json'})
        for path in m.RELEASE_FILES:self.offline([path])
        self.offline(m.RELEASE_SCOPE)
        committed=set(subprocess.check_output(['git','diff','--name-only',BASE,'HEAD'],cwd=ROOT,text=True).splitlines())
        dirty=set(subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT,text=True).splitlines())
        untracked=set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        whole=committed|dirty|untracked
        self.assertTrue(whole & m.RELEASE_FILES)
        self.assertLessEqual(whole,m.RELEASE_SCOPE)
        self.offline(whole)
        self.offline(whole|{'docs/mvp10-source-policy.json'})  # committed point + overlay

    def test_mixed_business_dependencies_keep_original_runtime_security_filters(self):
        for producer in ('src/Enginia360.Api/Program.cs',
                         'src/Modules/Documents/Enginia360.Documents/DocumentEndpoints.cs',
                         'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
                         'frontend/lib/private-backend.ts',
                         'database/runtime/manifest.json',
                         'src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
            before=m.selection([producer])
            after=m.selection(sorted(m.RELEASE_SCOPE|{producer}))
            self.assertTrue(after['mvp_offline'])
            for key,value in before.items():
                if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after[key],(producer,key))
            for token in before['api_filter'].split('|'):
                if token:self.assertIn(token,after['api_filter'])
            self.assertFalse(after['full_architecture'])

    def test_unknown_near_prefix_and_mixed_new_executable_paths_fail_closed(self):
        for anchor in m.RELEASE_FILES:
            for path in ('scripts/mvp10_release_copy.py','scripts/test-mvp10-unknown.py',
                         'docs/unmapped.py','tests/browser/mvp10-unknown.cjs',
                         'src/Modules/Documents/Enginia360.Documents/Unknown.cs','../AGENTS.md'):
                with self.subTest(anchor=anchor,path=path),self.assertRaises(ValueError):m.selection([anchor,path])
        self.assertFalse(m.selection(['docs/unrelated.md'])['mvp_offline'])
        for path in ('scripts/select-ci-impact.py','.github/workflows/ci.yml'):
            result=m.selection([path]);self.assertTrue(result['migrations']);self.assertTrue(result['browser'])

    def test_existing_ci_job_only_no_publish_deploy_or_automatic_main(self):
        source=(ROOT/'.github/workflows/ci.yml').read_text()
        trigger=source.split('concurrency:',1)[0]
        self.assertIn('  pull_request:',trigger);self.assertNotIn('  push:',trigger)
        block=source.split('  affected-mvp-offline:',1)[1].split('  affected-r05a8-offline:',1)[0]
        for token in ("if: needs.impact.outputs.mvp_offline == 'true'",'needs: impact',
                      'python3 -I scripts/test-mvp10-release.py && python3 -I scripts/test-mvp10-impact.py',
                      'python3 -I scripts/test-mvp-baseline.py','python3 -I scripts/test-d97-policy.py','python3 -I scripts/test-d98-policy.py'):
            self.assertIn(token,block)
        for token in ('docker ','gh release','mvp10_release.py build','contents: write','git push','workflow_run:'):
            self.assertNotIn(token,block)
        old=subprocess.check_output(['git','show',BASE+':.github/workflows/ci.yml'],cwd=ROOT,text=True)
        self.assertEqual(source.split('  runtime-migrations:',1)[1],old.split('  runtime-migrations:',1)[1])

    def test_published_runtime_and_locked_build_inputs_unchanged_by_mvp10(self):
        paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
        for path in paths:
            if path.startswith(('src/','frontend/','database/')) or path.endswith('Dockerfile') or path in ('global.json','Directory.Build.props','docs/r06-migration-inventory.json','docs/r06-readiness-registry.json'):
                self.assertEqual((ROOT/path).read_bytes(),subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT),path)
        # No hidden promotion of unproven operations by updating the old registry.
        readiness=json.loads((ROOT/'docs/mvp10-readiness.json').read_text())
        self.assertFalse(readiness['operationalReady'])
        self.assertTrue(readiness['trackingBoundary']['keepIssue149Open'])
        self.assertFalse(readiness['trackingBoundary']['readyForUseChecked'])


if __name__=='__main__':unittest.main(verbosity=2)
