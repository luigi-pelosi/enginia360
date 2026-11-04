#!/usr/bin/env python3
"""D97 documentary consistency/mutation gate; never runtime acceptance."""
import argparse
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = 'docs/mvp03b-user-administration.md'
CURRENT = ('AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
           'docs/mvp-delivery-plan.md')
QUOTE = 'Può anche creare e modificare ruoli e permessi sempre auditando il tutto'
CLAUSES = (
    'D97', 'creare e modificare ruoli e permessi',
    'audit immutabile e tracciabile obbligatorio', 'solo nel proprio tenant',
    'distinta dalla delega organizzativa', 'nessun SUPER ADMIN',
    'nessun potere cross-tenant o control-plane', 'nessuna subdelega o nomina implicita',
    'non solo ruoli definiti dal proprietario', 'nessun runtime consegnato qui',
)
DETAILS = (
    QUOTE, 'Alternativa A (raccomandata, NON SCELTA)',
    'soltanto assegnare ruoli definiti dal SUPER ADMIN',
    'Alternativa B (SCELTA)', 'azioni e scope eseguibili supportati',
    'interpretazione tecnica minima dell’agente, correggibile',
    'non un nuovo tetto ai ruoli', 'non codice arbitrario né bypass delle autorizzazioni API',
    'etichette dei ruoli', 'promozione globale automatica vietata',
    'matching azione/scope', 'inviti e abilitazione',
    'revoca', 'concorrenza', 'SSR', 'RLS', 'prima del runtime',
    'attore', 'destinatario', 'prima/dopo', 'correlazione',
    'atomica', 'fail-closed', 'retention',
)
STALE = (
    "Il perimetro dei ruoli assegnabili e l'eventuale abilitazione di ulteriori amministratori restano da precisare",
    "Il perimetro dei ruoli e permessi assegnabili, inclusa l'eventuale abilitazione di ulteriori amministratori, resta da definire",
    'soltanto ruoli predefiniti dal proprietario',
    'creazione e modifica di ruoli e permessi non approvata',
    'audit runtime D97 già consegnato',
)


def block(text):
    start, end = '<!-- d97-current:start -->', '<!-- d97-current:end -->'
    assert text.count(start) == text.count(end) == 1, 'one D97 current block required'
    assert text.index(start) < text.index(end), 'D97 markers reversed'
    return text.split(start)[1].split(end)[0]


def validate(root):
    for relative in CURRENT:
        text = (root / relative).read_text()
        active = text.split('<!-- mvp-current:end -->')[0] if relative == 'AGENTS.md' else text
        for stale in STALE:
            assert stale not in active, f'{relative}: stale active policy: {stale}'
        summary = block(text)
        for clause in CLAUSES:
            assert clause in summary, f'{relative}: missing {clause}'
        if relative == 'AGENTS.md':
            assert text.index('<!-- mvp-current:start -->') < text.index('<!-- d97-current:start -->') < text.index('<!-- mvp-current:end -->'), 'D97 outside current mandate'
        if relative == 'PROJECT_CHARTER.md':
            section = text.split('### 8.1 ')[1].split('\n## 9.')[0]
            assert '<!-- d97-current:start -->' in section, 'D97 must reconcile charter 8.1'
        assert 'mvp03b-user-administration.md' in active, f'{relative}: contract link missing'
    data = json.loads((root / 'docs/mvp-backlog.json').read_text())
    item = next(i for i in data['items'] if i['id'] == 'MVP-03')
    assert item['status'] == 'done' and item['issueNumber'] == 142 and item['runtimeDelivered'] is True, 'parent delivered after verified PR167'
    delivered = item['federatedFirstEntry']
    assert delivered['pr'] == 167 and delivered['runtimeDelivered'] is True, 'onboarding delivered separately from policy gate'
    assert delivered['mergedMain'] == 'c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb', 'exact verified merge proof'
    assert delivered['prCi'] == 41752991377 and delivered['runtimeDispatch'] == 41753044926, 'exact-head acceptance proof'
    for relative in CURRENT:
        current = (root / relative).read_text()
        assert '41752991377' in current and '41753044926' in current, 'current proof links missing'
    policy = item['userAdministrationPolicy']
    assert policy['decision'] == 'D97' and policy['runtimeDelivered'] is False, 'policy not runtime'
    assert policy['contract'] == DOC, 'finite contract reference'
    for clause in CLAUSES:
        assert clause in policy['summary'], f'backlog: missing {clause}'
    acceptance = ' '.join(item['acceptance'])
    for term in ('creazione e modifica', 'ruoli e permessi', 'audit immutabile', 'control-plane'):
        assert term in acceptance, f'backlog acceptance: missing {term}'
    doc = (root / DOC).read_text()
    assert len(re.findall(r'^### D97 —', doc, re.M)) == 1, 'unique D97 decision entry'
    for term in DETAILS:
        assert term in doc, f'contract missing {term}'
    for clause in CLAUSES:
        assert clause in block(doc), f'contract summary missing {clause}'
    assert 'full_architecture=false' in doc and '#142' in doc, 'delivery boundary'


