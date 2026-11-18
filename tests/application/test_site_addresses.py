"""Indirizzi fiscali e catalogo geografico locale: API reale nella copia isolata."""
import json
import unittest
from urllib.parse import urlencode
from unified_save_support import Case, Client, root_client, sql
from test_required_site_addresses import ADDRESS


class SiteAddressesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.root,cls.credentials=root_client()
    def setUp(self):
        self.case=Case(self.root)
        self.company=self.case.create('companies',{'name':'Azienda indirizzi'})
    def tearDown(self):self.case.close()
    def autocomplete(self,**kwargs):
        return '/api/addresses/autocomplete?'+urlencode({'tenantId':self.case.tenant['id'],'field':'city','text':'Capua','language':'it',**kwargs})
    def create_site(self,**values):
        status,row=self.root.request(self.case.path('sites',save=True),'POST',{'values':{'company_id':self.company['id'],'name':'Sede indirizzi','tax_code':'CF-test',**ADDRESS,**values}})
        self.assertEqual(status,201,row);return row
    def site(self,row):return json.loads(sql(f"SELECT row_to_json(t) FROM foundation.site t WHERE id='{row['id']}'").stdout)

    def test_metadata_places_code_after_name_and_supplies_all_iso_countries(self):
        status,resources=self.root.request('/api/resources');self.assertEqual(status,200)
        fields=next(r['fields'] for r in resources if r['key']=='sites')
        names=[f['name'] for f in fields];self.assertEqual(names[names.index('name')+1],'code')
        country=next(f for f in fields if f['name']=='country_code')
        self.assertEqual(country['type'],'select');self.assertEqual(len(country['options']),249)
        self.assertEqual(len(set(country['options'])),249);self.assertIn('IT',country['options']);self.assertIn('BQ',country['options']);self.assertNotIn('ZZ',country['options'])
        self.assertTrue(all(next(f for f in fields if f['name']==name)['required'] for name in ('address','city','province','postal_code','country_code')))

    def test_tax_identity_is_alternative_and_updates_merge_existing_values(self):
        status,error=self.root.request(self.case.path('sites',save=True),'POST',{'values':{'company_id':self.company['id'],'name':'Non valida',**ADDRESS}})
        self.assertEqual(status,400);self.assertEqual(error['code'],'tax_identity_required')
        row=self.create_site(tax_code=None,vat_number='  VAT-test  ')
        self.assertEqual(row['vat_number'],'VAT-test');self.assertIsNone(row['tax_code'])
        status,updated=self.root.request(self.case.path('sites',row['id'],save=True),'PUT',{'values':{'city':'Capua'}})
        self.assertEqual(status,200);self.assertEqual(updated['vat_number'],'VAT-test')
        before=self.site(row)
        status,error=self.root.request(self.case.path('sites',row['id'],save=True),'PUT',{'values':{'vat_number':' \t ','tax_code':None,'name':'Non salvare'}})
        self.assertEqual(status,400);self.assertEqual(error['code'],'tax_identity_required');self.assertEqual(self.site(row),before)
        status,updated=self.root.request(self.case.path('sites',row['id'],save=True),'PUT',{'values':{'vat_number':None,'tax_code':' CF-test '}})
        self.assertEqual(status,200);self.assertIsNone(updated['vat_number']);self.assertEqual(updated['tax_code'],'CF-test')

    def test_country_validation_and_legacy_crud_share_constraints(self):
        row=self.create_site(country_code='IT');before=self.site(row)
        for value in ('ZZ','UK','it','ITA'):
            status,_=self.root.request(self.case.path('sites',row['id']),'PUT',{'country_code':value})
            self.assertEqual(status,400);self.assertEqual(self.site(row),before)
        status,_=self.root.request(self.case.path('sites',row['id']),'PUT',{'country_code':None})
        self.assertEqual(status,400);self.assertEqual(self.site(row),before)

    def test_local_lookup_requires_authentication_and_site_write_permission(self):
        countries='/api/addresses/countries?'+urlencode({'tenantId':self.case.tenant['id']})
        reader,_,_,_=self.case.actor(['sites.read','settings.read'])
        creator,_,_,_=self.case.actor(['sites.create'])
        updater,_,_,_=self.case.actor(['sites.update'])
        for path in (self.autocomplete(),countries):
            with self.subTest(path=path):
                self.assertEqual(Client().request(path)[0],401)
                self.assertEqual(reader.request(path)[0],403)
                self.assertEqual(creator.request(path)[0],200)
                self.assertEqual(updater.request(path)[0],200)

    def test_local_catalog_completes_capua_and_alghero_without_street_or_attribution(self):
        for city,postal,province,region in [('Capua','81043','CE','Campania'),('Alghero','07041','SS','Sardegna')]:
            for field,text,context in [('city',city,{'province':'Provincia precedente'}),('postal_code',postal,{'city':city,'province':province}),('province',region,{'city':city})]:
                with self.subTest(city=city,field=field):
                    status,data=self.root.request(self.autocomplete(field=field,text=text,countryCode='IT',**context))
                    self.assertEqual(status,200,data);self.assertEqual(data['attribution'],'');self.assertLessEqual(len(data['items']),5)
                    self.assertTrue(all(item['countryCode']=='IT' for item in data['items']))
                    item=next(item for item in data['items'] if item['city']==city)
                    self.assertEqual((item['postalCode'],item['province'],item['region'],item['countryCode'],item['address']),(postal,province,region,'IT',''))
        status,data=self.root.request(self.autocomplete(text='Alghero',countryCode='GB'))
        self.assertEqual(status,200);self.assertEqual(data,{'items':[],'attribution':''})

    def test_street_is_manual_and_unknown_local_search_is_empty_without_writes(self):
        row=self.create_site();before=self.site(row)
        for field,text in [('address','Via Appia Capua'),('city','Località inesistente QA')]:
            with self.subTest(field=field):
                status,data=self.root.request(self.autocomplete(field=field,text=text,countryCode='IT'))
                self.assertEqual(status,200,data);self.assertEqual(data,{'items':[],'attribution':''})
        self.assertEqual(self.site(row),before)

    def test_lookup_rejects_invalid_queries(self):
        for query in ({'field':'region'},{'text':'Ca'},{'countryCode':'ZZ'},{'language':'fr'},{'text':'x'*201},{'extra':'unknown'}):
            with self.subTest(query=query):self.assertEqual(self.root.request(self.autocomplete(**query))[0],400)


if __name__=='__main__':unittest.main(verbosity=2)
