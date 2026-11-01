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

    def mutate(self, relative, old, new, count=1):
        path = self.root / relative
        text = path.read_text()
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count))

    def test_d77_active_policy_cannot_be_lost_in_history(self):
        self.mutate('docs/foundation/01-glossary-and-domain-boundaries.md',
                    '**D77 — accesso iniziale e delega limitata:**', '**Decisione non attiva:**')
        self.run_guard('missing active D77')

    def test_d77_cannot_expand_delegation_in_both_plan_and_backlog(self):
        path = self.root / 'docs/productization-backlog.json'
        cards = json.loads(path.read_text())
        card = next(card for card in cards if card['id'] == 'R01')
        old = card['gate']
        card['gate'] = old.replace('Nessun self-grant, subdelega, altro admin o default-first-user', 'Amministratore senza limiti')
        path.write_text(json.dumps(cards))
        self.mutate('docs/productization-plan.md',old,card['gate'])
        self.run_guard('D77 bounded mandate')

    def test_r01b_delivery_cannot_claim_full_provisioning_or_r02_policy(self):
        path=self.root/'docs/productization-backlog.json'
        cards=json.loads(path.read_text())
        card=next(card for card in cards if card['id']=='R01')
        old=card['gate']
        boundary='non provisioning completo né policy CRUD R02'
        self.assertIn(boundary,old)
        card['gate']=old.replace(boundary,'provisioning completo e policy CRUD R02 approvati')
        path.write_text(json.dumps(cards))
        self.mutate('docs/productization-plan.md',old,card['gate'])
        self.run_guard('D77 bounded mandate')

    def test_receipt_delivery_has_one_current_summary_not_candidate_status(self):
        for name in ('productization-plan.md', 'r06-recovery-runbook.md', 'r04b3-receipt-runtime.md'):
            text = (ROOT/'docs'/name).read_text()
            with self.subTest(document=name):
                self.assertEqual(text.count('<!-- receipt-delivery:start -->'), 1)
                active = text.split('<!-- receipt-delivery:start -->')[1].split('<!-- receipt-delivery:end -->')[0]
                for token in ('PR #133', 'PR #134', '#128 CLOSED', '#44/#45 OPEN',
                              'c1a503fa1d17782c6dce358a8a7b76a4781b025c', '41336683551',
                              'OPEN_NOT_REPAIRED', 'D76', 'full_architecture=false'):
                    self.assertIn(token, active)

    def test_receipt_delivery_cli_rejects_stale_metadata_and_scope_promotions(self):
        for old, new in (
            ('#128 CLOSED', '#128 OPEN'),
            ('#44/#45 OPEN', '#44/#45 CLOSED'),
            ('c1a503fa1d17782c6dce358a8a7b76a4781b025c', 'f'*40),
            ('41336683551', '41336683550'),
            ('15 job/145 step', '15 job/144 step'),
            ('full_architecture=false', 'full_architecture=true'),
            ('OPEN_NOT_REPAIRED', 'REPAIRED'),
            ('ERP per-order residual UNKNOWN', 'ERP per-order residual KNOWN'),
            ('provider lost ACK HOLD', 'provider automatic POST retry'),
            ('R04/R05 NON complete', 'R04/R05 complete'),
        ):
            with self.subTest(mutation=new):
                saved = {}
                for name in ('productization-plan.md', 'r06-recovery-runbook.md', 'r04b3-receipt-runtime.md'):
                    path = self.root/'docs'/name
                    original = path.read_text()
                    start, end = original.index('<!-- receipt-delivery:start -->'), original.index('<!-- receipt-delivery:end -->')
                    block = original[start:end]
                    self.assertIn(old, block)
                    saved[path] = original
                    path.write_text(original[:start]+block.replace(old, new)+original[end:])
                try:
                    self.run_guard('receipt delivery')
                finally:
                    for path, original in saved.items():
                        path.write_text(original)

    def test_receipt_delivery_cli_rejects_missing_or_divergent_active_summary(self):
        path = self.root/'docs/r04b3-receipt-runtime.md'
        original = path.read_text()
        for text in (original.replace('<!-- receipt-delivery:start -->', ''),
                     original.replace('costo q6 congelato', 'costo variabile', 1),
                     original+'\n<!-- receipt-delivery:start -->duplicate<!-- receipt-delivery:end -->'):
            path.write_text(text)
            self.run_guard('receipt delivery')
        path.write_text(original)

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
                    "python3 scripts/test-c00-consistency.py # python3 scripts/test-productization-consistency.py removed", count=-1)
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
