using System.Net;
using System.Net.Http.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

public sealed class BrowserSessionTests
{
    internal static Dictionary<string, string?> Settings() => new()
    {
        ["BrowserSessions:Enabled"] = "true",
        ["BrowserSessions:PublicOrigin"] = "https://localhost",
        ["BrowserSessions:Authority"] = "https://issuer.test/realms/runtime",
        ["BrowserSessions:ClientId"] = "runtime-browser",
        ["BrowserSessions:ClientSecret"] = "synthetic-test-only-secret",
    };

    internal sealed class BrowserFactory(Dictionary<string, string?>? overrides = null)
        : WebApplicationFactory<Program>
    {
        internal readonly System.Security.Cryptography.RSA SigningKey = System.Security.Cryptography.RSA.Create(2048);
        internal string? Nonce;
        internal string TokenKind = "valid";
        internal string MetadataKind = "valid";
        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            var values = Settings();
            if (overrides is not null)
                foreach (var pair in overrides)
                    values[pair.Key] = pair.Value;
            foreach (var pair in values)
                builder.UseSetting(pair.Key, pair.Value);
            builder.ConfigureServices(services => services.Configure<Microsoft.AspNetCore.Authentication.OpenIdConnect.OpenIdConnectOptions>("oidc", options =>
            {
                options.Configuration = new Microsoft.IdentityModel.Protocols.OpenIdConnect.OpenIdConnectConfiguration
                {
                    Issuer = MetadataKind == "issuer" ? "https://wrong.test" : "https://issuer.test/realms/runtime",
                    AuthorizationEndpoint = "https://issuer.test/realms/runtime/authorize",
                    TokenEndpoint = MetadataKind == "token" ? "http://issuer.test/token" : "https://issuer.test/realms/runtime/token",
                    JwksUri = MetadataKind == "jwks" ? "http://issuer.test/keys" : "https://issuer.test/realms/runtime/keys",
                };
                options.Configuration.SigningKeys.Add(new Microsoft.IdentityModel.Tokens.RsaSecurityKey(SigningKey) { KeyId = "test-key" });
                options.Backchannel = new HttpClient(new TokenHandler(this));
            }));
        }

