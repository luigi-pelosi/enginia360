#!/usr/bin/env python3
"""Actual TERM of R04.b.2a while Chromium and a separate physical SQL line-lock barrier are alive."""
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
acceptance = load('purchase', 'scripts/run-r04b2a-tests.py')
legacy.RUNNER = ROOT/'scripts/run-r04b2a-tests.py'
legacy.PROBE_DEADLINE_SECONDS = 420
legacy.MARKER = b'R03C_LIFECYCLE hold-line'
legacy.runner = acceptance.binding.r00
with contextlib.redirect_stdout(io.StringIO()): legacy.actual_term_probe()
print('PASS actual R04.b.2a TERM with Chromium and held SQL line lock alive; children/resources removed; protected inventory unchanged.')
