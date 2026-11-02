#!/usr/bin/env python3
"""Ephemeral MVP-01 only: locked verify/build, isolated HTTP/Chromium, exact cleanup."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--evidence-dir', required=True)
    args = parser.parse_args()
    evidence = Path(args.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    evidence.chmod(0o777)  # only this explicitly selected synthetic artifact directory
    name = 'enginia360-mvp01-' + uuid.uuid4().hex[:12]
    app, browser, network = name + '-app', name + '-browser', name + '-net'
    images = [name + ':runtime', name + ':browser']
    common = ['--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
              '--pids-limit=256', '--memory=1g', '--cpus=2',
              '--log-opt=max-size=2m', '--log-opt=max-file=1',
              '--tmpfs', '/scratch:rw,nosuid,nodev,size=256m,mode=1777',
              '-e', 'TMPDIR=/scratch', '-e', 'HOME=/scratch']
    def run(command, check=True):
        print('+', ' '.join(command), flush=True)
        return subprocess.run(command, cwd=ROOT, check=check, text=True)
    def output(command):
        return subprocess.check_output(command, cwd=ROOT, text=True).strip()
    def interrupted(signum, frame):
        raise InterruptedError(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        run(['docker', 'build', '--progress=plain', '--target', 'runtime', '-t', images[0], 'frontend'])
        if args.build_only:
            print('PASS locked install, dependency audit (low threshold), unit test, production build, typecheck', flush=True)
            return
        run(['docker', 'build', '--progress=plain', '--target', 'browser', '-t', images[1], 'frontend'])
        run(['docker', 'network', 'create', '--internal', network])
        run(['docker', 'run', '-d', '--name', app, '--network', network, '--network-alias', 'shell',
             '--user', '1000:1000', *common, images[0]])
        for _ in range(60):
            state = output(['docker', 'inspect', '--format', '{{.State.Health.Status}}', app])
            if state == 'healthy': break
            if state == 'unhealthy': raise RuntimeError('shell failed health check')
            time.sleep(1)
        else: raise TimeoutError('shell health deadline')
        metadata = json.loads(output(['docker', 'inspect', app]))[0]
        (evidence / 'container-inspect.json').write_text(json.dumps({
            'Config': metadata['Config'], 'HostConfig': metadata['HostConfig'],
            'State': metadata['State'], 'NetworkSettings': metadata['NetworkSettings']}, indent=2))
        run(['docker', 'run', '--name', browser, '--network', network, '--user', '1001:1001',
             *common, '--shm-size=256m', '-e', 'MVP01_BASE_URL=http://shell:3000',
             '--mount', f'type=bind,src={evidence},dst=/evidence', images[1]])
        print('PASS production HTTP SSR, seven domains, untrusted context ignored, no shared cache, Chromium keyboard/layout 1440/1366/390', flush=True)
    finally:
        for container in (browser, app):
            if subprocess.run(['docker', 'container', 'inspect', container], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                if container == browser:
                    copied = run(['docker', 'cp', f'{browser}:/scratch/results', str(evidence / 'browser-results')], check=False)
                    if copied.returncode != 0:
                        print('Browser results unavailable (browser may not have started); see retained logs', flush=True)
                with (evidence / (container.rsplit('-', 1)[-1] + '.log')).open('w') as log:
                    subprocess.run(['docker', 'logs', container], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                run(['docker', 'rm', '-f', container])
        if subprocess.run(['docker', 'network', 'inspect', network], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            run(['docker', 'network', 'rm', network])
        for image in images:
            if subprocess.run(['docker', 'image', 'inspect', image], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                run(['docker', 'image', 'rm', image])
        remaining = output(['docker', 'ps', '-aq', '--filter', f'name={name}'])
        networks = output(['docker', 'network', 'ls', '-q', '--filter', f'name={name}'])
        if remaining or networks: raise RuntimeError('owned resources survived cleanup')
        print('PASS exact owned container/network cleanup; no volumes or published ports created', flush=True)

if __name__ == '__main__': main()
