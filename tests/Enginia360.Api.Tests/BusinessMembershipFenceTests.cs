using System.Net;
using System.Net.Http.Json;
using System.Security.Claims;
using System.Text.Json;
using Enginia360.Inventory.Contracts;
using Enginia360.Billing.Contracts;
using Enginia360.Accounting.Contracts;
using Enginia360.Catalog.Contracts;
using Enginia360.Vehicles.Contracts;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Npgsql;
using Xunit;

// Written for the final #164 phase; no source-edit-stage execution is evidence.
public sealed class BusinessMembershipFenceTests
{
    private sealed class Barrier
    {
        internal bool Armed;
        internal TaskCompletionSource Reached = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal TaskCompletionSource Resume = new(TaskCreationOptions.RunContinuationsAsynchronously);
        internal async Task Pause(CancellationToken ct)
        {
            if (!Armed) return;
            Armed=false; Reached.SetResult(); await Resume.Task.WaitAsync(TimeSpan.FromSeconds(15),ct);
        }
    }
    private sealed class InventoryPause(IInventoryAccess inner, Barrier barrier) : IInventoryAccess
    {
        public Task<IReadOnlyList<WarehouseChoice>> Warehouses(string s,Guid c,Guid site,CancellationToken ct)=>inner.Warehouses(s,c,site,ct);
        public async Task<bool> Authorize(string s,Guid c,Guid site,Guid w,string a,bool cap,CancellationToken ct)
        { var v=await inner.Authorize(s,c,site,w,a,cap,ct);if(v&&a=="inventory.reservations.create")await barrier.Pause(ct);return v; }
    }
    private sealed class BillingPause(IBillingAccess inner, Barrier barrier) : IBillingAccess
    {
        public Task<BillingGrant?> ResolveMembership(string s,CancellationToken ct)=>inner.ResolveMembership(s,ct);
        public async Task<BillingGrant?> Authorize(string s,Guid c,Guid site,string a,bool cap,CancellationToken ct)
        {var v=await inner.Authorize(s,c,site,a,cap,ct);if(v is not null&&a=="billing.invoices.confirm")await barrier.Pause(ct);return v;}
    }
    private sealed class AccountingPause(IAccountingAccess inner, Barrier barrier) : IAccountingAccess
    {
        public Task<AccountingGrant?> ResolveMembership(string s,CancellationToken ct)=>inner.ResolveMembership(s,ct);
        public async Task<AccountingGrant?> Authorize(string s,Guid c,Guid site,string a,bool cap,CancellationToken ct)
        {var v=await inner.Authorize(s,c,site,a,cap,ct);if(v is not null&&a=="accounting.journal-entries.post")await barrier.Pause(ct);return v;}
    }
    private static void Decorate<T>(IServiceCollection services,Func<T,object> wrap) where T:class
    {
        var descriptor=services.Single(x=>x.ServiceType==typeof(T)); services.Remove(descriptor);
        services.AddScoped(typeof(T),sp=>wrap((T)ActivatorUtilities.CreateInstance(sp,descriptor.ImplementationType!)));
    }
    private static async Task<int> Waiter(NpgsqlDataSource admin,int blocker)
    {
        for(var i=0;i<200;i++)
        {
            await using var q=admin.CreateCommand("SELECT pid FROM pg_stat_activity WHERE @blocker=ANY(pg_blocking_pids(pid)) LIMIT 1");q.Parameters.AddWithValue("blocker",blocker);
            if(await q.ExecuteScalarAsync() is int pid)return pid;
            await Task.Delay(25);
        }
        throw new TimeoutException("Expected independent physical owning-effect waiter.");
    }
    [RuntimePostgreSqlTheory]
    [InlineData(1,"inventory","disable-first")]
    [InlineData(1,"inventory","effect-first")]
    [InlineData(1,"inventory","binding-first")]
    [InlineData(4,"inventory","disable-first")]
    [InlineData(4,"inventory","effect-first")]
    [InlineData(4,"inventory","binding-first")]
    [InlineData(1,"billing","disable-first")]
    [InlineData(1,"billing","effect-first")]
    [InlineData(1,"billing","binding-first")]
    [InlineData(4,"billing","disable-first")]
    [InlineData(4,"billing","effect-first")]
    [InlineData(4,"billing","binding-first")]
    [InlineData(1,"accounting","disable-first")]
    [InlineData(1,"accounting","effect-first")]
    [InlineData(1,"accounting","binding-first")]
    [InlineData(4,"accounting","disable-first")]
    [InlineData(4,"accounting","effect-first")]
    [InlineData(4,"accounting","binding-first")]
    public async Task Actual_effect_holds_current_membership_until_commit(int pool,string module,string race)
    {
        var owner=Guid.NewGuid();var identity=Guid.NewGuid();var member=Guid.NewGuid();var tenant=Guid.NewGuid();var company=Guid.NewGuid();var site=Guid.NewGuid();var warehouse=Guid.NewGuid();
        var order=Guid.NewGuid();var line=Guid.NewGuid();var item=Guid.NewGuid();var payer=Guid.NewGuid();var document=Guid.NewGuid();var invoice=Guid.NewGuid();var command=Guid.NewGuid();
        var os="business-owner-"+owner;var subject="business-member-"+identity;
        await using var admin=NpgsqlDataSource.Create(Environment.GetEnvironmentVariable("R00_POOL_ADMIN_CONNECTION")!);
        var summary=new InvoiceSummarySnapshot(order,payer,0,[new(line,order,item,1,"Synthetic service","Service","1","10","0","10","22",payer,order,1)],"10","2.2","12.2","EUR","Case001");
        await using(var seed=admin.CreateCommand("""
            INSERT INTO organization_access.external_identity_bindings VALUES (@owner,@issuer,@os),(@identity,@issuer,@subject);
            INSERT INTO organization_access.platform_authority VALUES(true,@owner,@issuer,@os,true,1);
            INSERT INTO organization_access.tenants VALUES (@tenant,'Synthetic business fence');
            INSERT INTO organization_access.memberships VALUES (@member,@tenant,@identity::text);
            INSERT INTO organization_access.legal_entities VALUES (@company,@tenant,'Synthetic company');
            INSERT INTO organization_access.sites VALUES (@site,@company,@tenant,'Synthetic site');
            INSERT INTO organization_access.warehouses VALUES (@warehouse,@site,@company,@tenant,'Synthetic warehouse');
            INSERT INTO organization_access.capability_activations SELECT @company,a,true FROM unnest(ARRAY['workshop','inventory','internal-billing','internal-accounting']) a;
            INSERT INTO organization_access.company_permissions SELECT gen_random_uuid(),@member,@tenant,@company,a,NULL::uuid,NULL::uuid FROM unnest(ARRAY['workshop.orders.read','billing.invoices.confirm','billing.invoices.read','accounting.journal-entries.post','accounting.journal-entries.read']) a;
            INSERT INTO organization_access.company_permissions VALUES (gen_random_uuid(),@member,@tenant,@company,'inventory.reservations.create',@site,@warehouse);
            INSERT INTO counterparties.counterparties VALUES (@payer,@tenant,'Synthetic payer','SYNTHETIC','Synthetic office');
            INSERT INTO catalog.items VALUES (@item,@tenant,@company,'Part','Synthetic part',1);
            INSERT INTO vehicles.vehicles VALUES (@payer,@tenant,@company,@payer,'Synthetic vehicle');
            INSERT INTO workshop.document_types VALUES (@document,@tenant,@company,1,'Synthetic type',true);
            INSERT INTO workshop.line_policies VALUES (@tenant,@company,@document,1,'Case001',false,true);
            INSERT INTO workshop.orders ("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId") VALUES (@order,@tenant,@company,@site,@document,1,@payer,@payer,@payer,@member);
            INSERT INTO workshop.working_groups VALUES (@order,@tenant,@order,'Synthetic group','Active',1,0);
            INSERT INTO workshop.commercial_lines ("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision") VALUES (@line,@tenant,@order,@item,1,'Synthetic part','Part',5,10,0,50,22,@payer,@order,1,0);
            INSERT INTO inventory.stock VALUES (@tenant,@company,@site,@warehouse,@item,10);
            INSERT INTO organization_access.company_stock_profiles ("CommandId","TenantId","LegalEntityId","Domain","Version","Direction","SourceId","ProfileId","ActorMembershipId","VerificationReference") VALUES (gen_random_uuid(),@tenant,@company,'stock',1,'Enginia360ToExternal',gen_random_uuid(),gen_random_uuid(),@member,gen_random_uuid());
            INSERT INTO billing.document_types VALUES (@tenant,@company,@document,1,'SYNTHETIC',true,true);
            INSERT INTO billing.issuer_profiles VALUES (@tenant,@company,1,'Synthetic issuer','SYNTHETIC','Synthetic office');
            INSERT INTO billing.invoices VALUES (@invoice,@tenant,@order,@company,@site,@payer,@document,1,1,0,DATE '2026-11-03','EUR','SYNTHETIC',@summary::jsonb,clock_timestamp(),@member);
            INSERT INTO accounting.chart_accounts SELECT @tenant,@company,1,p,'1000','Synthetic account' FROM unnest(ARRAY['Receivable','ServiceRevenue','PartRevenue','TaxPayable']) p;
            """))
        {
            foreach(var (k,v) in new Dictionary<string,object>{{"owner",owner},{"identity",identity},{"member",member},{"tenant",tenant},{"company",company},{"site",site},{"warehouse",warehouse},{"order",order},{"line",line},{"item",item},{"payer",payer},{"document",document},{"invoice",invoice},{"issuer",BindingApiFactory.Issuer},{"os",os},{"subject",subject},{"summary",JsonSerializer.Serialize(summary,new JsonSerializerOptions(JsonSerializerDefaults.Web))}})seed.Parameters.AddWithValue(k,v);
            await seed.ExecuteNonQueryAsync();
        }
        if(module=="accounting")
        {
            await using var seed=admin.CreateCommand("INSERT INTO billing.invoice_confirmations VALUES (@invoice,gen_random_uuid(),@tenant,1,'{}','{}',clock_timestamp(),@member)");seed.Parameters.AddWithValue("invoice",invoice);seed.Parameters.AddWithValue("tenant",tenant);seed.Parameters.AddWithValue("member",member);await seed.ExecuteNonQueryAsync();
        }
        var table=module switch{"inventory"=>"inventory.reservations","billing"=>"billing.invoice_confirmations",_=>"accounting.journal_entries"};
        var barrier=new Barrier();
        try
        {
            using var factory=new BindingApiFactory(pool);
            using var host=factory.WithWebHostBuilder(b=>b.UseSetting("Counterparties:Enabled","true").UseSetting("Workshop:Enabled","true").UseSetting("Inventory:Enabled","true").UseSetting("InternalBilling:Enabled","true").UseSetting("TechnicalAccounting:Enabled","true").ConfigureTestServices(s=>
            {
                foreach (var moduleName in new[]{"Inventory","Billing","Accounting","Workshop","Catalog","Vehicles","Counterparties"})
                {
                    var typeName=moduleName=="Counterparties"?"Enginia360.Counterparties.Infrastructure.CounterpartiesDbContext, Enginia360.Counterparties":$"Enginia360.{moduleName}.{moduleName}DbContext, Enginia360.{moduleName}";
                    var db=Type.GetType(typeName,true)!;
                    var optionsType=typeof(Microsoft.EntityFrameworkCore.DbContextOptions<>).MakeGenericType(db);
                    var configurationType=typeof(Microsoft.EntityFrameworkCore.Infrastructure.IDbContextOptionsConfiguration<>).MakeGenericType(db);
                    foreach(var d in s.Where(x=>x.ServiceType==optionsType||x.ServiceType==configurationType).ToArray())s.Remove(d);
                    var options=(Microsoft.EntityFrameworkCore.DbContextOptionsBuilder)Activator.CreateInstance(typeof(Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<>).MakeGenericType(db))!;
                    var cs=new NpgsqlConnectionStringBuilder(Environment.GetEnvironmentVariable("R00_POOL_CONNECTION")!){MaxPoolSize=pool,MinPoolSize=1};
                    Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,cs.ConnectionString);s.AddSingleton(optionsType,options.Options);
                }
                Decorate<IInventoryAccess>(s,x=>new InventoryPause(x,barrier));Decorate<IBillingAccess>(s,x=>new BillingPause(x,barrier));Decorate<IAccountingAccess>(s,x=>new AccountingPause(x,barrier));
            }));
            using var user=host.CreateClient();using var root=host.CreateClient();user.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(subject,Guid.NewGuid()));root.DefaultRequestHeaders.Authorization=new("Bearer",factory.Token(os,Guid.NewGuid()));
            var route="/api/v1/platform/tenant-roles/"+tenant;
            var memberRow=(await root.GetFromJsonAsync<JsonElement>(route)).GetProperty("memberships")[0];
            var disable=new{commandId=Guid.NewGuid(),membershipId=member,internalIdentityId=identity,bindingHash=memberRow.GetProperty("bindingHash").GetString(),expectedRevision=0,enabled=false};
            Task<HttpResponseMessage> Effect()=>module switch
            {
                "inventory"=>user.PostAsJsonAsync("/api/v1/inventory/orders/"+order+"/lines/"+line+"/reservations",new{id=command,warehouseId=warehouse,catalogVersion=1,quantity="1"}),
                "billing"=>user.PostAsJsonAsync("/api/v1/billing/workshop-invoices/"+invoice+"/confirmation",new{id=command,configurationVersion=1}),
                _=>user.PostAsJsonAsync("/api/v1/accounting/invoice-journal-entries",new{id=command,invoiceId=invoice,chartVersion=1})
            };
            if(race!="effect-first")
            {
                barrier.Armed=true;var effect=Effect();await barrier.Reached.Task.WaitAsync(TimeSpan.FromSeconds(10));
                if(race=="disable-first")Assert.Equal(HttpStatusCode.OK,(await root.PostAsJsonAsync(route+"/membership-access",disable)).StatusCode);
                else
                {
                    await using var change=admin.CreateCommand("UPDATE organization_access.external_identity_bindings SET \"Subject\"=\"Subject\"||'-replaced' WHERE \"InternalIdentityId\"=@identity");change.Parameters.AddWithValue("identity",identity);await change.ExecuteNonQueryAsync();
                }
                barrier.Resume.SetResult();var status=(await effect).StatusCode;
                Assert.True(status is HttpStatusCode.Forbidden or HttpStatusCode.NotFound,status.ToString());
            }
            else
            {
                // Real table insert barrier. The effect has passed its owning
                // current-access fence, not merely its detached adapter.
                await using(var fixture=admin.CreateCommand("CREATE FUNCTION public.fixture_business_membership_barrier() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock(777141); RETURN NEW; END $$;CREATE TRIGGER fixture_business_membership_barrier BEFORE INSERT ON "+table+" FOR EACH ROW EXECUTE FUNCTION public.fixture_business_membership_barrier()"))await fixture.ExecuteNonQueryAsync();
                try
                {
                    await using var holder=await admin.OpenConnectionAsync();await using var tx=await holder.BeginTransactionAsync();await using(var lockRow=new NpgsqlCommand("SELECT pg_advisory_xact_lock(777141)",holder,tx))await lockRow.ExecuteNonQueryAsync();
                    var effect=Effect();var pid=await Waiter(admin,holder.ProcessID);var mutation=root.PostAsJsonAsync(route+"/membership-access",disable);
                    if(pool>1)await Waiter(admin,pid);Assert.False(mutation.IsCompleted);await tx.CommitAsync();
                    var status=(await effect).StatusCode;
                    // A completed effect may lose its response projection after
                    // a following disable; read physical effect below, never hide it.
                    Assert.True(status is HttpStatusCode.Created or HttpStatusCode.Forbidden,status.ToString());
                    Assert.Equal(HttpStatusCode.OK,(await mutation).StatusCode);
                }
                finally{await using var drop=admin.CreateCommand("DROP TRIGGER fixture_business_membership_barrier ON "+table+";DROP FUNCTION public.fixture_business_membership_barrier()");await drop.ExecuteNonQueryAsync();}
            }
            await using(var count=admin.CreateCommand("SELECT count(*) FROM "+table+" WHERE \"TenantId\"=@tenant"))
            {count.Parameters.AddWithValue("tenant",tenant);Assert.Equal(race=="effect-first"?1L:0L,await count.ExecuteScalarAsync());}
            // Service callers cannot silently turn missing identity into workers.
            using var scope=host.Services.CreateScope();var accessor=scope.ServiceProvider.GetRequiredService<IHttpContextAccessor>();
            accessor.HttpContext=new DefaultHttpContext{User=new ClaimsPrincipal(new ClaimsIdentity([new(ClaimTypes.NameIdentifier,identity.ToString("D")),new("enginia360:verified-issuer",BindingApiFactory.Issuer),new("enginia360:external-subject",subject)],"Verified fixture"))};
            try
            {
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IWorkshopCatalog>().Find(tenant,item,CancellationToken.None));
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IWorkshopVehicles>().Find(tenant,payer,CancellationToken.None));
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IConfirmedInvoices>().Find(tenant,invoice,CancellationToken.None));
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IConfirmedInvoices>().Link(tenant,invoice,Guid.NewGuid(),CancellationToken.None));
                accessor.HttpContext=null;
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IWorkshopCatalog>().List(tenant,CancellationToken.None));
                await Assert.ThrowsAsync<UnauthorizedAccessException>(()=>scope.ServiceProvider.GetRequiredService<IWorkshopVehicles>().List(tenant,CancellationToken.None));
            }
            finally{accessor.HttpContext=null;}
        }
        finally{await using var cleanup=admin.CreateCommand("DELETE FROM organization_access.platform_authority WHERE \"InternalIdentityId\"=@owner");cleanup.Parameters.AddWithValue("owner",owner);await cleanup.ExecuteNonQueryAsync();}
    }
}
