#!/usr/bin/env python3
"""Offline owner/trusted-operator operation after identity/source verification.
Existing verified binding and membership only; no provisioning or delegate admin API.
Input contains technical references only. PG* environment must use verified TLS and
nonprivileged database owner. Keep actual verification evidence outside this tool.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

IDS={'commandId','tenantId','actorMembershipId','verificationReference','sourceId','profileId'}
FIELDS=IDS|{'domain','direction','expectedVersion','companyIds'}

def valid_id(value):
    return isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0

def validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:
        raise ValueError('every explicit field is required; no defaults or scheduling')
    if any(not valid_id(value[key]) for key in IDS):
        raise ValueError('nonempty canonical technical references required')
    if value['domain']!='counterparties' or value['direction'] not in ('Enginia360ToExternal','ExternalToEnginia360'):
        raise ValueError('unsupported domain/direction')
    if type(value['expectedVersion']) is not int or not 0<=value['expectedVersion']<2147483647:
        raise ValueError('explicit current version required')
    companies=value['companyIds']
    if not isinstance(companies,list) or not companies or len(companies)>1000 or any(not valid_id(x) for x in companies) or len(set(companies))!=len(companies):
        raise ValueError('explicit unique company references required')
    return value

def apply(value):
    value=validate(value)
    if os.environ.get('PGSSLMODE')!='verify-full' or not os.environ.get('PGSSLROOTCERT'):
        raise ValueError('CA-verified TLS required')
    sql='''BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',:'tenantId',true);
SELECT organization_access.establish_master_authority(:'commandId'::uuid,:'tenantId'::uuid,:'actorMembershipId'::uuid,:'verificationReference'::uuid,:'expectedVersion'::integer,:'direction',:'sourceId'::uuid,:'profileId'::uuid,:'companies'::uuid[]);
COMMIT;
SELECT set_config('app.tenant_id',:'tenantId',false);
SELECT count(*) FROM organization_access.master_authority_history WHERE "CommandId"=:'commandId'::uuid AND "TenantId"=:'tenantId'::uuid AND "ActorMembershipId"=:'actorMembershipId'::uuid AND "VerificationReference"=:'verificationReference'::uuid AND "Version"=:'expectedVersion'::integer+1 AND "Direction"=:'direction' AND "SourceId"=:'sourceId'::uuid AND "ProfileId"=:'profileId'::uuid AND "CompanyIds"=:'companies'::uuid[];
'''
    args=['psql','-X','-qAt','-v','ON_ERROR_STOP=1']
    for key in IDS|{'expectedVersion','direction'}:
        args+=['-v',key+'='+str(value[key])]
    args+=['-v','companies={'+','.join(value['companyIds'])+'}']
    result=subprocess.run(args,input=sql,text=True,capture_output=True,timeout=30)
    if result.returncode or result.stdout.splitlines()[-1:]!=['1']:
        raise ValueError('owner decision refused or exact readback failed')
    print('Owner authority decision committed/replayed and exact history read back. No identity or ERP provisioning performed.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    args=parser.parse_args()
    try: apply(json.loads(args.input.read_text()))
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError):
        print('Owner authority operation refused. Verify explicit references, trusted binding, source, current version, TLS and nonprivileged owner connection. No credentials logged.',file=sys.stderr)
        sys.exit(1)
