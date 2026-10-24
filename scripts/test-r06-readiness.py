#!/usr/bin/env python3
"""Readiness CLI acceptance: immutable facts, no network, DB or production approval."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IDS = ['OPE01', 'OPE02', 'OPE03', 'OPE04', 'OPE05']


def baseline():
    definitions = []
    for line in (ROOT/'docs/foundation/12-costs-and-operations.md').read_text().splitlines():
        if line.startswith('| OPE'):
            identifier, remit, condition = [v.strip() for v in line.strip('|').split('|')]
            definitions.append({'id': identifier, 'remit': remit, 'condition': condition})
    return {'version': 1, 'purpose': 'ACTUAL', 'requirements': definitions,
            'parent': {'issue': 46, 'state': 'OPEN'},
            'gates': [{'id': g, 'state': 'OPEN', 'target': None, 'scope': None,
                       'proof_ids': [], 'approval_ids': []} for g in IDS],
            'evidence': [], 'approvals': [], 'summary': {'parent_state': 'OPEN', 'r06_complete': False,
              'operational_ready': False, 'ope_states': dict.fromkeys(IDS, 'OPEN')}}


def restore_fact():
    base = 'https://github.com/luigi-pelosi/enginia360'
    head = 'da332f36985b37bd0d5396e214815e2f8bdcd792'
    return {'id': 'R06.b.1', 'kind': 'synthetic',
            'target': 'ephemeral-single-host-surviving-idp',
            'scope': 'all-table-restore-paused-dispatcher-not-DR',
            'pr': 81, 'pr_url': base+'/pull/81', 'head': head,
            'head_url': base+'/commit/'+head,
            'merge': '1761688f4710c373179f5d6087999d13744a3f26',
            'merge_url': base+'/commit/1761688f4710c373179f5d6087999d13744a3f26',
            'tree': 'bc7b9d606e51cd54f9af810b34a4300c96922dab',
            'tree_url': base+'/tree/bc7b9d606e51cd54f9af810b34a4300c96922dab',
            'verification_url': base+'/issues/46#issuecomment-6385112475',
            'runs': [{'id': 40099590231, 'head': head, 'event': 'pull_request', 'conclusion': 'success',
                      'url': base+'/actions/runs/40099590231',
                      'successful_jobs': ['affected-api', 'affected-r06-offline', 'affected-ui', 'impact']},
                     {'id': 40099603224, 'head': head, 'event': 'workflow_dispatch', 'conclusion': 'success',
                      'url': base+'/actions/runs/40099603224',
                      'successful_jobs': ['affected-api', 'affected-browser', 'affected-editor', 'affected-migrations',
                                          'affected-r06-offline', 'affected-r06-restore', 'affected-ui', 'impact']}],
            'claims': ['custom-archive-hash-toc', 'fresh-cluster', 'strict-all-table-readback',
                       'ledger-catalog-prefix-checks', 'scratch-forward-fix', 'TERM-cleanup'],
            'exclusions': ['offhost', 'idp-disaster-recovery', 'RPO', 'RTO', 'PITR', 'SLA',
                           'normal-active-dispatcher-recovery', 'SIGKILL-orchestrator-cleanup',
                           'production-backup', 'fiscal-validity', 'migration-import-idempotence']}


def cli(document):
    with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
        path = Path(tmp)/'registry.json'
        path.write_text(json.dumps(document) if isinstance(document, dict) else document)
        return subprocess.run([sys.executable, '-I', str(ROOT/'scripts/r06_readiness.py'), str(path)],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)


class RegistryTests(unittest.TestCase):
    def test_default_cli_requires_actual_registry_and_both_verified_deliveries(self):
        original = json.loads((ROOT/'docs/r06-readiness-registry.json').read_text())
        for mutation in ('valid', 'missing-fact', 'validation-only'):
            doc = copy.deepcopy(original)
            if mutation == 'missing-fact': doc['evidence'].pop()
            if mutation == 'validation-only': doc['purpose'] = 'VALIDATION_ONLY'
            with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
                root = Path(tmp)
                for name in ('scripts/r06_readiness.py', 'docs/foundation/12-costs-and-operations.md',
                             'docs/r06-recovery-runbook.md', 'docs/r06-migration-inventory.md',
                             'docs/r06-restore-rehearsal.md', 'docs/productization-plan.md', 'docs/productization-backlog.json'):
                    target = root/name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text((ROOT/name).read_text())
                (root/'docs/r06-readiness-registry.json').write_text(json.dumps(doc))
                result = subprocess.run([sys.executable, '-I', str(root/'scripts/r06_readiness.py')],
                                        capture_output=True, text=True, timeout=20)
                with self.subTest(mutation=mutation):
                    self.assertEqual(result.returncode, 0 if mutation == 'valid' else 2,
                                     'default CLI must not hide missing delivery or accept example as actual')

    def test_active_docs_reject_stale_readiness_summary(self):
        spec = importlib.util.spec_from_file_location('readiness_docs', ROOT/'scripts/r06_readiness.py')
        assert spec and spec.loader
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        summary = ('<!-- r06b2-summary:start -->\n'
                   '**Readiness attuale R06.b.2:** OPE01=OPEN; OPE02=OPEN; OPE03=OPEN; OPE04=OPEN; OPE05=OPEN; '
                   '#46 OPEN; R06 NON COMPLETA; nessuna readiness operativa.\n<!-- r06b2-summary:end -->')
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            root = Path(tmp)
            (root/'docs/foundation').mkdir(parents=True)
            (root/'docs/foundation/12-costs-and-operations.md').write_text((ROOT/'docs/foundation/12-costs-and-operations.md').read_text())
            for name in ('r06-migration-inventory.md', 'r06-restore-rehearsal.md', 'productization-plan.md'):
                (root/'docs'/name).write_text('# R06.b.2 — r06-recovery-runbook.md — r06-readiness-registry.json\n')
            (root/'docs/productization-backlog.json').write_text((ROOT/'docs/productization-backlog.json').read_text())
            runbook = root/'docs/r06-recovery-runbook.md'
            runbook.write_text(summary)
            tool.ROOT = root
            doc = baseline()
            tool.validate(doc)
            for mutation in ('OPE03=SATISFIED', 'R06 COMPLETA', 'offhost VERIFIED'):
                runbook.write_text(summary.replace('OPE03=OPEN', mutation))
                with self.subTest(mutation=mutation), self.assertRaises(ValueError, msg='stale active readiness summary accepted'):
                    tool.validate(doc)
            runbook.write_text(summary)
            (root/'docs/r06-restore-rehearsal.md').write_text('# R06 — fully ready\n')
            with self.assertRaises(ValueError, msg='stale active R06 header accepted'):
                tool.validate(doc)

    def test_untrusted_json_is_bounded_strict_and_does_not_echo_input(self):
        doc = baseline()
        unknown = copy.deepcopy(doc)
        unknown['password'] = 'DO-NOT-ECHO-SECRET'
        bad_version = copy.deepcopy(doc)
        bad_version['version'] = 999
        malformed = copy.deepcopy(doc)
        malformed['gates'] = 4
        for bad in (unknown, bad_version, malformed,
                    json.dumps(doc).replace('"version": 1', '"version": 1, "version": 1'),
                    '[1,2]', '{"secret":"DO-NOT-ECHO-SECRET"', ' '*1048577):
            with self.subTest(kind=type(bad).__name__):
                result = cli(bad)
                self.assertEqual(result.returncode, 2, 'unsafe/ambiguous registry input accepted')
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn('DO-NOT-ECHO-SECRET', result.stderr+result.stdout)

    def test_authoritative_ope_definitions_cannot_be_reworded_or_dropped(self):
        for label in ('definition', 'missing', 'duplicate'):
            doc = baseline()
            if label == 'definition': doc['requirements'][2]['condition'] = 'synthetic restore sufficient'
            if label == 'missing': doc['requirements'].pop()
            if label == 'duplicate': doc['requirements'].append(copy.deepcopy(doc['requirements'][0]))
            with self.subTest(mutation=label):
                self.assertEqual(cli(doc).returncode, 2, 'authoritative OPE definitions not enforced')

    def test_summary_and_parent_cannot_claim_passed_from_open_gates(self):
        for label in ('summary-gate', 'ready', 'complete', 'parent', 'partial-without-proof', 'dangling-proof', 'invented-approval'):
            doc = baseline()
            if label == 'summary-gate': doc['summary']['ope_states']['OPE03'] = 'SATISFIED'
            if label == 'ready': doc['summary']['operational_ready'] = True
            if label == 'complete': doc['summary']['r06_complete'] = True
            if label == 'parent': doc['parent']['state'] = 'CLOSED'
            if label == 'partial-without-proof': doc['gates'][0]['state'] = 'PARTIAL'
            if label == 'dangling-proof': doc['gates'][0]['proof_ids'] = ['missing']
            if label == 'invented-approval': doc['approvals'] = [{'id': 'invented', 'reviewer': 'owner'}]
            with self.subTest(mutation=label):
                result = cli(doc)
                self.assertEqual(result.returncode, 2, 'stale or unsupported readiness claim accepted: '+label)
                self.assertIn('refused', result.stderr)

    def test_synthetic_fact_scope_and_delivery_are_immutable(self):
        doc = baseline()
        doc['evidence'] = [restore_fact()]
        self.assertEqual(cli(doc).returncode, 0)
        for label in ('offhost', 'idp-disaster-recovery', 'RPO', 'head', 'tree', 'merge', 'run-head', 'run-id', 'run-url', 'jobs', 'missing-exclusion'):
            bad = copy.deepcopy(doc)
            fact = bad['evidence'][0]
            if label in ('offhost', 'idp-disaster-recovery', 'RPO'): fact['claims'].append(label)
            if label in ('head', 'tree', 'merge'): fact[label] = 'f'*40
            if label == 'run-head': fact['runs'][0]['head'] = 'f'*40
            if label == 'run-id': fact['runs'][0]['id'] = 40097097340
            if label == 'run-url': fact['runs'][0]['url'] += '0'
            if label == 'jobs': fact['runs'][0]['successful_jobs'].append('verify')
            if label == 'missing-exclusion': fact['exclusions'].pop()
            with self.subTest(mutation=label):
                result = cli(bad)
                self.assertEqual(result.returncode, 2, 'synthetic evidence overclaim/mismatch accepted: '+label)
                self.assertIn('refused', result.stderr)

    def test_complete_typed_example_is_validation_only(self):
        doc = baseline()
        doc['purpose'] = 'VALIDATION_ONLY'
        categories = ['destination_quotas', 'encryption_key_recovery', 'daily_checkpoint_transfer',
                      'retention_failure_monitoring', 'offhost_failure_independence', 'end_to_end_restore']
        proofs = [{'id': 'example-'+c, 'kind': 'target_specific', 'category': c,
                   'target': 'VALIDATION-ONLY-TARGET', 'scope': 'VALIDATION-ONLY-SCOPE',
                   'artifact_url': 'https://example.invalid/proof/'+c,
                   'artifact_sha256': 'a'*64, 'outcome': 'VERIFIED'} for c in categories]
        approval = {'id': 'example-approval', 'gate': 'OPE03', 'explicit': True,
                    'target': 'VALIDATION-ONLY-TARGET', 'scope': 'VALIDATION-ONLY-SCOPE',
                    'proof_ids': [p['id'] for p in proofs], 'reviewer_role': 'owner',
                    'decision_url': 'https://example.invalid/approved/OPE03',
                    'approved_on': '2026-10-24',
                    'proof_digest': hashlib.sha256(json.dumps(proofs, sort_keys=True).encode()).hexdigest()}
        doc['evidence'] = proofs
        doc['approvals'] = [approval]
        gate = doc['gates'][2]
        gate.update(state='SATISFIED', target=approval['target'], scope=approval['scope'],
                    proof_ids=approval['proof_ids'], approval_ids=[approval['id']])
        doc['summary']['ope_states']['OPE03'] = 'SATISFIED'
        result = cli(doc)
        self.assertEqual(result.returncode, 0, 'complete typed validation-only example rejected: '+result.stderr)
        self.assertIn('VALIDATION_ONLY', result.stdout)
        for label in ('category', 'target', 'scope', 'digest', 'explicit', 'provenance', 'date', 'synthetic', 'missing', 'production', 'proof-url-type', 'approval-url-type'):
            bad = copy.deepcopy(doc)
            if label == 'category': bad['evidence'][0]['category'] = 'arbitrary'
            if label == 'target': bad['evidence'][0]['target'] = 'another-target'
            if label == 'scope': bad['evidence'][0]['scope'] = 'another-scope'
            if label == 'digest': bad['approvals'][0]['proof_digest'] = 'b'*64
            if label == 'explicit': bad['approvals'][0]['explicit'] = False
            if label == 'provenance': bad['approvals'][0]['decision_url'] = 'arbitrary'
            if label == 'date': bad['approvals'][0]['approved_on'] = 'yesterday'
            if label == 'synthetic': bad['evidence'][0]['kind'] = 'synthetic'
            if label == 'missing': bad['gates'][2]['proof_ids'].pop()
            if label == 'production': bad['purpose'] = 'ACTUAL'
            if label == 'proof-url-type': bad['evidence'][0]['artifact_url'] = None
            if label == 'approval-url-type': bad['approvals'][0]['decision_url'] = None
            with self.subTest(mutation=label):
                result = cli(bad)
                self.assertEqual(result.returncode, 2, 'invalid typed proof accepted: '+label)
                self.assertIn('refused', result.stderr)

    def test_satisfied_without_typed_proof_and_synthetic_gate_links_are_refused(self):
        # Regression coverage of the implemented fail-closed approval boundary.
        for gate_id in IDS:
            for kind in ('empty', 'synthetic'):
                doc = baseline()
                doc['evidence'] = [restore_fact()]
                gate = next(g for g in doc['gates'] if g['id'] == gate_id)
                gate.update(state='SATISFIED', target='some-target', scope='pilot',
                            proof_ids=[] if kind == 'empty' else ['R06.b.1'])
                doc['summary']['ope_states'][gate_id] = 'SATISFIED'
                with self.subTest(gate=gate_id, kind=kind):
                    result = cli(doc)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn('refused', result.stderr)

    def test_arbitrary_review_fields_never_approve_an_operational_gate(self):
        for gate_id in IDS:
            doc = baseline()
            gate = next(g for g in doc['gates'] if g['id'] == gate_id)
            gate.update(state='SATISFIED', target='some-target', scope='pilot',
                        reviewer='somebody', date='2026-10-24', evidence_id='arbitrary')
            with self.subTest(gate=gate_id):
                result = cli(doc)
                self.assertEqual(result.returncode, 2, 'arbitrary review metadata accepted as operational proof')
                self.assertIn('refused', result.stderr)

    def test_exact_finite_gate_coverage(self):
        result = cli(baseline())
        self.assertEqual(result.returncode, 0, 'valid OPEN registry must validate: '+result.stderr)
        for mutation in ('missing', 'duplicate', 'unknown'):
            doc = baseline()
            if mutation == 'missing': doc['gates'].pop()
            if mutation == 'duplicate': doc['gates'].append(copy.deepcopy(doc['gates'][0]))
            if mutation == 'unknown': doc['gates'][0]['id'] = 'OPE99'
            with self.subTest(mutation=mutation):
                result = cli(doc)
                self.assertEqual(result.returncode, 2)
                self.assertIn('gate coverage', result.stderr)


if __name__ == '__main__':
    unittest.main()
