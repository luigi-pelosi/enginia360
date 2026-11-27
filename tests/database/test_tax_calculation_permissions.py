"""Prova finita F5 su PostgreSQL 18.6 isolato, senza connessioni live.

TAX_CALCULATION_DB_TESTS=1 python -m unittest tests.database.test_tax_calculation_permissions -v
Log SQL, exit effettivi e inventario hash persistono nella release privata.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import time
import unittest
import uuid

from database.sql_source import load_foundation_sql
from tests.database import test_taxmanagement_runtime as phase1

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path('/root/.config/enginia360/releases/taxcalculation-20261127/sql')
CODES = tuple('tax-calculation.' + action for action in ('read', 'simulate', 'calculate'))
CODE_SQL = ','.join("'" + code + "'" for code in CODES)
SCHEMAS = "('foundation','masterdata','taxmanagement')"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.environ.get('TAX_CALCULATION_DB_TESTS') == '1', 'Richiede PostgreSQL isolato esplicito')
class TaxCalculationPermissionsTests(unittest.TestCase):
    runtime_codes = []
    catalog_coherence = {}
    @classmethod
    def sql(cls, statement, database='taxproof', check=True):
        result = subprocess.run(['docker', 'exec', '-i', cls.container, 'psql', '-U', 'postgres',
            '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-d', database], input=statement,
            text=True, capture_output=True, timeout=75)
        cls.serial += 1
        stem = f'{cls.serial:04d}-{database}'
        (cls.run_dir / (stem + '.sql')).write_text(statement)
        (cls.run_dir / (stem + '.log')).write_text(result.stdout + result.stderr)
        with (cls.run_dir / 'actual-exits.jsonl').open('a') as handle:
            handle.write(json.dumps({'step': stem, 'exit': result.returncode}) + '\n')
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    @classmethod
    def scalar(cls, statement, database='taxproof'):
        return cls.sql(statement, database).stdout.strip()

    @classmethod
    def setUpClass(cls):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        cls.run_dir = EVIDENCE / ('final-permissions-' + uuid.uuid4().hex[:12])
        cls.run_dir.mkdir()
        cls.serial = 0
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)
        cls.tenants = [str(uuid.uuid4()) for _ in range(2)]
        cls.final_codes = cls.accepted_codes(cls.predicate('taxproof'), 'taxproof')
        assert len(cls.final_codes) == 147, cls.final_codes
        for tenant in cls.tenants:
            cls.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{tenant}','{tenant}','Prova sintetica');"
                + ''.join(f"INSERT INTO foundation.permission(tenant_id,code,name,description,is_system) VALUES('{tenant}','{code}','Nome preservato','Descrizione preservata',true);" for code in cls.final_codes)
                + f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{tenant}','custom.preserved','Custom preservato',false);"
                + f"INSERT INTO foundation.role(tenant_id,code,name) VALUES('{tenant}','existing','Ruolo preservato');"
                + f"INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT '{tenant}',r.id,p.id FROM foundation.role r JOIN foundation.permission p ON p.tenant_id=r.tenant_id WHERE r.tenant_id='{tenant}' AND p.code NOT IN ({CODE_SQL});")
        cls.before_rows = cls.rows('taxproof')
        cls.before_metadata = cls.metadata('taxproof')


    @classmethod
    def predicate(cls, database):
        return cls.scalar("SELECT pg_get_expr(conbin,conrelid) FROM pg_constraint WHERE conrelid='foundation.permission'::regclass AND conname='permission_system_code_check';", database)

    @classmethod
    def accepted_codes(cls, predicate, database):
        # Enumerazione del dominio finito: anche le coppie resource.action storiche.
        tokens = set(re.findall(r"'([^']*)'", predicate))
        candidates = sorted(tokens | {a + '.' + b for a in tokens for b in tokens})
        values = ','.join("('" + code.replace("'", "''") + "')" for code in candidates)
        return cls.scalar('SELECT code FROM (VALUES ' + values + ') v(code) CROSS JOIN (VALUES(true)) b(is_system) WHERE ' + predicate + ' ORDER BY code;', database).splitlines()

    @classmethod
    def rows(cls, database, ignore_new=False):
        tables = cls.scalar('SELECT schemaname||\'.\'||tablename FROM pg_tables WHERE schemaname IN ' + SCHEMAS + ' ORDER BY 1;', database).splitlines()
        assert len(tables) == 65, tables
        return cls.scalar(''.join("SELECT '" + table + "',coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]'::jsonb) FROM " + table + ' x'
            + (' WHERE code NOT IN (' + CODE_SQL + ')' if ignore_new and table == 'foundation.permission' else '') + ';' for table in tables), database)

    @classmethod
    def metadata(cls, database):
        # Metadati completi e OID; escluse solo statistiche fisiche, nessuna eccezione al CHECK.
        scope = 'SELECT oid FROM pg_namespace WHERE nspname IN ' + SCHEMAS
        rels = 'SELECT oid FROM pg_class WHERE relnamespace IN (' + scope + ')'
        queries = [
            ("pg_namespace", 'oid IN (' + scope + ')', 'to_jsonb(x)'),
            ("pg_class", 'relnamespace IN (' + scope + ')', "to_jsonb(x)-'relpages'-'reltuples'-'relallvisible'-'relallfrozen'"),
            ("pg_attribute", 'attrelid IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_attrdef", 'adrelid IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_constraint", 'connamespace IN (' + scope + ')', 'to_jsonb(x)'),
            ("pg_proc", 'pronamespace IN (' + scope + ')', 'to_jsonb(x)'),
            ("pg_trigger", 'tgrelid IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_index", 'indrelid IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_type", 'typnamespace IN (' + scope + ')', 'to_jsonb(x)'),
            ("pg_policy", 'polrelid IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_rewrite", 'ev_class IN (' + rels + ')', 'to_jsonb(x)'),
            ("pg_description", '(objoid IN (' + rels + ') OR objoid IN (SELECT oid FROM pg_proc WHERE pronamespace IN (' + scope + ')))', 'to_jsonb(x)'),
        ]
        return cls.scalar(''.join("SELECT '" + table + "',coalesce(jsonb_agg(j ORDER BY j::text),'[]'::jsonb) FROM (SELECT " + expression + ' AS j FROM ' + table + ' x WHERE ' + where + ') q;' for table, where, expression in queries), database)

    @classmethod
    def clone(cls):
        database = 'tc' + uuid.uuid4().hex[:12]
        cls.sql('CREATE DATABASE ' + database + ' TEMPLATE taxproof;', 'postgres')
        return database

    def refusal_preserves(self, database, statement, message):
        rows, metadata, predicate = self.rows(database), self.metadata(database), self.predicate(database)
        result = self.sql(statement, database, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.rows(database), rows)
        self.assertEqual(self.metadata(database), metadata)
        self.assertEqual(self.predicate(database), predicate)

    def test_01_final_definitions_no_implicit_calculation_grants(self):
        for tenant in self.tenants:
            self.assertEqual(self.scalar(f"SELECT count(*) FROM foundation.permission WHERE tenant_id='{tenant}' AND is_system;"), '147')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.permission WHERE code IN (' + CODE_SQL + ') AND is_system;'), '6')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission rp JOIN foundation.permission p ON p.id=rp.permission_id WHERE p.code IN (' + CODE_SQL + ');'), '0')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission;'), '290')
        self.assertEqual(self.scalar("SELECT count(*) FROM foundation.permission WHERE code='custom.preserved' AND NOT is_system;"), '2')


    def test_02_fresh_final_schema_parity(self):
        self.sql('CREATE DATABASE fresh;', 'postgres')
        self.sql(load_foundation_sql(), 'fresh')
        dumps=[]
        for database in ('fresh','taxproof'):
            result=subprocess.run(['docker','exec',self.container,'pg_dump','-U','postgres','--schema-only',database],capture_output=True,text=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stderr)
            dumps.append('\n'.join(line for line in result.stdout.splitlines() if not line.startswith(('\\restrict ','\\unrestrict '))))
        self.assertEqual(*dumps)
        self.assertEqual(self.accepted_codes(self.predicate('fresh'),'fresh'), self.final_codes)


    def test_07_exact_finite_147_and_invalid_system_codes_leave_rows_metadata_unchanged(self):
        self.__class__.runtime_codes = self.accepted_codes(self.predicate('taxproof'), 'taxproof')
        self.assertEqual(self.runtime_codes, self.final_codes)
        self.assertEqual(len(self.runtime_codes), 147)
        self.assertTrue(set(CODES).issubset(self.runtime_codes))
        for code in ('tax-calculation.delete', 'tax-calculation.read.extra', 'tax-calculation.READ',
                     'custom.operation', 'tax-item-profiles.update', 'company-tax-configurations.delete'):
            database = self.clone()
            self.refusal_preserves(database, f"BEGIN;INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.tenants[0]}','{code}','Vietato',true);COMMIT;", 'permission_system_code_check')
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission;'), '290')


    def test_08_runtime_catalog_and_parent_coherence_when_integrated(self):
        # Eseguire l'espressione C# REALE, non un'approssimazione regex del catalogo.
        # Isolamento dalla build applicativa mentre gli altri owner la modificano.
        paths = [ROOT / 'backend/Modules/AccessControl/PermissionCatalog.cs',
                 ROOT / 'backend/Api/Resources/Resources.cs',
                 ROOT / 'backend/Modules/Geography/CountryCodes.cs']
        permission, resources, country = [path.read_text() for path in paths]
        initializer = permission.split('public static readonly string[] Codes =', 1)[1].split(';', 1)[0]
        resource_prefix = resources.split('public sealed record Field', 1)[1].split('public static bool MetaReadOnly', 1)[0]
        # Nessuno stub dei valori: stessi record/helper/All/Links/IsGlobalMaster originali.
        scratch = Path(os.environ.get('TMPDIR', '/root/.hermes/cache/scratch')) / ('calculation-catalog-' + uuid.uuid4().hex[:12])
        scratch.mkdir()
        (scratch / 'Resources.cs').write_text('using Enginia360.Modules.Geography;\nnamespace Enginia360.Api.Resources;\npublic sealed record Field' + resource_prefix + '\n}\n')
        (scratch / 'CountryCodes.cs').write_text(country)
        (scratch / 'Program.cs').write_text('using System.Text.Json;\nusing ResourceCatalog = Enginia360.Api.Resources.Resources;\nConsole.WriteLine("SOURCE_CATALOG " + JsonSerializer.Serialize(SourceCatalog.Codes));\npublic static class SourceCatalog { public static readonly string[] Codes =' + initializer + '; }\n')
        (scratch / 'Catalog.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework><ImplicitUsings>enable</ImplicitUsings><Nullable>enable</Nullable></PropertyGroup></Project>')
        (scratch / 'NuGet.Config').write_text('<configuration><packageSources><clear /></packageSources></configuration>')
        container = 'enginia360-calculation-catalog-' + uuid.uuid4().hex[:12]
        try:
            result = subprocess.run(['docker', 'run', '--rm', '--pull=never', '--name', container,
                '--label', 'enginia360.scope=tax-calculation-catalog-proof', '--network=none', '--read-only',
                '--tmpfs', '/tmp', '-e', 'DOTNET_CLI_HOME=/tmp/dotnet', '-e', 'DOTNET_NOLOGO=1',
                '-v', str(scratch) + ':/proof', '-w', '/proof',
                'mcr.microsoft.com/dotnet/sdk:10.0.402-alpine3.24',
                'dotnet', 'run', '--project', 'Catalog.csproj', '--configuration', 'Release'],
                text=True, capture_output=True, timeout=90)
        finally:
            subprocess.run(['docker', 'rm', '-f', container], capture_output=True, timeout=30)
        (self.run_dir / 'source-catalog-runtime.log').write_text(result.stdout + result.stderr)
        with (self.run_dir / 'actual-exits.jsonl').open('a') as handle:
            handle.write(json.dumps({'step': 'source-catalog-runtime', 'exit': result.returncode}) + '\n')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = json.loads(next(line.removeprefix('SOURCE_CATALOG ') for line in result.stdout.splitlines() if line.startswith('SOURCE_CATALOG ')))
        runtime = self.accepted_codes(self.predicate('taxproof'), 'taxproof')
        self.assertEqual(actual, runtime)
        self.assertEqual(len(actual),147)
        self.__class__.catalog_coherence = {'state': 'integrated-exact',
            'runtimeCount': len(runtime), 'sourceCatalogCount': len(actual),
            'sourceHashes': {str(path.relative_to(ROOT)): digest(path) for path in paths},
            'scratch': str(scratch)}


if __name__ == '__main__':
    unittest.main(verbosity=2)
