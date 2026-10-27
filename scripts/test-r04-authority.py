#!/usr/bin/env python3
"""Offline documentary coherence only; does NOT enforce product setup or call an ERP."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = 'docs/foundation/01-glossary-and-domain-boundaries.md'
PLAN = 'docs/productization-plan.md'
RUNBOOK = 'docs/r06-recovery-runbook.md'
BACKLOG = 'docs/productization-backlog.json'
PATHS = ('AGENTS.md', GLOSSARY, PLAN, RUNBOOK, BACKLOG)
QUOTE = 'No approvo B: non si può gestire stock e flusso di acquisti in distinti fonti. La fonte in questo caso resta sempre l’ERP esterno'
START, END = '<!-- r04-authority:start -->', '<!-- r04-authority:end -->'
COMMON = (
    'D82', 'stock e catena acquisti', 'stesso ERP esterno autorevole',
    'stock locale + acquisti ERP non valido',
    'richiesta tecnica locale non è un writer alternativo',
    'nessun fallback locale implicito',
    '3 ordinati / 2 ricevuti', 'regola quantitativa condizionata all’autorità',
    'proiezione/integrazione ERP supportata da evidenze provider',
    'R04.b ERP BLOCKED', 'contratto ufficiale assente',
)


def require(text, tokens, label):
    for token in tokens:
        if token not in text:
            raise ValueError(label+': missing '+token)


def authority_block(text, label):
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError(label+': exactly one active authority block required')
    return text.split(START)[1].split(END)[0]


def validate(root):
    docs = {path: (root/path).read_text() for path in PATHS}
    active = docs[GLOSSARY].split('## Archivio storico')[0]
    require(active, ('D82', 'stesso ERP esterno autorevole'), 'active stock/purchasing authority')
    blocks = [authority_block(docs[path], path) for path in (GLOSSARY, PLAN)]
    for path, block in zip((GLOSSARY, PLAN), blocks):
        require(block, COMMON, path)
        require(block, ('profilo interamente locale futuro', 'setup coerente esplicitamente approvato',
                        'non obbliga tutti i clienti all’ERP', 'unica autorità tenant-wide D26/D65',
                        'estensioni/prezzi/stock societari distinti',
                        'nessun cambio automatico o retroattivo di autorità',
                        'D80/D81 consegnate', 'prove sintetiche valide',
                        'nessuna configurazione reale o deployment'), path)
    require(docs['AGENTS.md'], ('D82', 'same authoritative external ERP for stock and the purchasing chain in this pilot',
                                   'no mixed local-stock/ERP-purchasing writer or implicit local fallback'), 'AGENTS')
    card = next(card for card in json.loads(docs[BACKLOG]) if card['id'] == 'R04')
    require(card['gate'], ('D82', 'stesso ERP esterno autorevole', '3 ordinati / 2 ricevuti già approvato',
                           'R04.b ERP BLOCKED', 'contratto ufficiale assente'), 'R04 backlog gate')
    require(active, ('D80/D81 consegnate',), 'active delivery')
    if 'Implementazione e prove ancora necessarie' in active or 'implementazione e prove ancora necessarie' in active:
        raise ValueError('active delivery: stale D80/D81 status')
    # Historical decisions remain untouched; the new decision must be unique and next.
    ids = [int(x) for x in re.findall(r'^### D(\d+) —', docs[GLOSSARY], re.M)]
    if sorted(ids) != list(range(1, 85)):
        raise ValueError('decision register: retain unique D1–D83 and append D84')
    decision = docs[GLOSSARY].split('### D82 —')[1].split('### D83 —')[0]
    require(decision, (QUOTE, '25 ottobre 2026', '3 ordinati / 2 ricevuti',
                       'regola quantitativa condizionata all’autorità',
                       'non autorizza carichi locali Enginia360 nel profilo ERP'), 'D82 provenance')
    if 'Implementazione/prove necessarie;' in docs[PLAN] or 'non ancora consegnata.' in docs[PLAN]:
        raise ValueError('plan: stale D80/D81 delivery status')
    remaining = docs[RUNBOOK].split('## 5.')[1].split('## 6.')[0]
    require(remaining, ('D82', '3 ordinati / 2 ricevuti già approvato', 'D80/D81 consegnate',
                        'proiezione/integrazione ERP supportata da evidenze provider',
                        'R04.b ERP BLOCKED', 'contratto ufficiale assente',
                        'nessuna risposta stock/ordine/ricevimento inventata'), 'R06 remaining gates')
    if 'parzialità ancora da approvare' in remaining:
        raise ValueError('R06 remaining gates: resolved quantity rule reopened')
    scope = '\n'.join(blocks+[active, remaining, docs['AGENTS.md'], decision])
    forbidden = (
        r'R04[.]b(?:[.]1)?\s+(?:DELIVERED|COMPLETE|CONSEGNAT[AO]|IMPLEMENTAT[AO])',
        r'(?:stock locale|local stock)\s*\+\s*(?:acquisti ERP|ERP purchasing)\s+(?:valido|allowed)',
        r'(?:fallback locale|local fallback)\s+(?:consentito|allowed|automatico)',
        r'(?:richiesta tecnica locale)\s+(?:autorevole|alimenta carichi locali)',
        r'(?:tutti i clienti|all customers)\s+(?:devono usare|must use)\s+(?:l[’\x27])?ERP',
        r'(?:setup coherence|coerenza setup)\s+(?:already enforced|già implementata)',
    )
    for pattern in forbidden:
        if re.search(pattern, scope, re.I):
            raise ValueError('active authority: forbidden promotion or mixed writer')


class AuthorityTests(unittest.TestCase):
    def test_current_documents_are_coherent(self):
        validate(ROOT)

    def invoke(self, root):
        return subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--check',
                               '--root', str(root)], capture_output=True, text=True, timeout=20)

    def test_actual_cli_accepts_current_documents(self):
        result = self.invoke(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('not product setup enforcement', result.stdout)

    def test_controlled_cli_mutations_reject_authority_regressions(self):
        mutations = [
            (GLOSSARY, QUOTE, 'Owner quote omitted'),
            (GLOSSARY, '25 ottobre 2026', '24 ottobre 2026'),
            (GLOSSARY, '### D82 —', '### D81 —'),
        ]
        # Each independent active invariant must be enforced in BOTH active reading paths.
        for path in (GLOSSARY, PLAN):
            for token in COMMON + ('unica autorità tenant-wide D26/D65',
                                  'estensioni/prezzi/stock societari distinti',
                                  'nessun cambio automatico o retroattivo di autorità',
                                  'setup coerente esplicitamente approvato', 'prove sintetiche valide'):
                mutations.append((path, token, 'REMOVED'))
            for false_claim in ('R04.b.1 DELIVERED', 'stock locale + acquisti ERP valido',
                                'fallback locale consentito', 'richiesta tecnica locale autorevole',
                                'tutti i clienti devono usare ERP', 'coerenza setup già implementata'):
                mutations.append((path, END, false_claim+'\n'+END))
        mutations += [(RUNBOOK, '3 ordinati / 2 ricevuti già approvato', 'parzialità ancora da approvare'),
                      (BACKLOG, '3 ordinati / 2 ricevuti già approvato', 'da approvare'),
                      (RUNBOOK, 'contratto ufficiale assente', 'contratto verificato'),
                      ('AGENTS.md', 'same authoritative external ERP for stock and the purchasing chain in this pilot',
                       'local stock with ERP purchasing')]
        with tempfile.TemporaryDirectory(prefix='r04-authority-', dir=tempfile.gettempdir()) as temp:
            root = Path(temp)
            for index, (path, old, new) in enumerate(mutations):
                with self.subTest(index=index, path=path, old=old):
                    for source in PATHS:
                        target = root/source
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT/source, target)
                    target = root/path
                    text = target.read_text()
                    self.assertIn(old, text, 'mutation precondition')
                    target.write_text(text.replace(old, new))
                    result = self.invoke(root)
                    self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                    self.assertIn('documentary authority refused:', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    if '--check' in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--check', action='store_true')
        parser.add_argument('--root', type=Path, default=ROOT)
        args = parser.parse_args()
        try:
            validate(args.root)
        except (ValueError, OSError, IndexError) as error:
            print('documentary authority refused: '+str(error), file=sys.stderr)
            sys.exit(2)
        print('Documentary authority coherent; not product setup enforcement; no ERP contract/delivery proved.')
    else:
        unittest.main()
