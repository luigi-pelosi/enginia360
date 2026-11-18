"""Vincoli fiscali e paesi ISO: copie isolate, transazioni annullate."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

from dbbaseline import CONTAINER, DATABASE, sql as baseline_sql


def sql(statement):
    return baseline_sql(statement, check=False)


def fixture(columns='',values=''):
    extra=','+columns if columns else ''
    data=','+values if values else ''
    return sql("BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('92000000-0000-0000-0000-000000000001','address-proof','Prova indirizzi');"
        "INSERT INTO foundation.company(id,tenant_id,name) VALUES('92000000-0000-0000-0000-000000000002','92000000-0000-0000-0000-000000000001','Azienda prova');"
        'INSERT INTO foundation.site(tenant_id,company_id,name,address,city,province,postal_code'+('' if 'country_code' in columns else ',country_code')+extra+") VALUES('92000000-0000-0000-0000-000000000001','92000000-0000-0000-0000-000000000002','Sede prova','Via prova','Roma','RM','00100'"+('' if 'country_code' in columns else ",'IT'")+data+');ROLLBACK;')


class SiteAddressesDatabaseTests(unittest.TestCase):
    def test_tax_identity_requires_at_least_one_nonblank_value(self):
        for columns,values in [('', ''),('vat_number,tax_code','NULL,NULL'),('vat_number,tax_code',"'   ',E'\\t\\n'")]:
            with self.subTest(values=values):
                r=fixture(columns,values);self.assertNotEqual(r.returncode,0)
                self.assertIn('site_tax_identity_check',r.stderr)
        for values in ("'IT-test',NULL","NULL,'CF-test'","'IT-test','CF-test'"):
            with self.subTest(valid=values):
                r=fixture('vat_number,tax_code',values);self.assertEqual(r.returncode,0,r.stderr)

    def test_country_codes_are_required_and_only_official_uppercase_alpha2(self):
        for code in ('ZZ','UK','XX','it'):
            with self.subTest(invalid=code):
                r=fixture('tax_code,country_code',"'CF-test','"+code+"'");self.assertNotEqual(r.returncode,0)
                self.assertIn('site_country_code_check',r.stderr)
        for code in ('IT','US','JP','GB','BQ','VA','AX'):
            literal='NULL' if code is None else "'"+code+"'"
            r=fixture('tax_code,country_code',"'CF-test',"+literal);self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotEqual(fixture('tax_code,country_code',"'CF-test',NULL").returncode,0)

    def test_all_iso_country_codes_in_metadata_snapshot_are_admitted(self):
        codes=re.findall(r'"([A-Z]{2})"',(Path(__file__).resolve().parents[2] / 'backend/Modules/Geography/CountryCodes.cs').read_text())
        self.assertEqual(len(codes),249);self.assertEqual(len(set(codes)),249)
        # Lo stesso tenant sintetico e rollback, un solo round trip per il catalogo completo.
        r=fixture('tax_code,country_code',"'CF-test','IT'")
        self.assertEqual(r.returncode,0,r.stderr)
        base="BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('93000000-0000-0000-0000-000000000001','iso-proof','Prova ISO');INSERT INTO foundation.company(id,tenant_id,name) VALUES('93000000-0000-0000-0000-000000000002','93000000-0000-0000-0000-000000000001','Azienda ISO');"
        rows=','.join("('93000000-0000-0000-0000-000000000001','93000000-0000-0000-0000-000000000002','Sede "+c+"','CF-test','"+c+"','Via prova','Roma','RM','00100')" for c in codes)
        r=sql(base+'INSERT INTO foundation.site(tenant_id,company_id,name,tax_code,country_code,address,city,province,postal_code) VALUES '+rows+';ROLLBACK;')
        self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
