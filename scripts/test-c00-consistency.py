#!/usr/bin/env python3
"""Fail closed when active delivery metadata becomes stale."""

from pathlib import Path

FINAL_MAIN = "fa972837684e67b9e5094025acdd54848a46c62a"
FINAL_MAIN_RUN = "39518931794"
ACTIVE_DOCS = [
    "docs/foundation/01-glossary-and-domain-boundaries.md",
    "docs/foundation/04-first-vertical-slice.md",
    "docs/foundation/05-solution-and-module-boundaries.md",
    "docs/foundation/07-vertical-slice-backlog.md",
    "docs/foundation/09-stakeholder-validation.md",
]
REPORTS = {
    "docs/b10-verification.md": ("#31", "39424479525", "#16"),
    "docs/b11-verification.md": ("#32", "39454873760", "#17"),
    "docs/b12-verification.md": ("#33", "39487605553", "#18"),
    "docs/b13-verification.md": ("#34", "39498640111", "#19"),
    "docs/b14-verification.md": ("#35", "39513412208", "#20"),
}
MANUAL_RUNBOOKS = [
    "docs/b02-manual-testing.md",
    "docs/b03-manual-operations.md",
    "docs/b03-manual-scenarios.it.md",
    "docs/b04-manual-operations.md",
    "docs/b04-manual-scenarios.it.md",
    "docs/b05-manual-operations.md",
    "docs/b05-manual-scenarios.it.md",
    "docs/b06-manual-operations.md",
    "docs/b06-manual-scenarios.it.md",
]


def require(text: str, value: str, path: str) -> None:
    if value not in text:
        raise AssertionError(f"{path}: missing {value!r}")


def reject(condition: bool, message: str) -> None:
    if condition:
        raise AssertionError(message)


for path in ACTIVE_DOCS:
    text = Path(path).read_text()
    active = text.split("## Archivio storico", 1)[0]
    require(active, "## Stato corrente attivo — P00/UI01/R00–R06", path)
    require(active, "D76", path)
    for value in ("D74", "D75", "productization-plan.md", "Giobby", "autorità", "nessun go-live"):
        require(active, value, path)
    for stale in ("C00 è il solo", "UI01 richiede autorizzazione separata", "UI01 richiede un incarico separato"):
        reject(stale in active, f"{path}: obsolete authorization {stale!r}")
    require(active, "B01–B14", path)
    require(active, "PR #21–#35", path)
    require(active, "issue #8–#20", path)
    require(active, FINAL_MAIN, path)
    require(active, FINAL_MAIN_RUN, path)
    require(active, "D01", path)
    require(active, "B00", path)
    require(active, "UI01", path)
    require(active, "produzione", path)
    require(active, "manuale persistent", path)
    require(text, "## Archivio storico", path)
    for stale in ("B11 In corso", "B12–B14 restano Backlog", "consegna remota da verificare"):
        reject(stale in active, f"{path}: stale active status {stale!r}")

for path, (pr, run, issue) in REPORTS.items():
    header = "\n".join(Path(path).read_text().splitlines()[:8])
    for value in ("Consegna verificata", pr, run, issue, FINAL_MAIN, FINAL_MAIN_RUN):
        require(header, value, path)
    reject("da verificare" in header, f"{path}: remote delivery still pending in active header")

agents = Path("AGENTS.md").read_text()
for value in ("C00", "post-slice", "UI01", "No new persistent manual environment", "public deployment"):
    require(agents, value, "AGENTS.md")
reject("current sequential B07–B14" in agents, "AGENTS.md: obsolete sequential scope remains active")

for path in MANUAL_RUNBOOKS:
    banner = "\n".join(Path(path).read_text().splitlines()[:8])
    require(banner, "STORICO — ambiente rimosso", path)
    require(banner, "non è un endpoint attivo", path)

c00_report = Path("docs/c00-reconciliation.md").read_text()
for value in (FINAL_MAIN, FINAL_MAIN_RUN, "PR #21–#35", "#8–#20", "UI01", "#37", "nessuna rimozione"):
    require(c00_report, value, "docs/c00-reconciliation.md")

