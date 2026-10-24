#!/usr/bin/env python3
"""Mutation proof: R04.c.2 impact/R06 guards must fail closed on a mutated copy.

Each case copies only the guard inputs into a private temp tree, applies ONE
mutation, and runs the real guard script there. The guard must exit non-zero.
The unmutated control must pass, so a failing guard is attributable to the mutation.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COPY = ('scripts', '.github', 'docs', 'database/runtime', 'src/Modules')
IMPACT = 'scripts/test-r04c2-impact.py'
INVENTORY = 'scripts/test-r06-inventory.py'
CI = '.github/workflows/ci.yml'
INV = 'docs/r06-migration-inventory.json'
TABLE = 'inventory.new_part_returns'


def sub(text, pattern, replacement, flags=0):
    changed, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    assert count == 1, 'mutation did not apply: ' + pattern
    return changed


def drop_return_job(text):
    return sub(text, r'  affected-r04c2:\n.*?(?=\n  affected-r03b:)', '', re.S)


def inventory(mutator):
    def apply(text):
        records = json.loads(text)
        mutator(records)
        return json.dumps(records, indent=2) + '\n'
    return apply


def return_record(records):
    return next(r for r in records if r['table'] == TABLE)


def remove_table(records):
    records.remove(return_record(records))


def mark_eligible(records):
    return_record(records)['migration_eligibility'] = 'IMPORT_VIA_COMMAND'


def mark_other_category(records):
    return_record(records)['category'] = 'IMPORT_EVERYTHING'


def drop_owned_table(text):
    return sub(text, r'\s*"inventory\.new_part_returns",?', '')


MUTATIONS = (
    ('return job removed', IMPACT, CI, drop_return_job),
    ('return job made PR-automatic (skipped-not-pass boundary)', IMPACT, CI,
     lambda t: sub(t, r"(  affected-r04c2:\n    needs: impact\n    if: )github\.event_name == 'workflow_dispatch' && ", r'\1')),
    ('return job output not propagated', IMPACT, CI,
     lambda t: sub(t, r'      r04c2: \$\{\{ steps\.selection\.outputs\.r04c2 \}\}\n', '')),
    ('return job loses pool1 completion', IMPACT, CI,
     lambda t: sub(t, r'      - name: Actual explicit new part return pool1 completion\n.*\n', '')),
    ('return job loses TERM lifecycle', IMPACT, CI,
     lambda t: sub(t, r'      - name: Actual new part return TERM.*\n.*\n', '')),
    ('selection no longer maps migration 0024', IMPACT, 'scripts/select-ci-impact.py',
     lambda t: sub(t, r",'database/runtime/migrations/0024_new_part_returns\.sql'", '')),
    ('table dropped from R06 inventory', INVENTORY, INV, inventory(remove_table)),
    ('table marked migration-eligible in R06 inventory', INVENTORY, INV, inventory(mark_eligible)),
    ('table given invalid R06 category', INVENTORY, INV, inventory(mark_other_category)),
    ('table dropped from owning module declaration', IMPACT, 'src/Modules/Inventory/module.json', drop_owned_table),
)


class GuardMutationTests(unittest.TestCase):
    def tree(self):
        directory = tempfile.TemporaryDirectory(prefix='r04c2-guard-', dir=tempfile.gettempdir())
        self.addCleanup(directory.cleanup)
        copy = Path(directory.name) / 'repo'
        for item in COPY:
            shutil.copytree(ROOT / item, copy / item, ignore=shutil.ignore_patterns('bin', 'obj', '__pycache__'))
        return copy

    def run_guard(self, tree, script):
        return subprocess.run([sys.executable, '-I', str(tree / script)], capture_output=True, text=True, timeout=120)

    def test_unmutated_control_passes_both_guards(self):
        tree = self.tree()
        for script in (IMPACT, INVENTORY):
            result = self.run_guard(tree, script)
            self.assertEqual(result.returncode, 0, script + result.stderr[-800:])

    def test_each_single_mutation_makes_the_guard_fail(self):
        for name, script, target, mutate in MUTATIONS:
            with self.subTest(mutation=name):
                tree = self.tree()
                path = tree / target
                path.write_text(mutate(path.read_text()))
                result = self.run_guard(tree, script)
                self.assertNotEqual(result.returncode, 0, 'guard did not detect: ' + name)


if __name__ == '__main__':
    unittest.main()
