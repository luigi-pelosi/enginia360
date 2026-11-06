#!/usr/bin/env python3
"""FINAL-only source RC packaging/integrity; never builds, deploys or publishes.

Requires Git/Python stdlib and gh for build-time readbacks. Input review files are
private; output contains typed metadata and hashes only. Integrity is not trust,
functional acceptance, a new main CI run or operational readiness.
"""
import argparse
import datetime
import fnmatch
import posixpath
import shlex
import xml.etree.ElementTree as ET
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

MAX_JSON = 4 * 1024 * 1024
MAX_SOURCE = 100 * 1024 * 1024
REPOSITORY = 'luigi-pelosi/enginia360'
INHERITED_HEAD = 'e36697723d9d8ae96022cd0779bcc83958fc7f9f'
INHERITED_TREE = '8e2230c67865f1199a47a2d75c58cef0fa9caf52'
POLICY = 'docs/mvp10-source-policy.json'
COMMANDS = ['python3 -I scripts/test-mvp10-release.py',
            'python3 -I scripts/test-mvp10-impact.py',
            'python3 -I scripts/test-mvp09-contract.py',
            'python3 -I scripts/test-mvp-baseline.py',
            'python3 -I scripts/test-mvp-impact.py']
LIMITATIONS = ['source-only prerelease; no prebuilt binary or container image',
               'not operationally ready; target identity recovery privacy maintenance gates OPEN',
               'inherited functional evidence is not a new release-head runtime execution',
               'artifact URLs may expire or require authorization; hashes do not grant access',
               'GitHub automatic source downloads contain the full historical test checkout',
               'SHA256 integrity does not independently authenticate the publisher']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, keys):
    require(isinstance(value, dict) and set(value) == set(keys), 'unexpected or missing fields')


def positive(value):
    require(type(value) is int and value > 0, 'expected positive integer ID')


def digest(value, size=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{'+str(size)+'}', value), 'invalid exact digest')
    return value


def unique(values):
    require(isinstance(values, list) and bool(values), 'nonempty array required')
    require(len(values) == len(set(values)), 'duplicate entries refused')


def read_json(path):
    data = Path(path).read_bytes()
    require(len(data) <= MAX_JSON, 'JSON size limit exceeded')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)+'\n').encode()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def commit_tree(root, commit):
    digest(commit, 40)
    require(git(root, 'rev-parse', commit+'^{commit}').decode().strip() == commit, 'exact commit required')
    return digest(git(root, 'rev-parse', commit+'^{tree}').decode().strip(), 40)


def safe_path(path):
    if not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_./@\[\]-]+', path):
        return False
    p = PurePosixPath(path)
    if p.is_absolute() or str(p) != path or any(x in ('', '.', '..') for x in path.split('/')):
        return False
    forbidden = {'node_modules', '.git', '.next', 'bin', 'obj', 'dist', 'coverage', 'test-results',
                 'playwright-report', '__pycache__', 'fixtures', 'captures', 'logs', 'secrets', 'configenv'}
    if any(x.lower() in forbidden or x.lower().startswith('.env') or 'secret' in x.lower() for x in p.parts):
        return False
    return p.suffix.lower() not in {'.log', '.zip', '.gz', '.tar', '.dump', '.bak', '.pem', '.key', '.pfx', '.p12', '.tsbuildinfo', '.pyc'}


def validate_policy(policy):
    fields(policy, ('schemaVersion', 'repository', 'paths'))
    require(type(policy['schemaVersion']) is int and policy['schemaVersion'] == 1, 'policy version')
    require(policy['repository'] == REPOSITORY, 'repository boundary')
    unique(policy['paths'])
    require(all(safe_path(p) and not p.startswith(('tests/', 'keycloak/', 'web/')) for p in policy['paths']), 'unsafe source allowlist')


