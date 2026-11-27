"""Isolated SQL requirements proof; COMPANY_TAX_REQUIREMENTS_DB_TESTS=1 enables Docker.
No live connections/writes. Only a labelled network-none tmpfs cluster is changed.
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

from tests.database import test_taxmanagement_runtime as phase1
from tests.database import test_company_tax_runtime as previous

ROOT = Path(__file__).resolve().parents[2]
CODE = 'company-tax-configurations.update'


@unittest.skipUnless(os.environ.get('COMPANY_TAX_REQUIREMENTS_DB_TESTS') == '1', 'Explicit isolated SQL opt-in required')
class CompanyTaxRequirementsTests(unittest.TestCase):
    sql = classmethod(previous.CompanyTaxRuntimeTests.sql.__func__)
    scalar = previous.CompanyTaxRuntimeTests.scalar
    reject = previous.CompanyTaxRuntimeTests.reject
    root_sql = previous.CompanyTaxRuntimeTests.root_sql
    registration_sql = previous.CompanyTaxRuntimeTests.registration_sql
    profile_sql = previous.CompanyTaxRuntimeTests.profile_sql
    bump = previous.CompanyTaxRuntimeTests.bump

    @classmethod
    def setUpClass(cls):
        phase1.TaxManagementRuntimeTests.setUpClass.__func__(cls)
        cls.legacy_tenant, cls.legacy_actor, cls.legacy_company, cls.legacy_root = [str(uuid.uuid4()) for _ in range(4)]
        # Synthetic imported incomplete root: suppress ONLY the INSERT-time
        # completeness event while constructing it, then restore the final
        # trigger before tests exercise metadata edits and grandfathering.
        cls.sql("BEGIN;ALTER TABLE taxmanagement.company_tax_configurations DISABLE TRIGGER company_tax_root_require_initial_chain;" +
            f"INSERT INTO foundation.tenant(id,code,name) VALUES('{cls.legacy_tenant}','old','Original');"
            f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES('{cls.legacy_actor}','{cls.legacy_tenant}','old','old@example.test','Old','Actor');"
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{cls.legacy_company}','{cls.legacy_tenant}','Original');"
            f"INSERT INTO taxmanagement.company_tax_configurations(id,tenant_id,company_id,tax_type_id,establishment_country_id,created_by) SELECT '{cls.legacy_root}','{cls.legacy_tenant}','{cls.legacy_company}',t.id,c.id,'{cls.legacy_actor}' FROM taxmanagement.tax_types t CROSS JOIN foundation.country c WHERE t.code='VAT' AND c.iso_code='IT';COMMIT;ALTER TABLE taxmanagement.company_tax_configurations ENABLE TRIGGER company_tax_root_require_initial_chain;")


    def setUp(self):
        self.tenant,self.other,self.actor,self.foreign_actor,self.global_actor,self.company,self.root,self.reg,self.profile = [str(uuid.uuid4()) for _ in range(9)]
        self.sql(f"INSERT INTO foundation.tenant(id,code,name) VALUES('{self.tenant}','{self.tenant}','Proof');"
            f"INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES('{self.actor}','{self.tenant}','{self.actor}','sql@example.test','SQL','Proof');"
            f"INSERT INTO foundation.company(id,tenant_id,name) VALUES('{self.company}','{self.tenant}','Proof');")
        self.country = self.scalar("SELECT id FROM foundation.country WHERE iso_code='IT'")
        self.de = self.scalar("SELECT id FROM foundation.country WHERE iso_code='DE'")
        self.type = self.scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT'")
        self.regime = self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.country}'")


    def chain(self, **root):
        return self.root_sql(**root)+self.registration_sql()+self.profile_sql()

    def test_01_missing_root_chain_rejected_at_commit_and_atomic(self):
        for children,message in [('', 'almeno una registrazione'),(self.registration_sql(),'almeno un profilo')]:
            r=self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+self.root_sql()+children+"SELECT 'reached_precommit';COMMIT;",message)
            self.assertIn('reached_precommit',r.stdout)
            self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'0')
            self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE id='{self.reg}'"),'0')

    def test_02_every_initial_registration_needs_profile_final_state_draft(self):
        extra_id=str(uuid.uuid4())
        extra=self.registration_sql(id=extra_id,country_id=self.de,tax_identifier='DE136695976',registration_type='DIRECT_IDENTIFICATION')
        self.reject('BEGIN;'+self.chain()+extra+'COMMIT;','almeno un profilo')
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+self.chain(tax_code='Ab/c international')+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT status||':'||version||':'||tax_code FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'DRAFT:1:Ab/c international')
        # Final registration contract applies equally to later additions.
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+extra+self.bump()+'COMMIT;', 'Nuova registrazione richiede almeno un profilo')
        regime=self.scalar(f"SELECT id FROM taxmanagement.tax_regimes WHERE country_id='{self.de}'")
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+extra+self.profile_sql(id=str(uuid.uuid4()),company_tax_registration_id=extra_id,tax_regime_id=regime)+self.bump()+'COMMIT;')

    def test_03_old_incomplete_root_grandfathered_cf_edit_clear_version_guard(self):
        rid=self.legacy_root
        self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.company_tax_configurations SET tax_code='Free form',version=version+1 WHERE id='{rid}';")
        self.assertEqual(self.scalar(f"SELECT tax_code FROM taxmanagement.company_tax_configurations WHERE id='{rid}'"),'Free form')
        self.reject(f"UPDATE taxmanagement.company_tax_configurations SET tax_code='stale' WHERE id='{rid}';",'esattamente di uno')
        self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.company_tax_configurations SET tax_code=NULL,version=version+1 WHERE id='{rid}';")
        self.assertEqual(self.scalar(f"SELECT count(*) FROM taxmanagement.company_tax_registrations WHERE company_tax_configuration_id='{rid}'"),'0')

    def test_04_cf_nullable_max500_nonblank_no_casefold_unique_or_checksum(self):
        for value in ('', ' \t\n', 'x'*501):
            self.reject('BEGIN;'+self.chain(tax_code=value)+'COMMIT;','company_tax_configurations_tax_code_check')
        self.sql('BEGIN;'+self.chain(tax_code='x'*500)+'COMMIT;')
        self.reject(f"UPDATE taxmanagement.company_tax_configurations SET establishment_country_id='{self.de}',version=version+1 WHERE id='{self.root}';",'Identita configurazione')

    def test_05_final_permission_security_and_fiscal_identity_columns(self):
        self.sql(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES('{self.tenant}','{CODE}','Metadata update',true);")
        self.assertEqual(self.scalar('SELECT count(*) FROM foundation.role_permission'),'0')
        self.assertEqual(self.scalar("SELECT has_function_privilege('enginia360_app','taxmanagement.require_company_tax_initial_chain()','EXECUTE')"),'f')
        self.reject('SET ROLE enginia360_app;UPDATE taxmanagement.tax_regimes SET is_active=false;','permission denied')
        self.reject('SET ROLE enginia360_app;SELECT * FROM foundation.audit_event;','permission denied')
        self.assertEqual(self.scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='foundation' AND table_name='company' AND column_name='tax_code'"),'0')
        self.assertEqual(self.scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='taxmanagement' AND table_name='company_tax_configurations' AND column_name='tax_code' AND data_type='text' AND is_nullable='YES'"),'1')
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('foundation','masterdata','taxmanagement') AND c.relkind='r'"),'65')


    def test_08_metadata_audit_failure_atomic_and_null_clear(self):
        self.sql('BEGIN;'+self.chain(tax_code='Original')+'COMMIT;')
        update=f"UPDATE taxmanagement.company_tax_configurations SET tax_code='Changed',version=version+1 WHERE id='{self.root}';"
        audit=f"INSERT INTO foundation.audit_event(actor_id,tenant_id,action,resource,record_id,details) VALUES('{self.actor}','{self.tenant}','update','company-tax-configurations','{self.root}','[]'::jsonb);"
        self.reject('BEGIN;SET LOCAL ROLE enginia360_app;'+update+audit+'COMMIT;','audit_event_details_check')
        self.assertEqual(self.scalar(f"SELECT tax_code||':'||version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'Original:1')
        self.sql('BEGIN;SET LOCAL ROLE enginia360_app;'+update+audit.replace("'[]'::jsonb","'{}'::jsonb")+'COMMIT;')
        self.assertEqual(self.scalar(f"SELECT tax_code||':'||version FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'Changed:2')
        self.sql(f"SET ROLE enginia360_app;UPDATE taxmanagement.company_tax_configurations SET tax_code=NULL,version=version+1 WHERE id='{self.root}' AND version=2;")
        self.assertEqual(self.scalar(f"SELECT tax_code IS NULL AND version=3 FROM taxmanagement.company_tax_configurations WHERE id='{self.root}'"),'t')

    def test_09_fresh_baseline_current_tax_code_column(self):
        from database.sql_source import load_foundation_sql
        db='fresh'+uuid.uuid4().hex[:12]
        self.sql('CREATE DATABASE '+db+';',database='postgres')
        self.sql(load_foundation_sql(),database=db)
        self.assertEqual(self.sql("SELECT count(*) FROM pg_attribute WHERE attrelid='taxmanagement.company_tax_configurations'::regclass AND attname='tax_code' AND NOT attisdropped;",database=db).stdout,'1\n')


if __name__=='__main__': unittest.main()
