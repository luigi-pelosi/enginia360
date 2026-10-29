#!/usr/bin/env python3
"""Offline receipt evidence only; no network, adapter, stock writer or replay."""
import json
from decimal import Decimal, InvalidOperation

def number(value, positive=False):
    if type(value) not in (int,float,Decimal): return False
    try:
        d=Decimal(str(value))
        return d.is_finite() and d==d.quantize(Decimal('0.000001')) and (not positive or d>0)
    except InvalidOperation: return False

def string(value): return isinstance(value,str) and bool(value)

def decode_receipt(text):
    value=json.loads(text)
    if not isinstance(value,dict) or type(value.get('responseCode')) is not int or value['responseCode']!=200 or type(value.get('errorCode')) is not int or value['errorCode']!=0:
        raise ValueError('receipt business envelope required')
    d=value.get('document')
    if not isinstance(d,dict) or type(d.get('id')) is not int or type(d.get('idDocumentType')) is not int or d['idDocumentType']!=0 or type(d.get('idNumerator')) is not int:
        raise ValueError('persisted receipt identity, type0 and numerator required')
    if not all(string(d.get(k)) for k in ('idVendor','reference','idBu')):
        raise ValueError('receipt vendor, reference and BU required')
    rows=d.get('rows')
    if not isinstance(rows,list) or not rows: raise ValueError('receipt rows required')
    positions=set()
    for row in rows:
        if not isinstance(row,dict) or type(row.get('idPos')) is not int or row['idPos'] in positions or type(row.get('idPosType')) is not int:
            raise ValueError('distinct integer row position and type required')
        positions.add(row['idPos'])
        if not number(row.get('price')) or not number(row.get('quantity'),positive=row['idPosType']==1):raise ValueError('finite q6 row price and quantity required')
        if not isinstance(row.get('description'),str):raise ValueError('description required')
        if row['idPosType']==1 and not all(string(row.get(k)) for k in ('idMaterial','idStorage','idVat')):
            raise ValueError('material destination and VAT required')
    return value

def compare_receipt(sent, detail, expected_id):
    try: d=decode_receipt(json.dumps(detail))['document']
    except (ValueError,TypeError):return {'matches':False,'fractional_q6_stress_observed':False}
    fields=('idDocumentType','idVendor','reference','idBu','idNumerator')
    row_fields=('idMaterial','idPosType','quantity','price','description','idStorage','idVat')
    rows=sent.get('rows',[])
    equal=(type(expected_id) is int and d['id']==expected_id and all(k in sent and d[k]==sent[k] for k in fields)
           and len(rows)==len(d['rows']) and all(all(k in a and k in b and a[k]==b[k] for k in row_fields) for a,b in zip(rows,d['rows'])))
    fractional=equal and any(number(x.get('price')) and Decimal(str(x['price'])).as_tuple().exponent==-6 and Decimal(str(x['price']))!=Decimal(str(x['price'])).quantize(Decimal('0.01')) for x in rows)
    return {'matches':equal,'fractional_q6_stress_observed':fractional}

def assess_lookup(page, reference, vendor, detail, precommitted):
    hold='HOLD_NO_REPOST'
    if type(precommitted) is not bool or not string(reference) or not string(vendor) or not isinstance(page,dict):return hold
    if page.get('responseCode')!=200 or page.get('errorCode')!=0:return hold
    rows=page.get('documentsHeaders');meta=page.get('metadata')
    if not isinstance(rows,list) or not isinstance(meta,dict) or type(meta.get('limit')) is not int or meta['limit']!=5 or type(meta.get('offset')) is not int or meta['offset']!=0 or len(rows)>=5:return hold
    keys=('id','idDocumentType','idVendor','reference','idBu','idNumerator')
    if any(not isinstance(h,dict) or any(k not in h for k in keys) for h in rows):return hold
    matches=[h for h in rows if h['reference']==reference and h['idVendor']==vendor and type(h['idDocumentType']) is int and h['idDocumentType']==0]
    if len(matches)!=1:return hold
    try:d=decode_receipt(json.dumps(detail))['document']
    except (ValueError,TypeError):return hold
    if any(type(d[k]) is not type(matches[0][k]) or d[k]!=matches[0][k] for k in keys):return hold
    return 'BOUNDED_MATCH_NOT_PROVIDER_GUARANTEE' if precommitted else 'ORDINARY_MATCH_NOT_RECOVERY'

