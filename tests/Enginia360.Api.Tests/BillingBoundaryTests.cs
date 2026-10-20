using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class BillingBoundaryTests
{
    private const string Invoice = "/api/v1/billing/workshop-invoices";

    [Theory]
    [InlineData("POST", Invoice)]
    [InlineData("GET", Invoice + "/11111111-7777-0000-0000-000000000001")]
    [InlineData("POST", Invoice + "/11111111-7777-0000-0000-000000000001/confirmation")]
    public async Task Internal_billing_surface_requires_real_authentication_before_database_access(
        string method,
        string path
    )
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder =>
            builder
                .UseSetting("Workshop:Enabled", "true")
                .UseSetting("Counterparties:Enabled", "true")
                .UseSetting("Inventory:Enabled", "true")
                .UseSetting("InternalBilling:Enabled", "true")
        );
        using var client = factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method == "POST")
            request.Content = JsonContent.Create(new
            {
                id = Guid.NewGuid(),
                orderId = Guid.NewGuid(),
                documentTypeId = Guid.NewGuid(),
                configurationVersion = 1,
                documentDate = "2026-10-20",
                currency = "EUR",
                reference = "FV-001/2026",
            });

        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }
}