#!/bin/sh
# Reuse the proven ephemeral stack and cleanup, with B11 real fault probes.
set -eu
export B10_BEHAVIOR=b11
# Exercise container replacement deterministically, not just a same-container process restart.
export B11_FORCE_API_RECREATE="${B11_FORCE_API_RECREATE:-true}"
exec sh scripts/run-b10-tests.sh
