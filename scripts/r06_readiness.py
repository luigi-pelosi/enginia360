#!/usr/bin/env python3
"""Offline consistency guard, not an approval authority or live readiness assessment."""
import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
IDS = ('OPE01', 'OPE02', 'OPE03', 'OPE04', 'OPE05')


REPO_URL = 'https://github.com/luigi-pelosi/enginia360'
# Read back from merged PRs, git trees, exact-head Actions jobs and #46 comments.
# Historical immutable facts only; changing a JSON claim cannot change their scope.
DELIVERIES = {
    'R06.a.1': (77, '03bed79af6ffd9a6495c09dbeaafc1ae185a9a9c',
                'fe6ea5c1403056b4069f57ecd8050cb7f65c80a9', 'd03cf6b58ef951d5f80fc00cbdfa8a8c504cc4b7',
                [(40075451477, 'pull_request', ['affected-r06-offline', 'impact'])],
                'offline-synthetic-probes', 'matching-only-not-import',
                ['manifest-inventory', 'deterministic-probes', 'in-memory-reconciliation'],
                ['import-export-roundtrip', 'migration-import-idempotence', 'fiscal-validity', 'operational-readiness']),
    'R06.b.1': (81, 'da332f36985b37bd0d5396e214815e2f8bdcd792',
                '1761688f4710c373179f5d6087999d13744a3f26', 'bc7b9d606e51cd54f9af810b34a4300c96922dab',
                [(40099590231, 'pull_request', ['affected-api', 'affected-r06-offline', 'affected-ui', 'impact']),
                 (40099603224, 'workflow_dispatch', ['affected-api', 'affected-browser', 'affected-editor', 'affected-migrations',
                                                   'affected-r06-offline', 'affected-r06-restore', 'affected-ui', 'impact'])],
                'ephemeral-single-host-surviving-idp', 'all-table-restore-paused-dispatcher-not-DR',
                ['custom-archive-hash-toc', 'fresh-cluster', 'strict-all-table-readback',
                 'ledger-catalog-prefix-checks', 'scratch-forward-fix', 'TERM-cleanup'],
                ['offhost', 'idp-disaster-recovery', 'RPO', 'RTO', 'PITR', 'SLA', 'normal-active-dispatcher-recovery',
                 'SIGKILL-orchestrator-cleanup', 'production-backup', 'fiscal-validity', 'migration-import-idempotence']),
}


def known_fact(identifier):
    pr, head, merge, tree, runs, target, scope, claims, exclusions = DELIVERIES[identifier]
    return {'id': identifier, 'kind': 'synthetic', 'target': target, 'scope': scope,
            'pr': pr, 'pr_url': REPO_URL+'/pull/'+str(pr), 'head': head, 'head_url': REPO_URL+'/commit/'+head,
            'merge': merge, 'merge_url': REPO_URL+'/commit/'+merge, 'tree': tree, 'tree_url': REPO_URL+'/tree/'+tree,
            'verification_url': REPO_URL+'/issues/46#issuecomment-'+('6381666054' if identifier == 'R06.a.1' else '6385112475'),
            'runs': [{'id': n, 'head': head, 'event': event, 'conclusion': 'success',
                      'url': REPO_URL+'/actions/runs/'+str(n), 'successful_jobs': jobs} for n, event, jobs in runs],
            'claims': claims, 'exclusions': exclusions}


REQUIRED = {
    'OPE01': ('name_extension_registrar', 'initial_renewal_tax_extras', 'purchase_authorization', 'dns_control'),
    'OPE02': ('implementation_scope', 'identity_resources_transport', 'protocols_mfa', 'revocation_recovery', 'identity_maintenance'),
    'OPE03': ('destination_quotas', 'encryption_key_recovery', 'daily_checkpoint_transfer',
              'retention_failure_monitoring', 'offhost_failure_independence', 'end_to_end_restore'),
    'OPE04': ('coverage_timezone_holidays', 'rto_boundaries', 'smtp_received', 'backup_patch_identity_roles'),
    'OPE05': ('target_country_contracts', 'data_destinations', 'actual_costs_quotas_capacity', 'recovery_resources_tests'),
}
# No target-specific operational evidence/approval has been approved. Future additions
# require traced review of this trust catalog, not self-attestation inside input JSON.
APPROVED_TARGET_PROOFS = ()
APPROVED_TARGET_APPROVALS = ()


