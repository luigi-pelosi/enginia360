#!/usr/bin/env python3
"""Synthetic PostgreSQL acceptance for the append-only R03.a order-workspace migrations (upgrade, RLS, grants, history)."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration_tests', ROOT/'scripts/test-r00-migrations.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
BASELINE = 17
NEW_TABLES = ('workshop.working_groups', 'workshop.order_notes', 'workshop.workspace_history', 'workshop.editor_commands')


class ManifestContract(unittest.TestCase):
    def test_new_units_are_appended_after_the_published_head_without_rewriting_it(self):
        entries = json.loads((ROOT/'database/runtime/manifest.json').read_text())
        self.assertEqual([e['id'] for e in entries[17:]], ['0018_workshop_order_workspace', '0019_inventory_working_group_provenance'])
        digest = hashlib.sha256(json.dumps(entries[:17], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '0ad2ffe59881d41069e375abc10b6c4272e59868d39391fa51f2808cb4b03e97', 'published 17-unit prefix changed')


@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated PostgreSQL opt-in required')
class WorkspaceSqlTests(unittest.TestCase):
    setUp = legacy.PostgreSqlTests.setUp
    tearDown = legacy.PostgreSqlTests.tearDown
    sql = legacy.PostgreSqlTests.sql
    start_migration = legacy.PostgreSqlTests.start_migration
    migrate = legacy.PostgreSqlTests.migrate

    def prefix_manifest(self, count):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        shutil.copytree(ROOT/'database/runtime/migrations', root/'migrations')
        entries = json.loads((ROOT/'database/runtime/manifest.json').read_text())[:count]
        for extra in sorted((root/'migrations').iterdir()):
            if extra.stem not in {e['id'] for e in entries}:
                extra.unlink()
        (root/'manifest.json').write_text(json.dumps(entries))
        return root/'manifest.json'

    def seed_baseline(self):
        tenant, company, site, document, payer, holder, vehicle, member = [str(uuid.uuid4()) for _ in range(8)]
        data = dict(tenant=tenant, company=company, site=site, document=document)
        orders = [str(uuid.uuid4()) for _ in range(3)]
        lines = {orders[0]: [str(uuid.uuid4()), str(uuid.uuid4())], orders[1]: [str(uuid.uuid4())], orders[2]: []}
        statements = [f"SELECT set_config('app.tenant_id','{tenant}',false);",
                      f"INSERT INTO workshop.document_types VALUES ('{document}','{tenant}','{company}',7,'Synthetic',true);",
                      f"INSERT INTO workshop.line_policies VALUES ('{tenant}','{company}','{document}',9,'Case001',true);"]
        for order in orders:
            statements.append(f"INSERT INTO workshop.orders VALUES ('{order}','{tenant}','{company}','{site}','{document}',7,'{payer}','{vehicle}','{holder}','{member}');")
        for order, ids in lines.items():
            for number, line in enumerate(ids):
                kind = 'Service' if number == 0 else 'Part'
                statements.append(f"INSERT INTO workshop.commercial_lines VALUES ('{line}','{tenant}','{order}','{uuid.uuid4()}',8,'Synthetic','{kind}',2,10.5,0,21,22,'{payer}','{order}',9,{number});")
        statements.append(f"INSERT INTO inventory.reservations VALUES ('{uuid.uuid4()}','{tenant}','{orders[0]}','{lines[orders[0]][1]}','{company}','{site}','{uuid.uuid4()}','{uuid.uuid4()}',8,1);")
        self.sql('\n'.join(statements))
        return data, orders, lines

    def test_upgrade_backfills_revision_group_and_provenance_and_preserves_saved_values(self):
        self.assertEqual(self.migrate(self.prefix_manifest(BASELINE))[0], 0)
        data, orders, lines = self.seed_baseline()
        code, _, error = self.migrate()
        self.assertEqual(code, 0, error)
        self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '19')
        tenant = data['tenant']
        scope = f"SELECT set_config('app.tenant_id','{tenant}',false);"
        revisions = self.sql(scope+'SELECT "Id"::text||\'|\'||"CommercialRevision" FROM workshop.orders ORDER BY "Id"').splitlines()[1:]
        self.assertEqual(sorted(revisions), sorted(f'{order}|{len(lines[order])}' for order in orders), 'revision must equal the historical line count')
        groups = self.sql(scope+'SELECT "Id"::text FROM workshop.working_groups ORDER BY "Id"').splitlines()[1:]
        self.assertEqual(sorted(groups), sorted(orders[:2]), 'legacy group Id=OrderId only for orders that already have lines')
        self.assertEqual(self.sql(scope+'SELECT count(*) FROM workshop.commercial_lines WHERE "State"=\'Active\' AND "Version"=1 AND "NetAmount"=21').splitlines()[-1], '3')
        self.assertEqual(self.sql(scope+'SELECT count(*) FROM workshop.workspace_history WHERE "TargetKind"=\'Line\' AND "Operation"=\'Baseline\'').splitlines()[-1], '3', 'initial version of every saved row precedes enabling updates')
        self.assertEqual(self.sql(scope+'SELECT "WorkingGroupId"=\"OrderId\" FROM inventory.reservations').splitlines()[-1], 't')
        # No business seed and no editor command was invented by the migration.
        self.assertEqual(self.sql(scope+'SELECT count(*) FROM workshop.editor_commands').splitlines()[-1], '0')

    def test_repeated_kinds_in_one_group_and_cross_order_group_are_database_enforced(self):
        self.assertEqual(self.migrate()[0], 0)
        tenant, company, site, document, payer, order, other, group, foreign = [str(uuid.uuid4()) for _ in range(9)]
        self.sql(f'''SELECT set_config('app.tenant_id','{tenant}',false);
            INSERT INTO workshop.document_types VALUES ('{document}','{tenant}','{company}',7,'Synthetic',true);
            INSERT INTO workshop.orders("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId")
              VALUES ('{order}','{tenant}','{company}','{site}','{document}',7,'{payer}','{payer}','{payer}','{payer}'),('{other}','{tenant}','{company}','{site}','{document}',7,'{payer}','{payer}','{payer}','{payer}');
            INSERT INTO workshop.working_groups("Id","TenantId","OrderId","Title","State","Version","CreatedRevision") VALUES ('{group}','{tenant}','{order}','A','Active',1,1),('{foreign}','{tenant}','{other}','B','Active',1,1);''')
        def line(identifier, group_id, order_id=order):
            return f"INSERT INTO workshop.commercial_lines(\"Id\",\"TenantId\",\"OrderId\",\"CatalogItemId\",\"CatalogVersion\",\"CatalogLabel\",\"Kind\",\"Quantity\",\"UnitPrice\",\"DiscountPercent\",\"NetAmount\",\"TaxRate\",\"PayerId\",\"WorkingGroupId\",\"ConfigurationVersion\",\"ExpectedRevision\") VALUES ('{identifier}','{tenant}','{order_id}','{payer}',8,'X','Service',1,1,0,1,22,'{payer}','{group_id}',9,0);"
        scope = f"SELECT set_config('app.tenant_id','{tenant}',false);"
        self.sql(scope+line(str(uuid.uuid4()), group)+line(str(uuid.uuid4()), group))
        with self.assertRaises(AssertionError):
            self.sql(scope+line(str(uuid.uuid4()), foreign))

    def test_forced_rls_grants_and_append_only_history(self):
        self.assertEqual(self.migrate()[0], 0)
        app = os.environ['R00_APP_USER']
        for table in NEW_TABLES:
            self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{table}'::regclass"), 't', table)
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','DELETE') OR has_table_privilege('{app}','{table}','TRUNCATE')"), 'f', table)
            self.assertEqual(self.sql(f"SELECT count(*) FROM pg_policies WHERE schemaname||'.'||tablename='{table}' AND qual IS NOT NULL AND with_check IS NOT NULL"), '1', table)
        for table in ('workshop.commercial_lines', 'workshop.orders'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','DELETE')"), 'f', table)
        for table in ('workshop.workspace_history', 'workshop.editor_commands'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','UPDATE')"), 'f', table)
            self.assertEqual(self.sql(f"SELECT count(*) FROM pg_trigger WHERE tgrelid='{table}'::regclass AND NOT tgisinternal AND tgname LIKE 'immutable%'"), '1', table)
        self.assertEqual(self.sql("SELECT count(*) FROM workshop.line_policies WHERE true"), '0', 'no business seed')

    def test_revision_is_monotonic_and_saved_identity_and_part_structure_are_trigger_protected(self):
        self.assertEqual(self.migrate()[0], 0)
        tenant, company, site, document, payer, order, group, service, part = [str(uuid.uuid4()) for _ in range(9)]
        scope = f"SELECT set_config('app.tenant_id','{tenant}',false);"
        self.sql(f'''{scope}
            INSERT INTO workshop.document_types VALUES ('{document}','{tenant}','{company}',7,'Synthetic',true);
            INSERT INTO workshop.orders("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId")
              VALUES ('{order}','{tenant}','{company}','{site}','{document}',7,'{payer}','{payer}','{payer}','{payer}');
            INSERT INTO workshop.working_groups("Id","TenantId","OrderId","Title","State","Version","CreatedRevision") VALUES ('{group}','{tenant}','{order}','A','Active',1,1);''')
        for identifier, kind in ((service, 'Service'), (part, 'Part')):
            self.sql(f"""{scope}INSERT INTO workshop.commercial_lines("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision") VALUES ('{identifier}','{tenant}','{order}','{payer}',8,'X','{kind}',1,1,0,1,22,'{payer}','{group}',9,0);""")
        def refused(statement):
            with self.assertRaises(AssertionError, msg=statement):
                self.sql(scope+statement)
        refused(f'UPDATE workshop.orders SET "CommercialRevision"=5 WHERE "Id"=\'{order}\'')
        self.sql(scope+f'UPDATE workshop.orders SET "CommercialRevision"="CommercialRevision"+1 WHERE "Id"=\'{order}\'')
        refused(f'UPDATE workshop.orders SET "CommercialRevision"="CommercialRevision"-1 WHERE "Id"=\'{order}\'')
        refused(f'UPDATE workshop.commercial_lines SET "CatalogVersion"=9 WHERE "Id"=\'{service}\'')
        refused(f'UPDATE workshop.commercial_lines SET "Quantity"=2 WHERE "Id"=\'{part}\'')
        refused(f'UPDATE workshop.commercial_lines SET "State"=\'Removed\',"Version"=2 WHERE "Id"=\'{part}\'')
        self.sql(scope+f'UPDATE workshop.commercial_lines SET "Quantity"=2,"NetAmount"=2,"Version"=2 WHERE "Id"=\'{service}\'')
        self.sql(scope+f'UPDATE workshop.commercial_lines SET "UnitPrice"=3,"NetAmount"=3,"Version"=2 WHERE "Id"=\'{part}\'')
        self.sql(scope+f'UPDATE workshop.commercial_lines SET "State"=\'Removed\',"Version"=3 WHERE "Id"=\'{service}\'')
        refused(f'UPDATE workshop.commercial_lines SET "State"=\'Active\',"Version"=4 WHERE "Id"=\'{service}\'')


if __name__ == '__main__':
    unittest.main()
