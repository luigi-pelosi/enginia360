#!/usr/bin/env python3
"""Explicit new-part return acceptance must run, selected before production edits."""
import importlib.util
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class NewReturnImpactTests(unittest.TestCase):
    def test_return_direct_dependencies(self):
        for path in ('scripts/test-r04c2-impact.py','scripts/test-r04c2-guard-mutation.py','scripts/run-r04c2-tests.py','tests/browser/r04c2-acceptance.cjs','compose.r04c2-test.yaml','src/Modules/Inventory/Enginia360.Inventory/NewPartReturnEndpoints.cs','database/runtime/migrations/0024_new_part_returns.sql','web/src/ui01/runtime/MaterialNewReturn.tsx','web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css'):
            with self.subTest(path=path):
                s=m.selection([path])
                self.assertTrue(s.get('r04c2'),path)
                for key in ('r04a','r03a2','browser','migrations','ui01b','ui_build','ui_tests','r06_offline'): self.assertTrue(s[key],key)
                self.assertIn('AccountingBoundaryTests',s['api_filter'])
                self.assertFalse(s['full_architecture'])
    def test_dispatch_only(self):
        w=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('      r04c2: ${{ steps.selection.outputs.r04c2 }}',w)
        self.assertIn('  affected-r04c2:\n',w)
        b=re.split(r'\n  [A-Za-z][A-Za-z0-9_-]*:',w.split('  affected-r04c2:\n',1)[1],maxsplit=1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r04c2 == 'true'",b)
        self.assertIn('timeout 600 python3 scripts/run-r04c2-tests.py',b)
        self.assertIn('R04A_POOL_SIZE=1 timeout 600 python3 scripts/run-r04c2-tests.py',b)
        self.assertIn('timeout 420 python3 scripts/test-r04c2-lifecycle.py',b)
        self.assertIn('npm run build:ui01-runtime',b)
        self.assertNotIn('continue-on-error',b)
    def test_owning_module_declares_only_new_operative_return(self):
        import json
        module=json.loads((ROOT/'src/Modules/Inventory/module.json').read_text())
        self.assertIn('inventory.new-part-returns.create',module['providedActions'])
        self.assertIn('inventory.new_part_returns',module['ownedTables'])
        self.assertNotIn('inventory.new-part-returns.create',(ROOT/'database/runtime/migrations/0016_limited_grant_administration.sql').read_text())
    def test_lifecycle_probe_budget_covers_cold_build_and_stays_within_command_limit(self):
        text=(ROOT/'scripts/test-r04c2-lifecycle.py').read_text()
        self.assertIn('legacy.PROBE_DEADLINE_SECONDS = 420',text)
        self.assertIn('PROBE_DEADLINE_SECONDS=240',(ROOT/'scripts/test-r00b-lifecycle.py').read_text())
    def test_term_wording_matches_actual_held_line_lock(self):
        text=(ROOT/'scripts/test-r04c2-lifecycle.py').read_text()
        self.assertIn('hold-line:',text)
        self.assertIn('held SQL line lock',text)
        self.assertNotIn('SQL stock',text)
    def test_published_23_unit_prefix_is_byte_identical_and_new_contract_is_public(self):
        import hashlib,json
        entries=json.loads((ROOT/'database/runtime/manifest.json').read_text())
        self.assertEqual(hashlib.sha256(json.dumps(entries[:23],sort_keys=True,separators=(',',':')).encode()).hexdigest(),'e76101f21e5b75e6b27e7b53f1c73eaee75cd31dfa2bacb796bed150cb3430a3')
        self.assertEqual(entries[23]['id'],'0024_new_part_returns')
        for entry in entries:
            self.assertEqual(hashlib.sha256((ROOT/'database/runtime'/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
        endpoint=(ROOT/'src/Modules/Inventory/Enginia360.Inventory/NewPartReturnEndpoints.cs').read_text()
        self.assertIn('workshop.pick_has_installations(',endpoint)
        self.assertNotIn('workshop.installations',endpoint)
        self.assertNotIn('workshop.commercial_lines',endpoint)
        self.assertIn('inventory.pick_returned(', (ROOT/'src/Modules/Workshop/Enginia360.Workshop/InstallationEndpoints.cs').read_text())
        self.assertNotIn('inventory.new_part_returns',(ROOT/'src/Modules/Workshop/Enginia360.Workshop/InstallationEndpoints.cs').read_text())

    def test_historical_installation_fixtures_supply_transaction_local_tenant(self):
        for path in ('scripts/run-r04a-tests.py','scripts/run-r04c1-tests.py'):
            with self.subTest(path=path):
                source=(ROOT/path).read_text().split('elif action.startswith("external-history:"):',1)[1].split('legacy_local =',1)[0]
                self.assertIn("BEGIN; SELECT set_config('app.tenant_id','{t}',true);",source)
                self.assertIn("COMMIT;",source)

    def test_negative(self):
        self.assertFalse(m.selection(['docs/r04c2-release.md']).get('r04c2',False))
        with self.assertRaises(ValueError):m.selection(['scripts/unmapped-release.py'])
if __name__=='__main__':unittest.main()
