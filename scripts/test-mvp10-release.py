#!/usr/bin/env python3
"""FINAL-only stdlib source packaging regressions. No installation/runtime/publishing."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/mvp10_release.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FUTURE = (m.datetime.datetime.now(m.datetime.timezone.utc) + m.datetime.timedelta(days=7)).isoformat()


class ReleaseTests(unittest.TestCase):
    def test_policy_is_explicit_and_contains_actual_build_inputs_no_fixtures(self):
        policy = m.read_json(ROOT / 'docs/mvp10-source-policy.json')
        m.validate_policy(policy)
        for path in ('frontend/Dockerfile', 'frontend/package-lock.json', 'src/Enginia360.Api/Dockerfile',
                     'Directory.Build.props', 'global.json', 'database/runtime/manifest.json',
                     'database/runtime/migrations/0046_document_development.sql'):
            self.assertIn(path, policy['paths'])
        for path in policy['paths']:
            self.assertTrue((ROOT/path).is_file(), path)
            self.assertTrue(m.safe_path(path), path)
            self.assertFalse(path.startswith(('tests/', 'keycloak/', 'web/')), path)
        for path in ('.env', 'frontend/.env.example', 'frontend/.ENV.local', 'src/secrets.json', 'src/a/obj/a.cs',
                     '../src/a.cs', '/src/a.cs', 'src/a\\b.cs', 'frontend/node_modules/a.js',
                     'tests/fixtures/password.json', 'docs/raw.log', 'src/a.pfx'):
            with self.assertRaises(ValueError):m.validate_policy(dict(policy, paths=policy['paths']+[path]))
        for mutate in (lambda p:p['paths'].append(p['paths'][0]), lambda p:p.update(unknown=True)):
            p=copy.deepcopy(policy);mutate(p)
            with self.assertRaises(ValueError):m.validate_policy(p)

    def test_complete_build_closure_actual_inventory_and_missing_input_refusals(self):
        policy=m.read_json(ROOT/'docs/mvp10-source-policy.json')
        paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        read=lambda p:(ROOT/p).read_bytes()
        required=m.validate_build_inputs(paths,policy,read)
        self.assertGreater(len(required),150)
        # Every selected source/build input is necessary; omission fails closed.
        for missing in required:
            p=copy.deepcopy(policy);p['paths'].remove(missing)
            with self.subTest(missing=missing),self.assertRaises(ValueError):m.validate_build_inputs(paths,p,read)
        for new in ('src/Modules/New/Input.cs','frontend/lib/missing.ts','Directory.Packages.props'):
            with self.subTest(new=new),self.assertRaises(ValueError):m.validate_build_inputs(paths+[new],policy,read)
        for path,payload in (
            ('src/Enginia360.Api/Dockerfile', b'COPY unavailable.cs ./\n'),
            ('src/Enginia360.Api/Dockerfile', b'COPY ["src", "src"]\n'),
            ('src/Enginia360.Api/Dockerfile', b'ADD https://example.invalid/input ./\n'),
            ('src/Enginia360.Api/Enginia360.Api.csproj', b'<Project><ItemGroup><ProjectReference Include="../missing.csproj"/></ItemGroup></Project>'),
            ('src/Enginia360.Api/Enginia360.Api.csproj', b'<Project><Import Project="../../outside.props"/></Project>'),
            ('frontend/package.json',b'{"dependencies":{"input":"file:../unavailable"}}')):
            with self.subTest(path=path),self.assertRaises(ValueError):
                m.validate_build_inputs(paths,policy,lambda p:payload if p==path else read(p))
        # Static scan only: do not assemble the real candidate's release assets.
        for path in policy['paths']:
            data=read(path)
            self.assertNotRegex(data, rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----|(?:postgres(?:ql)?|https?)://[^\s/:]+:[^\s/@]+@|gh[pousr]_[A-Za-z0-9]{20,}')

    def test_strict_json_duplicate_keys_and_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'data.json'
            for data in ('{"a":1,"a":2}', 'x'*(m.MAX_JSON+1)):
                p.write_text(data)
                with self.assertRaises(ValueError):m.read_json(p)

    def test_archive_determinism_hashes_modes_and_rejection(self):
        records=[('src/a.cs', b'class A {}\n', 0o644), ('scripts/a.py', b'print(1)\n', 0o755)]
        a,files=m.source_archive(records);b,_=m.source_archive(list(reversed(records)))
        self.assertEqual(a,b)
        with tarfile.open(fileobj=io.BytesIO(a), mode='r:gz') as tf:
            self.assertEqual(tf.getnames(), ['enginia360/scripts/a.py','enginia360/src/a.cs'])
            for item in tf.getmembers():
                self.assertEqual((item.uid,item.gid,item.mtime),(0,0,0))
                stream=tf.extractfile(item);assert stream is not None
                self.assertEqual(hashlib.sha256(stream.read()).hexdigest(), files[item.name.split('/',1)[1]]['sha256'])
        for path,payload in [('src/.env',b'x'),('src/a.cs', b'-----BEGIN PRIVATE KEY-----'),
                             ('src/a.cs', b'postgres://user:pass@host/db')]:
            with self.assertRaises(ValueError):m.source_archive([(path,payload,0o644)])
        with self.assertRaises(ValueError):m.source_archive([records[0],records[0]])

    def test_git_archive_rejects_links_missing_paths_and_unlisted_files(self):
        def archive(name,kind):
            output=io.BytesIO()
            with tarfile.open(fileobj=output,mode='w') as tf:
                item=tarfile.TarInfo(name);item.type=kind
                if kind==tarfile.SYMTYPE:item.linkname='/private/secret'
                tf.addfile(item)
            return output.getvalue()
        policy=dict(schemaVersion=1,repository=m.REPOSITORY,paths=['src/a.cs'])
        for raw in (archive('src/a.cs',tarfile.SYMTYPE),archive('src/unlisted.cs',tarfile.REGTYPE),archive('src',tarfile.DIRTYPE)):
            with mock.patch.object(m,'git',return_value=raw),self.assertRaises(ValueError):m.git_records(ROOT,'a'*40,policy)

    def test_remote_jobs_require_actual_steps_every_named_job_no_skip_or_missing(self):
        jobs=[dict(id=1,name='impact',conclusion='success',status='completed',steps=[dict(number=1,name='guard',status='completed',conclusion='success')])]
        self.assertEqual(m.required_jobs(jobs,['impact'])[0]['id'],1)
        for mutate in (lambda j:j[0].update(conclusion='skipped'), lambda j:j[0]['steps'][0].update(conclusion='skipped'),
                       lambda j:j[0].update(steps=[]), lambda j:j.append(copy.deepcopy(j[0])), lambda j:j.clear(),
                       lambda j:j[0].update(id=True), lambda j:j[0]['steps'][0].update(number=True),
                       lambda j:j[0]['steps'][0].update(name='unsafe\nmetadata'),
                       lambda j:j[0]['steps'].append(copy.deepcopy(j[0]['steps'][0]))):
            j=copy.deepcopy(jobs);mutate(j)
            with self.assertRaises(ValueError):m.required_jobs(j,['impact'])
        with self.assertRaises(ValueError):m.required_jobs(jobs,[])
        with self.assertRaises(ValueError):m.required_jobs(jobs,['impact','impact'])

    def test_review_input_no_extra_fields_or_private_payload_projection(self):
        doc=dict(schemaVersion=1,runs=[dict(id=1,role='release-validation',requiredJobs=['impact'],artifacts=[])],proofs=[dict(name='parent-readback.json',path='/private/parent.json')])
        m.validate_review(doc)
        for mutation in (lambda d:d.update(rawCapture='unsafe'),lambda d:d['runs'][0].update(role='operational'),
                         lambda d:d['proofs'][0].update(name='../private'),lambda d:d['runs'][0].update(id=True),
                         lambda d:d.update(runs=[])):
            d=copy.deepcopy(doc);mutation(d)
            with self.assertRaises(ValueError):m.validate_review(d)

    def test_build_collects_real_files_remote_bindings_and_local_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'repo';root.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
            git('init','-q');git('config','user.name','Synthetic test');git('config','user.email','test@example.invalid')
            inputs = [('frontend/package.json','{"version":"0.1.0"}'), ('src/a.cs','class A {}'),
                      ('frontend/package-lock.json','{}'), ('Directory.Build.props','<Project/>'),
                      ('global.json','{}'), ('src/Enginia360.Api/Dockerfile','COPY src/ src/\nCOPY Directory.Build.props global.json ./\n'),
                      ('frontend/Dockerfile','COPY . .\n')]
            for path,text in inputs:
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            policy=dict(schemaVersion=1,repository='luigi-pelosi/enginia360',paths=sorted(path for path,_ in inputs))
            p=root/'docs/mvp10-source-policy.json';p.parent.mkdir();p.write_text(json.dumps(policy))
            # Clearly synthetic parser fixture, not claimed real remote evidence.
            baseline=dict(jobs=[dict(name='baseline-guard')],artifacts=[])
            (root/'docs/mvp10-functional-baseline.json').write_text(json.dumps(baseline))
            git('add','.');git('commit','-qm','synthetic fixture')
            head=git('rev-parse','HEAD');tree=git('rev-parse','HEAD^{tree}')
            proof=Path(directory)/'private-proof.json';proof.write_text('{"private":"NOT EXPORTED"}')
            artifact=Path(directory)/'actual.zip';artifact.write_bytes(b'actual downloaded bytes')
            digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
            review=dict(schemaVersion=1,runs=[dict(id=7,role='release-validation',requiredJobs=['impact','affected-mvp-offline'],artifacts=[dict(id=8,path=str(artifact))]),dict(id=42194906237,role='inherited-functional',requiredJobs=['baseline-guard'],artifacts=[])],proofs=[dict(name='parent-readback.json',path=str(proof))])
            reviewpath=Path(directory)/'review.json';reviewpath.write_text(json.dumps(review))
            def api(endpoint):
                if endpoint=='':return dict(full_name=policy['repository'],visibility='public',private=False)
                if endpoint=='actions/runs/7':return dict(id=7,head_sha=head,status='completed',conclusion='success',event='pull_request',run_attempt=1)
                if endpoint.startswith('commits/'):
                    return dict(sha=endpoint.split('/')[1],commit=dict(tree=dict(sha=tree)))
                if endpoint.startswith('compare/'):
                    return dict(status='identical',merge_base_commit=dict(sha=head))
                if endpoint=='actions/runs/42194906237':
                    return dict(id=42194906237,head_sha=m.INHERITED_HEAD,status='completed',conclusion='success',event='workflow_dispatch',run_attempt=1)
                if endpoint=='actions/runs/42194906237/jobs?per_page=100&page=1':
                    return dict(total_count=1,jobs=[dict(id=10,name='baseline-guard',status='completed',conclusion='success',steps=[dict(number=1,name='guard',status='completed',conclusion='success')])])
                if endpoint=='actions/runs/7/jobs?per_page=100&page=1':return dict(total_count=2,jobs=[dict(id=9+i,name=name,status='completed',conclusion='success',steps=[dict(number=1,name='guard',status='completed',conclusion='success')]) for i,name in enumerate(('impact','affected-mvp-offline'))])
                if endpoint=='actions/artifacts/8':return dict(id=8,name='proof',expired=False,expires_at=FUTURE,digest='sha256:'+digest,workflow_run=dict(id=7,head_sha=head))
                raise AssertionError(endpoint)
            out=Path(directory)/'assets'
            with mock.patch.object(m,'github',side_effect=api):
                result=m.build(root,head,head,reviewpath,out,'public',True)
            self.assertEqual(result['tree'],tree)
            self.assertEqual(result['version'],'v0.1.0-mvp.10.rc.'+head[:12])
            self.assertNotIn('NOT EXPORTED',(out/'provenance.json').read_text())
            self.assertNotIn('/private/',(out/'provenance.json').read_text())
            m.verify(out,root)
            cli=subprocess.run(['python3','-I',str(ROOT/'scripts/mvp10_release.py'),'verify','--output',str(out),'--repo',str(root)],text=True,capture_output=True)
            self.assertEqual(cli.returncode,0,cli.stderr)
            self.assertEqual(json.loads(cli.stdout)['status'],'SOURCE_ASSET_INTEGRITY_ONLY')
            saved={p.name:p.read_bytes() for p in out.iterdir()}
            # Malicious payloads have fresh checksums: the verifier must reject
            # the structure, not merely notice stale SHA256SUMS.
            for name,kind,mode in [('enginia360/../escape',tarfile.REGTYPE,0o644),
                                   ('enginia360/src/a.cs',tarfile.SYMTYPE,0o644),
                                   ('enginia360/src/a.cs',tarfile.REGTYPE,0o777)]:
                raw=io.BytesIO()
                with tarfile.open(fileobj=raw,mode='w:gz') as tf:
                    item=tarfile.TarInfo(name);item.type=kind;item.mode=mode
                    tf.addfile(item)
                data=raw.getvalue();(out/'enginia360-source.tar.gz').write_bytes(data)
                doc=json.loads(saved['provenance.json']);doc['assets']['enginia360-source.tar.gz']=dict(sha256=m.sha(data),size=len(data))
                (out/'provenance.json').write_bytes(m.encoded(doc))
                (out/'SHA256SUMS').write_text(m.file_hash(out/'enginia360-source.tar.gz')+'  enginia360-source.tar.gz\n'+m.file_hash(out/'provenance.json')+'  provenance.json\n')
                with self.subTest(name=name,mode=mode),self.assertRaises(ValueError):m.verify(out,root)
            for name,data in saved.items():(out/name).write_bytes(data)
            # Main reachability/TREE/visibility must come from readback, not labels.
            for label,endpoint,bad in [
                    ('visibility','',dict(full_name=m.REPOSITORY,visibility='private',private=True)),
                    ('tree','commits/'+head,dict(sha=head,commit=dict(tree=dict(sha='0'*40)))),
                    ('not-main','compare/'+head+'...main',dict(status='diverged',merge_base_commit=dict(sha='0'*40)))]:
                def refused(e):return bad if e==endpoint else api(e)
                with mock.patch.object(m,'github',side_effect=refused),self.assertRaises(ValueError):
                    m.build(root,head,head,reviewpath,Path(directory)/label,'public',True)
            (out/'enginia360-source.tar.gz').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):m.verify(out,root)
            with self.assertRaises(ValueError):m.build(root,head,head,reviewpath,out,'public',True)
            with self.assertRaises(ValueError):m.build(root,head,head,reviewpath,Path(directory)/'no-review','public',False)

    def test_remote_projection_refuses_visibility_head_artifact_and_step_mismatches(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact=Path(directory)/'archive.zip';artifact.write_bytes(b'actual bytes')
            head='a'*40
            review=dict(schemaVersion=1,runs=[dict(id=1,role='release-validation',requiredJobs=['impact'],artifacts=[dict(id=2,path=str(artifact))])],proofs=[])
            responses={
                '':dict(full_name=m.REPOSITORY,visibility='public',private=False),
                'actions/runs/1':dict(id=1,head_sha=head,status='completed',conclusion='success',event='pull_request',run_attempt=1),
                'actions/runs/1/jobs?per_page=100&page=1':dict(total_count=1,jobs=[dict(id=3,name='impact',status='completed',conclusion='success',steps=[dict(name='guard',number=1,status='completed',conclusion='success')])]),
                'actions/artifacts/2':dict(id=2,name='proof',expired=False,workflow_run=dict(id=1,head_sha=head),digest='sha256:'+m.file_hash(artifact),expires_at=FUTURE)}
            with mock.patch.object(m,'github',side_effect=lambda endpoint:responses[endpoint]):
                public=m.remote_provenance(review,head,'public')
            self.assertEqual(public[0]['artifacts'][0]['sha256'],m.file_hash(artifact))
            for endpoint,mutation in [('',lambda v:v.update(visibility='private')),
                                      ('actions/runs/1',lambda v:v.update(head_sha='b'*40)),
                                      ('actions/runs/1',lambda v:v.update(conclusion='failure')),
                                      ('actions/runs/1',lambda v:v.update(id=True)),
                                      ('actions/runs/1',lambda v:v.update(event='push')),
                                      ('actions/runs/1',lambda v:v.update(run_attempt=True)),
                                      ('actions/runs/1/jobs?per_page=100&page=1',lambda v:v.update(total_count=True)),
                                      ('actions/runs/1/jobs?per_page=100&page=1',lambda v:v['jobs'][0]['steps'][0].update(conclusion='skipped')),
                                      ('actions/artifacts/2',lambda v:v.update(expired=True)),
                                      ('actions/artifacts/2',lambda v:v.update(expired=0)),
                                      ('actions/artifacts/2',lambda v:v.update(expires_at='2000-01-01T00:00:00Z')),
                                      ('actions/artifacts/2',lambda v:v.update(expires_at='2099-01-01T00:00:00')),
                                      ('actions/artifacts/2',lambda v:v.update(name='/private/path')),
                                      ('actions/artifacts/2',lambda v:v.update(digest='sha256:'+'0'*64)),
                                      ('actions/artifacts/2',lambda v:v['workflow_run'].update(id=99))]:
                data=copy.deepcopy(responses);mutation(data[endpoint])
                with mock.patch.object(m,'github',side_effect=lambda e:data[e]),self.assertRaises(ValueError):m.remote_provenance(review,head,'public')

    def test_unsafe_git_modes_and_tree_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);subprocess.run(['git','init','-q',str(root)],check=True)
            for token in ('HEAD','a'*39,'A'*40,'--help'):
                with self.assertRaises(ValueError):m.commit_tree(root,token)
            for path in ('src/x',):
                self.assertTrue(m.safe_path(path))

    def test_current_status_readiness_and_source_contract_no_operational_promotion(self):
        readiness=m.read_json(ROOT/'docs/mvp10-readiness.json')
        self.assertFalse(readiness['operationalReady'])
        self.assertEqual(readiness['publication']['status'],'PENDING')
        self.assertEqual(readiness['functional']['status'],'VERIFIED_MVP09')
        self.assertEqual(set(g['status'] for g in readiness['gates']),{'OPEN'})
        self.assertEqual({g['id'] for g in readiness['gates']},{'target-access','identity','recovery','privacy','monitoring-maintenance'})
        for gate in readiness['gates']:
            self.assertIsNone(gate['target']);self.assertEqual(gate['proofs'],[])
            self.assertTrue(gate['ownerInput']);self.assertTrue(gate['requiredProof'])
        backlog=m.read_json(ROOT/'docs/mvp-backlog.json');items={x['id']:x for x in backlog['items']}
        self.assertEqual(items['MVP-09']['status'],'done')
        self.assertEqual(items['MVP-10']['status'],'in_progress')
        self.assertEqual(items['MVP-10']['validationStatus'],'UNEXECUTED')
        self.assertFalse(items['MVP-10']['operationalReady'])
        text=(ROOT/'docs/mvp10-source-release.md').read_text()
        for token in ('SOURCE_COMPLETE_UNVERIFIED','--public-metadata-reviewed','SHA256SUMS','mvp10_release.py verify',
                      'No downgrade SQL','#149 remains OPEN','Node 24.22.0','46 published','not a production Compose'):
            self.assertIn(token,text)


if __name__=='__main__':unittest.main(verbosity=2)
