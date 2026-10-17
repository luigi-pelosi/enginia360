using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.IdentityModel.Protocols;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;
using Microsoft.IdentityModel.Tokens;
using Xunit;

public sealed class AuthorizedContextContractTests : IClassFixture<TestApiFactory>
{
    private readonly HttpClient client;
    private readonly TestApiFactory factory;

    public AuthorizedContextContractTests(TestApiFactory factory)
    {
        this.factory = factory;
        client = factory.CreateClient();
    }

    [Fact]
    public async Task Anonymous_requests_cannot_read_organizational_contexts() =>
        Assert.Equal(
            HttpStatusCode.Unauthorized,
            (await client.GetAsync("/api/v1/organization/contexts")).StatusCode
        );

    [Fact]
    public async Task Client_identity_headers_are_not_accepted_as_authentication()
    {
        using var r = new HttpRequestMessage(HttpMethod.Get, "/api/v1/organization/contexts");
        r.Headers.TryAddWithoutValidation("X-User-Id", "x");
        r.Headers.TryAddWithoutValidation("X-Tenant-Id", "x");
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.SendAsync(r)).StatusCode);
    }

    public static IEnumerable<object[]> InvalidTokens()
    {
        yield return ["wrong-signature"];
        yield return ["wrong-issuer"];
        yield return ["wrong-audience"];
        yield return ["expired"];
        yield return ["not-yet-valid"];
    }

    [Theory, MemberData(nameof(InvalidTokens))]
    public async Task Invalid_jwt_is_rejected_by_real_authentication_pipeline(string kind)
    {
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue(
            "Bearer",
            factory.Token(kind)
        );
        Assert.Equal(
            HttpStatusCode.Unauthorized,
            (await client.GetAsync("/api/v1/organization/contexts")).StatusCode
        );
    }

    [Fact]
    public void Identity_subject_is_globally_unique_for_b02()
    {
        using var scope = factory.Services.CreateScope();
        var model = scope
            .ServiceProvider.GetRequiredService<Enginia360.Api.OrganizationAccess.OrganizationAccessDbContext>()
            .Model;
        var membership = model.FindEntityType(
            typeof(Enginia360.Api.OrganizationAccess.Membership)
        )!;
        Assert.Contains(
            membership.GetIndexes(),
            index =>
                index.IsUnique
                && index
                    .Properties.Select(property => property.Name)
                    .SequenceEqual([
                        nameof(Enginia360.Api.OrganizationAccess.Membership.IdentitySubject),
                    ])
        );
    }

    [Fact]
    public void Note_message_check_matches_database_baseline()
    {
        using var scope = factory.Services.CreateScope();
        var model = scope
            .ServiceProvider.GetRequiredService<Enginia360.Api.OrganizationAccess.OrganizationAccessDbContext>()
            .GetService<Microsoft.EntityFrameworkCore.Metadata.IDesignTimeModel>()
            .Model;
        var note = model.FindEntityType(typeof(Enginia360.Api.OrganizationAccess.ContextNote))!;
        Assert.Contains(
            note.GetCheckConstraints(),
            constraint => constraint.Sql == "length(btrim(\"Message\")) BETWEEN 1 AND 200"
        );
    }

    [Fact]
    public void Capability_activation_references_its_legal_entity()
    {
        using var scope = factory.Services.CreateScope();
        var model = scope
            .ServiceProvider.GetRequiredService<Enginia360.Api.OrganizationAccess.OrganizationAccessDbContext>()
            .Model;
        var activation = model.FindEntityType(
            typeof(Enginia360.Api.OrganizationAccess.CapabilityActivation)
        )!;
        Assert.Contains(
            activation.GetForeignKeys(),
            foreignKey =>
                foreignKey.PrincipalEntityType.ClrType
                    == typeof(Enginia360.Api.OrganizationAccess.LegalEntity)
                && foreignKey
                    .Properties.Select(property => property.Name)
                    .SequenceEqual([
                        nameof(
                            Enginia360.Api.OrganizationAccess.CapabilityActivation.LegalEntityId
                        ),
                    ])
        );
    }
}

public sealed class TestApiFactory : WebApplicationFactory<Program>
{
    private readonly RSA rsa = RSA.Create(2048);
    private readonly RsaSecurityKey key;
    private const string Issuer = "https://issuer.test/real-config",
        Audience = "enginia360-api";

    public TestApiFactory() => key = new RsaSecurityKey(rsa) { KeyId = "test-key" };

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration(
            (_, c) =>
                c.AddInMemoryCollection(
                    new Dictionary<string, string?>
                    {
                        {
                            "ConnectionStrings:OrganizationAccess",
                            "Host=127.0.0.1;Database=unused;Username=unused;Password=unused"
                        },
                        { "Authentication:ValidIssuer", Issuer },
                        { "Authentication:Audience", Audience },
                        { "Authentication:RequireHttpsMetadata", "false" },
                    }
                )
        );
        builder.ConfigureServices(s =>
            s.PostConfigure<JwtBearerOptions>(
                JwtBearerDefaults.AuthenticationScheme,
                o =>
                    o.ConfigurationManager =
                        new StaticConfigurationManager<OpenIdConnectConfiguration>(
                            new OpenIdConnectConfiguration
                            {
                                Issuer = Issuer,
                                SigningKeys = { key },
                            }
                        )
            )
        );
    }

    public string Token(string kind)
    {
        var now = DateTime.UtcNow;
        var signing =
            kind == "wrong-signature"
                ? new RsaSecurityKey(RSA.Create(2048)) { KeyId = "other" }
                : key;
        var descriptor = new SecurityTokenDescriptor
        {
            Subject = new ClaimsIdentity([new Claim(JwtRegisteredClaimNames.Sub, "subject")]),
            Issuer = kind == "wrong-issuer" ? "https://wrong.invalid" : Issuer,
            Audience = kind == "wrong-audience" ? "wrong-audience" : Audience,
            NotBefore = kind == "not-yet-valid" ? now.AddMinutes(5) : now.AddMinutes(-5),
            Expires =
                kind == "expired" ? now.AddMinutes(-1)
                : kind == "not-yet-valid" ? now.AddMinutes(10)
                : now.AddMinutes(5),
            SigningCredentials = new SigningCredentials(signing, SecurityAlgorithms.RsaSha256),
        };
        return new JwtSecurityTokenHandler().WriteToken(
            new JwtSecurityTokenHandler().CreateToken(descriptor)
        );
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
            rsa.Dispose();
    }
}
