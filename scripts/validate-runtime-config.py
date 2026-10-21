#!/usr/bin/env python3
"""Runtime-only role configuration; error messages never echo input."""
import os
import re


def validate(environment):
    names = [environment.get(key, '') for key in ('R00_OWNER_USER', 'R00_APP_USER')]
    if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', name) or name.startswith('pg_') for name in names) or len(set(names)) != 2 or any(name in ('postgres', 'enginia360_outbox_reader') for name in names):
        raise ValueError('invalid or overlapping runtime role names')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', environment.get('POSTGRES_DB','')):
        raise ValueError('missing or invalid runtime database name')
    keys = ('R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'POSTGRES_PASSWORD')
    for key in keys:
        if not re.fullmatch(r'[0-9a-f]{48,128}', environment.get(key, '')):
            raise ValueError('missing or invalid runtime secret')
    if len({environment[key] for key in keys}) != len(keys):
        raise ValueError('runtime roles require distinct secrets')


if __name__ == '__main__':
    try:
        validate(os.environ)
    except ValueError as error:
        raise SystemExit(str(error)) from None
