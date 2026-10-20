using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class InstallationBoundaryTests
{
    private const string Route = "/api/v1/workshop/orders/11111111-6666-0000-0000-000000000001/lines/11111111-7777-0000-0000-000000000002/picks/11111111-8888-0000-0000-000000000001/installations";
    [Theory]
    [InlineData("GET")]
    [InlineData("POST")]
    public async Task Installation_requires_real_authentication_before_database_access(string method)
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder => builder
            .UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true")
            .UseSetting("Inventory:Enabled", "true"));
        using var client = factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), Route);
        if (method == "POST") request.Content = JsonContent.Create(new { id = Guid.NewGuid(), quantity = "1" });
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }
    [Fact]
    public async Task Installation_surface_is_absent_without_inventory()
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder => builder
            .UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true"));
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(Route)).StatusCode);
    }
}
