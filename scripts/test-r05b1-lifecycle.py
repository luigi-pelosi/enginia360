#!/usr/bin/env python3
"""Actual TERM through the same guarded R05.b.0 lifecycle, with the Giobby protocol fake."""
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
acceptance = load('sales_order', 'scripts/run-r05b1-tests.py')
legacy.RUNNER = ROOT/'scripts/run-r05b1-tests.py'
legacy.MARKER = b'R03C_LIFECYCLE hold-dispatch'
legacy.runner = acceptance.binding.r00
with contextlib.redirect_stdout(io.StringIO()): legacy.actual_term_probe()
print('PASS actual R05B1 TERM with Chromium and held SQL dispatch barrier; children/resources removed; protected inventory unchanged.')
