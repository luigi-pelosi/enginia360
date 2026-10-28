using System.Net;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Enginia360.Integrations;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

// R04.b.2b.3: Giobby purchase-order connector over the owned R05.a.7 projections only. No live traffic.
public sealed class GiobbyPurchaseOrderTests
{
    private static readonly Guid Tenant = Guid.Parse("22222222-0000-0000-0000-000000000001");
    private static readonly Guid Company = Guid.Parse("22222222-0000-0000-0000-000000000002");
    private static readonly Guid Site = Guid.Parse("22222222-0000-0000-0000-000000000003");
    private static readonly Guid Item = Guid.Parse("22222222-0000-0000-0000-000000000005");
    private const string Vendor = "owned-vendor-A";
    private const string VendorName = "Owned Synthetic Vendor";
    private sealed class Wire(Func<HttpRequestMessage, int, HttpResponseMessage> response) : HttpMessageHandler
    {
        internal string Identity { get; set; } = "{\"idCompany\":101,\"cid\":\"SYNTH-CID-A\"}";
        internal List<(string Method, string Path, string? Body, string? Realm, string? Auth)> Calls { get; } = [];
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct)
        {
            if (request.RequestUri!.AbsolutePath == "/loggeduser") return Reply(Identity);
            Calls.Add((request.Method.Method, request.RequestUri!.PathAndQuery, request.Content is null ? null : await request.Content.ReadAsStringAsync(ct),
                request.Headers.TryGetValues("X-Giobby-Realm", out var realm) ? realm.Single() : null, request.Headers.Authorization?.ToString()));
            return response(request, Calls.Count);
        }
    }
    private static HttpResponseMessage Reply(string json, HttpStatusCode status = HttpStatusCode.OK) => new(status) { Content = new StringContent(json, Encoding.UTF8, "application/json") };
    private static JsonNode Capture(string name)
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "tests/fixtures/r05a7-owned-captures.json"))) dir = dir.Parent;
        return JsonNode.Parse(File.ReadAllText(Path.Combine(dir!.FullName, "tests/fixtures/r05a7-owned-captures.json")))![name]!.DeepClone();
    }
    private static string Reference(PurchaseDispatchMessage m) => "E360-PO-" + m.IntentId.ToString("N");
    // The owned po-readback projection, with only identifiers/amounts replaced to describe the message under test (synthetic transformation).
    private static string Detail(PurchaseDispatchMessage m, int id = 301, Action<JsonObject, JsonObject>? edit = null)
    {
        var root = Capture("po-readback").AsObject(); var d = root["document"]!.AsObject(); var row = d["rows"]![0]!.AsObject();
        d["id"] = id; d["reference"] = Reference(m); d["idVendor"] = m.VendorId;
        row["description"] = m.Description; row["quantity"] = decimal.Parse(m.Quantity, System.Globalization.CultureInfo.InvariantCulture);
        row["price"] = decimal.Parse(m.UnitPrice, System.Globalization.CultureInfo.InvariantCulture);
        edit?.Invoke(d, row);
        return root.ToJsonString();
    }
    private static string Header(PurchaseDispatchMessage m, int id = 301, string? reference = null) =>
        $"{{\"docCurrency\":\"EUR\",\"docNumber\":\"5\",\"docStatus\":\"CREATED\",\"id\":{id},\"idContact\":null,\"idDocumentType\":2,\"idOrderType\":1,\"idVendor\":\"{m.VendorId}\",\"reference\":\"{reference ?? Reference(m)}\",\"totalAmount\":15.07}}";
    private static string Page(params string[] headers) => $"{{\"documentsHeaders\":[{string.Join(',', headers)}],\"errorCode\":0,\"metadata\":{{\"limit\":5,\"offset\":0,\"totalCount\":{headers.Length}}},\"responseCode\":200}}";
    private static PurchaseDispatchMessage Message(string quantity = "2.000000", string price = "12.345678", Guid? tenant = null)
    {
        var host = new Host((_, _) => Reply("{}")); // only to learn the frozen binding fingerprint of the host fixture
        var fingerprint = host.Services.GetRequiredService<AdministrativeConnectorBinding>().DestinationFingerprint; host.Dispose();
        return new(tenant ?? Tenant, Company, Site, Guid.NewGuid(), Item, "Pastiglie freno sintetiche", quantity, price, Vendor, VendorName, fingerprint);
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
                ["Giobby:TokenFile"] = token,
                ["Giobby:PurchaseOrder:DocumentType"] = "2", ["Giobby:PurchaseOrder:OrderType"] = "1", ["Giobby:PurchaseOrder:BusinessUnit"] = "U1",
                ["Giobby:PurchaseOrder:Numerator"] = "1", ["Giobby:PurchaseOrder:PosType"] = "1", ["Giobby:PurchaseOrder:Payments"] = "none",
                ["Giobby:PurchaseOrder:Currency"] = "EUR", ["Giobby:PurchaseOrder:Vat"] = "22", ["Giobby:PurchaseOrder:Storage"] = "MB",
                [$"Giobby:PurchaseOrder:Materials:{Item}"] = "owned-product-1"
            };
            edit?.Invoke(values);
            var config = new ConfigurationBuilder().AddInMemoryCollection(values).Build();
            var services = new ServiceCollection(); services.AddLogging(); services.AddExternalAdministration("Host=unused;Database=unused", config);
            Http = new Wire(reply);
            services.AddHttpClient("GiobbyPurchaseOrderConnector").ConfigurePrimaryHttpMessageHandler(() => Http);
            Services = services.BuildServiceProvider();
        }
        internal async Task<(string Outcome, string? Code, string? Reference)> Invoke(string operation, PurchaseDispatchMessage m)
        {
            var connectorType = typeof(IntegrationsModule).Assembly.GetType("Enginia360.Integrations.GiobbyPurchaseOrderConnector")!;
            var connector = Services.GetRequiredService(connectorType);
            var method = connector.GetType().GetMethod(operation, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)!;
            var task = (Task)method.Invoke(connector, [m, CancellationToken.None])!; await task;
            var result = task.GetType().GetProperty("Result")!.GetValue(task)!;
            return (result.GetType().GetProperty("Outcome")!.GetValue(result)!.ToString()!, (string?)result.GetType().GetProperty("Code")!.GetValue(result), (string?)result.GetType().GetProperty("ExternalReference")!.GetValue(result));
        }
        public void Dispose() { Services.Dispose(); File.Delete(token); }
    }

    [Fact]
    public async Task Persisted_order_is_posted_with_observed_declared_fields_then_completed_only_by_exact_readback()
    {
        var message = Message();
        using var host = new Host((request, _) => request.Method == HttpMethod.Post ? Reply(Capture("po-ack").ToJsonString()) : Reply(Detail(message)));
        var result = await host.Invoke("Submit", message);
        Assert.Equal(["POST /purchases/orders?simulation=false", "GET /purchases/301/orders"], host.Http.Calls.Select(x => x.Method + " " + x.Path));
        Assert.All(host.Http.Calls, c => { Assert.Equal("api-server", c.Realm); Assert.Equal("Bearer synthetic-test-bearer", c.Auth); });
        using var body = JsonDocument.Parse(host.Http.Calls[0].Body!); var p = body.RootElement;
        Assert.Equal(2, p.GetProperty("idDocumentType").GetInt32());
        Assert.Equal(1, p.GetProperty("idOrderType").GetInt32());
        Assert.Equal(JsonValueKind.Null, p.GetProperty("idContact").ValueKind);
        Assert.Equal(Vendor, p.GetProperty("idVendor").GetString());
        Assert.Equal("U1", p.GetProperty("idBu").GetString());
        Assert.Equal(1, p.GetProperty("idNumerator").GetInt32());
        Assert.Equal("EUR", p.GetProperty("docCurrency").GetString());
        Assert.Equal(Reference(message), p.GetProperty("reference").GetString());
        Assert.Equal(JsonValueKind.Array, p.GetProperty("payments").ValueKind); Assert.Equal(0, p.GetProperty("payments").GetArrayLength());
        Assert.False(p.TryGetProperty("docNumber", out _)); Assert.False(p.TryGetProperty("docStatus", out _)); Assert.False(p.TryGetProperty("idCustomer", out _));
        var row = Assert.Single(p.GetProperty("rows").EnumerateArray());
        Assert.Equal("owned-product-1", row.GetProperty("idMaterial").GetString());
        Assert.Equal(1, row.GetProperty("idPosType").GetInt32());
        Assert.Equal(0, row.GetProperty("idAttributeCombination").GetInt32());
        Assert.Equal("Pastiglie freno sintetiche", row.GetProperty("description").GetString());
        Assert.Equal(2m, row.GetProperty("quantity").GetDecimal());
        Assert.Equal("12.345678", row.GetProperty("price").GetRawText());
        Assert.Equal("22", row.GetProperty("idVat").GetString());
        Assert.Equal("MB", row.GetProperty("idStorage").GetString());
        Assert.Equal(("Completed", null, "GiobbyPurchaseOrder-301"), result);
    }

    // ---- Regression coverage added after the S1 implementation (initially GREEN, not RED): fail-closed and mismatch boundaries. ----
    [Theory]
    [InlineData("Giobby:PurchaseOrder:DocumentType")]
    [InlineData("Giobby:PurchaseOrder:OrderType")]
    [InlineData("Giobby:PurchaseOrder:BusinessUnit")]
    [InlineData("Giobby:PurchaseOrder:Numerator")]
    [InlineData("Giobby:PurchaseOrder:PosType")]
    [InlineData("Giobby:PurchaseOrder:Payments")]
    [InlineData("Giobby:PurchaseOrder:Currency")]
    [InlineData("Giobby:PurchaseOrder:Vat")]
    [InlineData("Giobby:PurchaseOrder:Storage")]
    [InlineData("Giobby:PurchaseOrder:Materials")]
    [InlineData("Giobby:TenantId")]
    [InlineData("Giobby:LegalEntityId")]
    [InlineData("Giobby:SiteId")]
    public async Task Missing_or_foreign_purchase_setup_fails_closed_before_any_business_http(string missing)
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString()), v => v[missing == "Giobby:PurchaseOrder:Materials" ? $"Giobby:PurchaseOrder:Materials:{Item}" : missing] = null);
        foreach (var operation in new[] { "Submit", "Status" })
        {
            var result = await host.Invoke(operation, message);
            Assert.Equal(("Failure", "mapping_missing"), (result.Outcome, result.Code));
        }
        Assert.Empty(host.Http.Calls);
    }
    [Theory]
    [InlineData("Giobby:PurchaseOrder:DocumentType", "3")]
    [InlineData("Giobby:PurchaseOrder:Payments", "default")]
    [InlineData("Giobby:PurchaseOrder:Currency", "USD")]
    public async Task Unverified_purchase_setup_values_are_refused_not_defaulted(string key, string value)
    {
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString()), v => v[key] = value);
        var result = await host.Invoke("Submit", Message());
        Assert.Equal("mapping_missing", result.Code); Assert.Empty(host.Http.Calls);
    }
    [Theory]
    [InlineData("0.000000", "1.000000")]
    [InlineData("1.0000001", "1.000000")]
    [InlineData("1.000000", "-1.000000")]
    [InlineData("1e3", "1.000000")]
    [InlineData("abc", "1.000000")]
    public async Task Invalid_quantity_or_price_never_reaches_the_provider(string quantity, string price)
    {
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString()));
        var result = await host.Invoke("Submit", Message(quantity, price));
        Assert.Equal("mapping_missing", result.Code); Assert.Empty(host.Http.Calls);
    }
    [Fact]
    public async Task Deliberate_zero_price_is_a_valid_frozen_price()
    {
        var message = Message(price: "0.000000");
        using var host = new Host((request, _) => request.Method == HttpMethod.Post ? Reply(Capture("po-ack").ToJsonString()) : Reply(Detail(message)));
        Assert.Equal("Completed", (await host.Invoke("Submit", message)).Outcome);
    }
    [Fact]
    public async Task Wrong_company_identity_holds_before_any_business_request()
    {
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString())) { };
        host.Http.Identity = "{\"idCompany\":999,\"cid\":\"SYNTH-CID-A\"}";
        var result = await host.Invoke("Submit", Message());
        Assert.Equal(("Failure", "identity_unverified"), (result.Outcome, result.Code)); Assert.Empty(host.Http.Calls);
    }
    [Theory]
    [InlineData("price")]
    [InlineData("quantity")]
    [InlineData("description")]
    [InlineData("reference")]
    [InlineData("vendor")]
    [InlineData("material")]
    [InlineData("storage")]
    [InlineData("vat")]
    [InlineData("type")]
    [InlineData("status")]
    [InlineData("id")]
    [InlineData("rows")]
    [InlineData("rowsEmpty")]
    public async Task Any_readback_mismatch_is_not_completed(string field)
    {
        var message = Message();
        using var host = new Host((request, _) => request.Method == HttpMethod.Post ? Reply(Capture("po-ack").ToJsonString()) : Reply(Detail(message, edit: (d, r) =>
        {
            switch (field)
            {
                case "price": r["price"] = 12.345679m; break;
                case "quantity": r["quantity"] = 3m; break;
                case "description": r["description"] = "altro"; break;
                case "reference": d["reference"] = "E360-PO-other"; break;
                case "vendor": d["idVendor"] = "other-vendor"; break;
                case "material": r["idMaterial"] = "other"; break;
                case "storage": r["idStorage"] = "XX"; break;
                case "vat": r["idVat"] = "10"; break;
                case "type": d["idDocumentType"] = 3; break;
                case "status": d["docStatus"] = "SENT"; break;
                case "id": d["id"] = 999; break;
                case "rows": d["rows"]!.AsArray().Add(r.DeepClone()); break;
                case "rowsEmpty": d["rows"] = new JsonArray(); break;
            }
        })));
        var result = await host.Invoke("Submit", message);
        Assert.Equal(("Failure", "readback_mismatch"), (result.Outcome, result.Code));
    }
    [Fact]
    public async Task Header_total_rounded_to_two_decimals_is_not_compared()
    {
        var message = Message(quantity: "1.000000");
        using var host = new Host((request, _) => request.Method == HttpMethod.Post ? Reply(Capture("po-ack").ToJsonString()) : Reply(Detail(message, edit: (d, _) => d["totalAmount"] = 0.01m)));
        Assert.Equal("Completed", (await host.Invoke("Submit", message)).Outcome);
    }
    [Theory]
    [InlineData("500")]
    [InlineData("empty")]
    [InlineData("malformed")]
    [InlineData("business-error")]
    [InlineData("no-id")]
    [InlineData("zero-id")]
    [InlineData("string-id")]
    public async Task Unsuccessful_or_unparseable_post_response_never_completes_and_never_posts_twice(string kind)
    {
        using var host = new Host((request, _) => kind switch
        {
            "500" => Reply("{\"errorCode\":500}", HttpStatusCode.InternalServerError),
            "empty" => Reply(""), "malformed" => Reply("{not json"),
            "business-error" => Reply("{\"errorCode\":324,\"responseCode\":400,\"idDocument\":301}"),
            "no-id" => Reply("{\"errorCode\":0,\"responseCode\":200}"), "zero-id" => Reply("{\"errorCode\":0,\"responseCode\":200,\"idDocument\":0}"),
            _ => Reply("{\"errorCode\":0,\"responseCode\":200,\"idDocument\":\"301\"}")
        });
        var result = await host.Invoke("Submit", Message());
        Assert.Equal("Failure", result.Outcome); Assert.Null(result.Reference);
        Assert.Single(host.Http.Calls); Assert.All(host.Http.Calls, c => Assert.Equal("POST", c.Method));
    }
    [Fact]
    public async Task Timeout_after_the_post_is_a_failure_not_a_second_post()
    {
        var message = Message();
        using var host = new Host((request, _) => throw new TaskCanceledException("timeout"));
        var result = await host.Invoke("Submit", message);
        Assert.Equal("Failure", result.Outcome); Assert.Single(host.Http.Calls);
    }
    [Fact]
    public async Task Only_the_declared_purchase_order_endpoints_are_generated()
    {
        var message = Message();
        using var host = new Host((request, _) => request.Method == HttpMethod.Post ? Reply(Capture("po-ack").ToJsonString()) : Reply(Detail(message)));
        await host.Invoke("Submit", message);
        Assert.All(host.Http.Calls, c => Assert.Matches(@"^(POST /purchases/orders\?simulation=false|GET /purchases/\d+/orders)$", c.Method + " " + c.Path));
    }

    // ---- S3: lost-success recovery is GET only. ----
    [Fact]
    public async Task Lost_success_is_recovered_by_vendor_name_lookup_and_exact_reference_then_readback_without_post()
    {
        var message = Message();
        using var host = new Host((request, _) => request.RequestUri!.AbsolutePath == "/purchases/orders"
            ? Reply(Page(Header(message, 301), Header(message, 201, "E360-SB-R05A5-other"))) : Reply(Detail(message)));
        var result = await host.Invoke("Status", message);
        Assert.Equal(["GET /purchases/orders?offset=0&limit=5&freeText=Owned%20Synthetic%20Vendor&docStatus=CREATED", "GET /purchases/301/orders"], host.Http.Calls.Select(x => x.Method + " " + x.Path));
        Assert.DoesNotContain(host.Http.Calls, c => c.Method == "POST");
        Assert.Equal(("Completed", null, "GiobbyPurchaseOrder-301"), result);
    }
    [Fact]
    public async Task Lookup_miss_is_uncertain_failure_and_never_a_second_post()
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Page(Header(message, 201, "E360-SB-R05A5-other"))));
        var result = await host.Invoke("Status", message);
        Assert.Equal(("Failure", "lookup_empty", null), result);
        Assert.Single(host.Http.Calls); Assert.Equal("GET", host.Http.Calls[0].Method);
    }
    [Fact]
    public async Task Full_page_without_the_exact_reference_is_held_as_truncated_not_absent()
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Page(Enumerable.Range(1, 5).Select(i => Header(message, 100 + i, "E360-PO-x" + i)).ToArray())));
        Assert.Equal("lookup_truncated", (await host.Invoke("Status", message)).Code);
    }
    [Fact]
    public async Task Duplicate_exact_references_are_nonunique_and_never_guessed()
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Page(Header(message, 301), Header(message, 302))));
        Assert.Equal("lookup_nonunique", (await host.Invoke("Status", message)).Code);
        Assert.Single(host.Http.Calls);
    }
    [Fact]
    public async Task A_matching_header_for_another_vendor_or_type_is_not_a_match()
    {
        var message = Message();
        var other = Header(message, 301).Replace($"\"idVendor\":\"{Vendor}\"", "\"idVendor\":\"someone-else\"");
        using var host = new Host((_, _) => Reply(Page(other, Header(message, 302).Replace("\"idDocumentType\":2", "\"idDocumentType\":3"))));
        Assert.Equal("lookup_empty", (await host.Invoke("Status", message)).Code);
    }
    [Theory]
    [InlineData("500")]
    [InlineData("empty")]
    [InlineData("malformed")]
    [InlineData("shape")]
    public async Task Unusable_lookup_response_is_a_failure_with_no_post(string kind)
    {
        using var host = new Host((_, _) => kind switch { "500" => Reply("{}", HttpStatusCode.InternalServerError), "empty" => Reply(""), "malformed" => Reply("[["), _ => Reply("{\"errorCode\":0,\"responseCode\":200}") });
        var result = await host.Invoke("Status", Message());
        Assert.Equal("Failure", result.Outcome); Assert.DoesNotContain(host.Http.Calls, c => c.Method == "POST");
    }
    [Fact]
    public async Task Recovered_order_with_different_price_is_a_mismatch_not_completed()
    {
        var message = Message();
        using var host = new Host((request, _) => request.RequestUri!.AbsolutePath == "/purchases/orders" ? Reply(Page(Header(message, 301))) : Reply(Detail(message, edit: (_, r) => r["price"] = 1m)));
        Assert.Equal("readback_mismatch", (await host.Invoke("Status", message)).Code);
    }

    // ---- S4: frozen destination binding. ----
    private static string Fingerprint(Action<Dictionary<string, string?>>? edit = null)
    {
        using var host = new Host((_, _) => Reply("{}"), edit);
        return host.Services.GetRequiredService<AdministrativeConnectorBinding>().DestinationFingerprint;
    }
    [Fact]
    public void Purchase_order_setup_is_excluded_from_the_frozen_sales_binding_fingerprint()
    {
        var baseline = Fingerprint();
        Assert.Equal(64, baseline.Length);
        Assert.Equal(baseline, Fingerprint(v => { v["Giobby:PurchaseOrder:BusinessUnit"] = "U2"; v["Giobby:PurchaseOrder:Storage"] = "XX"; v["Giobby:PurchaseOrder:Numerator"] = "3"; }));
        Assert.NotEqual(baseline, Fingerprint(v => v["Giobby:CompanyId"] = "102"));
    }
    [Fact]
    public async Task A_message_frozen_against_another_destination_is_refused_before_any_http()
    {
        var message = Message() with { DestinationFingerprint = new string('a', 64) };
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString()));
        foreach (var operation in new[] { "Submit", "Status" })
            Assert.Equal(("Failure", "destination_binding_mismatch"), ((await host.Invoke(operation, message)).Outcome, (await host.Invoke(operation, message)).Code));
        Assert.Empty(host.Http.Calls);
    }
    [Fact]
    public async Task Host_not_in_the_exact_allowlist_never_receives_business_traffic()
    {
        using var host = new Host((_, _) => Reply(Capture("po-ack").ToJsonString()), v => v["Giobby:AllowedHosts:0"] = "other.test");
        var result = await host.Invoke("Submit", Message());
        Assert.Equal("Failure", result.Outcome); Assert.Empty(host.Http.Calls);
    }
}
