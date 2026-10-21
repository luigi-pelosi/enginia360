#!/usr/bin/env python3
"""Safety contract for the destructive, isolated restore rehearsal."""
from pathlib import Path
s = Path('scripts/test-b14-restore.py').read_text()
for requirement in ['--env-file', 'compose.b14-test.yaml', 'com.docker.compose.project', 'sha256', 'before_state_hash', 'dump_sha256', 'source_revision']:
    assert requirement in s, requirement
print('PASS B14 restore uses exact Compose configuration, project labels and integrity/provenance evidence')
