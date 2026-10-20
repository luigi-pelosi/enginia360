#!/usr/bin/env python3
"""Bounded structured B09 audit, technical identifiers only."""
import json
import sys
import uuid
rows=[]
for line in sys.stdin:
    try: row=json.loads(line)
    except json.JSONDecodeError: continue
    rows.append(row)
returns=[r for r in rows if r.get('EventId') == 606 and '/carcass-returns' in str(r.get('State',{}))]
committed=[r for r in rows if r.get('EventId') == 609]
gates=[r for r in rows if r.get('EventId') == 404 and '/technical-closure-gate' in str(r.get('State',{}))]
assert returns, 'Missing Inventory carcass-return request audit'
assert committed, 'Missing Inventory committed carcass-return audit'
assert gates, 'Missing Workshop closure-gate audit'
assert any(r['State'].get('Outcome') == 201 for r in returns), 'Missing accepted carcass return audit'
for row in returns:
    state=row['State']
    if state.get('Outcome') in (200,201): assert uuid.UUID(state['ResourceId']).int != 0,state
for row in committed:
    state=row['State']
    assert uuid.UUID(state['ReturnId']).int != 0,state
    assert set(state) <= {'Message','ReturnId','IdentityId','{OriginalFormat}'},state
serialized=json.dumps(returns+committed+gates)
for forbidden in ['synthetic-alpha-password','access_token','Bearer ','Carcassa sostituita sintetica','Description','Synthetic carcass link fault']:
    assert forbidden not in serialized,forbidden
print('PASS B09 structured technical carcass-return/closure-gate audit, real resource IDs, no descriptions or sensitive payloads')
