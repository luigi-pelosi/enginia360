#!/usr/bin/env python3
"""Exercise the consistency guard against isolated corruptions, never runtime."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts/test-c00-consistency.py"
SCRATCH = Path(os.environ.get("TMPDIR", "/root/.hermes/cache/scratch"))


class ConsistencyGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="productization-docs-", dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "docs", self.root / "docs")
        shutil.copy(ROOT / "AGENTS.md", self.root / "AGENTS.md")
        shutil.copytree(ROOT / ".github/workflows", self.root / ".github/workflows")

    def run_guard(self, expected=None):
        result = subprocess.run(["python3", str(GUARD)], cwd=self.root,
                                text=True, capture_output=True, check=False)
        if expected is None:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stderr)

    def mutate(self, relative, old, new):
        path = self.root / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1))

    def test_current_documentation_passes(self):
        self.run_guard()

    def test_delivery_prohibition_cannot_remain_active(self):
        self.mutate("AGENTS.md", "# Engineering standards",
                    "# Engineering standards\n\nno commit, push or merge yet")
        self.run_guard("obsolete preparation restriction")

    def test_giobby_evidence_reference_must_resolve(self):
        evidence = self.root / "docs/giobby-discovery.md"
        evidence.unlink(missing_ok=True)
        self.run_guard("Giobby evidence missing")

    def test_mutation_suite_is_executed_in_ci(self):
        self.mutate(".github/workflows/ci.yml", "python3 scripts/test-c00-consistency.py",
                    "python3 scripts/test-c00-consistency.py # python3 scripts/test-productization-consistency.py removed")
        self.run_guard("Productization mutation suite must execute in CI")

    def test_stale_active_authorization_is_rejected(self):
        self.mutate("docs/foundation/04-first-vertical-slice.md",
                    "D74 autorizza", "C00 è il solo WIP; D74 autorizza")
        self.run_guard("obsolete authorization")

    def test_missing_direction_decision_is_rejected(self):
        self.mutate("docs/foundation/04-first-vertical-slice.md", "D76", "omitted-decision")
        self.run_guard("missing 'D76'")

    def test_tenant_master_invariant_cannot_be_removed(self):
        self.mutate("docs/productization-plan.md",
                    "unica autorità del nucleo anagrafico condiviso tenant-wide D26/D65",
                    "multiple concurrent master authorities")
        self.run_guard("tenant-wide D26/D65")

    def test_historical_delivery_evidence_remains_required(self):
        self.mutate("docs/b13-verification.md", "39498640111", "incorrect-run")
        self.run_guard("39498640111")

    def test_original_roadmap_meaning_cannot_be_renumbered(self):
        path = self.root / "docs/productization-backlog.json"
        cards = json.loads(path.read_text())
        next(card for card in cards if card["id"] == "R01")["title"] = "Runtime"
        path.write_text(json.dumps(cards))
        self.run_guard("original meaning changed")

    def test_forward_dependency_is_rejected(self):
        path = self.root / "docs/productization-backlog.json"
        cards = json.loads(path.read_text())
        cards[0]["depends"] = ["R06"]
        path.write_text(json.dumps(cards))
        self.run_guard("missing/forward/cyclic dependency")

    def test_authority_gate_cannot_be_removed(self):
        path = self.root / "docs/productization-backlog.json"
        cards = json.loads(path.read_text())
        card = next(card for card in cards if card["id"] == "R04")
        old = card["gate"]
        card["gate"] = old.replace("AUTHORITY", "omitted-gate")
        path.write_text(json.dumps(cards))
        self.mutate("docs/productization-plan.md", old, card["gate"])
        self.run_guard("missing 'AUTHORITY'")

    def test_decision_history_cannot_be_renumbered(self):
        self.mutate("docs/foundation/01-glossary-and-domain-boundaries.md",
                    "### D26 —", "### D25 —")
        self.run_guard("Decision register")

    def test_ci_regression_suite_cannot_be_removed(self):
        self.mutate(".github/workflows/ci.yml", "run: sh scripts/run-b13-tests.sh",
                    "run: true # suite removed")
        self.run_guard("CI selection must contain exactly one")


if __name__ == "__main__":
    unittest.main(verbosity=2)
