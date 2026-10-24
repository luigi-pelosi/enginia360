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

    private static Task Dispatch(NpgsqlDataSource admin, WorkshopClosureSnapshotTests.Scope scope, Guid request, string state) =>
        Exec(admin, """
            INSERT INTO integrations.administrative_dispatches ("RequestId","TenantId","State","Attempts","LastAttemptAt","NextAttemptAt","LeaseUntil","LastError","UpdatedAt","Failures")
            VALUES (@request,@tenant,@state,4,clock_timestamp(),clock_timestamp(),NULL,NULL,clock_timestamp(),CASE WHEN @state='NeedsReconciliation' THEN 4 ELSE 0 END)
            """, ("request", request), ("tenant", scope.Tenant), ("state", state));

    private static Task Outcome(NpgsqlDataSource admin, WorkshopClosureSnapshotTests.Scope scope, Guid request, bool confirmed) =>
        Exec(admin, "INSERT INTO workshop.administrative_outcomes VALUES (@request,@tenant,@status,@reference,@code,clock_timestamp())",
            ("request", request), ("tenant", scope.Tenant), ("status", confirmed ? "Confirmed" : "Rejected"),
            ("reference", confirmed ? "AMM-SIM-000001" : DBNull.Value), ("code", confirmed ? DBNull.Value : "synthetic_refusal"));

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Reconciliation_may_be_attempted_only_for_needs_reconciliation_with_read_reconcile_grants_and_capability(int poolSize)
    {
        await using var admin = Admin();
        var ok = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.reconcile");
        await Dispatch(admin, ok, await Closed(admin, ok, request: true), "NeedsReconciliation");
        var queued = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.reconcile");
        await Dispatch(admin, queued, await Closed(admin, queued, request: true), "Uncertain");
        var noGrant = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read");
        await Dispatch(admin, noGrant, await Closed(admin, noGrant, request: true), "NeedsReconciliation");
        var off = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read", "workshop.administrative-requests.reconcile");
        await Dispatch(admin, off, await Closed(admin, off, request: true), "NeedsReconciliation");
        await Exec(admin, "UPDATE organization_access.capability_activations SET \"Enabled\"=false WHERE \"LegalEntityId\"=@company AND \"Capability\"='external-administration'", ("company", off.Company));
        using var factory = new ClosureApiFactory(poolSize);
        var granted = (await Read(factory, ok)).Body;
        Assert.True(granted.GetProperty("mayRequestReconciliation").GetBoolean());
        Assert.Empty(Reasons(granted, "reconcile"));
        Assert.Equal(["reconciliation_not_available"], Reasons((await Read(factory, queued)).Body, "reconcile"));
        Assert.Equal(["not_authorized"], Reasons((await Read(factory, noGrant)).Body, "reconcile"));
        var disabled = (await Read(factory, off)).Body;
        Assert.True(disabled.GetProperty("canReadAdministrativeState").GetBoolean()); // history stays readable with the capability off
        Assert.Equal(["capability_disabled"], Reasons(disabled, "reconcile"));
        foreach (var scope in new[] { queued, noGrant, off })
            Assert.False((await Read(factory, scope)).Body.GetProperty("mayRequestReconciliation").GetBoolean());
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Administrative_closure_needs_a_workshop_confirmed_outcome_never_a_completed_delivery_alone(int poolSize)
    {
        await using var admin = Admin();
        var grants = new[] { "workshop.orders.read", "workshop.administrative-requests.read", "workshop.orders.complete-administrative" };
        var confirmed = await WorkshopClosureSnapshotTests.Seed(admin, grants);
        var confirmedRequest = await Closed(admin, confirmed, request: true);
        await Dispatch(admin, confirmed, confirmedRequest, "Completed"); await Outcome(admin, confirmed, confirmedRequest, confirmed: true);
        var lagging = await WorkshopClosureSnapshotTests.Seed(admin, grants);
        await Dispatch(admin, lagging, await Closed(admin, lagging, request: true), "Completed");
        var rejected = await WorkshopClosureSnapshotTests.Seed(admin, grants);
        var rejectedRequest = await Closed(admin, rejected, request: true);
        await Dispatch(admin, rejected, rejectedRequest, "Rejected"); await Outcome(admin, rejected, rejectedRequest, confirmed: false);
        var noGrant = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.administrative-requests.read");
        var noGrantRequest = await Closed(admin, noGrant, request: true);
        await Dispatch(admin, noGrant, noGrantRequest, "Completed"); await Outcome(admin, noGrant, noGrantRequest, confirmed: true);
        var done = await WorkshopClosureSnapshotTests.Seed(admin, grants);
        var doneRequest = await Closed(admin, done, request: true);
        await Dispatch(admin, done, doneRequest, "Completed"); await Outcome(admin, done, doneRequest, confirmed: true);
        await Exec(admin, "INSERT INTO workshop.administrative_closures VALUES (@order,@id,@tenant,@request,'AMM-SIM-000001',clock_timestamp(),@operator)",
            ("order", done.Order), ("id", Guid.NewGuid()), ("tenant", done.Tenant), ("request", doneRequest), ("operator", done.Identity));
        using var factory = new ClosureApiFactory(poolSize);
        var yes = (await Read(factory, confirmed)).Body;
        Assert.True(yes.GetProperty("canCompleteAdministrative").GetBoolean()); Assert.Empty(Reasons(yes, "completeAdministrative"));
        var lag = (await Read(factory, lagging)).Body;
        Assert.False(lag.GetProperty("canCompleteAdministrative").GetBoolean()); Assert.Equal(["external_confirmation_required"], Reasons(lag, "completeAdministrative"));
        var refused = (await Read(factory, rejected)).Body;
        Assert.False(refused.GetProperty("canCompleteAdministrative").GetBoolean()); Assert.Equal(["external_confirmation_required"], Reasons(refused, "completeAdministrative"));
        Assert.Equal(["not_authorized"], Reasons((await Read(factory, noGrant)).Body, "completeAdministrative"));
        var closed = (await Read(factory, done)).Body;
        Assert.False(closed.GetProperty("canCompleteAdministrative").GetBoolean()); Assert.Equal(["already_closed"], Reasons(closed, "completeAdministrative"));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1)]
    [InlineData(4)]
    public async Task Without_the_external_connector_only_technical_closure_is_available_and_the_runtime_is_unavailable(int poolSize)
    {
        await using var admin = Admin();
        var scope = await WorkshopClosureSnapshotTests.Seed(admin, "workshop.orders.read", "workshop.orders.complete-technical", "workshop.administrative-requests.read");
        using var factory = new ClosureApiFactory(poolSize, external: false);
        var (body, _) = await Read(factory, scope);
        Flags(body, read: false, technical: true, request: false, reconcile: false, administrative: false);
        Assert.Equal(["route_unavailable"], Reasons(body, "readAdministrativeState"));
        Assert.Equal("Unavailable", body.GetProperty("administrativeRuntime").GetProperty("kind").GetString());
        Assert.Equal(0, body.GetProperty("administrativeRuntime").GetProperty("contractVersion").GetInt32());
    }
}
