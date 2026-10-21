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
    require(active, "## Stato corrente attivo — C00", path)
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

print("PASS C00 active status, report delivery metadata, historical runbooks and CI selection are consistent")