def validate_build_inputs(paths, policy, read):
    """Finite conservative closure of the *existing* two build contexts.

    Every tracked src/frontend input is required, not just a few sentinel files.
    Unsupported new COPY/reference forms fail closed for explicit review. This
    is static completeness, not a substitute for the later extracted build.
    """
    validate_policy(policy)
    paths, allowed = set(paths), set(policy['paths'])
    required = {'Directory.Build.props', 'global.json', 'src/Enginia360.Api/Dockerfile',
                'frontend/Dockerfile', 'frontend/package.json', 'frontend/package-lock.json'}
    required |= {p for p in paths if p.startswith(('src/', 'frontend/'))}
    required |= {p for p in paths if '/' not in p and p.endswith(('.props', '.targets'))}
    require(required <= paths and required <= allowed, 'missing build input in committed source allowlist')
    for dockerfile, context in (('src/Enginia360.Api/Dockerfile', ''), ('frontend/Dockerfile', 'frontend/')):
        for line in read(dockerfile).decode().splitlines():
            if not re.match(r'^\s*(?:COPY|ADD)\s', line, re.I):
                continue
            words = shlex.split(line)
            require(words[0].upper() == 'COPY' and not line.rstrip().endswith('\\'), 'unsupported Docker build input form')
            if any(w.startswith('--from=') for w in words):
                continue  # Generated output from a prior stage, never host input.
            words = [w for w in words[1:] if not w.startswith('--')]
            require(len(words) >= 2 and not any('[' in w or '$' in w or '://' in w for w in words), 'unsupported COPY form')
            for value in words[:-1]:
                source = posixpath.normpath(context + value).rstrip('/')
                require(not source.startswith(('/', '../')), 'COPY outside source context')
                matches = {p for p in paths if source == '.' or p == source or p.startswith(source + '/') or fnmatch.fnmatchcase(p, source)}
                require(bool(matches) and matches <= allowed, 'COPY input missing from allowlist')
    for path in sorted(required):
        if not path.endswith(('.csproj', '.props', '.targets')):
            continue
        project = ET.fromstring(read(path))
        for node in project.iter():
            kind = node.tag.rsplit('}', 1)[-1]
            attr = 'Project' if kind == 'Import' else 'Include'
            if kind not in ('Import', 'ProjectReference', 'Compile', 'Content', 'EmbeddedResource', 'None') or attr not in node.attrib:
                continue
            value = node.attrib[attr].replace('\\', '/')
            require(not any(x in value for x in ('$', '@', ';', '*', '?')) and not value.startswith('/'), 'unsupported project input expression')
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), value))
            require(target in paths and target in allowed, 'unavailable referenced project/build input')
            if kind == 'ProjectReference':
                lock = posixpath.join(posixpath.dirname(target), 'packages.lock.json')
                require(lock in paths and lock in allowed, 'referenced project lock missing')
    package = json.loads(read('frontend/package.json'))
    for group in ('dependencies', 'devDependencies', 'optionalDependencies'):
        for version in package.get(group, {}).values():
            require(isinstance(version, str) and not version.startswith(('file:', 'link:', 'workspace:')), 'unreviewed external local npm input')
    return sorted(required)


