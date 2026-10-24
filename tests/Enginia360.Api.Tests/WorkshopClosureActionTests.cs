using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using Npgsql;
using Xunit;

// R03.c advisory closure-actions read against real PostgreSQL. Synthetic data only; flags are advice, every command re-authorizes.
[Collection("r03c-runtime")]
public sealed class WorkshopClosureActionTests
{
    private static NpgsqlDataSource Admin() => NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);

    private static async Task<(JsonElement Body, string Raw)> Read(ClosureApiFactory factory, WorkshopClosureSnapshotTests.Scope scope)
    {
        using var client = factory.CreateClient();
        client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", factory.Token(scope.Subject, scope.Tenant));
        var response = await client.GetAsync($"/api/v1/workshop/orders/{scope.Order}/closure-actions");
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var raw = await response.Content.ReadAsStringAsync();
        return (JsonDocument.Parse(raw).RootElement.Clone(), raw);
    }

    private static string[] Reasons(JsonElement body, string action) => body.GetProperty("actionReasons").EnumerateArray()
        .Where(x => x.GetProperty("action").GetString() == action).Select(x => x.GetProperty("code").GetString()!).ToArray();

    // The order trigger only admits +1 steps, exactly like real commercial edits.
    private static async Task Revision(NpgsqlDataSource admin, Guid order, int revision)
    {
        for (var step = 0; step < revision; step++)
        {
            await using var update = admin.CreateCommand("UPDATE workshop.orders SET \"CommercialRevision\"=\"CommercialRevision\"+1 WHERE \"Id\"=@order");
            update.Parameters.AddWithValue("order", order);
            await update.ExecuteNonQueryAsync();
        }
    }


    private static async Task Exec(NpgsqlDataSource admin, string sql, params (string, object)[] values)
    {
        await using var command = admin.CreateCommand(sql);
        foreach (var (name, value) in values) command.Parameters.AddWithValue(name, value);
        await command.ExecuteNonQueryAsync();
    }

    private static async Task<Guid> Closed(NpgsqlDataSource admin, WorkshopClosureSnapshotTests.Scope scope, bool request)
    {
        await using var connection = await admin.OpenConnectionAsync();
        return await WorkshopClosureSnapshotTests.Close(connection, null, scope, request);
    }

    private static Task Grant(NpgsqlDataSource admin, WorkshopClosureSnapshotTests.Scope scope, string permission) =>
        Exec(admin, "INSERT INTO organization_access.company_permissions VALUES (@id,@membership,@tenant,@company,@permission,NULL,NULL)",
            ("id", Guid.NewGuid()), ("membership", scope.Membership), ("tenant", scope.Tenant), ("company", scope.Company), ("permission", permission));

    private static void Flags(JsonElement body, bool read, bool technical, bool request, bool reconcile, bool administrative)
    {
        Assert.Equal(read, body.GetProperty("canReadAdministrativeState").GetBoolean());
        Assert.Equal(technical, body.GetProperty("canCompleteTechnical").GetBoolean());
        Assert.Equal(request, body.GetProperty("canRequestAdministrative").GetBoolean());
        Assert.Equal(reconcile, body.GetProperty("mayRequestReconciliation").GetBoolean());
        Assert.Equal(administrative, body.GetProperty("canCompleteAdministrative").GetBoolean());
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Technical_only_grant_on_open_order_gets_persisted_revision_runtime_and_a_named_read_requirement(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.orders.complete-technical");
        await Revision(admin, scope.Order, 7);
        using var factory = new ClosureApiFactory(poolSize);
        var (body, _) = await Read(factory, scope);
        Assert.Equal(scope.Order, body.GetProperty("orderId").GetGuid());
        Assert.Equal(7, body.GetProperty("commercialRevision").GetInt32());
        Assert.Equal(JsonValueKind.Null, body.GetProperty("technicalClosure").ValueKind);
        Assert.True(body.GetProperty("canCompleteTechnical").GetBoolean());
        Assert.False(body.GetProperty("canReadAdministrativeState").GetBoolean());
        Assert.False(body.GetProperty("canRequestAdministrative").GetBoolean());
        Assert.False(body.GetProperty("mayRequestReconciliation").GetBoolean());
        Assert.False(body.GetProperty("canCompleteAdministrative").GetBoolean());
        Assert.Equal("SimulatorV1", body.GetProperty("administrativeRuntime").GetProperty("kind").GetString());
        Assert.Equal(1, body.GetProperty("administrativeRuntime").GetProperty("contractVersion").GetInt32());
        Assert.Equal(["not_authorized"], Reasons(body, "readAdministrativeState"));
        Assert.Equal(["administrative_read_required"], Reasons(body, "requestAdministrative"));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Technical_only_grant_after_closure_sees_the_technical_fact_but_nothing_administrative(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.orders.complete-technical");
        await using (var connection = await admin.OpenConnectionAsync()) await WorkshopClosureSnapshotTests.Close(connection, null, scope, request: true);
        await using var requestId = admin.CreateCommand("SELECT \"Id\"::text FROM workshop.administrative_requests WHERE \"OrderId\"=@order");
        requestId.Parameters.AddWithValue("order", scope.Order);
        var request = (string)(await requestId.ExecuteScalarAsync())!;
        using var factory = new ClosureApiFactory(poolSize);
        var (body, raw) = await Read(factory, scope);
        Assert.NotEqual(JsonValueKind.Null, body.GetProperty("technicalClosure").ValueKind);
        Assert.False(body.GetProperty("canCompleteTechnical").GetBoolean());
        Assert.Equal(["already_closed"], Reasons(body, "completeTechnical"));
        Assert.DoesNotContain(request, raw);
        Assert.DoesNotContain("already_requested", raw);
        Assert.DoesNotContain("external_confirmation_required", raw);
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Request_is_offered_only_after_technical_closure_with_exact_read_and_create_grants(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.create");
        using var factory = new ClosureApiFactory(poolSize);
        var (open, _) = await Read(factory, scope);
        Flags(open, read: true, technical: false, request: false, reconcile: false, administrative: false);
        Assert.Equal(["technical_closure_required"], Reasons(open, "requestAdministrative"));
        await Closed(admin, scope, request: false);
        var (closed, _) = await Read(factory, scope);
        Flags(closed, read: true, technical: false, request: true, reconcile: false, administrative: false);
        Assert.Empty(Reasons(closed, "requestAdministrative"));
        Assert.Equal(["already_closed"], Reasons(closed, "completeTechnical"));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Persisted_request_blocks_a_second_one_and_withholds_administrative_closure_until_a_local_outcome(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.create",
            "workshop.orders.complete-administrative");
        await Closed(admin, scope, request: true);
        using var factory = new ClosureApiFactory(poolSize);
        var (body, _) = await Read(factory, scope);
        Flags(body, read: true, technical: false, request: false, reconcile: false, administrative: false);
        Assert.Equal(["already_requested"], Reasons(body, "requestAdministrative"));
        Assert.Equal(["external_confirmation_required"], Reasons(body, "completeAdministrative"));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Request_reasons_distinguish_missing_grant_disabled_capability_missing_destination_and_internal_allocation(int poolSize)
    {
        await using var admin = Admin();
        var plain = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read");
        await Closed(admin, plain, request: false);
        var noCapability = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.create");
        await Closed(admin, noCapability, request: false);
        await Exec(admin, "UPDATE organization_access.capability_activations SET \"Enabled\"=false WHERE \"LegalEntityId\"=@company AND \"Capability\"='external-administration'", ("company", noCapability.Company));
        var internalDestination = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.create");
        await Closed(admin, internalDestination, request: false);
        await Exec(admin, "INSERT INTO workshop.administrative_destinations VALUES (@tenant,@company,2,'Internal')", ("tenant", internalDestination.Tenant), ("company", internalDestination.Company));
        var claimed = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.create");
        await Closed(admin, claimed, request: false);
        await Exec(admin, "INSERT INTO workshop.internal_billing_claims VALUES (@invoice,@tenant,@order,1,0,clock_timestamp())", ("invoice", Guid.NewGuid()), ("tenant", claimed.Tenant), ("order", claimed.Order));
        using var factory = new ClosureApiFactory(poolSize);
        Assert.Equal(["not_authorized"], Reasons((await Read(factory, plain)).Body, "requestAdministrative"));
        Assert.Equal(["capability_disabled"], Reasons((await Read(factory, noCapability)).Body, "requestAdministrative"));
        Assert.Equal(["administrative_destination_missing"], Reasons((await Read(factory, internalDestination)).Body, "requestAdministrative"));
        Assert.Equal(["internal_invoice_already_allocated"], Reasons((await Read(factory, claimed)).Body, "requestAdministrative"));
        foreach (var scope in new[] { plain, noCapability, internalDestination, claimed })
            Assert.False((await Read(factory, scope)).Body.GetProperty("canRequestAdministrative").GetBoolean());
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Write_grants_without_the_administrative_read_never_enable_or_reveal_administrative_actions(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.create",
            "workshop.administrative-requests.reconcile", "workshop.orders.complete-administrative");
        var request = await Closed(admin, scope, request: true);
        using var factory = new ClosureApiFactory(poolSize);
        var (body, raw) = await Read(factory, scope);
        Flags(body, read: false, technical: false, request: false, reconcile: false, administrative: false);
        Assert.Equal(["administrative_read_required"], Reasons(body, "requestAdministrative"));
        Assert.Equal(["administrative_read_required"], Reasons(body, "reconcile"));
        Assert.Equal(["administrative_read_required"], Reasons(body, "completeAdministrative"));
        Assert.DoesNotContain(request.ToString(), raw);
        Assert.DoesNotContain("already_requested", raw);
    }
}
