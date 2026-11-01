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
SUPPLIER = 'docs/r04b1-supplier-role.md'
INTENT = 'docs/r04b2a-purchase-intent.md'
PATHS = ('AGENTS.md', GLOSSARY, PLAN, RUNBOOK, BACKLOG, INVENTORY, SUPPLIER, INTENT, 'docs/r04b2b1-supplier-purchase-prices.md', 'docs/r05a9-isolated-receipt-contract.md')
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


def validate_d90(docs):
    """Documentary policy only, not runtime purchase capacity enforcement."""
    history = docs[GLOSSARY].encode()
    history = history[history.index('### D1 —'.encode()):][:144854]
    if hashlib.sha256(history).hexdigest() != 'e37f0a21dd9f4ddb376256d138b497a2ef442b562d0b4151574434b270e27e54':
        raise ValueError('D90: D1–D89 history changed')
    register = docs[GLOSSARY].split('### D90 —')[1]
    require(register, ('> Confermo A\n',
        'Esempio: la riga richiede 3 pezzi e una richiesta d’acquisto pendente ne copre già 2. Una nuova richiesta, anche verso un altro fornitore, può chiedere: A — consigliato: al massimo 1 pezzo, contando cumulativamente tutte le richieste della stessa riga. B: altri 2 pezzi, consentendo di superare il fabbisogno complessivo. I retry della stessa richiesta restano senza duplicati in entrambi i casi. Confermi A?',
        '27 ottobre 2026', 'Registro D1–D89 verificato prima dell’assegnazione',
        'Interpretazione dell’agente', 'Nessuna enforcement runtime'), 'D90 provenance')
    active_tokens = ('D90', 'singola riga Part sorgente',
        'somma delle quantità degli intenti pendenti più la nuova quantità non supera il fabbisogno',
        'tutti i fornitori e magazzini', 'Riga 3 / intento pendente 2 → residuo 1',
        'nuova richiesta 2 rifiutata, 1 ammessa', 'nuovo UUID non azzera il cap',
        'replay esatto senza quantità aggiuntiva', 'non riducono automaticamente il cap',
        'nessuna sottrazione implicita né doppio conteggio',
        'non introduce cancellazione/rifiuto/rilascio/ricevimento',
        'né riapertura automatica del cap', 'lifecycle successive fuori perimetro',
        'D82 invariata', 'solo intento/outbox, nessun writer locale',
        'D88 resta manuale con azione dedicata e nessun approvatore separato',
        'nessun nuovo scope/ruolo/provisioning', 'Nessuna scelta di mapping o codice',
        'Gate quantitativo #114 risolto', 'solo dopo merge', 'vero RED→GREEN',
        '#114/#44/#45 restano aperte', 'D89 invariata', 'Esercizio OPEN/BACKLOG',
        'nessuna acceptance runtime o readiness')
    scopes = []
    for path in (GLOSSARY, PLAN):
        start, end = '<!-- r04-d90:start -->', '<!-- r04-d90:end -->'
        if docs[path].count(start) != 1 or docs[path].count(end) != 1:
            raise ValueError('D90: exactly one active cap block required: '+path)
        block = docs[path].split(start)[1].split(end)[0]
        require(block, active_tokens, 'D90 '+path)
        scopes.append(block)
    agents = next((line for line in docs['AGENTS.md'].splitlines() if line.startswith('- D90 ')), '')
    require(agents, ('per source Part line across suppliers and warehouse choices', 'never per command',
        'Line3/pending2 leaves1', 'new UUID does not reset the cap',
        'exact replay with no extra quantity', 'do not automatically reduce the cap',
        'no cancellation/rejection/release/receipt transitions or automatic capacity replenishment',
        'later lifecycle is out of scope', 'D82/D88/D77/D89 unchanged',
        'no new scopes/roles/provisioning', 'mapping or code decisions',
        'must merge before implementation', '#114/#44/#45 stay open', 'offline checks only'), 'D90 AGENTS')
    card = next(card for card in json.loads(docs[BACKLOG]) if card['id'] == 'R04')['gate']
    require(card, ('D90', 'cap cumulativo per riga Part sorgente', 'pendenti/fornitori/magazzini',
        'non per comando', 'riga 3 / intento 2 → residuo 1', 'nuova 2 rifiutata e 1 ammessa',
        'nuovo UUID non azzera', 'replay esatto senza quantità aggiuntiva',
        'Nessuna riduzione automatica', 'nessuna transizione lifecycle o riapertura automatica',
        'Gate quantitativo #114 risolto', 'dopo merge', 'vero RED→GREEN', '#114/#44/#45 aperte',
        'nessun nuovo scope/ruolo/provisioning', 'mapping o codice deciso'), 'D90 backlog')
    supplier = docs[SUPPLIER].split('## Requisiti rimanenti per R04.b.2')[1]
    require(supplier, ('D90', 'cap cumulativo per riga Part sorgente',
        'intenti pendenti, fornitori e magazzini', 'riga 3 / intento 2 → residuo 1',
        'nuova 2 rifiutata e 1 ammessa', 'Nuovo UUID non azzera il cap',
        'replay esatto senza quantità aggiuntiva', 'non sottratte automaticamente',
        'senza cancellazione/rifiuto/rilascio/ricevimento o riapertura automatica',
        'lifecycle successivo fuori perimetro', 'Gate quantitativo #114 risolto',
        'solo dopo merge', 'vero RED→GREEN', 'Nessuna enforcement runtime provata qui',
        'D82/D88/D77', 'nessun nuovo scope/ruolo/provisioning', 'mapping o codice deciso'), 'D90 supplier')
    scopes += [register, docs['AGENTS.md'], card, supplier]
    forbidden = (
        r'cap\s+per\s+comando\s+(?:consentito|approvato)',
        r'(?:nuovo UUID|cambio fornitore|cambio magazzino)\s+azzera\s+il\s+cap',
        r'same UUID\s+adds\s+(?:more|extra)\s+quantity',
        r'(?:ERP availability|reserved quantity)\s+automatically\s+reduces\s+the\s+cap',
        r'(?:cancellation|receipt)\s+automatically\s+(?:replenishes|reopens)\s+capacity',
        r'new purchase roles and provisioning\s+approved',
        r'vendor mapping policy\s+decided by D90',
        r'D90 cap runtime enforcement\s+delivered',
    )
    for pattern in forbidden:
        if re.search(pattern, '\n'.join(scopes), re.I):
            raise ValueError('D90: contradictory cap, inferred lifecycle or expanded authority')


