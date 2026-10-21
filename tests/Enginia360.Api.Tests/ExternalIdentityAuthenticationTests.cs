using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Cryptography;
using Enginia360.Api.OrganizationAccess;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.IdentityModel.Protocols;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;
using Microsoft.IdentityModel.Tokens;
using Npgsql;
using Xunit;

public sealed class ExternalIdentityAuthenticationTests
{
    [Fact]
    public async Task Binding_store_outage_returns_controlled_unavailable_not_login_or_authorization()
    {
        using var factory = new BindingApiFactory(1, unavailable: true);
        using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token("opaque-subject", Guid.NewGuid()));
        var response = await client.GetAsync("/api/v1/organization/contexts");
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        Assert.Null(response.Headers.Location);
        Assert.DoesNotContain("Bearer ", await response.Content.ReadAsStringAsync());
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task Only_exact_verified_binding_resolves_to_existing_internal_membership(int poolSize)
    {
        var internalId = Guid.NewGuid();
        var unassignedId = Guid.NewGuid();
        var tenant = Guid.NewGuid();
        var company = Guid.NewGuid();
        var site = Guid.NewGuid();
        var warehouse = Guid.NewGuid();
        var membership = Guid.NewGuid();
        var subject = "Opaque-" + new string('x', 248); // full 255 ASCII characters, not a UUID
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES
                (@identity,@issuer,@subject), (@unassigned,@issuer,'no-membership');
            INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic binding test');
            INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.sites VALUES (@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.warehouses VALUES (@warehouse,@site,@company,@tenant,'Synthetic warehouse');
            INSERT INTO organization_access.memberships VALUES (@membership,@tenant,@internalSubject);
            INSERT INTO organization_access.membership_scopes VALUES
                (@scope,@membership,@tenant,@company,@site,@warehouse,'organization-context.read');
            INSERT INTO organization_access.capability_activations VALUES
                (@company,'organization-context',true);
            """))
        {
            seed.Parameters.AddWithValue("identity", internalId);
            seed.Parameters.AddWithValue("unassigned", unassignedId);
            seed.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("subject", subject);
            seed.Parameters.AddWithValue("tenant", tenant);
            seed.Parameters.AddWithValue("company", company);
            seed.Parameters.AddWithValue("site", site);
            seed.Parameters.AddWithValue("warehouse", warehouse);
            seed.Parameters.AddWithValue("membership", membership);
            seed.Parameters.AddWithValue("internalSubject", internalId.ToString("D"));
            seed.Parameters.AddWithValue("scope", Guid.NewGuid());
            await seed.ExecuteNonQueryAsync();
        }
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
            // An external UUID, roles, email and tenant claims do not establish binding.
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(internalId.ToString("D"), tenant));
            var unbound = await client.GetAsync("/api/v1/organization/contexts");
            Assert.True(unbound.StatusCode == HttpStatusCode.Unauthorized,
                $"Expected 401, got {(int)unbound.StatusCode}");
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(subject, tenant));
            var contexts = await client.GetFromJsonAsync<OrganizationContextContract[]>("/api/v1/organization/contexts");
            Assert.Equal(tenant, Assert.Single(contexts!).TenantId);
            // Matching subject with an untrusted issuer is not an alias.
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(subject, tenant, "https://other.test"));
            unbound = await client.GetAsync("/api/v1/organization/contexts");
            Assert.True(unbound.StatusCode == HttpStatusCode.Unauthorized,
                $"Expected 401, got {(int)unbound.StatusCode}");
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(subject.ToLowerInvariant(), tenant));
            unbound = await client.GetAsync("/api/v1/organization/contexts");
            Assert.True(unbound.StatusCode == HttpStatusCode.Unauthorized,
                $"Expected 401, got {(int)unbound.StatusCode}");
            // A bound identity with no membership is authenticated, with empty context, not admin.
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token("no-membership", tenant));
            Assert.Empty((await client.GetFromJsonAsync<OrganizationContextContract[]>("/api/v1/organization/contexts"))!);
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(subject, tenant));
            await using (var remove = admin.CreateCommand("DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\"=@id"))
            {
                remove.Parameters.AddWithValue("id", internalId);
                await remove.ExecuteNonQueryAsync();
            }
            unbound = await client.GetAsync("/api/v1/organization/contexts");
            Assert.True(unbound.StatusCode == HttpStatusCode.Unauthorized,
                $"Expected 401, got {(int)unbound.StatusCode}");
        }
        finally
        {
            await using var cleanup = admin.CreateCommand("""
                DELETE FROM organization_access.tenants WHERE "Id"=@tenant;
                DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"=ANY(@ids);
                """);
            cleanup.Parameters.AddWithValue("tenant", tenant);
            cleanup.Parameters.AddWithValue("ids", new[] { internalId, unassignedId });
            await cleanup.ExecuteNonQueryAsync();
        }
    }
}

public sealed class BindingApiFactory(int poolSize, bool unavailable = false) : WebApplicationFactory<Program>
{
    public const string Issuer = "https://binding-issuer.test";
    private readonly RSA rsa = RSA.Create(2048);
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        var connection = new NpgsqlConnectionStringBuilder(unavailable
            ? "Host=127.0.0.1;Port=1;Database=unavailable;Username=unavailable;Timeout=1;Pooling=false"
            : Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!)
        {
            MaxPoolSize = poolSize,
            MinPoolSize = 1,
        };
        builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["ConnectionStrings:OrganizationAccess"] = connection.ConnectionString,
            ["Authentication:ValidIssuer"] = Issuer,
            ["Authentication:Audience"] = "enginia360-api",
        }));
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<DbContextOptions<OrganizationAccessDbContext>>();
            services.RemoveAll<IDbContextOptionsConfiguration<OrganizationAccessDbContext>>();
            services.AddDbContext<OrganizationAccessDbContext>(options => options.UseNpgsql(connection.ConnectionString));
            services.PostConfigure<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme, options =>
            {
                options.TokenValidationParameters.ValidIssuer = Issuer;
                options.ConfigurationManager = new StaticConfigurationManager<OpenIdConnectConfiguration>(new()
                {
                    Issuer = Issuer,
                    SigningKeys = { new RsaSecurityKey(rsa) { KeyId = "binding-test" } },
                });
            });
        });
    }

    public string Token(string subject, Guid tenant, string issuer = Issuer)
    {
        var now = DateTime.UtcNow;
        return new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(issuer, "enginia360-api",
            [new("sub", subject), new("email", "not-a-binding@synthetic.invalid"), new("role", "admin"), new("tenant", tenant.ToString("D"))],
            now.AddSeconds(-5), now.AddMinutes(2),
            new SigningCredentials(new RsaSecurityKey(rsa) { KeyId = "binding-test" }, SecurityAlgorithms.RsaSha256)));
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
            rsa.Dispose();
    }
}
