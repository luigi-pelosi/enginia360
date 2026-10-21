using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Xunit;

public sealed class BrowserAuthenticationBoundaryTests
{
    [Fact]
    public async Task Development_login_flag_alone_does_not_publish_credential_surface()
    {
        using var factory = new BoundaryFactory(new() { ["DevelopmentTestLogin:Enabled"] = "true" });
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound,
            (await client.PostAsJsonAsync("/api/v1/development/login", new { })).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound,
            (await client.GetAsync("/api/v1/organization/database-session")).StatusCode);
    }

    [Fact]
    public async Task Default_application_does_not_publish_browser_authentication_endpoints()
    {
        using var factory = new BoundaryFactory(new());
        using var client = factory.CreateClient();
        foreach (var path in new[] { "/auth/session", "/auth/csrf", "/signin-oidc", "/signout-callback-oidc" })
            Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync(path)).StatusCode);
    }
}

public sealed class BoundaryFactory(Dictionary<string, string?> values) : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder) =>
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(values));
}