def source_archive(records):
    require(bool(records), 'empty source refused')
    require(sum(len(data) for _, data, _ in records) <= MAX_SOURCE, 'source size limit')
    names = [path for path, _, _ in records]
    unique(names)
    output = io.BytesIO()
    files = {}
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tf:
            for path, data, mode in sorted(records):
                require(safe_path(path) and mode in (0o644, 0o755), 'unsafe archive entry')
                require(not re.search(rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----|(?:postgres(?:ql)?|https?)://[^\s/:]+:[^\s/@]+@|gh[pousr]_[A-Za-z0-9]{20,}', data), 'credential-shaped source refused; review without logging content')
                item = tarfile.TarInfo('enginia360/'+path)
                item.size, item.mode, item.mtime = len(data), mode, 0
                item.uid = item.gid = 0
                item.uname = item.gname = ''
                tf.addfile(item, io.BytesIO(data))
                files[path] = dict(sha256=sha(data), size=len(data), mode=format(mode, '04o'))
    return output.getvalue(), files


def git_records(root, commit, policy):
    # Git archive supplies committed bytes only: no worktree overlays, ignored
    # files, fixture directory recursion or local configuration can enter.
    raw = git(root, 'archive', '--format=tar', commit, '--', *policy['paths'])
    require(len(raw) <= MAX_SOURCE*2, 'Git archive size limit')
    records = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tf:
        for item in tf.getmembers():
            if item.isdir():
                continue
            require(item.isfile() and item.name in policy['paths'], 'symlink/submodule/unlisted entry refused')
            stream = tf.extractfile(item)
            if stream is None:
                raise ValueError('missing archive payload')
            records.append((item.name, stream.read(), 0o755 if item.mode & 0o111 else 0o644))
    require({p for p, _, _ in records} == set(policy['paths']), 'missing explicit source path')
    return records


def validate_review(doc):
    fields(doc, ('schemaVersion', 'runs', 'proofs'))
    require(type(doc['schemaVersion']) is int and doc['schemaVersion'] == 1, 'review version')
    require(isinstance(doc['runs'], list) and bool(doc['runs']), 'current remote proof required')
    ids = []
    for run in doc['runs']:
        fields(run, ('id', 'role', 'requiredJobs', 'artifacts'))
        positive(run['id']);ids.append(run['id'])
        require(run['role'] in ('release-validation', 'inherited-functional'), 'unknown proof role')
        unique(run['requiredJobs'])
        require(all(isinstance(n, str) and 0 < len(n) < 200 for n in run['requiredJobs']), 'job names')
        require(isinstance(run['artifacts'], list), 'artifact array')
        artifact_ids = []
        for item in run['artifacts']:
            fields(item, ('id', 'path'));positive(item['id']);artifact_ids.append(item['id'])
            require(isinstance(item['path'], str) and bool(item['path']), 'local artifact path')
        require(len(artifact_ids) == len(set(artifact_ids)), 'duplicate artifact')
    unique(ids)
    require(any(r['role'] == 'release-validation' for r in doc['runs']), 'release-head remote proof required')
    require(isinstance(doc['proofs'], list), 'proof array')
    names = []
    for proof in doc['proofs']:
        fields(proof, ('name', 'path'))
        require(isinstance(proof['name'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', proof['name']), 'sanitized proof name required')
        require(isinstance(proof['path'], str) and bool(proof['path']), 'proof file path')
        names.append(proof['name'])
    require(len(names) == len(set(names)), 'duplicate proof label')


def github(endpoint):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/'+REPOSITORY+('/'+endpoint if endpoint else '')], stderr=subprocess.PIPE))


def required_jobs(jobs, required):
    unique(required)
    selected = []
    for name in sorted(required):
        matches = [j for j in jobs if j['name'] == name]
        require(len(matches) == 1, 'missing/ambiguous required job')
        job = matches[0]
        positive(job['id'])
        require(job['status'] == 'completed' and job['conclusion'] == 'success', 'required job not success')
        require(isinstance(job['steps'], list) and bool(job['steps']), 'empty required job')
        steps = []
        numbers = []
        for step in job['steps']:
            positive(step['number']);numbers.append(step['number'])
            require(isinstance(step['name'], str) and 0 < len(step['name']) <= 300 and not any(ord(c) < 32 for c in step['name']), 'invalid step name')
            require(step['status'] == 'completed' and step['conclusion'] == 'success', 'required step skipped/failed/incomplete')
            steps.append(dict(number=step['number'], name=step['name'], conclusion='success'))
        unique(numbers)
        selected.append(dict(id=job['id'], name=name, conclusion='success', steps=steps))
    unique([j['id'] for j in selected])
    return selected


def remote_provenance(review, candidate, visibility):
    repo = github('')
    require(repo['full_name'] == REPOSITORY and repo['visibility'] == visibility and repo['private'] == (visibility == 'private'), 'fresh repository visibility differs from approved boundary')
    runs = []
    for record in review['runs']:
        rid = record['id']
        run = github('actions/runs/'+str(rid))
        expected = candidate if record['role'] == 'release-validation' else INHERITED_HEAD
        positive(run['id']);positive(run['run_attempt'])
        require(run['id'] == rid and run['head_sha'] == expected and run['status'] == 'completed' and run['conclusion'] == 'success', 'run/head/conclusion mismatch')
        require(run['event'] == ('pull_request' if record['role'] == 'release-validation' else 'workflow_dispatch'), 'unexpected proof event')
        jobs = []
        for page in range(1, 101):
            response = github(f'actions/runs/{rid}/jobs?per_page=100&page={page}')
            positive(response['total_count'])
            require(isinstance(response['jobs'], list), 'remote jobs array required')
            jobs.extend(response['jobs'])
            if len(jobs) >= response['total_count']:
                break
            require(bool(response['jobs']), 'truncated remote job list')
        else:
            raise ValueError('remote job pagination limit')
        require(len(jobs) == response['total_count'], 'remote job total mismatch')
        for job in jobs:positive(job['id'])
        unique([job['id'] for job in jobs])
        artifacts = []
        for reference in record['artifacts']:
            aid = reference['id'];artifact = github('actions/artifacts/'+str(aid))
            positive(artifact['id']);positive(artifact['workflow_run']['id'])
            require(artifact['id'] == aid and artifact['workflow_run']['id'] == rid and artifact['workflow_run']['head_sha'] == expected and artifact['expired'] is False, 'artifact provenance/expiry mismatch')
            require(isinstance(artifact['name'], str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', artifact['name']), 'unsafe public artifact name')
            expires = datetime.datetime.fromisoformat(artifact['expires_at'].replace('Z', '+00:00'))
            require(expires.tzinfo is not None and expires > datetime.datetime.now(datetime.timezone.utc), 'artifact expiry timestamp invalid/past')
            payload_hash = file_hash(Path(reference['path']))
            require(artifact.get('digest') == 'sha256:'+payload_hash, 'remote artifact digest missing or mismatch')
            artifacts.append(dict(id=aid, name=artifact['name'], sha256=payload_hash,
                                  githubDigest=artifact.get('digest'), expiresAt=artifact['expires_at'],
                                  url=f'https://github.com/{REPOSITORY}/actions/runs/{rid}/artifacts/{aid}'))
        runs.append(dict(id=rid, head=expected, role=record['role'], event=run['event'],
                         attempt=run['run_attempt'], conclusion='success',
                         url=f'https://github.com/{REPOSITORY}/actions/runs/{rid}',
                         jobs=required_jobs(jobs, record['requiredJobs']), artifacts=artifacts))
    return runs


def file_hash(path):
    require(path.is_file() and not path.is_symlink(), 'regular local evidence file required')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def build(root, commit, candidate, review_path, output, visibility, reviewed):
    require(reviewed is True, 'explicit public metadata review required, even for private publication')
    require(visibility in ('private', 'public'), 'explicit approved repository visibility required')
    root, output = Path(root).resolve(), Path(output).resolve()
    require(not output.exists() and output != root and root not in output.parents, 'new output directory outside checkout required')
    tree = commit_tree(root, commit)
    require(commit_tree(root, candidate) == tree, 'tested candidate and merged commit TREE differ')
    require(git(root, 'status', '--porcelain', '--untracked-files=all') == b'', 'clean committed source required')
    policy_bytes = git(root, 'show', commit+':'+POLICY)
    policy = json.loads(policy_bytes)
    validate_policy(policy)
    paths = git(root, 'ls-tree', '-r', '--name-only', commit).decode().splitlines()
    validate_build_inputs(paths, policy, lambda path: git(root, 'show', commit+':'+path))
    review = read_json(review_path);validate_review(review)
    package = json.loads(git(root, 'show', commit+':frontend/package.json'))
    require(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', package['version']), 'existing source version unsupported')
    # Verify actual remote object TREEs and main reachability, not only a local
    # caller-supplied label. No release/tag mutation is ever performed here.
    for identity in (commit, candidate):
        remote = github('commits/'+identity)
        require(remote['sha'] == identity and remote['commit']['tree']['sha'] == tree, 'remote commit/TREE mismatch')
    comparison = github('compare/'+commit+'...main')
    require(comparison['status'] in ('identical','ahead') and comparison['merge_base_commit']['sha'] == commit, 'release commit not on remote main history')
    baseline = json.loads(git(root, 'show', commit+':docs/mvp10-functional-baseline.json'))
    inherited = [r for r in review['runs'] if r['role'] == 'inherited-functional']
    require(len(inherited) == 1 and inherited[0]['id'] == 42194906237, 'exact MVP09 inherited proof required')
    require(set(inherited[0]['requiredJobs']) == {j['name'] for j in baseline['jobs']}, 'inherited required-job coverage mismatch')
    require({a['id'] for a in inherited[0]['artifacts']} == {a['id'] for a in baseline['artifacts']}, 'inherited artifact coverage mismatch')
    for current in (r for r in review['runs'] if r['role'] == 'release-validation'):
        require(set(current['requiredJobs']) == {'impact','affected-mvp-offline'}, 'MVP10 finite required-job set mismatch; review actual new impact before extending')
    runs = remote_provenance(review, candidate, visibility)
    historical = next(r for r in runs if r['role'] == 'inherited-functional')
    require({a['id']:a['sha256'] for a in historical['artifacts']} == {a['id']:a['sha256'] for a in baseline['artifacts']}, 'inherited artifact hashes differ from verified parent baseline')
    archive, files = source_archive(git_records(root, commit, policy))
    result = dict(schemaVersion=1, kind='source-supported-prerelease', repository=REPOSITORY,
                  visibility=visibility, version='v'+package['version']+'-mvp.10.rc.'+commit[:12],
                  commit=commit, testedCandidate=candidate, tree=tree, newMainCi=False,
                  operationalReady=False, sourcePolicySha256=sha(policy_bytes),
                  assets={'enginia360-source.tar.gz':dict(sha256=sha(archive),size=len(archive))},
                  files=files, runs=runs,
                  inheritedFunctional=dict(head=INHERITED_HEAD, tree=INHERITED_TREE, run=42194906237,
                                           applicability='unchanged MVP09 business runtime; parent impact review required'),
                  proofs=[dict(name=p['name'], sha256=file_hash(Path(p['path']))) for p in review['proofs']],
                  validationCommands=COMMANDS, limitations=LIMITATIONS)
    provenance = encoded(result)
    output.mkdir(mode=0o700, parents=True)
    (output/'enginia360-source.tar.gz').write_bytes(archive)
    (output/'provenance.json').write_bytes(provenance)
    (output/'SHA256SUMS').write_text(sha(archive)+'  enginia360-source.tar.gz\n'+sha(provenance)+'  provenance.json\n')
    verify(output, root)
    return result


def verify(output, root=None):
    output = Path(output)
    require({p.name for p in output.iterdir()} == {'enginia360-source.tar.gz','provenance.json','SHA256SUMS'}, 'unexpected/missing managed asset')
    sums = (output/'SHA256SUMS').read_text().splitlines()
    require(len(sums) == 2, 'checksum coverage')
    for line, name in zip(sums, ('enginia360-source.tar.gz','provenance.json')):
        require(line == file_hash(output/name)+'  '+name, 'managed asset checksum mismatch')
    doc = read_json(output/'provenance.json')
    require(doc['schemaVersion'] == 1 and doc['kind'] == 'source-supported-prerelease' and doc['repository'] == REPOSITORY, 'provenance kind')
    require(doc['operationalReady'] is False and doc['newMainCi'] is False, 'unsupported readiness claim')
    for key in ('commit','testedCandidate','tree'):digest(doc[key],40)
    require((output/'enginia360-source.tar.gz').stat().st_size <= MAX_SOURCE*2, 'compressed source limit')
    data = (output/'enginia360-source.tar.gz').read_bytes()
    require(doc['assets'] == {'enginia360-source.tar.gz':dict(sha256=sha(data),size=len(data))}, 'archive asset metadata')
    records = []
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tf:
        for item in tf:
            require(item.isfile() and item.name.startswith('enginia360/'), 'unsafe archive member')
            total += item.size
            require(total <= MAX_SOURCE and len(records) < 10000, 'expanded source limit')
            require((item.uid,item.gid,item.mtime,item.uname,item.gname) == (0,0,0,'',''), 'nondeterministic archive metadata')
            stream = tf.extractfile(item)
            if stream is None:
                raise ValueError('missing archive bytes')
            records.append((item.name[len('enginia360/'):],stream.read(),item.mode))
    canonical, files = source_archive(records)
    require(canonical == data and files == doc['files'], 'source manifest/mode/order mismatch')
    if root is not None:
        require(commit_tree(root,doc['commit']) == doc['tree'] == commit_tree(root,doc['testedCandidate']), 'local Git TREE mismatch')
        policy = json.loads(git(root,'show',doc['commit']+':'+POLICY));validate_policy(policy)
        require(sha(git(root,'show',doc['commit']+':'+POLICY)) == doc['sourcePolicySha256'], 'policy digest mismatch')
        expected, expected_files = source_archive(git_records(root,doc['commit'],policy))
        require(expected == data and expected_files == files, 'archive differs from exact committed allowlist')
    # Offline verifier checks bytes only; parent separately authenticates remote
    # run/job/artifact evidence and release tag/asset readbacks before publication.
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    b = sub.add_parser('build')
    b.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    b.add_argument('--commit',required=True);b.add_argument('--candidate',required=True)
    b.add_argument('--review',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
    b.add_argument('--visibility',choices=('public','private'),required=True)
    b.add_argument('--public-metadata-reviewed',action='store_true')
    v = sub.add_parser('verify');v.add_argument('--output',type=Path,required=True)
    v.add_argument('--repo',type=Path,help='also compare archive against exact Git commit/TREE')
    args = parser.parse_args()
    try:
        if args.action == 'build':
            result = build(args.repo,args.commit,args.candidate,args.review,args.output,args.visibility,args.public_metadata_reviewed)
        else:
            result = verify(args.output,args.repo)
        print(json.dumps(dict(status='SOURCE_ASSET_INTEGRITY_ONLY', version=result['version'],
                              commit=result['commit'],tree=result['tree'],operationalReady=False)))
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, tarfile.TarError):
        print('Source release refused: inspect source policy, exact commits, reviewed evidence and remote readbacks. No credentials logged.',file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
