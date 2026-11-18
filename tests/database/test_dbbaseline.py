"""Invarianti correnti della baseline vuota; nessuna migrazione storica."""
import json
import unittest
from dbbaseline import sql, normalize_dump
from test_foundation import TABLES, fixture


class BaselineInvariantTests(unittest.TestCase):
    def test_exact_table_inventory(self):
        names = json.loads(sql("SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='foundation'").stdout)
        self.assertEqual(sorted(TABLES), names)
        self.assertEqual(len(names), 23)

    def test_runtime_role_has_no_escalation_or_ownership(self):
        attrs = json.loads(sql("""SELECT json_build_object('super',rolsuper,'createdb',rolcreatedb,
            'createrole',rolcreaterole,'replication',rolreplication,'bypassrls',rolbypassrls,
            'login',rolcanlogin) FROM pg_roles WHERE rolname='enginia360_app'""").stdout)
        self.assertEqual(attrs, dict.fromkeys(attrs, False))
        self.assertEqual(sql("SELECT count(*) FROM pg_auth_members WHERE member='enginia360_app'::regrole").stdout.strip(), '0')
        self.assertEqual(sql("SELECT count(*) FROM pg_class WHERE relnamespace='foundation'::regnamespace AND relowner<>'postgres'::regrole").stdout.strip(), '0')
        self.assertEqual(sql("SELECT nspowner='postgres'::regrole FROM pg_namespace WHERE nspname='foundation'").stdout.strip(), 't')
        for statement in ('SET ROLE postgres', 'SET SESSION AUTHORIZATION postgres',
                          'CREATE ROLE escalation',
                          'CREATE TABLE foundation.forbidden_test(id int)',
                          'ALTER TABLE foundation.tenant ADD COLUMN forbidden int',
                          'TRUNCATE foundation.tenant CASCADE',

                          'SELECT * FROM foundation.audit_event',
                          'UPDATE foundation.audit_event SET action=action',
                          'DELETE FROM foundation.audit_event'):
            with self.subTest(statement=statement):
                result=sql('BEGIN;'+statement+';ROLLBACK;',role='enginia360_app',check=False)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('42501',result.stderr)
        result=sql('CREATE DATABASE escalation;',role='enginia360_app',check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('42501',result.stderr)
        acl=sql("SELECT nspacl::text FROM pg_namespace WHERE nspname='foundation'").stdout
        grant=sql('GRANT ALL ON SCHEMA foundation TO PUBLIC;',role='enginia360_app',check=False)
        self.assertIn('no privileges were granted',grant.stderr)
        self.assertEqual(acl,sql("SELECT nspacl::text FROM pg_namespace WHERE nspname='foundation'").stdout)
        self.assertEqual(sql("SELECT has_schema_privilege('enginia360_app','foundation','USAGE') AND NOT has_schema_privilege('enginia360_app','foundation','CREATE')").stdout.strip(),'t')
        self.assertEqual(sql("""SELECT bool_and(has_table_privilege('enginia360_app',c.oid,'SELECT')
            AND has_table_privilege('enginia360_app',c.oid,'INSERT')
            AND has_table_privilege('enginia360_app',c.oid,'UPDATE')
            AND has_table_privilege('enginia360_app',c.oid,'DELETE')
            AND NOT has_table_privilege('enginia360_app',c.oid,'TRUNCATE'))
            FROM pg_class c WHERE relnamespace='foundation'::regnamespace
            AND relkind='r' AND relname<>'audit_event'""").stdout.strip(),'t')

    def test_audit_details_are_objects_and_runtime_can_only_append(self):
        for details in ('NULL', "'{}'::jsonb", "'{\"beforeIds\":[],\"afterIds\":[]}'::jsonb"):
            sql("BEGIN;INSERT INTO foundation.audit_event(action,resource,details) VALUES('proof','roles',"+details+");ROLLBACK;",role='enginia360_app')
        for details in ("'[]'", "'false'", "'1'", "'\"text\"'"):
            result=sql("BEGIN;INSERT INTO foundation.audit_event(action,resource,details) VALUES('proof','roles',"+details+"::jsonb);ROLLBACK;",role='enginia360_app',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('audit_event_details_check',result.stderr)

    def test_permission_catalog_is_not_a_seed_and_current_fifty_codes_are_admitted(self):
        resources=('companies','sites','warehouse-types','warehouses','warehouse-locations',
                   'settings','users','groups','roles','sales-organizations','purchasing-organizations')
        codes=[r+'.'+a for r in resources for a in ('read','create','update','delete')]
        codes+=['permissions.read','users.reset_password','roles.assign','groups.assign_users',
                'roles.assign_permissions','purchasing-organizations.assign_scope']
        self.assertEqual(len(set(codes)),50)
        base="BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('95000000-0000-0000-0000-000000000001','catalog-proof','Verifica');"
        values=','.join("('95000000-0000-0000-0000-000000000001','"+c+"','Operazione',true)" for c in codes)
        result=sql(base+'INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES '+values+';SELECT count(*) FROM foundation.role_permission;ROLLBACK;',role='enginia360_app')
        self.assertEqual(result.stdout.strip(),'0')
        for code in ('companies.write','tenants.read','roles.assign_users','unknown.read','users.read.extra'):
            result=sql(base+"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('95000000-0000-0000-0000-000000000001','"+code+"','Non ammesso',true);ROLLBACK;",check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('permission_system_code_check',result.stderr)
        sql(base+"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('95000000-0000-0000-0000-000000000001','legacy-custom','Fuori catalogo',false);ROLLBACK;")

    def test_user_identity_required_profile_and_optional_details(self):
        columns=json.loads(sql("SELECT json_object_agg(column_name,is_nullable) FROM information_schema.columns WHERE table_schema='foundation' AND table_name='user'").stdout)
        self.assertNotIn('display_name',columns)
        self.assertNotIn('user_id',columns)
        for c in ('username','first_name','last_name','email','preferred_language'):
            self.assertEqual(columns[c],'NO')
        for c in ('date_of_birth','phone_number','tenant_id','password_hash'):
            self.assertEqual(columns[c],'YES')
        for patch in ("first_name=' '","last_name=E'\\t'","email='not-an-email'",
                      "preferred_language='fr'","date_of_birth=(CURRENT_DATE+2)",
                      "phone_number=repeat('x',51)","is_super_admin=true"):
            result=sql('BEGIN;'+fixture()+'UPDATE foundation."user" SET '+patch+';ROLLBACK;',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('23514',result.stderr)
        result=sql('BEGIN;'+fixture()+"SELECT preferred_language='it' AND password_hash IS NULL FROM foundation.\"user\";ROLLBACK;")
        self.assertEqual(result.stdout.strip().splitlines(),['t','t'])

    def test_geography_global_identity_and_country_guard(self):
        base="""BEGIN;
            INSERT INTO foundation.country(id,name,iso_code) VALUES('96000000-0000-0000-0000-000000000001','Italia','IT');
            INSERT INTO foundation.city(country_id,name,postal_code,province,istat_code)
            VALUES('96000000-0000-0000-0000-000000000001','Roma','00100','RM','058091');"""
        sql(base+'ROLLBACK;',role='enginia360_app')
        for statement,marker in (
            ("UPDATE foundation.country SET iso_code='US'",'23503'),
            ("DELETE FROM foundation.country",'23001'),
            ("INSERT INTO foundation.country(name,iso_code) VALUES('Italia duplicata','IT')",'23505'),
            ("INSERT INTO foundation.country(name,iso_code) VALUES('Non valido','ZZ')",'23514'),
            ("INSERT INTO foundation.city(country_id,name,postal_code,province) VALUES('96000000-0000-0000-0000-000000000001',' roma ','00100',' rm ')",'23505'),
            ("INSERT INTO foundation.city(country_id,name,postal_code,istat_code) VALUES('96000000-0000-0000-0000-000000000001','Altro','00100','058091')",'23505')):
            with self.subTest(statement=statement):
                result=sql(base+statement+';ROLLBACK;',role='enginia360_app',check=False)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(marker,result.stderr)
        sql(base+"INSERT INTO foundation.city(country_id,name,postal_code,province,istat_code) VALUES('96000000-0000-0000-0000-000000000001','Roma','00101','RM','058091');ROLLBACK;")

    def test_oracle_normalization_does_not_hide_schema_changes(self):
        original="-- Dumped by pg_dump version 18.6\n\\restrict abc\nCREATE TABLE t(id int DEFAULT 1);\nGRANT SELECT ON t TO r;\n\\unrestrict abc\n"
        expected='CREATE TABLE t(id int DEFAULT 1);\nGRANT SELECT ON t TO r;\n'
        self.assertEqual(normalize_dump(original),expected)
        for changed in (original.replace('DEFAULT 1','DEFAULT 2'),original.replace('TO r','TO PUBLIC'),
                        original.replace('id int','id bigint'),original.replace('SELECT','ALL')):
            self.assertNotEqual(normalize_dump(original),normalize_dump(changed))


if __name__=='__main__':
    unittest.main(verbosity=2)
