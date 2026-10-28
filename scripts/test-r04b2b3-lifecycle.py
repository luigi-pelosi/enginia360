#!/usr/bin/env python3
"""Actual TERM with live Chromium and a held physical purchase-dispatch claim lock."""
import contextlib
import importlib.util
import io
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);assert spec and spec.loader
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
legacy=load('lifecycle','scripts/test-r00b-lifecycle.py')
acceptance=load('prices','scripts/run-r04b2b3-tests.py')
legacy.RUNNER=ROOT/'scripts/run-r04b2b3-tests.py'
legacy.PROBE_DEADLINE_SECONDS=420
legacy.MARKER=b'R03C_LIFECYCLE po-hold'
legacy.runner=acceptance.binding.r00
try:
 with contextlib.redirect_stdout(io.StringIO()):legacy.actual_term_probe()
except Exception as error:
 # Retain only error class/location, never child payloads, configuration or credentials.
 trace=error.__traceback__
 while trace is not None:
  if trace.tb_frame.f_code.co_name=='actual_term_probe':
   pending=trace.tb_frame.f_locals.get('pending',b'').decode('utf-8',errors='replace')
   for line in pending.splitlines():
    if line.startswith(('locator.', 'TimeoutError', 'TypeError', 'AssertionError', '    at login', '    at async')):
     print('TERM_CHILD_DIAGNOSTIC '+line[:300])
  trace=trace.tb_next
 raise
print('PASS actual R04.b.2b.3 TERM with Chromium and held physical purchase-dispatch claim lock alive; children/resources removed; protected inventory unchanged.')