SOURCE_CATALOG={
    'api-ack':('R05a5',28,'2026-10-27T12:04:06.035448+00:00','ecfed57184d8aba73854026000ef07cdef93335b4aa929618dab75a50d3a98c6'),
    'api-detail':('R05a5',29,'2026-10-27T12:04:06.780489+00:00','0710eb975a7d88cc524472a44eb1c9cc439e5a5ef8207a94790f2aec33ee591a'),
    'order-before':('R05a5',21,'2026-10-27T12:03:11.940673+00:00','ef52089417a7718b54265e68b56d52523cabd5d79013938c7fffe4405f9a8b15'),
    'order-after':('R05a5',30,'2026-10-27T12:04:07.433214+00:00','ef52089417a7718b54265e68b56d52523cabd5d79013938c7fffe4405f9a8b15'),
    'stock-before':('R05a5',22,'2026-10-27T12:03:12.620230+00:00','c45279a93707039f26f9665d290be64dc7d51fe7da8ff50f3aaa5f8c2d898b24'),
    'stock-after':('R05a5',31,'2026-10-27T12:04:08.109569+00:00','c35306af98632db457248bfb55f18af7dba1cf3238eea758e22479ca222be06f'),
    'ui-linked-detail':('R05a3',23,'2026-10-27T10:36:37.049525+00:00','7575c9c6938370881403c96296b93ee145b4cccce63d6ffad6863221209128f4'),
    'ui-ordinary-list':('R05a3',32,'2026-10-27T10:38:06.897414+00:00','d9d6fc9cc54899d751640feb6830aa8030e3174474560f1852bba4ef362dd598')}
CLAIMS=('fractional_q6_receipt_precision_proven','standalone_receipt_recovery_proven','precommitted_recovery','real_lost_success','server_idempotency','exactly_once','native_order_link','numeric_per_order_residual_proven','pending_cap_replenishment','new_receiving_grant','runtime_connector','r04_complete','r05_complete','readiness','full_architecture_pass','policy_decided')
BOUNDARIES=('READ_ONLY_REPROJECTION','GET_ONLY_HELD','FRACTIONAL_Q6_UNPROVEN','ORDINARY_LOOKUP_NOT_RECOVERY','PER_ORDER_RESIDUAL_UNKNOWN','D82_ERP_ONLY','D86_INTERNAL_SOURCE_LINK','D93_DISTINCT_OWNER_GRANT','D90_NO_REPLENISHMENT','D91_FROZEN_PRICE','D92_NO_EXPANSION','R04_R05_OPEN','NO_RUNTIME','NO_READINESS','FULL_ARCHITECTURE_FALSE','PARTIAL_3_2_APPROVED','OTHER_QUANTITY_OVERRECEIPT_WAREHOUSE_PRICING_FISCAL_UNDECIDED')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def require(ok,message):
    if not ok:raise ValueError(message)

def pointer_types(value,pointer=''):
    if isinstance(value,dict):return {p:t for k,v in value.items() for p,t in pointer_types(v,pointer+'/'+k).items()}
    if isinstance(value,list):return {p:t for i,v in enumerate(value) for p,t in pointer_types(v,pointer+'/'+str(i)).items()}
    return {pointer:'null' if value is None else 'boolean' if type(value) is bool else 'integer' if type(value) is int else 'number' if type(value) is float else 'string'}

