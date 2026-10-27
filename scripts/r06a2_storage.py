#!/usr/bin/env python3
"""Actual PostgreSQL staging-only export/import. No app tables or migration engine."""
import importlib.util
import json
import subprocess
from pathlib import Path
spec = importlib.util.spec_from_file_location('r06a2_transfer', Path(__file__).with_name('r06a2_transfer.py'))
assert spec and spec.loader
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


def sql_json(value):
    # Only hex is interpolated into SQL. No untrusted identifiers or psql commands.
    return "convert_from(decode('" + transfer.synthetic.canonical(value).hex() + "','hex'),'UTF8')::jsonb"


def export_source(sql):
    dataset = {'format': transfer.synthetic.FORMAT, 'records': json.loads(sql(
        "SELECT coalesce(jsonb_agg(payload ORDER BY source_id),'[]'::jsonb) FROM r06a2_staging.source;"))}
    return transfer.envelope(dataset)


def import_bytes(sql, payload):
    document = transfer.parse(payload)
    header = {k: v for k, v in document.items() if k != 'dataset'}
    value = sql_json(document)
    statement = 'BEGIN; SET LOCAL statement_timeout=\'20s\'; CREATE TEMP TABLE incoming(doc jsonb) ON COMMIT DROP; INSERT INTO incoming VALUES (' + value + ');'
    statement += '''LOCK TABLE r06a2_staging.batches IN SHARE ROW EXCLUSIVE MODE;
DO $import$ BEGIN
IF EXISTS (SELECT FROM r06a2_staging.batches b,incoming i WHERE b.source_system=i.doc->>'source_system'
 AND b.batch_id=i.doc->>'batch_id' AND b.revision=(i.doc->>'revision')::int AND b.hash=i.doc->>'sha256') THEN RETURN; END IF;
IF EXISTS (SELECT FROM r06a2_staging.batches b,incoming i WHERE b.source_system=i.doc->>'source_system'
 AND b.batch_id=i.doc->>'batch_id' AND b.revision=(i.doc->>'revision')::int) THEN RAISE EXCEPTION 'R06A2_REFUSED_CONFLICTING_REPLAY'; END IF;
IF NOT EXISTS (SELECT FROM r06a2_staging.configuration c,incoming i WHERE c.value=i.doc->'context') THEN
 RAISE EXCEPTION 'R06A2_REFUSED_SCOPE_OR_AUTHORITY_HELD'; END IF;
INSERT INTO r06a2_staging.batches
 SELECT doc->>'source_system',doc->>'batch_id',(doc->>'revision')::int,doc->>'sha256',doc-'dataset',now() FROM incoming;
INSERT INTO r06a2_staging.imported
 SELECT doc->>'source_system',doc->>'batch_id',(doc->>'revision')::int,r->>'source_id',r->>'internal_id',doc->>'sha256',r
 FROM incoming, jsonb_array_elements(doc->'dataset'->'records') r;
INSERT INTO r06a2_staging.audit
 SELECT doc->>'source_system',doc->>'batch_id',(doc->>'revision')::int,doc->>'sha256',now() FROM incoming;
END $import$;
COMMIT;'''
    try:
        sql(statement)
    except subprocess.CalledProcessError as error:
        raise ValueError('import refused: ' + ('conflicting replay' if 'R06A2_REFUSED_CONFLICTING' in (error.stderr or '') else
                                                 'scope or authority held' if 'R06A2_REFUSED_SCOPE' in (error.stderr or '') else 'storage rejected')) from None
    return header


def export_target(sql, key):
    key_json = sql_json(key)
    condition = "source_system = k->>'source_system' AND batch_id = k->>'batch_id' AND revision = (k->>'revision')::int"
    statement = "WITH key AS (SELECT " + key_json + " k) SELECT header || jsonb_build_object('dataset',jsonb_build_object('format','" + transfer.synthetic.FORMAT + "','records',"
    statement += "(SELECT coalesce(jsonb_agg(payload ORDER BY source_id),'[]'::jsonb) FROM r06a2_staging.imported,key WHERE " + condition + "))) FROM r06a2_staging.batches,key WHERE " + condition + ';'
    return json.loads(sql(statement))
