#!/usr/bin/env python3
"""Validate actual structured Billing audit events, never synthesize evidence."""
import json
import sys
rows=[]
for line in sys.stdin:
    try: value=json.loads(line)
    except json.JSONDecodeError: continue
    if value.get('EventId')==312:
        rows.append(value)
assert rows, 'Billing audit absent'
assert {200,201,403,404,409,500} <= {row.get('State',{}).get('Outcome') for row in rows}, 'missing real success, denial, conflict or fault audit'
for row in rows:
    text=json.dumps(row)
    assert not any(word in text for word in ['Bearer ', 'password', 'FiscalIdentifier', 'RegisteredOffice', 'LegalName']), 'sensitive business/auth payload in technical audit'
    if row['State'].get('Outcome') in [200,201]:
        assert row['State'].get('ResourceId')!='00000000-0000-0000-0000-000000000000', 'audit lost committed invoice identity'
print('PASS B12 actual audit 200/201/403/404/409/500, technical IDs and no business/auth payload')