def unique_records(records):
    result = {r['id']: r for r in records}
    if len(result) != len(records):
        raise ValueError('duplicate evidence/approval id')
    return result


def validate_claim(gate, evidence, approvals, example):
    proof_ids, approval_ids = gate['proof_ids'], gate['approval_ids']
    if len(set(proof_ids)) != len(proof_ids) or len(set(approval_ids)) != len(approval_ids):
        raise ValueError('duplicate gate proof/approval reference')
    proofs = [evidence[p] for p in proof_ids]
    decisions = [approvals[p] for p in approval_ids]
    if not example and (any(p not in APPROVED_TARGET_PROOFS for p in proofs)
                        or any(a not in APPROVED_TARGET_APPROVALS for a in decisions)):
        raise ValueError('unapproved target proof or approval provenance')
    if sorted(p['category'] for p in proofs) != sorted(REQUIRED[gate['id']]):
        raise ValueError('required typed evidence categories incomplete')
    if not gate['target'] or not gate['scope']:
        raise ValueError('target and scope required')
    if example and (gate['target'] != 'VALIDATION-ONLY-TARGET' or gate['scope'] != 'VALIDATION-ONLY-SCOPE'):
        raise ValueError('example is not operational evidence')
    for proof in proofs:
        if set(proof) != {'id', 'kind', 'category', 'target', 'scope', 'artifact_url', 'artifact_sha256', 'outcome'}:
            raise ValueError('typed proof fields')
        if proof['kind'] != 'target_specific' or proof['outcome'] != 'VERIFIED':
            raise ValueError('synthetic or unverified proof cannot satisfy operational categories')
        if (proof['target'], proof['scope']) != (gate['target'], gate['scope']):
            raise ValueError('proof target/scope mismatch')
        prefix = 'https://example.invalid/proof/' if example else 'https://github.com/luigi-pelosi/enginia360/'
        if not isinstance(proof['artifact_url'], str) or not proof['artifact_url'].startswith(prefix) or not re.fullmatch('[0-9a-f]{64}', proof['artifact_sha256']):
            raise ValueError('proof artifact provenance invalid')
    digest = hashlib.sha256(json.dumps(proofs, sort_keys=True).encode()).hexdigest()
    if not decisions:
        raise ValueError('explicit owner approval required')
    for approval in decisions:
        if set(approval) != {'id', 'gate', 'explicit', 'target', 'scope', 'proof_ids', 'reviewer_role', 'decision_url', 'approved_on', 'proof_digest'}:
            raise ValueError('approval fields')
        if (approval['gate'], approval['target'], approval['scope']) != (gate['id'], gate['target'], gate['scope']):
            raise ValueError('approval target/scope mismatch')
        if approval['explicit'] is not True or approval['reviewer_role'] != 'owner':
            raise ValueError('explicit owner approval required, not reviewer/date alone')
        prefix = 'https://example.invalid/approved/' if example else 'https://github.com/luigi-pelosi/enginia360/'
        if not isinstance(approval['decision_url'], str) or not approval['decision_url'].startswith(prefix) or approval['proof_ids'] != proof_ids or approval['proof_digest'] != digest:
            raise ValueError('approval provenance does not cover exact evidence')
        if datetime.date.fromisoformat(approval['approved_on']).isoformat() != approval['approved_on']:
            raise ValueError('approval date invalid')


def authoritative_requirements():
    rows = []
    for line in (ROOT/'docs/foundation/12-costs-and-operations.md').read_text().splitlines():
        if line.startswith('| OPE'):
            identifier, remit, condition = [v.strip() for v in line.strip('|').split('|')]
            rows.append({'id': identifier, 'remit': remit, 'condition': condition})
    if [r['id'] for r in rows] != list(IDS):
        raise ValueError('authoritative OPE source coverage changed')
    return rows


