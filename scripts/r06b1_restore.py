"""R06.b.1 restore rehearsal: pure, side-effect-free guards and fingerprint definitions.

Synthetic ephemeral single-host rehearsal only. Nothing here talks to Docker or a database.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil

LABEL = 'synthetic ephemeral single-host measurement'
DISCLAIMER = 'NOT RPO/RTO/SLA/PITR/off-host/disaster-recovery evidence; OPE03 remains open'
PROJECT_RE = re.compile(r'enginia360-r00b-[0-9a-f]{12}')
PROTECTED_NAMES = re.compile(r'^/?enginia360-(?:api|web)-1$')
ARCHIVE_MAGIC = b'PGDMP'


def assert_ephemeral_project(project):
    if not isinstance(project, str) or not PROJECT_RE.fullmatch(project):
        raise ValueError('refusing non-ephemeral target')


def assert_exact_targets(containers, project, config, protected_ids=()):
    """Every container to be touched is exactly labelled, hardened and free of volumes/host ports."""
    assert_ephemeral_project(project)
    if not containers:
        raise ValueError('no exact ephemeral target')
    for item in containers:
        if item['Id'] in protected_ids or PROTECTED_NAMES.match(item.get('Name', '')):
            raise ValueError('protected object refused')
        labels = item['Config'].get('Labels') or {}
        if labels.get('com.docker.compose.project') != project or labels.get('com.docker.compose.project.config_files') != str(config):
            raise ValueError('label/config mismatch refused')
        host = item['HostConfig']
        if item['Config'].get('User') in ('', '0', 'root', '0:0', None) or not host.get('ReadonlyRootfs'):
            raise ValueError('target is not nonroot/read-only')
        if host.get('CapDrop') != ['ALL'] or 'no-new-privileges:true' not in (host.get('SecurityOpt') or []):
            raise ValueError('target keeps capabilities or privilege escalation')
        if host.get('PortBindings') or any(mount.get('Type') == 'volume' for mount in item.get('Mounts', [])):
            raise ValueError('target exposes a host port or persistent volume')


def assert_empty_target(summary):
    if summary['domain_relations'] or summary['ledger_present'] or summary['schemas']:
        raise ValueError('restore into a non-empty target refused')


def verify_dump(path, expected_sha256, toc):
    path = Path(path)
    status = path.stat()
    if status.st_mode & 0o777 != 0o600:
        raise ValueError('dump must be mode 0600')
    payload = path.read_bytes()
    if not payload:
        raise ValueError('empty dump')
    if not payload.startswith(ARCHIVE_MAGIC):
        raise ValueError('not a PostgreSQL custom-format archive')
    if hashlib.sha256(payload).hexdigest() != expected_sha256:
        raise ValueError('dump sha256 mismatch (corrupt or truncated)')
    if not any(line.strip() and not line.startswith(';') for line in (toc or '').splitlines()):
        raise ValueError('dump table of contents is empty')


def compare_table_snapshots(before, after):
    problems = []
    for table in sorted(set(before) | set(after)):
        if table not in after:
            problems.append('missing:' + table)
        elif table not in before:
            problems.append('unexpected:' + table)
        else:
            if before[table]['rows'] != after[table]['rows']:
                problems.append('rows:' + table)
            if before[table]['sha256'] != after[table]['sha256']:
                problems.append('hash:' + table)
    return problems


def compare_ledger(before, after):
    before, after = [tuple(row) for row in before], [tuple(row) for row in after]
    if before == after:
        return []
    problems = []
    for index in range(max(len(before), len(after))):
        if index >= len(after):
            problems.append('ledger-missing:' + before[index][0])
        elif index >= len(before):
            problems.append('ledger-extra:' + after[index][0])
        elif before[index] != after[index]:
            problems.append('ledger-differs:%d:%s' % (index + 1, before[index][0]))
    return problems or ['ledger-differs']


def compare_fingerprints(before, after):
    return ['fingerprint:' + category for category in sorted(set(before) | set(after)) if before.get(category) != after.get(category)]


def check_markers(pre_present, post_present):
    if not pre_present:
        raise ValueError('pre-dump marker absent after restore')
    if post_present:
        raise ValueError('post-dump marker present after restore')


def is_excluded_namespace(name):
    return re.match(r'^pg_', name) is not None or name == 'information_schema'


def discovery_sql():
    # Literal ^pg_ regex (never LIKE 'pg\_%'): a user schema such as pgx_legacy must stay in scope. The ledger is a normal table.
    return ("SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.relkind IN ('r','p') AND c.relpersistence <> 't' AND NOT c.relispartition "
            "AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' ORDER BY 1")


def table_digest_sql(qualified):
    """Per-table count + sha256 over every column of every row (duplicates kept, deterministic C-collation order)."""
    return ("SELECT %s||'|'||count(*)||'|'||encode(sha256(convert_to(coalesce(jsonb_agg(v ORDER BY v::text COLLATE \"C\"),'[]'::jsonb)::text,'UTF8')),'hex') "
            "FROM (SELECT to_jsonb(t) v FROM %s t) q" % ("'" + qualified.replace("'", "''") + "'", qualified))


_USER_NS = "n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"
_HASH = "encode(sha256(convert_to(coalesce(string_agg(x, E'\\n' ORDER BY x COLLATE \"C\"),''),'UTF8')),'hex')"
# Names, never OIDs. Each statement returns exactly one sha256 text value.
FINGERPRINT_SQL = {
    'relations': "SELECT %s FROM (SELECT concat_ws('|',n.nspname,c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity,c.relpersistence,coalesce(c.reloptions::text,'')) x FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE %s AND c.relkind IN ('r','p','v','m','S','f')) q" % (_HASH, _USER_NS),
    'columns': "SELECT %s FROM (SELECT concat_ws('|',n.nspname,c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attgenerated,a.attidentity,coalesce(pg_get_expr(d.adbin,d.adrelid),'')) x FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE %s AND a.attnum>0 AND NOT a.attisdropped AND c.relkind IN ('r','p','v','m','f')) q" % (_HASH, _USER_NS),
    'constraints': "SELECT %s FROM (SELECT concat_ws('|',n.nspname,c.relname,k.conname,k.contype,k.condeferrable,k.condeferred,k.convalidated,CASE WHEN k.contype='c' THEN regexp_replace(regexp_replace(pg_get_constraintdef(k.oid),'::(character varying|text|bpchar)(\\[\\])?','','g'),'[()[:space:]]','','g') ELSE pg_get_constraintdef(k.oid) END) x FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE %s) q" % (_HASH, _USER_NS),
    'indexes': "SELECT %s FROM (SELECT concat_ws('|',schemaname,tablename,indexname,indexdef) x FROM pg_indexes WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema') q" % _HASH,
    'policies': "SELECT %s FROM (SELECT concat_ws('|',schemaname,tablename,policyname,permissive,roles::text,cmd,coalesce(qual,''),coalesce(with_check,'')) x FROM pg_policies WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema') q" % _HASH,
    'acl': "SELECT %s FROM (SELECT concat_ws('|','rel',n.nspname,c.relname,coalesce(c.relacl,acldefault((CASE c.relkind WHEN 'S' THEN 's' ELSE 'r' END)::\"char\",c.relowner))::text) x FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE %s AND c.relkind IN ('r','p','v','m','S','f') UNION ALL SELECT concat_ws('|','col',n.nspname,c.relname,a.attname,a.attacl::text) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE %s AND a.attacl IS NOT NULL UNION ALL SELECT concat_ws('|','schema',n.nspname,coalesce(n.nspacl,acldefault('n'::\"char\",n.nspowner))::text) FROM pg_namespace n WHERE %s UNION ALL SELECT concat_ws('|','fn',n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),coalesce(p.proacl,acldefault('f'::\"char\",p.proowner))::text) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE %s) q" % (_HASH, _USER_NS, _USER_NS, _USER_NS, _USER_NS),
    'owners': "SELECT %s FROM (SELECT concat_ws('|','rel',n.nspname,c.relname,pg_get_userbyid(c.relowner)) x FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE %s AND c.relkind IN ('r','p','v','m','S','f') UNION ALL SELECT concat_ws('|','schema',n.nspname,pg_get_userbyid(n.nspowner)) FROM pg_namespace n WHERE %s UNION ALL SELECT concat_ws('|','fn',n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),pg_get_userbyid(p.proowner)) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE %s) q" % (_HASH, _USER_NS, _USER_NS, _USER_NS),
    'triggers': "SELECT %s FROM (SELECT concat_ws('|',n.nspname,c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid)) x FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT t.tgisinternal AND %s) q" % (_HASH, _USER_NS),
    'functions': "SELECT %s FROM (SELECT concat_ws('|',n.nspname,p.proname,pg_get_function_identity_arguments(p.oid),p.prosecdef,coalesce(p.proconfig::text,''),p.provolatile,md5(pg_get_functiondef(p.oid))) x FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE %s AND p.prokind IN ('f','p')) q" % (_HASH, _USER_NS),
    'sequences': "SELECT %s FROM (SELECT concat_ws('|',schemaname,sequencename,sequenceowner,data_type,start_value,increment_by,coalesce(last_value::text,'')) x FROM pg_sequences WHERE schemaname !~ '^pg_' AND schemaname <> 'information_schema') q" % _HASH,
    'roles': "SELECT %s FROM (SELECT concat_ws('|',rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit) x FROM pg_roles WHERE rolname !~ '^pg_' UNION ALL SELECT concat_ws('|','member',pg_get_userbyid(roleid),pg_get_userbyid(member),inherit_option,set_option,admin_option) FROM pg_auth_members WHERE pg_get_userbyid(roleid) !~ '^pg_') q" % _HASH,
    'database': "SELECT %s FROM (SELECT concat_ws('|',datname,pg_get_userbyid(datdba),coalesce(datacl,acldefault('d'::\"char\",datdba))::text) x FROM pg_database WHERE datname=current_database()) q" % _HASH,
}


# Row-level view of exactly the same statements, kept in the baseline so that a mismatch is explained, not just detected.
FINGERPRINT_ROWS_SQL = {name: statement.replace('SELECT ' + _HASH + ' FROM (', 'SELECT x FROM (', 1) + ' ORDER BY x COLLATE "C"'
                        for name, statement in FINGERPRINT_SQL.items()}


def diff_rows(before, after):
    return {'only_before': sorted(set(before) - set(after)), 'only_after': sorted(set(after) - set(before))}


# While the API runs, the administrative dispatcher retries an unreachable simulator and rewrites attempt/error state.
# This is the only table whose CONTENT may move after restore; its row count and every other table must stay identical.
DISPATCHER_STATE_TABLES = {'integrations.administrative_dispatches'}


def unclassified_changes(changed, allowed):
    return [change for change in changed if not (change.startswith('hash:') and change[5:] in allowed)]


def dump_argv():
    # Full single-database archive; global roles are intentionally NOT in a pg_dump and come from the infrastructure bootstrap.
    return ['pg_dump', '--username=postgres', '--dbname=runtime', '--format=custom']


def restore_argv():
    # No --clean/--create/--no-owner/--no-acl: the target must be empty and ownership/ACL/policies come from the archive.
    return ['pg_restore', '--username=postgres', '--dbname=runtime', '--exit-on-error', '--single-transaction']


def build_scratch_manifest(source, destination, units):
    source, destination = Path(source), Path(destination)
    published = json.loads((source/'manifest.json').read_text())
    ids = {entry['id'] for entry in published}
    appended = []
    for number, (name, sql) in enumerate(units, len(published) + 1):
        identifier = '%04d_%s' % (number, name)
        if not re.fullmatch(r'[a-z][a-z0-9_]*', name or '') or identifier in ids:
            raise ValueError('invalid or colliding scratch migration name')
        appended.append((identifier, sql))
    destination.mkdir(parents=True)
    (destination/'migrations').mkdir()
    for entry in published:
        target = destination/entry['path']
        shutil.copyfile(source/entry['path'], target)
        target.chmod(0o444)
    entries = list(published)
    for identifier, sql in appended:
        path = destination/'migrations'/(identifier + '.sql')
        payload = sql.encode()
        path.write_bytes(payload)
        path.chmod(0o444)
        entries.append({'id': identifier, 'path': 'migrations/%s.sql' % identifier, 'sha256': hashlib.sha256(payload).hexdigest()})
    manifest = destination/'manifest.json'
    manifest.write_text(json.dumps(entries, indent=2) + '\n')
    manifest.chmod(0o444)
    for directory in (destination, destination/'migrations'):
        directory.chmod(0o555)
    return entries


def timing_report(phases):
    if not phases or any(not isinstance(value, (int, float)) or value < 0 for value in phases.values()):
        raise ValueError('timings must be non-empty and non-negative')
    lines = ['%s (monotonic seconds; %s)' % (LABEL, DISCLAIMER)]
    lines += ['  %s: %.3f s' % (name, value) for name, value in phases.items()]
    return '\n'.join(lines)
