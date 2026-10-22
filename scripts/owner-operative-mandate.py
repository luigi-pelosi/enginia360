#!/usr/bin/env python3
"""Owner-only mandate operation for EXISTING trusted bindings, never provisioning.
Uses normal PG* environment; TLS verify-full required. No credential arguments/logs.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

FIELDS = {'operation','ownerActorId','mandateId','tenantId','adminMembershipId',
          'legalEntityId','siteId','warehouseId','action','validFrom','validUntil'}


def validate(value):
    if not isinstance(value,dict) or set(value) != FIELDS:
        raise ValueError('provide every explicit mandate field; no defaults')
    if any(not isinstance(item,str) for item in value.values()):
        raise ValueError('all explicit mandate values must be strings')
    for name in FIELDS-{'operation','action','validFrom','validUntil'}:
        if not isinstance(value[name],str) or str(uuid.UUID(value[name])) != value[name] or uuid.UUID(value[name]).int == 0:
            raise ValueError('nonempty canonical technical identifiers required')
    if value['operation'] not in ('create','revoke') or value['action'] not in ('organization-context.read','organization-context.write'):
        raise ValueError('unsupported operation/action')
    start,end = (datetime.fromisoformat(value[name].replace('Z','+00:00')) for name in ('validFrom','validUntil'))
    if start.tzinfo is None or end.tzinfo is None or end<=start:
        raise ValueError('explicit ordered timezone-aware validity required')
    return value


def apply(value):
    value=validate(value)
    if os.environ.get('PGSSLMODE') != 'verify-full' or not os.environ.get('PGSSLROOTCERT'):
        raise ValueError('CA-verified TLS required')
    sql = '''BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
DO $$ BEGIN
 IF current_user<>(SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database())
 OR (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user) THEN
 RAISE EXCEPTION 'requires nonprivileged database owner, never app role'; END IF;
END $$;
SELECT set_config('app.tenant_id',:'tenantId',true),set_config('app.owner_actor',:'ownerActorId',true);
'''
    match='''"Id"=:'mandateId'::uuid AND "TenantId"=:'tenantId'::uuid AND "AdminMembershipId"=:'adminMembershipId'::uuid
 AND "LegalEntityId"=:'legalEntityId'::uuid AND "SiteId"=:'siteId'::uuid AND "WarehouseId"=:'warehouseId'::uuid
 AND "Action"=:'action' AND "ValidFrom"=:'validFrom'::timestamptz AND "ValidUntil"=:'validUntil'::timestamptz'''
    if value['operation']=='create':
        sql+='''INSERT INTO organization_access.delegation_mandates VALUES (:'mandateId'::uuid,:'tenantId'::uuid,:'adminMembershipId'::uuid,:'legalEntityId'::uuid,:'siteId'::uuid,:'warehouseId'::uuid,:'action',:'validFrom'::timestamptz,:'validUntil'::timestamptz,NULL);
'''
    else:
        # Exact state match: one revoke, not a silent no-op or replacement of the mandate.
        sql+='CREATE TEMP TABLE revoked_count AS WITH changed AS (UPDATE organization_access.delegation_mandates SET "RevokedAt"=clock_timestamp() WHERE '+match+' AND "RevokedAt" IS NULL RETURNING 1) SELECT count(*) n FROM changed;\n'
        sql+="DO $$ BEGIN IF (SELECT n FROM revoked_count)<>1 THEN RAISE EXCEPTION 'exact active mandate not found'; END IF; END $$;\n"
    sql+='COMMIT;\n'
    # Exact readback in the same trusted connection after commit; fail instead of claiming success.
    sql+="SELECT set_config('app.tenant_id',:'tenantId',false);\nSELECT count(*) FROM organization_access.delegation_mandates WHERE "+match+' AND "RevokedAt" IS '+('NULL' if value['operation']=='create' else 'NOT NULL')+';\n'
    args=['psql','-X','-qAt','-v','ON_ERROR_STOP=1']
    for key,item in value.items():
        args+=['-v',key+'='+item]
    result=subprocess.run(args,input=sql,text=True,capture_output=True,timeout=30)
    if result.returncode or result.stdout.splitlines()[-1:] != ['1']:
        raise ValueError('mandate command refused or readback failed; no success claim')
    print('Explicit mandate '+value['operation']+' committed and exact state read back; preserve owner verification evidence separately.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    args=parser.parse_args()
    try:
        apply(json.loads(args.input.read_text()))
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError):
        print('Owner mandate operation refused. Check explicit input, verified bindings, scope, TLS and owner connection; no credentials logged.',file=sys.stderr)
        sys.exit(1)
