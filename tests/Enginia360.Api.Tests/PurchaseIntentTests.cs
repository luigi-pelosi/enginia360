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

    // R04.b.2b.3 PR2: the dispatch readout is derived from owner-module facts only (Inventory price/outcome + the Integrations-owned technical state published through Inventory.Contracts).
    private static readonly Guid Priced = Guid.Parse("33333333-3333-4333-8333-333333333331"), Legacy = Guid.Parse("33333333-3333-4333-8333-333333333332");
    private static (string State, string? Reason, string? Reference) Readout(bool priced, string? outcome, string? state, string? error)
    {
        var r = Enginia360.Inventory.Contracts.PurchaseDispatchReadout.From(priced, outcome, state is null ? null : new Enginia360.Inventory.Contracts.PurchaseDelivery(state, error));
        return (r.State, r.Reason, r.ExternalReference);
    }
    [Fact]
    public void Dispatch_readout_distinguishes_unsendable_queued_uncertain_and_confirmed()
    {
        Assert.Equal(("not_sendable", "unpriced", null), Readout(false, null, null, null));
        Assert.Equal(("not_sendable", "unpriced", null), Readout(false, null, "Queued", null));
        Assert.Equal(("queued", null, null), Readout(true, null, null, null));
        Assert.Equal(("queued", null, null), Readout(true, null, "Queued", null));
        Assert.Equal(("queued", null, null), Readout(true, null, "Queued", "source_unavailable"));
        Assert.Equal(("uncertain", null, null), Readout(true, null, "Uncertain", "provider_timeout"));
        Assert.Equal(("uncertain", null, null), Readout(true, null, "Completed", null));
        Assert.Equal(("confirmed", null, "GiobbyPurchaseOrder-301"), Readout(true, "GiobbyPurchaseOrder-301", "Completed", null));
        Assert.Equal(("confirmed", null, "GiobbyPurchaseOrder-301"), Readout(true, "GiobbyPurchaseOrder-301", null, null));
    }
    [Theory]
    [InlineData("mapping_missing")]
    [InlineData("provider_unconfigured")]
    [InlineData("destination_binding_mismatch")]
    [InlineData("identity_unverified")]
    public void Dispatch_readout_reports_missing_purchase_configuration_without_host_detail(string code)
    {
        Assert.Equal(("queued", "configuration_missing", null), Readout(true, null, "Queued", code));
        Assert.Equal(("uncertain", "configuration_missing", null), Readout(true, null, "Uncertain", code));
        Assert.Equal(("confirmed", null, "GiobbyPurchaseOrder-301"), Readout(true, "GiobbyPurchaseOrder-301", "Uncertain", code));
    }
    [Fact]
    public void Dispatch_readout_merges_into_the_owner_state_and_removes_internal_outcome()
    {
        var state = System.Text.Json.Nodes.JsonNode.Parse("""
            {"state":"ready","intents":[
             {"id":"33333333-3333-4333-8333-333333333331","status":"Held","acceptedPrice":{"unitPurchasePrice":"1.000000"},"outcome":{"externalReference":"GiobbyPurchaseOrder-301"}},
             {"id":"33333333-3333-4333-8333-333333333332","status":"Held","acceptedPrice":null,"outcome":null}]}
            """)!.AsObject();
        Enginia360.Inventory.Contracts.PurchaseDispatchReadout.Apply(state, new Dictionary<Guid, Enginia360.Inventory.Contracts.PurchaseDelivery> { [Priced] = new("Completed", null), [Legacy] = new("Queued", "mapping_missing") });
        var intents = state["intents"]!.AsArray();
        Assert.Equal("confirmed", intents[0]!["dispatch"]!["state"]!.GetValue<string>());
        Assert.Equal("GiobbyPurchaseOrder-301", intents[0]!["dispatch"]!["externalReference"]!.GetValue<string>());
        Assert.Equal("not_sendable", intents[1]!["dispatch"]!["state"]!.GetValue<string>());
        Assert.Equal("unpriced", intents[1]!["dispatch"]!["reason"]!.GetValue<string>());
        Assert.All(intents, i => Assert.False(i!.AsObject().ContainsKey("outcome")));
        Assert.DoesNotContain("mapping_missing", state.ToJsonString());
    }
}
