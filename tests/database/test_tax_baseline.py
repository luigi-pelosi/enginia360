"""Final Tax baseline: bounded source + real PostgreSQL 18.6 proofs.

TAX_BASELINE_DB_TESTS=1 python3 -m unittest tests.database.test_tax_baseline -v
Optional TAX_BASELINE_EVIDENCE selects the private evidence directory.
The two golden hashes come from the untouched, archived eleven-include source,
installed with PostgreSQL 18.6 before consolidation (2026-11-27). Only pg_dump
restrict/unrestrict random tokens are excluded from the complete schema hash.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch'))
IMAGE = 'postgres:18.6-alpine3.24'
SDK_IMAGE = 'mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24'
SCHEMA_HASH = '902915562efd06b48c358243631b01d20d7e7fc4bde5f4ed99652eaf81ffc88a'
DATA_HASH = '7f38e2a129fea59c5f1bc2a8dcb5c85e5eca86ec8e6e65f22846c79589d2ade4'
INCLUDES = (
    r'\ir masterdata_business_partner.sql',
    r'\ir masterdata_payments.sql',
    r'\ir masterdata_catalog.sql',
    r'\ir seeds/countries.sql',
    r'\ir taxmanagement.sql',
)
_spec = importlib.util.spec_from_file_location('tax_baseline_sql_source', ROOT / 'database/sql_source.py')
assert _spec is not None and _spec.loader is not None
loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loader)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def dump_without_random_tokens(source):
    return '\n'.join(line for line in source.splitlines()
                     if not line.startswith(('\\restrict ', '\\unrestrict '))) + '\n'


class TaxBaselineSourceTests(unittest.TestCase):
    def test_exact_include_order_and_final_tables(self):
        source = (ROOT / 'database/foundation.sql').read_text()
        self.assertEqual(tuple(line for line in source.splitlines() if line.lstrip().startswith('\\')), INCLUDES)
        expanded = loader.load_foundation_sql()
        self.assertNotIn('\\ir ', expanded)
        tax = (ROOT / 'database/taxmanagement.sql').read_text()
        self.assertEqual(len(re.findall(r'^CREATE TABLE taxmanagement\.', tax, re.M)), 16)
        self.assertEqual(len(re.findall(r'^CREATE TABLE ', expanded, re.M)), 65)
        for forbidden in ('CREATE TEMP TABLE', 'permission_contract', 'INSERT INTO foundation.permission',
                          'ALTER TABLE taxmanagement.', 'CREATE OR REPLACE FUNCTION', '$preflight$',
                          'DROP SCHEMA', 'DROP TABLE'):
            self.assertNotIn(forbidden, tax)
        self.assertEqual(tax.count('CREATE FUNCTION taxmanagement.guard_company_tax_root()'), 1)
        self.assertIn("ARRAY['status','version','updated_at','tax_code']", tax)
        self.assertIn('company_tax_root_require_initial_chain', tax)
        self.assertIn('company_tax_registration_require_initial_profile', tax)
        company = source.split('CREATE TABLE foundation.company (', 1)[1].split('\n);', 1)[0]
        site = source.split('CREATE TABLE foundation.site (', 1)[1].split('\n);', 1)[0]
        self.assertNotIn('tax_code', company)
        self.assertNotIn('vat_number', site)
        self.assertNotIn('tax_code', site)

    def test_loader_rejects_noncanonical_directives(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH, prefix='tax-loader-') as directory:
            directory = Path(directory)
            for directive in INCLUDES:
                path = directory / directive.split(' ', 1)[1]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SELECT 1;\n')
            baseline = directory / 'foundation.sql'
            invalid = [INCLUDES[::-1], INCLUDES[:-1], INCLUDES + (INCLUDES[0],),
                       (r'\ir ../taxmanagement.sql',), (r'\ir migrations/20261125_taxmanagement.sql',),
                       tuple(' ' + item for item in INCLUDES), (r'\i taxmanagement.sql',)]
            for directives in invalid:
                with self.subTest(directives=directives):
                    baseline.write_text('\n'.join(directives))
                    with self.assertRaises(ValueError):
                        loader.read_sql(baseline)
                    with self.assertRaises(ValueError):
                        loader.load_foundation_sql(baseline)
            baseline.write_text('\n'.join(INCLUDES))
            self.assertEqual(loader.read_sql(baseline).count('SELECT 1;'), 5)
            (directory / 'taxmanagement.sql').write_text(r'\ir nested.sql')
            with self.assertRaises(ValueError):
                loader.read_sql(baseline)
            baseline.write_text('SELECT 42;\n')
            self.assertEqual(loader.read_sql(baseline), 'SELECT 42;\n')
            with self.assertRaises(ValueError):
                loader.load_foundation_sql(baseline)


@unittest.skipUnless(os.environ.get('TAX_BASELINE_DB_TESTS') == '1', 'set TAX_BASELINE_DB_TESTS=1')
class TaxBaselinePostgresTests(unittest.TestCase):
    @classmethod
    def command(cls, args, source=None, check=True, step='command', timeout=120):
        result = subprocess.run(args, input=source, capture_output=True, text=True, timeout=timeout)
        with (cls.evidence / 'actual-exits.jsonl').open('a') as handle:
            handle.write(json.dumps({'step': step, 'exit': result.returncode}) + '\n')
        if check and result.returncode:
            raise AssertionError(step + '\n' + result.stdout + result.stderr)
        return result

    @classmethod
    def sql(cls, source, db='direct', check=True, step='sql'):
        return cls.command(['docker', 'exec', '-i', cls.container, 'psql', '-XAt', '-U', 'postgres',
                            '-d', db, '-v', 'ON_ERROR_STOP=1'], source, check, step)

    @classmethod
    def scalar(cls, source, db='direct'):
        return cls.sql(source, db).stdout.strip()

    @classmethod
    def dump(cls, db):
        return cls.command(['docker', 'exec', cls.container, 'pg_dump', '-U', 'postgres', '-d', db,
                            '--schema-only'], step='dump-' + db).stdout

    @classmethod
    def setUpClass(cls):
        cls.evidence = Path(os.environ.get('TAX_BASELINE_EVIDENCE', str(SCRATCH / ('tax-baseline-' + uuid.uuid4().hex))))
        cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.container = 'enginia360-taxfinal-baseline-' + uuid.uuid4().hex[:12]
        result = cls.command(['docker', 'run', '-d', '--pull=never', '--name', cls.container,
            '--label', 'org.enginia360.taxfinal=baseline-proof', '--network=none',
            '--tmpfs', '/var/lib/postgresql:rw', '--tmpfs', '/var/run/postgresql:rw',
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-v', str(ROOT / 'database') + ':/schema:ro', IMAGE], step='start')
        cls.container_id = result.stdout.strip()
        cls.addClassCleanup(cls.cleanup)
        inspect = json.loads(cls.command(['docker', 'inspect', cls.container], step='inspect').stdout)[0]
        (cls.evidence / 'container-inspect.json').write_text(json.dumps(inspect, indent=2) + '\n')
        assert inspect['HostConfig']['NetworkMode'] == 'none'
        assert set(inspect['HostConfig']['Tmpfs']) == {'/var/lib/postgresql', '/var/run/postgresql'}
        assert not any(mount['Type'] == 'volume' for mount in inspect['Mounts'])
        assert inspect['Config']['Labels']['org.enginia360.taxfinal'] == 'baseline-proof'
        for _ in range(60):
            result = cls.command(['docker', 'exec', cls.container, 'pg_isready', '-U', 'postgres'],
                                 check=False, step='ready')
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise AssertionError('PostgreSQL did not become ready')
        cls.sql('CREATE ROLE enginia360_app NOLOGIN;', db='postgres', step='role')
        for db in ('direct', 'stdin', 'rollback'):
            cls.command(['docker', 'exec', cls.container, 'createdb', '-U', 'postgres', db], step='create-' + db)
        result = cls.command(['docker', 'exec', cls.container, 'psql', '-X', '-U', 'postgres',
            '-d', 'direct', '-v', 'ON_ERROR_STOP=1', '-f', '/schema/foundation.sql'], step='direct-install')
        (cls.evidence / 'direct-install.log').write_text(result.stdout + result.stderr)
        result = cls.sql(loader.load_foundation_sql(), 'stdin', step='stdin-install')
        (cls.evidence / 'stdin-install.log').write_text(result.stdout + result.stderr)
        (cls.evidence / 'sql-hashes.json').write_text(json.dumps({str(path.relative_to(ROOT)): digest(path.read_text())
            for path in [ROOT / 'database/foundation.sql', ROOT / 'database/sql_source.py', ROOT / 'database/taxmanagement.sql']}, indent=2) + '\n')

    @classmethod
    def cleanup(cls):
        info = cls.command(['docker', 'inspect', cls.container_id], check=False, step='cleanup-inspect')
        if info.returncode == 0:
            info = json.loads(info.stdout)[0]
            assert info['Config']['Labels']['org.enginia360.taxfinal'] == 'baseline-proof'
            cls.command(['docker', 'rm', '-f', cls.container_id], step='cleanup-remove')
        result = cls.command(['docker', 'inspect', cls.container_id], check=False, step='cleanup-absence')
        assert result.returncode != 0

    def test_01_complete_schema_exact_frozen_parity_both_routes(self):
        for db in ('direct', 'stdin'):
            raw = self.dump(db)
            (self.evidence / (db + '-schema.sql')).write_text(raw)
            self.assertEqual(digest(dump_without_random_tokens(raw)), SCHEMA_HASH)
        self.assertEqual(dump_without_random_tokens(self.dump('direct')), dump_without_random_tokens(self.dump('stdin')))

    def test_02_global_catalog_business_keys_and_no_fixtures(self):
        tables = self.scalar("SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') "
            "AND c.relkind='r' ORDER BY 1").splitlines()
        self.assertEqual(len(tables), 65)
        self.assertEqual(sum(table.startswith('taxmanagement.') for table in tables), 16)
        for db in ('direct', 'stdin'):
            data = {table: [json.loads(row) for row in self.scalar(f'SELECT to_jsonb(t) FROM {table} t;', db).splitlines()]
                    for table in tables}
            nonempty = {table: len(rows) for table, rows in data.items() if rows}
            self.assertEqual(nonempty, {'foundation.country': 249, 'foundation.currency': 178,
                'masterdata.fatturapa_payment_codes': 8, 'taxmanagement.tax_nature_codes': 21,
                'taxmanagement.tax_regimes': 3, 'taxmanagement.tax_types': 5})
            identities = {row['id']: table + ':' + str(row.get('iso_code', row.get('code', row['id'])))
                          for table, rows in data.items() for row in rows if 'id' in row}
            def canonical(value):
                if isinstance(value, dict):
                    return {key: canonical(item) for key, item in value.items() if key not in ('created_at', 'updated_at')}
                if isinstance(value, list):
                    return [canonical(item) for item in value]
                return identities.get(value, value) if isinstance(value, str) else value
            data = {table: sorted([canonical(row) for row in rows], key=lambda row: json.dumps(row, sort_keys=True))
                    for table, rows in data.items()}
            text = json.dumps(data, indent=2, sort_keys=True) + '\n'
            (self.evidence / (db + '-canonical-business-keys.json')).write_text(text)
            self.assertEqual(digest(text), DATA_HASH)

    def test_03_reapply_refusal_preserves_full_schema_and_catalogs(self):
        before = dump_without_random_tokens(self.dump('direct'))
        result = self.sql(loader.load_foundation_sql(), check=False, step='reapply-refused')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('esiste già', result.stderr)
        self.assertEqual(dump_without_random_tokens(self.dump('direct')), before)
        self.test_02_global_catalog_business_keys_and_no_fixtures()

    def test_04_install_failure_rolls_back_and_can_reinstall(self):
        source = loader.load_foundation_sql()
        # Fail immediately before the real outer COMMIT, after every definition and seed.
        failed = source.rsplit('COMMIT;', 1)[0] + "SELECT 1/0;\nCOMMIT;\n"
        result = self.sql(failed, 'rollback', check=False, step='full-install-rollback')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('division by zero', result.stderr)
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_namespace WHERE nspname IN ('foundation','masterdata','taxmanagement');", 'rollback'), '0')
        self.sql(source, 'rollback', step='reinstall-after-rollback')
        self.assertEqual(digest(dump_without_random_tokens(self.dump('rollback'))), SCHEMA_HASH)

    def test_05_runtime_catalog_actual_csharp_initializer_exact_147(self):
        paths = [ROOT / 'backend/Modules/AccessControl/PermissionCatalog.cs', ROOT / 'backend/Api/Resources/Resources.cs',
                 ROOT / 'backend/Modules/Geography/CountryCodes.cs']
        permission, resources, country = [path.read_text() for path in paths]
        initializer = permission.split('public static readonly string[] Codes =', 1)[1].split(';', 1)[0]
        prefix = resources.split('public sealed record Field', 1)[1].split('public static bool MetaReadOnly', 1)[0]
        scratch = self.evidence / 'runtime-catalog'
        scratch.mkdir()
        (scratch / 'Resources.cs').write_text('using Enginia360.Modules.Geography;\nnamespace Enginia360.Api.Resources;\npublic sealed record Field' + prefix + '\n}\n')
        (scratch / 'CountryCodes.cs').write_text(country)
        (scratch / 'Program.cs').write_text('using System.Text.Json;\nusing ResourceCatalog = Enginia360.Api.Resources.Resources;\nConsole.WriteLine("SOURCE_CATALOG " + JsonSerializer.Serialize(SourceCatalog.Codes));\npublic static class SourceCatalog { public static readonly string[] Codes =' + initializer + '; }\n')
        (scratch / 'Catalog.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup></Project>')
        (scratch / 'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        result = self.command(['docker', 'run', '--rm', '--pull=never', '--name', self.container + '-catalog',
            '--label', 'org.enginia360.taxfinal=runtime-catalog', '--network=none', '--read-only', '--tmpfs', '/tmp',
            '-e', 'DOTNET_CLI_HOME=/tmp/dotnet', '-e', 'DOTNET_NOLOGO=1', '-v', str(scratch) + ':/proof',
            '-w', '/proof', SDK_IMAGE, 'dotnet', 'run', '--project', 'Catalog.csproj', '--configuration', 'Release'],
            step='runtime-catalog', check=False)
        (self.evidence / 'runtime-catalog.log').write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = json.loads(next(line.removeprefix('SOURCE_CATALOG ') for line in result.stdout.splitlines() if line.startswith('SOURCE_CATALOG ')))
        predicate = self.scalar("SELECT pg_get_expr(conbin,conrelid) FROM pg_constraint WHERE conrelid='foundation.permission'::regclass AND conname='permission_system_code_check';")
        tokens = set(re.findall(r"'([^']*)'", predicate))
        candidates = sorted(tokens | {a + '.' + b for a in tokens for b in tokens})
        values = ','.join("('" + code.replace("'", "''") + "')" for code in candidates)
        accepted = self.scalar('SELECT code FROM (VALUES ' + values + ') v(code) CROSS JOIN (VALUES(true)) b(is_system) WHERE ' + predicate + ' ORDER BY code;').splitlines()
        self.assertEqual(len(accepted), 147)
        self.assertEqual(actual, accepted)
        (self.evidence / 'permission-codes-147.json').write_text(json.dumps(actual, indent=2) + '\n')
        (self.evidence / 'runtime-source-hashes.json').write_text(json.dumps({str(path.relative_to(ROOT)): digest(path.read_text()) for path in paths}, indent=2) + '\n')
        tenant = str(uuid.uuid4())
        self.sql("BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('" + tenant + "','baseline-permissions','Baseline');"
            "INSERT INTO foundation.permission(tenant_id,code,name,is_system) SELECT '" + tenant + "',code,code,true FROM (VALUES " + values + ') v(code) CROSS JOIN (VALUES(true)) b(is_system) WHERE ' + predicate + ';ROLLBACK;', step='accept-147-no-grants')
        for code in ('tax-calculation.delete', 'tax-rules.read.extra', 'companies.read.extra', 'unapproved.read'):
            result = self.sql("BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('" + tenant + "','baseline-negative','Baseline');"
                "INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('" + tenant + "','" + code + "','Denied',true);COMMIT;", check=False, step='reject-unknown-system-code')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('permission_system_code_check', result.stderr)
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission;'), '0')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.tenant;'), '0')

    def test_06_initial_chain_and_new_registration_constraints_real_runtime_role(self):
        # Synthetic identities exist only in rollback transactions, never canonical seeds.
        t, c, u, root, reg = [str(uuid.uuid4()) for _ in range(5)]
        prefix = f"""BEGIN;
