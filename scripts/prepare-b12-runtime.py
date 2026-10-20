#!/usr/bin/env python3
"""Prepare one technically closed synthetic order for the B12 DOM runtime test."""
import importlib.util
import json
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
assert spec and spec.loader
b10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b10)
b10.b.BASE = sys.argv[1].rstrip('/')
status, order = b10.b.call('/orders', b10.b.alpha, 'POST', b10.b.body())
assert status == 201, (status, order)
status, line = b10.b.call(b10.order_path(order) + '/lines', b10.b.alpha, 'POST', b10.b06.b05.line_body('Service'))
assert status == 201, (status, line)
status, gate = b10.b09.gate(order, b10.b.alpha)
assert status == 200 and gate['status'] == 'Clear', (status, gate)
status, summary = b10.b.call(b10.order_path(order) + '/commercial-summary', b10.b.alpha)
assert status == 200, (status, summary)
status, closure = b10.close(order, summary['revision'])
assert status == 201, (status, closure)
print(json.dumps({'orderId': order['id'], 'revision': summary['revision']}))