class PolicyTests(unittest.TestCase):
    def test_current_policy(self):
        validate(ROOT)

    def test_complete_cli_baseline_then_boundary_mutations_fail(self):
        validate(ROOT)
        with tempfile.TemporaryDirectory(prefix='d97-policy-') as directory:
            target = Path(directory)
            files = (*CURRENT, 'docs/mvp-backlog.json', DOC)
            originals = {p: (ROOT / p).read_text() for p in files}
            for relative, text in originals.items():
                path = target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            def run():
                return subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                                       '--check-root', str(target)], capture_output=True, text=True)
            self.assertEqual(run().returncode, 0, 'valid complete CLI baseline')
            for relative in (*CURRENT, DOC):
                original = originals[relative]
                for clause in CLAUSES:
                    with self.subTest(path=relative, removed=clause):
                        start = original.index('<!-- d97-current:start -->')
                        prefix, current = original[:start], original[start:]
                        (target / relative).write_text(prefix + current.replace(clause, 'REMOVED', 1))
                        result = run()
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('missing', result.stderr)
                        (target / relative).write_text(original)
            for term in DETAILS:
                with self.subTest(contract_removed=term):
                    (target / DOC).write_text(originals[DOC].replace(term, 'REMOVED'))
                    self.assertNotEqual(run().returncode, 0)
                    (target / DOC).write_text(originals[DOC])
            for relative in CURRENT:
                for stale in STALE:
                    with self.subTest(stale=stale, path=relative):
                        original = originals[relative]
                        text = original.replace('<!-- d97-current:end -->', stale + '\n<!-- d97-current:end -->')
                        (target / relative).write_text(text)
                        self.assertNotEqual(run().returncode, 0)
                        (target / relative).write_text(original)
            original_data = json.loads(originals['docs/mvp-backlog.json'])
            for clause in CLAUSES:
                data = copy.deepcopy(original_data)
                item = next(i for i in data['items'] if i['id'] == 'MVP-03')
                item['userAdministrationPolicy']['summary'] = item['userAdministrationPolicy']['summary'].replace(clause, 'REMOVED')
                (target / 'docs/mvp-backlog.json').write_text(json.dumps(data))
                self.assertNotEqual(run().returncode, 0)
            for key, value in (('status', 'in_progress'), ('runtimeDelivered', False)):
                data = copy.deepcopy(original_data)
                next(i for i in data['items'] if i['id'] == 'MVP-03')[key] = value
                (target / 'docs/mvp-backlog.json').write_text(json.dumps(data))
                self.assertNotEqual(run().returncode, 0)
            for key, value in (('runtimeDelivered', True), ('decision', 'D96'), ('contract', 'absent.md')):
                data = copy.deepcopy(original_data)
                next(i for i in data['items'] if i['id'] == 'MVP-03')['userAdministrationPolicy'][key] = value
                (target / 'docs/mvp-backlog.json').write_text(json.dumps(data))
                self.assertNotEqual(run().returncode, 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-root', type=Path)
    args, rest = parser.parse_known_args()
    if args.check_root:
        try:
            validate(args.check_root)
        except (AssertionError, KeyError, OSError, ValueError, IndexError) as error:
            print(str(error), file=sys.stderr)
            sys.exit(1)
        print('D97 historical documentary gate consistent; subsequent MVP03 runtime delivery proof retained')
    else:
        unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
