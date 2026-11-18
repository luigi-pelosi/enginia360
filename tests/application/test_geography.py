"""Cataloghi globali e fallback geografico locale, esclusivamente su copia isolata."""
import unittest
from unified_save_support import Case,root_client,sql

class GeographyApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.root,_=root_client()
 def setUp(self):
  sql('DELETE FROM foundation.login_limit;');self.case=Case(self.root);self.actor,self.user,_,_=self.case.actor(['sites.create'])
 def tearDown(self):self.case.close()
 def test_countries_are_global_and_readable_without_tenant(self):
  status,data=self.actor.request('/api/data/countries');self.assertEqual(status,200,data);self.assertIn('items',data)
  self.assertEqual(self.root.request('/api/data/countries')[0],200)
  metadata=self.actor.request('/api/resources')[1];self.assertTrue(next(r for r in metadata if r['key']=='countries')['readOnly'])
  self.assertEqual(self.actor.request('/api/data/countries','POST',{'name':'Nazione non autorizzata','iso_code':'ES'})[0],403)
 def test_missing_geoapify_uses_local_catalog_instead_of_configuration_error(self):
  status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Capua&countryCode=IT');self.assertEqual(status,200,data);self.assertIn('items',data);self.assertEqual(data['attribution'],'')

 def test_city_search_can_change_province_without_manually_clearing_old_context(self):
  status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Capua&countryCode=IT&province=SS');self.assertEqual(status,200);self.assertTrue(any(x['city']=='Capua' and x['province']=='CE' for x in data['items']),'La provincia precedente non deve impedire la scelta di una nuova città')

 def test_local_search_matches_common_italian_accentless_input(self):
  status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Forli&countryCode=IT');self.assertEqual(status,200);self.assertTrue(any(x['city']=='Forlì' for x in data['items']),'Forli deve trovare Forlì')

 def test_import_covers_all_municipalities_and_preserves_leading_zero_cap(self):
  stats=sql("SELECT count(*),count(DISTINCT istat_code) FROM foundation.city WHERE istat_code IS NOT NULL;").stdout.strip();self.assertEqual(stats,'8458|7894')
  status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Alghero&countryCode=IT');self.assertEqual(status,200);city=next(x for x in data['items'] if x['city']=='Alghero');self.assertEqual((city['postalCode'],city['province'],city['region'],city['countryCode']),('07041','SS','Sardegna','IT'))
  status,data=self.actor.request('/api/addresses/countries');self.assertEqual(status,200);self.assertEqual(data['provider'],'catalog');self.assertEqual(data['items'],[{'isoCode':'IT','name':'Italia'}])
 def test_global_catalog_can_only_be_maintained_by_global_super_admin(self):
  status,country=self.root.request('/api/data/countries','POST',{'name':'Spagna QA','iso_code':'ES'});self.assertEqual(status,201,country);city=None
  try:
   status,city=self.root.request('/api/data/cities/save','POST',{'values':{'name':'Città QA','postal_code':'28001','province':'M','region':'Madrid','country_id':country['id']}});self.assertEqual(status,201,city)
   self.assertNotIn('tenant_id',city);self.assertNotIn('tenant_id',country)
   self.assertEqual(self.actor.request('/api/data/cities/'+city['id'],'PUT',{'name':'Non autorizzata'})[0],403)
   self.assertEqual(self.actor.request('/api/data/cities/'+city['id'],'DELETE')[0],403)
   admin,_,_,_=self.case.actor(list(self.case.catalog));self.assertEqual(admin.request('/api/data/countries/'+country['id'],'PUT',{'name':'Non autorizzata'})[0],403)
   status,updated=self.root.request('/api/data/cities/'+city['id']+'/save','PUT',{'values':{'name':'Città QA aggiornata','notes':'Nota manuale'}});self.assertEqual(status,200,updated);self.assertEqual(updated['name'],'Città QA aggiornata')
   self.assertEqual(self.root.request('/api/data/countries/'+country['id'],'DELETE')[0],409)
   status,data=self.actor.request('/api/data/cities?search=28001');self.assertEqual(status,200);self.assertTrue(any(x['id']==city['id'] for x in data['items']))
  finally:
   if city and 'id' in city:self.root.request('/api/data/cities/'+city['id'],'DELETE')
   self.root.request('/api/data/countries/'+country['id'],'DELETE')
 def test_global_reference_lookup_is_same_across_tenants_and_ordinary_users_have_read_only_metadata(self):
  first=self.actor.request('/api/data/countries')[1]
  second=self.root.request('/api/data/countries?tenantId='+self.case.tenant['id'])[1];self.assertEqual(first['items'],second['items'])
  self.assertEqual(sql("SELECT count(*) FROM information_schema.columns WHERE table_schema='foundation' AND table_name IN('country','city') AND column_name='tenant_id';").stdout.strip(),'0')
  self.assertEqual(len(self.case.catalog),50)
 def test_inactive_city_does_not_appear_in_local_suggestions(self):
  row=self.root.request('/api/data/cities?search=Alghero')[1]['items'][0]
  try:
   self.assertEqual(self.root.request('/api/data/cities/'+row['id'],'PUT',{'is_enabled':False})[0],200)
   status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Alghero&countryCode=IT');self.assertEqual(status,200);self.assertFalse(any(x['city']=='Alghero' for x in data['items']))
  finally:self.root.request('/api/data/cities/'+row['id'],'PUT',{'is_enabled':True})
 def test_provider_configuration_is_no_longer_available(self):
  path='/api/settings/geoapify?tenantId='+self.case.tenant['id']
  self.assertEqual(self.root.request(path)[0],404)
  self.assertEqual(self.root.request(path,'POST',{'apiKey':'unused-provider-key','isEnabled':True})[0],404)
  status,data=self.actor.request('/api/addresses/countries');self.assertEqual(status,200);self.assertEqual(data['provider'],'catalog')

 def test_global_catalog_writes_require_csrf_and_preserve_data_on_rejection(self):
  count=sql('SELECT count(*) FROM foundation.country;').stdout
  self.assertEqual(self.root.request('/api/data/countries','POST',{'name':'Non salvare','iso_code':'ES'},csrf=False)[0],400)
  self.assertEqual(self.root.request('/api/data/countries','POST',{'name':'Non salvare','iso_code':'ES'},origin='https://untrusted.example.invalid')[0],403)
  self.assertEqual(sql('SELECT count(*) FROM foundation.country;').stdout,count)
 def test_global_city_audit_failure_rolls_back_record_and_audit(self):
  row=self.root.request('/api/data/cities?search=Alghero')[1]['items'][0];before=sql("SELECT row_to_json(t) FROM foundation.city t WHERE id='"+row['id']+"';").stdout
  audit=sql('SELECT count(*) FROM foundation.audit_event;').stdout
  sql("CREATE FUNCTION foundation.qa_city_audit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'QA city audit failure'; END $$; CREATE CONSTRAINT TRIGGER qa_city_audit_failure AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW WHEN (NEW.record_id='"+row['id']+"'::uuid AND NEW.resource='cities') EXECUTE FUNCTION foundation.qa_city_audit_failure();")
  try:
   status,_=self.root.request('/api/data/cities/'+row['id']+'/save','PUT',{'values':{'notes':'Non salvare'}});self.assertGreaterEqual(status,400)
   self.assertTrue(sql("SELECT row_to_json(t) FROM foundation.city t WHERE id='"+row['id']+"';").stdout==before);self.assertEqual(sql('SELECT count(*) FROM foundation.audit_event;').stdout,audit)
  finally:sql('DROP TRIGGER qa_city_audit_failure ON foundation.audit_event; DROP FUNCTION foundation.qa_city_audit_failure();')

if __name__=='__main__':unittest.main(verbosity=2)
