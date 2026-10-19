#!/usr/bin/env python3
import json,sys
rows=[]
for line in sys.stdin:
    try: row=json.loads(line)
    except ValueError: continue
    if row.get('EventId')==404 and '/lines' in row.get('State',{}).get('Action',''): rows.append(row)
assert rows,'No real B05 line audits found'
for row in rows:
    state=row['State']
    assert set(state)=={'Action','Outcome','ResourceId','IdentityId','{OriginalFormat}'},state
    assert state['Outcome']<500,state
created=[x['State'] for x in rows if x['State']['Outcome']==201]
assert created and all(x['ResourceId']!='00000000-0000-0000-0000-000000000000' for x in created)
assert any(x['State']['Outcome'] in (403,404,409) for x in rows)
print('PASS B05 technical audit: committed line IDs, actual denies/conflicts, no commercial payload or identity secrets')
