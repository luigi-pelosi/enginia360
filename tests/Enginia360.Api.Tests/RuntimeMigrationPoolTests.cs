using Npgsql;
using Xunit;

// Synthetic PostgreSQL acceptance only; no runtime provisioning or auth changes.
public sealed class RuntimeMigrationPoolTests
{
    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task Transaction_local_tenant_context_does_not_leak_through_real_pool(int size)
    {
        var builder = new NpgsqlConnectionStringBuilder(
            Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!
        ) { MaxPoolSize = size, MinPoolSize = 1 };
        await using var source = NpgsqlDataSource.Create(builder.ConnectionString);
        await using var admin = NpgsqlDataSource.Create(
            Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!
        );
        var tenants = new[] { Guid.NewGuid(), Guid.NewGuid() };
        try
        {
            for (var i = 0; i < tenants.Length; i++)
            {
                await using var seed = admin.CreateCommand("""
                    INSERT INTO counterparties.counterparties
                    ("Id","TenantId","LegalName","FiscalIdentifier","RegisteredOffice")
                    VALUES (@id,@tenant,'Synthetic pool acceptance','SYNTHETIC','Test only')
                    """);
                seed.Parameters.AddWithValue("id", Guid.NewGuid());
                seed.Parameters.AddWithValue("tenant", tenants[i]);
                await seed.ExecuteNonQueryAsync();
            }
            if (size == 1)
            {
                int? previousPid = null;
                for (var i = 0; i < 6; i++)
                {
                    var pid = await Exercise(source, tenants[i % 2], rollback: i % 2 == 0);
                    if (previousPid.HasValue)
                        Assert.Equal(previousPid.Value, pid);
                    previousPid = pid;
                }
            }
            else
            {
                var ready = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
                var opened = 0;
                var tasks = Enumerable.Range(0, size).Select(async i =>
                {
                    await using var connection = await source.OpenConnectionAsync();
                    if (Interlocked.Increment(ref opened) == size)
                        ready.SetResult();
                    await ready.Task.WaitAsync(TimeSpan.FromSeconds(15));
                    var pid = connection.ProcessID;
                    await ExerciseConnection(connection, tenants[i % 2], i % 2 == 0);
                    return pid;
                }).ToArray();
                var pids = await Task.WhenAll(tasks);
                Assert.Equal(size, pids.Distinct().Count());
            }
            await using var reused = await source.OpenConnectionAsync();
            await AssertNoContext(reused);
            await using (var transaction = await reused.BeginTransactionAsync())
            {
                await SetTenant(reused, tenants[0]);
                await using var sleep = new NpgsqlCommand("SELECT pg_sleep(10)", reused);
                using var cancellation = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));
                await Assert.ThrowsAnyAsync<OperationCanceledException>(() => sleep.ExecuteNonQueryAsync(cancellation.Token));
                await transaction.RollbackAsync();
            }
            await AssertNoContext(reused);
        }
        finally
        {
            await using var cleanup = admin.CreateCommand("DELETE FROM counterparties.counterparties WHERE \"TenantId\"=ANY(@tenants)");
            cleanup.Parameters.AddWithValue("tenants", tenants);
            await cleanup.ExecuteNonQueryAsync();
        }
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task Explicit_authority_and_identity_do_not_leak_across_reused_real_pool(int size)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var contexts = Enumerable.Range(0, 2).Select(_ => new { Tenant=Guid.NewGuid(), Company=Guid.NewGuid(), Actor=Guid.NewGuid(), Member=Guid.NewGuid() }).ToArray();
        foreach (var item in contexts)
        {
            await using var connection = await admin.OpenConnectionAsync();
            await using var transaction = await connection.BeginTransactionAsync();
            await using var seed = new NpgsqlCommand("""
                INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic authority pool');
                INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
                INSERT INTO organization_access.external_identity_bindings VALUES (@actor,'https://synthetic.test',@subject);
                INSERT INTO organization_access.memberships VALUES (@member,@tenant,@subject);
                INSERT INTO organization_access.company_permissions VALUES (@grant,@member,@tenant,@company,'counterparties.read',NULL,NULL);
                SET LOCAL ROLE runtime_owner;
                SELECT set_config('app.tenant_id',@tenant_text,true);
                SELECT organization_access.establish_master_authority(@command,@tenant,@member,@proof,0,'Enginia360ToExternal',@source,@profile,ARRAY[@company]);
                """, connection);
            seed.Parameters.AddWithValue("tenant",item.Tenant); seed.Parameters.AddWithValue("company",item.Company);
            seed.Parameters.AddWithValue("actor",item.Actor); seed.Parameters.AddWithValue("subject",item.Actor.ToString());
            seed.Parameters.AddWithValue("member",item.Member); seed.Parameters.AddWithValue("grant",Guid.NewGuid());
            seed.Parameters.AddWithValue("tenant_text",item.Tenant.ToString()); seed.Parameters.AddWithValue("command",Guid.NewGuid());
            seed.Parameters.AddWithValue("proof",Guid.NewGuid()); seed.Parameters.AddWithValue("source",Guid.NewGuid()); seed.Parameters.AddWithValue("profile",Guid.NewGuid());
            await seed.ExecuteNonQueryAsync(); await transaction.CommitAsync();
        }
        var builder = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize=size, MinPoolSize=1 };
        await using var source = NpgsqlDataSource.Create(builder.ConnectionString);
        var barrier = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously); var opened=0;
        var tasks=Enumerable.Range(0,size).Select(async index =>
        {
            await using var connection=await source.OpenConnectionAsync();
            if(Interlocked.Increment(ref opened)==size) barrier.SetResult();
            await barrier.Task.WaitAsync(TimeSpan.FromSeconds(15));
            for(var round=0;round<4;round++)
            {
                var item=contexts[(index+round)%2];
                await using(var tx=await connection.BeginTransactionAsync())
                {
                    await using var set=new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.identity_subject',@subject,true)",connection);
                    set.Parameters.AddWithValue("tenant",item.Tenant.ToString()); set.Parameters.AddWithValue("subject",item.Actor.ToString());
                    await set.ExecuteNonQueryAsync();
                    await using var query=new NpgsqlCommand("SELECT organization_access.read_master_authority(@company)->>'state'",connection);
                    query.Parameters.AddWithValue("company",item.Company);
                    Assert.Equal("local",await query.ExecuteScalarAsync());
                    if(round%2==0) await tx.CommitAsync(); else await tx.RollbackAsync();
                }
                await using var denied=new NpgsqlCommand("SELECT organization_access.read_master_authority(@company)->>'state'",connection);
                denied.Parameters.AddWithValue("company",item.Company);
                Assert.Equal("forbidden",await denied.ExecuteScalarAsync());
            }
            return connection.ProcessID;
        });
        Assert.Equal(size,(await Task.WhenAll(tasks)).Distinct().Count());
        // Immutable authority history is retained until the isolated acceptance database is destroyed.
    }

    private static async Task<int> Exercise(NpgsqlDataSource source, Guid tenant, bool rollback)
    {
        await using var connection = await source.OpenConnectionAsync();
        var pid = connection.ProcessID;
        await ExerciseConnection(connection, tenant, rollback);
        return pid;
    }

    private static async Task ExerciseConnection(NpgsqlConnection connection, Guid tenant, bool rollback)
    {
        await AssertNoContext(connection);
        await using (var transaction = await connection.BeginTransactionAsync())
        {
            await SetTenant(connection, tenant);
            await using var query = new NpgsqlCommand("SELECT \"TenantId\" FROM counterparties.counterparties", connection);
            await using (var reader = await query.ExecuteReaderAsync())
            {
                Assert.True(await reader.ReadAsync());
                Assert.Equal(tenant, reader.GetGuid(0));
                Assert.False(await reader.ReadAsync());
            }
            if (rollback)
                await transaction.RollbackAsync();
            else
                await transaction.CommitAsync();
        }
        await AssertNoContext(connection);
    }

    private static async Task SetTenant(NpgsqlConnection connection, Guid tenant)
    {
        await using var set = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true)", connection);
        set.Parameters.AddWithValue("tenant", tenant.ToString("D"));
        await set.ExecuteNonQueryAsync();
    }

    private static async Task AssertNoContext(NpgsqlConnection connection)
    {
        await using var query = new NpgsqlCommand("SELECT count(*) FROM counterparties.counterparties", connection);
        Assert.Equal(0L, await query.ExecuteScalarAsync());
    }
}

public sealed class RuntimePostgreSqlTheoryAttribute : TheoryAttribute
{
    public RuntimePostgreSqlTheoryAttribute()
    {
        if (Environment.GetEnvironmentVariable("R00_POOL_CONNECTION") is null)
            Skip = "R00.a real PostgreSQL pool acceptance is selected by the isolated runtime runner";
    }
}
