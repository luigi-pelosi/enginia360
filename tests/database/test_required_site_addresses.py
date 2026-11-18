"""Campi indirizzo obbligatori: PostgreSQL isolato, nessuna scrittura persistente."""
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

from dbbaseline import CONTAINER, DATABASE, sql as baseline_sql
FIELDS=('address','city','province','postal_code','country_code')
BASE={'tax_code':'QA-SITE-TAX','address':'Via QA 1','city':'Città QA','province':'Provincia QA','postal_code':'00000','country_code':'IT'}
SETUP="BEGIN; INSERT INTO foundation.tenant(id,code,name) VALUES('94000000-0000-0000-0000-000000000001','required-proof','Prova obbligatorietà'); INSERT INTO foundation.company(id,tenant_id,name) VALUES('94000000-0000-0000-0000-000000000002','94000000-0000-0000-0000-000000000001','Azienda QA');"


def sql(statement):
    return baseline_sql(statement, check=False)


def literal(value):return 'NULL' if value is None else "'"+value.replace("'","''")+"'"


def fixture(values,patch=None):
    columns=','.join(values)
    data=','.join(literal(v) for v in values.values())
    insert="INSERT INTO foundation.site(tenant_id,company_id,name,"+columns+") VALUES('94000000-0000-0000-0000-000000000001','94000000-0000-0000-0000-000000000002','Sede QA',"+data+");"
    update='' if patch is None else 'UPDATE foundation.site SET '+','.join(k+'='+literal(v) for k,v in patch.items())+" WHERE tenant_id='94000000-0000-0000-0000-000000000001';"
    return sql(SETUP+insert+update+'ROLLBACK;')


class RequiredSiteAddressDatabaseTests(unittest.TestCase):
    def test_five_columns_are_not_nullable_and_blank_check_exists(self):
        result=sql("SELECT json_object_agg(attname,attnotnull) FROM pg_attribute WHERE attrelid='foundation.site'::regclass AND attname IN ('address','city','province','postal_code','country_code')")
        self.assertEqual(json.loads(result.stdout),dict.fromkeys(FIELDS,True))
        result=sql("SELECT count(*) FROM pg_constraint WHERE conrelid='foundation.site'::regclass AND conname='site_address_required_check'")
        self.assertEqual(result.stdout.strip(),'1')

    def test_direct_insert_and_update_cannot_omit_null_or_blank_required_fields(self):
        for name in FIELDS:
            missing={k:v for k,v in BASE.items() if k!=name}
            with self.subTest(field=name,value='omitted'):
                self.assertNotEqual(fixture(missing).returncode,0)
            for value in (None,'','   ','\t\n'):
                with self.subTest(field=name,value=value):
                    self.assertNotEqual(fixture({**BASE,name:value}).returncode,0)
                    self.assertNotEqual(fixture(BASE,{name:value}).returncode,0)

    def test_valid_manual_international_addresses_and_all_iso_codes_remain_admitted(self):
        for country,city,province,zip_code in [('IT','Capua','CE','81043'),('GB','London','Greater London','SW1A 1AA'),('US','New York','NY','10001')]:
            result=fixture({**BASE,'country_code':country,'city':city,'province':province,'postal_code':zip_code})
            self.assertEqual(result.returncode,0,result.stderr)
        codes=re.findall(r'"([A-Z]{2})"',(Path(__file__).resolve().parents[2] / 'backend/Modules/Geography/CountryCodes.cs').read_text())
        self.assertEqual(len(set(codes)),249)
        values=','.join("('94000000-0000-0000-0000-000000000001','94000000-0000-0000-0000-000000000002','QA','CF-QA','Via QA','Città QA','Provincia QA','00000','"+code+"')" for code in codes)
        result=sql(SETUP+'INSERT INTO foundation.site(tenant_id,company_id,name,tax_code,address,city,province,postal_code,country_code) VALUES '+values+';ROLLBACK;')
        self.assertEqual(result.returncode,0,result.stderr)
        result=fixture(BASE,{'name':'Modifica parziale'})
        self.assertEqual(result.returncode,0,result.stderr)

    def test_alternative_tax_identity_and_iso_restriction_still_apply(self):
        for values in ({**BASE,'tax_code':None},{**BASE,'country_code':'ZZ'},{**BASE,'country_code':'it'}):
            self.assertNotEqual(fixture(values).returncode,0)
        result=fixture({**BASE,'tax_code':None,'vat_number':'QA-VAT'})
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
