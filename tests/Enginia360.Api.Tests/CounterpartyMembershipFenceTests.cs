using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Counterparties.Contracts;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class CounterpartyMembershipFenceTests
{
    // A test-only port decorator pauses AFTER the real adapter transaction has
    // committed. It holds no connection/lock and does not replace authorization.
    private sealed class AuthorizationBarrier
    {
        internal TaskCompletionSource Reached = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal TaskCompletionSource Resume = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal bool Armed;
    }
    private sealed class PausedAccess(ICounterpartyAccess inner, AuthorizationBarrier barrier) : ICounterpartyAccess
    {
        public Task<IReadOnlyList<CounterpartyCompany>> ListCompanies(string subject, CancellationToken ct) => inner.ListCompanies(subject, ct);
        public async Task<CounterpartyAccess?> Authorize(string subject, Guid company, string permission, CancellationToken ct)
        {
            var result = await inner.Authorize(subject, company, permission, ct);
            if (result is not null && barrier.Armed)
            {
                barrier.Armed = false;
                barrier.Reached.SetResult();
                await barrier.Resume.Task.WaitAsync(TimeSpan.FromSeconds(15), ct);
            }
            return result;
        }
    }
    private static async Task<int> WaitForWaiter(NpgsqlDataSource admin, int blocker)
    {
        for (var i = 0; i < 160; i++)
        {
            await using var q = admin.CreateCommand("SELECT pid FROM pg_stat_activity WHERE @pid=ANY(pg_blocking_pids(pid)) LIMIT 1");
            q.Parameters.AddWithValue("pid", blocker);
            if (await q.ExecuteScalarAsync() is int pid) return pid;
            await Task.Delay(25);
        }
        throw new TimeoutException("Physical transaction waiter missing.");
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1, "sql-read")]
    [InlineData(4, "sql-read")]
    [InlineData(1, "sql-write")]
    [InlineData(4, "sql-write")]
    [InlineData(1, "recipient-port")]
    [InlineData(4, "recipient-port")]
    [InlineData(1, "read-after-adapter")]
    [InlineData(4, "read-after-adapter")]
    [InlineData(1, "read-rebind")]
    [InlineData(4, "read-rebind")]
    [InlineData(1, "sql-missing-identity")]
    [InlineData(4, "sql-missing-identity")]
    [InlineData(1, "sd-order-state")]
    [InlineData(4, "sd-order-state")]
    [InlineData(1, "sd-order-edit")]
    [InlineData(4, "sd-order-edit")]
    [InlineData(1, "sd-order-supplier")]
    [InlineData(4, "sd-order-supplier")]
    [InlineData(1, "sd-order-list")]
    [InlineData(4, "sd-order-list")]
    public async Task Disabled_counterparty_business_ingresses_cannot_use_prior_authorization(int poolSize, string ingress)
    {
        var identity = Guid.NewGuid(); var member = Guid.NewGuid(); var tenant = Guid.NewGuid();
        var company = Guid.NewGuid(); var counterparty = Guid.NewGuid(); var subject = "ingress-member-"+identity;
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@identity,@issuer,@subject);
            INSERT INTO organization_access.tenants("Id","Name") VALUES (@tenant,'Synthetic ingress tenant');
            INSERT INTO organization_access.memberships VALUES (@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES (@company,@tenant,'Synthetic ingress company');
            INSERT INTO organization_access.company_permissions VALUES (gen_random_uuid(),@member,@tenant,@company,'counterparties.read',NULL,NULL);
            INSERT INTO counterparties.counterparties ("Id","TenantId","LegalName","FiscalIdentifier","RegisteredOffice") VALUES (@counterparty,@tenant,'Synthetic ingress payer','SYNTHETIC','Synthetic office');
            """))
        {
            seed.Parameters.AddWithValue("identity",identity); seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("subject",subject); seed.Parameters.AddWithValue("member",member);
            seed.Parameters.AddWithValue("tenant",tenant); seed.Parameters.AddWithValue("company",company);
            seed.Parameters.AddWithValue("counterparty",counterparty); await seed.ExecuteNonQueryAsync();
        }
        async Task Disable()
        {
            await using var q = admin.CreateCommand("INSERT INTO organization_access.membership_access_state VALUES (@member,@tenant,false,1)");
            q.Parameters.AddWithValue("member",member); q.Parameters.AddWithValue("tenant",tenant); await q.ExecuteNonQueryAsync();
        }
        if (ingress.StartsWith("sql-",StringComparison.Ordinal) || ingress.StartsWith("sd-order-",StringComparison.Ordinal))
        {
            await using var appSql = NpgsqlDataSource.Create(new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) {MaxPoolSize=poolSize}.ConnectionString);
            if (ingress is "sql-read" or "sql-write") await Disable();
            await using var connection = await appSql.OpenConnectionAsync(); await using var tx = await connection.BeginTransactionAsync();
            await using (var context = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.legal_entity_id',@company,true),set_config('app.identity_subject',@identity,true),set_config('app.identity_issuer',@issuer,true),set_config('app.external_subject',@subject,true)",connection,tx))
            {
                context.Parameters.AddWithValue("tenant",tenant.ToString("D")); context.Parameters.AddWithValue("company",company.ToString("D")); context.Parameters.AddWithValue("identity",identity.ToString("D"));
                context.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer); context.Parameters.AddWithValue("subject",subject); await context.ExecuteNonQueryAsync();
            }
            if (ingress == "sql-missing-identity")
            {
                await using var clear = new NpgsqlCommand("SELECT set_config('app.identity_issuer','',true),set_config('app.external_subject','',true)",connection,tx);
                await clear.ExecuteNonQueryAsync();
            }
            if (ingress.StartsWith("sd-order-",StringComparison.Ordinal))
            {
                var call = ingress switch
                {
                    "sd-order-state" => "counterparties.common_edit_state(@company,@record)",
                    "sd-order-edit" => "counterparties.edit_common(@company,@record,gen_random_uuid(),0,0,'Synthetic','SYNTHETIC','Synthetic')",
                    "sd-order-supplier" => "counterparties.set_supplier_role(@company,@record,gen_random_uuid(),0,0,true)",
                    _ => "counterparties.purchase_suppliers(@company)"
                };
                await using var holder = await admin.OpenConnectionAsync(); await using var holdTx = await holder.BeginTransactionAsync();
                await using (var hold = new NpgsqlCommand("SELECT pg_advisory_xact_lock(777036)",holder,holdTx)) { await hold.ExecuteNonQueryAsync(); }
                await using var invoke = new NpgsqlCommand("SELECT "+call,connection,tx);
                invoke.Parameters.AddWithValue("company",company); invoke.Parameters.AddWithValue("record",counterparty);
                var pending = invoke.ExecuteScalarAsync();
                bool orderCorrect;
                try
                {
                    await WaitForWaiter(admin,holder.ProcessID);
                    await using var inspect = new NpgsqlCommand("SELECT pg_try_advisory_xact_lock(hashtextextended('master-authority:'||@tenant,0))",holder,holdTx);
                    inspect.Parameters.AddWithValue("tenant",tenant.ToString("D"));
                    orderCorrect = (bool)(await inspect.ExecuteScalarAsync())!;
                }
                finally { await holdTx.RollbackAsync(); }
                await pending;
                Assert.True(orderCorrect,"Direct SD ingress acquired master-authority before membership boundary777036 (reverse of owning HTTP path).");
            }
            else if (ingress is "sql-read" or "sql-missing-identity")
            {
                await using var q = new NpgsqlCommand("SELECT count(*) FROM counterparties.counterparties",connection,tx);
                Assert.Equal(0L,await q.ExecuteScalarAsync());
            }
            else
            {
                await using var q = new NpgsqlCommand("INSERT INTO counterparties.destinations (\"Id\",\"TenantId\",\"CounterpartyId\",\"OwnerLegalEntityId\",\"Address\",\"Published\") VALUES (gen_random_uuid(),@tenant,@counterparty,@company,'Synthetic direct write',false)",connection,tx);
                q.Parameters.AddWithValue("tenant",tenant); q.Parameters.AddWithValue("counterparty",counterparty); q.Parameters.AddWithValue("company",company);
                var refused = await Assert.ThrowsAsync<PostgresException>(() => q.ExecuteNonQueryAsync());
                Assert.Equal("42501",refused.SqlState);
            }
            await tx.RollbackAsync();
            return;
        }
        var barrier = new AuthorizationBarrier();
        using var factory = new BindingApiFactory(poolSize);
        using var host = factory.WithWebHostBuilder(b => b.UseSetting("Counterparties:Enabled","true").ConfigureTestServices(services => ConfigureModule(services,poolSize,barrier)));
        using var user = host.CreateClient();
        user.DefaultRequestHeaders.Authorization = new("Bearer",factory.Token(subject,Guid.NewGuid()));
        if (ingress is "read-after-adapter" or "read-rebind")
        {
            barrier.Armed = true;
            var pending = user.GetAsync("/api/v1/counterparties?legalEntityId="+company);
            await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
            if (ingress == "read-rebind")
            {
                await using var rebind = admin.CreateCommand("UPDATE organization_access.external_identity_bindings SET \"Subject\"=\"Subject\"||'-replaced' WHERE \"InternalIdentityId\"=@identity");
                rebind.Parameters.AddWithValue("identity",identity); await rebind.ExecuteNonQueryAsync();
            }
            else await Disable();
            barrier.Resume.SetResult();
            Assert.Equal(HttpStatusCode.Forbidden,(await pending).StatusCode);
        }
        else
        {
            // This port is called by Billing.Confirm to create NEW user-derived
            // work; it is NOT an accepted-work worker and must not default-allow.
            using var scope = host.Services.CreateScope();
            var accessor = scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Http.IHttpContextAccessor>();
            accessor.HttpContext = new Microsoft.AspNetCore.Http.DefaultHttpContext { User = new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
                new(System.Security.Claims.ClaimTypes.NameIdentifier,identity.ToString("D")),new("enginia360:verified-issuer",BindingApiFactory.Issuer),new("enginia360:external-subject",subject)],"Synthetic direct consumer")) };
            try
            {
                var port = scope.ServiceProvider.GetRequiredService<IInvoiceCounterparties>();
                Assert.NotNull(await port.Find(tenant,counterparty,CancellationToken.None));
                await Disable();
                await Assert.ThrowsAsync<UnauthorizedAccessException>(() => port.Find(tenant,counterparty,CancellationToken.None));
            }
            finally { accessor.HttpContext = null; }
        }
    }

    private static void ConfigureModule(IServiceCollection services, int poolSize, AuthorizationBarrier barrier)
    {
        var moduleDb = typeof(Enginia360.Counterparties.CounterpartiesModule).Assembly.GetType("Enginia360.Counterparties.Infrastructure.CounterpartiesDbContext")!;
        var optionsType = typeof(Microsoft.EntityFrameworkCore.DbContextOptions<>).MakeGenericType(moduleDb);
        var configType = typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(moduleDb);
        foreach (var item in services.Where(x => x.ServiceType == optionsType || x.ServiceType == configType).ToArray()) services.Remove(item);
        var connection = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize=poolSize,MinPoolSize=1,ApplicationName="counterparty-owning-effect" };
        var options = (Microsoft.EntityFrameworkCore.DbContextOptionsBuilder)Activator.CreateInstance(typeof(Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<>).MakeGenericType(moduleDb))!;
        Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,connection.ConnectionString);
        services.AddSingleton(optionsType,options.Options);
        var original = services.Single(x => x.ServiceType == typeof(ICounterpartyAccess));
        services.Remove(original);
        services.AddScoped<ICounterpartyAccess>(sp => new PausedAccess((ICounterpartyAccess)ActivatorUtilities.CreateInstance(sp,original.ImplementationType!),barrier));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Destination_owning_effect_rechecks_after_committed_adapter_and_serializes_disable(int poolSize)
    {
        var owner = Guid.NewGuid(); var identity = Guid.NewGuid(); var member = Guid.NewGuid();
        var tenant = Guid.NewGuid(); var company = Guid.NewGuid(); var counterparty = Guid.NewGuid();
        var ownerSubject = "fence-owner-" + owner; var memberSubject = "fence-member-" + identity;
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using (var seed = admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@owner,@issuer,@os),(@identity,@issuer,@ms);
            INSERT INTO organization_access.platform_authority VALUES(true,@owner,@issuer,@os,true,1);
            INSERT INTO organization_access.tenants("Id","Name") VALUES (@tenant,'Synthetic fence tenant');
            INSERT INTO organization_access.memberships VALUES (@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES (@company,@tenant,'Synthetic fence company');
            INSERT INTO organization_access.company_permissions VALUES
              (gen_random_uuid(),@member,@tenant,@company,'counterparties.read',NULL,NULL),
              (gen_random_uuid(),@member,@tenant,@company,'counterparties.destination.write',NULL,NULL);
            INSERT INTO organization_access.common_edit_permissions VALUES (@member,@tenant);
            INSERT INTO organization_access.master_authority_history("CommandId","TenantId","Version","Direction","SourceId","ProfileId","CompanyIds","ActorMembershipId","VerificationReference")
              VALUES (gen_random_uuid(),@tenant,1,'Enginia360ToExternal',gen_random_uuid(),gen_random_uuid(),ARRAY[@company],@member,gen_random_uuid());
            INSERT INTO counterparties.counterparties ("Id","TenantId","LegalName","FiscalIdentifier","RegisteredOffice")
              VALUES (@counterparty,@tenant,'Synthetic fence payer','SYNTHETIC','Synthetic office');
            """))
        {
            seed.Parameters.AddWithValue("owner",owner); seed.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer);
            seed.Parameters.AddWithValue("os",ownerSubject); seed.Parameters.AddWithValue("ms",memberSubject);
            seed.Parameters.AddWithValue("identity",identity); seed.Parameters.AddWithValue("member",member);
            seed.Parameters.AddWithValue("tenant",tenant); seed.Parameters.AddWithValue("company",company);
            seed.Parameters.AddWithValue("counterparty",counterparty); await seed.ExecuteNonQueryAsync();
        }
        var barrier = new AuthorizationBarrier();
        try
        {
            using var factory = new BindingApiFactory(poolSize);
            using var app = factory.WithWebHostBuilder(b => b.UseSetting("Counterparties:Enabled","true").ConfigureTestServices(services => ConfigureModule(services,poolSize,barrier)));
            using var user = app.CreateClient(); using var ownerClient = app.CreateClient();
            user.DefaultRequestHeaders.Authorization = new("Bearer",factory.Token(memberSubject,Guid.NewGuid()));
            ownerClient.DefaultRequestHeaders.Authorization = new("Bearer",factory.Token(ownerSubject,Guid.NewGuid()));
            var route = "/api/v1/platform/tenant-roles/"+tenant;
            var directory = await ownerClient.GetFromJsonAsync<JsonElement>(route);
            var hash = directory.GetProperty("memberships")[0].GetProperty("bindingHash").GetString();
            async Task State(int revision, bool enabled)
            {
                var response = await ownerClient.PostAsJsonAsync(route+"/membership-access",new { commandId=Guid.NewGuid(),membershipId=member,internalIdentityId=identity,bindingHash=hash,expectedRevision=revision,enabled });
                Assert.Equal(HttpStatusCode.OK,response.StatusCode);
            }
            var effectRoute = "/api/v1/counterparties/"+counterparty+"/destinations";
            var payload = new { legalEntityId=company,address="Synthetic destination" };
            // Old member without an access-state row remains enabled, not newly granted.
            var initial = await user.PostAsJsonAsync(effectRoute,payload);
            Assert.True(initial.StatusCode == HttpStatusCode.Created, await initial.Content.ReadAsStringAsync());
            var editRoute = "/api/v1/counterparties/"+counterparty;
            var edit = new { legalEntityId=company,commandId=Guid.NewGuid(),authorityVersion=1,expectedRevision=0,legalName="Synthetic edited payer",fiscalIdentifier="SYNTHETIC",registeredOffice="Synthetic office" };
            Assert.Equal(HttpStatusCode.OK,(await user.PutAsJsonAsync(editRoute,edit)).StatusCode);
            Assert.Equal(HttpStatusCode.OK,(await user.PutAsJsonAsync(editRoute,edit)).StatusCode);
            Assert.Equal(HttpStatusCode.OK,(await user.PutAsJsonAsync(editRoute+"/supplier-role",new { legalEntityId=company,commandId=Guid.NewGuid(),authorityVersion=1,expectedRevision=1,isSupplier=true })).StatusCode);
            Assert.Equal(HttpStatusCode.OK,(await user.GetAsync(editRoute+"/edit-state?legalEntityId="+company)).StatusCode);
            barrier.Armed = true;
            var paused = user.PostAsJsonAsync(effectRoute,payload);
            await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
            await State(0,false); // physical disable committed while adapter is done
            barrier.Resume.SetResult();
            var refused = await paused;
            await using (var count = admin.CreateCommand("SELECT count(*) FROM counterparties.destinations WHERE \"TenantId\"=@tenant"))
            {
                count.Parameters.AddWithValue("tenant",tenant);
                // Persisted effect is checked before HTTP status: this RED must
                // demonstrate a business mutation, not a missing route/fixture.
                Assert.Equal(1L,await count.ExecuteScalarAsync());
            }
            Assert.Equal(HttpStatusCode.Forbidden,refused.StatusCode);
            Assert.Equal(HttpStatusCode.Forbidden,(await user.PutAsJsonAsync(editRoute,edit)).StatusCode);
            await using (var verify = admin.CreateCommand("SELECT \"LegalName\"='Synthetic edited payer' AND \"IsSupplier\" AND (SELECT count(*) FROM counterparties.common_edit_history WHERE \"CounterpartyId\"=@record)=2 FROM counterparties.counterparties WHERE \"Id\"=@record"))
            { verify.Parameters.AddWithValue("record",counterparty); Assert.Equal(true,await verify.ExecuteScalarAsync()); }
            await State(1,true);
            await using (var install = admin.CreateCommand("""
                CREATE FUNCTION counterparties.fixture_membership_effect() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(777141); RETURN NEW; END $$;
                CREATE TRIGGER fixture_membership_effect BEFORE INSERT ON counterparties.destinations FOR EACH ROW EXECUTE FUNCTION counterparties.fixture_membership_effect();
                """)) { await install.ExecuteNonQueryAsync(); }
            try
            {
                await using var holder = await admin.OpenConnectionAsync();
                await using var tx = await holder.BeginTransactionAsync();
                await using (var hold = new NpgsqlCommand("SELECT pg_advisory_xact_lock(777141)",holder,tx)) { await hold.ExecuteNonQueryAsync(); }
                var effect = user.PostAsJsonAsync(effectRoute,payload);
                var effectPid = await WaitForWaiter(admin,holder.ProcessID);
                var disable = State(2,false);
                // OrganizationAccess pool is independent of the owner module pool,
                // including pool1: no nested held adapter connection is permitted.
                await WaitForWaiter(admin,effectPid);
                Assert.False(disable.IsCompleted);
                await tx.CommitAsync();
                Assert.Equal(HttpStatusCode.Created,(await effect).StatusCode);
                await disable;
            }
            finally
            {
                await using var drop = admin.CreateCommand("DROP TRIGGER fixture_membership_effect ON counterparties.destinations; DROP FUNCTION counterparties.fixture_membership_effect()");
                await drop.ExecuteNonQueryAsync();
            }
            await using (var count = admin.CreateCommand("SELECT count(*) FROM counterparties.destinations WHERE \"TenantId\"=@tenant"))
            { count.Parameters.AddWithValue("tenant",tenant); Assert.Equal(2L,await count.ExecuteScalarAsync()); }
        }
        finally
        {
            barrier.Resume.TrySetResult();
            await using var cleanup = admin.CreateCommand("DELETE FROM organization_access.platform_authority WHERE \"InternalIdentityId\"=@owner");
            cleanup.Parameters.AddWithValue("owner",owner); await cleanup.ExecuteNonQueryAsync();
        }
    }
}
