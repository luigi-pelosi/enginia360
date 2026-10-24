using System.IdentityModel.Tokens.Jwt;
using System.Net;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text.Json;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.IdentityModel.Protocols;
using Microsoft.IdentityModel.Protocols.OpenIdConnect;
using Microsoft.IdentityModel.Tokens;
using Npgsql;
using Xunit;

// R03.c real PostgreSQL acceptance of the closure read model. Synthetic data only, selected by the isolated runner.
[Collection("r03c-runtime")]
public sealed class WorkshopClosureSnapshotTests
{
    internal sealed record Scope(Guid Tenant, Guid Company, Guid Site, Guid Order, Guid Membership, Guid Identity, string Subject);

    internal static async Task<Scope> Seed(NpgsqlDataSource admin, params string[] permissions)
    {
        var scope = new Scope(Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid(), "r03c-" + Guid.NewGuid().ToString("N"));
        await using var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic closure');
            INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.sites VALUES (@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.memberships VALUES (@membership,@tenant,@internalSubject);
            INSERT INTO organization_access.capability_activations VALUES (@company,'workshop',true),(@company,'inventory',true),(@company,'external-administration',true);
            INSERT INTO workshop.document_types VALUES (@order,@tenant,@company,1,'Synthetic closure type',true);
            INSERT INTO workshop.orders ("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId")
              VALUES (@order,@tenant,@company,@site,@order,1,@order,@order,@order,@membership);
            INSERT INTO workshop.administrative_destinations VALUES (@tenant,@company,1,'External');
            """);
        seed.Parameters.AddWithValue("identity", scope.Identity); seed.Parameters.AddWithValue("issuer", ClosureApiFactory.Issuer);
        seed.Parameters.AddWithValue("subject", scope.Subject); seed.Parameters.AddWithValue("tenant", scope.Tenant);
        seed.Parameters.AddWithValue("company", scope.Company); seed.Parameters.AddWithValue("site", scope.Site);
        seed.Parameters.AddWithValue("membership", scope.Membership); seed.Parameters.AddWithValue("internalSubject", scope.Identity.ToString("D"));
        seed.Parameters.AddWithValue("order", scope.Order);
        await seed.ExecuteNonQueryAsync();
        foreach (var permission in permissions)
        {
            await using var grant = admin.CreateCommand("INSERT INTO organization_access.company_permissions VALUES (@id,@membership,@tenant,@company,@permission,NULL,NULL)");
            grant.Parameters.AddWithValue("id", Guid.NewGuid()); grant.Parameters.AddWithValue("membership", scope.Membership);
            grant.Parameters.AddWithValue("tenant", scope.Tenant); grant.Parameters.AddWithValue("company", scope.Company); grant.Parameters.AddWithValue("permission", permission);
            await grant.ExecuteNonQueryAsync();
        }
        return scope;
    }

    internal static async Task<Guid> Close(NpgsqlConnection connection, NpgsqlTransaction? tx, Scope scope, bool request)
    {
        await using var insert = new NpgsqlCommand("""
            INSERT INTO workshop.technical_closures ("OrderId","Id","TenantId","Revision","ClosedAt","OperatorId") VALUES (@order,@closure,@tenant,0,clock_timestamp(),@operator);
            """ + (request ? """
            INSERT INTO workshop.administrative_requests ("Id","TenantId","OrderId","LegalEntityId","SiteId","Destination","DestinationVersion","ContractVersion","Revision","NetAmount","TaxAmount","Total","Currency","Summary","RequestedAt","OperatorId")
              VALUES (@request,@tenant,@order,@company,@site,'External',1,1,0,0,0,0,'EUR',CAST(@summary AS jsonb),clock_timestamp(),@operator);
            INSERT INTO workshop.administrative_outbox VALUES (@request,@tenant,clock_timestamp());
            """ : ""), connection, tx);
        insert.Parameters.AddWithValue("order", scope.Order); insert.Parameters.AddWithValue("closure", Guid.NewGuid());
        insert.Parameters.AddWithValue("tenant", scope.Tenant); insert.Parameters.AddWithValue("operator", scope.Identity);
        var requestId = request ? Guid.NewGuid() : Guid.Empty;
        if (request)
        {
            insert.Parameters.AddWithValue("request", requestId); insert.Parameters.AddWithValue("company", scope.Company); insert.Parameters.AddWithValue("site", scope.Site);
            insert.Parameters.AddWithValue("summary", JsonSerializer.Serialize(new { orderId = scope.Order, payerId = scope.Order, revision = 0, lines = Array.Empty<object>(),
                netAmount = "0.000000", taxAmount = "0.000000", total = "0.000000", currency = "EUR", policy = "Case001" }));
        }
        await insert.ExecuteNonQueryAsync();
        return requestId;
    }

    internal static async Task WaitForBlockedReader(NpgsqlDataSource admin, string relation)
    {
        var stop = DateTime.UtcNow.AddSeconds(10);
        while (DateTime.UtcNow < stop)
        {
            await using var probe = admin.CreateCommand("SELECT count(*) FROM pg_locks WHERE NOT granted AND relation=@relation::regclass");
            probe.Parameters.AddWithValue("relation", relation);
            if ((long)(await probe.ExecuteScalarAsync())! > 0) return;
            await Task.Delay(20);
        }
        throw new TimeoutException("reader never reached the barrier");
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Closure_state_never_combines_open_with_a_request_committed_between_its_queries(int poolSize)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var scope = await Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read");
        using var factory = new ClosureApiFactory(poolSize);
        using var client = factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(scope.Subject, scope.Tenant));
        var url = $"/api/v1/workshop/orders/{scope.Order}/closure-state";
        Assert.Equal(HttpStatusCode.OK, (await client.GetAsync(url)).StatusCode);
        await using var holder = await admin.OpenConnectionAsync();
        await using var tx = await holder.BeginTransactionAsync();
        await using (var barrier = new NpgsqlCommand("LOCK TABLE workshop.administrative_closures IN ACCESS EXCLUSIVE MODE", holder, tx)) await barrier.ExecuteNonQueryAsync();
        var reading = client.GetAsync(url);
        await WaitForBlockedReader(admin, "workshop.administrative_closures");
        await Close(holder, tx, scope, request: true);
        await tx.CommitAsync();
        var response = await reading;
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var state = JsonSerializer.Deserialize<OrderClosureState>(await response.Content.ReadAsStringAsync(), new JsonSerializerOptions(JsonSerializerDefaults.Web))!;
        // One snapshot: either nothing of the concurrent commit, or all of it. Never a request beside an Open order.
        Assert.False(state.Status == "Open" && state.Request is not null, $"mixed snapshot: status={state.Status}, request={(state.Request is null ? "none" : "present")}");
        Assert.Equal(state.TechnicalClosure is null, state.Request is null);
    }
}

[CollectionDefinition("r03c-runtime", DisableParallelization = true)]
public sealed class R03cRuntimeCollection;

public sealed class ClosureApiFactory : WebApplicationFactory<Program>
{
    public const string Issuer = "https://closure-issuer.test";
    private readonly RSA rsa = RSA.Create(2048);
    private readonly string? previousConnection = Environment.GetEnvironmentVariable("ConnectionStrings__OrganizationAccess");
    private readonly string connection;

    public ClosureApiFactory(int poolSize, bool external = true)
    {
        connection = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize = poolSize, MinPoolSize = 1 }.ConnectionString;
        // Every module reads this key at composition; only this serialized class sets it and Dispose restores it.
        Environment.SetEnvironmentVariable("ConnectionStrings__OrganizationAccess", connection);
        External = external;
    }
    private bool External { get; }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseSetting("Workshop:Enabled", "true").UseSetting("Counterparties:Enabled", "true").UseSetting("Inventory:Enabled", "true");
        if (External) builder.UseSetting("ExternalAdministration:Enabled", "true").UseSetting("ExternalAdministration:SimulatorBaseUrl", "http://127.0.0.1:9/")
            .UseSetting("ExternalAdministration:PollMilliseconds", "60000");
        builder.ConfigureServices(services => services.PostConfigure<JwtBearerOptions>(JwtBearerDefaults.AuthenticationScheme, options =>
        {
            options.TokenValidationParameters.ValidIssuer = Issuer;
            options.ConfigurationManager = new StaticConfigurationManager<OpenIdConnectConfiguration>(new()
            {
                Issuer = Issuer,
                SigningKeys = { new RsaSecurityKey(rsa) { KeyId = "closure-test" } },
            });
        }));
    }

    public string Token(string subject, Guid tenant)
    {
        var now = DateTime.UtcNow;
        return new JwtSecurityTokenHandler().WriteToken(new JwtSecurityToken(Issuer, "enginia360-api",
            [new("sub", subject), new("tenant", tenant.ToString("D"))], now.AddSeconds(-5), now.AddMinutes(2),
            new SigningCredentials(new RsaSecurityKey(rsa) { KeyId = "closure-test" }, SecurityAlgorithms.RsaSha256)));
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing)
        {
            Environment.SetEnvironmentVariable("ConnectionStrings__OrganizationAccess", previousConnection);
            rsa.Dispose();
        }
    }
}