INSERT INTO foundation.tenant(id,code,name) VALUES('{t}','baseline-chain','Baseline');
INSERT INTO foundation.company(id,tenant_id,name) VALUES('{c}','{t}','Baseline Company');
INSERT INTO foundation."user"(id,tenant_id,username,email,first_name,last_name) VALUES('{u}','{t}','baseline-actor','baseline@example.invalid','Baseline','Actor');
SET LOCAL ROLE enginia360_app;
INSERT INTO taxmanagement.company_tax_configurations(id,tenant_id,company_id,establishment_country_id,tax_type_id,created_by,tax_code)
SELECT '{root}','{t}','{c}',c.id,v.id,'{u}','General fiscal identity'
FROM foundation.country c CROSS JOIN taxmanagement.tax_types v WHERE c.iso_code='IT' AND v.code='VAT';
"""
        registration = f"""INSERT INTO taxmanagement.company_tax_registrations(id,tenant_id,company_tax_configuration_id,country_id,tax_identifier,registration_type,valid_from,created_by)
SELECT '{reg}','{t}','{root}',id,'IT12345678901','DOMESTIC',DATE '2026-11-26','{u}' FROM foundation.country WHERE iso_code='IT';
"""
        profile = f"""INSERT INTO taxmanagement.company_tax_regime_profiles(tenant_id,company_tax_registration_id,tax_regime_id,valid_from,created_by)
