#!/usr/bin/env python3
"""D91 owner/trusted offline pricing grant setup. No web delegation or provisioning."""
import uuid
IDS={'commandId','tenantId','legalEntityId','actorMembershipId','targetMembershipId','verificationReference'}
FIELDS=IDS|{'expectedRevision','action','operation'}
def validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError('closed explicit pricing grant command required')
    for key in IDS:
        v=value[key]
        if not isinstance(v,str) or str(uuid.UUID(v))!=v or uuid.UUID(v).int==0:raise ValueError('canonical nonempty UUID required')
    if value['actorMembershipId']==value['targetMembershipId']:raise ValueError('no self grant')
    if type(value['expectedRevision']) is not int or not 0<=value['expectedRevision']<2**31:raise ValueError('bounded expected revision required')
    if value['action'] not in ('catalog.purchase-prices.read','catalog.purchase-prices.manage') or value['operation'] not in ('grant','revoke'):raise ValueError('finite exact pricing action and operation required')
    return value

def apply(value):
    import os
    import subprocess
    value=validate(value)
    if os.environ.get('PGSSLMODE')!='verify-full' or not os.environ.get('PGSSLROOTCERT'):raise ValueError('CA-verified TLS required')
    sql="""BEGIN;
SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
SELECT set_config('app.tenant_id',:'tenantId',true),set_config('app.legal_entity_id',:'legalEntityId',true);
SELECT organization_access.set_purchase_price_grant(:'commandId'::uuid,:'tenantId'::uuid,:'legalEntityId'::uuid,:'actorMembershipId'::uuid,:'targetMembershipId'::uuid,:'verificationReference'::uuid,:'expectedRevision'::integer,:'action',:'operation');
COMMIT;
SELECT set_config('app.tenant_id',:'tenantId',false),set_config('app.legal_entity_id',:'legalEntityId',false);
SELECT count(*) FROM organization_access.purchase_price_grant_history WHERE "CommandId"=:'commandId'::uuid AND "TenantId"=:'tenantId'::uuid AND "LegalEntityId"=:'legalEntityId'::uuid AND "ActorMembershipId"=:'actorMembershipId'::uuid AND "TargetMembershipId"=:'targetMembershipId'::uuid AND "VerificationReference"=:'verificationReference'::uuid AND "Revision"::bigint=:'expectedRevision'::bigint+1 AND "Action"=:'action' AND "Operation"=:'operation';
"""
    args=['psql','-X','-qAt','-v','ON_ERROR_STOP=1']
    for key in sorted(FIELDS):args+=['-v',key+'='+str(value[key])]
    result=subprocess.run(args,input=sql,text=True,capture_output=True,timeout=30)
    lines=result.stdout.splitlines()
    if result.returncode or len(lines)<4 or lines[-3] not in ('applied','replayed') or lines[-1]!='1':raise ValueError('owner pricing grant refused or exact readback failed')
    print('Pricing grant committed/replayed; exact immutable audit read back. No delegation or provisioning.')

if __name__=='__main__':
    import argparse,json,subprocess,sys
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);args=parser.parse_args()
    try:apply(json.loads(args.input.read_text()))
    except (ValueError,TypeError,KeyError,OSError,subprocess.SubprocessError):
        print('Pricing grant refused: check verified memberships, exact scope/action/revision, TLS and nonprivileged owner connection. No credentials logged.',file=sys.stderr);sys.exit(1)
