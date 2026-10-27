using Npgsql;
using Xunit;

// Synthetic PostgreSQL acceptance only; no runtime provisioning or auth changes.
public sealed class RuntimeMigrationPoolTests
{
    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Workshop_own_stream_context_resets_tenant_and_membership_on_reused_physical_pool(int size)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var tenant = Guid.NewGuid(); var foreign = Guid.NewGuid(); var order = Guid.NewGuid(); var foreignOrder = Guid.NewGuid();
        var members = new[] { Guid.NewGuid(), Guid.NewGuid(), Guid.NewGuid() };
        foreach (var scope in new[] { (Tenant: tenant, Order: order), (Tenant: foreign, Order: foreignOrder) })
        {
            await using var seed = admin.CreateCommand("""
                INSERT INTO workshop.document_types VALUES (@order,@tenant,@order,1,'Synthetic own pool',true);
                INSERT INTO workshop.orders ("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId")
                  VALUES (@order,@tenant,@order,@order,@order,1,@order,@order,@order,@order);
                """);
            seed.Parameters.AddWithValue("order", scope.Order); seed.Parameters.AddWithValue("tenant", scope.Tenant); await seed.ExecuteNonQueryAsync();
        }
        for (var i = 0; i < 3; i++)
        {
            await using var seed = admin.CreateCommand("INSERT INTO workshop.own_actual_time_streams VALUES (@tenant,@order,@member,0)");
            seed.Parameters.AddWithValue("tenant", i < 2 ? tenant : foreign); seed.Parameters.AddWithValue("order", i < 2 ? order : foreignOrder); seed.Parameters.AddWithValue("member", members[i]); await seed.ExecuteNonQueryAsync();
        }
        var builder = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize = size, MinPoolSize = 1 };
        await using var source = NpgsqlDataSource.Create(builder.ConnectionString);
        async Task Exercise(NpgsqlConnection connection, int index)
        {
            await using (var empty = new NpgsqlCommand("SELECT count(*) FROM workshop.own_actual_time_streams", connection)) Assert.Equal(0L, await empty.ExecuteScalarAsync());
            await using (var tx = await connection.BeginTransactionAsync())
            {
                await using var context = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.workshop_actor_membership_id',@member,true)", connection);
                context.Parameters.AddWithValue("tenant", (index < 2 ? tenant : foreign).ToString()); context.Parameters.AddWithValue("member", members[index].ToString()); await context.ExecuteNonQueryAsync();
                await using var read = new NpgsqlCommand("SELECT \"MembershipId\" FROM workshop.own_actual_time_streams", connection);
                await using (var rows = await read.ExecuteReaderAsync()) { Assert.True(await rows.ReadAsync()); Assert.Equal(members[index], rows.GetGuid(0)); Assert.False(await rows.ReadAsync()); }
                if (index % 2 == 0) await tx.CommitAsync(); else await tx.RollbackAsync();
            }
            await using var reset = new NpgsqlCommand("SELECT count(*) FROM workshop.own_actual_time_streams", connection); Assert.Equal(0L, await reset.ExecuteScalarAsync());
        }
        if (size == 1)
        {
            int? previous = null; for (var i = 0; i < 6; i++) { await using var connection = await source.OpenConnectionAsync(); if (previous.HasValue) Assert.Equal(previous.Value, connection.ProcessID); previous = connection.ProcessID; await Exercise(connection, i % 3); }
        }
        else
        {
            var ready = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously); var opened = 0;
            var ids = await Task.WhenAll(Enumerable.Range(0, size).Select(async i => { await using var connection = await source.OpenConnectionAsync(); if (Interlocked.Increment(ref opened) == size) ready.SetResult(); await ready.Task.WaitAsync(TimeSpan.FromSeconds(15)); await Exercise(connection, i % 3); return connection.ProcessID; }));
            Assert.Equal(size, ids.Distinct().Count());
        }
        // Synthetic rows remain only in this ephemeral acceptance database; append-only facts are never deleted for test cleanup.
    }
    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(12)]
    public async Task Transaction_local_tenant_context_does_not_leak_through_real_pool(int size)
    {
        var builder = new NpgsqlConnectionStringBuilder(
            Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!
        )
        { MaxPoolSize = size, MinPoolSize = 1 };
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
        var contexts = Enumerable.Range(0, 2).Select(_ => new { Tenant = Guid.NewGuid(), Company = Guid.NewGuid(), Actor = Guid.NewGuid(), Member = Guid.NewGuid() }).ToArray();
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
            seed.Parameters.AddWithValue("tenant", item.Tenant); seed.Parameters.AddWithValue("company", item.Company);
            seed.Parameters.AddWithValue("actor", item.Actor); seed.Parameters.AddWithValue("subject", item.Actor.ToString());
            seed.Parameters.AddWithValue("member", item.Member); seed.Parameters.AddWithValue("grant", Guid.NewGuid());
            seed.Parameters.AddWithValue("tenant_text", item.Tenant.ToString()); seed.Parameters.AddWithValue("command", Guid.NewGuid());
            seed.Parameters.AddWithValue("proof", Guid.NewGuid()); seed.Parameters.AddWithValue("source", Guid.NewGuid()); seed.Parameters.AddWithValue("profile", Guid.NewGuid());
            await seed.ExecuteNonQueryAsync(); await transaction.CommitAsync();
        }
        var builder = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize = size, MinPoolSize = 1 };
        await using var source = NpgsqlDataSource.Create(builder.ConnectionString);
        var barrier = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously); var opened = 0;
        var tasks = Enumerable.Range(0, size).Select(async index =>
        {
            await using var connection = await source.OpenConnectionAsync();
            if (Interlocked.Increment(ref opened) == size) barrier.SetResult();
            await barrier.Task.WaitAsync(TimeSpan.FromSeconds(15));
            for (var round = 0; round < 4; round++)
            {
                var item = contexts[(index + round) % 2];
                await using (var tx = await connection.BeginTransactionAsync())
                {
                    await using var set = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.identity_subject',@subject,true)", connection);
                    set.Parameters.AddWithValue("tenant", item.Tenant.ToString()); set.Parameters.AddWithValue("subject", item.Actor.ToString());
                    await set.ExecuteNonQueryAsync();
                    await using var query = new NpgsqlCommand("SELECT organization_access.read_master_authority(@company)->>'state'", connection);
                    query.Parameters.AddWithValue("company", item.Company);
                    Assert.Equal("local", await query.ExecuteScalarAsync());
                    if (round % 2 == 0) await tx.CommitAsync(); else await tx.RollbackAsync();
                }
                await using var denied = new NpgsqlCommand("SELECT organization_access.read_master_authority(@company)->>'state'", connection);
                denied.Parameters.AddWithValue("company", item.Company);
                Assert.Equal("forbidden", await denied.ExecuteScalarAsync());
            }
            return connection.ProcessID;
        });
        Assert.Equal(size, (await Task.WhenAll(tasks)).Distinct().Count());
        // Immutable authority history is retained until the isolated acceptance database is destroyed.
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Supplier_role_and_company_vendor_identity_do_not_leak_across_reused_real_pool(int size)
    {
        await using var admin = NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var contexts = Enumerable.Range(0, 2).Select(index => new { Tenant = Guid.NewGuid(), Company = Guid.NewGuid(), Actor = Guid.NewGuid(), Member = Guid.NewGuid(), Record = Guid.NewGuid(), VendorId = "V" + Guid.NewGuid().ToString("N")[..12] }).ToArray();
        foreach (var item in contexts)
        {
            await using var connection = await admin.OpenConnectionAsync();
            await using var transaction = await connection.BeginTransactionAsync();
            await using var seed = new NpgsqlCommand("""
                INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic supplier pool');
                INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
                INSERT INTO organization_access.external_identity_bindings VALUES (@actor,'https://synthetic.test',@subject);
                INSERT INTO organization_access.memberships VALUES (@member,@tenant,@subject);
                INSERT INTO organization_access.company_permissions VALUES (@grant,@member,@tenant,@company,'counterparties.read',NULL,NULL);
                INSERT INTO organization_access.common_edit_permissions VALUES (@member,@tenant);
                INSERT INTO counterparties.counterparties VALUES (@record,@tenant,'Synthetic supplier pool','SYNTHETIC','Test only');
                SET LOCAL ROLE runtime_owner;
                SELECT set_config('app.tenant_id',@tenant_text,true);
                SELECT organization_access.establish_master_authority(@command,@tenant,@member,@proof,0,'Enginia360ToExternal',@source,@profile,ARRAY[@company]);
                """, connection);
            seed.Parameters.AddWithValue("tenant", item.Tenant); seed.Parameters.AddWithValue("company", item.Company);
            seed.Parameters.AddWithValue("actor", item.Actor); seed.Parameters.AddWithValue("subject", item.Actor.ToString());
            seed.Parameters.AddWithValue("member", item.Member); seed.Parameters.AddWithValue("grant", Guid.NewGuid()); seed.Parameters.AddWithValue("record", item.Record);
            seed.Parameters.AddWithValue("tenant_text", item.Tenant.ToString()); seed.Parameters.AddWithValue("command", Guid.NewGuid());
            seed.Parameters.AddWithValue("proof", Guid.NewGuid()); seed.Parameters.AddWithValue("source", Guid.NewGuid()); seed.Parameters.AddWithValue("profile", Guid.NewGuid());
            await seed.ExecuteNonQueryAsync(); await transaction.CommitAsync();
        }
        var builder = new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) { MaxPoolSize = size, MinPoolSize = 1 };
        await using var source = NpgsqlDataSource.Create(builder.ConnectionString);
        // The gated role command runs through the application pool; the mapping only through the owner path.
        foreach (var item in contexts)
        {
            await using var connection = await source.OpenConnectionAsync();
            await using (var tx = await connection.BeginTransactionAsync())
            {
                await using var set = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.identity_subject',@subject,true),set_config('app.legal_entity_id',@company,true)", connection);
                set.Parameters.AddWithValue("tenant", item.Tenant.ToString()); set.Parameters.AddWithValue("subject", item.Actor.ToString()); set.Parameters.AddWithValue("company", item.Company.ToString());
                await set.ExecuteNonQueryAsync();
                await using var role = new NpgsqlCommand("SELECT counterparties.set_supplier_role(@company,@record,@command,1,0,true)->>'state'", connection);
                role.Parameters.AddWithValue("company", item.Company); role.Parameters.AddWithValue("record", item.Record); role.Parameters.AddWithValue("command", Guid.NewGuid());
                Assert.Equal("applied", await role.ExecuteScalarAsync());
                await tx.CommitAsync();
            }
            await using var ownerConnection = await admin.OpenConnectionAsync();
            await using var ownerTx = await ownerConnection.BeginTransactionAsync();
            await using var context = new NpgsqlCommand("SET LOCAL ROLE runtime_owner; SELECT set_config('app.tenant_id',@tenant_text,true),set_config('app.legal_entity_id',@company_text,true)", ownerConnection);
            context.Parameters.AddWithValue("tenant_text", item.Tenant.ToString()); context.Parameters.AddWithValue("company_text", item.Company.ToString());
            await context.ExecuteNonQueryAsync();
            await using var owner = new NpgsqlCommand("SELECT counterparties.establish_giobby_vendor_identity(@command,@tenant,@company,@record,@member,@proof,0,@vendor,'Synthetic Supplier Pool')", ownerConnection);
            owner.Parameters.AddWithValue("command", Guid.NewGuid()); owner.Parameters.AddWithValue("tenant", item.Tenant); owner.Parameters.AddWithValue("company", item.Company);
            owner.Parameters.AddWithValue("record", item.Record); owner.Parameters.AddWithValue("member", item.Member); owner.Parameters.AddWithValue("proof", Guid.NewGuid()); owner.Parameters.AddWithValue("vendor", item.VendorId);
            Assert.Equal("applied", await owner.ExecuteScalarAsync()); await ownerTx.CommitAsync();
        }
        var barrier = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously); var opened = 0;
        var tasks = Enumerable.Range(0, size).Select(async index =>
        {
            await using var connection = await source.OpenConnectionAsync();
            if (Interlocked.Increment(ref opened) == size) barrier.SetResult();
            await barrier.Task.WaitAsync(TimeSpan.FromSeconds(15));
            for (var round = 0; round < 4; round++)
            {
                var item = contexts[(index + round) % 2];
                var other = contexts[(index + round + 1) % 2];
                await using (var tx = await connection.BeginTransactionAsync())
                {
                    await using var set = new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.identity_subject',@subject,true),set_config('app.legal_entity_id',@company,true)", connection);
                    set.Parameters.AddWithValue("tenant", item.Tenant.ToString()); set.Parameters.AddWithValue("subject", item.Actor.ToString()); set.Parameters.AddWithValue("company", item.Company.ToString());
                    await set.ExecuteNonQueryAsync();
                    await using var own = new NpgsqlCommand("SELECT counterparties.read_giobby_vendor_identity(@company,@record)->'vendor'->>'vendorId'", connection);
                    own.Parameters.AddWithValue("company", item.Company); own.Parameters.AddWithValue("record", item.Record);
                    Assert.Equal(item.VendorId, await own.ExecuteScalarAsync());
                    await using var foreign = new NpgsqlCommand("SELECT counterparties.read_giobby_vendor_identity(@company,@record)->>'state'", connection);
                    foreign.Parameters.AddWithValue("company", other.Company); foreign.Parameters.AddWithValue("record", other.Record);
                    Assert.Equal("forbidden", await foreign.ExecuteScalarAsync());
                    if (round % 2 == 0) await tx.CommitAsync(); else await tx.RollbackAsync();
                }
                await using var denied = new NpgsqlCommand("SELECT counterparties.read_giobby_vendor_identity(@company,@record)->>'state'", connection);
                denied.Parameters.AddWithValue("company", item.Company); denied.Parameters.AddWithValue("record", item.Record);
                Assert.Equal("forbidden", await denied.ExecuteScalarAsync());
            }
            return connection.ProcessID;
        });
        Assert.Equal(size, (await Task.WhenAll(tasks)).Distinct().Count());
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
