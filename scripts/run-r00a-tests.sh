#!/bin/sh
# R00_MIGRATION_TESTS=1 and test-r00-migrations.py selection live in the Python runner.
# Destructive cleanup verifies com.docker.compose.project and exact dedicated configuration.
set -eu
exec python3 "$(dirname "$0")/run-r00a-tests.py"
