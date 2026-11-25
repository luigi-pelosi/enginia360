"""Narrow structural guards supplement the native/runtime behavioral proof."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class RoleUnifiedSaveSourceTests(unittest.TestCase):
    def test_company_contract_is_role_only_and_preflight_precedes_dml(self):
        source = (ROOT / 'backend/Api/Resources/DataEndpoints.cs').read_text()
        save = source.split('private static async Task<IResult> Save(', 1)[1].split('private static long ParseVersion', 1)[0]
        self.assertIn('if(name=="companyIds")', save)
        self.assertIn('Check.Require(resource=="roles")', save)
        self.assertIn('RoleCompanyEndpoints.Parse(prop.Value)', save)
        for check in ['await Security.Authorize(ctx,"roles.assign_companies")',
                      'await Resources.EnsureRow(db,r,ownerId.Value,tenant)',
                      'await RoleCompanyEndpoints.Validate(db,tenant!.Value,companyIds)',
                      'Resources.Get(Resources.Links[name].TargetResource)']:
            self.assertLess(save.index(check), save.index('after=await Create('))
        self.assertIn('if(companyIds!=null) await RoleCompanyEndpoints.Replace(', save)
        self.assertIn('Results.Ok(new {id=ownerId.Value})', save)

    def test_compatibility_put_uses_the_same_company_primitive(self):
        source = (ROOT / 'backend/Modules/AccessControl/RoleCompanyEndpoints.cs').read_text()
        route = source.split('app.MapPut(', 1)[1].split('internal static', 1)[0]
        self.assertIn('var ids=Parse(raw)', route)
        self.assertIn('await Validate(db,tenant,ids)', route)
        self.assertIn('await Replace(db,state,tenant,roleId,ids)', route)
        self.assertNotIn('DELETE FROM', route)
        self.assertEqual(source.count('DELETE FROM foundation.role_company'), 1)
        self.assertEqual(source.count('"assign_companies","role-companies"'), 1)
        self.assertIn('db.Database.CurrentTransaction!=null', source)
        self.assertIn('PartnerInput.Array(raw,1000)', source)
        self.assertIn('Guid.TryParseExact(text,"D"', source)
        self.assertIn('new{beforeIds,afterIds}', source)
        self.assertIn('AND NOT(company_id=ANY', source)

    def test_existing_middleware_owns_the_transaction_and_buffers_response(self):
        program = (ROOT / 'backend/Program.cs').read_text()
        self.assertIn('if(ctx.Response.StatusCode < 400) await tx.CommitAsync()', program)
        self.assertLess(program.index('await tx.CommitAsync();', program.index('var originalBody=')), program.index('await buffer.CopyToAsync'))

if __name__ == '__main__':
    unittest.main()
