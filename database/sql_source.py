"""Espande soltanto i cinque include ordinati della baseline finale."""
from pathlib import Path

_CANONICAL_INCLUDES = (
    r'\ir masterdata_business_partner.sql',
    r'\ir masterdata_payments.sql',
    r'\ir masterdata_catalog.sql',
    r'\ir seeds/countries.sql',
    r'\ir taxmanagement.sql',
)


def read_sql(path: str | Path) -> str:
    baseline = Path(path)
    source = baseline.read_text()
    directives = [line for line in source.splitlines() if line.lstrip().startswith('\\')]
    if not directives:
        return source
    if tuple(directives) != _CANONICAL_INCLUDES:
        raise ValueError('Attesi solo include canonici, senza altre direttive psql')
    for directive in directives:
        domain = (baseline.parent / directive.split(' ', 1)[1]).read_text()
        if any(line.lstrip().startswith('\\') for line in domain.splitlines()):
            raise ValueError('Il frammento non può contenere direttive psql')
        source = source.replace(directive, domain.rstrip('\n'), 1)
    return source


def load_foundation_sql(path: str | Path | None = None) -> str:
    baseline = Path(path) if path is not None else Path(__file__).with_name('foundation.sql')
    source = baseline.read_text()
    directives = tuple(line for line in source.splitlines() if line.lstrip().startswith('\\'))
    if directives != _CANONICAL_INCLUDES:
        raise ValueError('Attesi gli include canonici Business Partner, Payments, Catalogo, Nazioni e TaxManagement')
    return read_sql(baseline)
