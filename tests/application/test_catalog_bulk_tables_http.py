"""Metadati aziendali minimi per la selezione massiva del Catalogo."""
from test_catalog_companies_http import CatalogCompaniesHttp
from catalog_items_helpers import fixture_sql

HTTP_CASES=('test_legal_address_uses_first_active_legal_site_and_exact_company_scope',)
class CatalogBulkTablesHttp(CatalogCompaniesHttp):
    def site(self,company,site_type,address,enabled=True):
        return self.data_create('sites',{'company_id':company['id'],'name':address,'site_type':site_type,'address':address,'city':'Roma','province':'RM','postal_code':'00100','country_code':'IT','is_enabled':enabled})
    def options(self,client=None):
        status,body=(client or self.root).request(self.path('item-companies','options'));self.assertEqual(status,200,body);return {row['id']:row for row in body['items']}
    def test_legal_address_uses_first_active_legal_site_and_exact_company_scope(self):
        self.site(self.a,'LEGAL','Sede legale disabilitata',False);self.site(self.a,'LOCAL_UNIT','Solo operativa')
        first=self.site(self.a,'LEGAL','Via Legale 1');self.site(self.a,'LEGAL','Via Legale 2')
        self.site(self.b,'SECONDARY','Nessuna sede legale')
        before=fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}'")
        result=self.options();self.assertIn('legal_address',result[self.a['id']]);self.assertEqual(result[self.a['id']]['legal_address'],{'address':first['address'],'city':'Roma','province':'RM','postal_code':'00100','country_code':'IT'})
        self.assertIsNone(result[self.b['id']]['legal_address'])
        self.assertEqual(fixture_sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.tenant_id}'"),before)
        actor,_,_=self.scoped_actor(['catalog-item-companies.read','catalog-item-companies.create'],[self.a]);scoped=self.options(actor);self.assertEqual(set(scoped),{self.a['id']});self.assertEqual(scoped[self.a['id']]['legal_address'],result[self.a['id']]['legal_address'])
        status,_=actor.request('/api/data/sites?tenantId='+self.tenant_id);self.assertEqual(status,403)
