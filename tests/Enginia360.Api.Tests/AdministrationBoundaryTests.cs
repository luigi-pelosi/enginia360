using System.Net;
using System.Net.Http.Json;
using Enginia360.Integrations;
using Enginia360.Workshop;
using Microsoft.AspNetCore.Hosting;
using Xunit;

public sealed class AdministrationBoundaryTests
{
    private const string Order = "/api/v1/workshop/orders/11111111-6666-0000-0000-000000000001";

    private static WebApplicationFactoryHandle Factory(bool external, string url = "http://admin-simulator:8080/")
    {
        var baseline = new TestApiFactory();
        var factory = baseline.WithWebHostBuilder(builder =>
        {
            builder.UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true").UseSetting("Inventory:Enabled", "true");
            if (external) builder.UseSetting("ExternalAdministration:Enabled", "true").UseSetting("ExternalAdministration:SimulatorBaseUrl", url)
                .UseSetting("ExternalAdministration:PollMilliseconds", "60000");
        });
        return new(baseline, factory);
    }

    [Theory]
    [InlineData("POST", "/technical-closure")]
    [InlineData("POST", "/administrative-requests")]
    [InlineData("GET", "/administrative-requests")]
    [InlineData("GET", "/closure-state")]
    [InlineData("POST", "/administrative-closure")]
    public async Task Administration_surface_requires_real_authentication_before_database_access(string method, string route)
    {
        using var handle = Factory(true);
        using var client = handle.Factory.CreateClient();
        using var request = new HttpRequestMessage(new HttpMethod(method), Order + route);
        if (method == "POST") request.Content = JsonContent.Create(new { id = Guid.NewGuid(), expectedRevision = 2 });
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(request)).StatusCode);
    }

    [Theory]
    [InlineData("/administrative-requests")]
    [InlineData("/closure-state")]
    public async Task External_request_surface_is_absent_without_the_connector(string route)
    {
        using var handle = Factory(false);
        using var client = handle.Factory.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(Order + route)).StatusCode);
    }

    [Theory]
    [InlineData("ftp://admin-simulator/")]
    [InlineData("http://user:secret@admin-simulator/")]
    [InlineData("http://admin-simulator:8080/v1?tenant=x")]
    [InlineData("not-a-url")]
    public void Connector_refuses_unsafe_or_ambiguous_remote_configuration(string url)
    {
        using var handle = Factory(true, url);
        Assert.ThrowsAny<InvalidOperationException>(() => handle.Factory.CreateClient());
    }

    [Fact]
    public void Integrations_exposes_registration_only_and_references_only_workshop_contracts()
    {
        var assembly = typeof(IntegrationsModule).Assembly;
        Assert.Equal([typeof(IntegrationsModule)], assembly.GetExportedTypes());
        Assert.DoesNotContain(assembly.GetReferencedAssemblies(), a => a.Name!.StartsWith("Enginia360.") && a.Name != "Enginia360.Workshop.Contracts");
        Assert.DoesNotContain(typeof(WorkshopModule).Assembly.GetReferencedAssemblies(), a => a.Name == "Enginia360.Integrations");
    }

    internal sealed class WebApplicationFactoryHandle(TestApiFactory baseline,
        Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactory<Program> factory) : IDisposable
    {
        internal Microsoft.AspNetCore.Mvc.Testing.WebApplicationFactory<Program> Factory { get; } = factory;
        public void Dispose()
        {
            Factory.Dispose();
            baseline.Dispose();
        }
    }
}