def validate_d91(docs):
    """Price policy evidence only; no purchase runtime enforcement is claimed."""
    history = docs[GLOSSARY].encode()
    history = history[history.index('### D1 —'.encode()):][:148355]
    if hashlib.sha256(history).hexdigest() != 'a540c2e4d4a87e408de5ec44374e3c56152f70a427344d15296912c6acb5c261':
        raise ValueError('D91: D1–D90 history changed')
    register = docs[GLOSSARY].split('### D91 —')[1]
    require(register, (
        '> B: prezzo di acquisto definito nei listini di acquisto del fornitore configurabili dall’amministratore o da chi ne ha i permessi. Laddove il prezzo di acquisto non esiste nel listino allora è zero di default ed è delegato all’operatore di inserire obbligatoriamente il prezzo.\n',
        'DocumentRowApi.price', '28 ottobre 2026',
        'A: inviare 0 e modificare in ERP; B: costo configurato dall’host; C: inserimento operatore',
        'ricostruito dal handoff, non citazione verbatim',
        'Registro D1–D90 verificato prima dell’assegnazione'), 'D91 provenance')
    tokens = ('D91', 'listini/prezzi ed estensioni societari', 'tenant-wide D26/D65',
              'configurabili dall’amministratore o da chi ha i permessi',
              'host-cost-only', 'è superata', 'mai fallback di costo',
              'default UI 0 solo provvisorio', 'non confermato automaticamente',
              'inserimento/completamento esplicito obbligatorio',
              'interpretazione dell’agente correggibile dall’owner',
              'non impone >0 né vieta uno zero deliberato', 'azione/scope esatti',
              'etichetta admin senza diritti impliciti', 'concessioni owner-controlled D77',
              'nessun self-grant o subdelega', 'prezzo sorgente (o assenza)',
              'prezzo finale accettato e provenienza', 'prima dell’invio',
              'nessun repricing retroattivo',
              'prerequisito listini fornitore -> inserimento obbligatorio costo mancante/prezzo acquisto congelato -> ripresa connettore R04.b.2b',
              '0028 PUBLISHED invariata', 'append-only', 'nessun backfill automatico',
              'restano non decisi', 'fuori dalla prima implementazione limitata',
              'nessuna enforcement runtime o consegna adapter',
              'D76/D77/D82/D88/D89/D90 invariati', 'Esercizio non blocca sviluppo isolato')
    scopes = [register, docs['AGENTS.md']]
    for path in (GLOSSARY, PLAN):
        start, end = '<!-- r04-d91:start -->', '<!-- r04-d91:end -->'
        if docs[path].count(start) != 1 or docs[path].count(end) != 1:
            raise ValueError('D91: exactly one active pricing block required: '+path)
        block = docs[path].split(start)[1].split(end)[0]
        require(block, tokens, 'D91 '+path)
        scopes.append(block)
    for card in json.loads(docs[BACKLOG]):
        if card['id'] in ('R04', 'R05'):
            require(card['gate'], tokens, 'D91 backlog '+card['id'])
            scopes.append(card['gate'])
    intent = docs[INTENT].split('## Prossimo gate')[1]
    require(intent, ('D91', 'listini di acquisto fornitore societari',
        'tenant-wide D26/D65', 'non costo configurato soltanto dall’host',
        'Azione/scope prezzi esatti', 'etichetta admin senza diritti impliciti',
        'owner-controlled D77', 'nessun self-grant/subdelega',
        'default UI 0 solo provvisorio', 'mai conferma/invio automatico',
        'inserimento/completamento esplicito obbligatorio', 'correggibile owner',
        'nessun >0 imposto o divieto di zero deliberato', 'prezzo sorgente/assenza',
        'prezzo finale accettato e provenienza', 'prima dell’invio',
        'nessun repricing retroattivo', 'Nessun fallback dal prezzo di vendita',
        'Prima listini fornitore -> inserimento obbligatorio costo mancante/prezzo acquisto congelato -> ripresa connettore R04.b.2b',
        '0028 PUBLISHED invariata', 'append-only', 'nessun backfill automatico',
        'non decisi', 'fuori dalla prima implementazione limitata',
        'nessun adapter/prezzo runtime consegnato', 'Esercizio non blocca sviluppo isolato'), 'D91 purchase intent')
    scopes.append(intent)
    agents = [line for line in docs['AGENTS.md'].splitlines() if line.startswith('- D91 ')]
    if len(agents) != 1:
        raise ValueError('D91 AGENTS: exactly one active pricing summary required')
    require(agents[0], D91_AGENTS_TOKENS, 'D91 AGENTS')
    forbidden = (
        r'host-cost-only\s+policy\s+approved',
        r'sales\s+UnitPrice\s+fallback\s+to\s+purchase\s+cost\s+allowed',
        r'missing-price\s+provisional\s+zero\s+auto-dispatch\s+allowed',
        r'admin\s+label\s+grants\s+implicit\s+pricing\s+rights',
        r'frozen\s+purchase\s+intents\s+retroactively\s+repriced',
        r'prezzo\s+di\s+vendita\s+come\s+costo\s+consentito',
        r'zero\s+provvisorio\s+inviato\s+automaticamente',
        r'admin\s+concede\s+diritti\s+prezzi\s+impliciti',
    )
    if any(re.search(pattern, '\n'.join(scopes), re.I) for pattern in forbidden):
        raise ValueError('D91: contradictory pricing, missing-cost dispatch or implicit rights')


def validate_d92(docs):
    """Decision evidence/active boundaries only, never purchasing runtime acceptance."""
    history = docs[GLOSSARY].encode().split('### D1 —'.encode(), 1)[1]
    history = '### D1 —'.encode()+history
    if hashlib.sha256(history[:152968]).hexdigest() != '53551d8c884be224783f2a0d8ad4d353fb32d80203a99c608ca6608d9d8a3ad7':
        raise ValueError('D92: D1–D91 history changed')
    decision = docs[GLOSSARY].split('### D92 —')[1]
    require(decision, (D92_QUESTION, '> Confermo A\n', '28 ottobre 2026',
                      'Registro D1–D91 verificato', 'B non selezionata',
                      'distinta dal «Confermo A» di D90'), 'D92 provenance')
    scopes = []
    for path in D92_DOC_PATHS:
        text = docs[path]
        start, end = '<!-- r04-d92:start -->', '<!-- r04-d92:end -->'
        if text.count(start) != 1 or text.count(end) != 1:
            raise ValueError('D92: exactly one active quote block required: '+path)
        block = text.split(start)[1].split(end)[0]
        require(block, D92_TOKENS, 'D92 '+path)
        scopes.append(block)
    for card in json.loads(docs[BACKLOG]):
        if card['id'] in ('R04', 'R05'):
            require(card['gate'], D92_TOKENS, 'D92 backlog '+card['id'])
            scopes.append(card['gate'])
    lines = [line for line in docs['AGENTS.md'].splitlines() if line.startswith('- D92 ')]
    if len(lines) != 1:
        raise ValueError('D92: exactly one active AGENTS summary required')
    require(lines[0], D92_AGENTS_TOKENS, 'D92 AGENTS')
    scopes.extend((docs['AGENTS.md'], decision))
    forbidden = (
        r'purchasing\s+grants\s+full\s+price-list\s+browsing',
        r'purchasing\s+grants\s+price\s+history\s+and\s+maintenance',
        r'purchasing\s+automatically\s+grants\s+catalog[.]purchase-prices[.]read/manage',
        r'arbitrary\s+tenant-wide\s+quote\s+lookup\s+allowed',
        r'bulk\s+quote\s+browsing\s+allowed', r'source\s+access\s+bypass\s+allowed',
        r'tenant\s+from\s+browser\s+trusted\s+for\s+quote',
        r'quote\s+runtime\s+delivered\s+by\s+D92',
        r'runtime\s+starts\s+before\s+docs\s+merge',
        r'quote\s+requires\s+catalog[.]purchase-prices[.]read\s+in\s+addition\s+to\s+purchase\s+permission',
    )
    if any(re.search(pattern, '\n'.join(scopes), re.I) for pattern in forbidden):
        raise ValueError('D92: expanded quote authority, B prerequisite or false runtime claim')


