"""Sedi fisiche senza identità fiscale e paesi ISO: transazioni annullate."""
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
    def test_site_has_no_fiscal_identity_and_can_be_created_without_it(self):
        r=fixture();self.assertEqual(r.returncode,0,r.stderr)
        for column in ('vat_number','tax_code'):
            with self.subTest(column=column):
                r=fixture(column,"'obsolete'");self.assertNotEqual(r.returncode,0)
                self.assertIn('does not exist',r.stderr)

    def test_country_codes_are_required_and_only_official_uppercase_alpha2(self):
        for code in ('ZZ','UK','XX','it'):
            with self.subTest(invalid=code):
                r=fixture('country_code',"'"+code+"'");self.assertNotEqual(r.returncode,0)
                self.assertIn('site_country_code_check',r.stderr)
        for code in ('IT','US','JP','GB','BQ','VA','AX'):
            literal='NULL' if code is None else "'"+code+"'"
            r=fixture('country_code',literal);self.assertEqual(r.returncode,0,r.stderr)
        self.assertNotEqual(fixture('country_code','NULL').returncode,0)

    def test_all_iso_country_codes_in_metadata_snapshot_are_admitted(self):
        codes=re.findall(r'"([A-Z]{2})"',(Path(__file__).resolve().parents[2] / 'backend/Modules/Geography/CountryCodes.cs').read_text())
        self.assertEqual(len(codes),249);self.assertEqual(len(set(codes)),249)
        # Lo stesso tenant sintetico e rollback, un solo round trip per il catalogo completo.
        r=fixture('country_code',"'IT'")
        self.assertEqual(r.returncode,0,r.stderr)
        base="BEGIN;INSERT INTO foundation.tenant(id,code,name) VALUES('93000000-0000-0000-0000-000000000001','iso-proof','Prova ISO');INSERT INTO foundation.company(id,tenant_id,name) VALUES('93000000-0000-0000-0000-000000000002','93000000-0000-0000-0000-000000000001','Azienda ISO');"
        rows=','.join("('93000000-0000-0000-0000-000000000001','93000000-0000-0000-0000-000000000002','Sede "+c+"','"+c+"','Via prova','Roma','RM','00100')" for c in codes)
        r=sql(base+'INSERT INTO foundation.site(tenant_id,company_id,name,country_code,address,city,province,postal_code) VALUES '+rows+';ROLLBACK;')
        self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
