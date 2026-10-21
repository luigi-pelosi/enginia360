#!/usr/bin/env python3
"""Explicit, checksummed runtime migrations. Never imports historical fixture SQL."""
import hashlib
import json
from pathlib import Path
import re
import os
import subprocess
import sys
import argparse
import signal
import ctypes


def apply_migrations(entries):
    app_user = os.environ.get('R00_APP_USER', '')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', app_user):
        raise ValueError('invalid application role')
    for key in ('PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD'):
        if not os.environ.get(key):
            raise ValueError('missing runtime database configuration')
    sql = r'''SET lock_timeout = '10s';
SET statement_timeout = '30s';
SELECT pg_advisory_lock(hashtextextended('enginia360.runtime_migrations.v1', 0));
CREATE TEMP TABLE runtime_role_config AS SELECT :'app_user'::text AS app_user;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_roles r, runtime_role_config c WHERE r.rolname=c.app_user
    AND r.rolcanlogin AND NOT (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolinherit)
    AND r.rolname<>current_user
    AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=r.oid)
    AND NOT pg_has_role(r.rolname, current_user, 'MEMBER')
    AND NOT pg_has_role(r.rolname, 'enginia360_outbox_reader', 'MEMBER')) THEN
  RAISE EXCEPTION 'unsafe application database role';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='enginia360_outbox_reader'
   AND NOT rolcanlogin AND rolbypassrls AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit)) THEN
  RAISE EXCEPTION 'unsafe outbox technical role';
 END IF;
END $$;
DO $$ BEGIN
 IF (SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname=current_user)
    OR current_user <> (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) THEN
  RAISE EXCEPTION 'migrator must be the nonprivileged database owner';
 END IF;
END $$;
SELECT to_regclass('runtime_migrations.applied') IS NULL AS untracked \gset
\if :untracked
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema','public'))
 OR EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public')
 OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public')
 OR EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public')
 OR EXISTS (SELECT 1 FROM pg_extension WHERE extname<>'plpgsql') THEN
  RAISE EXCEPTION 'untracked nonempty database refused';
 END IF;
END $$;
BEGIN;
CREATE SCHEMA runtime_migrations;
REVOKE ALL ON SCHEMA runtime_migrations FROM PUBLIC;
CREATE TABLE runtime_migrations.applied (
 id text PRIMARY KEY, checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
 applied_at timestamptz NOT NULL DEFAULT clock_timestamp());
GRANT USAGE ON SCHEMA runtime_migrations TO :"app_user";
GRANT SELECT ON runtime_migrations.applied TO :"app_user";
COMMIT;
\endif
CREATE TEMP TABLE expected_migrations (id text PRIMARY KEY, checksum text NOT NULL, ordinal integer NOT NULL);
'''
    values = ','.join(f"('{entry['id']}','{entry['sha256']}',{number})" for number, entry in enumerate(entries, 1))
    sql += 'INSERT INTO expected_migrations VALUES ' + values + ';\n'
    sql += r'''DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM runtime_migrations.applied a FULL JOIN expected_migrations e USING (id)
   WHERE (a.id IS NOT NULL AND (e.id IS NULL OR a.checksum<>e.checksum))
      OR (a.id IS NULL AND e.ordinal <= (SELECT count(*) FROM runtime_migrations.applied))) THEN
  RAISE EXCEPTION 'migration history is not a matching manifest prefix';
 END IF;
END $$;
'''
    for entry in entries:
        identifier = entry['id']
        sql += f"SELECT NOT EXISTS (SELECT 1 FROM runtime_migrations.applied WHERE id='{identifier}') AS pending \\gset\n\\if :pending\n"
        sql += 'BEGIN;\n' + entry['sql'] + f"\nINSERT INTO runtime_migrations.applied(id,checksum) VALUES ('{identifier}','{entry['sha256']}');\nCOMMIT;\n\\endif\n"
    env = {key: value for key, value in os.environ.items() if key in ('PATH', 'PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD')}
    env.update(PGCONNECT_TIMEOUT='5', PGAPPNAME='enginia360-runtime-migrator', LC_ALL='C')
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    if not sys.platform.startswith('linux'):
        raise ValueError('runtime migrator requires Linux parent-death protection')
    # The CLI is single-threaded. Kill psql on uncatchable parent death as well as normal cancellation.
    # Otherwise quiet DDL can finish and COMMIT from buffered stdin after the controller is SIGKILLed.
    parent_pid = os.getpid()
    libc = ctypes.CDLL(None, use_errno=True)
    def parent_death_guard():
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent_pid:
            os._exit(125)

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    process = None
    try:
        process = subprocess.Popen(['psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-v', f'app_user={app_user}'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                                   preexec_fn=parent_death_guard)
        process.communicate(sql, timeout=120)
        if process.returncode:
            raise ValueError('runtime migration refused or failed; current unit was not recorded')
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print('Runtime migration manifest verified and applied.')


def validate_sql(sql):
    # Ignore quoted bodies/literals/comments before looking for engine-owned commands.
    # This is a restrictive migration-file check, not an untrusted-SQL sandbox.
    tokens = re.compile(r'''(?P<dollar>\$(?:[a-zA-Z_][a-zA-Z_0-9]*)?\$).*?(?P=dollar)|'(?:''|[^'])*'|"(?:""|[^"])*"|--[^\n]*(?:\n|$)|/\*.*?\*/|(?P<end>;)|(?P<word>[a-zA-Z_][a-zA-Z_0-9]*)|(?P<meta>\\)|.''', re.S)
    words = []
    for token in tokens.finditer(sql):
        if token.group('meta'):
            raise ValueError('psql commands are engine-owned')
        if token.group('word') and len(words) < 2:
            words.append(token.group('word').upper())
        if token.group('end'):
            if words and (words[0] in ('BEGIN','COMMIT','ROLLBACK','END','ABORT') or words == ['START','TRANSACTION']):
                raise ValueError('transaction wrappers are engine-owned')
            words = []
    if words and words[0] in ('BEGIN','COMMIT','ROLLBACK','END','ABORT'):
        raise ValueError('transaction wrappers are engine-owned')


def load_manifest(path):
    path = Path(path)
    entries = json.loads(path.read_text())
    if not isinstance(entries, list) or not entries:
        raise ValueError('empty or invalid manifest')
    result = []
    for number, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or set(entry) != {'id', 'path', 'sha256'}:
            raise ValueError('invalid manifest fields')
        identifier = entry['id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9]{4}_[a-z][a-z0-9_]*', identifier) or not identifier.startswith(f'{number:04d}_'):
            raise ValueError('invalid migration order or id')
        if entry['path'] != f'migrations/{identifier}.sql':
            raise ValueError('migration path outside allowlist')
        source = path.parent / entry['path']
        if (path.parent / 'migrations').is_symlink() or source.is_symlink() or source.resolve().parent != (path.parent / 'migrations').resolve():
            raise ValueError('migration symlink outside allowlist')
        payload = source.read_bytes()
        if entry['sha256'] != hashlib.sha256(payload).hexdigest():
            raise ValueError('migration checksum mismatch')
        sql = payload.decode('utf-8')
        validate_sql(sql)
        result.append(dict(entry, sql=sql))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=Path(__file__).resolve().parents[1] / 'database/runtime/manifest.json')
    args = parser.parse_args()
    try:
        apply_migrations(load_manifest(args.manifest))
    except KeyboardInterrupt:
        print('Runtime migration interrupted; connection closed and current unit rolled back.', file=sys.stderr)
        raise SystemExit(130) from None
    except (ValueError, OSError, subprocess.SubprocessError):
        print('Runtime migration refused or failed; inspect manifest/configuration and ledger. No secrets logged.', file=sys.stderr)
        raise SystemExit(1) from None
