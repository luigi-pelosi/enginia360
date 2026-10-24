#!/usr/bin/env python3
"""Offline CREATE inventory, not a database inspector or migration authorizer."""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
# Preserve positions while ignoring SQL literals, comments and function bodies.
IGNORED = re.compile(r"(?P<tag>\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$).*?(?P=tag)|'(?:''|[^'])*'|--[^\n]*|/\*.*?\*/", re.S)
CREATE = re.compile(r'\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z_0-9]*\.[a-z_][a-z_0-9]*)\s*\(', re.I)
CATEGORIES = {'organization_structure', 'security_binding', 'security_evidence', 'shared_master',
              'company_extension', 'business_configuration', 'authority_evidence', 'operational_fact',
              'stock_state', 'integration_evidence', 'audit_history', 'derived_projection', 'technical_ledger'}
SECURITY_BINDINGS = {'organization_access.'+name for name in (
    'memberships', 'membership_scopes', 'company_permissions', 'common_edit_permissions',
    'external_identity_bindings', 'delegation_mandates', 'delegated_scopes')}


def definitions(manifest):
    """Support the published qualified CREATE grammar; fail on unhandled CREATEs.

    Read only manifest-selected SQL using the existing checksum/path validator.
    ALTER statements are deliberately not a live-schema reconstruction.
    """
    spec = importlib.util.spec_from_file_location('runtime_manifest', ROOT/'scripts/apply-runtime-migrations.py')
    assert spec and spec.loader
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    result = {}
    for entry in engine.load_manifest(manifest):
        sql = entry['sql']
        masked = IGNORED.sub(lambda m: ''.join('\n' if c == '\n' else ' ' for c in m[0]), sql)
        matches = list(CREATE.finditer(masked))
        if len(matches) != len(re.findall(r'\bCREATE\s+TABLE\b', masked, re.I)):
            raise ValueError('unsupported CREATE TABLE grammar')
        for match in matches:
            depth, end = 1, match.end()
            while end < len(masked) and depth:
                depth += (masked[end] == '(') - (masked[end] == ')')
                end += 1
            terminator = re.match(r'\s*;', masked[end:])
            if depth or terminator is None:
                raise ValueError('unterminated CREATE TABLE')
            end += terminator.end()
            table = match[1].lower()
            if table in result:
                raise ValueError('duplicate CREATE TABLE')
            ddl = sql[match.start():end]
            columns = re.findall(r'(?:\(|,)\s*"([^"]+)"\s+[a-z]', ddl)
            composite = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', ddl, re.I)
            keys = re.findall(r'"([^"]+)"', composite[1]) if composite else re.findall(r'"([^"]+)"\s+\w+\s+PRIMARY\s+KEY', ddl, re.I)
            if not columns or not keys:
                raise ValueError('unsupported columns or primary key')
            result[table] = {'migration': entry['id'], 'path': 'database/runtime/'+entry['path'],
                             'file_sha256': entry['sha256'], 'create_sql': ddl,
                             'columns': columns, 'primary_key': keys}
    return result


def verify(root, records, manifest=None):
    root = Path(root)
    found = definitions(manifest or root/'database/runtime/manifest.json')
    if not isinstance(records, list) or len(records) != len(found) or {r['table'] for r in records} != set(found):
        raise ValueError('inventory coverage mismatch')
    for row in records:
        fields = {'table', 'owner', 'category', 'migration_eligibility', 'handling_constraint',
                  'available_command', 'reconcile_keys', 'definition'}
        if set(row) != fields or row['owner'] != row['table'].split('.')[0] or row['migration_eligibility'] != 'UNDECIDED':
            raise ValueError('invalid classification fields or unapproved eligibility')
        if row['category'] not in CATEGORIES:
            raise ValueError('invalid classification')
        security = row['table'] in SECURITY_BINDINGS
        if (row['category'] == 'security_binding') != security or row['handling_constraint'] != (
                'RESTORE_ONBOARDING_ONLY' if security else 'NO_LEGACY_IMPORT_APPROVED'):
            raise ValueError('security binding classification or handling mismatch')
        if row['definition'] != found[row['table']]:
            raise ValueError('CREATE definition drift')
        definition = found[row['table']]
        expected_keys = list(dict.fromkeys([c for c in ('TenantId', 'LegalEntityId', 'OwnerLegalEntityId', 'SiteId', 'WarehouseId')
                                           if c in definition['columns']] + definition['primary_key']))
        if row['reconcile_keys'] != expected_keys:
            raise ValueError('invalid reconciliation identifiers')
        command = row['available_command']
        if command is not None:
            if (not isinstance(command, dict) or set(command) != {'source', 'registration', 'purpose'}
                    or any(not isinstance(value, str) or not value for value in command.values())):
                raise ValueError('invalid command evidence')
            source = root/command['source']
            if (not command['source'].startswith('src/Modules/') or '..' in Path(command['source']).parts
                    or command['purpose'] != 'EXISTING_OPERATION_NOT_IMPORT_AUTHORIZATION'
                    or not source.is_file()
                    or command['registration'] not in [line.strip() for line in source.read_text().splitlines()]):
                raise ValueError('unverified existing command')
    return {'tables': len(found), 'migrations': len(json.loads((manifest or root/'database/runtime/manifest.json').read_text())),
            'schemas': len({name.split('.')[0] for name in found}),
            'categories': dict(sorted(Counter(row['category'] for row in records).items())),
            'migration_eligibility': 'UNDECIDED', 'approval': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'database/runtime/manifest.json')
    parser.add_argument('--inventory', type=Path, default=ROOT/'docs/r06-migration-inventory.json')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(ROOT, json.loads(args.inventory.read_text()), args.manifest), sort_keys=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError):
        print('offline inventory refused: invalid manifest, definition or classification', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
