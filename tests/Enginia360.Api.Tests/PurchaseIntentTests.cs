using Microsoft.Extensions.Configuration;
using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class PurchaseIntentTests : IClassFixture<TestApiFactory>
{
    private readonly TestApiFactory factory;
    public PurchaseIntentTests(TestApiFactory factory) => this.factory = factory;
    [Fact]
    public void Purchase_destination_is_frozen_from_the_verified_giobby_binding_and_external_stock_profile()
    {
        var tenant = Guid.NewGuid().ToString(); var company = Guid.NewGuid().ToString(); var site = Guid.NewGuid().ToString(); var source = Guid.NewGuid().ToString(); var profile = Guid.NewGuid().ToString();
        var config = new Microsoft.Extensions.Configuration.ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
            { ["TenantId"] = tenant, ["LegalEntityId"] = company, ["SiteId"] = site, ["PurchaseStockSourceId"] = source, ["PurchaseStockProfileId"] = profile }).Build();
        var binding = new Enginia360.Workshop.Contracts.AdministrativeConnectorBinding("GiobbyV1", 1, new string('a', 64));
        var json = System.Text.Json.JsonDocument.Parse(Enginia360.Integrations.IntegrationsModule.PurchaseDestinationDescriptor(binding, config)!).RootElement;
        Assert.Equal("GiobbyPurchaseV1", json.GetProperty("kind").GetString());
        Assert.Equal(1, json.GetProperty("version").GetInt32());
        Assert.Equal(64, json.GetProperty("fingerprint").GetString()!.Length);
        Assert.NotEqual(binding.DestinationFingerprint, json.GetProperty("fingerprint").GetString());
        Assert.Equal((tenant, company, site), (json.GetProperty("tenantId").GetString(), json.GetProperty("legalEntityId").GetString(), json.GetProperty("siteId").GetString()));
        Assert.Equal(source, json.GetProperty("stockSourceId").GetString());
        Assert.Equal(profile, json.GetProperty("stockProfileId").GetString());
        foreach (var unavailable in new[] { new Enginia360.Workshop.Contracts.AdministrativeConnectorBinding("SimulatorV1", 1, new string('a', 64)), new Enginia360.Workshop.Contracts.AdministrativeConnectorBinding("Unavailable", 0, "") })
            Assert.Null(Enginia360.Integrations.IntegrationsModule.PurchaseDestinationDescriptor(unavailable, config));
    }

    [Fact]
    public void Purchase_creation_descriptor_covers_every_purchase_mapping_and_excludes_secrets()
    {
        var values = new Dictionary<string, string?> { ["TenantId"] = Guid.NewGuid().ToString(), ["LegalEntityId"] = Guid.NewGuid().ToString(), ["SiteId"] = Guid.NewGuid().ToString(), ["PurchaseStockSourceId"] = Guid.NewGuid().ToString(), ["PurchaseStockProfileId"] = Guid.NewGuid().ToString(), ["PurchaseOrder:Storage"] = "A", ["TokenFile"] = "/secret/a" };
        var binding = new Enginia360.Workshop.Contracts.AdministrativeConnectorBinding("GiobbyV1", 1, new string('a', 64));
        string Fingerprint()
        {
            var config = new ConfigurationBuilder().AddInMemoryCollection(values).Build();
            using var json = System.Text.Json.JsonDocument.Parse(Enginia360.Integrations.IntegrationsModule.PurchaseDestinationDescriptor(binding, config)!);
            return json.RootElement.GetProperty("fingerprint").GetString()!;
        }
        var original = Fingerprint();
        values["TokenFile"] = "/secret/b"; Assert.Equal(original, Fingerprint());
        values["PurchaseOrder:Storage"] = "B"; Assert.NotEqual(original, Fingerprint());
    }

    [Theory]
    [InlineData("GET", "quote")]
    [InlineData("POST", "accepted")]
    public async Task Quoted_and_priced_intent_surfaces_require_real_authentication(string method, string suffix)
    {
        using var app = factory.WithWebHostBuilder(b => b.UseSetting("Inventory:Enabled", "true").UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true"));
        using var client = app.CreateClient();
        client.DefaultRequestHeaders.Add("X-Tenant-Id", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Identity-Subject", Guid.NewGuid().ToString());
        var path = "/api/v1/inventory/orders/11111111-1111-4111-8111-111111111111/lines/11111111-1111-4111-8111-111111111111/purchase-intents/" + suffix + "?warehouseId=11111111-1111-4111-8111-111111111111&supplierId=11111111-1111-4111-8111-111111111111";
        var result = method == "GET" ? await client.GetAsync(path) : await client.PostAsJsonAsync(path, new {});
        Assert.Equal(HttpStatusCode.Unauthorized, result.StatusCode);
    }

    [Theory]
    [InlineData("GET")]
    [InlineData("POST")]
    public async Task Purchase_intents_require_real_authentication_not_identity_headers(string method)
    {
        using var app = factory.WithWebHostBuilder(b => b.UseSetting("Inventory:Enabled", "true").UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true"));
        using var client = app.CreateClient();
        client.DefaultRequestHeaders.Add("X-Tenant-Id", Guid.NewGuid().ToString());
        client.DefaultRequestHeaders.Add("X-Identity-Subject", Guid.NewGuid().ToString());
        var path = "/api/v1/inventory/orders/11111111-1111-4111-8111-111111111111/lines/11111111-1111-4111-8111-111111111111/purchase-intents?warehouseId=11111111-1111-4111-8111-111111111111";
        var result = method == "GET" ? await client.GetAsync(path) : await client.PostAsJsonAsync(path, new {});
        Assert.Equal(HttpStatusCode.Unauthorized, result.StatusCode);
    }
}
