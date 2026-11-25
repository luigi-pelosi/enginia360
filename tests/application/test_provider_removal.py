"""Dismissione del provider e geografia locale su copia isolata."""
import unittest
from unified_save_support import root_client, Case, sql

class ProviderRemovalTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.root,_=root_client()
 def setUp(self):
  sql('DELETE FROM foundation.login_limit;')
  self.case=Case(self.root)
  self.actor,_,_,_=self.case.actor(['sites.create'])
 def tearDown(self): self.case.close()
 def test_provider_settings_route_is_removed(self):
  for method in ('GET','POST','PUT','DELETE'):
   status,_=self.root.request('/api/settings/geoapify?tenantId='+self.case.tenant['id'],method,{} if method in ('POST','PUT') else None)
   self.assertEqual(status,404,method)
 def test_only_enabled_catalog_countries_are_available(self):
  status,data=self.actor.request('/api/addresses/countries')
  self.assertEqual(status,200)
  self.assertEqual(data['provider'],'catalog')
  self.assertEqual(data['items'],[{'isoCode':'IT','name':'Italia'}])
 def test_local_selection_returns_complete_city_without_provider_attribution(self):
  status,data=self.actor.request('/api/addresses/autocomplete?field=city&text=Alghero&countryCode=IT')
  self.assertEqual(status,200)
  item=next(x for x in data['items'] if x['city']=='Alghero')
  self.assertEqual((item['postalCode'],item['province'],item['region'],item['countryCode']),('07041','SS','Sardegna','IT'))
  self.assertEqual(data['attribution'],'')
 def test_provider_setting_is_removed_from_storage(self):
  self.assertEqual(sql("SELECT to_regclass('foundation.setting') IS NULL;").stdout.strip(),'t')

if __name__=='__main__':unittest.main()