def validate_d93(docs):
    """Receiving authorization documentation, never a runtime grant or provider claim."""
    history = docs[GLOSSARY].encode().split('### D1 —'.encode(), 1)[1]
    history = '### D1 —'.encode()+history
    if hashlib.sha256(history[:D93_HISTORY_BYTES]).hexdigest() != D93_HISTORY_SHA256:
        raise ValueError('D93: D1–D92 history changed')
    decision = docs[GLOSSARY].split('### D93 —')[1]
    require(decision, (D93_QUESTION, '> Opzione A. Procedi\n', '29 ottobre 2026',
                       'Registro D1–D92 verificato', 'B non selezionata'), 'D93 provenance')
    scopes = [decision]
    for path in D93_DOC_PATHS:
        start, end = '<!-- r04-d93:start -->', '<!-- r04-d93:end -->'
        if docs[path].count(start) != 1 or docs[path].count(end) != 1:
            raise ValueError('D93: exactly one active receiving block required: '+path)
        block = docs[path].split(start)[1].split(end)[0]
        require(block, D93_TOKENS, 'D93 '+path)
        scopes.append(block)
    for card in json.loads(docs[BACKLOG]):
        if card['id'] in ('R04', 'R05'):
            if card['gate'].count('**D93;') != 1:
                raise ValueError('D93: exactly one backlog receiving boundary required')
            scope = card['gate'].split('**D93;', 1)[1]
            require('D93;'+scope, D93_TOKENS, 'D93 backlog '+card['id'])
            scopes.append(scope)
    lines = [line for line in docs['AGENTS.md'].splitlines() if line.startswith('- D93 ')]
    if len(lines) != 1:
        raise ValueError('D93: exactly one AGENTS receiving summary required')
    require(lines[0], D93_AGENTS_TOKENS, 'D93 AGENTS')
    scopes.append(lines[0])
    scope = '\n'.join(scopes).casefold()
    if any(claim.casefold() in scope for claim in D93_FORBIDDEN_CLAIMS):
        raise ValueError('D93: implicit receiving grant, expanded delegation/lifecycle or false delivery')


def validate_d94(docs):
    """Offline receiving-cap policy only; not runtime capacity enforcement."""
    text = docs[GLOSSARY]
    history = text.encode()[text.encode().index('### D1 —'.encode()):]
    if hashlib.sha256(history[:D94_HISTORY_BYTES]).hexdigest() != D94_HISTORY_SHA256:
        raise ValueError('D94: D1–D93 history changed')
    if text.count('### D94 —') != 1:
        raise ValueError('D94: exactly one receiving-cap decision required')
    decision = text.split('### D94 —')[1]
    require(decision, D94_PROVENANCE+D94_TOKENS, 'D94 decision')
    scopes = [decision]
    for path in D94_DOC_PATHS:
        start, end = '<!-- r04-d94:start -->', '<!-- r04-d94:end -->'
        if docs[path].count(start) != 1 or docs[path].count(end) != 1:
            raise ValueError('D94: exactly one active receiving-cap block required: '+path)
        block = docs[path].split(start)[1].split(end)[0]
        require(block, D94_TOKENS, 'D94 '+path)
        scopes.append(block)
    for card in json.loads(docs[BACKLOG]):
        if card['id'] in ('R04', 'R05'):
            if card['gate'].count('**D94;') != 1:
                raise ValueError('D94: exactly one backlog receiving-cap boundary required')
            block = 'D94;'+card['gate'].split('**D94;', 1)[1]
            require(block, D94_TOKENS, 'D94 backlog '+card['id'])
            scopes.append(block)
    lines = [line for line in docs['AGENTS.md'].splitlines() if line.startswith('- D94 ')]
    if len(lines) != 1:
        raise ValueError('D94: exactly one AGENTS receiving-cap summary required')
    require(lines[0], D94_TOKENS, 'D94 AGENTS')
    scopes.append(lines[0])
    if any(claim.casefold() in '\n'.join(scopes).casefold() for claim in D94_FORBIDDEN):
        raise ValueError('D94: unsafe receiving capacity, authority or runtime claim')


def validate(root):
    docs = {path: (root/path).read_text() for path in PATHS}
    priority_scope = '\n'.join(docs.values())
    for pattern in (r'operational_ready\s*=\s*true',
                    r'full_architecture\s*=\s*true\s+for each increment',
                    r'OPE01[–-]OPE05\s+(?:WAIVED|PASSED|SATISFIED|CLOSED)'):
        if re.search(pattern, priority_scope, re.I):
            raise ValueError('delivery priority: deferral is not readiness/waiver or routine full architecture')
    sequence = 'functional-completion -> final-explicit-full-architecture -> operational-exercise-later'
    for path in ('AGENTS.md', GLOSSARY, PLAN, RUNBOOK, BACKLOG):
        text = docs[path]
        if path in (GLOSSARY, PLAN, RUNBOOK):
            start, end = '<!-- pilot-priority:start -->', '<!-- pilot-priority:end -->'
            if text.count(start) != 1 or text.count(end) != 1:
                raise ValueError('delivery priority: exactly one active block required: '+path)
            text = text.split(start)[1].split(end)[0]
            boundaries = ('non waived né pronto', 'non lo sviluppo funzionale corrente',
                          'nessun pass prima dell’esecuzione effettiva',
                          'nessun nuovo lavoro specialistico esterno/a pagamento')
        elif path == 'AGENTS.md':
            text = next((line for line in text.splitlines() if line.startswith('- D89 ')), '')
            boundaries = ('not waived or ready', 'not current functional development',
                          'no pass before actual execution')
        else:
            text = next(card['gate'] for card in json.loads(text) if card['id'] == 'R06')
            boundaries = ('non waived né pronto', 'non sviluppo funzionale isolato/sintetico/sandbox',
                          'nessun pass prima di esecuzione')
        require(text, ('D89', sequence, 'OPEN/BACKLOG', 'full_architecture=false',
                       'full_architecture=true', 'tenant/RLS/CSRF')+boundaries, 'delivery priority '+path)
    full = docs[GLOSSARY].encode()
    full = full[full.index('### D1 —'.encode()):][:141575]
    if hashlib.sha256(full).hexdigest() != 'a4c152382cb6acef1e74043991c63e93d01669c283cdfed10730a90b5e04636a':
        raise ValueError('delivery priority: D1–D88 history changed')
    d89 = docs[GLOSSARY].split('### D89 —')[1]
    require(d89, ('La fase ultima "Esercizio" per ora lasciamola in backlog: voglio prima arrivare a testare a 360 gradi l\'intera architettura una volta terminato il pilota. Procediamo spediti.',
                  '27 ottobre 2026', 'Fonte e contesto', 'interpretazione dell’agente',
                  'correggibile dall’owner', 'non una nuova policy business',
                  'D1–D88 verificato', 'OPE01–OPE05 restano OPEN/BACKLOG',
                  'non lo sviluppo funzionale corrente', 'nessun esito anticipato'), 'delivery priority D89')
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
    if sorted(ids) != list(range(1, 95)):
        raise ValueError('decision register: retain unique D1–D93 and append D94')
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
    validate_d90(docs)
    validate_d91(docs)
    validate_d92(docs)
    validate_d93(docs)
    validate_d94(docs)


D92_TOKENS = (
    'D92',
    'quotazione corrente minima di proprietà Catalog',
    'riga Part sorgente selezionata, fornitore e società autorizzati',
    'inventory.purchase-intents.create',
    'workshop.orders.read',
    'senza catalog.purchase-prices.read/manage',
    'nessuna consultazione completa, storico o manutenzione listini',
    'nessun grant implicito o globale',
    'nessun lookup arbitrario tenant-wide, consultazione massiva o bypass della sorgente',
    'server deriva identità, tenant, contesto, grant correnti e accesso corrente alla sorgente',
    'mai tenant dal browser',
    'D91 manutenzione invariata',
    'D77 nessun self-grant, subdelega o nuovo potere delegabile',
    'D82/D88/D90 invariati',
    '#121 POLICY_RESOLVED_PENDING_DOCS_MERGE_RUNTIME',
    '#121/#44/#45 aperte',
    'runtime solo dopo merge docs/guardie',
    'completamento costo mancante e prezzo/provenienza congelati prima del connettore',
    'nessun runtime consegnato qui',
    '0028 Held e 0029 invariati',
    'nessun backfill automatico o repricing retroattivo',
    'D89 solo offline, nessuna full architecture ora',
)
D92_AGENTS_TOKENS = (
    'D92',
    'minimal Catalog-owned current quote',
    'selected source Part line/supplier/company',
    'inventory.purchase-intents.create + workshop.orders.read',
    'without catalog.purchase-prices.read/manage',
    'no list browsing/history/maintenance',
    'no implicit/global pricing grant',
    'no arbitrary tenant-wide lookup, bulk browsing or source bypass',
    'server derives identity/tenant/context/current grants/current source access',
    'never tenant from browser',
    'D91 maintenance unchanged',
    'D77 no self-grant/subdelegation/new delegation',
    'D82/D88/D90 unchanged',
    '#121 POLICY_RESOLVED_PENDING_DOCS_MERGE_RUNTIME',
    '#121/#44/#45 stay open',
    'runtime only after docs/guards merge',
    'missing-cost completion/frozen price/provenance before connector',
    'no runtime delivered here',
    '0028 Held/0029 unchanged',
    'no automatic backfill/repricing',
    'D89 offline only, no full architecture now',
)
D92_DOC_PATHS = (GLOSSARY, PLAN, INTENT, "docs/r04b2b1-supplier-purchase-prices.md")

