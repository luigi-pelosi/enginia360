#!/usr/bin/env python3
"""D95 owner/trusted offline positive supplier fact projection on an EXISTING counterparty.

Run only after independently verifying the already-trusted operator and external fact offline.
References record that work; they do not authenticate, verify Giobby, or create a trust binding.
No provider call, user grant, company VendorId mapping, negative role or authority setup.
Connection secrets stay in libpq environment/service configuration, never CLI arguments.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

IDS = {'commandId','tenantId','legalEntityId','counterpartyId','actorMembershipId',
       'verificationReference','sourceFactReference','sourceId','profileId'}
FIELDS = IDS | {'authorityVersion','expectedRevision','sourceSystem','isSupplier'}


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('explicit closed projection input required')
    for key in IDS:
        token = value[key]
        if not isinstance(token, str) or len(token) != 36:
            raise ValueError('canonical nonempty technical references required')
        if str(uuid.UUID(token)) != token or uuid.UUID(token).int == 0:
            raise ValueError('canonical nonempty technical references required')
    for key, minimum in (('authorityVersion', 1), ('expectedRevision', 0)):
        if type(value[key]) is not int or not minimum <= value[key] <= 2147483647:
            raise ValueError('exact bounded integer revision required')
    if value['isSupplier'] is not True or value['sourceSystem'] != 'Giobby':
        raise ValueError('only a positive Giobby supplier fact is permitted')
    return value


def apply(value):
    value = validate(value)
    if os.environ.get('PGSSLMODE') != 'verify-full' or not os.environ.get('PGSSLROOTCERT'):
        raise ValueError('CA-verified TLS required')
    sql = """BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',(:'payload'::jsonb)->>'tenantId',true),set_config('app.legal_entity_id',(:'payload'::jsonb)->>'legalEntityId',true);
SELECT 'D95_RESULT|'||counterparties.project_external_supplier_role(:'payload'::jsonb)::text;
COMMIT;
BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',(:'payload'::jsonb)->>'tenantId',true);
SELECT 'D95_RECEIPT|'||jsonb_build_object('request',p."Request",'snapshot',p."Snapshot",'revision',h."Revision",'isSupplier',c."IsSupplier")::text
FROM counterparties.external_supplier_projection_history p
JOIN counterparties.common_edit_history h ON h."CommandId"=p."CommandId" AND h."TenantId"=p."TenantId"
JOIN counterparties.counterparties c ON c."Id"=h."CounterpartyId" AND c."TenantId"=p."TenantId"
WHERE p."CommandId"=((:'payload'::jsonb)->>'commandId')::uuid AND p."Request"=:'payload'::jsonb;
COMMIT;
"""
    result = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1','-v',
                             'payload='+json.dumps(value, separators=(',',':'))],
                            input=sql, text=True, capture_output=True, timeout=35)
    try:
        results = [json.loads(line[len('D95_RESULT|'):]) for line in result.stdout.splitlines() if line.startswith('D95_RESULT|')]
        receipts = [json.loads(line[len('D95_RECEIPT|'):]) for line in result.stdout.splitlines() if line.startswith('D95_RECEIPT|')]
        expected = dict(counterpartyId=value['counterpartyId'], isSupplier=True,
                        revision=value['expectedRevision']+1, authorityVersion=value['authorityVersion'])
        if (result.returncode or len(results) != 1 or len(receipts) != 1
                or results[0] not in (dict(state='applied', snapshot=expected), dict(state='replayed', snapshot=expected))
                or receipts[0] != dict(request=value, snapshot=expected, revision=expected['revision'], isSupplier=True)):
            raise ValueError('projection refused or exact immutable readback failed')
    except (TypeError, KeyError, json.JSONDecodeError):
        raise ValueError('projection refused or exact immutable readback failed') from None
    print('Positive supplier projection committed/replayed; exact immutable provenance and shared role read back. No ERP call.')


def closed_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    try:
        with args.input.open('rb') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('bounded input required')
        apply(json.loads(raw, object_pairs_hook=closed_object))
    except (ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError):
        print('Supplier projection refused. Check offline verification, current trusted binding/membership, exact authority/source/profile/company/revision, TLS and nonprivileged owner connection. No credentials logged.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
