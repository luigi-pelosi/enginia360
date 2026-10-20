using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class CarcassBoundaryTests
{
    private const string Returns = "/api/v1/inventory/orders/11111111-6666-0000-0000-000000000001/lines/11111111-7777-0000-0000-000000000002/carcass-returns";
    private const string Gate = "/api/v1/workshop/orders/11111111-6666-0000-0000-000000000001/technical-closure-gate";
    [Theory]
    [InlineData("GET", Returns)]
    [InlineData("POST", Returns)]
    [InlineData("GET", Gate)]
    public async Task Carcass_surface_requires_real_authentication_before_database_access(string method, string route)
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder => builder
            .UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true")
            .UseSetting("Inventory:Enabled", "true"));
        using var client = factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), route + (method == "GET" && route == Returns ? "?warehouseId=" + Guid.NewGuid() : ""));
        if (method == "POST") request.Content = JsonContent.Create(new { id = Guid.NewGuid(), warehouseId = Guid.NewGuid(), quantity = "2", description = "Carcassa" });
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }
    [Fact]
    public async Task Closure_gate_is_absent_without_inventory()
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder => builder
            .UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true"));
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(Gate)).StatusCode);
    }
}
