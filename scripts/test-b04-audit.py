#!/usr/bin/env python3
"""Assert operational audit shape and minimization; not a compliance journal."""
import json
import sys
rows = []
for line in sys.stdin:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get('EventId') == 404:
        rows.append(event)
assert rows, 'Workshop audit events must exist'
encoded = json.dumps(rows)
for forbidden in ['synthetic-alpha-password', 'access_token', 'Bearer ', 'SYNTHETIC-', 'Veicolo sintetico', 'Sede sintetica']:
    assert forbidden not in encoded, 'Audit must not contain payload or credential: ' + forbidden
states = [r['State'] for r in rows]
assert any(s.get('Outcome') == 201 for s in states), 'Successful creation audited'
assert all(s.get('ResourceId') != '00000000-0000-0000-0000-000000000000' for s in states if s.get('Outcome') == 201), 'Successful creation audit must identify the committed resource'
assert any(s.get('Outcome') in [400, 403, 404, 409] for s in states), 'Denied operation audited'
assert all(set(s) == {'Action','Outcome','ResourceId','IdentityId','{OriginalFormat}'} for s in states), states[0]
print(f'PASS B04 minimized technical audit: {len(rows)} events, successful and rejected actions')