def validate_artifacts(matrix, fixture_bytes, doc, root):
    import hashlib
    sha=lambda b:hashlib.sha256(b).hexdigest()
    require(sha(fixture_bytes)=='f0dd3a100b522265c5c6043517d75456bd2d0a3ef6ed73ae9856a16eadce5189','owned projection changed; no invented response or private fields')
    f=json.loads(fixture_bytes)
    require(set(matrix)=={'increment','base_main','refs','new_decision','status','acquisition','reprojected_utc','new_run','claims','observations','provenance','historical_ledgers','historical_files','redaction','remaining_gates','incidents'},'unexpected/missing matrix fields')
    require(matrix['increment']=='R05.a.8' and matrix['base_main']=='15c8f94a44f100a3f49f9bd8bfcfc3689aad7412' and matrix['refs']==[128,44,45] and matrix['new_decision'] is None,'wrong scope or invented decision')
    require(matrix['status']=='OBSERVED_CONTRACT_WITH_GAPS' and matrix['acquisition']=='READ_ONLY_REPROJECTION_OF_RETAINED_OWNED_RAW','false acquisition/completion')
    expected_run={'business_requests':0,'persisted_receipt_posts':0,'simulation_posts':0,'objects_created':0,'caps':{'business_requests':25,'persisted_receipt_posts':1,'simulation_posts':1},'sandbox_executor_started':False}
    require(canonical(matrix['new_run'])==canonical(expected_run),'run counts/caps must reflect zero actual calls, not theoretical permission')
    require(matrix['claims']=={k:False for k in CLAIMS} and all(v is False for v in matrix['claims'].values()),'unproved claim promoted')
    require(set(f)==set(SOURCE_CATALOG)|{'sent-comparison'},'capture set changed')
    require(compare_receipt(f['sent-comparison'],f['api-detail'],f['api-ack']['idDocument'])=={'matches':True,'fractional_q6_stress_observed':False},'receipt exact readback or precision limit changed')
    require(f['order-before']==f['order-after'],'source order changed')
    d=f['api-detail']['document'];before=f['stock-before']['stockReports'][0];after=f['stock-after']['stockReports'][0]
    require(d['reference']==f['order-before']['document']['reference'],'historical shared reference not a unique receipt key')
    require(all(d['rows'][0][k] is None for k in ('saleorderref','saleorderposref','materialmovementref','materialmovementposref')),'native links invented')
    require((before['quantity'],after['quantity'],before['orderedToSuppliersQty'],after['orderedToSuppliersQty'])==(1,2,6,6),'stock comparison changed')
    ui=f['ui-linked-detail']['document']
    require(assess_lookup(f['ui-ordinary-list'],ui['reference'],ui['idVendor'],f['ui-linked-detail'],False)=='ORDINARY_MATCH_NOT_RECOVERY','ordinary UI evidence improperly promoted')
    expected_observations={'receipt_type':0,'receipt_quantity':1.0,'receipt_price':1.0,'exact_request_readback_fields':['idDocumentType','idVendor','reference','idBu','idNumerator','idMaterial','idPosType','quantity','price','description','idStorage','idVat'],'source_order_unchanged':True,'stock_physical_before':1.0,'stock_physical_after':2.0,'stock_ordered_before':6.0,'stock_ordered_after':6.0,'per_order_residual':'UNKNOWN','ordered_stock_semantics':'POOL_AGGREGATE_NOT_ORDER_RESIDUAL','native_reference_values':'NULL','request_reference_shared_with_source_order':True,'recovery':'GET_ONLY_HELD','ui_lookup':'ORDINARY_POSTACK_LOOKUP_NOT_PRECOMMITTED_RECOVERY','standalone_receipt_list':'NO_POSITIVE_RETAINED_CAPTURE','raw_empty_receipt_list_sequences':[25,32]}
    require(canonical(matrix['observations'])==canonical(expected_observations),'observation changed or inference promoted')
    p=matrix['provenance'];require(isinstance(p,list) and len(p)==len(SOURCE_CATALOG),'capture provenance count changed')
    require(len({v['name'] for v in p})==len(p),'duplicate provenance')
    times={}
    for v in p:
        name=v['name'];require(name in SOURCE_CATALOG,'unknown provenance')
        require(set(v)=={'name','phase','seq','acquired_utc','http_status','source_sha256','projection_sha256','pointer_types','ownership'},'unexpected provenance fields')
        require((v['phase'],v['seq'],v['acquired_utc'],v['source_sha256'])==SOURCE_CATALOG[name],'source identity/hash/chronology mismatch')
        require(type(v['http_status']) is int and v['http_status']==200 and v['ownership']=='exact-owned-ledger-id-and-synthetic-reference','status or ownership invalid')
        require(v['projection_sha256']==sha(canonical(f[name])) and v['pointer_types']==pointer_types(f[name]),'projection hash/pointer types invalid')
        times[name]=v['acquired_utc']
    require(times['order-before']<times['api-ack']<times['api-detail']<times['order-after']<times['stock-after'],'historical read chronology changed')
    require(times['ui-linked-detail']<times['ui-ordinary-list'],'postack lookup not prior recovery')
    require(matrix['historical_ledgers']=={'R05a3':'d33adfead2a1dc55304ca7c006c580d2f671bf5f1036d58f9cb897355a1c87dc','R05a4':'e6cc604b9c826391fab4ffc453bc06f2f85b9133392a63a9f5091e9392b7114d','R05a5':'ce501229fe278f44b8a7a153fa7cb1b0db77598e78f0e50af73714baa116f538'},'historical ledger pins changed')
    historical={path:sha((root/path).read_bytes()) for phase in ('r05a3','r05a5','r05a7') for path in ('docs/'+phase+'-evidence.json','tests/fixtures/'+phase+'-owned-captures.json')}
    require(matrix['historical_files']==historical,'historical files altered or omitted')
    require(set(matrix['redaction'])=={'ids','vendor_bu_storage_material_vat','description','excluded'} and all(isinstance(v,str) for v in matrix['redaction'].values()),'private or unexpected redaction metadata')
    require(isinstance(matrix['remaining_gates'],list) and len(matrix['remaining_gates'])==6 and all(string(x) for x in matrix['remaining_gates']),'remaining gates missing')
    require(isinstance(matrix['incidents'],list) and len(matrix['incidents'])==5,'historical incidents missing')
    require(all(token in doc for token in BOUNDARIES),'document boundary removed')
    require(not any(token in doc for token in ('R04_COMPLETE=true','R05_COMPLETE=true','RECEIPT_Q6_PROVEN=true','RECOVERY_PRECOMMITTED=true','LOCAL_STOCK_WRITER=true')),'unsafe document promotion')

def main():
    import argparse
    from pathlib import Path
    import sys
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser()
    parser.add_argument('--matrix',type=Path,default=root/'docs/r05a8-evidence.json')
    parser.add_argument('--fixtures',type=Path,default=root/'tests/fixtures/r05a8-owned-captures.json')
    parser.add_argument('--doc',type=Path,default=root/'docs/r05a8-sandbox-receipt-contract.md')
    args=parser.parse_args()
    try:
        validate_artifacts(json.loads(args.matrix.read_text()),args.fixtures.read_bytes(),args.doc.read_text(),root)
    except (ValueError,TypeError,KeyError,OSError) as error:
        print('Receipt evidence rejected: '+str(error),file=sys.stderr);return 2
    print('Offline evidence consistent; GET_ONLY_HELD; no runtime/provider compatibility claim');return 0

if __name__=='__main__':
    raise SystemExit(main())
