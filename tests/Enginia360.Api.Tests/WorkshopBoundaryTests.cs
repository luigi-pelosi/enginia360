using System.Net;
using Enginia360.Vehicles;
using Enginia360.Vehicles.Contracts;
using Enginia360.Workshop;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Configuration;
using Xunit;

public sealed class WorkshopBoundaryTests
{
    [Theory]
    [InlineData("/api/v1/workshop/contexts")]
    [InlineData("/api/v1/workshop/vehicles?legalEntityId=11111111-1111-1111-1111-111111111101&siteId=11111111-1111-1111-1111-111111110101")]
    [InlineData("/api/v1/workshop/document-types?legalEntityId=11111111-1111-1111-1111-111111111101&siteId=11111111-1111-1111-1111-111111110101")]
    [InlineData("/api/v1/workshop/orders/11111111-6666-0000-0000-000000000001")]
    public async Task Enabled_workshop_queries_require_real_authentication(string path)
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder => builder
            .UseSetting("Workshop:Enabled", "true")
            .UseSetting("Counterparties:Enabled", "true"));
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(path)).StatusCode);
    }

    [Theory]
    [InlineData(typeof(WorkshopModule))]
    [InlineData(typeof(VehiclesModule))]
    public void Module_implementation_exposes_only_registration_and_depends_only_on_public_contracts(Type module)
    {
        Assert.Equal([module], module.Assembly.GetExportedTypes());
        Assert.All(module.Assembly.GetReferencedAssemblies().Where(x => x.Name!.StartsWith("Enginia360.")),
            dependency => Assert.EndsWith(".Contracts", dependency.Name));
    }

    [Theory]
    [InlineData(typeof(OrderContract))]
    [InlineData(typeof(VehicleChoice))]
    public void Public_contracts_do_not_depend_on_orm_or_other_implementations(Type contract)
    {
        Assert.DoesNotContain(contract.Assembly.GetReferencedAssemblies(), x =>
            x.Name!.StartsWith("Microsoft.") || x.Name.StartsWith("Npgsql") || x.Name.StartsWith("Enginia360."));
    }
}
