#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_migrations', ROOT/'scripts/apply-runtime-migrations.py')
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MigrationTlsTests(unittest.TestCase):
    def test_verified_tls_parameters_survive_minimal_child_environment(self):
        environment = {'PATH':'/usr/bin','PGHOST':'postgres','PGPORT':'5432','PGDATABASE':'runtime',
                       'PGUSER':'runtime_owner','PGPASSWORD':'synthetic','R00_APP_USER':'runtime_app',
                       'PGSSLMODE':'verify-full','PGSSLROOTCERT':'/run/tls/ca.crt','UNRELATED_SECRET':'must-not-inherit'}
        process = MagicMock(returncode=0)
        with patch.dict(module.os.environ, environment, clear=True), patch.object(module.subprocess,'Popen',return_value=process) as popen:
            module.apply_migrations([])
        child = popen.call_args.kwargs['env']
        self.assertEqual(child.get('PGSSLMODE'),'verify-full')
        self.assertEqual(child.get('PGSSLROOTCERT'),'/run/tls/ca.crt')
        self.assertNotIn('UNRELATED_SECRET',child)


if __name__ == '__main__':
    unittest.main()