D92_QUESTION = 'Serve una decisione sui permessi: un operatore autorizzato a creare richieste d’acquisto, ma senza accesso ai listini, può vedere e accettare il prezzo corrente del fornitore per quella richiesta? A — consigliata: il permesso d’acquisto consente di vedere il solo prezzo necessario alla richiesta selezionata, senza accesso alla consultazione completa, allo storico o alla modifica dei listini. B: serve anche il permesso esplicito catalog.purchase-prices.read, concesso tramite il percorso controllato dal proprietario.'

D91_AGENTS_TOKENS = (
    'supplier PURCHASE PRICE LISTS', 'company-scoped prices',
    'tenant-wide shared supplier/catalog identities',
    'admin or user with the exact pricing action/scope', 'no implicit grant or D77 bypass',
    'missing list cost defaults to provisional 0',
    'mandatory operator price entry/explicit completion before dispatch',
    'no automatic provisional-zero dispatch', 'no sales-price fallback',
    'no host-cost-only default', 'freeze accepted price/source-or-absence/provenance',
    'no retroactive repricing', 'does not require >0 or forbid deliberate zero',
    'listed-price overrides and new fiscal policy remain undecided',
    'supplier price-list prerequisite only after docs merge',
)


D93_QUESTION = 'Un operatore ha `inventory.purchase-intents.create` sul magazzino ma nessun permesso di ricevimento; l’ordine Giobby confermato è di 3 pezzi e ne arrivano2. A — consigliata: serve un’azione di ricevimento distinta, concessa soltanto dal percorso owner già controllato, senza nuova delega tenant-admin. B: il permesso di creazione richiesta consente anche questo ricevimento. Quale scegli?'
D93_HISTORY_BYTES = 156758
D93_HISTORY_SHA256 = 'fdbe603a40b6d0186498091d29ab1a304b188a8ee61285950229d14bdcdc43ea'
D93_DOC_PATHS = (GLOSSARY, PLAN, RUNBOOK)
D93_TOKENS = (
    'D93', 'Opzione A. Procedi', 'azione di ricevimento distinta',
    'inventory.purchase-intents.create non concede ricevimento',
    'grant esplicito owner-controlled', 'binding/membership già trusted',
    'verifica identità offline e riferimento audit immutabile',
    'azione/scope esatti e finiti da implementare',
    'nessuna estensione delega tenant-admin', 'nessun self-grant, subdelega o provisioning',
    'ordine3/ricevimento2 è esempio di permesso, non nuova policy quantitativa',
    'nessun nuovo ruolo o approvatore', 'overreceipt e nuove regole fiscali non decisi',
    'ricevimento ERP standalone', 'collegamento interno esplicito all’ordine confermato e alle righe congelate',
    'overlay residuo non autorevole con discrepanza Giobby visibile',
    'D82 Giobby unica autorità stock/documenti', 'nessun writer stock locale o correzione silenziosa',
    'D90 lifecycle e riapertura cap fuori perimetro', 'D91 prezzo/provenienza congelati e D92 quote minima invariati',
    'docs/guardie prima del runtime', 'nessun runtime consegnato qui',
    '#128/#44/#45 OPEN', 'D89 Esercizio OPEN/BACKLOG', 'solo offline full_architecture=false',
)
D93_AGENTS_TOKENS = (
    'Opzione A. Procedi', 'distinct receiving action',
    'purchase-intent creation does NOT grant receiving', 'explicit owner-controlled grant',
    'already-trusted binding/membership', 'offline identity verification and immutable audit reference',
    'finite exact action/scope to implement', 'no tenant-admin delegation extension',
    'no self-grant/subdelegation/provisioning', 'no new role/approver',
    'order3/receive2 is a permission example, not new quantity policy',
    'overreceipt/fiscal rules undecided', 'D86 standalone ERP receipt with explicit internal confirmed-order/frozen-line link',
    'non-authoritative residual and visible Giobby discrepancy', 'D82 Giobby sole stock/document authority',
    'no local stock writer or silent correction', 'D90 lifecycle/cap replenishment out of scope',
    'D91 frozen price/provenance and D92 minimal quote unchanged',
    'docs/guards merge before runtime', 'no runtime delivered here',
    '#128/#44/#45 OPEN', 'D89 operations OPEN/BACKLOG', 'offline full_architecture=false',
)


D93_FORBIDDEN_CLAIMS = (
    'Purchase-intent creation also grants receiving.',
    'Tenant-admin can delegate receiving.',
    'Receiving self-grant is allowed.',
    'Receiving subdelegation is allowed.',
    'Receiving provisions new memberships.',
    'Receiving requires a new approver.',
    'D93 approves overreceipt.',
    'Receipt replenishes D90 capacity.',
    'Local receipt stock writer authorized by D93.',
    'Receipt residual replaces Giobby order state.',
    'Giobby discrepancy is silently corrected.',
    'Receipt runtime delivered by D93.',
    'Receipt runtime may start before docs merge.',
)


D94_QUESTION = 'Ordine confermato di 3 pezzi: 2 già ricevuti oppure impegnati in un ricevimento con esito incerto. A — consigliata: consento al massimo un altro pezzo; blocco 2 anche con nuovo UUID e non libero la quota incerta per timeout. B: vuoi consentire eccedenze rispetto ai 3 ordinati, con una regola da specificare? Confermi A?'
D94_HISTORY_BYTES = 161719
D94_HISTORY_SHA256 = '399e7bbeba91fc352b812795a4c0fffc5daea3efce387a13fb620e3ef975c5ef'
D94_DOC_PATHS = (GLOSSARY, PLAN, RUNBOOK, 'docs/r05a9-isolated-receipt-contract.md')
D94_TOKENS = (
    'D94;', 'owner «Confermo A»',
    'cumulative receiving cap per confirmed source purchase-order line',
    'accepted receipts plus in-flight uncertain quantity plus new quantity <= ordered quantity',
    'ordered3/received-or-uncertain2 leaves1; reject2, allow at most1',
    'new UUID does not reset the cap', 'identical UUID/payload is exact replay without extra quantity',
    'timeout does not release uncertain quantity', 'no oversupply',
    'distinct from D90 Part-line pending purchase-intent cap and D92 quote visibility',
    'receipt completion does not replenish D90',
    'cancellation/rejection/manual uncertain release/overdelivery exceptions/new fiscal rules out of scope',
    'D93 dedicated owner-controlled receiving grant; no implicit purchase permission; D77 no bypass',
    'D82 Giobby sole stock/document authority',
    'D86 explicit internal confirmed-order/frozen-line relationship, not native ERP linkage',
    'non-authoritative overlay; ERP per-order residual UNKNOWN; stock precision discrepancy visible; no silent correction',
    'lost ACK HOLD; no blind POST', 'existing R05.a.9 provider proof sufficient; no new sandbox calls',
    'POLICY_RESOLVED_PENDING_DOCS_MERGE_RUNTIME', 'docs/guards merge before runtime',
    '#128/#44/#45 OPEN', 'offline full_architecture=false; D89 operations OPEN/BACKLOG',
    'no runtime delivered here',
)
D94_PROVENANCE = (D94_QUESTION, '> Confermo A\n', '1 novembre 2026',
                  'Registro D1–D93 verificato', 'A selezionata; B non selezionata',
                  'B: regola UNDECIDED', 'distinta dalle risposte «Confermo A» di D90 e D92')
