#!/usr/bin/env python3
"""R03.a static wiring: append-only manifest, readiness constants, grants, runner/Compose/CI/doc presence. No runtime claims."""
import hashlib
import json
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
read = lambda path: (ROOT/path).read_text()


class R03aContract(unittest.TestCase):
    def test_manifest_hashes_match_bytes_and_published_prefix_is_untouched(self):
        entries = json.loads(read('database/runtime/manifest.json'))
        self.assertEqual(len(entries), 20)
        for entry in entries:
            self.assertEqual(hashlib.sha256((ROOT/'database/runtime'/entry['path']).read_bytes()).hexdigest(), entry['sha256'], entry['id'])
        digest = hashlib.sha256(json.dumps(entries[:17], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '0ad2ffe59881d41069e375abc10b6c4272e59868d39391fa51f2808cb4b03e97')

    def test_new_units_have_no_seed_values_delete_grants_or_unforced_tables(self):
        text = read('database/runtime/migrations/0018_workshop_order_workspace.sql')+read('database/runtime/migrations/0019_inventory_working_group_provenance.sql')
        self.assertNotRegex(text, r'(?is)INSERT\s+INTO[^;]*\bVALUES\b')
        self.assertNotRegex(text, r'(?i)GRANT[^;]*\b(DELETE|TRUNCATE|ALL)\b')
        for table in ('working_groups', 'order_notes', 'workspace_history', 'editor_commands'):
            self.assertIn('workshop.'+table, text)
        self.assertIn("'workshop.working_groups','workshop.order_notes','workshop.workspace_history','workshop.editor_commands'", text)
        self.assertIn('FORCE ROW LEVEL SECURITY', text)

    def test_readiness_constants_and_suites_follow_the_manifest(self):
        for path in ('scripts/run-r00a-tests.py', 'scripts/run-r00b-tests.py', 'scripts/run-ui01b-tests.py', 'scripts/run-r03a-tests.py'):
            self.assertRegex(read(path), r"== ?'20'", path)
            self.assertNotRegex(read(path), r"== ?'17'", path)
        self.assertIn('scripts/test-r03a-migration.py', read('scripts/run-r00a-tests.py'))
        self.assertIn('scripts/test-r03a-migration.py', read('migrator.runtime.Dockerfile'))

    def test_runner_is_ephemeral_guarded_and_compose_has_no_ports_or_volumes(self):
        runner = read('scripts/run-r03a-tests.py')
        for needle in ('r00.cleanup(command,project)', 'r00.inventory(\'volume\')==before_volumes', 'signal.SIGTERM', 'R00_POOL_SIZE'):
            self.assertIn(needle, runner)
        compose = read('compose.r03a-test.yaml')
        self.assertNotRegex(compose, r'(?m)^\s*ports:')
        self.assertIn('Inventory__Enabled', compose)
        self.assertIn('r03a-acceptance.cjs', compose)

    def test_editor_routes_actions_and_cap_are_wired(self):
        module = read('src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs')
        self.assertIn('EditorEndpoints.Map(routes)', module)
        editor = read('src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs')
        for action in ('workshop.lines.add', 'workshop.lines.edit', 'workshop.lines.remove', 'workshop.notes.write', 'workshop.groups.write', 'workshop.orders.read'):
            self.assertIn('"'+action+'"', editor)
        self.assertNotIn('COUNT', read('src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs').split('CloseTechnically',1)[1].split('Request(',1)[0].upper().replace('COUNTERPARTIES', ''))

    def test_contract_document_records_the_remaining_structural_contract(self):
        doc = read('docs/r03a-order-workspace.md')
        for needle in ('material_structure_edit_not_supported', 'line_has_commitments', 'commercial_summary_limit', 'P1', 'P2', '#43'):
            self.assertIn(needle, doc)


if __name__ == '__main__':
    unittest.main()
