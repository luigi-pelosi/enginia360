#!/usr/bin/env python3
"""Actual TERM of R04.a while Chromium and its separate physical SQL stock barrier are alive."""

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
acceptance = load("r04a", "scripts/run-r04a-tests.py")
legacy.RUNNER = ROOT / "scripts/run-r04a-tests.py"
legacy.MARKER = b"R04A_LIFECYCLE hold-stock"
legacy.runner = acceptance.r00
with contextlib.redirect_stdout(io.StringIO()):
    legacy.actual_term_probe()
print(
    "PASS actual R04.a TERM with Chromium and held SQL stock lock alive; children/resources removed; protected inventory unchanged."
)
