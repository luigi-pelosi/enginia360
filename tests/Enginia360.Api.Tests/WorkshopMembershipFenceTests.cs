using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

public sealed class WorkshopMembershipFenceTests
{
    private sealed class Barrier(string action)
    {
        internal string Action = action;
        internal TaskCompletionSource Reached = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal TaskCompletionSource Resume = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal bool Armed;
    }
    // Fixture-only pause after the REAL adapter has released its transaction.
    private sealed class PausedAccess(IWorkshopAccess inner, Barrier barrier) : IWorkshopAccess
    {
        public Task<WorkshopGrant?> ResolveMembership(string s, CancellationToken ct) => inner.ResolveMembership(s,ct);
        public Task<IReadOnlyList<WorkshopContext>> ListContexts(string s, CancellationToken ct) => inner.ListContexts(s,ct);
        public Task<bool> CapabilityEnabled(Guid t, Guid c, string a, CancellationToken ct) => inner.CapabilityEnabled(t,c,a,ct);
        public async Task<WorkshopGrant?> Authorize(string s, Guid c, Guid site, string action, bool capability, CancellationToken ct)
        {
            var result = await inner.Authorize(s,c,site,action,capability,ct);
            if (result is not null && barrier.Armed && action == barrier.Action)
            {
                barrier.Armed = false; barrier.Reached.SetResult();
                await barrier.Resume.Task.WaitAsync(TimeSpan.FromSeconds(15),ct);
            }
            return result;
        }
    }
    private static async Task<int> Waiter(NpgsqlDataSource admin, int blocker)
    {
        for (var i=0;i<200;i++)
        {
            await using var q=admin.CreateCommand("SELECT pid FROM pg_stat_activity WHERE @pid=ANY(pg_blocking_pids(pid)) LIMIT 1");
            q.Parameters.AddWithValue("pid",blocker);
            if (await q.ExecuteScalarAsync() is int pid) return pid;
            await Task.Delay(25);
        }
        throw new TimeoutException("Physical Workshop transaction waiter missing.");
    }
    private static void Configure(IServiceCollection services, int pool, Barrier barrier)
    {
        foreach (var name in new[] { "Enginia360.Workshop.WorkshopDbContext, Enginia360.Workshop", "Enginia360.Inventory.InventoryDbContext, Enginia360.Inventory" })
        {
            var db=Type.GetType(name,true)!;
            var ot=typeof(Microsoft.EntityFrameworkCore.DbContextOptions<>).MakeGenericType(db);
            var ct=typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(db);
            foreach(var d in services.Where(x=>x.ServiceType==ot || x.ServiceType==ct).ToArray()) services.Remove(d);
            var options=(Microsoft.EntityFrameworkCore.DbContextOptionsBuilder)Activator.CreateInstance(typeof(Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<>).MakeGenericType(db))!;
            var cs=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) {MaxPoolSize=pool,MinPoolSize=1,ApplicationName="workshop-owning-effect"};
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,cs.ConnectionString);
            services.AddSingleton(ot,options.Options);
        }
        var original=services.Single(x=>x.ServiceType==typeof(IWorkshopAccess)); services.Remove(original);
        services.AddScoped<IWorkshopAccess>(sp=>new PausedAccess((IWorkshopAccess)ActivatorUtilities.CreateInstance(sp,original.ImplementationType!),barrier));
    }

    [RuntimePostgreSqlTheory]
    [InlineData(1,"editor")]
    [InlineData(4,"editor")]
    [InlineData(1,"technical")]
    [InlineData(4,"technical")]
    [InlineData(1,"snapshot-disable")]
    [InlineData(4,"snapshot-disable")]
    [InlineData(1,"snapshot-rebind")]
    [InlineData(4,"snapshot-rebind")]
    [InlineData(1,"sql-read")]
    [InlineData(4,"sql-read")]
    [InlineData(1,"sql-write")]
    [InlineData(4,"sql-write")]
    [InlineData(1,"sql-source")]
    [InlineData(4,"sql-source")]
    [InlineData(1,"sql-stale-snapshot")]
    [InlineData(4,"sql-stale-snapshot")]
    [InlineData(1,"port-billing")]
    [InlineData(4,"port-billing")]
    [InlineData(1,"port-allocate")]
    [InlineData(4,"port-allocate")]
    [InlineData(1,"port-reservation")]
    [InlineData(4,"port-reservation")]
    [InlineData(1,"accepted-work")]
    [InlineData(4,"accepted-work")]
    [InlineData(1,"snapshot-cancel")]
    [InlineData(4,"snapshot-cancel")]
    [InlineData(1,"editor-rebind")]
    [InlineData(4,"editor-rebind")]
    [InlineData(1,"technical-rebind")]
    [InlineData(4,"technical-rebind")]
    [InlineData(1,"port-missing")]
    [InlineData(4,"port-missing")]
    [InlineData(1,"sql-missing")]
    [InlineData(4,"sql-missing")]
    public async Task Actual_Workshop_effect_rechecks_after_adapter_commit_and_holds_disable_until_effect_commit(int pool, string kind)
    {
        var owner=Guid.NewGuid(); var identity=Guid.NewGuid(); var member=Guid.NewGuid(); var tenant=Guid.NewGuid();
        var company=Guid.NewGuid(); var site=Guid.NewGuid(); var document=Guid.NewGuid();
        var orders=new[]{Guid.NewGuid(),Guid.NewGuid(),Guid.NewGuid()};
        var os="workshop-owner-"+owner; var subject="workshop-member-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        await using(var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@owner,@issuer,@os),(@identity,@issuer,@subject);
            INSERT INTO organization_access.platform_authority VALUES(true,@owner,@issuer,@os,true,1);
            INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic Workshop fence');
            INSERT INTO organization_access.memberships VALUES (@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.sites VALUES (@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.capability_activations VALUES (@company,'workshop',true);
            INSERT INTO organization_access.company_permissions
              SELECT gen_random_uuid(),@member,@tenant,@company,a,NULL::uuid,NULL::uuid FROM unnest(ARRAY['workshop.orders.read','workshop.groups.write','workshop.orders.complete-technical']) a;
            INSERT INTO workshop.document_types VALUES (@document,@tenant,@company,1,'Synthetic type',true);
            INSERT INTO workshop.line_policies VALUES (@tenant,@company,@document,1,'Case001',false,true);
            INSERT INTO workshop.orders ("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId")
              SELECT id,@tenant,@company,@site,@document,1,gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),@member FROM unnest(@orders) id;
            """))
        {
            foreach(var (key,value) in new Dictionary<string,object>{{"owner",owner},{"issuer",BindingApiFactory.Issuer},{"os",os},{"identity",identity},{"subject",subject},{"tenant",tenant},{"member",member},{"company",company},{"site",site},{"document",document},{"orders",orders}}) seed.Parameters.AddWithValue(key,value);
            await seed.ExecuteNonQueryAsync();
        }
        var action=kind.StartsWith("snapshot-",StringComparison.Ordinal)?"workshop.orders.read":kind.StartsWith("editor",StringComparison.Ordinal)?"workshop.groups.write":"workshop.orders.complete-technical";
        var barrier=new Barrier(action);
        var table=kind.StartsWith("editor",StringComparison.Ordinal)?"working_groups":"technical_closures";
        try
        {
            using var factory=new BindingApiFactory(pool);
            using var host=factory.WithWebHostBuilder(b=>b.UseSetting("Counterparties:Enabled","true").UseSetting("Workshop:Enabled","true").UseSetting("Inventory:Enabled","true").ConfigureTestServices(s=>Configure(s,pool,barrier)));
            using var user=host.CreateClient(); using var root=host.CreateClient();
            user.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(subject,Guid.NewGuid()));
            root.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(os,Guid.NewGuid()));
            var route="/api/v1/platform/tenant-roles/"+tenant;
            var directory=await root.GetFromJsonAsync<JsonElement>(route);
            var hash=directory.GetProperty("memberships")[0].GetProperty("bindingHash").GetString();
            if (kind=="snapshot-cancel")
            {
                var readRoute="/api/v1/workshop/orders/"+orders[0]+"/closure-actions";
                Assert.Equal(HttpStatusCode.OK,(await user.GetAsync(readRoute)).StatusCode);
                barrier.Armed=true;
                using var cancellation=new CancellationTokenSource();
                var read=user.GetAsync(readRoute,cancellation.Token);
                await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
                await using var holder=await admin.OpenConnectionAsync(); await using var tx=await holder.BeginTransactionAsync();
                await using(var hold=new NpgsqlCommand("SELECT pg_advisory_xact_lock(777036)",holder,tx)) await hold.ExecuteNonQueryAsync();
                barrier.Resume.SetResult(); await Waiter(admin,holder.ProcessID);
                cancellation.Cancel(); await Assert.ThrowsAnyAsync<OperationCanceledException>(()=>read);
                await tx.RollbackAsync();
                Assert.Equal(HttpStatusCode.OK,(await user.GetAsync(readRoute)).StatusCode);
                await using var locks=admin.CreateCommand("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.application_name='workshop-owning-effect' AND l.locktype='advisory' AND l.classid=0 AND l.objid=777036 AND l.granted");
                Assert.Equal(0L,await locks.ExecuteScalarAsync());
                return;
            }
            if (kind.StartsWith("snapshot-",StringComparison.Ordinal))
            {
                var readRoute="/api/v1/workshop/orders/"+orders[0]+"/closure-actions";
                Assert.Equal(HttpStatusCode.OK,(await user.GetAsync(readRoute)).StatusCode);
                barrier.Armed=true;
                var read=user.GetAsync(readRoute);
                await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
                await using var holder=await admin.OpenConnectionAsync();
                await using var tx=await holder.BeginTransactionAsync();
                await using(var hold=new NpgsqlCommand("SELECT pg_advisory_xact_lock(777036)",holder,tx)) await hold.ExecuteNonQueryAsync();
                await using(var change=new NpgsqlCommand(kind=="snapshot-disable"
                    ? "INSERT INTO organization_access.membership_access_state VALUES (@member,@tenant,false,1)"
                    : "UPDATE organization_access.external_identity_bindings SET \"Subject\"=\"Subject\"||'-replaced' WHERE \"InternalIdentityId\"=@identity",holder,tx))
                {
                    change.Parameters.AddWithValue("member",member); change.Parameters.AddWithValue("tenant",tenant); change.Parameters.AddWithValue("identity",identity);
                    await change.ExecuteNonQueryAsync();
                }
                barrier.Resume.SetResult();
                // This is the actual ReadSnapshot RepeatableRead owner, not a shared-guard copy.
                var pid=await Waiter(admin,holder.ProcessID);
                await using(var observe=admin.CreateCommand("SELECT query FROM pg_stat_activity WHERE pid=@pid"))
                {
                    observe.Parameters.AddWithValue("pid",pid);
                    var sql=(string)(await observe.ExecuteScalarAsync())!;
                    Assert.True(sql.Contains("current_membership_access",StringComparison.Ordinal) || sql.Contains("777036",StringComparison.Ordinal),sql);
                }
                await tx.CommitAsync();
                Assert.Equal(HttpStatusCode.Forbidden,(await read).StatusCode);
                await using var unchanged=admin.CreateCommand("SELECT count(*) FROM workshop.technical_closures WHERE \"TenantId\"=@tenant");
                unchanged.Parameters.AddWithValue("tenant",tenant); Assert.Equal(0L,await unchanged.ExecuteScalarAsync());
                return;
            }
            async Task State(int revision,bool enabled)
            {
                var response=await root.PostAsJsonAsync(route+"/membership-access",new{commandId=Guid.NewGuid(),membershipId=member,internalIdentityId=identity,bindingHash=hash,expectedRevision=revision,enabled});
                Assert.Equal(HttpStatusCode.OK,response.StatusCode);
            }
            Task<HttpResponseMessage> Effect(Guid order,Guid command)=>kind.StartsWith("editor",StringComparison.Ordinal)
                ? user.PostAsJsonAsync("/api/v1/workshop/orders/"+order+"/editor/commands",new{commandId=command,type="AddGroup",expectedRevision=0,expectedLinePolicyVersion=1,expectedStructurePolicyVersion=1,groupId=command,title="Synthetic group"})
                : user.PostAsJsonAsync("/api/v1/workshop/orders/"+order+"/technical-closure",new{id=command,expectedRevision=0});
            async Task<long> Count()
            {
                await using var q=admin.CreateCommand("SELECT count(*) FROM workshop."+table+" WHERE \"TenantId\"=@tenant");
                q.Parameters.AddWithValue("tenant",tenant); return (long)(await q.ExecuteScalarAsync())!;
            }
            if (kind.StartsWith("sql-",StringComparison.Ordinal) || kind.StartsWith("port-",StringComparison.Ordinal) || kind=="accepted-work")
            {
                var line=Guid.NewGuid();
                await using(var seed=admin.CreateCommand("""
                    INSERT INTO workshop.working_groups VALUES (@order,@tenant,@order,'Synthetic work','Active',1,0);
                    INSERT INTO workshop.commercial_lines ("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision")
                      SELECT @line,@tenant,@order,gen_random_uuid(),1,'Synthetic part','Part',1,0,0,0,22,"PayerId",@order,1,0 FROM workshop.orders WHERE "Id"=@order;
                    INSERT INTO workshop.technical_closures SELECT "Id",gen_random_uuid(),"TenantId",0,clock_timestamp(),@identity FROM workshop.orders WHERE "TenantId"=@tenant;
                    INSERT INTO workshop.administrative_destinations VALUES (@tenant,@company,1,'Internal');
                    """))
                {
                    seed.Parameters.AddWithValue("order",orders[0]); seed.Parameters.AddWithValue("tenant",tenant); seed.Parameters.AddWithValue("line",line); seed.Parameters.AddWithValue("identity",identity); seed.Parameters.AddWithValue("company",company); await seed.ExecuteNonQueryAsync();
                }
                using var scope=host.Services.CreateScope();
                var accessor=scope.ServiceProvider.GetRequiredService<Microsoft.AspNetCore.Http.IHttpContextAccessor>();
                accessor.HttpContext=new Microsoft.AspNetCore.Http.DefaultHttpContext {User=new System.Security.Claims.ClaimsPrincipal(new System.Security.Claims.ClaimsIdentity([
                    new(System.Security.Claims.ClaimTypes.NameIdentifier,identity.ToString("D")),new("enginia360:verified-issuer",BindingApiFactory.Issuer),new("enginia360:external-subject",subject)],"Synthetic verified fixture"))};
                try
                {
                    var billing=scope.ServiceProvider.GetRequiredService<IWorkshopBillingSources>();
                    var reservation=scope.ServiceProvider.GetRequiredService<IWorkshopReservationLines>();
                    Assert.NotNull(await billing.Find(tenant,orders[0],CancellationToken.None));
                    Assert.NotNull(await reservation.Find(tenant,orders[0],line,CancellationToken.None));
                    var invoice=Guid.NewGuid();
                    Assert.NotNull(await billing.Allocate(tenant,orders[0],invoice,0,CancellationToken.None));
                    Assert.NotNull(await billing.Allocate(tenant,orders[0],invoice,0,CancellationToken.None));
                    if (kind is not ("sql-stale-snapshot" or "sql-missing" or "port-missing")) await State(0,false);
                    if (kind.StartsWith("sql-",StringComparison.Ordinal))
                    {
                        await using var appSql=NpgsqlDataSource.Create(new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!) {MaxPoolSize=pool}.ConnectionString);
                        await using var connection=await appSql.OpenConnectionAsync(); await using var tx=await connection.BeginTransactionAsync(kind=="sql-stale-snapshot"?System.Data.IsolationLevel.RepeatableRead:System.Data.IsolationLevel.ReadCommitted);
                        await using(var context=new NpgsqlCommand("SELECT set_config('app.tenant_id',@tenant,true),set_config('app.identity_subject',@identity,true),set_config('app.identity_issuer',@issuer,true),set_config('app.external_subject',@subject,true)",connection,tx))
                        {
                            context.Parameters.AddWithValue("tenant",tenant.ToString("D")); context.Parameters.AddWithValue("identity",identity.ToString("D")); context.Parameters.AddWithValue("issuer",BindingApiFactory.Issuer); context.Parameters.AddWithValue("subject",subject); await context.ExecuteNonQueryAsync();
                        }
                        if(kind=="sql-missing")
                        {
                            await using var clear=new NpgsqlCommand("SELECT set_config('app.identity_issuer','',true),set_config('app.external_subject','',true)",connection,tx); await clear.ExecuteNonQueryAsync();
                        }
                        if(kind=="sql-stale-snapshot")
                        {
                            await State(0,false); // Snapshot exists BEFORE the committed disable.
                            await using var stale=new NpgsqlCommand("SELECT count(*) FROM workshop.orders",connection,tx);
                            Assert.Equal("40001",(await Assert.ThrowsAsync<PostgresException>(()=>stale.ExecuteScalarAsync())).SqlState);
                            return;
                        }
                        await using var q=new NpgsqlCommand(kind switch {"sql-read" or "sql-missing"=>"SELECT count(*) FROM workshop.orders", "sql-source"=>"SELECT count(*) FROM workshop.reservation_line(@tenant,@order,@line)", _=>"INSERT INTO workshop.working_groups VALUES (gen_random_uuid(),@tenant,@order,'Refused','Active',1,0)"},connection,tx);
                        q.Parameters.AddWithValue("tenant",tenant); q.Parameters.AddWithValue("order",orders[0]); q.Parameters.AddWithValue("line",line);
                        if(kind=="sql-write") Assert.Equal("42501",(await Assert.ThrowsAsync<PostgresException>(()=>q.ExecuteNonQueryAsync())).SqlState);
                        else Assert.Equal(0L,await q.ExecuteScalarAsync());
                    }
                    else if(kind=="port-missing")
                    {
                        accessor.HttpContext=null;
                        await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>billing.Find(tenant,orders[0],CancellationToken.None));
                        await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>billing.Allocate(tenant,orders[1],Guid.NewGuid(),0,CancellationToken.None));
                        await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>reservation.Find(tenant,orders[0],line,CancellationToken.None));
                    }
                    else if(kind=="port-billing") await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>billing.Find(tenant,orders[0],CancellationToken.None));
                    else if(kind=="port-allocate")
                    {
                        await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>billing.Allocate(tenant,orders[1],Guid.NewGuid(),0,CancellationToken.None));
                        await using var count=admin.CreateCommand("SELECT count(*) FROM workshop.internal_billing_claims WHERE \"TenantId\"=@tenant"); count.Parameters.AddWithValue("tenant",tenant); Assert.Equal(1L,await count.ExecuteScalarAsync());
                    }
                    else if(kind=="port-reservation") await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>reservation.Find(tenant,orders[0],line,CancellationToken.None));
                    else
                    {
                        var request=Guid.NewGuid(); var unbound=Guid.NewGuid();
                        await using(var seed=admin.CreateCommand("""
                            INSERT INTO organization_access.capability_activations VALUES (@company,'external-administration',true);
                            INSERT INTO workshop.administrative_requests
                              SELECT id,@tenant,ord,@company,@site,'External',1,1,0,0,0,0,'EUR',
                                jsonb_build_object('orderId',ord,'payerId',gen_random_uuid(),'revision',0,'lines','[]'::jsonb,'netAmount','0.000000','taxAmount','0.000000','total','0.000000','currency','EUR','policy','Case001'),clock_timestamp(),@identity
                              FROM (VALUES (@request,@order),(@unbound,@other)) v(id,ord);
                            INSERT INTO workshop.administrative_bindings
                              SELECT "Id","TenantId","OrderId","LegalEntityId","SiteId","DestinationVersion","ContractVersion","RequestedAt","OperatorId",'SimulatorV1',1,repeat('a',64)
                              FROM workshop.administrative_requests WHERE "Id"=@request;
                            INSERT INTO workshop.administrative_outbox SELECT "Id","TenantId","RequestedAt" FROM workshop.administrative_requests WHERE "Id" IN (@request,@unbound);
                            """))
                        {
                            foreach(var (k,v) in new Dictionary<string,object>{{"company",company},{"tenant",tenant},{"site",site},{"identity",identity},{"request",request},{"unbound",unbound},{"order",orders[1]},{"other",orders[2]}}) seed.Parameters.AddWithValue(k,v);
                            await seed.ExecuteNonQueryAsync();
                        }
                        accessor.HttpContext=null; // Accepted work must NOT require any operator session.
                        var worker=scope.ServiceProvider.GetRequiredService<IWorkshopAdministrativeOutbox>();
                        var envelope=new AdministrativeOutboxEnvelope(tenant,request);
                        Assert.Contains(await worker.Pending(100,0,CancellationToken.None),x=>x==envelope);
                        Assert.NotNull(await worker.Read(envelope,CancellationToken.None));
                        var historical=await worker.Read(new(tenant,unbound),CancellationToken.None);
                        Assert.NotNull(historical);
                        Assert.Null(historical.ConnectorBinding); // Worker must observe missing binding and HOLD, not retry source_unavailable.
                        Assert.Null(await worker.Read(new(Guid.NewGuid(),request),CancellationToken.None));
                        Assert.False(await worker.Record(new(tenant,unbound),new("Confirmed","SYNTHETIC-ORPHAN",null),CancellationToken.None));
                        Assert.True(await worker.Record(envelope,new("Confirmed","SYNTHETIC-"+request,null),CancellationToken.None));
                        Assert.True(await worker.Record(envelope,new("Confirmed","SYNTHETIC-"+request,null),CancellationToken.None));
                        Assert.False(await worker.Record(envelope,new("Rejected",null,"other"),CancellationToken.None));
                        Assert.DoesNotContain(await worker.Pending(100,0,CancellationToken.None),x=>x==envelope);
                        await using var verify=admin.CreateCommand("SELECT count(*) FROM workshop.administrative_outcomes WHERE \"TenantId\"=@tenant"); verify.Parameters.AddWithValue("tenant",tenant); Assert.Equal(1L,await verify.ExecuteScalarAsync());
                    }
                }
                finally { accessor.HttpContext=null; }
                return;
            }
            // Historical positive: no membership access row is enabled, not an implicit grant.
            var originalCommand=Guid.NewGuid();
            var initial=await Effect(orders[0],originalCommand);
            Assert.True(initial.StatusCode==HttpStatusCode.Created,await initial.Content.ReadAsStringAsync());
            Assert.Equal(HttpStatusCode.OK,(await Effect(orders[0],originalCommand)).StatusCode);
            barrier.Armed=true;
            var paused=Effect(orders[1],Guid.NewGuid());
            await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
            if (kind.EndsWith("-rebind",StringComparison.Ordinal))
            {
                await using var rebind=admin.CreateCommand("UPDATE organization_access.external_identity_bindings SET \"Subject\"=\"Subject\"||'-replaced' WHERE \"InternalIdentityId\"=@identity");
                rebind.Parameters.AddWithValue("identity",identity); await rebind.ExecuteNonQueryAsync();
                barrier.Resume.SetResult();
                var denied=await paused; Assert.Equal(1L,await Count()); Assert.Equal(HttpStatusCode.Forbidden,denied.StatusCode);
                return;
            }
            await State(0,false);
            barrier.Resume.SetResult();
            var refused=await paused;
            Assert.Equal(1L,await Count()); // Business effect before transport assertion: genuine RED.
            Assert.Equal(HttpStatusCode.Forbidden,refused.StatusCode);
            Assert.True((await Effect(orders[0],originalCommand)).StatusCode is HttpStatusCode.Forbidden or HttpStatusCode.NotFound);
            await State(1,true);
            await using(var install=admin.CreateCommand("CREATE FUNCTION workshop.fixture_membership_effect() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(777141); RETURN NEW; END $$; CREATE TRIGGER fixture_membership_effect BEFORE INSERT ON workshop."+table+" FOR EACH ROW EXECUTE FUNCTION workshop.fixture_membership_effect()")) await install.ExecuteNonQueryAsync();
            try
            {
                await using var holder=await admin.OpenConnectionAsync(); await using var tx=await holder.BeginTransactionAsync();
                await using(var hold=new NpgsqlCommand("SELECT pg_advisory_xact_lock(777141)",holder,tx)) await hold.ExecuteNonQueryAsync();
                var effect=Effect(orders[2],Guid.NewGuid()); var effectPid=await Waiter(admin,holder.ProcessID);
                var disable=State(2,false); await Waiter(admin,effectPid); Assert.False(disable.IsCompleted);
                await tx.CommitAsync(); Assert.Equal(HttpStatusCode.Created,(await effect).StatusCode); await disable;
            }
            finally
            {
                await using var drop=admin.CreateCommand("DROP TRIGGER fixture_membership_effect ON workshop."+table+"; DROP FUNCTION workshop.fixture_membership_effect()"); await drop.ExecuteNonQueryAsync();
            }
            Assert.Equal(2L,await Count());
        }
        finally
        {
            barrier.Resume.TrySetResult();
            await using var cleanup=admin.CreateCommand("DELETE FROM organization_access.platform_authority WHERE \"InternalIdentityId\"=@owner"); cleanup.Parameters.AddWithValue("owner",owner); await cleanup.ExecuteNonQueryAsync();
        }
    }
}
