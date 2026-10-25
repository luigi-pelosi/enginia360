#!/usr/bin/env python3
"""Offline documentary provenance only; never fetches or calls an ERP."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {'read-response', 'stock-meaning', 'company-identity', 'pagination-consistency',
          'delta-cancellation', 'permissions'}
FALSE_BOUNDARIES = ('mixed_writer', 'local_fallback', 'local_receipt_writer',
                    'automatic_switch', 'retroactive_switch', 'provider_contract_ready',
                    'r04_complete', 'r05_complete', 'operational_ready',
                    'runtime_setup_enforced', 'contains_provider_payloads')
READ_PATHS = ('/stocks/avaibility', '/stocks/avaibility/report', '/storages', '/storageLocations',
              '/storages/{id}', '/products', '/products/{id}', '/um', '/um/{idUm}',
              '/businessunit/{idBu}/storage', '/businessunitpoint/{idBup}/storage',
              '/purchases/orders', '/purchases/{id}/orders',
              '/purchases/goodsreceipt', '/purchases/{id}/goodsreceipt')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def pointer(document, location):
    require(location.startswith('#/'), 'absolute JSON pointer required')
    value = document
    for token in location[2:].split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def validate(data, root):
    require(set(data) == {'increment', 'status', 'boundary', 'sources', 'claims',
                          'required_unknown_scopes', 'private_manifest', 'probe'},
            'unrecognized dossier field or fabricated payload')
    require(data.get('increment') == 'R05.a.1', 'increment changed')
    require(data.get('status') == 'BLOCKED_PROVIDER_READ_SCHEMA', 'current contract is blocked')
    boundary = data.get('boundary', {})
    for field in FALSE_BOUNDARIES:
        require(boundary.get(field) is False, 'unsafe authority/readiness/payload claim: '+field)
    require(boundary.get('stock_authority') == 'same-external-ERP-as-purchasing', 'D82 mismatch')
    require(boundary.get('master_authority') == 'single-tenant-wide-D26-D65', 'master mismatch')
    require(boundary.get('partial_receipt') == '3 ordered / 2 received: conditional on authority, not local ERP-profile write permission', 'conditional partial receipt changed')
    sources = {}
    for source in data['sources']:
        url = source['url']; parsed = urlsplit(url)
        require(parsed.scheme == 'https' and parsed.hostname in ('app.giobby.com', 'www.giobby.com'), 'official primary source required')
        require(source['status'] == 200 and source['content_type'].split(';')[0] in ('text/html', 'application/json'), 'not static documentary evidence')
        require(re.fullmatch('[a-f0-9]{64}', source['sha256']) is not None, 'source hash required')
        require(source['sha256'] in source['private_path'] and source['private_path'].startswith('/root/.hermes/cache/scratch/R05a1-public/'), 'private immutable extract path required')
        require(source['accessed_at'].startswith('2026-10-25T'), 'acquisition date missing')
        require(url not in sources, 'duplicate source')
        sources[url] = source
    ids = set(); unknown_scopes = set(); response_paths = set()
    for claim in data['claims']:
        require(claim['id'] not in ids, 'duplicate claim'); ids.add(claim['id'])
        require(claim['status'] in ('fact', 'unknown'), 'unsupported certainty')
        source = sources.get(claim.get('primary_url'))
        require(source is not None and claim.get('source_sha256') == source['sha256'], 'claim source/hash missing or inconsistent')
        require(isinstance(claim.get('pointer'), str) and claim['pointer'].startswith('#/'), 'claim pointer missing')
        require(claim.get('extract_sha256') == digest(claim.get('extract')), 'extract hash missing or inconsistent')
        require(bool(claim.get('meaning')), 'scope/meaning missing')
        if claim['status'] == 'unknown': unknown_scopes.add(claim['scope'])
        if claim['scope'] == 'read-response':
            require(claim['status'] == 'unknown', 'unknown response schema cannot be supported')
            require(claim['extract'] == {'default': {'description': 'successful operation'}}, 'response evidence changed; review gate, do not infer support')
            response_paths.add(claim['pointer'])
        elif claim['status'] == 'fact':
            require(claim['scope'] in ('read-request', 'model-declaration', 'write-schema-context-only'), 'READ field support requires an actual response schema')
    required_responses = {'#/paths/'+p.replace('~', '~0').replace('/', '~1')+'/get/responses' for p in READ_PATHS}
    require(response_paths == required_responses, 'finite READ response gap coverage missing')
    require(SCOPES <= unknown_scopes and set(data['required_unknown_scopes']) == SCOPES, 'required unknowns cannot be filled or removed')
    for path, tokens in {
        'docs/r05a1-giobby-read-contract.md': ('BLOCKED_PROVIDER_READ_SCHEMA', 'D82', 'R04 e R05 restano incompleti', 'Nessuna scrittura locale di ricevimento', 'non compatibilità provider', '3 ordinati / 2 ricevuti'),
        'docs/r05a1-provider-questions.md': ('NON inviata', 'P1', 'P2', 'P3', 'P4', 'P5', 'BLOCKED_PROVIDER_READ_SCHEMA'),
    }.items():
        text = (root/path).read_text()
        for token in tokens: require(token in text, 'required documentary boundary missing: '+token)
        for forbidden in ('R05 complete', 'R04 complete', 'operational readiness verified', 'local fallback allowed'):
            require(forbidden not in text, 'unsupported completion/authority assertion: '+forbidden)


def probe_assets(data, directory):
    """Verify real acquired static bytes; no network, synthetic responses or skip."""
    documents = {}
    for source in data['sources']:
        suffix = '.json' if source['content_type'] == 'application/json' else '.html'
        raw = (directory/(source['sha256']+suffix)).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == source['sha256'], 'acquired source hash differs')
        require(len(raw) == source['bytes'], 'source byte count differs')
        if suffix == '.json': documents[source['url']] = json.loads(raw)
    for claim in data['claims']:
        actual = pointer(documents[claim['primary_url']], claim['pointer'])
        require(actual == claim['extract'] and digest(actual) == claim['extract_sha256'], 'source pointer/extract mismatch: '+claim['id'])
    return len(data['claims'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--assets', type=Path)
    args = parser.parse_args()
    data = json.loads((ROOT/'docs/r05a1-evidence.json').read_text())
    validate(data, ROOT)
    print('PASS documentary consistency; provider compatibility NOT proven; contract BLOCKED_PROVIDER_READ_SCHEMA')
    if args.assets:
        print(f'PASS {probe_assets(data, args.assets)} exact pointers against acquired private static assets; no provider response exercised')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        print('FAIL documentary evidence: '+str(error), file=sys.stderr)
        sys.exit(2)
