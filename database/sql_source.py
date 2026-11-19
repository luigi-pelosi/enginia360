"""Espansione minima della baseline psql per fixture che inviano SQL su stdin.

Non interpreta SQL: riconosce soltanto la direttiva canonica completa su una
riga. L'installazione ordinaria usa psql -f database/foundation.sql.
"""
from pathlib import Path

_CANONICAL_INCLUDE = r'\ir masterdata_business_partner.sql'


def read_sql(path: str | Path) -> str:
    """Legge SQL storico senza include o espande il solo include canonico.

    Nessuna interpretazione generale SQL/psql e nessuna risoluzione arbitraria.
    """
    baseline = Path(path)
    source = baseline.read_text()
    directives = [line for line in source.splitlines() if line.lstrip().startswith('\\')]
    if not directives:
        return source
    if directives != [_CANONICAL_INCLUDE]:
        raise ValueError('Atteso un solo include canonico Business Partner, senza altre direttive psql')
    domain = baseline.with_name('masterdata_business_partner.sql').read_text()
    if any(line.lstrip().startswith('\\') for line in domain.splitlines()):
        raise ValueError('Il frammento Business Partner non può contenere direttive psql')
    return source.replace(_CANONICAL_INCLUDE, domain.rstrip('\n'), 1)


def load_foundation_sql(path: str | Path | None = None) -> str:
    """Carica la baseline corrente esigendo il suo unico include canonico."""
    baseline = Path(path) if path is not None else Path(__file__).with_name('foundation.sql')
    source = baseline.read_text()
    if _CANONICAL_INCLUDE not in source.splitlines():
        raise ValueError('Include canonico Business Partner assente')
    return read_sql(baseline)