def validate(document):
    if set(document) != {'version', 'purpose', 'requirements', 'parent', 'gates', 'evidence', 'approvals', 'summary'} or type(document['version']) is not int or document['version'] != 1:
        raise ValueError('registry schema/version invalid')
    if document['requirements'] != authoritative_requirements():
        raise ValueError('authoritative OPE definitions mismatch')
    gates = document['gates']
    if sorted(g['id'] for g in gates) != list(IDS):
        raise ValueError('gate coverage must be exactly OPE01-OPE05')
    if document['purpose'] not in ('ACTUAL', 'VALIDATION_ONLY'):
        raise ValueError('purpose invalid')
    example = document['purpose'] == 'VALIDATION_ONLY'
    evidence = unique_records(document['evidence'])
    approvals = unique_records(document.get('approvals', []))
    for fact in evidence.values():
        if fact.get('kind') == 'synthetic':
            if fact['id'] not in DELIVERIES or fact != known_fact(fact['id']):
                raise ValueError('synthetic evidence scope or commit/CI identity mismatch')
        elif not example and fact not in APPROVED_TARGET_PROOFS:
            raise ValueError('no approved target evidence recorded')
    if document['parent'] != {'issue': 46, 'state': 'OPEN'}:
        raise ValueError('current parent snapshot must remain OPEN')
    if not example and any(a not in APPROVED_TARGET_APPROVALS for a in approvals.values()):
        raise ValueError('unrecognized approval provenance')
    for gate in gates:
        if set(gate) != {'id', 'state', 'target', 'scope', 'proof_ids', 'approval_ids'}:
            raise ValueError('gate fields refused')
        if gate['state'] not in ('OPEN', 'PARTIAL', 'SATISFIED'):
            raise ValueError('unknown gate state')
        if gate['state'] == 'SATISFIED':
            validate_claim(gate, evidence, approvals, example)
        elif gate['state'] == 'OPEN':
            if gate['proof_ids'] or gate['approval_ids'] or gate['target'] is not None or gate['scope'] is not None:
                raise ValueError('OPEN gate cannot hide proof or target claims')
        else:
            # Partial is only for approved target-specific subsets, never linked synthetic facts.
            if not gate['proof_ids'] or not gate['target'] or not gate['scope']:
                raise ValueError('PARTIAL requires target-specific proof')
            for identifier in gate['proof_ids']:
                proof = evidence[identifier]
                if proof not in APPROVED_TARGET_PROOFS or (proof['target'], proof['scope']) != (gate['target'], gate['scope']):
                    raise ValueError('unapproved PARTIAL evidence')
    expected = {'parent_state': 'OPEN', 'r06_complete': False, 'operational_ready': False,
                'ope_states': {g['id']: g['state'] for g in gates}}
    if document['summary'] != expected:
        raise ValueError('stale readiness summary disagrees with gates or open parent')
    if not example:
        validate_documents(document)


def validate_documents(document):
    start, end = '<!-- r06b2-summary:start -->', '<!-- r06b2-summary:end -->'
    states = '; '.join(g['id']+'='+g['state'] for g in document['gates'])
    expected = '**Readiness attuale R06.b.2:** '+states+'; #46 OPEN; R06 NON COMPLETA; nessuna readiness operativa.'
    runbook = (ROOT/'docs/r06-recovery-runbook.md').read_text()
    if runbook.count(start) != 1 or runbook.count(end) != 1 or runbook.split(start)[1].split(end)[0].strip() != expected:
        raise ValueError('stale active readiness summary')
    for name in ('r06-migration-inventory.md', 'r06-restore-rehearsal.md', 'productization-plan.md'):
        header = (ROOT/'docs'/name).read_text()[:1000]
        if any(token not in header for token in ('R06.b.2', 'r06-recovery-runbook.md', 'r06-readiness-registry.json')):
            raise ValueError('stale active R06 header')


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def read_registry(path):
    with path.open('rb') as stream:
        content = stream.read(1048577)
    if len(content) > 1048576:
        raise ValueError('registry exceeds 1 MiB offline bound')
    return json.loads(content, object_pairs_hook=strict_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registry', nargs='?', type=Path, default=ROOT/'docs/r06-readiness-registry.json')
    args = parser.parse_args()
    try:
        document = read_registry(args.registry)
        if args.registry.resolve() == (ROOT/'docs/r06-readiness-registry.json').resolve():
            if document['purpose'] != 'ACTUAL' or sorted(e['id'] for e in document['evidence']) != sorted(DELIVERIES):
                raise ValueError('default registry requires actual purpose and all verified deliveries')
        validate(document)
    except (ValueError, KeyError, TypeError, OSError):
        print('readiness registry refused: gate coverage or invalid input', file=sys.stderr)
        return 2
    print('VALID '+document['purpose']+' registry; offline consistency only, not operational readiness')
    return 0


if __name__ == '__main__':
    sys.exit(main())
