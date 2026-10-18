#!/usr/bin/env python3
"""Validate structured B03 audit from real container stdout, no payload logging."""
import json, sys
rows = []
for line in sys.stdin:
    try:
        row = json.loads(line)
    except ValueError:
        continue
    if row.get('EventId') == 303:
        rows.append(row)
assert rows, 'Expected technical B03 audit EventId 303 in API logs'
for row in rows:
    state = row['State']
    assert {'Action', 'Outcome', 'ResourceId', 'IdentityId'} <= state.keys(), state
    assert set(state) <= {'Message', '{OriginalFormat}', 'Action', 'Outcome', 'ResourceId', 'IdentityId'}, state
    assert isinstance(state['Outcome'], int)
    raw = json.dumps(row)
    assert not any(value in raw for value in ['SYNTHETIC-', 'Destinazione sintetica', 'synthetic-alpha-password', 'registeredOffice', 'access_token'])
assert any(r['State']['Outcome'] == 200 for r in rows)
assert any(r['State']['Outcome'] == 403 for r in rows)
print(f'PASS audit: {len(rows)} technical success/denial events, fixed metadata only')
