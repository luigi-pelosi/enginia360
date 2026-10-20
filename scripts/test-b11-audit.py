#!/usr/bin/env python3
import json,sys
rows=[]
for line in sys.stdin:
 try: rows.append(json.loads(line))
 except ValueError: pass
if '--capture' in sys.argv:
 for row in rows:
  if row.get('EventId')==610 or (row.get('EventId')==404 and '/reconciliation' in str(row.get('State',{}))):
   print(json.dumps(row))
 sys.exit(0)
recovery=[r for r in rows if r.get('EventId')==404 and '/reconciliation' in str(r.get('State',{}))]
assert {r['State'].get('Outcome') for r in recovery}>={202,200,403,409},'missing scoped recovery acceptance/replay/refusal audit'
dispatch=[r for r in rows if r.get('EventId')==610]
assert {r['State'].get('State') for r in dispatch}>={'Uncertain','NeedsReconciliation','Completed'},'missing distinct recovery delivery states'
for row in recovery+dispatch:
 text=json.dumps(row)
 for bad in ['access_token','synthetic-alpha-password','netAmount','catalogLabel','Manodopera']:
  assert bad not in text,bad
print('PASS B11 authorized recovery/refusal and uncertainty/escalation structured audit without payloads or credentials')
