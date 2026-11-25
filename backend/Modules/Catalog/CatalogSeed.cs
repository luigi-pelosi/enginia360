using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Catalog;

public static class CatalogSeed
{
    public static async Task Seed(AppDb db,Guid tenant,Guid? actor=null)
    {
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        await db.Execute("SELECT masterdata.seed_catalog(@tenant,@actor::uuid)",("tenant",tenant),("actor",actor));
    }
}
