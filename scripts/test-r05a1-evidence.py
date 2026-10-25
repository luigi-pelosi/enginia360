#!/usr/bin/env python3
"""Test-first documentary acceptance; no fake provider payloads."""
from pathlib import Path
import copy
import importlib.util
import json
import unittest
ROOT=Path(__file__).resolve().parents[1]
class EvidenceTests(unittest.TestCase):
    def test_dossier_artifacts_exist_before_positive_claims(self):
        for path in ['docs/r05a1-evidence.json','docs/r05a1-giobby-read-contract.md','docs/r05a1-provider-questions.md','scripts/r05a1_evidence.py']:
            self.assertTrue((ROOT/path).is_file(), 'missing bounded dossier artifact: '+path)
    def validator(self):
        spec=importlib.util.spec_from_file_location('evidence',ROOT/'scripts/r05a1_evidence.py')
        assert spec and spec.loader
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module
    def matrix(self): return json.loads((ROOT/'docs/r05a1-evidence.json').read_text())
    def test_baseline_consistency(self): self.validator().validate(self.matrix(),ROOT)
    def test_supported_claim_requires_pointer_and_hash(self):
        module=self.validator()
        for field in ['pointer','extract_sha256','source_sha256','primary_url']:
            data=self.matrix(); del next(x for x in data['claims'] if x['status']=='fact')[field]
            with self.subTest(field=field),self.assertRaises(ValueError): module.validate(data,ROOT)
    def test_unknown_response_never_becomes_supported(self):
        data=self.matrix(); next(x for x in data['claims'] if x['scope']=='read-response')['status']='fact'
        with self.assertRaises(ValueError): self.validator().validate(data,ROOT)
    def test_authority_no_backdoor(self):
        for field in ['mixed_writer','local_fallback','local_receipt_writer','automatic_switch','retroactive_switch']:
            data=self.matrix(); data['boundary'][field]=True
            with self.subTest(field=field),self.assertRaises(ValueError): self.validator().validate(data,ROOT)
    def test_missing_schema_blocks_current_contract(self):
        for field in ['provider_contract_ready','r04_complete','r05_complete','operational_ready','runtime_setup_enforced','contains_provider_payloads']:
            data=self.matrix(); data['boundary'][field]=True
            with self.subTest(field=field),self.assertRaises(ValueError): self.validator().validate(data,ROOT)
    def test_evidence_tamper_and_unknown_removal_fail(self):
        data=self.matrix(); data['claims'][0]['extract']='tampered'
        with self.assertRaises(ValueError): self.validator().validate(data,ROOT)
        data=self.matrix(); data['claims']=[x for x in data['claims'] if x['status']!='unknown']
        with self.assertRaises(ValueError): self.validator().validate(data,ROOT)
    def test_fabricated_payload_keys_rejected(self):
        for field in ['provider_payload', 'fixtures', 'response_examples']:
            data=self.matrix(); data[field]='invented-marker-not-provider-data'
            with self.subTest(field=field),self.assertRaises(ValueError): self.validator().validate(data,ROOT)
    def test_positive_completion_text_rejected(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) as directory:
            root=Path(directory); (root/'docs').mkdir()
            for name in ['r05a1-giobby-read-contract.md','r05a1-provider-questions.md']:
                (root/'docs'/name).write_text((ROOT/'docs'/name).read_text())
            path=root/'docs/r05a1-giobby-read-contract.md'
            original=path.read_text()
            for claim in ['R05 complete', 'R04 complete', 'operational readiness verified', 'local fallback allowed']:
                path.write_text(original+'\n'+claim)
                with self.subTest(claim=claim),self.assertRaises(ValueError): self.validator().validate(self.matrix(),root)
    def test_offline_cli_no_provider_or_network(self):
        import subprocess
        result=subprocess.run(['python3','-I',str(ROOT/'scripts/r05a1_evidence.py'),'--check'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('provider compatibility NOT proven',result.stdout)
if __name__=='__main__': unittest.main()
