using System.Net.Http.Json;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public sealed class BootstrapTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient client;

    public BootstrapTests(WebApplicationFactory<Program> factory) =>
        client = factory.CreateClient();

    [Fact]
    public async Task Status_discloses_bootstrap_scope_without_claiming_product_readiness()
    {
        var response = await client.GetAsync("/api/v1/system/status");
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadFromJsonAsync<System.Text.Json.JsonElement>();
        Assert.Equal("Enginia360", body.GetProperty("product").GetString());
        Assert.Equal("bootstrap", body.GetProperty("stage").GetString());
        Assert.False(body.GetProperty("foundationDossierApproved").GetBoolean());
        Assert.False(body.GetProperty("businessCapabilitiesAvailable").GetBoolean());
    }

    [Theory]
    [InlineData("/health/live")]
    [InlineData("/health/ready")]
    public async Task Health_reports_process_readiness_only(string path)
    {
        var response = await client.GetAsync(path);
        response.EnsureSuccessStatusCode();
        Assert.Equal("Healthy", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task OpenApi_describes_public_status_endpoint()
    {
        var response = await client.GetAsync("/openapi/v1.json");
        response.EnsureSuccessStatusCode();
        var body = await response.Content.ReadFromJsonAsync<System.Text.Json.JsonElement>();
        Assert.True(body.GetProperty("paths").TryGetProperty("/api/v1/system/status", out _));
    }

    [Theory]
    [InlineData("/api/v1/development/login", "POST")]
    [InlineData("/api/v1/organization/database-session", "GET")]
    public async Task Development_only_endpoints_are_not_mapped_by_default(
        string path,
        string method
    )
    {
        using var request = new HttpRequestMessage(new HttpMethod(method), path);
        var response = await client.SendAsync(request);
        Assert.Equal(System.Net.HttpStatusCode.NotFound, response.StatusCode);
    }

    [Theory]
    [InlineData("request-123_ABC", true)]
    [InlineData("bad id", false)]
    [InlineData("<script>", false)]
    [InlineData("", false)]
    [InlineData("first,second", false)]
    public async Task Correlation_accepts_only_bounded_safe_tokens(string candidate, bool accepted)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "/api/v1/system/status");
        request.Headers.TryAddWithoutValidation("X-Correlation-ID", candidate);
        var response = await client.SendAsync(request);
        var actual = Assert.Single(response.Headers.GetValues("X-Correlation-ID"));
        if (accepted)
            Assert.Equal(candidate, actual);
        else
            Assert.Matches("^[a-f0-9]{32}$", actual);
    }

    [Fact]
    public async Task Correlation_replaces_oversized_and_multiple_tokens()
    {
        foreach (var values in new[] { new[] { new string('a', 65) }, new[] { "first", "second" } })
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, "/missing");
            request.Headers.TryAddWithoutValidation("X-Correlation-ID", values);
            var response = await client.SendAsync(request);
            Assert.Matches(
                "^[a-f0-9]{32}$",
                Assert.Single(response.Headers.GetValues("X-Correlation-ID"))
            );
        }
    }
}
