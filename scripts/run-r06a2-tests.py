#!/usr/bin/env python3
"""R06.a.2 STAGING-ONLY runner: one ephemeral PostgreSQL container, no app migrations, no caller-supplied target.

Synthetic probes only; this is not a product/domain migration and approves no real-table eligibility.
"""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('r06a2_storage_tests', Path(__file__).with_name('test-r06a2-storage.py'))
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

if __name__ == '__main__':
    raise SystemExit(module.main())
