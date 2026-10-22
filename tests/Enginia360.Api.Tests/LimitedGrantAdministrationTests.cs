using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Api.OrganizationAccess;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class LimitedGrantAdministrationTests
{
    [Fact]
    public async Task Anonymous_cannot_inspect_or_command_delegation()
    {
        using var factory = new TestApiFactory();
        using var client = factory.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.GetAsync("/api/v1/organization/grant-administration")).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", new { })).StatusCode);
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    public async Task Synthetic_legacy_context_preserves_original_schema_without_delegation_runtime(int poolSize)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var database = "r01b_legacy_" + Guid.NewGuid().ToString("N");
        await using (var create = admin.CreateCommand($"CREATE DATABASE {database}")) await create.ExecuteNonQueryAsync();
        try
        {
            var app = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { Database = database, MaxPoolSize = poolSize };
            var infrastructure = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!) { Database = database };
            await using var fixture = NpgsqlDataSource.Create(infrastructure.ConnectionString);
            var schema = await File.ReadAllTextAsync(Environment.GetEnvironmentVariable("R01_LEGACY_SCHEMA")!);
            schema = schema.Replace(":\"app_user\"", new NpgsqlCommandBuilder().QuoteIdentifier(app.Username!));
            await using (var ddl = fixture.CreateCommand(schema)) await ddl.ExecuteNonQueryAsync();
            var ids = Enumerable.Range(0, 7).Select(_ => Guid.NewGuid()).ToArray();
            await using (var seed = fixture.CreateCommand($"""
                INSERT INTO organization_access.tenants VALUES ('{ids[0]}','Synthetic legacy');
                INSERT INTO organization_access.legal_entities VALUES ('{ids[1]}','{ids[0]}','Synthetic company');
                INSERT INTO organization_access.sites VALUES ('{ids[2]}','{ids[1]}','{ids[0]}','Synthetic site');
                INSERT INTO organization_access.warehouses VALUES ('{ids[3]}','{ids[2]}','{ids[1]}','{ids[0]}','Synthetic warehouse');
                INSERT INTO organization_access.memberships VALUES ('{ids[4]}','{ids[0]}','{ids[5]}');
                INSERT INTO organization_access.membership_scopes VALUES ('{ids[6]}','{ids[4]}','{ids[0]}','{ids[1]}','{ids[2]}','{ids[3]}','organization-context.read');
                INSERT INTO organization_access.capability_activations VALUES ('{ids[1]}','organization-context',true);
                """)) await seed.ExecuteNonQueryAsync();
            var configuration = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["ConnectionStrings:OrganizationAccess"] = app.ConnectionString,
                ["Authentication:Profile"] = "SyntheticLegacy",
                ["Authentication:ValidIssuer"] = BindingApiFactory.Issuer,
                ["Authentication:Audience"] = "enginia360-api",
            }).Build();
            var services = new ServiceCollection();
            services.AddLogging();
            services.AddSingleton<IConfiguration>(configuration);
            services.AddOrganizationAccess(configuration);
            await using var provider = services.BuildServiceProvider();
            await using var scope = provider.CreateAsyncScope();
            var service = scope.ServiceProvider.GetRequiredService<OrganizationContextService>();
            Assert.Single(await service.ListContexts(ids[5].ToString(), CancellationToken.None));
            configuration["Authentication:Profile"] = null;
            var absentRuntime = await Assert.ThrowsAsync<PostgresException>(() => service.ListContexts(ids[5].ToString(), CancellationToken.None));
            Assert.Equal(PostgresErrorCodes.UndefinedTable, absentRuntime.SqlState);
        }
        finally
        {
            await using var drop = admin.CreateCommand($"DROP DATABASE {database} WITH (FORCE)");
            await drop.ExecuteNonQueryAsync();
        }
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task Explicit_mandate_not_operation_permission_controls_one_exact_action(int poolSize)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var ids = Enumerable.Range(0, 11).Select(_ => Guid.NewGuid()).ToArray();
        var tenant = ids[0]; var company = ids[1]; var site = ids[2]; var warehouse = ids[3];
        var actor = ids[4]; var target = ids[5]; var actorMembership = ids[6]; var targetMembership = ids[7]; var mandate = ids[8];
        async Task Sql(string text)
        {
            await using var command = admin.CreateCommand("SELECT set_config('app.owner_actor','" + ids[10] + "',false);" + text);
            await command.ExecuteNonQueryAsync();
        }
        await Sql($"""
            INSERT INTO organization_access.external_identity_bindings VALUES ('{actor}','{BindingApiFactory.Issuer}','{actor}'),('{target}','{BindingApiFactory.Issuer}','{target}');
            INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic limited grant');
            INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company');
            INSERT INTO organization_access.sites VALUES ('{site}','{company}','{tenant}','Synthetic site');
            INSERT INTO organization_access.warehouses VALUES ('{warehouse}','{site}','{company}','{tenant}','Synthetic warehouse');
            INSERT INTO organization_access.memberships VALUES ('{actorMembership}','{tenant}','{actor}'),('{targetMembership}','{tenant}','{target}');
            INSERT INTO organization_access.capability_activations VALUES ('{company}','organization-context',true);
            """);
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var client = factory.CreateClient(new() { AllowAutoRedirect = false });
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(actor.ToString(), tenant));
            object Request(Guid command, Guid member, string action = "organization-context.read", Guid? scope = null) => new
            {
                commandId = command,
                mandateId = mandate,
                targetMembershipId = member,
                tenantId = tenant,
                legalEntityId = scope ?? company,
                siteId = site,
                warehouseId = warehouse,
                action,
                operation = "grant"
            };
            Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", Request(Guid.NewGuid(), targetMembership))).StatusCode);
            await Sql($"""
                INSERT INTO organization_access.delegation_mandates VALUES ('{mandate}','{tenant}','{actorMembership}','{company}','{site}','{warehouse}','organization-context.read',clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour',NULL);
                """);
            var panel = await client.GetFromJsonAsync<JsonElement>("/api/v1/organization/grant-administration");
            Assert.Equal(targetMembership, panel[0].GetProperty("targetMembershipId").GetGuid());
            foreach (var invalid in new[] { Request(Guid.NewGuid(), actorMembership), Request(Guid.NewGuid(), Guid.NewGuid()), Request(Guid.NewGuid(), targetMembership, "organization-context.write"), Request(Guid.NewGuid(), targetMembership, scope: Guid.NewGuid()) })
                Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", invalid)).StatusCode);
            var commandId = Guid.NewGuid(); var request = Request(commandId, targetMembership);
            var replies = await Task.WhenAll(Enumerable.Range(0, 4).Select(_ => client.PostAsJsonAsync("/api/v1/organization/grant-commands", request)));
            Assert.All(replies, r => Assert.Equal(HttpStatusCode.OK, r.StatusCode));
            Assert.Equal(HttpStatusCode.Conflict, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", Request(Guid.NewGuid(), targetMembership))).StatusCode);
            Assert.Equal(HttpStatusCode.Conflict, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", Request(commandId, targetMembership, "organization-context.write"))).StatusCode);
            Assert.Equal(HttpStatusCode.Conflict, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", Request(commandId, targetMembership, scope: Guid.NewGuid()))).StatusCode);
            Assert.Equal(HttpStatusCode.BadRequest, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", Request(Guid.Empty, targetMembership))).StatusCode);
            using var targetClient = factory.CreateClient();
            targetClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(target.ToString(), tenant));
            Assert.Single((await targetClient.GetFromJsonAsync<JsonElement[]>("/api/v1/organization/contexts"))!);
            Assert.Empty((await targetClient.GetFromJsonAsync<JsonElement[]>("/api/v1/organization/grant-administration"))!);
            Assert.Equal(HttpStatusCode.Forbidden, (await targetClient.PostAsJsonAsync("/api/v1/organization/grant-commands", request)).StatusCode);
            await Sql($"UPDATE organization_access.delegation_mandates SET \"RevokedAt\"=clock_timestamp() WHERE \"Id\"='{mandate}'");
            Assert.Empty((await targetClient.GetFromJsonAsync<JsonElement[]>("/api/v1/organization/contexts"))!);
            Assert.Equal(HttpStatusCode.Forbidden, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", request)).StatusCode);
            // A fresh explicitly owner-created mandate can grant an ineffective old scope;
            // renewal never revives the revoked mandate or silently creates delegation.
            var renewed = ids[9];
            await Sql($"""
                INSERT INTO organization_access.delegation_mandates VALUES ('{renewed}','{tenant}','{actorMembership}','{company}','{site}','{warehouse}','organization-context.read',clock_timestamp()-interval '1 minute',clock_timestamp()+interval '1 hour',NULL);
                """);
            Assert.Equal(HttpStatusCode.OK, (await client.PostAsJsonAsync("/api/v1/organization/grant-commands", new
            {
                commandId = Guid.NewGuid(),
                mandateId = renewed,
                targetMembershipId = targetMembership,
                tenantId = tenant,
                legalEntityId = company,
                siteId = site,
                warehouseId = warehouse,
                action = "organization-context.read",
                operation = "grant"
            })).StatusCode);
            Assert.Single((await targetClient.GetFromJsonAsync<JsonElement[]>("/api/v1/organization/contexts"))!);
            await using var check = admin.CreateCommand($"SELECT count(*) FROM organization_access.grant_commands WHERE \"CommandId\"='{commandId}'");
            Assert.Equal(1L, await check.ExecuteScalarAsync());
            await using var auditCheck = admin.CreateCommand($"SELECT count(*) FROM organization_access.delegation_audit WHERE \"CommandId\"='{commandId}' AND \"Result\"='applied'");
            Assert.Equal(1L, await auditCheck.ExecuteScalarAsync());
        }
        finally
        {
            // Audit is retained, even in this isolated runtime fixture; remove only synthetic operational rows.
            await Sql($"DELETE FROM organization_access.tenants WHERE \"Id\"='{tenant}'; DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\" IN ('{actor}','{target}');");
        }
    }
}
