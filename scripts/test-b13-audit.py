#!/usr/bin/env python3
"""Validate actual structured Accounting audit events, never synthesize evidence."""
import json
import sys
rows=[]
for line in sys.stdin:
    try: value=json.loads(line)
    except json.JSONDecodeError: continue
    if value.get('EventId')==313:
        rows.append(value)
assert rows, 'Accounting audit absent'
outcomes={row.get('State',{}).get('Outcome') for row in rows}
assert {200,201,400,403,404,409} <= outcomes, ('missing real posting, denial, conflict or refusal audit', sorted(str(o) for o in outcomes))
for row in rows:
    text=json.dumps(row)
    assert not any(word in text for word in ['Bearer ', 'password', '200.69', '120100', 'Crediti']), 'amounts, accounts or credentials in technical audit'
    if row['State'].get('Outcome') in [200,201]:
        assert row['State'].get('ResourceId')!='00000000-0000-0000-0000-000000000000', 'audit lost committed entry identity'
print('PASS B13 actual audit 200/201/400/403/404/409, technical IDs and no amounts, accounts or credentials')