workflow = Path(".github/workflows/ci.yml").read_text()
require(workflow, "python3 scripts/test-c00-consistency.py", ".github/workflows/ci.yml")
for number in range(2, 15):
    selection = f"run: sh scripts/run-b{number:02d}-tests.sh"
    reject(workflow.count(selection) != 1, f"CI selection must contain exactly one {selection!r}")

# Productization extends authorization, never the historical delivery assertions.
import json
import re

plan_path = "docs/productization-plan.md"
plan = Path(plan_path).read_text()
cards = json.loads(Path("docs/productization-backlog.json").read_text())
expected = {
    "P00": "Perimetro pilota", "UI01": "Editor commessa", "R00": "Runtime",
    "R01": "Amministrazione organizzativa", "R02": "Anagrafiche",
    "R03": "Ciclo officina", "R04": "Magazzino e approvvigionamento",
    "R05": "Integrazione Giobby", "R06": "Migrazione e readiness",
}
reject([card["id"] for card in cards] != list(expected), "Productization IDs/order changed or duplicated")
seen = set()
for card in cards:
    identifier = card["id"]
    reject(card["title"] != expected[identifier], f"{identifier}: original meaning changed")
    reject(not set(card["depends"]).issubset(seen), f"{identifier}: missing/forward/cyclic dependency")
    reject(not card["slices"] or not card["gate"] or not card["criteria"], f"{identifier}: incomplete card")
    require(plan, f"### {identifier} — {card['title']}", plan_path)
    for value in [card["gate"], card["criteria"], *card["slices"]]:
        require(plan, value, plan_path)
    if identifier in ("R02", "R04", "R05"):
        require(card["gate"], "AUTHORITY", identifier)
    seen.add(identifier)
require(plan, "unica autorità del nucleo anagrafico condiviso tenant-wide D26/D65", plan_path)
for value in ("D76", "direzione unilaterale configurabile", "societarie", "profilo tecnico concreto",
              "Non servono nuova approvazione D26", "Nessun writer bidirezionale concorrente"):
    require(plan, value, plan_path)
for value in ("D74", "D75", "Giobby", "SAP custom BTP", "nessun codice applicativo",
              "Nessun go-live", "stock", "non certificano", "contabile interna"):
    require(plan, value, plan_path)
for value in ("D74", "D75", "P00/UI01/R00–R06", "Giobby", "D76",
              "no app changes", "25 retained", "SAP custom BTP"):
    require(agents, value, "AGENTS.md")
reject("only current post-slice authorization is C00" in agents, "AGENTS.md: obsolete C00-only authorization")
register = Path(ACTIVE_DOCS[0]).read_text()
ids = re.findall(r"^### D(\d+) —", register, re.MULTILINE)
reject(len(ids) != len(set(ids)) or set(map(int, ids)) != set(range(1, 87)),
       "Decision register must retain D1–D85 and append unique D86")
# Authorization guards inspect active text only; chronological decisions stay intact.
reject('**D77 — accesso iniziale e delega limitata:**' not in register.split('## Archivio storico', 1)[0],
       'missing active D77')
r01_gate = next(card['gate'] for card in cards if card['id'] == 'R01')
for boundary in ('fuori dall\'applicazione', 'verifica identità e tracciamento',
                 'esplicitamente delegati', 'Nessun self-grant, subdelega, altro admin o default-first-user',
                 'binding e mandato restano al proprietario', 'non provisioning completo né policy CRUD R02'):
    reject(boundary not in r01_gate, 'D77 bounded mandate: '+boundary)
for path in ["AGENTS.md", plan_path, *ACTIVE_DOCS]:
    active = Path(path).read_text().split("## Archivio storico", 1)[0]
    for stale in ("no commit, push or merge yet", "senza commit/push/merge",
                  "non effettuare commit/push/merge", "nessun codice applicativo, commit/push/merge"):
        reject(stale in active, f"{path}: obsolete preparation restriction {stale!r}")
require(plan, "giobby-discovery.md", plan_path)
reject(not Path("docs/giobby-discovery.md").is_file(), "Giobby evidence missing")
# Read the command, not a comment containing the command's name.
ci_commands = "\n".join(line.split("#", 1)[0] for line in workflow.splitlines())
reject("python3 scripts/test-productization-consistency.py" not in ci_commands,
       "Productization mutation suite must execute in CI")
print("PASS C00 delivery/history/CI invariants and D74–D77 bounded productization authorization, IDs, dependencies and gates")
