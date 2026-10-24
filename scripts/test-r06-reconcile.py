#!/usr/bin/env python3
"""Synthetic-only offline acceptance; no import, API or ERP calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    path = ROOT/'scripts'/('r06_'+name+'.py')
    assert path.exists(), 'offline '+name+' tool missing'
    spec = importlib.util.spec_from_file_location('r06_'+name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticTests(unittest.TestCase):
    def test_generator_cli_emits_meaningful_decimal_probes_and_summary(self):
        command = [sys.executable, '-I', str(ROOT/'scripts/r06_synthetic.py'), '--seed', '7']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), 'synthetic dataset CLI missing')
        dataset = json.loads(result.stdout)
        tool = load_tool('synthetic')
        self.assertEqual(dataset, tool.generate(7))
        self.assertIn('10.25', {r['discount_percent'] for r in dataset['records']})
        self.assertIn('0.000001', {r['net_amount'] for r in dataset['records']})
        summary = subprocess.run(command+['--summary'], capture_output=True, text=True)
        self.assertEqual(summary.returncode, 0, summary.stderr)
        self.assertEqual(json.loads(summary.stdout)['sha256'], tool.digest(dataset))
        self.assertEqual(json.loads(summary.stdout)['records'], len(dataset['records']))
        invalid = subprocess.run(command[:-1]+['-1'], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)

    def test_strict_synthetic_envelope_q6_discount2_and_supported_enum_only(self):
        tool = load_tool('synthetic')
        self.assertTrue(hasattr(tool, 'validate'), 'synthetic input validation missing')
        dataset = tool.generate(7)
        tool.validate(dataset)
        cases = [('kind', 'LegacyImport'), ('source_id', '12345678901'),
                 ('fiscal_identifier', 'RSSMRA80A01H501U'), ('quantity', '0'),
                 ('quantity', '1.0000001'), ('quantity', 1.0), ('quantity', '1e2'),
                 ('quantity', '-0'), ('quantity', ' 1'), ('quantity', '1000000'),
                 ('discount_percent', '1.001'), ('discount_percent', '100.01'),
                 ('unit_price', 'NaN'), ('net_amount', '1,00'), ('tax_rate', '23.000000')]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(dataset)
                changed['records'][0][field] = value
                with self.assertRaises(ValueError):
                    tool.validate(changed)
        for changed in ({'format': 'production', 'records': []},
                        dict(dataset, surprise=True), dict(dataset, records='wrong')):
            with self.assertRaises(ValueError):
                tool.validate(changed)
        for field in ('source_id', 'kind'):
            changed = copy.deepcopy(dataset)
            del changed['records'][0][field]
            with self.assertRaises(ValueError):
                tool.validate(changed)
        for seed in (-1, True, 'real-name', 4294967296):
            with self.assertRaises(ValueError):
                tool.generate(seed)
        for args in [('0', '1', '0'), ('1', '1', '0.001'), ('1', '1e2', '0')]:
            with self.assertRaises(ValueError):
                tool.line_net(*args)

    def test_documented_d67_half_up6_then_payer_rate_group_tax(self):
        tool = load_tool('synthetic')
        self.assertTrue(hasattr(tool, 'line_net'), 'D67 offline Decimal calculation missing')
        cases = [('1', '0.000001', '50.00', '0.000001'),
                 ('2.123456', '10.000001', '10.25', '19.058020'),
                 ('1', '95', '5', '90.250000'), ('1', '10', '100', '0.000000')]
        for quantity, price, discount, expected in cases:
            self.assertEqual(tool.line_net(quantity, price, discount), expected)
        data = tool.generate(7)
        rows = data['records'][:2]
        for row in rows:
            row['net_amount'] = '0.000002'
        group = tool.amount_groups(rows)
        self.assertEqual(len(group), 1)
        self.assertEqual(next(iter(group.values())), {'net': '0.000004', 'tax': '0.000001', 'total': '0.000005'})
        rows[1]['payer_id'] += '-OTHER'
        self.assertEqual(len(tool.amount_groups(rows)), 2)
        self.assertEqual({g['tax'] for g in tool.amount_groups(rows).values()}, {'0.000000'})
        # Never group across independent document/tenant/company boundaries.
        for field in ('order_id', 'tenant_id', 'company_id'):
            changed = copy.deepcopy(rows)
            changed[1]['payer_id'] = changed[0]['payer_id']
            changed[1][field] += '-OTHER'
            self.assertEqual(len(tool.amount_groups(changed)), 2)

    def test_repeatable_seed_hash_and_invalid_production_identifiers(self):
        tool = load_tool('synthetic')
        first = tool.generate(7)
        self.assertEqual(first, tool.generate(7))
        self.assertEqual(tool.digest(first), hashlib.sha256(tool.canonical(first)).hexdigest())
        self.assertNotEqual(tool.digest(first), tool.digest(tool.generate(8)))
        self.assertEqual(first['format'], 'SYNTH_INVALID_FOR_PRODUCTION_V1')
        self.assertGreater(len(first['records']), 3)
        for row in first['records']:
            for key, value in row.items():
                if key.endswith('_id') or key == 'fiscal_identifier':
                    self.assertTrue(value.startswith('SYNTH-INVALID-FOR-PRODUCTION-'), key)
                    self.assertFalse(re.fullmatch(r'\d{11}|[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]', value), key)
            self.assertNotEqual(row['payer_id'], row['vehicle_owner_id'])
        self.assertGreater(len({r['tenant_id'] for r in first['records']}), 1)
        self.assertGreater(len({r['company_id'] for r in first['records']}), 1)


class ReconcileTests(unittest.TestCase):
    def test_valid_numeric_spelling_is_normalized_without_mutating_inputs(self):
        source = load_tool('synthetic').generate(7)
        target = copy.deepcopy(source)
        target['records'][0]['quantity'] = '1'
        target['records'][0]['discount_percent'] = '0'
        target['records'][6]['unit_price'] = '82.5'
        before = copy.deepcopy(target)
        report = load_tool('reconcile').compare(source, target)
        self.assertTrue(report['ok'], 'documented numeric normalization must not invent a delta')
        self.assertEqual(target, before)

    def test_counts_by_probe_kind_and_ambiguous_matches_are_honest(self):
        source = load_tool('synthetic').generate(7)
        target = copy.deepcopy(source)
        target['records'].append(copy.deepcopy(target['records'][0]))
        report = load_tool('reconcile').compare(source, target)
        self.assertEqual(report['counts'].get('by_kind'), {
            'source': {'Service': 4, 'Part': 4}, 'target': {'Service': 5, 'Part': 4}})
        self.assertEqual(report['matched'], 7, 'ambiguous source keys are not successful one-to-one matches')

    def test_actual_cli_reports_success_difference_and_invalid_input_exit_codes(self):
        command = [sys.executable, '-I', str(ROOT/'scripts/r06_reconcile.py')]
        source = load_tool('synthetic').generate(7)
        with tempfile.TemporaryDirectory() as tmp:
            left, right = Path(tmp)/'source.json', Path(tmp)/'target.json'
            left.write_text(json.dumps(source))
            right.write_text(json.dumps(source))
            result = subprocess.run(command+[str(left), str(right)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.strip(), 'reconciliation CLI summary missing')
            self.assertTrue(json.loads(result.stdout)['ok'])
            mutated = copy.deepcopy(source)
            mutated['records'][0]['reserved_stock'] = '2.000001'
            right.write_text(json.dumps(mutated))
            result = subprocess.run(command+[str(left), str(right)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(result.stdout)['reserved_stock_delta'][0]['delta'], '1.000000')
            for payload in ('{', '{"format":"unexpected","records":[]}',
                            json.dumps(source)[:-1]+',"format":"SYNTH_INVALID_FOR_PRODUCTION_V1"}'):
                right.write_text(payload)
                result = subprocess.run(command+[str(left), str(right)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(result.stdout)
                self.assertIn('refused', result.stderr)
            result = subprocess.run(command+[str(left), str(right)+'-absent'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)

    def test_payer_owner_overwrite_and_other_identity_loss_are_explicit(self):
        source = load_tool('synthetic').generate(7)
        for field in ('payer_id', 'vehicle_owner_id', 'working_group_id', 'order_id', 'fiscal_identifier', 'kind'):
            with self.subTest(field=field):
                target = copy.deepcopy(source)
                target['records'][0][field] = (target['records'][0]['vehicle_owner_id'] if field == 'payer_id'
                                               else 'Part' if field == 'kind' else target['records'][4][field])
                report = load_tool('reconcile').compare(source, target)
                self.assertFalse(report['ok'])
                category = 'role_mismatch' if field in ('payer_id', 'vehicle_owner_id') else 'field_mismatch'
                self.assertIn(field, [d['field'] for d in report.get(category, [])])

    def test_tenant_company_and_exact_scope_mismatches_are_reported(self):
        source = load_tool('synthetic').generate(7)
        for field in ('tenant_id', 'company_id', 'site_id', 'warehouse_id', 'scope_id'):
            with self.subTest(field=field):
                target = copy.deepcopy(source)
                target['records'][0][field] = target['records'][4][field]
                report = load_tool('reconcile').compare(source, target)
                self.assertFalse(report['ok'])
                self.assertEqual([d['field'] for d in report.get('scope_mismatch', [])], [field])

    def test_amount_physical_and_reserved_deltas_are_separate_and_do_not_cancel(self):
        source = load_tool('synthetic').generate(7)
        tool = load_tool('reconcile')
        for field, value, category, delta in (
                ('net_amount', '0.010002', 'amount_delta', '0.010000'),
                ('physical_stock', '4.000001', 'physical_stock_delta', '1.000000'),
                ('reserved_stock', '2.000001', 'reserved_stock_delta', '1.000000')):
            with self.subTest(field=field):
                target = copy.deepcopy(source)
                target['records'][0][field] = value
                report = tool.compare(source, target)
                self.assertFalse(report['ok'])
                self.assertEqual([d['delta'] for d in report.get(category, [])], [delta])
        target = copy.deepcopy(source)
        target['records'][6]['net_amount'] = '74.260000'
        target['records'][7]['net_amount'] = '90.240000'
        report = tool.compare(source, target)
        self.assertFalse(report['ok'])
        self.assertEqual(len(report.get('amount_delta', [])), 2, 'equal totals must not hide opposite row deltas')
        self.assertEqual(report.get('amount_groups', {}).get('source'), report.get('amount_groups', {}).get('target'))

    def test_swapped_provenance_fails_even_with_equal_counts_and_totals(self):
        source = load_tool('synthetic').generate(7)
        target = copy.deepcopy(source)
        a, b = target['records'][:2]
        a['internal_id'], b['internal_id'] = b['internal_id'], a['internal_id']
        report = load_tool('reconcile').compare(source, target)
        self.assertFalse(report['ok'])
        self.assertEqual(len(report.get('provenance_mismatch', [])), 2)

    def test_missing_unexpected_and_duplicate_identity_are_not_silent(self):
        source = load_tool('synthetic').generate(7)
        tool = load_tool('reconcile')
        target = copy.deepcopy(source)
        removed = target['records'].pop()
        report = tool.compare(source, target)
        self.assertFalse(report['ok'])
        self.assertEqual(report.get('missing'), [removed['source_id']])
        extra = copy.deepcopy(removed)
        extra['source_id'] += '-EXTRA'
        extra['internal_id'] += '-EXTRA'
        target['records'].append(extra)
        report = tool.compare(source, target)
        self.assertEqual(report.get('unexpected'), [extra['source_id']])
        self.assertEqual(report.get('missing'), [removed['source_id']])
        duplicated = copy.deepcopy(source)
        duplicated['records'].append(copy.deepcopy(source['records'][0]))
        for left, right in ((source, duplicated), (duplicated, source), (duplicated, duplicated)):
            report = tool.compare(left, right)
            self.assertFalse(report['ok'])
            self.assertTrue(report.get('duplicate'), 'duplicates must be rejected even if both inputs agree')
        collision = copy.deepcopy(source)
        collision['records'][1]['internal_id'] = collision['records'][0]['internal_id']
        report = tool.compare(source, collision)
        self.assertTrue(report.get('duplicate'), 'distinct source keys cannot collapse to one internal identity')

    def test_identical_reordered_and_repeated_in_memory_comparison_is_tool_only(self):
        dataset = load_tool('synthetic').generate(7)
        tool = load_tool('reconcile')
        report = tool.compare(dataset, dataset)
        self.assertTrue(report['ok'])
        self.assertEqual(report['matched'], len(dataset['records']))
        self.assertEqual(report['proof'], 'OFFLINE_TOOL_ONLY_NOT_MIGRATION_IDEMPOTENCE')
        reordered = copy.deepcopy(dataset)
        reordered['records'].reverse()
        self.assertEqual(tool.compare(dataset, reordered), report)
        self.assertEqual(tool.compare(dataset, dataset), report)
        self.assertEqual(report['counts']['source'], len(dataset['records']))
        self.assertEqual(report['counts']['target'], len(dataset['records']))


if __name__ == '__main__':
    unittest.main()