D94_FORBIDDEN = (
    'Receiving cap resets with a new UUID.',
    'Uncertain quantity is released automatically on timeout.',
    'Only accepted receipts consume receiving capacity.',
    'Overdelivery is allowed by D94.',
    'Receipt completion replenishes D90.',
    'Purchase permission implicitly grants receiving.',
    'ERP residual is the internal overlay.',
    'Lost ACK allows another POST.',
    'D94 runtime delivered.',
)
D94_HANDOFF = (
    'physical-connection race pool4', 'single-connection completion pool1',
    'accepted AND in-flight uncertain quantities count', 'exact replay after completion and timeout',
    'no automatic release', 'distinct UUIDs cannot oversupply the same confirmed source line',
    'source-line lock and atomic capacity/receipt/outbox recording',
)


class AuthorityTests(unittest.TestCase):
    def test_d94_records_exact_owner_answer_question_and_history(self):
        text = (ROOT/GLOSSARY).read_text()
        self.assertIn('### D94 —', text, 'cumulative receiving decision missing')
        before, decision = text.split('### D94 —')
        history = before.encode()[before.encode().index('### D1 —'.encode()):]
        self.assertEqual(hashlib.sha256(history[:D94_HISTORY_BYTES]).hexdigest(), D94_HISTORY_SHA256)
        require(decision, D94_PROVENANCE, 'D94 provenance')

    def test_d94_active_boundaries(self):
        for path in D94_DOC_PATHS:
            text = (ROOT/path).read_text()
            self.assertEqual(text.count('<!-- r04-d94:start -->'), 1, path)
            self.assertEqual(text.count('<!-- r04-d94:end -->'), 1, path)
            require(text.split('<!-- r04-d94:start -->')[1].split('<!-- r04-d94:end -->')[0], D94_TOKENS, 'D94 '+path)
        for card in json.loads((ROOT/BACKLOG).read_text()):
            if card['id'] in ('R04', 'R05'):
                require(card['gate'], D94_TOKENS, 'D94 backlog '+card['id'])

    def test_d94_agents_summary(self):
        lines = [line for line in (ROOT/'AGENTS.md').read_text().splitlines() if line.startswith('- D94 ')]
        self.assertEqual(len(lines), 1, 'missing unique D94 AGENTS summary')
        require(lines[0], D94_TOKENS, 'D94 AGENTS')

    def test_d94_runtime_handoff(self):
        text = (ROOT/RUNBOOK).read_text()
        self.assertIn('### D94 — next implementation handoff', text)
        require(text.split('### D94 — next implementation handoff')[1].split('## 5.')[0], D94_HANDOFF, 'D94 handoff')

    def d94_mutation(self, path, token=None, claim=None, card_id=None, decision=False):
        with tempfile.TemporaryDirectory(prefix='d94-cap-') as temp:
            root = Path(temp)
            for source in (*PATHS, *D94_DOC_PATHS):
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/path
            text = target.read_text()
            if card_id:
                cards = json.loads(text)
                card = next(c for c in cards if c['id'] == card_id)
                before, scope = card['gate'].split('**D94;', 1)
                scope = '**D94;'+scope
                after = ''
            elif decision:
                before, scope = text.split('### D94 —')
                before += '### D94 —'
                after = ''
            elif path == 'AGENTS.md':
                scope = next(line for line in text.splitlines() if line.startswith('- D94 '))
                before, after = text.split(scope)
            else:
                before, rest = text.split('<!-- r04-d94:start -->')
                scope, after = rest.split('<!-- r04-d94:end -->')
                before += '<!-- r04-d94:start -->'
                after = '<!-- r04-d94:end -->'+after
            if token:
                self.assertIn(token, scope, 'valid D94 mutation precondition')
                scope = scope.replace(token, 'REMOVED')
            else:
                scope += ' '+claim
            if card_id:
                card['gate'] = before+scope
                text = json.dumps(cards, ensure_ascii=False)
            else:
                text = before+scope+after
            target.write_text(text)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D94', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d94_cli_refuses_each_removed_boundary(self):
        for path in (*D94_DOC_PATHS, 'AGENTS.md'):
            for token in D94_TOKENS:
                with self.subTest(path=path, token=token):
                    self.d94_mutation(path, token=token)
        for card_id in ('R04', 'R05'):
            for token in D94_TOKENS:
                with self.subTest(card=card_id, token=token):
                    self.d94_mutation(BACKLOG, token=token, card_id=card_id)

    def test_d94_cli_refuses_provenance_changes(self):
        for token in D94_PROVENANCE:
            with self.subTest(token=token):
                self.d94_mutation(GLOSSARY, token=token, decision=True)

    def test_d94_cli_refuses_prior_d93_history_edit(self):
        with tempfile.TemporaryDirectory(prefix='d94-history-') as temp:
            root = Path(temp)
            for source in (*PATHS, *D94_DOC_PATHS):
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/GLOSSARY
            text = target.read_text()
            self.assertEqual(text.count('### D93 —'), 1)
            target.write_text(text.replace('### D93 —', '### D93 — MODIFIED'))
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D94', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d94_cli_refuses_unsafe_claims(self):
        for path in (*D94_DOC_PATHS, 'AGENTS.md'):
            for claim in D94_FORBIDDEN:
                with self.subTest(path=path, claim=claim):
                    self.d94_mutation(path, claim=claim)
        for card_id in ('R04', 'R05'):
            for claim in D94_FORBIDDEN:
                with self.subTest(card=card_id, claim=claim):
                    self.d94_mutation(BACKLOG, claim=claim, card_id=card_id)

    def d93_mutation(self, path, old=None, claim=None, card_id=None, history=False):
        with tempfile.TemporaryDirectory(prefix='d93-receipt-') as temp:
            root = Path(temp)
            for source in PATHS:
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/path
            text = target.read_text()
            if card_id:
                cards = json.loads(text)
                card = next(c for c in cards if c['id'] == card_id)
                self.assertIn(old, card['gate']) if old else None
                before, scope = card['gate'].split('**D93;', 1)
                self.assertIn(old, '**D93;'+scope) if old else None
                scope = ('**D93;'+scope).replace(old, 'REMOVED') if old else '**D93;'+scope+' '+claim
                card['gate'] = before+scope
                text = json.dumps(cards, ensure_ascii=False)
            elif history:
                if old == '### D92 —':
                    self.assertIn(old, text)
                    text = text.replace(old, old+' MODIFIED')
                else:
                    before, decision = text.split('### D93 —')
                    self.assertIn(old, decision)
                    text = before+'### D93 —'+decision.replace(old, 'REMOVED')
            elif path in D93_DOC_PATHS:
                before, rest = text.split('<!-- r04-d93:start -->')
                scope, after = rest.split('<!-- r04-d93:end -->')
                self.assertIn(old, scope) if old else None
                scope = scope.replace(old, 'REMOVED') if old else scope+' '+claim
                text = before+'<!-- r04-d93:start -->'+scope+'<!-- r04-d93:end -->'+after
            else:
                lines = [line for line in text.splitlines() if line.startswith('- D93 ')]
                self.assertEqual(len(lines), 1)
                line = lines[0]
                self.assertIn(old, line) if old else None
                changed = line.replace(old, 'REMOVED') if old else line+' '+claim
                text = text.replace(line, changed)
            target.write_text(text)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D93', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d93_cli_refuses_each_removed_boundary(self):
        for path in D93_DOC_PATHS:
            for token in D93_TOKENS:
                with self.subTest(path=path, token=token):
                    self.d93_mutation(path, old=token)
        for card_id in ('R04', 'R05'):
            for token in D93_TOKENS:
                with self.subTest(card=card_id, token=token):
                    self.d93_mutation(BACKLOG, old=token, card_id=card_id)
        for token in D93_AGENTS_TOKENS:
            with self.subTest(path='AGENTS.md', token=token):
                self.d93_mutation('AGENTS.md', old=token)
        line = next(l for l in (ROOT/'AGENTS.md').read_text().splitlines() if l.startswith('- D93 '))
        self.d93_mutation('AGENTS.md', old=line)

    def test_d93_cli_refuses_question_answer_and_prior_history_changes(self):
        for token in (D93_QUESTION, '> Opzione A. Procedi\n', 'B non selezionata', '### D92 —'):
            with self.subTest(token=token):
                self.d93_mutation(GLOSSARY, old=token, history=True)

    def test_d93_cli_refuses_implicit_grant_and_false_runtime_claims(self):
        for path in (*D93_DOC_PATHS, 'AGENTS.md'):
            for claim in D93_FORBIDDEN_CLAIMS:
                with self.subTest(path=path, claim=claim):
                    self.d93_mutation(path, claim=claim)
        for card_id in ('R04', 'R05'):
            for claim in D93_FORBIDDEN_CLAIMS:
                with self.subTest(card=card_id, claim=claim):
                    self.d93_mutation(BACKLOG, claim=claim, card_id=card_id)

    def test_d93_records_exact_owner_answer_question_and_history(self):
        text = (ROOT/GLOSSARY).read_text()
        self.assertIn('### D93 —', text, 'receiving authorization decision missing')
        before, decision = text.split('### D93 —')
        history = before.encode().split('### D1 —'.encode(), 1)[1]
        history = '### D1 —'.encode()+history
        self.assertEqual(hashlib.sha256(history[:D93_HISTORY_BYTES]).hexdigest(), D93_HISTORY_SHA256)
        require(decision, (D93_QUESTION, '> Opzione A. Procedi\n', '29 ottobre 2026',
                           'Registro D1–D92 verificato', 'B non selezionata'), 'D93 provenance')

    def test_d93_evidence_handoff_preserves_bounded_continuation(self):
        text = (ROOT/RUNBOOK).read_text()
        self.assertIn('### D86/D93 — handoff evidenza dopo merge documentale', text)
        require(text.split('### D86/D93 — handoff evidenza dopo merge documentale')[1], (
            'raw capture propri conservati, read-only e zero-write prima',
            'massimo 1 POST ricevimento persistito + 1 simulazione', '<=25 chiamate business',
            'ledger fsync prima della richiesta', 'limit=5/offset=0',
            'chiave receipt-list preregistrata prima di aprire l’oracle',
            'pagina piena/vuota/non univoca/errore => HOLD, mai secondo POST',
            'nessun nuovo fornitore/materiale/ordine', 'nessun PUT/DELETE/transform',
            'confronto ordine sorgente e stock pool', 'D93 non estende D83/D84',
        ), 'D93 evidence handoff')

    def test_d93_agents_summary(self):
        lines = [line for line in (ROOT/'AGENTS.md').read_text().splitlines() if line.startswith('- D93 ')]
        self.assertEqual(len(lines), 1, 'missing unique D93 AGENTS summary')
        require(lines[0], D93_AGENTS_TOKENS, 'D93 AGENTS')

    def test_d93_active_receiving_boundary_and_agents_summary(self):
        for path in D93_DOC_PATHS:
            text = (ROOT/path).read_text()
            self.assertEqual(text.count('<!-- r04-d93:start -->'), 1, path)
            self.assertEqual(text.count('<!-- r04-d93:end -->'), 1, path)
            require(text.split('<!-- r04-d93:start -->')[1].split('<!-- r04-d93:end -->')[0], D93_TOKENS, 'D93 '+path)
        for card in json.loads((ROOT/BACKLOG).read_text()):
            if card['id'] in ('R04', 'R05'):
                require(card['gate'], D93_TOKENS, 'D93 backlog '+card['id'])
        lines = [line for line in (ROOT/'AGENTS.md').read_text().splitlines() if line.startswith('- D93 ')]
        self.assertEqual(len(lines), 1, 'missing unique D93 AGENTS summary')
        require(lines[0], D93_AGENTS_TOKENS, 'D93 AGENTS')

    def d92_mutation(self, path, old=None, claim=None, card_id=None, history=False):
        with tempfile.TemporaryDirectory(prefix='d92-quote-') as temp:
            root = Path(temp)
            for source in PATHS:
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/path
            text = target.read_text()
            if card_id:
                cards = json.loads(text)
                card = next(c for c in cards if c['id'] == card_id)
                self.assertIn(old, card['gate']) if old else None
                card['gate'] = card['gate'].replace(old, 'REMOVED') if old else card['gate']+' '+claim
                text = json.dumps(cards, ensure_ascii=False)
            elif path in D92_DOC_PATHS and not history:
                before, rest = text.split('<!-- r04-d92:start -->')
                scope, after = rest.split('<!-- r04-d92:end -->')
                self.assertIn(old, scope) if old else None
                scope = scope.replace(old, 'REMOVED') if old else scope+' '+claim
                text = before+'<!-- r04-d92:start -->'+scope+'<!-- r04-d92:end -->'+after
            elif history and old == '### D91 —':
                self.assertIn(old, text)
                text = text.replace(old, '### D91 — MODIFIED')
            elif history:
                before, scope = text.split('### D92 —')
                self.assertIn(old, scope)
                text = before+'### D92 —'+scope.replace(old, 'REMOVED')
            else:
                self.assertIn(old, text) if old else None
                text = text.replace(old, 'REMOVED') if old else text+'\n'+claim
            target.write_text(text)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D92', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d92_cli_refuses_each_removed_active_boundary(self):
        for path in D92_DOC_PATHS:
            for token in D92_TOKENS:
                with self.subTest(path=path, token=token):
                    self.d92_mutation(path, old=token)
        for card_id in ('R04', 'R05'):
            for token in D92_TOKENS:
                with self.subTest(card=card_id, token=token):
                    self.d92_mutation(BACKLOG, old=token, card_id=card_id)
        for token in D92_AGENTS_TOKENS:
            with self.subTest(path='AGENTS.md', token=token):
                # Mutate only the active D92 summary, not older decisions.
                line = next(l for l in (ROOT/'AGENTS.md').read_text().splitlines() if l.startswith('- D92 '))
                self.d92_mutation('AGENTS.md', old=line, claim=None) if token == 'D92' else self.d92_mutation('AGENTS.md', old=token)

    def test_d92_cli_refuses_quote_question_and_history_changes(self):
        for token in ('> Confermo A\n', D92_QUESTION, 'B non selezionata'):
            with self.subTest(token=token):
                self.d92_mutation(GLOSSARY, old=token, history=True)
        self.d92_mutation(GLOSSARY, old='### D91 —', history=True)

    def test_d92_cli_refuses_expanded_authority_or_runtime_claims(self):
        claims = ('Purchasing grants full price-list browsing.',
                  'Purchasing grants price history and maintenance.',
                  'Purchasing automatically grants catalog.purchase-prices.read/manage.',
                  'Arbitrary tenant-wide quote lookup allowed.',
                  'Bulk quote browsing allowed.', 'Source access bypass allowed.',
                  'Tenant from browser trusted for quote.',
                  'Quote runtime delivered by D92.',
                  'Runtime starts before docs merge.',
                  'Quote requires catalog.purchase-prices.read in addition to purchase permission.')
        for path in (*D92_DOC_PATHS, 'AGENTS.md'):
            for claim in claims:
                with self.subTest(path=path, claim=claim):
                    self.d92_mutation(path, claim=claim)
        for card_id in ('R04', 'R05'):
            for claim in claims:
                with self.subTest(card=card_id, claim=claim):
                    self.d92_mutation(BACKLOG, claim=claim, card_id=card_id)

    def test_d92_active_quote_boundary_and_agents_summary(self):
        for path in D92_DOC_PATHS:
            text = (ROOT/path).read_text()
            self.assertEqual(text.count('<!-- r04-d92:start -->'), 1, path)
            self.assertEqual(text.count('<!-- r04-d92:end -->'), 1, path)
            block = text.split('<!-- r04-d92:start -->')[1].split('<!-- r04-d92:end -->')[0]
            require(block, D92_TOKENS, 'D92 '+path)
        for card in json.loads((ROOT/BACKLOG).read_text()):
            if card['id'] in ('R04', 'R05'):
                require(card['gate'], D92_TOKENS, 'D92 backlog '+card['id'])

    def test_d92_agents_summary(self):
        lines = [line for line in (ROOT/'AGENTS.md').read_text().splitlines()
                 if line.startswith('- D92 ')]
        self.assertEqual(len(lines), 1, 'missing unique D92 AGENTS summary')
        require(lines[0], D92_AGENTS_TOKENS, 'D92 AGENTS')

    def test_d92_records_exact_question_answer_and_old_history(self):
        text = (ROOT/GLOSSARY).read_text()
        self.assertIn('### D92 —', text, 'quote visibility decision not recorded')
        before, decision = text.split('### D92 —')
        history = before.encode().split('### D1 —'.encode(), 1)[1]
        history = '### D1 —'.encode()+history
        self.assertEqual(len(history[:152968]), 152968)
        self.assertEqual(hashlib.sha256(history[:152968]).hexdigest(),
                         '53551d8c884be224783f2a0d8ad4d353fb32d80203a99c608ca6608d9d8a3ad7')
        require(decision, (D92_QUESTION, '> Confermo A\n', '28 ottobre 2026',
                          'Registro D1–D91 verificato', 'B non selezionata',
                          'distinta dal «Confermo A» di D90'), 'D92 provenance')

    def test_d91_agents_summary_preserves_exact_pricing_boundary(self):
        lines = [line for line in (ROOT/'AGENTS.md').read_text().splitlines()
                 if line.startswith('- D91 ')]
        self.assertEqual(len(lines), 1, 'missing unique D91 AGENTS summary')
        require(lines[0], D91_AGENTS_TOKENS, 'D91 AGENTS')

    def test_d91_agents_summary_removal_is_refused_by_cli(self):
        for token in D91_AGENTS_TOKENS:
            with self.subTest(token=token):
                self.d91_mutation('AGENTS.md', old=token)
        line = next(line for line in (ROOT/'AGENTS.md').read_text().splitlines()
                    if line.startswith('- D91 '))
        self.d91_mutation('AGENTS.md', old=line)

    def test_d91_rejects_unsafe_pricing_policy_in_active_paths(self):
        claims = ('Host-cost-only policy approved.',
                  'Sales UnitPrice fallback to purchase cost allowed.',
                  'Missing-price provisional zero auto-dispatch allowed.',
                  'Admin label grants implicit pricing rights.',
                  'Frozen purchase intents retroactively repriced.')
        paths = (GLOSSARY, PLAN, BACKLOG, 'docs/r04b2a-purchase-intent.md', 'AGENTS.md')
        for path in paths:
            for claim in claims:
                with self.subTest(path=path, claim=claim):
                    self.d91_mutation(path, claim=claim)

    def test_d91_boundaries_and_provenance_are_required(self):
        tokens = ('listini/prezzi ed estensioni societari', 'mai fallback di costo',
                  'default UI 0 solo provvisorio', 'non confermato automaticamente',
                  'inserimento/completamento esplicito obbligatorio',
                  'non impone >0 né vieta uno zero deliberato', 'azione/scope esatti',
                  'etichetta admin senza diritti impliciti', 'concessioni owner-controlled D77',
                  'nessun self-grant o subdelega', 'prezzo sorgente (o assenza)',
                  'prezzo finale accettato e provenienza', 'nessun repricing retroattivo',
                  'prerequisito listini fornitore -> inserimento obbligatorio costo mancante/prezzo acquisto congelato -> ripresa connettore R04.b.2b',
                  '0028 PUBLISHED invariata', 'append-only', 'nessun backfill automatico',
                  'restano non decisi', 'fuori dalla prima implementazione limitata',
                  'nessuna enforcement runtime o consegna adapter')
        for path in (GLOSSARY, PLAN, BACKLOG):
            for token in tokens:
                with self.subTest(path=path, token=token):
                    self.d91_mutation(path, old=token)
        for token in ('> B: prezzo di acquisto definito nei listini di acquisto del fornitore',
                      'A: inviare 0 e modificare in ERP; B: costo configurato dall’host; C: inserimento operatore',
                      'La scelta B non è approvata.'):
            with self.subTest(token=token):
                self.d91_mutation(GLOSSARY, old=token, historical=True)

    def d91_mutation(self, path, claim=None, old=None, historical=False):
        with tempfile.TemporaryDirectory(prefix='d91-pricing-') as temp:
            root = Path(temp)
            for source in (*PATHS, 'docs/r04b2a-purchase-intent.md'):
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/path
            text = target.read_text()
            if path in (GLOSSARY, PLAN) and not historical:
                before, rest = text.split('<!-- r04-d91:start -->')
                scope, after = rest.split('<!-- r04-d91:end -->')
                self.assertIn(old, scope) if old else None
                scope = scope.replace(old, 'REMOVED') if old else scope+'\n'+claim+'\n'
                text = before+'<!-- r04-d91:start -->'+scope+'<!-- r04-d91:end -->'+after
            elif claim:
                if path == BACKLOG:
                    cards = json.loads(text)
                    next(c for c in cards if c['id'] == 'R04')['gate'] += ' '+claim
                    text = json.dumps(cards, ensure_ascii=False)
                else:
                    text += '\n'+claim+'\n'
            else:
                self.assertIn(old, text, 'valid pricing mutation precondition')
                text = text.replace(old, 'REMOVED')
            target.write_text(text)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D91', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d91_records_exact_owner_refinement_and_context(self):
        text = (ROOT/GLOSSARY).read_text()
        self.assertIn('### D91 —', text, 'supplier purchase-price policy not recorded')
        decision = text.split('### D91 —')[1]
        self.assertIn('> B: prezzo di acquisto definito nei listini di acquisto del fornitore configurabili dall’amministratore o da chi ne ha i permessi. Laddove il prezzo di acquisto non esiste nel listino allora è zero di default ed è delegato all’operatore di inserire obbligatoriamente il prezzo.\n', decision)
        self.assertIn('DocumentRowApi.price', decision)
        self.assertIn('A: inviare 0 e modificare in ERP; B: costo configurato dall’host; C: inserimento operatore', decision)
        self.assertIn('Registro D1–D90 verificato prima dell’assegnazione', decision)
        self.assertIn('28 ottobre 2026', decision)

    def test_d90_records_exact_owner_answer_and_question(self):
        text = (ROOT/GLOSSARY).read_text()
        self.assertIn('### D90 —', text, 'confirmed cumulative purchase-intent cap is not recorded')
        decision = text.split('### D90 —')[1]
        self.assertIn('> Confermo A\n', decision)
        self.assertIn('Esempio: la riga richiede 3 pezzi e una richiesta d’acquisto pendente ne copre già 2. Una nuova richiesta, anche verso un altro fornitore, può chiedere: A — consigliato: al massimo 1 pezzo, contando cumulativamente tutte le richieste della stessa riga. B: altri 2 pezzi, consentendo di superare il fabbisogno complessivo. I retry della stessa richiesta restano senza duplicati in entrambi i casi. Confermi A?', decision)
        self.assertIn('Registro D1–D89 verificato prima dell’assegnazione', decision)
        self.assertIn('27 ottobre 2026', decision)

    def test_d90_active_cap_and_bounds_cannot_be_removed(self):
        cases = {
            GLOSSARY: ('singola riga Part sorgente', 'tutti i fornitori e magazzini',
                       'nuovo UUID non azzera il cap', 'replay esatto senza quantità aggiuntiva',
                       'non riducono automaticamente il cap', 'lifecycle successive fuori perimetro',
                       'nessun nuovo scope/ruolo/provisioning', 'Nessuna scelta di mapping o codice',
                       'solo dopo merge', 'nessuna acceptance runtime o readiness'),
            PLAN: ('singola riga Part sorgente', 'tutti i fornitori e magazzini',
                   'nuovo UUID non azzera il cap', 'replay esatto senza quantità aggiuntiva',
                   'non riducono automaticamente il cap', 'lifecycle successive fuori perimetro',
                   'nessun nuovo scope/ruolo/provisioning', 'Nessuna scelta di mapping o codice',
                   'solo dopo merge', 'nessuna acceptance runtime o readiness'),
            'AGENTS.md': ('per source Part line across suppliers and warehouse choices',
                          'never per command', 'new UUID does not reset the cap',
                          'exact replay with no extra quantity', 'do not automatically reduce the cap',
                          'later lifecycle is out of scope', 'no new scopes/roles/provisioning',
                          'mapping or code decisions', 'must merge before implementation'),
            BACKLOG: ('cap cumulativo per riga Part sorgente', 'pendenti/fornitori/magazzini',
                      'non per comando', 'nuovo UUID non azzera', 'replay esatto senza quantità aggiuntiva',
                      'Nessuna riduzione automatica', 'nessuna transizione lifecycle',
                      'nessun nuovo scope/ruolo/provisioning', 'mapping o codice deciso', 'dopo merge'),
            'docs/r04b1-supplier-role.md': ('cap cumulativo per riga Part sorgente',
                      'intenti pendenti, fornitori e magazzini', 'Nuovo UUID non azzera il cap',
                      'replay esatto senza quantità aggiuntiva', 'non sottratte automaticamente',
                      'lifecycle successivo fuori perimetro', 'nessun nuovo scope/ruolo/provisioning',
                      'mapping o codice deciso', 'solo dopo merge'),
        }
        for path, tokens in cases.items():
            for token in tokens:
                with self.subTest(path=path, token=token):
                    self.d90_mutation(path, token, 'REMOVED', active_only=True)

    def d90_mutation(self, path, old, new, active_only=False):
        with tempfile.TemporaryDirectory(prefix='d90-cap-') as temp:
            root = Path(temp)
            for source in (*PATHS, 'docs/r04b1-supplier-role.md'):
                target = root/source
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/source, target)
            target = root/path
            text = target.read_text()
            if active_only and path in (GLOSSARY, PLAN):
                before, rest = text.split('<!-- r04-d90:start -->')
                block, after = rest.split('<!-- r04-d90:end -->')
                self.assertIn(old, block, 'valid active mutation precondition')
                text = before+'<!-- r04-d90:start -->'+block.replace(old, new)+'<!-- r04-d90:end -->'+after
            else:
                self.assertIn(old, text, 'valid mutation precondition')
                text = text.replace(old, new)
            target.write_text(text)
            result = self.invoke(root)
            self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
            self.assertIn('D90', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_d90_rejects_per_command_reset_and_inferred_policy(self):
        claims = ('Cap per comando consentito.', 'Nuovo UUID azzera il cap.',
                  'Cambio fornitore azzera il cap.', 'Cambio magazzino azzera il cap.',
                  'Same UUID adds more quantity.', 'ERP availability automatically reduces the cap.',
                  'Reserved quantity automatically reduces the cap.',
                  'Cancellation automatically replenishes capacity.',
                  'Receipt automatically reopens capacity.',
                  'New purchase roles and provisioning approved.',
                  'Vendor mapping policy decided by D90.',
                  'D90 cap runtime enforcement delivered.')
        for path in (GLOSSARY, PLAN, 'AGENTS.md', BACKLOG, 'docs/r04b1-supplier-role.md'):
            for claim in claims:
                with self.subTest(path=path, claim=claim):
                    self.d90_mutation(path, 'D90', 'D90 '+claim, active_only=path in (GLOSSARY, PLAN))

    def test_d90_provenance_and_d89_bytes_are_preserved(self):
        for old, new in (('> Confermo A\n', '> Confermo B\n'),
                         ('Confermi A?', 'Confermi B?'),
                         ('### D89 — Priorità', '### D89 — MODIFIED Priorità')):
            with self.subTest(old=old):
                self.d90_mutation(GLOSSARY, old, new)

    def test_current_documents_are_coherent(self):
        validate(ROOT)

    def invoke(self, root):
        return subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--check',
                               '--root', str(root)], capture_output=True, text=True, timeout=20)

    def test_ops_deferral_is_not_readiness_or_routine_full_architecture(self):
        claims = ('Operational exercise deferred means operational_ready=true',
                  'full_architecture=true for each increment',
                  'OPE01–OPE05 WAIVED')
        with tempfile.TemporaryDirectory(prefix='pilot-priority-') as temp:
            root = Path(temp)
            for claim in claims:
                with self.subTest(claim=claim):
                    for source in PATHS:
                        target = root/source
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT/source, target)
                    target = root/'AGENTS.md'
                    target.write_text(target.read_text()+'\n'+claim+'\n')
                    result = self.invoke(root)
                    self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                    self.assertIn('delivery priority', result.stderr)

    def test_explicit_priority_sequence_is_required_in_each_active_reading_path(self):
        for path in ('AGENTS.md', GLOSSARY, PLAN, RUNBOOK, BACKLOG):
            with self.subTest(path=path), tempfile.TemporaryDirectory(prefix='pilot-sequence-') as temp:
                root = Path(temp)
                for source in PATHS:
                    target = root/source
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT/source, target)
                target = root/path
                # Before D89 there is no block; afterwards remove its required anchor.
                target.write_text(target.read_text().replace('functional-completion -> final-explicit-full-architecture -> operational-exercise-later', 'SEQUENCE OMITTED'))
                result = self.invoke(root)
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                self.assertIn('delivery priority', result.stderr)

    def test_deferral_boundaries_cannot_be_removed_from_active_priority(self):
        cases = [('AGENTS.md', 'not waived or ready'),
                 ('AGENTS.md', 'not current functional development'),
                 ('AGENTS.md', 'no pass before actual execution')]
        for path in (GLOSSARY, PLAN, RUNBOOK):
            cases += [(path, token) for token in ('non waived né pronto',
                       'non lo sviluppo funzionale corrente', 'nessun pass prima dell’esecuzione effettiva',
                       'nessun nuovo lavoro specialistico esterno/a pagamento')]
        cases += [(BACKLOG, token) for token in ('non waived né pronto',
                  'non sviluppo funzionale isolato/sintetico/sandbox', 'nessun pass prima di esecuzione')]
        with tempfile.TemporaryDirectory(prefix='pilot-boundaries-') as temp:
            root = Path(temp)
            for path, token in cases:
                with self.subTest(path=path, token=token):
                    for source in PATHS:
                        target = root/source
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT/source, target)
                    target = root/path
                    text = target.read_text()
                    self.assertIn(token, text)
                    target.write_text(text.replace(token, 'REMOVED'))
                    result = self.invoke(root)
                    self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                    self.assertIn('delivery priority', result.stderr)

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
