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
with contextlib.redirect_stdout(io.StringIO()):legacy.actual_term_probe()
print('PASS actual R04.b.2b.3 TERM with Chromium and held physical purchase-dispatch claim lock alive; children/resources removed; protected inventory unchanged.')
