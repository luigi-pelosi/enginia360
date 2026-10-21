#!/usr/bin/env python3
"""Read back security settings of the exact ephemeral project's running services."""
import json
import re
import subprocess
import sys
project=sys.argv[1]
assert re.fullmatch(r'enginia360-b14-[0-9]+',project)
ids=subprocess.check_output(['docker','ps','-q','--filter','label=com.docker.compose.project='+project],text=True).split()
assert len(ids)==5, len(ids)
for c in json.loads(subprocess.check_output(['docker','inspect',*ids])):
    assert c['Config']['Labels']['com.docker.compose.project']==project
    h=c['HostConfig']
    assert c['Config']['User'] not in ('','0','root','0:0')
    assert h['ReadonlyRootfs'] and 'ALL' in h['CapDrop']
    assert 'no-new-privileges:true' in h['SecurityOpt']
    assert not h['PortBindings'], 'service ports published'
    assert h['Memory']>0 and h['NanoCpus']>0 and h['PidsLimit']>0
    assert h['LogConfig']['Config']['max-size'] and h['LogConfig']['Config']['max-file']
print('PASS B14 exact-label runtime hardening: five nonroot/read-only/bounded services, dropped capabilities, no published ports')
