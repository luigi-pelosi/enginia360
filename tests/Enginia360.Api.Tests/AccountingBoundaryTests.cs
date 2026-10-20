using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class AccountingBoundaryTests
{
    private const string Entries = "/api/v1/accounting/invoice-journal-entries";

    [Theory]
    [InlineData("POST", Entries)]
    [InlineData("GET", Entries + "/11111111-8888-0000-0000-000000000001")]
    public async Task Technical_accounting_surface_requires_real_authentication_before_database_access(
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
                .UseSetting("TechnicalAccounting:Enabled", "true")
        );
        using var client = factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        if (method == "POST")
            request.Content = JsonContent.Create(new
            {
                id = Guid.NewGuid(),
                invoiceId = Guid.NewGuid(),
                chartVersion = 1,
            });

        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }

    [Fact]
    public async Task Technical_accounting_requires_internal_billing()
    {
        using var baseline = new TestApiFactory();
        using var factory = baseline.WithWebHostBuilder(builder =>
            builder
                .UseSetting("Workshop:Enabled", "true")
                .UseSetting("Counterparties:Enabled", "true")
                .UseSetting("Inventory:Enabled", "true")
                .UseSetting("InternalBilling:Enabled", "false")
                .UseSetting("TechnicalAccounting:Enabled", "true")
        );

        var failure = await Assert.ThrowsAsync<InvalidOperationException>(async () =>
        {
            using var client = factory.CreateClient();
            await client.GetAsync("/api/v1/system/status");
        });
        Assert.Contains("Technical accounting requires internal billing", failure.Message);
    }
}
