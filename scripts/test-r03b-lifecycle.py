#!/usr/bin/env python3
"""Actual TERM of R03.b with Chromium and a separate SQL lock holder alive."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
legacy=load('lifecycle','scripts/test-r00b-lifecycle.py')
acceptance=load('r03b','scripts/run-r03b-tests.py')
legacy.RUNNER=ROOT/'scripts/run-r03b-tests.py'
legacy.MARKER=b'R03B_LIFECYCLE hold-order:'
legacy.runner=acceptance.r00
import contextlib
import io
# The reused assertion primitive has an R00/paused-database-specific label.
# Suppress that label; its actual readback assertions still execute unmodified.
with contextlib.redirect_stdout(io.StringIO()):
    legacy.actual_term_probe()
print('PASS actual R03.b TERM with Chromium and held SQL barrier alive; children/resources removed; protected inventory unchanged.')
