"""Nullable business codes: prove dello schema sul solo cluster optional-code."""
import json
import subprocess
import unittest
import uuid

from dbbaseline import CONTAINER, SITE_ADDRESS, sql as execute
TABLES=('company','site','warehouse_type','warehouse','warehouse_location','user_group','role')


class OptionalCodeSchemaTests(unittest.TestCase):
    def test_business_codes_are_nullable_without_weakening_technical_codes(self):
        rows=json.loads(execute("SELECT json_object_agg(table_name,is_nullable) FROM information_schema.columns WHERE table_schema='foundation' AND column_name='code'").stdout)
        for table in TABLES:
            with self.subTest(table=table):self.assertEqual(rows[table],'YES','Il codice anagrafico deve accettare NULL')
        self.assertEqual(rows['tenant'],'NO')
        self.assertEqual(rows['permission'],'NO')

    def test_multiple_null_codes_are_allowed_under_the_same_parent(self):
        tenant,company,site,kind,warehouse=[str(uuid.uuid4()) for _ in range(5)]
        statements=[f"INSERT INTO foundation.tenant(id,code,name) VALUES('{tenant}','proof-{tenant}','Verifica schema');"]
        values={
            'company':({'tenant_id':tenant},company),
            'site':({'tenant_id':tenant,'company_id':company,**SITE_ADDRESS},site),
            'warehouse_type':({'tenant_id':tenant},kind),
            'warehouse':({'tenant_id':tenant,'site_id':site,'warehouse_type_id':kind},warehouse),
            'warehouse_location':({'tenant_id':tenant,'warehouse_id':warehouse},str(uuid.uuid4())),
            'user_group':({'tenant_id':tenant},str(uuid.uuid4())),
            'role':({'tenant_id':tenant},str(uuid.uuid4())),
        }
        for table,(refs,record_id) in values.items():
            for position in range(2):
                body={'id':record_id if position==0 else str(uuid.uuid4()),**refs,'name':'Senza codice '+str(position)}
                statements.append('INSERT INTO foundation.'+table+'('+','.join(body)+') VALUES('+','.join("'"+value+"'" for value in body.values())+');')
        result=execute('BEGIN;\n'+'\n'.join(statements)+'\nROLLBACK;',role='enginia360_app',check=False)
        self.assertEqual(result.returncode,0,'Il ruolo applicativo deve poter salvare più righe senza codice nello stesso ambito: '+result.stderr)

    def test_populated_code_unique_scope_and_empty_string_checks_are_preserved(self):
        for invalid,expected in [("INSERT INTO foundation.company(tenant_id,name,code) VALUES('{tenant}','Seconda','same');",'23505'),
                                 ("INSERT INTO foundation.company(tenant_id,name,code) VALUES('{tenant}','Seconda','');",'23514')]:
            tenant=str(uuid.uuid4())
            statement=f"BEGIN; INSERT INTO foundation.tenant(id,code,name) VALUES('{tenant}','proof-{tenant}','Schema'); "
            statement+=f"INSERT INTO foundation.company(tenant_id,name,code) VALUES('{tenant}','Prima','same'); "
            result=execute(statement+invalid.format(tenant=tenant)+' ROLLBACK;',role='enginia360_app',check=False)
            self.assertNotEqual(result.returncode,0)
            self.assertIn(expected,result.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
