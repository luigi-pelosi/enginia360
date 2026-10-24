#!/usr/bin/env python3
"""Actual TERM of R04.c.1 while Chromium and its separate physical SQL line-lock barrier are alive."""

import contextlib
import importlib.util
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


legacy = load("lifecycle", "scripts/test-r00b-lifecycle.py")
acceptance = load("r04c1", "scripts/run-r04c1-tests.py")
legacy.RUNNER = ROOT / "scripts/run-r04c1-tests.py"
# Cold build and startup alone take ~220s on a loaded host; the first held line lock follows.
legacy.PROBE_DEADLINE_SECONDS = 420
legacy.MARKER = b"R04A_LIFECYCLE hold-line:"
legacy.runner = acceptance.r00
with contextlib.redirect_stdout(io.StringIO()):
    legacy.actual_term_probe()
print(
    "PASS actual R04.c.1 TERM with Chromium and held SQL line lock alive; children/resources removed; protected inventory unchanged."
)
