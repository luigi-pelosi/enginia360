#!/usr/bin/env python3
"""R04.a paths select actual material acceptance, not a generic editor smoke."""

import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "impact", ROOT / "scripts/select-ci-impact.py"
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MaterialImpactTests(unittest.TestCase):
    def test_changed_migration_consumer_is_mapped_without_full_architecture(self):
        selected = m.selection(["scripts/test-r03a-migration.py"])
        self.assertTrue(selected["migrations"] and selected["r03a2"])
        self.assertFalse(selected["full_architecture"])

    def test_panel_and_owning_contracts_select_actual_runtime_and_direct_dependencies(
        self,
    ):
        for path in (
            "web/src/ui01/runtime/MaterialOperations.tsx",
            "web/src/ui01/runtime/materialContracts.ts",
            "web/src/ui01/runtime/WorkshopRuntime.tsx",
            "src/Enginia360.Api/OrganizationAccess/InventoryAccessAdapter.cs",
            "database/runtime/manifest.json",
            "scripts/test-r04a-impact.py",
            "scripts/run-r04a-tests.py",
            "scripts/test-r04a-stock-profile.py",
            "scripts/test-r04a-lifecycle.py",
            "scripts/owner-stock-profile.py",
            "tests/browser/r04a-acceptance.cjs",
            "src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs",
            "database/runtime/migrations/0021_company_stock_profile.sql",
        ):
            with self.subTest(path=path):
                result = m.selection([path])
                self.assertTrue(
                    result.get("r04a", False),
                    "actual R04 material runtime not selected",
                )
                self.assertTrue(
                    result["ui01b"] and result["ui_build"] and result["migrations"]
                )
                self.assertIn("InstallationBoundaryTests", result["api_filter"])
                self.assertIn("AccountingBoundaryTests", result["api_filter"])
                self.assertFalse(result["full_architecture"])

    def test_unrelated_docs_do_not_select_runtime_and_unknown_executable_refuses(self):
        self.assertFalse(
            m.selection(["docs/r04a-material-operations.md"]).get("r04a", False)
        )
        with self.assertRaises(ValueError):
            m.selection(["scripts/unmapped-r04-command.py"])

    def test_selected_material_runtime_has_a_dispatch_only_acceptance_job(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("      r04a: ${{ steps.selection.outputs.r04a }}", workflow)
        self.assertIn("  affected-r04a:\n", workflow)
        block = re.split(
            r"\n  [A-Za-z][A-Za-z0-9_-]*:",
            workflow.split("  affected-r04a:\n", 1)[1],
            maxsplit=1,
        )[0]
        self.assertIn(
            "github.event_name == 'workflow_dispatch' && needs.impact.outputs.r04a == 'true'",
            block,
        )
        self.assertIn("timeout 600 python3 scripts/run-r04a-tests.py", block)
        self.assertIn("timeout 300 python3 scripts/test-r04a-lifecycle.py", block)
        self.assertNotIn("continue-on-error", block)
        self.assertNotIn("  push:", workflow.split("concurrency:", 1)[0])


if __name__ == "__main__":
    unittest.main()
