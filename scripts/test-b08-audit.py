#!/usr/bin/env python3
"""Bounded structured B08 audit, technical identifiers only."""
import json
import sys
import uuid
rows=[]
for line in sys.stdin:
    try: row=json.loads(line)
    except json.JSONDecodeError: continue
    rows.append(row)
install=[r for r in rows if r.get('EventId') == 404 and '/installations' in str(r.get('State',{}))]
consume=[r for r in rows if r.get('EventId') == 608]
assert install, 'Missing Workshop installation audit'
assert consume, 'Missing Inventory committed consumption audit'
for row in install:
    state=row['State']
    if state.get('Outcome') in (201,202): assert uuid.UUID(state['ResourceId']).int != 0,state
for row in consume:
    state=row['State']
    assert uuid.UUID(state['InstallationId']).int != 0,state
    assert set(state) <= {'Message','InstallationId','IdentityId','{OriginalFormat}'},state
serialized=json.dumps(install+consume)
for forbidden in ['synthetic-alpha-password','access_token','Bearer ','UnitPrice','DiscountPercent','legalAddress','Synthetic stock update fault']:
    assert forbidden not in serialized,forbidden
print('PASS B08 structured technical installation and committed consumption audit, real resource IDs, no sensitive payloads')
