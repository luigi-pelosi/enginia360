"""Phase2 incremental migration preservation and collision proof on isolated PostgreSQL."""
import json
import os
from pathlib import Path
import subprocess
import unittest

@unittest.skipUnless(os.environ.get('BP_PHASE2_DATABASE_PROOF')=='1','isolated phase2 PostgreSQL required')
class Phase2MigrationProof(unittest.TestCase):
    def sql(self, text):
        return subprocess.run(['docker','exec','-i',os.environ.get('BP_PHASE2_DATABASE_CONTAINER','enginia360-bp-phase2-db'),'psql','-X','-U','postgres','-d','phase2_incremental','-v','ON_ERROR_STOP=1','-At'],input=text,text=True,capture_output=True)
    def test_original_rows_and_function_sources_owners_acls_preserved(self):
        before=json.loads(Path(os.environ.get('BP_PHASE2_BEFORE','backend/obj/bp-phase2-evidence/incremental-before.json')).read_text())
        for name,schema in [('tenant','foundation'),('permission','foundation'),('company','foundation'),('business_partner','masterdata')]:
            ids=','.join("'"+r['id']+"'::uuid" for r in before[name])
            result=self.sql(f"SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY x.id),'[]') FROM {schema}.{name} x WHERE id IN ({ids});")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),sorted(before[name],key=lambda r:r['id']))
        for function in before['functions']:
            result=self.sql(f"SELECT jsonb_build_object('oid',p.oid,'name',p.proname,'source',pg_get_functiondef(p.oid),'owner',p.proowner,'acl',p.proacl) FROM pg_proc p WHERE p.oid={function['oid']};")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),function)
    def test_exact_six_permissions_seeded_with_no_grants_or_company_assignments(self):
        result=self.sql("SELECT (SELECT count(*) FROM foundation.permission WHERE code IN ('roles.assign_companies','business-partner-companies.read','business-partner-companies.create','business-partner-companies.update','business-partner-companies.use_customer','business-partner-companies.use_supplier') AND is_system AND is_enabled),(SELECT count(*) FROM foundation.role_permission),(SELECT count(*) FROM foundation.role_company);")
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'6|0|0')
    def test_reapplying_migration_fails_without_modifying_seed(self):
        migration=Path('database/migrations/archive/business_partner/20261119_business_partner_companies.sql').read_text()
        result=self.sql(migration)
        self.assertNotEqual(result.returncode,0);self.assertIn('Phase2 destination collision',result.stderr)
        self.test_exact_six_permissions_seeded_with_no_grants_or_company_assignments()

if __name__=='__main__':unittest.main(verbosity=2)
