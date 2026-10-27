#!/usr/bin/env python3
"""Offline documentary coherence only; does NOT enforce product setup or call an ERP."""
import argparse
import hashlib
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
INVENTORY = 'docs/r06-migration-inventory.md'
PATHS = ('AGENTS.md', GLOSSARY, PLAN, RUNBOOK, BACKLOG, INVENTORY)
QUOTE = 'No approvo B: non si può gestire stock e flusso di acquisti in distinti fonti. La fonte in questo caso resta sempre l’ERP esterno'
START, END = '<!-- r04-authority:start -->', '<!-- r04-authority:end -->'
D1_D84_BYTES = 131965
D1_D84_SHA256 = 'c44de21abddad6830093a28a18abcd8b05363c74548d2df0765ebb2ce2b63802'
D1_D86_BYTES = 135677
D1_D86_SHA256 = '42a55f555aaff3ddc9cd8f073ee7900aa22adc704dd88376d9555f2a3e9a4818'
D1_D87_BYTES = 138358
D1_D87_SHA256 = '96acb334602294350382bd45b5f451fce3a1eb7b2eb67511f070f56cc2bf5cf6'
D88_START, D88_END = '<!-- r04-d88:start -->', '<!-- r04-d88:end -->'
Q88A = 'L\'operatore di magazzino la crea a mano dalla riga (consigliato)'
Q88B = 'Il fornitore diventa un ruolo nell\'anagrafica condivisa, con ID Giobby in un\'estensione societaria'
Q88C = 'No: una sola azione con permesso dedicato basta (consigliato)'
D88_TOKENS = (
    'D88', 'creata a mano da un operatore di magazzino dalla riga Part', 'non automatica su insufficient_available',
    'ruolo nell’anagrafica condivisa tenant-wide', 'ID fornitore Giobby in un’estensione societaria',
    'mai nell’anagrafica condivisa', 'nessuna lista fornitori configurata dall’host',
    'una sola azione con permesso dedicato', 'nessun approvatore separato',
    'non autoassegnabile né subdelegabile', 'R04.b.2',
    'Giobby resta l’unica autorità per stock e documenti d’acquisto (D82)', 'intento/outbox',
    'mai writer locale di acquisto o stock', 'non è autorità sull’anagrafica fornitori quando la possiede l’ERP',
    'lettura dell’agente', 'punto aperto', 'nessuna proiezione D76',
)
D88_FORBIDDEN = (
    r'(?<!non )(?<!not )(?:richiesta d[’\x27]acquisto|purchase request)\s+(?:viene\s+|è\s+|is\s+)?(?:creat[ao]\s+|created\s+)?automatic\w*\s+(?:su|on|quando|when|se|if)\b',
    r'(?:creazione|creation)\s+automatic\w*\s+(?:della\s+|of\s+(?:the\s+)?)?(?:richiesta d[’\x27]acquisto|purchase request)',
    r'(?:writer|scrittore)\s+locale\s+(?:di\s+)?(?:acquist\w+|stock|giacenza)\s+(?:consentito|ammesso|autorizzato|allowed)',
    r'(?:Enginia360|locale|local)\s+(?:scrive|crea|writes|creates)\s+(?:l[’\x27]|un\s+|il\s+|the\s+|a\s+)?(?:local\s+)?(?:ordine\s+d[’\x27]acquisto|purchase\s+(?:order|document)|documento\s+d[’\x27]acquisto)',
    r'ID\s+(?:Giobby|fornitore|vendor)\s+(?:è\s+)?(?:nell[’\x27]anagrafica condivisa|nel master condiviso)',
    r'(?:vendor|supplier)\s+ID\s+(?:is\s+)?(?:in|stored in)\s+the\s+shared\s+master',
    r'(?:approvatore|approvazione)\s+separat\w*\s+(?:è\s+)?(?:richiest\w+|obbligatori\w+|necessari\w+)',
    r'separate\s+approver\s+(?:is\s+)?(?:required|needed|mandatory)',
    r'(?:proiezione|projection)\s+D76\s+(?:implementat\w+|consegnat\w+|delivered|implemented)',
)
D87_START, D87_END = '<!-- r05-d87:start -->', '<!-- r05-d87:end -->'
Q87 = 'Esatto. L’ordine riserva lo stock.'
Q87_MIGRATION = 'Per ora non è prevista nessuna attività di migrazione dal sistema legacy.'
D87_TOKENS = (
    'D87', 'riserva lo stock', 'fisico invariato', 'disponibile −1', 'senza scaricarlo',
    'tipo di documento accettato dall’owner per il pilota',
    'supera, ai fini dell’adapter, la scelta aperta «ordine o proforma» di D85',
    'proforma resta solo un possibile secondo passo successivo, non pianificato',
    'rilascio/annullo della riserva', 'conversione manuale ordine→fattura',
    'lacune di evidenza **non provate**', 'Giobby resta l’autorità per stock e documenti (D82)',
    'nessuna validità fiscale affermata',
    'Perimetro R06.a', 'dichiarazione di scoping', 'Non è un divieto permanente',
    'una nuova decisione oltre il perimetro', 'fuori perimetro per ora',
    'R06.a è considerata completa per i soli strumenti sintetici staging-only consegnati',
    '#76/#77, #106/#107', '66 voci', 'UNDECIDED', 'registro OPEN',
    'restore di fatti applicativi già legittimi', 'onboarding owner D77',
    'OPE01–OPE05 invariati OPEN', '#46 resta aperta',
)
D87_FORBIDDEN = (
    r'(?<!non )(?<!not )(?:rilascio|annullo|annullamento|cancellazione)(?:/\w+)?\s+(?:della\s+|di\s+)?(?:riserva|prenotazione)\s+(?:è\s+|risulta\s+|resta\s+)?(?:provat|verificat|dimostrat|esercitat|confermat)',
    r'(?<!not )(?<!un)(?:reservation|reserve)\s+(?:release|cancellation)\s+(?:is\s+|was\s+)?(?:proven|verified|demonstrated|confirmed)',
    r'(?<!non )(?<!not )conversione\s+(?:manuale\s+)?(?:ordine\s*(?:→|->)\s*fattura|in fattura|da ordine a fattura)\s+(?:è\s+|risulta\s+)?(?:provat|verificat|dimostrat|esercitat|confermat)',
    r'(?<!not )(?:order\s*(?:→|->|to)\s*invoice|invoice)\s+conversion\s+(?:is\s+|was\s+)?(?:proven|verified|demonstrated|exercised|confirmed)',
    r'(?<!non è un )(?<!non è )(?<!non )(?<!not a )divieto\s+permanente',
    r'migrazione(?:\s+(?:dei\s+dati\s+)?legacy)?\s+(?:è\s+)?(?:permanentemente|per sempre|definitivamente)\s+(?:vietat|proibit|esclus)',
    r'(?:vietat|proibit)[aoe]\s+(?:per sempre|permanentemente|definitivamente)',
    r'migrat?ion\s+(?:is\s+)?permanently\s+(?:prohibited|forbidden|excluded)',
    r'migrazione(?:\s+(?:dei\s+dati\s+)?legacy)?\s+(?:è\s+)?(?:approvata|autorizzata|decisa)',
    r'(?:legacy\s+)?(?:data\s+)?migration\s+(?:is\s+|was\s+)?(?:approved|authori[sz]ed|decided)',
    r'eleggibilità\s+(?:approvata|decisa|definita)',
    r'R06\s+(?:è\s+)?(?:COMPLETA|completa)\b',
)
D85_START, D85_END = '<!-- r05-d85-d86:start -->', '<!-- r05-d85-d86:end -->'
Q85 = 'Ordine cliente (o proforma) in Giobby, da trasformare in fattura a mano: nessun numero fiscale né scarico finché non lo decidi tu'
Q86 = "Enginia360 crea il ricevimento via API e tiene da sé il residuo dell'ordine, segnalando la discrepanza con Giobby"
D85_TOKENS = (
    'D85', 'ordine cliente (o proforma)', 'trasformazione manuale in fattura avviene in Giobby',
    'nessun numero fiscale né scarico magazzino', 'Sostituisce «bozza di fattura vendita» di D79',
    'D79 resta cronologia', 'POST /sales/orders', 'docType 33',
    'non decisi', 'gate di evidenza', 'nessuna scelta per assunzione',
    'Nessuna integrazione né validità fiscale',
)
D86_TOKENS = (
    'D86', 'ricevimento merci via API', 'residuo d’ordine (ordinato meno ricevuto',
    '3 ordinati / 2 ricevuti già approvata', 'overlay/read model derivato **non autorevole**',
    'discrepanza con Giobby', 'Coerenza con D82', 'unica autorità per stock e documenti',
    'non scrive stock né documenti d’acquisto', 'non sostituisce lo stato d’ordine ERP',
    'nessun writer misto né fallback locale', 'mostrata e riconciliata, mai corretta in silenzio',
    'documento ERP standalone', 'rischio di doppio conteggio riconosciuto',
    'lettura dell’agente della risposta owner', 'unico punto che l’owner può correggere',
)
D85_REGISTER_TOKENS = (
    'ordine cliente (o proforma)', 'Sostituisce «bozza di fattura vendita» di D79', 'D79 resta cronologia',
    '`POST /sales/orders`', 'docType 33', 'Gate di evidenza (non deciso)', 'Non si sceglie per assunzione',
    'validità fiscale affermate',
)
D85_FORBIDDEN = (
    r'(?:crea|creates?|emette|issues?|invia|sends?)\s+(?:automaticamente\s+|automatically\s+)?(?:una\s+|an?\s+)?(?:fattura|invoice)\s+numerat',
    r'(?<!mai )(?<!mai una )(?<!never )(?<!never an )(?:fattura|invoice)\s+numerata\s+automatic',
    r'(?:Enginia360|locale|local)\s+(?:scrive|aggiorna|writes|updates)\s+(?:la\s+|the\s+)?(?:giacenza|stock)',
    r'(?:residuo|residual)\s+(?:scrive|aggiorna|writes|updates)',
    r'residuo\s+(?:ERP\s+)?autorevole',
    r'(?<!non-)(?<!non )authoritative\s+residual',
    r'residuo\s+(?:sostituisce|replaces)',
    r'proforma\s+(?:scelta|selezionata|decisa|selected|chosen)\b',
    r'ordine\s+cliente\s+(?:scelto|selezionato|deciso)\s+come\s+tipo\s+esatto',
)
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
    d85_blocks = []
    for path in (GLOSSARY, PLAN):
        if docs[path].count(D85_START) != 1 or docs[path].count(D85_END) != 1:
            raise ValueError(path+': exactly one active D85/D86 block required')
        block = docs[path].split(D85_START)[1].split(D85_END)[0]
        require(block, D85_TOKENS+D86_TOKENS, path+' D85/D86')
        d85_blocks.append(block)
    d87_blocks = []
    for path in (GLOSSARY, PLAN):
        if docs[path].count(D87_START) != 1 or docs[path].count(D87_END) != 1:
            raise ValueError(path+': exactly one active D87 block required')
        block = docs[path].split(D87_START)[1].split(D87_END)[0]
        require(block, D87_TOKENS, path+' D87')
        d87_blocks.append(block)
    d88_blocks = []
    for path in (GLOSSARY, PLAN):
        if docs[path].count(D88_START) != 1 or docs[path].count(D88_END) != 1:
            raise ValueError(path+': exactly one active D88 block required')
        block = docs[path].split(D88_START)[1].split(D88_END)[0]
        require(block, D88_TOKENS, path+' D88')
        d88_blocks.append(block)
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
    require(docs['AGENTS.md'], ('D85', 'sales order (or proforma)', 'never an automatically numbered invoice',
                                 'D86', 'non-authoritative residual overlay', 'no local receipt-stock writer',
                                 'mismatch is shown and reconciled'), 'AGENTS D85/D86')
    cards = {card['id']: card for card in json.loads(docs[BACKLOG])}
    require(cards['R04']['gate'], ('D86', 'residuo non autorevole', 'D82'), 'R04 backlog D86 gate')
    require(cards['R05']['gate'], ('D85', 'ordine cliente (o proforma)', 'D87', 'ordine cliente accettato dall’owner',
                                   'riserva stock senza scarico', 'rilascio/annullo della riserva', 'conversione manuale ordine→fattura',
                                   'non provati', 'D82'), 'R05 backlog D85/D87 gate')
    require(cards['R04']['gate'], ('D87', 'riserva stock', 'rilascio/annullo della riserva non provati', 'D82'), 'R04 backlog D87 gate')
    require(cards['R06']['gate'], ('migrazione legacy fuori perimetro per ora', 'R06.a completa per i soli strumenti sintetici',
                                   '66 voci UNDECIDED', 'OPE01–OPE05 OPEN', '#46'), 'R06 backlog descoping gate')
    card = cards['R04']
    require(card['gate'], ('D82', 'stesso ERP esterno autorevole', '3 ordinati / 2 ricevuti già approvato',
                           'R04.b ERP BLOCKED', 'contratto ufficiale assente'), 'R04 backlog gate')
    require(active, ('D80/D81 consegnate',), 'active delivery')
    if 'Implementazione e prove ancora necessarie' in active or 'implementazione e prove ancora necessarie' in active:
        raise ValueError('active delivery: stale D80/D81 status')
    # Historical decisions remain untouched; the new decision must be unique and next.
    ids = [int(x) for x in re.findall(r'^### D(\d+) —', docs[GLOSSARY], re.M)]
    if sorted(ids) != list(range(1, 89)):
        raise ValueError('decision register: retain unique D1–D87 and append D88')
    prefix = docs[GLOSSARY].encode()
    prefix = prefix[prefix.index(b'### D1 \xe2\x80\x94'):][:D1_D84_BYTES]
    if hashlib.sha256(prefix).hexdigest() != D1_D84_SHA256:
        raise ValueError('decision register: D1–D84 history changed')
    full = docs[GLOSSARY].encode()
    full = full[full.index(b'### D1 \xe2\x80\x94'):][:D1_D86_BYTES]
    if hashlib.sha256(full).hexdigest() != D1_D86_SHA256:
        raise ValueError('decision register: D1–D86 history changed')
    full = docs[GLOSSARY].encode()
    full = full[full.index(b'### D1 \xe2\x80\x94'):][:D1_D87_BYTES]
    if hashlib.sha256(full).hexdigest() != D1_D87_SHA256:
        raise ValueError('decision register: D1–D87 history changed')
    d88 = docs[GLOSSARY].split('### D88 —')[1]
    require(d88, (Q88A, Q88B, Q88C, '27 ottobre 2026', 'Domanda posta', 'Esempio', 'Registro D1–D87 verificato prima dell’assegnazione',
                  'Interpretazione dell’agente') + D88_TOKENS[1:], 'D88 register')
    require(docs['AGENTS.md'], ('D88', 'manually from a Part line', 'supplier is a role in the tenant-wide shared Counterparties master',
                                'vendor ID in a company extension', 'single dedicated action', 'never a local purchase/stock writer'), 'AGENTS D88')
    require(cards['R04']['gate'], ('D88', 'richiesta d’acquisto manuale', 'ruolo fornitore', 'estensione societaria', 'nessun approvatore separato', 'D82'), 'R04 backlog D88 gate')
    require(cards['R05']['gate'], ('D88', 'ID fornitore Giobby', 'estensione societaria', 'D82'), 'R05 backlog D88 gate')
    plan_r04 = docs[PLAN].split('### R04 — Magazzino e approvvigionamento')[1].split('### R05')[0]
    require(plan_r04, ('D88', 'richiesta d’acquisto manuale', 'ruolo fornitore', 'R04.b.2'), 'plan R04 D88')
    d87 = docs[GLOSSARY].split('### D87 —')[1].split('### D88 —')[0]
    require(d87, (Q87, Q87_MIGRATION, '27 ottobre 2026', 'Domanda posta', 'Registro D1–D86 verificato prima dell’assegnazione',
                  'Interpretazione dell’agente') + D87_TOKENS[1:], 'D87 register')
    for number, quote in ((85, Q85), (86, Q86)):
        section = docs[GLOSSARY].split('### D%d —' % number)[1].split('### D%d —' % (number+1))[0]
        require(section, (quote, '27 ottobre 2026'), 'D%d provenance' % number)
    d86 = docs[GLOSSARY].split('### D86 —')[1]
    require(d86, D86_TOKENS[3:], 'D86 register')
    d85 = docs[GLOSSARY].split('### D85 —')[1].split('### D86 —')[0]
    require(d85, D85_REGISTER_TOKENS, 'D85 register')
    decision = docs[GLOSSARY].split('### D82 —')[1].split('### D83 —')[0]
    require(decision, (QUOTE, '25 ottobre 2026', '3 ordinati / 2 ricevuti',
                       'regola quantitativa condizionata all’autorità',
                       'non autorizza carichi locali Enginia360 nel profilo ERP'), 'D82 provenance')
    plan_r05 = docs[PLAN].split('### R05 — Integrazione Giobby')[1].split('### R06')[0]
    require(plan_r05, ('D85', 'ordine cliente (o proforma)', 'D87', 'ordine cliente accettato dall’owner', 'D86', 'residuo non autorevole',
                       'rilascio/annullo della riserva', 'conversione manuale ordine→fattura'), 'plan R05 D85/D87')
    plan_r04 = docs[PLAN].split('### R04 — Magazzino e approvvigionamento')[1].split('### R05')[0]
    require(plan_r04, ('D87', 'riserva stock', 'rilascio/annullo della riserva non provati'), 'plan R04 D87')
    plan_r06 = docs[PLAN].split('### R06 — Migrazione e readiness')[1].split('\n## ')[0]
    require(plan_r06, ('migrazione legacy fuori perimetro per ora', 'R06.a completa per i soli strumenti sintetici',
                       '66 voci UNDECIDED', 'OPE01–OPE05 OPEN', '#46'), 'plan R06 descoping')
    inventory = docs[INVENTORY].split('## Inventario verificabile')[0]
    require(inventory, ('migrazione legacy fuori perimetro per ora', 'R06.a completa per i soli strumenti sintetici', '66 voci UNDECIDED', '#46'), 'R06 inventory header')
    require(docs[RUNBOOK].split('## 5.')[1].split('## 6.')[0], ('migrazione legacy fuori perimetro per ora', 'D87'), 'R06 runbook residuals')
    require(docs['AGENTS.md'], ('D87', 'sales order reserves stock', 'release/cancellation of the reservation and order-to-invoice conversion remain unproven'), 'AGENTS D87')
    if 'Implementazione/prove necessarie;' in docs[PLAN] or 'non ancora consegnata.' in docs[PLAN]:
        raise ValueError('plan: stale D80/D81 delivery status')
    remaining = docs[RUNBOOK].split('## 5.')[1].split('## 6.')[0]
    require(remaining, ('D82', '3 ordinati / 2 ricevuti già approvato', 'D80/D81 consegnate',
                        'proiezione/integrazione ERP supportata da evidenze provider',
                        'R04.b ERP BLOCKED', 'contratto ufficiale assente',
                        'nessuna risposta stock/ordine/ricevimento inventata'), 'R06 remaining gates')
    if 'parzialità ancora da approvare' in remaining:
        raise ValueError('R06 remaining gates: resolved quantity rule reopened')
    scope = '\n'.join(blocks+d85_blocks+d87_blocks+d88_blocks+[inventory, plan_r04, plan_r06, active, remaining, docs['AGENTS.md'], decision, plan_r05, cards['R04']['gate'], cards['R05']['gate']])
    forbidden = (
        r'R04[.]b(?:[.]1)?\s+(?:DELIVERED|COMPLETE|CONSEGNAT[AO]|IMPLEMENTAT[AO])',
        r'(?:stock locale|local stock)\s*\+\s*(?:acquisti ERP|ERP purchasing)\s+(?:valido|allowed)',
        r'(?:fallback locale|local fallback)\s+(?:consentito|allowed|automatico)',
        r'(?:richiesta tecnica locale)\s+(?:autorevole|alimenta carichi locali)',
        r'(?:tutti i clienti|all customers)\s+(?:devono usare|must use)\s+(?:l[’\x27])?ERP',
        r'(?:setup coherence|coerenza setup)\s+(?:already enforced|già implementata)',
    )
    for pattern in forbidden+D85_FORBIDDEN+D87_FORBIDDEN+D88_FORBIDDEN:
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
        for path in (GLOSSARY, PLAN):
            for token in D85_TOKENS + D86_TOKENS:
                mutations.append((path, token, 'REMOVED'))
            for false_claim in ('Enginia360 crea una fattura numerata', 'fattura numerata automaticamente', 'Enginia360 scrive la giacenza',
                                'il residuo aggiorna lo stock', 'residuo ERP autorevole', 'residuo sostituisce lo stato ordine',
                                'proforma scelta come tipo esatto'):
                mutations.append((path, D85_END, false_claim+'\n'+D85_END))
        for path in (GLOSSARY, PLAN):
            for token in D87_TOKENS:
                mutations.append((path, token, 'REMOVED'))
            for false_claim in ('Il rilascio della riserva è provato', 'L’annullo della prenotazione risulta verificato',
                                'reservation release is proven', 'La conversione manuale ordine→fattura è provata',
                                'order-to-invoice conversion is verified', 'Esiste un divieto permanente della migrazione',
                                'migrazione legacy permanentemente vietata', 'legacy migration is permanently prohibited',
                                'La migrazione legacy è approvata', 'legacy data migration is approved', 'R06 COMPLETA',
                                'eleggibilità approvata'):
                mutations.append((path, D87_END, false_claim+'\n'+D87_END))
        for path in (GLOSSARY, PLAN):
            for token in D88_TOKENS:
                mutations.append((path, token, 'REMOVED'))
            for false_claim in ('La richiesta d’acquisto è creata automaticamente su insufficient_available',
                                'purchase request is created automatically when stock is insufficient',
                                'creazione automatica della richiesta d’acquisto',
                                'writer locale di acquisti consentito', 'Enginia360 crea l’ordine d’acquisto',
                                'local writes purchase order', 'ID Giobby nell’anagrafica condivisa',
                                'vendor ID is in the shared master', 'approvatore separato richiesto',
                                'separate approver is required', 'proiezione D76 implementata'):
                mutations.append((path, D88_END, false_claim+'\n'+D88_END))
        mutations += [(GLOSSARY, Q88A, 'Quote omitted'), (GLOSSARY, Q88B, 'Quote omitted'), (GLOSSARY, Q88C, 'Quote omitted'),
                      (GLOSSARY, '### D88 —', '### D87 —'),
                      ('AGENTS.md', 'manually from a Part line', 'automatically on insufficient availability'),
                      ('AGENTS.md', 'never a local purchase/stock writer', 'local purchase writer allowed'),
                      (BACKLOG, 'nessun approvatore separato', 'approvatore separato richiesto'),
                      (BACKLOG, 'estensione societaria', 'anagrafica condivisa'),
                      (GLOSSARY, Q87, 'Quote omitted'), (GLOSSARY, Q87_MIGRATION, 'Quote omitted'),
                      (GLOSSARY, '### D87 —', '### D86 —'),
                      (INVENTORY, '66 voci UNDECIDED', '66 voci APPROVED'),
                      (RUNBOOK, 'migrazione legacy fuori perimetro per ora', 'migrazione legacy approvata'),
                      ('AGENTS.md', 'sales order reserves stock', 'sales order discharges stock'),
                      ('AGENTS.md', 'order-to-invoice conversion remain unproven', 'order-to-invoice conversion is proven'),
                      (BACKLOG, 'rilascio/annullo della riserva non provati', 'rilascio/annullo della riserva provati'),
                      (BACKLOG, 'migrazione legacy fuori perimetro per ora', 'migrazione legacy permanentemente vietata'),
                      (GLOSSARY, Q85, 'Quote omitted'), (GLOSSARY, Q86, 'Quote omitted'),
                      (GLOSSARY, '### D85 —', '### D84 —'),
                      ('AGENTS.md', 'never an automatically numbered invoice', 'invoice allowed'),
                      ('AGENTS.md', 'no local receipt-stock writer', 'local writer allowed'),
                      (BACKLOG, 'ordine cliente accettato dall’owner', 'ordine cliente non deciso'),
                      (BACKLOG, 'residuo non autorevole', 'residuo autorevole')]
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
