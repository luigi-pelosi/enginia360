"""Accesso fail-closed al solo PostgreSQL effimero della baseline."""
import json
import os
import re
import subprocess
from functools import lru_cache

CONTAINER = 'enginia360-foundation-schema-proof'
DATABASE = 'enginia360'
SCOPE = 'foundation-close-sql'
SITE_ADDRESS = {'tax_code': 'CF-PROOF', 'address': 'Via prova 1', 'city': 'Roma',
                'province': 'RM', 'postal_code': '00100', 'country_code': 'IT'}


@lru_cache(maxsize=1)
def require_isolated():
    if os.environ.get('ENGINIA360_BASELINE_PROOF') != '1':
        raise RuntimeError('Abilitare esplicitamente ENGINIA360_BASELINE_PROOF=1 sul solo cluster effimero')
    info = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER], text=True))[0]
    if (info['Name'] != '/' + CONTAINER
            or info['Config']['Labels'].get('enginia360.scope') != SCOPE
            or info['HostConfig']['NetworkMode'] != 'none'
            or info['HostConfig']['PortBindings']
            or any(m['Type'] != 'tmpfs' for m in info['Mounts'])):
        raise RuntimeError('Identità o isolamento del cluster baseline non validi')


def sql(statement, role='postgres', check=True, database=DATABASE):
    require_isolated()
    if database != DATABASE and not database.startswith('enginia360_proof_'):
        raise ValueError('Database fuori dallo scope di prova')
    if role not in ('postgres', 'enginia360_app'):
        raise ValueError('Ruolo di prova non ammesso')
    # Il runtime resta NOLOGIN. La sessione parte da un login effimero non
    # privilegiato: SET SESSION AUTHORIZATION da postgres sarebbe reversibile.
    if role != 'postgres':
        statement = 'SET ROLE enginia360_app;\n' + statement
    login = 'postgres' if role == 'postgres' else 'enginia360_proof_login'
    return subprocess.run(['docker', 'exec', '-i', CONTAINER, 'psql', '-U', login,
                           '-d', database, '-X', '-qAt', '-v', 'ON_ERROR_STOP=1',
                           '-v', 'VERBOSITY=verbose'], input=statement, text=True,
                          capture_output=True, check=check, timeout=90)


def dump_schema():
    require_isolated()
    return subprocess.check_output(['docker', 'exec', '-e',
        'PGOPTIONS=-c default_transaction_read_only=on', CONTAINER,
        'pg_dump', '-U', 'postgres', '-d', DATABASE, '--schema-only',
        '--schema=foundation'], text=True, timeout=60)


def normalize_dump(raw):
    """Rimuove soltanto intestazione/versioni e nonce del formato pg_dump.

    Non cambia SQL, commenti di dominio, nomi vincoli, owner, ACL o whitespace
    interno. Non ordina righe e non sopprime alcuna differenza di catalogo.
    """
    lines = raw.splitlines(keepends=True)
    return ''.join(line for line in lines if not (
        line.startswith('\\restrict ') or line.startswith('\\unrestrict ')
        or line.startswith('-- Dumped from database version ')
        or line.startswith('-- Dumped by pg_dump version ')))


PERSONAL_GRANT = re.compile(
    r'GRANT [A-Z]+(?:,[A-Z]+)* ON (?:SCHEMA foundation|TABLE foundation\.(?:[a-z_]+|"user")) TO luigi_pelosi;\n?'
)


def personal_grant_lines(raw):
    """Solo GRANT monoriga foundation al destinatario personale esatto."""
    return [line for line in raw.splitlines(keepends=True) if PERSONAL_GRANT.fullmatch(line)]


def normalize_product_dump(raw):
    """Delta approvato nuove installazioni: sole ACL personali, non owner/commenti.

    La normalizzazione tecnica precedente resta separata e invariata.
    Ogni altra riga, anche vuota o commento ACL, rimane byte per byte.
    """
    return ''.join(line for line in normalize_dump(raw).splitlines(keepends=True)
                   if not PERSONAL_GRANT.fullmatch(line))

