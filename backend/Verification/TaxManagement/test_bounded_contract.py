"""Focused integration-wiring regressions; runtime proof is separate."""
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[2] / 'Modules' / 'TaxManagement'

class BoundedContract(unittest.TestCase):
    def test_template_scope_matches_identity(self):
        source = (MODULE / 'TaxEndpoints.cs').read_text()
        self.assertIn('WHERE tenant_id=@t AND country_id=@country AND tax_type_id=@type AND lower(code)=lower(@code)', source)

    def test_code_lookups_are_separate_and_complete(self):
        source = (MODULE / 'TaxEndpoints.cs').read_text()
        self.assertIn('app.MapGet("/api/tax/lookups",Lookups)', source)
        lookup = source.split('Task<IResult> Lookups(', 1)[-1].split('Task<IResult> Types(', 1)[0]
        for permission in ['tax-codes.read', 'tax-codes.create', 'tax-codes.update', 'tax-codes.schedule']:
            self.assertIn(permission, lookup)
        self.assertIn('new {countries,types,natureCodes}', lookup)
        self.assertIn('tax_lookup_limit_exceeded', source)
        self.assertIn('LIMIT 10001', source)
        self.assertNotIn('tax-types.read', lookup)
        self.assertNotIn('tax-nature-codes.read', lookup)

    def test_audit_does_not_repeat_aggregate(self):
        source = (MODULE / 'TaxEndpoints.cs').read_text()
        update = source.split('Task<IResult> Update(', 1)[1].split('Task<IResult> Schedule(', 1)[0]
        schedule = source.split('Task<IResult> Schedule(', 1)[1].split('Task<IResult> SetActive(', 1)[0]
        self.assertIn('TaxAuditChanges.Metadata(before,after)', update)
        self.assertIn('predecessor', schedule)
        self.assertNotIn('new {expectedVersion=root["version"],before,after}', schedule)

if __name__ == '__main__':
    unittest.main()
