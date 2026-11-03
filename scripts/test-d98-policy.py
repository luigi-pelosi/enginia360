#!/usr/bin/env python3
"""D98 finite documentary CLI/mutation gate, not onboarding runtime proof."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = 'docs/mvp03b2-user-onboarding.md'
CURRENT = ('AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
           'docs/mvp-delivery-plan.md')
QUESTION = 'Per l’ingresso di un nuovo utente: Mario si autentica con il provider federato, ma non è ancora registrato in Enginia360. Chi può approvare la sua associazione al tenant del cliente? In entrambi i casi, autenticazione e audit restano obbligatori e non vengono concessi automaticamente ruoli o poteri amministrativi.'
CHOICE = 'L’amministratore delegato alla gestione utenti, soltanto per il proprio tenant'
OTHER = 'Tu, come SUPER ADMIN, oppure un tuo operatore incaricato; il delegato gestisce gli utenti dopo questa approvazione'
CLAUSES = ('D98:', 'prima associazione binding + membership', 'soggetto federato autenticato',
           'delegato alla gestione utenti', 'solo nel proprio tenant',
           'autenticazione e audit obbligatori', 'nessun ruolo o potere amministrativo automatico',
           'nessun tetto owner-only', 'runtime D98 non consegnato')
DETAILS = (QUESTION, CHOICE, OTHER, 'Alternativa A (raccomandata, SCELTA)',
           'Alternativa B (NON SCELTA)', 'trusted issuer + opaque subject',
           'pending onboarding principal', 'non è autorizzazione business',
           'nessun matching email', 'correlation token non è autenticazione',
           'nessuna espansione multi-tenant', 'nessuna modifica IdP',
           'audit atomico', 'rollback', 'conflitto', 'revoca corrente', 'replay identico',
           'payload diverso', 'pool 1 e 4', 'SSRBJWT', 'tutte le origini',
           'root/D77/ruoli/grant societari', 'SQL/RLS', 'OR permissivo',
           'conserva identità, grant e storico', 'abilitare non aggiunge autorità',
           'target privilegiati', 'subdelega', 'contratto tecnico finito',
           'TTL', 'consegna', 'CSRF', 'no-store', 'full_architecture=false')
DELIVERY_HEADERS = ('docs/mvp03b-user-administration.md', 'docs/mvp-delivery-plan.md',
                    'docs/mvp03b1-tenant-role-contract.md', 'docs/mvp03b1-progress.md')
STATUS = ('MVP03.b.1 consegnato via PR #162', 'organization-context.read/write',
          'MVP03.b non completato', 'invito/abilitazione',
          'nessun runtime consegnato qui', 'gate di policy D97')


def block(text):
    start, end = '<!-- d98-current:start -->', '<!-- d98-current:end -->'
    assert text.count(start) == text.count(end) == 1, 'one D98 current block required'
    assert text.index(start) < text.index(end), 'D98 markers reversed'
    return text.split(start)[1].split(end)[0]


def validate(root):
    for relative in CURRENT:
        text = (root / relative).read_text()
        for clause in CLAUSES:
            assert clause in block(text), f'{relative}: missing {clause}'
        assert 'mvp03b2-user-onboarding.md' in text, f'{relative}: missing next contract'
        if relative == 'AGENTS.md':
            assert text.index('<!-- mvp-current:start -->') < text.index('<!-- d98-current:start -->') < text.index('<!-- mvp-current:end -->'), 'D98 outside current mandate'
        if relative == 'PROJECT_CHARTER.md':
            assert '<!-- d98-current:start -->' in text.split('### 8.1 ')[1].split('\n## 9.')[0], 'D98 outside 8.1'
    doc = (root / DOC).read_text()
    assert len(re.findall(r'^### D98 —', doc, re.M)) == 1, 'unique D98 decision entry'
    for term in CLAUSES:
        assert term in block(doc), f'contract summary missing {term}'
    for term in (*CLAUSES, *DETAILS):
        assert term in doc, f'contract missing {term}'
    data = json.loads((root / 'docs/mvp-backlog.json').read_text())
    item = next(i for i in data['items'] if i['id'] == 'MVP-03')
    assert item['status'] == 'in_progress' and item['issueNumber'] == 142, 'parent remains open'
    assert item['runtimeDelivered'] is False, 'whole MVP03.b not delivered'
    policy = item['userOnboardingPolicy']
    assert policy['decision'] == 'D98' and policy['contract'] == DOC, 'next finite policy contract'
    assert policy['runtimeDelivered'] is False, 'D98 policy not runtime'
    for clause in CLAUSES:
        assert clause in policy['summary'], f'backlog missing {clause}'
    delivered = item['deliveredSubincrements']['MVP03.b.1']
    assert delivered['pr'] == 162 and delivered['runtimeDelivered'] is True, 'role subincrement delivered'
    assert delivered['catalog'] == ['organization-context.read', 'organization-context.write'], 'finite current executable catalog'
    for path in DELIVERY_HEADERS:
        active = (root / path).read_text().split('<!-- d97-history:start -->')[0]
        for term in STATUS:
            assert term in active, f'{path}: missing reconciled status {term}'


class PolicyTests(unittest.TestCase):
    def test_complete_positive_cli_and_boundary_mutations(self):
        files = tuple(dict.fromkeys((*CURRENT, DOC, 'docs/mvp-backlog.json', *DELIVERY_HEADERS)))
        with tempfile.TemporaryDirectory(prefix='d98-policy-') as directory:
            target = Path(directory)
            originals = {p: (ROOT / p).read_text() for p in files}
            for relative, text in originals.items():
                path = target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            def run():
                return subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
                                       '--check-root', str(target)], capture_output=True, text=True)
            baseline = run()
            self.assertEqual(baseline.returncode, 0, baseline.stderr)
            for relative in (*CURRENT, DOC):
                original = originals[relative]
                for clause in CLAUSES:
                    with self.subTest(path=relative, removed=clause):
                        start = original.index('<!-- d98-current:start -->')
                        prefix, suffix = original[:start], original[start:]
                        (target / relative).write_text(prefix + suffix.replace(clause, 'REMOVED', 1))
                        result = run()
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('missing', result.stderr)
                        (target / relative).write_text(original)
            for term in DETAILS:
                with self.subTest(contract_removed=term):
                    (target / DOC).write_text(originals[DOC].replace(term, 'REMOVED'))
                    self.assertNotEqual(run().returncode, 0)
                    (target / DOC).write_text(originals[DOC])
            for relative in DELIVERY_HEADERS:
                for term in STATUS:
                    with self.subTest(status_path=relative, removed=term):
                        active, *history = originals[relative].split('<!-- d97-history:start -->', 1)
                        text = active.replace(term, 'REMOVED')
                        if history:
                            text += '<!-- d97-history:start -->' + history[0]
                        (target / relative).write_text(text)
                        self.assertNotEqual(run().returncode, 0)
                        (target / relative).write_text(originals[relative])
            for mutation in (*CLAUSES, 'D98', DOC, 'false-whole', 'false-policy', 'true-role', 'catalog'):
                data = json.loads(originals['docs/mvp-backlog.json'])
                item = next(i for i in data['items'] if i['id'] == 'MVP-03')
                policy = item['userOnboardingPolicy']
                if mutation == 'false-whole':
                    item['runtimeDelivered'] = True
                elif mutation == 'false-policy':
                    policy['runtimeDelivered'] = True
                elif mutation == 'true-role':
                    item['deliveredSubincrements']['MVP03.b.1']['runtimeDelivered'] = False
                elif mutation == 'catalog':
                    item['deliveredSubincrements']['MVP03.b.1']['catalog'].append('all-domains.*')
                elif mutation == DOC:
                    policy['contract'] = 'absent.md'
                elif mutation == 'D98':
                    policy['decision'] = 'D97'
                else:
                    policy['summary'] = policy['summary'].replace(mutation, 'REMOVED')
                with self.subTest(backlog_mutation=mutation):
                    (target / 'docs/mvp-backlog.json').write_text(json.dumps(data))
                    self.assertNotEqual(run().returncode, 0)
            (target / 'docs/mvp-backlog.json').write_text(originals['docs/mvp-backlog.json'])
            self.assertEqual(run().returncode, 0, 'restored complete CLI baseline')

    def test_preserved_historical_decisions_and_d97_assertions(self):
        # Immutable historical dossier D1–D95; D96/D97 spans preserved separately.
        expected = {
            'docs/foundation/09-stakeholder-validation.md': '9f8286ab2938e84f1d5ddfc677111c2e383ad2adb78deace572335e36f99fd0c',
            'scripts/test-d97-policy.py': '6cd4ad89bddb0ce6cb2af683949a241973f5df80e8185237e990e48f6a955612',
            'scripts/test-d97-impact.py': '4526f0e535d2a40cea0ea36fb63a0d160dca8f71b1fe5e4b6e1c7d72f0fe38e6',
        }
        for path, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)
        charter = (ROOT / 'PROJECT_CHARTER.md').read_text()
        d96 = charter.split('### 4.2 D96')[1].split('### 4.3')[0]
        self.assertEqual(hashlib.sha256(d96.encode()).hexdigest(),
                         'dcf80e88c7a54b06c482cc3ddb7efe3c896668b97cbd6a9ea3e94f5c3353ae65')
        historical = (ROOT / 'docs/mvp03b-user-administration.md').read_text()
        d97 = historical.split('## Decisione e alternative')[1].split('## Interpretazione tecnica')[0]
        self.assertEqual(hashlib.sha256(d97.encode()).hexdigest(),
                         '87524d7204f459e18f18896678f6d67456e531eac95c3824c1fb8d859e30c2de')


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
        print('D98 documentary policy consistent; onboarding runtime not delivered')
    else:
        unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
