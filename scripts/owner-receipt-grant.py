#!/usr/bin/env python3
"""D93 owner/trusted offline receiving grant setup. No web delegation or provisioning."""
import uuid
IDS={'commandId','tenantId','legalEntityId','actorMembershipId','targetMembershipId','verificationReference','siteId','warehouseId'}
FIELDS=IDS|{'expectedRevision','operation'}
def validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('closed explicit receiving grant command required')
    for key in IDS:
        v=value[key]
        if not isinstance(v,str) or str(uuid.UUID(v))!=v or uuid.UUID(v).int==0:raise ValueError('canonical nonempty UUID required')
    if value['actorMembershipId']==value['targetMembershipId']:raise ValueError('no self grant')
    if type(value['expectedRevision']) is not int or not 0<=value['expectedRevision']<2**31:raise ValueError('bounded expected revision required')
    if value['operation'] not in ('grant','revoke'):raise ValueError('finite exact receiving action and operation required')
    return value

def apply(value):
    import os
    import subprocess
    value=validate(value)
    if os.environ.get('PGSSLMODE')!='verify-full' or not os.environ.get('PGSSLROOTCERT'):raise ValueError('CA-verified TLS required')
    sql="""BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',:'tenantId',true),set_config('app.legal_entity_id',:'legalEntityId',true);
SELECT organization_access.set_receipt_grant(:'commandId'::uuid,:'tenantId'::uuid,:'legalEntityId'::uuid,:'siteId'::uuid,:'warehouseId'::uuid,:'actorMembershipId'::uuid,:'targetMembershipId'::uuid,:'verificationReference'::uuid,:'expectedRevision'::integer,:'operation');
COMMIT;
SELECT set_config('app.tenant_id',:'tenantId',false),set_config('app.legal_entity_id',:'legalEntityId',false);
SELECT count(*) FROM organization_access.receipt_grant_history WHERE "CommandId"=:'commandId'::uuid AND "TenantId"=:'tenantId'::uuid AND "LegalEntityId"=:'legalEntityId'::uuid AND "ActorMembershipId"=:'actorMembershipId'::uuid AND "TargetMembershipId"=:'targetMembershipId'::uuid AND "VerificationReference"=:'verificationReference'::uuid AND "Revision"::bigint=:'expectedRevision'::bigint+1 AND "SiteId"=:'siteId'::uuid AND "WarehouseId"=:'warehouseId'::uuid AND "Operation"=:'operation';
"""
    args=['psql','-X','-qAt','-v','ON_ERROR_STOP=1']
    for key in sorted(FIELDS):args+=['-v',key+'='+str(value[key])]
    result=subprocess.run(args,input=sql,text=True,capture_output=True,timeout=30)
    lines=result.stdout.splitlines()
    if result.returncode or len(lines)<4 or lines[-3] not in ('applied','replayed') or lines[-1]!='1':raise ValueError('owner receiving grant refused or exact readback failed')
    print('Receiving grant committed/replayed; exact immutable audit read back. No delegation or provisioning.')

if __name__=='__main__':
    import argparse,json,subprocess,sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);args=parser.parse_args()
    try:apply(json.loads(args.input.read_text()))
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError):
        print('Receiving grant refused: check verified memberships, exact scope/action/revision, TLS and nonprivileged owner connection. No credentials logged.',file=sys.stderr);sys.exit(1)
