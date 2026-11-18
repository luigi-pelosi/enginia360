"""Conservazione dei dati durante l'aggiornamento anagrafico autorizzato."""

from datetime import datetime
import json
from user_rename_checks import snapshot

OWNER = 'b2364a9f-98dd-4957-ab0a-a762ac0ec3f7'
REMOVED = 'f4b58885-b1f9-4dda-a6de-fe8461deca00'


def ordered(rows):
    return sorted(json.dumps(row, sort_keys=True) for row in rows)


def verify(before, after, backfill):
    assert set(before['tables']) == set(after['tables'])
    for name, rows in before['tables'].items():
        if name in ('user', 'audit_event'):
            continue
        expected = [row for row in rows if row.get('user_id') != REMOVED] if name in ('user_role', 'user_group_member') else rows
        assert ordered(expected) == ordered(after['tables'][name]), name
    users = {row['id']: row for row in before['tables']['user']}
    assert set(users) <= {OWNER, REMOVED}, 'Utenti aggiunti: completare esplicitamente la mappatura'
    current = {row['id']: row for row in after['tables']['user']}
    assert set(current) == {OWNER}
    expected = dict(users[OWNER])
    assert expected['username'] == 'luigi.pelosi' and expected['is_super_admin']
    expected.pop('display_name')
    expected.update({key: backfill[0][key] for key in ('first_name', 'last_name', 'email')})
    expected.update(date_of_birth=None, phone_number=None, preferred_language='it')
    assert datetime.fromisoformat(current[OWNER]['updated_at']) >= datetime.fromisoformat(expected['updated_at'])
    expected['updated_at'] = current[OWNER]['updated_at']
    assert current[OWNER] == expected, 'Modifica inattesa dei dati o delle credenziali'
    previous_audit = {row['id']: row for row in before['tables']['audit_event']}
    audit = {row['id']: row for row in after['tables']['audit_event']}
    assert all(audit.get(key) == value for key, value in previous_audit.items())
    added = [row for key, row in audit.items() if key not in previous_audit]
    actions = {('update', OWNER)} | ({('delete', REMOVED)} if REMOVED in users else set())
    assert len(added) == len(actions)
    assert {(row['action'], row['record_id']) for row in added} == actions
    assert all(row['resource'] == 'users' and row['actor_id'] == OWNER for row in added)
    for key in ('oid', 'owner', 'acl', 'indexes', 'references', 'triggers'):
        assert before['identity'][key] == after['identity'][key], key
    for constraint in before['identity']['constraints']:
        if 'display_name' not in constraint:
            assert constraint in after['identity']['constraints'], constraint
    return {'tables_preserved': len(after['tables']), 'credentials_and_super_admin_preserved': True,
            'historical_audit_preserved': len(previous_audit), 'authorized_audit_events': len(added),
            'test_user_removed': True, 'personal_fields_verified': True, 'acl_and_references_preserved': True}


def script(migration, backfill):
    assert migration.count('BEGIN;') == 1 and migration.count('COMMIT;') == 1
    unit = migration.replace('BEGIN;', '', 1).replace('COMMIT;', '', 1)
    value = json.dumps(backfill).replace("'", "''")
    return f'''BEGIN;
SELECT pg_advisory_xact_lock(3607902026);
SET LOCAL enginia360.user_profile_backfill = '{value}';
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM foundation."user" WHERE id='{OWNER}' AND username='luigi.pelosi' AND is_super_admin AND tenant_id IS NULL) THEN
  RAISE EXCEPTION 'Identita proprietario non corrispondente';
 END IF;
 IF EXISTS (SELECT 1 FROM foundation."user" WHERE id='{REMOVED}' AND (username<>'test' OR is_super_admin)) THEN
  RAISE EXCEPTION 'Identita da rimuovere non corrispondente';
 END IF;
END $$;
DELETE FROM foundation.user_role WHERE user_id='{REMOVED}';
DELETE FROM foundation.user_group_member WHERE user_id='{REMOVED}';
WITH removed AS (
 DELETE FROM foundation."user" WHERE id='{REMOVED}' AND username='test' AND NOT is_super_admin RETURNING id,tenant_id
) INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id)
 SELECT '{OWNER}',tenant_id,'delete','users',id FROM removed;
{unit}
INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id)
 VALUES ('{OWNER}',NULL,'update','users','{OWNER}');
COMMIT;
'''
