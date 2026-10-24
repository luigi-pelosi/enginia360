#!/usr/bin/env python3
"""R03.a.2 exact affected selection and bounded actual direct-consumer proof wiring."""
import importlib.util
import json
import hashlib
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

class Impact(unittest.TestCase):
    def test_every_material_owner_and_direct_runtime_test_selects_required_r03a2(self):
        for path in ('src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs',
                     'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
                     'web/src/ui01/runtime/OrderWorkspace.tsx','web/src/ui01/runtime/editorMessages.ts',
                     'database/runtime/migrations/0020_material_structure_fence.sql',
                     'scripts/run-r03a2-tests.py','scripts/test-r03a2-impact.py','scripts/test-r03a2-lifecycle.py',
                     'tests/browser/r03a2-acceptance.cjs','compose.r03a2-test.yaml'):
            with self.subTest(path=path):
                selected=module.selection([path])
                self.assertTrue(selected.get('r03a2',False),path)
                self.assertFalse(selected['full_architecture'])
                for dependency in ('InventoryArchitectureTests','BillingBoundaryTests','AccountingBoundaryTests'):
                    self.assertIn(dependency,selected['api_filter'])
    def test_unrelated_changes_do_not_select_runtime(self):
        for path in ('docs/r03a2-safe-material-corrections.md','web/src/ui01/App.tsx'):
            self.assertFalse(module.selection([path]).get('r03a2',False))
    def test_actual_runtime_jobs_are_dispatch_only_and_both_pool_sizes_execute(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-r03a2:',workflow)
        block=workflow.split('  affected-r03a2:\n')[1].split('\n  runtime-migrations:')[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r03a2 == 'true'",block)
        self.assertIn('timeout 600 python3 scripts/run-r03a2-tests.py',block)
        self.assertIn('R03A2_POOL_SIZE=1 timeout 600 python3 scripts/run-r03a2-tests.py',block)
        self.assertNotIn('  push:',workflow.split('concurrency:')[0])
    def test_published_nineteen_checksums_are_unchanged(self):
        import subprocess
        published=json.loads(subprocess.check_output(['git','show','520c9ae3dda6906ab9944d756666c6619b59b394:database/runtime/manifest.json'],cwd=ROOT,text=True))
        current=json.loads((ROOT/'database/runtime/manifest.json').read_text())
        self.assertEqual(current[:19],published)
        self.assertEqual(len(current),21)
        for entry in current:
            self.assertEqual(hashlib.sha256((ROOT/'database/runtime'/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
if __name__=='__main__': unittest.main()
