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
    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Organization_commands_use_real_signed_bearer_current_authority_and_no_membership(int poolSize)
    {
        var identity = Guid.NewGuid(); var subject = "org-" + Guid.NewGuid().ToString("D");
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@id,@issuer,@subject);
            INSERT INTO organization_access.platform_authority VALUES(true,@id,@issuer,@subject,true,1);
            """))
        {
            seed.Parameters.AddWithValue("id", identity); seed.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("subject", subject); await seed.ExecuteNonQueryAsync();
        }
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
            const string route = "/api/v1/platform/tenants";
            client.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token(subject, Guid.NewGuid()));
            var command = new { commandId = Guid.NewGuid().ToString("D"), operation = "create", kind = "tenant",
                tenantId = (string?)null, resourceId = (string?)null, parentId = (string?)null,
                name = "Signed bearer synthetic organization", expectedRevision = 0 };
            var replies = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ => client.PostAsJsonAsync(route, command)));
            var values = new List<System.Text.Json.JsonElement>();
            foreach (var reply in replies)
            {
                Assert.Equal(HttpStatusCode.OK, reply.StatusCode); Assert.True(reply.Headers.CacheControl?.NoStore);
                values.Add(await reply.Content.ReadFromJsonAsync<System.Text.Json.JsonElement>());
            }
            Assert.Single(values, v => v.GetProperty("state").GetString() == "applied");
            Assert.Equal(3, values.Count(v => v.GetProperty("state").GetString() == "replayed"));
            var snapshot = values[0].GetProperty("snapshot"); var id = snapshot.GetProperty("resourceId").GetGuid();
            Assert.All(values, v => Assert.Equal(snapshot.ToString(), v.GetProperty("snapshot").ToString()));
            var read = await client.GetAsync(route + "/" + id);
            Assert.Equal(HttpStatusCode.OK, read.StatusCode); Assert.True(read.Headers.CacheControl?.NoStore);
            Assert.Empty((await client.GetFromJsonAsync<OrganizationContextContract[]>("/api/v1/organization/contexts"))!);
            await using (var verify = admin.CreateCommand("SELECT count(*) FROM organization_access.organization_commands WHERE \"CommandId\"=@id"))
            {
                verify.Parameters.AddWithValue("id", Guid.Parse(command.commandId)); Assert.Equal(1L, await verify.ExecuteScalarAsync());
            }
            await using (var revoke = admin.CreateCommand("UPDATE organization_access.platform_authority SET \"Active\"=false WHERE \"InternalIdentityId\"=@id"))
            {
                revoke.Parameters.AddWithValue("id", identity); await revoke.ExecuteNonQueryAsync();
            }
            Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync(route, command)).StatusCode);
            Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync(route + "/" + id)).StatusCode);
            client.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token(identity.ToString("D"), Guid.NewGuid()));
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(route)).StatusCode);
        }
        finally
        {
            // Append-only command/audit and synthetic organization remain in the ephemeral fixture only.
            await using var cleanup = admin.CreateCommand("DELETE FROM organization_access.platform_authority WHERE \"InternalIdentityId\"=@id; DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\"=@id;");
            cleanup.Parameters.AddWithValue("id", identity); await cleanup.ExecuteNonQueryAsync();
        }
    }

    [Fact]
    public async Task Anonymous_platform_metadata_is_no_store_even_without_browser_profile()
    {
        using var factory = new BindingApiFactory(1, unavailable: true);
        using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
        var response = await client.GetAsync("/api/v1/platform/tenants");
        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.True(response.Headers.CacheControl?.NoStore, "platform authentication refusal must be no-store");
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Platform_authority_is_current_exact_and_membership_free_for_real_signed_bearer(int poolSize)
    {
        var identity = Guid.NewGuid();
        var subject = "platform-" + Guid.NewGuid().ToString("D");
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@id,@issuer,@subject);
            """);
        seed.Parameters.AddWithValue("id", identity);
        seed.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
        seed.Parameters.AddWithValue("subject", subject);
        await seed.ExecuteNonQueryAsync();
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
            const string route = "/api/v1/platform/administration-eligibility";
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(route)).StatusCode);
            client.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token(subject, Guid.NewGuid()));
            var denied = await client.GetAsync(route);
            Assert.Equal(HttpStatusCode.Forbidden, denied.StatusCode);
            Assert.True(denied.Headers.CacheControl?.NoStore);
            await using var grant = admin.CreateCommand("""
                INSERT INTO organization_access.platform_authority VALUES(true,@id,@issuer,@subject,true,1);
                """);
            grant.Parameters.AddWithValue("id", identity);
            grant.Parameters.AddWithValue("issuer", BindingApiFactory.Issuer);
            grant.Parameters.AddWithValue("subject", subject);
            await grant.ExecuteNonQueryAsync();
            var allowed = await client.GetAsync(route);
            Assert.Equal(HttpStatusCode.OK, allowed.StatusCode);
            Assert.True(allowed.Headers.CacheControl?.NoStore);
            Assert.Equal("{\"canAdministerPlatform\":true}", await allowed.Content.ReadAsStringAsync());
            Assert.Empty((await client.GetFromJsonAsync<OrganizationContextContract[]>("/api/v1/organization/contexts"))!);
            await using var revoke = admin.CreateCommand("UPDATE organization_access.platform_authority SET \"Active\"=false WHERE \"InternalIdentityId\"=@id");
            revoke.Parameters.AddWithValue("id", identity);
            await revoke.ExecuteNonQueryAsync();
            Assert.Equal(HttpStatusCode.Forbidden, (await client.GetAsync(route)).StatusCode);
            client.DefaultRequestHeaders.Authorization = new("Bearer", factory.Token(identity.ToString("D"), Guid.NewGuid()));
            Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync(route)).StatusCode);
        }
        finally
        {
            await using var cleanup = admin.CreateCommand("""
                DELETE FROM organization_access.platform_authority WHERE "InternalIdentityId"=@id;
                DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"=@id;
                """);
            cleanup.Parameters.AddWithValue("id", identity);
            await cleanup.ExecuteNonQueryAsync();
        }
    }

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
