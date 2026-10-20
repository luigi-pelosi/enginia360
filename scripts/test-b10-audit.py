#!/usr/bin/env python3
"""Bounded structured B10 audit, technical identifiers only."""
import json
import sys
import uuid
rows=[]
for line in sys.stdin:
    try: row=json.loads(line)
    except json.JSONDecodeError: continue
    rows.append(row)
routes=[r for r in rows if r.get('EventId') == 404 and any(x in str(r.get('State',{})) for x in ['/technical-closure','/administrative-requests','/administrative-closure','/closure-state'])]
dispatches=[r for r in rows if r.get('EventId') == 610]
assert any(r['State'].get('Outcome') == 201 and '/technical-closure' in r['State'].get('Action','') for r in routes), 'Missing accepted technical closure audit'
assert any(r['State'].get('Outcome') == 201 and '/administrative-requests' in r['State'].get('Action','') for r in routes), 'Missing accepted request audit'
assert any(r['State'].get('Outcome') == 409 and '/administrative-closure' in r['State'].get('Action','') for r in routes), 'Missing blocked administrative closure audit'
for row in routes:
    state=row['State']
    if state.get('Outcome') in (200,201) and state['Action'].startswith('POST'): assert uuid.UUID(state['ResourceId']).int != 0,state
assert {r['State'].get('State') for r in dispatches} >= {'Received','Completed'}, 'Missing dispatch state audit'
for row in dispatches:
    state=row['State']
    assert uuid.UUID(state['RequestId']).int != 0,state
    assert set(state) <= {'Message','RequestId','State','Attempts','Error','{OriginalFormat}'},state
serialized=json.dumps(routes+dispatches)
for forbidden in ['synthetic-alpha-password','access_token','Bearer ','netAmount','164.5','Componente sintetico','Manodopera','payerId']:
    assert forbidden not in serialized,forbidden
print('PASS B10 structured technical closure/request/dispatch audit, real resource IDs, no amounts, labels or tokens')
