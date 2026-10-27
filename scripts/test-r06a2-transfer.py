#!/usr/bin/env python3
"""Pure offline guards for the staging-only envelope. Runtime proof is test-r06a2-storage.py."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transfer = load('r06a2_transfer.py')
synth = transfer.synthetic


def sample():
    return transfer.envelope(synth.generate(7))


def resign(document):
    document['sha256'] = synth.digest({k: v for k, v in document.items() if k != 'sha256'})
    return document


class EnvelopeGuards(unittest.TestCase):
    def parse(self, document):
        return transfer.parse(synth.canonical(document) if not isinstance(document, bytes) else document)

    def test_valid_envelope_has_provenance_q6_counts_checksum_and_staging_label(self):
        document = sample()
        parsed = self.parse(document)
        self.assertEqual(parsed, document)
        self.assertEqual(document['format'], 'R06A2_STAGING_ONLY_V1')
        self.assertEqual(document['counts'], {'records': 8, 'by_kind': {'Part': 4, 'Service': 4}})
        self.assertEqual(document['context']['authority'], 'STAGING_PROBES_ONLY_NO_DOMAIN_AUTHORITY')
        self.assertTrue(all('.' in r['quantity'] and len(r['quantity'].split('.')[1]) == 6 for r in document['dataset']['records']))

    def test_unsupported_version_unknown_fields_oversize_and_duplicate_keys_are_rejected(self):
        base = sample()
        cases = []
        for value in ('R06A2_STAGING_ONLY_V2', 'SYNTH_INVALID_FOR_PRODUCTION_V1', 1):
            cases.append(resign(dict(copy.deepcopy(base), format=value)))
        cases.append(dict(copy.deepcopy(base), surprise=1))
        cases.append(resign(dict(copy.deepcopy(base), revision=0)))
        cases.append(resign(dict(copy.deepcopy(base), revision=True)))
        cases.append(resign(dict(copy.deepcopy(base), source_system='REAL-ERP')))
        cases.append(resign(dict(copy.deepcopy(base), batch_id='x' * 200)))
        for index, document in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.parse(document)
        with self.assertRaises(ValueError):
            self.parse(b'{' + b' ' * transfer.MAX_BYTES + b'}')
        raw = synth.canonical(base).decode()
        with self.assertRaises(ValueError):
            self.parse(raw[:-2].encode() + b',"format":"R06A2_STAGING_ONLY_V1"}\n')
        for payload in (b'', b'[]', b'\xff', b'{', b'{"format":NaN}'):
            with self.assertRaises(ValueError):
                self.parse(payload)

    def test_checksum_counts_and_record_limit_are_enforced(self):
        base = sample()
        tampered = copy.deepcopy(base)
        tampered['dataset']['records'][0]['net_amount'] = '9.000000'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.parse(tampered)
        for field, value in (('records', 7), ('by_kind', {'Part': 8})):
            changed = copy.deepcopy(base)
            changed['counts'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'count'):
                self.parse(resign(changed))
        many = copy.deepcopy(base)
        many['dataset']['records'] = [copy.deepcopy(many['dataset']['records'][0]) for _ in range(transfer.MAX_RECORDS + 1)]
        many['counts'] = {'records': len(many['dataset']['records']), 'by_kind': {'Service': len(many['dataset']['records'])}}
        with self.assertRaises(ValueError):
            self.parse(resign(many))

    def test_numeric_values_must_be_canonical_q6_decimal_strings(self):
        base = sample()
        for field, value in (('quantity', '1'), ('quantity', '1.0'), ('unit_price', '1e2'), ('quantity', 1.0), ('net_amount', 'NaN'),
                             ('net_amount', '-0.000001'), ('physical_stock', '1000000000000.000000'), ('discount_percent', '10.250000'),
                             ('reserved_stock', '1,000000'), ('tax_rate', '22.000001')):
            changed = copy.deepcopy(base)
            changed['dataset']['records'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.parse(resign(changed))

    def test_identity_scope_and_duplicate_keys_are_rejected_before_storage(self):
        base = sample()
        for field, value in (('source_id', 'REAL-1'), ('tenant_id', '123'), ('fiscal_identifier', 'RSSMRA80A01H501U')):
            changed = copy.deepcopy(base)
            changed['dataset']['records'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse(resign(changed))
        duplicate = copy.deepcopy(base)
        duplicate['dataset']['records'].append(copy.deepcopy(duplicate['dataset']['records'][0]))
        duplicate['counts'] = {'records': 9, 'by_kind': {'Part': 4, 'Service': 5}}
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.parse(resign(duplicate))
        context = copy.deepcopy(base)
        context['context']['scopes'].pop()
        with self.assertRaisesRegex(ValueError, 'scope'):
            self.parse(resign(context))
        context = copy.deepcopy(base)
        context['context']['authority'] = 'ERP_AUTHORITATIVE'
        with self.assertRaisesRegex(ValueError, 'authority'):
            self.parse(resign(context))

if __name__ == '__main__':
    unittest.main()
