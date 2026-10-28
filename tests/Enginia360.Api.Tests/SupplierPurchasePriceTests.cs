using Microsoft.AspNetCore.Hosting;
using System.Net;
using System.Net.Http.Json;
using Xunit;

public sealed class SupplierPurchasePriceTests : IClassFixture<TestApiFactory>
{
    private readonly TestApiFactory factory;
    public SupplierPurchasePriceTests(TestApiFactory factory) => this.factory = factory;
    [Theory]
    [InlineData("GET")]
    [InlineData("PUT")]
    public async Task Supplier_purchase_prices_require_authentication_not_scope_headers(string method)
    {
        using var app = factory.WithWebHostBuilder(b => b.UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true"));
        using var client = app.CreateClient();
        client.DefaultRequestHeaders.Add("X-Tenant-Id", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Identity-Subject", Guid.NewGuid().ToString());
        var path = "/api/v1/catalog/suppliers/11111111-1111-4111-8111-111111111111/items/11111111-1111-4111-8111-111111111111/purchase-price?legalEntityId=11111111-1111-4111-8111-111111111111";
        var result = method == "GET" ? await client.GetAsync(path) : await client.PutAsJsonAsync(path, new {});
        Assert.Equal(HttpStatusCode.Unauthorized, result.StatusCode);
    }
}
