"""Focused source-contract checks; real HTTP/RBAC proof belongs to the integration runner."""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'Modules/BusinessPartners/BusinessPartnerCompanyEndpoints.cs'


class BusinessPartnerCompanyListingSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = SOURCE.read_text()
        self.listing = self.source.split('private static async Task<IResult> List(', 1)[1].split('private static async Task<Guid> Gate(', 1)[0]

    def test_all_company_route_reuses_list_without_a_requested_company(self):
        self.assertRegex(self.source, r'app\.MapGet\("/api/business-partner-companies",\s*\(HttpContext ctx,AppDb db\)=>List\(ctx,db,null\)\)')
        self.assertIn('Guid? companyId)', self.listing)

    def test_requested_company_keeps_explicit_gate(self):
        self.assertIn('app.MapGet("/api/companies/{companyId:guid}/business-partners"', self.source)
        self.assertRegex(self.listing, r'companyId\.HasValue\s*\?\s*await Gate\(ctx,db,companyId\.Value,"read"\)')

    def test_read_scope_filters_both_count_and_items(self):
        self.assertIn('await Security.Authorize(ctx,"business-partners.read")', self.listing)
        self.assertIn('await Security.Authorize(ctx,"business-partner-companies.read")', self.listing)
        self.assertRegex(self.listing, r'grants\.Where\(x=>x\.Value\.Contains\("read"\)\)\.Select\(x=>x\.Key\)\.ToArray\(\)')
        self.assertIn('cbp.company_id=ANY(@ids::uuid[])', self.listing)
        self.assertIn('("ids",ids)', self.listing)
        self.assertIn('BusinessPartnerEligibility.Joins+" WHERE "+where', self.listing)
        self.assertIn('Query(db,grants,where+', self.listing)

    def test_shared_parser_defaults_projection_and_order_remain(self):
        self.assertIn('values.Count<=1', self.source)
        self.assertIn('var role=Parameter(ctx,"role")', self.listing)
        self.assertIn('var usable=usableText=="true"', self.listing)
        self.assertIn('Number("page",1,100000)', self.listing)
        self.assertIn('Number("pageSize",25,100)', self.listing)
        self.assertIn('ORDER BY cbp.created_at,cbp.id LIMIT @size OFFSET @offset', self.listing)
        self.assertIn("'company_name',c.name", self.source)
        self.assertIn('return Results.Ok(new{items,total,page,pageSize})', self.listing)


if __name__ == '__main__':
    unittest.main(verbosity=2)
