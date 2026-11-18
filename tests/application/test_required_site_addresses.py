"""Indirizzo obbligatorio: entrambe le CRUD reali nella copia isolata."""
import json
import unittest
from unified_save_support import Case, root_client, sql

FIELDS=('address','city','province','postal_code','country_code')
ADDRESS={'address':'1 QA Street','city':'London','province':'Greater London','postal_code':'SW1A 1AA','country_code':'GB'}


class RequiredSiteAddressesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()
    def setUp(self):
        self.case=Case(self.root);self.company=self.case.create('companies',{'name':'Azienda QA'})
        self.valid={'company_id':self.company['id'],'name':'Sede QA','tax_code':'QA-TAX',**ADDRESS}
    def tearDown(self):self.case.close()
    def body(self,values,save):return {'values':values} if save else values
    def row(self,id):return sql(f"SELECT row_to_json(t) FROM foundation.site t WHERE id='{id}'").stdout.strip()
    def count(self,table):return sql(f"SELECT count(*) FROM foundation.{table} WHERE tenant_id='{self.case.tenant['id']}'"+(' AND resource=\'sites\'' if table=='audit_event' else '')).stdout.strip()

    def test_metadata_requires_five_fields_keeps_iso_and_code_position(self):
        status,resources=self.root.request('/api/resources');self.assertEqual(status,200)
        fields=next(r['fields'] for r in resources if r['key']=='sites');metadata={f['name']:f for f in fields}
        self.assertEqual({key:metadata[key]['required'] for key in FIELDS},dict.fromkeys(FIELDS,True))
        self.assertFalse(metadata['vat_number']['required']);self.assertFalse(metadata['tax_code']['required'])
        self.assertEqual(len(set(metadata['country_code']['options'])),249)
        names=[f['name'] for f in fields];self.assertEqual(names[names.index('name')+1],'code');self.assertFalse(metadata['code']['required'])

    def test_create_omitted_null_blank_whitespace_rejected_atomically_on_both_routes(self):
        initial=(self.count('site'),self.count('audit_event'))
        for save in (False,True):
            for field in FIELDS:
                for kind,value in [('omitted',None),('null',None),('empty',''),('space','   '),('whitespace','\t\n')]:
                    with self.subTest(save=save,field=field,kind=kind):
                        values={**self.valid}
                        if kind=='omitted':values.pop(field)
                        else:values[field]=value
                        status,_=self.root.request(self.case.path('sites',save=save),'POST',self.body(values,save))
                        self.assertEqual(status,400)
        self.assertEqual((self.count('site'),self.count('audit_event')),initial)

    def test_partial_updates_preserve_omitted_fields_and_invalid_patch_rolls_back(self):
        for save in (False,True):
            status,row=self.root.request(self.case.path('sites',save=save),'POST',self.body(self.valid,save));self.assertEqual(status,201,row)
            status,updated=self.root.request(self.case.path('sites',row['id'],save=save),'PUT',self.body({'name':'Nome aggiornato','is_enabled':False},save))
            self.assertEqual(status,200);self.assertFalse(updated['is_enabled']);self.assertEqual({f:updated[f] for f in FIELDS},ADDRESS)
            before=self.row(row['id']);audit=self.count('audit_event')
            for field in FIELDS:
                for value in (None,'','  ','\t\n'):
                    with self.subTest(save=save,field=field,value=value):
                        status,_=self.root.request(self.case.path('sites',row['id'],save=save),'PUT',self.body({field:value,'name':'Non salvare'},save))
                        self.assertEqual(status,400)
            self.assertEqual(self.row(row['id']),before);self.assertEqual(self.count('audit_event'),audit)

    def test_fiscal_alternative_is_unchanged_and_no_geographic_values_are_invented(self):
        status,error=self.root.request(self.case.path('sites',save=True),'POST',{'values':{**self.valid,'tax_code':None}})
        self.assertEqual(status,400);self.assertEqual(error['code'],'tax_identity_required')
        status,row=self.root.request(self.case.path('sites',save=True),'POST',{'values':{**self.valid,'tax_code':None,'vat_number':'QA-VAT'}})
        self.assertEqual(status,201);self.assertEqual({f:row[f] for f in FIELDS},ADDRESS);self.assertIsNone(row['code'])
        status,row=self.root.request(self.case.path('sites',row['id'],save=True),'PUT',{'values':{'vat_number':None,'tax_code':'QA-TAX'}})
        self.assertEqual(status,200);self.assertIsNone(row['vat_number'])

    def test_direct_fixture_consumers_produce_explicit_complete_synthetic_sites(self):
        row=self.case.create('sites',{'company_id':self.company['id'],'name':'Sede fixture'})
        self.assertTrue(all(row[f] for f in FIELDS));self.assertEqual(row['country_code'],'IT')

if __name__=='__main__':unittest.main(verbosity=2)
