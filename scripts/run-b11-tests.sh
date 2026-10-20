#!/bin/sh
# Reuse the proven ephemeral stack and cleanup, with B11 real fault probes.
set -eu
export B10_BEHAVIOR=b11
exec sh scripts/run-b10-tests.sh