        private sealed class TokenHandler(BrowserFactory factory) : HttpMessageHandler
        {
            protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            {
                using var wrongKey = System.Security.Cryptography.RSA.Create(2048);
                var now = DateTime.UtcNow;
                var token = new System.IdentityModel.Tokens.Jwt.JwtSecurityToken(
                    issuer: factory.TokenKind == "issuer" ? "https://wrong.test" : "https://issuer.test/realms/runtime",
                    audience: factory.TokenKind == "audience" ? "wrong-client" : "runtime-browser",
                    claims: [new("iat", new DateTimeOffset(now).ToUnixTimeSeconds().ToString(), System.Security.Claims.ClaimValueTypes.Integer64), new("sub", "opaque-external-subject"), new("nonce", factory.TokenKind == "nonce" ? "wrong" : factory.Nonce!)],
                    notBefore: factory.TokenKind == "future" ? now.AddMinutes(10) : now.AddMinutes(-5),
                    expires: factory.TokenKind == "expired" ? now.AddMinutes(-1) : now.AddMinutes(15),
                    signingCredentials: new(new Microsoft.IdentityModel.Tokens.RsaSecurityKey(factory.TokenKind == "signature" ? wrongKey : factory.SigningKey) { KeyId = "test-key" }, "RS256"));
                return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = JsonContent.Create(new { token_type = "Bearer", access_token = "server-only-test-access", id_token = new System.IdentityModel.Tokens.Jwt.JwtSecurityTokenHandler().WriteToken(token) }),
                });
            }
        }
    }

    [Fact]
    public async Task Browser_profile_exposes_anonymous_session_and_secure_antiforgery()
    {
        await using var factory = new BrowserFactory();
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false });
        var session = await client.GetAsync("/auth/session");
        Assert.Equal(HttpStatusCode.OK, session.StatusCode);
        Assert.False((await session.Content.ReadFromJsonAsync<Session>())!.Authenticated);
        Assert.Equal("no-store", session.Headers.CacheControl!.ToString());
        var csrf = await client.GetAsync("/auth/csrf");
        Assert.Equal(HttpStatusCode.OK, csrf.StatusCode);
        var cookie = Assert.Single(csrf.Headers.GetValues("Set-Cookie"));
        Assert.StartsWith("__Host-enginia360-csrf=", cookie);
        Assert.Contains("secure", cookie);
        Assert.Contains("httponly", cookie);
        Assert.Contains("samesite=strict", cookie);
        Assert.DoesNotContain("domain=", cookie);
        Assert.False(string.IsNullOrEmpty((await csrf.Content.ReadFromJsonAsync<Csrf>())!.RequestToken));
    }

    [Theory]
    [InlineData("/auth/login")]
    [InlineData("/auth/logout")]
    [InlineData("/AUTH/LOGIN/")]
    [InlineData("/auth/logout/")]
    public async Task Browser_commands_require_real_antiforgery(string path)
    {
        await using var factory = new BrowserFactory();
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false });
        var response = await client.PostAsync(path, new FormUrlEncodedContent([]));
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Contains("csrf_invalid", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Http_and_forged_forwarding_headers_cannot_access_authentication()
    {
        await using var factory = new BrowserFactory();
        using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
        client.DefaultRequestHeaders.Add("X-Forwarded-Proto", "https");
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/auth/csrf")).StatusCode);
    }

    [Theory]
    [InlineData("Authentication:Profile", "SyntheticLegacy")]
    [InlineData("BrowserSessions:PublicOrigin", "http://localhost")]
    [InlineData("BrowserSessions:Authority", "http://issuer.test")]
    [InlineData("BrowserSessions:ClientSecret", "")]
    [InlineData("Authentication:Audience", "runtime-browser")]
    public async Task Unsafe_browser_configuration_is_rejected(string key, string value)
    {
        await using var factory = new BrowserFactory(new() { [key] = value });
        Assert.ThrowsAny<Exception>(() => factory.CreateClient());
    }

    [Fact]
    public async Task Valid_login_uses_official_code_S256_state_nonce_without_browser_tokens()
    {
        await using var factory = new BrowserFactory();
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false });
        var csrf = (await client.GetFromJsonAsync<Csrf>("/auth/csrf"))!.RequestToken;
        var response = await client.PostAsync("/auth/login", new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["__RequestVerificationToken"] = csrf,
        }));
        Assert.Equal(HttpStatusCode.Redirect, response.StatusCode);
        var query = Microsoft.AspNetCore.WebUtilities.QueryHelpers.ParseQuery(response.Headers.Location!.Query);
        Assert.Equal("code", query["response_type"]);
        Assert.Equal("S256", query["code_challenge_method"]);
        Assert.Equal("openid", query["scope"]);
        Assert.Equal("https://localhost/signin-oidc", query["redirect_uri"]);
        Assert.False(string.IsNullOrEmpty(query["state"]));
        Assert.False(string.IsNullOrEmpty(query["nonce"]));
        Assert.False(string.IsNullOrEmpty(query["code_challenge"]));
        Assert.False(query.ContainsKey("client_secret"));
        Assert.False(query.ContainsKey("code_verifier"));
        Assert.Equal(HttpStatusCode.MethodNotAllowed, (await client.GetAsync("/auth/logout")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync("/signin-oidc?code=forged&state=forged")).StatusCode);
    }

    [Fact]
    public async Task Ticket_store_does_not_renew_or_resurrect_revoked_tickets_and_is_process_local()
    {
        await using var factory = new BrowserFactory();
        var store = factory.Services.GetRequiredService<Microsoft.AspNetCore.Authentication.Cookies.ITicketStore>();
        var ticket = new Microsoft.AspNetCore.Authentication.AuthenticationTicket(
            new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity("browser")),
            new() { ExpiresUtc = DateTimeOffset.UtcNow.AddMinutes(15) }, "browser");
        var key = await store.StoreAsync(ticket);
        Assert.NotNull(await store.RetrieveAsync(key));
        await store.RemoveAsync(key);
        await store.RenewAsync(key, ticket);
        Assert.Null(await store.RetrieveAsync(key));
        await using var other = new BrowserFactory();
        Assert.Null(await other.Services.GetRequiredService<Microsoft.AspNetCore.Authentication.Cookies.ITicketStore>().RetrieveAsync(key));
    }

    [Theory]
    [InlineData("valid", HttpStatusCode.ServiceUnavailable)]
    [InlineData("signature", HttpStatusCode.BadRequest)]
    [InlineData("issuer", HttpStatusCode.BadRequest)]
    [InlineData("audience", HttpStatusCode.BadRequest)]
    [InlineData("expired", HttpStatusCode.BadRequest)]
    [InlineData("future", HttpStatusCode.BadRequest)]
    [InlineData("nonce", HttpStatusCode.BadRequest)]
    public async Task Real_oidc_validation_precedes_binding_and_never_signs_in_on_store_outage(string kind, HttpStatusCode expected)
    {
        await using var factory = new BrowserFactory { TokenKind = kind };
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false });
        var csrf = (await client.GetFromJsonAsync<Csrf>("/auth/csrf"))!.RequestToken;
        var challenge = await client.PostAsync("/auth/login", new FormUrlEncodedContent(new Dictionary<string, string> { ["__RequestVerificationToken"] = csrf }));
        var query = Microsoft.AspNetCore.WebUtilities.QueryHelpers.ParseQuery(challenge.Headers.Location!.Query);
        factory.Nonce = query["nonce"];
        var callback = "/signin-oidc?code=synthetic-code&state=" + Uri.EscapeDataString(query["state"]!);
        var response = await client.GetAsync(callback);
        Assert.Equal(expected, response.StatusCode);
        Assert.DoesNotContain(response.Headers.TryGetValues("Set-Cookie", out var cookies) ? cookies : [], value => value.StartsWith("__Host-enginia360-session="));
        Assert.False((await client.GetFromJsonAsync<Session>("/auth/session"))!.Authenticated);
        Assert.Equal(HttpStatusCode.BadRequest, (await client.GetAsync(callback)).StatusCode);
    }

    [Fact]
    public async Task Cookie_binding_is_revalidated_fail_closed_and_fake_bearer_never_falls_back()
    {
        await using var factory = new BrowserFactory();
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false, HandleCookies = false });
        var store = factory.Services.GetRequiredService<Microsoft.AspNetCore.Authentication.Cookies.ITicketStore>();
        var principal = new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
            new(System.Security.Claims.ClaimTypes.NameIdentifier, Guid.NewGuid().ToString("D")),
            new(Enginia360.Api.BrowserAuthentication.ExternalIdentityResolver.IssuerClaim, "https://issuer.test/realms/runtime"),
            new(Enginia360.Api.BrowserAuthentication.ExternalIdentityResolver.SubjectClaim, "opaque-external-subject"),
        ], "browser"));
        var key = await store.StoreAsync(new(principal, new() { ExpiresUtc = DateTimeOffset.UtcNow.AddMinutes(15) }, "browser"));
        var reference = new Microsoft.AspNetCore.Authentication.AuthenticationTicket(
            new(new System.Security.Claims.ClaimsIdentity([new("Microsoft.AspNetCore.Authentication.Cookies-SessionId", key)], "browser")), "browser");
        var options = factory.Services.GetRequiredService<Microsoft.Extensions.Options.IOptionsMonitor<Microsoft.AspNetCore.Authentication.Cookies.CookieAuthenticationOptions>>().Get("browser");
        client.DefaultRequestHeaders.Add("Cookie", "__Host-enginia360-session=" + options.TicketDataFormat.Protect(reference));
        Assert.Equal(HttpStatusCode.ServiceUnavailable, (await client.GetAsync("/auth/session")).StatusCode);
        client.DefaultRequestHeaders.Add("Authorization", "Bearer not-a-token");
        var response = await client.GetAsync("/api/v1/organization/contexts");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Null(response.Headers.Location);
    }

    [Theory]
    [InlineData("issuer")]
    [InlineData("token")]
    [InlineData("jwks")]
    public async Task Invalid_discovery_never_redirects_or_exchanges_confidential_credentials(string kind)
    {
        await using var factory = new BrowserFactory { MetadataKind = kind };
        using var client = factory.CreateClient(new() { BaseAddress = new("https://localhost"), AllowAutoRedirect = false });
        var token = (await client.GetFromJsonAsync<Csrf>("/auth/csrf"))!.RequestToken;
        var response = await client.PostAsync("/auth/login", new FormUrlEncodedContent(new Dictionary<string, string> { ["__RequestVerificationToken"] = token }));
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Null(response.Headers.Location);
    }

    private sealed record Session(bool Authenticated);
    private sealed record Csrf(string RequestToken);
}
