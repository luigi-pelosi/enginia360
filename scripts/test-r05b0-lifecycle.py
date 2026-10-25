#!/usr/bin/env python3
"""Actual R05.b.0 TERM, using the established exact-target cleanup assertions."""
import contextlib
import importlib.util
import io
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
legacy = load('lifecycle', 'scripts/test-r00b-lifecycle.py')
acceptance = load('r05b0', 'scripts/run-r05b0-tests.py')
legacy.RUNNER = ROOT/'scripts/run-r05b0-tests.py'
legacy.MARKER = b'R03C_LIFECYCLE hold-dispatch'
legacy.runner = acceptance.r00
with contextlib.redirect_stdout(io.StringIO()): legacy.actual_term_probe()
print('PASS actual R05B0 TERM with Chromium and held SQL dispatch barrier; all children/resources removed; protected inventory unchanged.')
