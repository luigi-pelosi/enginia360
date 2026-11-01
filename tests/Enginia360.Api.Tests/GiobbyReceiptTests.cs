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

// D86 standalone receipt connector over owned R05.a.9 projections; transformed synthetic identifiers, no live traffic.
public sealed class GiobbyReceiptTests
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
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "tests/fixtures/r05a9-owned-captures.json"))) dir = dir.Parent;
        return JsonNode.Parse(File.ReadAllText(Path.Combine(dir!.FullName, "tests/fixtures/r05a9-owned-captures.json")))![name]!.DeepClone();
    }
    private static string Reference(ReceiptDispatchMessage m) => "E360-GR-" + m.ReceiptId.ToString("N");
    // The owned receipt-detail projection, with only identifiers/amounts replaced to describe the message under test (synthetic transformation).
    private static string Detail(ReceiptDispatchMessage m, int id = 902, Action<JsonObject, JsonObject>? edit = null)
    {
        var root = Capture("receipt-detail").AsObject(); var d = root["document"]!.AsObject(); var row = d["rows"]![0]!.AsObject();
        d["id"] = id; d["docNumber"] = Reference(m); d["reference"] = Reference(m); d["idVendor"] = m.VendorId;
        row["description"] = m.Description; row["quantity"] = decimal.Parse(m.Quantity, System.Globalization.CultureInfo.InvariantCulture);
        row["price"] = decimal.Parse(m.UnitPrice, System.Globalization.CultureInfo.InvariantCulture);
        edit?.Invoke(d, row);
        return root.ToJsonString();
    }
    private static ReceiptDispatchMessage Message(string quantity = "0.123456", string price = "12.345678", Guid? tenant = null)
    {
        var host = new Host((_, _) => Reply("{}")); // only to learn the frozen binding fingerprint of the host fixture
        var type = typeof(IntegrationsModule).Assembly.GetType("Enginia360.Integrations.GiobbyHost")!;
        var fingerprint = (string)type.GetProperty("ReceiptFingerprint", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(host.Services.GetRequiredService(type))!; host.Dispose();
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
                ["Giobby:Receipt:DocumentType"] = "0", ["Giobby:Receipt:OrderType"] = "1", ["Giobby:Receipt:BusinessUnit"] = "owned-bu-A",
                ["Giobby:Receipt:Numerator"] = "71", ["Giobby:Receipt:PosType"] = "1", ["Giobby:Receipt:Payments"] = "none",
                ["Giobby:Receipt:Currency"] = "EUR", ["Giobby:Receipt:Vat"] = "owned-vat-A", ["Giobby:Receipt:Storage"] = "owned-storage-A",
                [$"Giobby:Receipt:Materials:{Item}"] = "owned-material-A"
            };
            edit?.Invoke(values);
            var config = new ConfigurationBuilder().AddInMemoryCollection(values).Build();
            var services = new ServiceCollection(); services.AddLogging(); services.AddExternalAdministration("Host=unused;Database=unused", config);
            Http = new Wire(reply);
            services.AddHttpClient("GiobbyReceiptConnector").ConfigurePrimaryHttpMessageHandler(() => Http);
            Services = services.BuildServiceProvider();
        }
        internal async Task<(string Outcome, string? Code, string? Reference)> Invoke(string operation, ReceiptDispatchMessage m)
        {
            var connectorType = typeof(IntegrationsModule).Assembly.GetType("Enginia360.Integrations.GiobbyReceiptConnector")!;
            var connector = Services.GetRequiredService(connectorType);
            var method = connector.GetType().GetMethod(operation, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)!;
            var task = (Task)method.Invoke(connector, [m, CancellationToken.None])!; await task;
            var result = task.GetType().GetProperty("Result")!.GetValue(task)!;
            return (result.GetType().GetProperty("Outcome")!.GetValue(result)!.ToString()!, (string?)result.GetType().GetProperty("Code")!.GetValue(result), (string?)result.GetType().GetProperty("ExternalReference")!.GetValue(result));
        }
        public void Dispose() { Services.Dispose(); File.Delete(token); }
    }

    [Fact]
    public async Task Non_numeric_ack_is_unknown_not_an_unhandled_exception()
    {
        using var host=new Host((_,_)=>Reply("{\"responseCode\":200,\"errorCode\":0,\"idDocument\":\"902\"}"));
        Assert.Equal(("Failure","ack_unknown",(string?)null),await host.Invoke("Submit",Message()));
    }
    [Fact]
    public void Receipt_readout_exposes_technical_hold_without_promoting_it_into_business_confirmation()
    {
        var id=Guid.NewGuid();var state=JsonNode.Parse("{\"state\":\"ready\",\"receipts\":[{\"id\":\""+id+"\",\"status\":\"PendingUnconfirmed\"}]}")!.AsObject();
        ReceiptDispatchReadout.Apply(state,new Dictionary<Guid,ReceiptDelivery>{{id,new("Uncertain","ack_unknown_hold",null)}});
        Assert.NotNull(state["receipts"]![0]!["delivery"]);
        Assert.Equal("ack_unknown_hold",state["receipts"]![0]!["delivery"]!["lastError"]!.GetValue<string>());
        Assert.Equal("PendingUnconfirmed",state["receipts"]![0]!["status"]!.GetValue<string>());
    }
    [Theory]
    [InlineData("500")]
    [InlineData("timeout")]
    [InlineData("malformed")]
    public async Task Unknown_post_effect_remains_held_and_status_never_posts_again(string mode)
    {
        var message=Message();
        using var host=new Host((r,_)=>r.Method==HttpMethod.Post ? mode switch {
            "500"=>Reply("{}",HttpStatusCode.InternalServerError),"timeout"=>throw new TaskCanceledException(),_=>Reply("{broken")
        } : Reply(Capture("receipt-lookup").ToJsonString()));
        Assert.Equal(("Failure","ack_unknown",(string?)null),await host.Invoke("Submit",message));
        for(var i=0;i<2;i++)Assert.Equal(("Failure","ack_unknown_hold",(string?)null),await host.Invoke("Status",message));
        Assert.Single(host.Http.Calls,c=>c.Method=="POST");
    }
    [Fact]
    public async Task Known_ack_temporary_get_failure_retries_only_that_exact_detail()
    {
        var message=Message() with { KnownDocumentId=902 };
        using var host=new Host((_,n)=> n==1 ? Reply("{}",HttpStatusCode.InternalServerError) : Reply(Detail(message)));
        Assert.Equal("Failure",(await host.Invoke("Status",message)).Outcome);
        Assert.Equal("Completed",(await host.Invoke("Status",message)).Outcome);
        Assert.All(host.Http.Calls,c=>Assert.Equal(("GET","/purchases/902/goodsreceipt?onlyHeaderData=false"),(c.Method,c.Path)));
    }
    [Fact]
    public void Receipt_mapping_changes_invalidate_only_the_receipt_binding_not_existing_sales_or_purchase_bindings()
    {
        using var a = new Host((_,_)=>Reply("{}"));
        using var b = new Host((_,_)=>Reply("{}"), v=>v["Giobby:Receipt:Storage"]="other");
        var t = typeof(IntegrationsModule).Assembly.GetType("Enginia360.Integrations.GiobbyHost")!;
        string F(Host h,string property) => (string)t.GetProperty(property, BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(h.Services.GetRequiredService(t))!;
        Assert.NotEqual(F(a,"ReceiptFingerprint"),F(b,"ReceiptFingerprint"));
        Assert.Equal(a.Services.GetRequiredService<AdministrativeConnectorBinding>(),b.Services.GetRequiredService<AdministrativeConnectorBinding>());
        Assert.Equal(F(a,"PurchaseFingerprint"),F(b,"PurchaseFingerprint"));
    }
    [Theory]
    [InlineData("Giobby:Receipt:DocumentType", "5")]
    [InlineData("Giobby:Receipt:Storage", null)]
    [InlineData("Giobby:Receipt:BusinessUnit", null)]
    [InlineData("Giobby:Receipt:Numerator", null)]
    [InlineData("Giobby:Receipt:PosType", null)]
    [InlineData("Giobby:Receipt:Vat", null)]
    public async Task Unsupported_type5_or_incomplete_receipt_setup_is_refused_before_identity_or_business_http(string key, string? value)
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Capture("receipt-ack").ToJsonString()), v => v[key] = value);
        foreach (var operation in new[] { "Submit", "Status" })
            Assert.Equal(("NotSent", "mapping_missing", (string?)null), await host.Invoke(operation, message));
        Assert.Empty(host.Http.Calls);
    }
    [Fact]
    public async Task Changed_receipt_binding_refuses_submit_and_status_before_http()
    {
        var message = Message() with { DestinationFingerprint = new string('f', 64) };
        using var host = new Host((_, _) => Reply(Capture("receipt-ack").ToJsonString()));
        foreach (var operation in new[] { "Submit", "Status" })
            Assert.Equal(("NotSent", "destination_binding_mismatch", (string?)null), await host.Invoke(operation, message));
        Assert.Empty(host.Http.Calls);
    }
    [Fact]
    public async Task Unknown_ack_uses_declared_capped_get_only_and_empty_never_means_absence()
    {
        var message = Message();
        using var host = new Host((_, _) => Reply(Capture("receipt-lookup").ToJsonString()));
        Assert.Equal(("Failure", "ack_unknown_hold", (string?)null), await host.Invoke("Status", message));
        Assert.Equal(["GET /purchases/goodsreceipt?offset=0&limit=5&freeText=" + Reference(message)], host.Http.Calls.Select(c => c.Method + " " + c.Path));
    }
    [Theory]
    [InlineData("type")]
    [InlineData("quantity")]
    [InlineData("price")]
    [InlineData("vendor")]
    [InlineData("reference")]
    [InlineData("storage")]
    [InlineData("vat")]
    [InlineData("material")]
    [InlineData("bu")]
    [InlineData("numerator")]
    [InlineData("number")]
    public async Task Exact_receipt_detail_mismatches_hold_including_type5_and_independent_q6_fields(string field)
    {
        var message = Message() with { KnownDocumentId = 902 };
        using var host = new Host((_, _) => Reply(Detail(message, edit: (d,r) => {
            switch (field) {
                case "type": d["idDocumentType"] = 5; break;
                case "quantity": r["quantity"] = 0.12346m; break;
                case "price": r["price"] = 12.345679m; break;
                case "vendor": d["idVendor"] = "other"; break;
                case "reference": d["reference"] = "other"; break;
                case "storage": r["idStorage"] = "other"; break;
                case "vat": r["idVat"] = "other"; break;
                case "material": r["idMaterial"] = "other"; break;
                case "bu": d["idBu"] = "other"; break;
                case "numerator": d["idNumerator"] = 72; break;
                case "number": d["docNumber"] = "other"; break;
            }
        })));
        Assert.Equal(("Failure", "readback_mismatch", (string?)null), await host.Invoke("Status",message));
        Assert.DoesNotContain(host.Http.Calls,c=>c.Method=="POST");
    }

    [Fact]
    public async Task Type0_receipt_ack_is_not_confirmation_and_known_ack_detail_alone_confirms()
    {
        var message = Message();
        using var host = new Host((r, _) => r.Method == HttpMethod.Post ? Reply(Capture("receipt-ack").ToJsonString()) : Reply(Detail(message)));
        var ack = await host.Invoke("Submit", message);
        Assert.Equal(("Failure", "ack_pending", "GiobbyReceipt-902"), ack);
        Assert.Equal(["POST /purchases/goodsreceipt"], host.Http.Calls.Select(c => c.Method + " " + c.Path));
        using var body = JsonDocument.Parse(host.Http.Calls[0].Body!);
        Assert.Equal(0, body.RootElement.GetProperty("idDocumentType").GetInt32());
        Assert.True(body.RootElement.TryGetProperty("payments",out var payments),"captured receipt request requires explicit payments");
        Assert.Empty(payments.EnumerateArray());
        Assert.Equal(JsonValueKind.Null,body.RootElement.GetProperty("idContact").ValueKind);
        Assert.Equal("EUR",body.RootElement.GetProperty("docCurrency").GetString());
        Assert.Equal(0,body.RootElement.GetProperty("rows")[0].GetProperty("idAttributeCombination").GetInt32());
        Assert.Equal("0.123456", body.RootElement.GetProperty("rows")[0].GetProperty("quantity").GetRawText());
        Assert.Equal("12.345678", body.RootElement.GetProperty("rows")[0].GetProperty("price").GetRawText());
        Assert.Equal(("Completed", (string?)null, "GiobbyReceipt-902"), await host.Invoke("Status", message with { KnownDocumentId = 902 }));
        Assert.Equal("GET /purchases/902/goodsreceipt?onlyHeaderData=false", host.Http.Calls[1].Method + " " + host.Http.Calls[1].Path);
    }
}
