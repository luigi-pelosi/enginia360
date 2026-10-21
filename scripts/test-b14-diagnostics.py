#!/usr/bin/env python3
"""B14 diagnosability: correlation IDs and module audit present, secrets and business payloads absent."""
import json
import os
import re
import sys

secrets = [value for key, value in os.environ.items()
           if key in ('B02_DB_PASSWORD', 'B02_DB_APP_PASSWORD') and value]
assert secrets, 'the suite must pass the ephemeral credentials so their absence is actually checked'
lines = sys.stdin.read().splitlines()
assert lines, 'no application log collected'
events, correlations, traces = set(), set(), set()
for line in lines:
    for secret in secrets:
        assert secret not in line, 'ephemeral credential leaked into the application log'
    for forbidden in ['Bearer ', 'synthetic-alpha-password', 'synthetic-beta-password']:
        assert forbidden not in line, forbidden
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        continue
    identifier = value.get('EventId')
    if identifier:
        events.add(identifier)
    if identifier in {404, 312, 313}:
        assert not any(term in line for term in ['AccountCode', 'Amount', '200.69', '120100', 'Bearer ', 'synthetic-alpha-password']), 'business payload in technical audit'
    scope = value.get('Scopes') or []
    for item in scope:
        if isinstance(item, dict) and item.get('CorrelationId'):
            correlations.add(item['CorrelationId'])
        if isinstance(item, dict) and re.fullmatch('[a-f0-9]{32}', item.get('TraceId', '')) and re.fullmatch('[a-f0-9]{16}', item.get('SpanId', '')):
            traces.add(item['TraceId'])
assert traces, 'W3C trace/span scope absent'
assert {404, 312, 313, 314} <= events, ('missing workshop, billing or accounting audit events', sorted(events))
assert len(correlations) > 5, ('correlation scope missing from HTTP diagnostics', len(correlations))
print('PASS B14 diagnosable logs: workshop/billing/accounting audit events and distinct correlation IDs, no credentials or tokens')