SELECT '{t}','{reg}',r.id,DATE '2026-11-26','{u}' FROM taxmanagement.tax_regimes r JOIN foundation.country c ON c.id=r.country_id WHERE c.iso_code='IT';
"""
        result = self.sql(prefix + 'SET CONSTRAINTS ALL IMMEDIATE;ROLLBACK;', check=False, step='missing-initial-registration')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('almeno una registrazione iniziale', result.stderr)
        result = self.sql(prefix + registration + 'SET CONSTRAINTS ALL IMMEDIATE;ROLLBACK;', check=False, step='missing-initial-profile')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('profilo', result.stderr)
        # Initial valid chain, including final root function that permits tax_code changes.
        self.sql(prefix + registration + profile + f"UPDATE taxmanagement.company_tax_configurations SET tax_code='Updated',version=version+1 WHERE id='{root}';SET CONSTRAINTS ALL IMMEDIATE;ROLLBACK;", step='valid-chain-runtime-role')
        # After the first initial chain has passed, a later registration independently requires a profile.
        later = f"""SET CONSTRAINTS ALL IMMEDIATE;SET CONSTRAINTS ALL DEFERRED;
INSERT INTO taxmanagement.company_tax_registrations(tenant_id,company_tax_configuration_id,country_id,tax_identifier,registration_type,valid_from,created_by)
SELECT '{t}','{root}',id,'DE123456789','DIRECT_IDENTIFICATION',DATE '2026-11-26','{u}' FROM foundation.country WHERE iso_code='DE';
SET CONSTRAINTS taxmanagement.company_tax_registration_require_initial_profile IMMEDIATE;ROLLBACK;
"""
        result = self.sql(prefix + registration + profile + later, check=False, step='later-registration-requires-profile')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Nuova registrazione richiede almeno un profilo', result.stderr)
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.tenant;'), '0')

    def test_07_catalog_and_function_privileges_not_broadened(self):
        self.assertEqual(self.scalar("SELECT has_table_privilege('enginia360_app','taxmanagement.tax_regimes','SELECT'),"
            "has_table_privilege('enginia360_app','taxmanagement.tax_regimes','UPDATE'),"
            "has_table_privilege('enginia360_app','taxmanagement.tax_types','UPDATE'),"
            "has_table_privilege('enginia360_app','taxmanagement.company_tax_configurations','DELETE'),"
            "has_column_privilege('enginia360_app','taxmanagement.company_tax_registrations','valid_to','UPDATE'),"
            "has_column_privilege('enginia360_app','taxmanagement.company_tax_registrations','tax_identifier','UPDATE'),"
            "has_function_privilege('enginia360_app','taxmanagement.require_company_tax_registration_initial_profile()','EXECUTE');"), 't|f|f|f|t|f|f')
        self.assertEqual(self.scalar("SELECT attname FROM pg_attribute WHERE attrelid='taxmanagement.company_tax_configurations'::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum DESC LIMIT 1;"), 'tax_code')
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_namespace WHERE nspname IN ('foundation','masterdata','taxmanagement','public');"), '4')


if __name__ == '__main__':
    unittest.main(verbosity=2)
