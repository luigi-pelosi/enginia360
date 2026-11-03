#!/usr/bin/env python3
"""Owner-only offline authority bootstrap/recovery. A reference is NOT identity verification.

Before grant, the owner verifies the exact existing identity out of band. This CLI
never authenticates from the JSON, provisions identities, or delegates authority.
Use only the nonprivileged database-owner connection with CA-verified TLS.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
import uuid
FIELDS = {'commandId', 'operation', 'internalIdentityId', 'issuer', 'subject', 'verificationReference', 'expectedRevision'}

def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('closed explicit command required')
    for key in ('commandId', 'internalIdentityId', 'verificationReference'):
        item = value[key]
        if not isinstance(item, str) or not re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', item) or uuid.UUID(item).int == 0:
            raise ValueError('canonical nonempty UUID required')
    if value['operation'] not in ('grant', 'revoke'):
        raise ValueError('finite operation required')
    if type(value['expectedRevision']) is not int or not 0 <= value['expectedRevision'] <= 2147483646:
        raise ValueError('bounded revision required')
    issuer = value['issuer']
    subject = value['subject']
    if not isinstance(issuer, str) or not re.fullmatch('[!-~]{9,2048}', issuer):
        raise ValueError('exact HTTPS issuer required')
    parsed = urlsplit(issuer)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or (parsed.password is not None) or parsed.query or parsed.fragment or any((x in issuer for x in ('?', '#', '@'))):
        raise ValueError('exact HTTPS issuer required')
    _ = parsed.port
    if not isinstance(subject, str) or not re.fullmatch('[ -~]{1,255}', subject):
        raise ValueError('exact opaque subject required')
    return value

def read_command(path):
    if path.stat().st_size > 8192:
        raise ValueError('bounded input required')

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate field refused')
            value[key] = item
        return value
    return json.loads(path.read_text(), object_pairs_hook=unique_pairs)

def apply(value):
    value = validate(value)
    if os.environ.get('PGSSLMODE') != 'verify-full' or not os.environ.get('PGSSLROOTCERT'):
        raise ValueError('CA-verified TLS required')
    args = ['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-v', 'request=' + json.dumps(value, separators=(',', ':'))]
    sql = """BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT organization_access.command_platform_authority(:'request'::jsonb);
COMMIT;
SELECT jsonb_build_object('request',"Request",'snapshot',"Snapshot")
FROM organization_access.platform_authority_audit
WHERE "CommandId"=(:'request'::jsonb->>'commandId')::uuid;
"""
    result = subprocess.run(args, input=sql, text=True, capture_output=True, timeout=30)
    lines = result.stdout.splitlines()
    if result.returncode or len(lines) != 2:
        raise ValueError('command refused or readback failed')
    outcome = json.loads(lines[0])
    readback = json.loads(lines[1])
    if outcome.get('state') not in ('applied', 'replayed') or readback.get('request') != value or readback.get('snapshot') != outcome.get('snapshot'):
        raise ValueError('exact committed audit readback failed')
    print(json.dumps(outcome, sort_keys=True))
    print('Platform authority committed/replayed and exact immutable audit read back. Snapshot is original command result, not current authority on replay.')
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    try:
        apply(read_command(args.input))
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        print('Platform authority refused. Check offline identity verification, exact existing binding, revision, owner connection and verified TLS. No credentials logged.', file=sys.stderr)
        sys.exit(1)
