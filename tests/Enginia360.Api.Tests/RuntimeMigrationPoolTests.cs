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
