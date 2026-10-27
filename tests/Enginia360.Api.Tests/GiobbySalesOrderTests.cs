using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using Enginia360.Integrations;
using Enginia360.Workshop.Contracts;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

public sealed class GiobbySalesOrderTests
{
    private static readonly Guid Tenant = Guid.Parse("11111111-0000-0000-0000-000000000001");
    private static readonly Guid Company = Guid.Parse("11111111-0000-0000-0000-000000000002");
    private static readonly Guid Site = Guid.Parse("11111111-0000-0000-0000-000000000003");
    private static readonly Guid Payer = Guid.Parse("11111111-0000-0000-0000-000000000004");
    private static readonly Guid Material = Guid.Parse("11111111-0000-0000-0000-000000000005");
    private static AdministrativeDispatchMessage Message()
    {
        var order = Guid.NewGuid();
        var line = new LineContract(Guid.NewGuid(), order, Material, 1, "Synthetic", "Part", "1.000000", "1.000000", "0.000000", "1.000000", "22.000000", Payer, Guid.NewGuid(), 1);
        return new(Tenant, Guid.NewGuid(), order, Company, Site, 1, new(order, Payer, 2, [line], "1.000000", "0.220000", "1.220000", "EUR", "q6"));
    }
    private sealed class Wire(Func<HttpRequestMessage, int, HttpResponseMessage> response) : HttpMessageHandler
    {
        internal string Identity { get; set; } = "{\"idCompany\":101,\"cid\":\"SYNTH-CID-A\"}";
        internal int IdentityReads { get; private set; }
        internal List<(string Method, string Path, string? Body, string? Realm, string? Auth)> Calls { get; } = [];
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            if (request.RequestUri!.AbsolutePath == "/loggeduser") { IdentityReads++; return Reply(Identity); }
            Calls.Add((request.Method.Method, request.RequestUri!.PathAndQuery, request.Content is null ? null : await request.Content.ReadAsStringAsync(ct),
                request.Headers.TryGetValues("X-Giobby-Realm", out var realm) ? realm.Single() : null, request.Headers.Authorization?.ToString()));
            return response(request, Calls.Count);
        }
    }
    private static HttpResponseMessage Reply(string json, HttpStatusCode status = HttpStatusCode.OK) => new(status) { Content = new StringContent(json, Encoding.UTF8, "application/json") };
    private static string Capture(string name)
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "tests/fixtures/r05a6-owned-captures.json"))) dir = dir.Parent;
        using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir!.FullName, "tests/fixtures/r05a6-owned-captures.json")));
        return doc.RootElement.GetProperty(name).GetRawText();
    }
    private sealed class Host : IDisposable
    {
        private readonly string token = Path.GetTempFileName();
        internal ServiceProvider Services { get; }
        internal Wire Http { get; }
        internal Host(Func<HttpRequestMessage, int, HttpResponseMessage> reply, Action<Dictionary<string, string?>>? edit = null)
        {
            File.WriteAllText(token, "synthetic-test-bearer");
            var values = new Dictionary<string, string?>
            {
                ["Protocol"] = "GiobbyV1", ["ProtocolVersion"] = "1", ["SimulatorBaseUrl"] = "https://giobby.test/",
                ["Giobby:BaseUrl"] = "https://giobby.test/", ["Giobby:AllowedHosts:0"] = "giobby.test", ["Giobby:CompanyAlias"] = "synthetic-company-A",
                ["Giobby:CompanyId"] = "101", ["Giobby:Cid"] = "SYNTH-CID-A",
                ["Giobby:TenantId"] = Tenant.ToString(), ["Giobby:LegalEntityId"] = Company.ToString(), ["Giobby:SiteId"] = Site.ToString(),
                ["Giobby:TokenFile"] = token, ["Giobby:BusinessUnit"] = "U1", ["Giobby:Numerator"] = "1", ["Giobby:Storage"] = "MB",
                [$"Giobby:Customers:{Payer}:Id"] = "owned-customer-1", [$"Giobby:Customers:{Payer}:ContactId"] = "9001", [$"Giobby:Customers:{Payer}:LookupName"] = "Owned synthetic customer",
                [$"Giobby:Materials:{Material}"] = "owned-product-1", ["Giobby:Taxes:22.000000"] = "22"
            };
            edit?.Invoke(values);
            var config = new ConfigurationBuilder().AddInMemoryCollection(values).Build();
            var services = new ServiceCollection(); services.AddLogging(); services.AddExternalAdministration("Host=unused;Database=unused", config);
            Http = new Wire(reply);
            services.AddHttpClient("SimulatorConnector").ConfigurePrimaryHttpMessageHandler(() => Http);
            services.AddHttpClient("GiobbySalesOrderConnector").ConfigurePrimaryHttpMessageHandler(() => Http);
            Services = services.BuildServiceProvider();
        }
        internal async Task<(string Outcome, string? Code)> Invoke(string operation, AdministrativeDispatchMessage m)
        {
            var dispatcher = typeof(IntegrationsModule).Assembly.GetType("Enginia360.Integrations.AdministrativeDispatcher")!;
            var connectorType = dispatcher.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic).Single().GetParameters()[2].ParameterType;
            var connector = Services.GetRequiredService(connectorType);
            var method = connector.GetType().GetMethod(operation, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)!;
            var task = (Task)method.Invoke(connector, [m, CancellationToken.None])!; await task;
            var result = task.GetType().GetProperty("Result")!.GetValue(task)!;
            return (result.GetType().GetProperty("Outcome")!.GetValue(result)!.ToString()!, (string?)result.GetType().GetProperty("Code")!.GetValue(result));
        }
        public void Dispose() { Services.Dispose(); File.Delete(token); }
    }
    [Theory]
    [InlineData("material")]
    [InlineData("tax")]
    [InlineData("storage")]
    [InlineData("customer")]
    [InlineData("lookup")]
    [InlineData("tenant")]
    [InlineData("company")]
    [InlineData("site")]
    public async Task Missing_or_foreign_verified_mapping_holds_before_business_http(string missing)
    {
        using var host = new Host((_, _) => Reply(Capture("order-create-response")), v =>
        {
            var key = missing switch { "material" => $"Giobby:Materials:{Material}", "tax" => "Giobby:Taxes:22.000000", "customer" => $"Giobby:Customers:{Payer}:Id", "lookup" => $"Giobby:Customers:{Payer}:LookupName", "tenant" => "Giobby:TenantId", "company" => "Giobby:LegalEntityId", "site" => "Giobby:SiteId", _ => "Giobby:Storage" };
            v[key] = null;
        });
        var result = await host.Invoke("Submit", Message());
        Assert.Empty(host.Http.Calls);
        Assert.Equal("mapping_missing", result.Code);
    }
    [Fact]
    public async Task Payload_uses_declared_sales_order_fields_and_q6_mappings()
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        await host.Invoke("Submit", message);
        Assert.Equal("/sales/orders?simulation=false", host.Http.Calls[0].Path);
        using var doc = JsonDocument.Parse(host.Http.Calls[0].Body!);
        var p = doc.RootElement;
        Assert.True(p.TryGetProperty("idDocumentType", out var type), "sales order document type missing");
        Assert.Equal(3, type.GetInt32());
        Assert.Equal("owned-customer-1", p.GetProperty("idCustomer").GetString());
        Assert.Equal(9001, p.GetProperty("idContact").GetInt32());
        Assert.Equal("E360-" + message.RequestId.ToString("N"), p.GetProperty("reference").GetString());
        var row = p.GetProperty("rows")[0];
        Assert.Equal("owned-product-1", row.GetProperty("idMaterial").GetString());
        Assert.Equal("MB", row.GetProperty("idStorage").GetString());
        Assert.Equal("22", row.GetProperty("idVat").GetString());
        Assert.Equal(1.000000m, row.GetProperty("quantity").GetDecimal());
        Assert.Equal(JsonValueKind.Number, row.GetProperty("price").ValueKind);
        Assert.False(p.TryGetProperty("docNumber", out _));
        Assert.DoesNotContain(host.Http.Calls, x => x.Path.Contains("invoice", StringComparison.OrdinalIgnoreCase));
    }
    [Fact]
    public async Task Regression_fractional_q6_payload_preserves_values_and_does_not_round_to_cents()
    {
        var m = Message();
        m = m with { Summary = m.Summary with { Lines = [m.Summary.Lines[0] with { Quantity = "2.123456", UnitPrice = "10.000001", DiscountPercent = "10.25", NetAmount = "19.058020" }], NetAmount = "19.058020", TaxAmount = "4.192764", Total = "23.250784" } };
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        await host.Invoke("Submit", m);
        using var json = JsonDocument.Parse(host.Http.Calls[0].Body!);
        var row = json.RootElement.GetProperty("rows")[0];
        Assert.Equal(2.123456m, row.GetProperty("quantity").GetDecimal());
        Assert.Equal(10.000001m, row.GetProperty("price").GetDecimal());
        Assert.Equal(10.25m, row.GetProperty("dsc1").GetDecimal());
    }
    [Theory]
    [InlineData("Submit", "tenant")]
    [InlineData("Status", "company")]
    [InlineData("Submit", "site")]
    [InlineData("Status", "payer")]
    public async Task Regression_company_mapping_never_applies_to_an_arbitrary_owner_or_payer(string operation, string changed)
    {
        var m = Message();
        m = changed switch { "tenant" => m with { TenantId = Guid.NewGuid() }, "company" => m with { LegalEntityId = Guid.NewGuid() }, "site" => m with { SiteId = Guid.NewGuid() }, _ => m with { Summary = m.Summary with { PayerId = Guid.NewGuid() } } };
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        Assert.Equal("mapping_missing", (await host.Invoke(operation, m)).Code);
        Assert.Empty(host.Http.Calls); Assert.Equal(0, host.Http.IdentityReads);
    }
    [Fact]
    public void Lease_must_cover_all_three_bounded_Giobby_http_calls()
    {
        var error = Record.Exception(() => { using var host = new Host((_, _) => Reply("{}"), v => { v["TimeoutMilliseconds"] = "1000"; v["LeaseMilliseconds"] = "2500"; }); });
        Assert.IsType<InvalidOperationException>(error);
    }
    [Fact]
    public async Task Token_identity_is_checked_through_authenticated_loggeduser_before_business_http()
    {
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        host.Http.Identity = "{\"idCompany\":102,\"cid\":\"SYNTH-CID-B\"}";
        var result = await host.Invoke("Submit", Message());
        Assert.Empty(host.Http.Calls);
        Assert.Equal(1, host.Http.IdentityReads);
        Assert.Equal("identity_unverified", result.Code);
    }
    [Fact]
    public async Task Tax_mapping_is_decimal_q6_not_source_string_format()
    {
        var message = Message();
        message = message with { Summary = message.Summary with { Lines = [message.Summary.Lines[0] with { TaxRate = "22" }] } };
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        await host.Invoke("Submit", message);
        Assert.Equal(2, host.Http.Calls.Count);
    }
    [Fact]
    public void Configured_runtime_and_immutable_descriptor_identify_actual_Giobby_company_order_destination()
    {
        using var a = new Host((_, _) => Reply("{}"));
        using var b = new Host((_, _) => Reply("{}"), v => v["Giobby:CompanyAlias"] = "synthetic-company-B");
        var binding = a.Services.GetRequiredService<AdministrativeConnectorBinding>();
        Assert.Equal("GiobbyV1", binding.Kind);
        Assert.Equal(1, binding.ProtocolVersion);
        Assert.NotEqual(binding, b.Services.GetRequiredService<AdministrativeConnectorBinding>());
        Assert.Equal(new AdministrativeRuntime("GiobbyV1", 1), a.Services.GetService<AdministrativeRuntime>());
    }
    [Fact]
    public async Task Host_auth_boundary_attaches_api_server_bearer_not_payload_authentication()
    {
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        await host.Invoke("Submit", Message());
        Assert.All(host.Http.Calls, c => { Assert.Equal("api-server", c.Realm); Assert.Equal("Bearer synthetic-test-bearer", c.Auth); });
        Assert.DoesNotContain("synthetic-test-bearer", host.Http.Calls[0].Body!);
    }
    [Theory]
    [InlineData("Submit", "missing-token")]
    [InlineData("Status", "missing-token")]
    [InlineData("Submit", "http")]
    [InlineData("Status", "foreign-host")]
    public async Task Unconfigured_auth_or_untrusted_base_holds_without_http(string operation, string mode)
    {
        using var host = new Host((_, _) => Reply(Capture("order-create-response")), v =>
        {
            if (mode == "missing-token") v["Giobby:TokenFile"] = "/nonexistent/synthetic-token";
            if (mode == "http") v["Giobby:BaseUrl"] = "http://giobby.test/";
            if (mode == "foreign-host") v["Giobby:BaseUrl"] = "https://foreign.test/";
        });
        Assert.Equal("Failure", (await host.Invoke(operation, Message())).Outcome);
        Assert.Empty(host.Http.Calls);
    }
    [Fact]
    public async Task Unknown_business_error_with_document_id_is_ambiguous_without_readback()
    {
        using var host = new Host((_, _) => Reply("{\"responseCode\":200,\"errorCode\":2121003,\"idDocument\":101}"));
        var result = await host.Invoke("Submit", Message());
        Assert.Equal("Failure", result.Outcome); Assert.Single(host.Http.Calls);
    }
    [Theory]
    [InlineData("Submit", "timeout")]
    [InlineData("Status", "timeout")]
    [InlineData("Submit", "transport")]
    [InlineData("Status", "transport")]
    [InlineData("Submit", "oversize")]
    [InlineData("Status", "invalid-json")]
    [InlineData("Submit", "500")]
    public async Task Unknown_transport_or_invalid_response_is_ambiguous_without_exception(string operation, string mode)
    {
        using var host = new Host((_, _) => mode switch
        {
            "timeout" => throw new TaskCanceledException(), "transport" => throw new HttpRequestException(),
            "oversize" => Reply(new string(' ', 65537) + Capture("order-create-response")),
            "500" => Reply(Capture("order-create-response"), HttpStatusCode.InternalServerError), _ => Reply("not-json")
        });
        (string Outcome, string? Code) result = default;
        var error = await Record.ExceptionAsync(async () => result = await host.Invoke(operation, Message()));
        Assert.Null(error); Assert.Equal("Failure", result.Outcome); Assert.Single(host.Http.Calls);
    }
    [Fact]
    public async Task Status_uses_preconfigured_customer_name_and_exact_typed_reference_then_readback()
    {
        var message = Message();
        string Bound(string name) => Capture(name).Replace("E360-SB-R05A6-20261027T131422Z-ORD", "E360-" + message.RequestId.ToString("N"));
        using var host = new Host((_, count) => Reply(Bound(count == 1 ? "order-lookup-customer-name-status" : "order-readback")));
        Assert.Equal("Completed", (await host.Invoke("Status", message)).Outcome);
        Assert.Equal("/sales/orders?offset=0&limit=5&freeText=Owned%20synthetic%20customer&docStatus=CREATED", host.Http.Calls[0].Path);
        Assert.All(host.Http.Calls, x => Assert.Equal("GET", x.Method));
    }
    [Theory]
    [InlineData("empty", "lookup_empty")]
    [InlineData("nonunique", "lookup_nonunique")]
    [InlineData("truncated", "lookup_truncated")]
    [InlineData("wrong-type", "lookup_empty")]
    [InlineData("wrong-reference", "lookup_empty")]
    public async Task Ambiguous_lookup_never_means_NotFound_or_resubmit(string mode, string expected)
    {
        var message = Message();
        var root = System.Text.Json.Nodes.JsonNode.Parse(Capture("order-lookup-customer-name-status"))!;
        root["documentsHeaders"]![0]!["reference"] = "E360-" + message.RequestId.ToString("N");
        if (mode == "empty") { root["documentsHeaders"] = new System.Text.Json.Nodes.JsonArray(); root["metadata"]!["totalCount"] = 0; }
        if (mode == "nonunique") { root["documentsHeaders"]!.AsArray().Add(root["documentsHeaders"]![0]!.DeepClone()); root["metadata"]!["totalCount"] = 2; }
        if (mode == "truncated") root["metadata"]!["totalCount"] = 6;
        if (mode == "wrong-type") root["documentsHeaders"]![0]!["idDocumentType"] = 10;
        if (mode == "wrong-reference") root["documentsHeaders"]![0]!["reference"] = "other";
        using var host = new Host((_, _) => Reply(root.ToJsonString()));
        var result = await host.Invoke("Status", message);
        Assert.Equal("Failure", result.Outcome); Assert.Equal(expected, result.Code);
        Assert.Single(host.Http.Calls); Assert.Equal("GET", host.Http.Calls[0].Method);
    }
    [Fact]
    public async Task Completed_requires_exact_owned_readback_not_only_document_id()
    {
        var message = Message();
        var capture = JsonDocument.Parse(Capture("order-readback")).RootElement;
        var readback = capture.GetRawText().Replace(capture.GetProperty("document").GetProperty("reference").GetString()!, "E360-" + message.RequestId.ToString("N"));
        using var host = new Host((_, count) => Reply(count == 1 ? Capture("order-create-response") : readback));
        var result = await host.Invoke("Submit", message);
        Assert.Equal("Completed", result.Outcome);
        Assert.Equal(2, host.Http.Calls.Count);
    }
    [Theory]
    [InlineData("reference")]
    [InlineData("idCustomer")]
    [InlineData("totalAmount")]
    [InlineData("quantity")]
    [InlineData("price")]
    [InlineData("idMaterial")]
    [InlineData("idStorage")]
    [InlineData("dsc1")]
    [InlineData("idVat")]
    [InlineData("idDocumentType")]
    [InlineData("rows")]
    public async Task Mismatched_readback_is_ambiguous(string field)
    {
        var message = Message();
        var root = System.Text.Json.Nodes.JsonNode.Parse(Capture("order-readback"))!;
        var document = root["document"]!;
        document["reference"] = "E360-" + message.RequestId.ToString("N");
        if (field == "rows") document["rows"] = new System.Text.Json.Nodes.JsonArray();
        else if (field is "quantity" or "price" or "dsc1") document["rows"]![0]![field] = 2m;
        else if (field is "idMaterial" or "idStorage" or "idVat") document["rows"]![0]![field] = "other";
        else if (field is "totalAmount" or "idDocumentType") document[field] = 10;
        else document[field] = "other";
        using var host = new Host((_, count) => Reply(count == 1 ? Capture("order-create-response") : root.ToJsonString()));
        Assert.Equal("Failure", (await host.Invoke("Submit", message)).Outcome);
    }
    [Fact]
    public async Task Http200_idDocument_is_not_completed_without_matching_readback()
    {
        using var host = new Host((_, _) => Reply(Capture("order-create-response")));
        var result = await host.Invoke("Submit", Message());
        Assert.NotEqual("Completed", result.Outcome);
        Assert.Equal(2, host.Http.Calls.Count); // Acknowledge-only success MUST cause a readback, not business completion.
        Assert.Equal("/sales/101/orders", host.Http.Calls[1].Path);
    }
}
