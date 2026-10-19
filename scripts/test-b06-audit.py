#!/usr/bin/env python3
"""Bounded technical audit, no payload or credential disclosure."""
import json
import sys
rows=[]
for line in sys.stdin:
    try: row=json.loads(line)
    except ValueError: continue
    if row.get('EventId')==606: rows.append(row['State'])
assert rows, 'No real B06 Inventory audit events'
for row in rows:
    assert set(row)=={'Action','Outcome','ResourceId','IdentityId','{OriginalFormat}'}, row
    assert row['Outcome'] < 500, row
    assert len(row['Action']) <= 180 and len(row['IdentityId']) <= 36, row
created=[x for x in rows if x['Outcome']==201]
assert created and all(x['ResourceId']!='00000000-0000-0000-0000-000000000000' for x in created)
assert any(x['Outcome'] in (403,404,409) for x in rows)
print('PASS B06 technical audit: committed IDs, denies, bounded fields, no request payload/secrets')
