#!/usr/bin/env python3
"""Offline guards over sanitized observations, NOT a provider response parser."""
import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT/'docs/r05a2-evidence.json'
NO_MUTATIONS = False
EXPECTED = {'/loggeduser', '/storages', '/storageLocations', '/um', '/products',
            '/stocks/avaibility', '/purchases/orders', '/purchases/goodsreceipt',
            '/purchases/{id}/orders', '/purchases/{id}/goodsreceipt', '/settings',
            '/businessunit', '/plugins/archivium/{idBu}/settings', '/swagger/swagger.json'}

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

class EvidenceTests(unittest.TestCase):
    def matrix(self):
        self.assertTrue(MATRIX.is_file(), 'actual sanitized sandbox evidence is missing')
        return json.loads(MATRIX.read_text())

    def test_observation_provenance_and_finite_request_scope(self):
        data = self.matrix()
        self.assertEqual(data['increment'], 'R05.a.2')
        self.assertEqual(data['status'], 'OBSERVED_READS_WRITE_SAFETY_BLOCKED')
        obs = data['observations']
        self.assertEqual({o['template'] for o in obs}, EXPECTED)
        self.assertEqual(len(obs), len(EXPECTED), 'no implicit export or repeated acquisition')
        for o in obs:
            self.assertEqual(o['method'], 'GET')
            self.assertEqual(o['http_status'], 200)
            self.assertRegex(o['response_sha256'], r'^[a-f0-9]{64}$')
            self.assertGreater(o['response_bytes'], 0)
            self.assertEqual(datetime.datetime.fromisoformat(o['timestamp_utc']).utcoffset(), datetime.timedelta())
            self.assertEqual(o['evidence_class'], 'public-static-declaration' if o['template']=='/swagger/swagger.json' else 'observed-in-this-sandbox')
            self.assertEqual(o['shape_sha256'], canonical_hash(o['field_types']))
            self.assertEqual(set(o), {'method','template','query','http_status','response_sha256','response_bytes','content_type','timestamp_utc','evidence_class','field_types','business_status','shape_sha256'})
            for pointer, kind in o['field_types'].items():
                self.assertTrue(pointer.startswith('/'))
                self.assertIn(kind, {'object','array','string','integer','number','boolean','null'})
            if 'limit' in o['query']:
                self.assertEqual(o['query'], {'limit':1,'offset':0})
            self.assertNotRegex(o['template'], r'/purchases/\d+/|/archivium/[^{}]+/settings')

    def test_actual_shape_distinctions_not_request_models(self):
        obs = {o['template']:o for o in self.matrix()['observations']}
        user = obs['/loggeduser']['field_types']
        self.assertEqual(user['/cid'], 'string'); self.assertEqual(user['/idCompany'], 'integer')
        self.assertNotIn('/responseCode', user, 'loggeduser is a plain object, not an envelope')
        for path, key in (('/storages','storages'),('/storageLocations','storageLocations'),('/um','ums'),('/products','products'),('/stocks/avaibility','stocks'),('/purchases/orders','documentsHeaders'),('/purchases/goodsreceipt','documentsHeaders')):
            self.assertEqual(obs[path]['field_types']['/'+key], 'array')
            self.assertEqual(obs[path]['business_status'], {'responseCode':200,'errorCode':0})
        for suffix in ('orders','goodsreceipt'):
            fields = obs['/purchases/{id}/'+suffix]['field_types']
            self.assertEqual(fields['/document/id'], 'integer')
            self.assertEqual(fields['/document/rows/0/idPos'], 'integer')
        order = obs['/purchases/{id}/orders']['field_types']
        receipt = obs['/purchases/{id}/goodsreceipt']['field_types']
        self.assertEqual(order['/document/rows/0/quantity'], 'null', 'observed null must not become zero or required number')
        self.assertEqual(receipt['/document/rows/0/quantity'], 'number')
        self.assertEqual(order['/document/rows/0/idMaterial'], 'null')
        self.assertEqual(receipt['/document/rows/0/idMaterial'], 'string')

    def test_authority_safety_and_evidence_classes_remain_bounded(self):
        data = self.matrix()
        self.assertEqual(data['authorization']['decision'], 'D83')
        self.assertEqual(data['authorization']['realm'], 'api-server')
        self.assertEqual(data['authorization']['token_endpoint'], 'https://auth.giobby.com/auth/realms/api-server/protocol/openid-connect/token')
        self.assertTrue(data['authentication']['cid_matches_private_context'])
        self.assertTrue(data['authentication']['company_matches_jwt'])
        self.assertEqual(set(data['authentication']['permissions'].values()), {True})
        self.assertEqual(data['safety']['outbound_safety'], 'NOT_ESTABLISHED')
        self.assertEqual(data['safety']['sdi_disabled'], 'owner-assertion-not-independent-guarantee')
        self.assertFalse(data['safety']['settings_mutated'])
        self.assertEqual(data['ledger'], {'run_prefix':'E360-SB-R05A2-20261027','writes':[],'objects':[]})
        self.assertEqual(set(data['scenarios'].values()), {'blocked-before-first-write'})
        for name in ('provider_schema_guaranteed','positive_adapter','stock_semantics_proved','partial_receipt_proved','persistent_invoice_draft_proved','safe_replay_proved','r04_complete','r05_complete','operational_ready'):
            self.assertIs(data['claims'][name], False, name)
        self.assertEqual(data['shape_scope'], 'first array item only; observed types, not requiredness, nullability guarantee, completeness or supported schema')
        self.assertEqual(data['capture_policy'], 'raw business bytes not retained; hashes cover original bytes; no synthetic provider payload')

    def test_dossier_and_active_decision(self):
        self.matrix()
        path = ROOT/'docs/r05a2-sandbox-contract.md'
        self.assertTrue(path.is_file(), 'finite research dossier missing')
        text = path.read_text()
        for token in ('D83','NOT_ESTABLISHED','3 ordinati / 2 ricevuti','D79','nessun adapter','osservazione sandbox','garanzia provider','zero oggetti'):
            self.assertIn(token.lower(), text.lower())
        decisions = (ROOT/'docs/foundation/01-glossary-and-domain-boundaries.md').read_text()
        ids = list(map(int,re.findall(r'^### D(\d+) —',decisions,re.M)))
        self.assertEqual(sorted(ids), list(range(1,85)))
        d83 = decisions.split('### D83 —')[-1].split('### D84 —')[0]
        for token in ('27 ottobre 2026','api-server','sandbox','SdI','D82','nessun invio esterno'):
            self.assertIn(token,d83)

    def test_cli_mutations_reject_false_positive_evidence(self):
        if NO_MUTATIONS: return
        data = self.matrix()
        mutations = [lambda d:d['claims'].__setitem__('positive_adapter',True),
                     lambda d:d['safety'].__setitem__('outbound_safety','SAFE'),
                     lambda d:d['authorization'].__setitem__('realm','api-client'),
                     lambda d:d['observations'][0].__setitem__('evidence_class','provider-guarantee'),
                     lambda d:d['observations'][0].__setitem__('response_sha256',''),
                     lambda d:d['observations'][0]['field_types'].__setitem__('/responseCode','integer'),
                     lambda d:d['ledger']['objects'].append('unverified-object'),
                     lambda d:d['observations'][0].__setitem__('raw_body','forbidden')]
        with tempfile.TemporaryDirectory(prefix='r05a2-',dir=__import__('os').environ.get('TMPDIR',tempfile.gettempdir())) as temp:
            path = Path(temp)/'matrix.json'
            for mutate in mutations:
                changed = copy.deepcopy(data); mutate(changed);path.write_text(json.dumps(changed))
                result = subprocess.run([sys.executable,'-I',__file__,'--matrix',str(path),'--no-mutations'],capture_output=True,text=True,timeout=20)
                self.assertEqual(result.returncode,1,'guard accepted tampered observation')
                self.assertIn('FAIL:',result.stderr)
                self.assertNotIn('ERROR:',result.stderr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix',type=Path,default=MATRIX)
    parser.add_argument('--no-mutations',action='store_true')
    args, remaining = parser.parse_known_args()
    MATRIX = args.matrix; NO_MUTATIONS = args.no_mutations
    unittest.main(argv=[sys.argv[0],*remaining])
