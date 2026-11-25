using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Catalog;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Numbering;
using Enginia360.Shared.Validation;
using Microsoft.EntityFrameworkCore;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;

namespace Enginia360.Verification.Catalog;

// Fixture HTTP esplicita: endpoint e policy reali, identita iniettata, NON prova cookie/CSRF.
// Il runner Python fornisce solo il PostgreSQL effimero senza porte host.
public static class CatalogItemStatesTests
{
    public static async Task Run(string connection)
    {
        void Ensure(bool ok,string message) {if(!ok) throw new Exception(message);}
        AppDb Db()=>new(new DbContextOptionsBuilder<AppDb>().UseNpgsql(connection).Options);
        var tenant=Guid.NewGuid();var actor=Guid.NewGuid();var category=Guid.NewGuid();
        Guid good,service,pz,kg,cf,plt;
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Items runtime');INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES(@actor,@t,@username,'proof@example.test','SQL','Proof')",("t",tenant),("code",tenant.ToString()),("actor",actor),("username",actor.ToString()));
            await CatalogSeed.Seed(db,tenant,actor);
            await db.Execute("INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES(@id,@t,'Categoria')",("id",category),("t",tenant));
            good=(Guid)(await db.Scalar("SELECT id FROM masterdata.catalog_item_type WHERE tenant_id=@t AND kind='GOOD'",("t",tenant)))!;
            service=(Guid)(await db.Scalar("SELECT id FROM masterdata.catalog_item_type WHERE tenant_id=@t AND kind='SERVICE'",("t",tenant)))!;
            async Task<Guid> Unit(string code)=>(Guid)(await db.Scalar("SELECT id FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND code=@code",("t",tenant),("code",code)))!;
            pz=await Unit("PZ");kg=await Unit("KG");
            cf=Guid.NewGuid();plt=Guid.NewGuid();
            await db.Execute("INSERT INTO masterdata.catalog_unit_of_measure(id,tenant_id,code,name,dimension,conversion_scope,factor_to_base,decimal_places) VALUES(@cf,@t,'CF','Confezione','COUNT','ITEM',NULL,2),(@plt,@t,'PLT','Pallet','COUNT','ITEM',NULL,2)",("t",tenant),("cf",cf),("plt",plt));
            await tx.CommitAsync();
        }
        var builder=WebApplication.CreateBuilder();
        builder.Logging.ClearProviders();
        builder.WebHost.UseUrls("http://127.0.0.1:0");
        builder.Services.AddDbContext<AppDb>(o=>o.UseNpgsql(connection));
        PermissionCatalog.Configure(builder.Services);
        await using var app=builder.Build();
        app.Use(async(ctx,next)=>{
            var db=ctx.RequestServices.GetRequiredService<AppDb>();
            await using var tx=await db.Database.BeginTransactionAsync();
            await Security.Lock(db);
            var permissions=ctx.Request.Headers["X-Proof-Permissions"].ToString().Split(',',StringSplitOptions.RemoveEmptyEntries);
            ctx.Items["identity"]=new IdentityState(new User {Id=actor,TenantId=tenant,Username="proof",IsEnabled=true},"proof","Proof",permissions);
            var response=ctx.Response.Body;
            await using var buffered=new MemoryStream();ctx.Response.Body=buffered;
            try {
                await next(ctx);
                await tx.CommitAsync();
                buffered.Position=0;ctx.Response.Body=response;await buffered.CopyToAsync(response);
            } catch(ApiException e) {
                await tx.RollbackAsync();ctx.Response.Body=response;ctx.Response.Clear();ctx.Response.StatusCode=e.Status;
                await ctx.Response.WriteAsJsonAsync(new {error=e.Code,field=e.Field});
            }
        });
        CatalogEndpoints.Map(app);CatalogItemEndpoints.Map(app);
        await app.StartAsync();
        using var client=new HttpClient {BaseAddress=new Uri(app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single())};
        async Task<JsonElement> Call(HttpMethod method,string path,object? body=null,int status=200,string permissions="catalog-items.read,catalog-items.create,catalog-items.update,catalog-items.activate,catalog-items.deactivate,catalog-items.archive,catalog-brands.read,catalog-brands.create,catalog-brands.update,catalog-units.read,catalog-units.create") {
            using var request=new HttpRequestMessage(method,"/api/catalog/"+path);
            request.Headers.Add("X-Proof-Permissions",permissions);
            if(body!=null) request.Content=JsonContent.Create(body);
            using var response=await client.SendAsync(request);
            var text=await response.Content.ReadAsStringAsync();
            Ensure((int)response.StatusCode==status,$"{method} {path}: expected {status}, got {(int)response.StatusCode}: {text}");
            return text.Length==0?default:JsonSerializer.Deserialize<JsonElement>(text);
        }
        long Version(JsonElement row)=>row.GetProperty("version").GetInt64();
        var values=new {name="Active default",item_type_id=good,category_id=category,base_uom_id=pz};
        var item=await Call(HttpMethod.Post,"items",new {values},201);
        Ensure(item.GetProperty("status").GetString()=="ACTIVE" && item.GetProperty("activated_at").ValueKind==JsonValueKind.String,"Omitted POST status must create ACTIVE with first activation");
        var id=item.GetProperty("id").GetGuid();
        Ensure(Version(item)==1,"Active create must have version 1");
        await Call(HttpMethod.Post,"items",new {values},403,"catalog-items.create");
        await Call(HttpMethod.Post,"items",new {values,status="ARCHIVED"},400);
        foreach(var status in new[]{"DRAFT","INACTIVE"}) {
            await Call(HttpMethod.Post,"items",new {values,status},400);
            await Call(HttpMethod.Get,"items?status="+status,status:400);
            await Call(HttpMethod.Put,$"items/{id}/status",new {status,expectedVersion=Version(item)},400);
            await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Old status"},status,expectedVersion=Version(item)},400);
        }
        await Call(HttpMethod.Post,"items",new {values=new {name="Missing refs",item_type_id=good}},400);
        await Call(HttpMethod.Post,"items",new {values=new {name="Incomplete",item_type_id=good},status="SUSPENDED"},400,"catalog-items.create");
        var suspended=await Call(HttpMethod.Post,"items",new {values,status="SUSPENDED"},201,"catalog-items.create");
        Ensure(suspended.GetProperty("activated_at").ValueKind==JsonValueKind.Null,"Suspended create never activated");
        var sid=suspended.GetProperty("id").GetGuid();
        await Call(HttpMethod.Put,$"items/{sid}",new {values=new {category_id=(Guid?)null},expectedVersion=1},400);
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Denied"},status="SUSPENDED",expectedVersion=1},403,"catalog-items.update");
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Off with physical"},status="SUSPENDED",physicalData=new {net_weight="2",weight_uom_id=kg},expectedVersion=Version(item)},permissions:"catalog-items.update,catalog-items.deactivate");
        Ensure(Version(item)==2 && item.GetProperty("status").GetString()=="SUSPENDED" && item.GetProperty("physicalData").GetProperty("net_weight").GetString()=="2","Unified state + physical insertion must advance exactly once");
        var first=item.GetProperty("activated_at").GetString();
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Stale"},status="ACTIVE",physicalData=(object?)null,expectedVersion=1},409);
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Preserve state"},expectedVersion=Version(item)},permissions:"catalog-items.update");
        Ensure(Version(item)==3 && item.GetProperty("status").GetString()=="SUSPENDED" && item.GetProperty("physicalData").ValueKind==JsonValueKind.Object,"Omitted PUT state/physical must preserve");
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Remove physical"},physicalData=(object?)null,expectedVersion=Version(item)},permissions:"catalog-items.update");
        Ensure(Version(item)==4 && item.GetProperty("physicalData").ValueKind==JsonValueKind.Null,"Explicit null physical must delete once");
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Already absent"},physicalData=(object?)null,expectedVersion=Version(item)},permissions:"catalog-items.update");
        Ensure(Version(item)==5,"Null absent physical must increment once");
        item=await Call(HttpMethod.Put,$"items/{id}/status",new {status="ACTIVE",expectedVersion=Version(item)},permissions:"catalog-items.activate");
        Ensure(Version(item)==6 && item.GetProperty("activated_at").GetString()==first,"Reactivate must preserve first activation");
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {code="Changed"},expectedVersion=Version(item)},409);
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Archived"},status="ARCHIVED",expectedVersion=Version(item)},permissions:"catalog-items.update,catalog-items.archive");
        Ensure(Version(item)==7 && item.GetProperty("status").GetString()=="ARCHIVED","Unified archive must increment once");
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Terminal"},expectedVersion=Version(item)},409);
        await Call(HttpMethod.Put,$"items/{id}/status",new {status="ACTIVE",expectedVersion=Version(item)},409);
        await using(var db=Db()) {
            Ensure((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@id AND action='deactivate'",("id",id)))! == 1,"Suspend uses deactivate audit action");
            Ensure((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@id AND action='activate'",("id",id)))! == 2,"Active creation and reactivation audited");
            Ensure((bool)(await db.Scalar("SELECT bool_and(details->'after'->>'status'='SUSPENDED') FROM foundation.audit_event WHERE record_id=@id AND action='deactivate'",("id",id)))!,"Status audit state");
        }
        var staged=await Call(HttpMethod.Post,"items",new {values,units=new[]{new {uom_id=cf,conversion_numerator="6",conversion_denominator="1",is_active=true}},identifiers=new[]{new {identifier_type="OEM",value="STAGED",uom_id=cf}},physicalData=new {net_weight="1",weight_uom_id=kg}},201);
        Ensure(Version(staged)==1 && staged.GetProperty("status").GetString()=="ACTIVE","Staged active create version");
        var stagedId=staged.GetProperty("id").GetGuid();
        await Call(HttpMethod.Put,$"items/{stagedId}",new {values=new {name="Rejected combination"},status="SUSPENDED",physicalData=new {net_weight="5",gross_weight="1"},expectedVersion=Version(staged)},400);
        Ensure((await Call(HttpMethod.Get,$"items/{stagedId}")).GetRawText()==staged.GetRawText(),"Rejected combined state/physical changed aggregate");
        async Task<int> CompetingSuspend(string name) {
            using var request=new HttpRequestMessage(HttpMethod.Put,$"/api/catalog/items/{stagedId}");
            request.Headers.Add("X-Proof-Permissions","catalog-items.update,catalog-items.deactivate");
            request.Content=JsonContent.Create(new {values=new {name},status="SUSPENDED",physicalData=new {net_weight="3"},expectedVersion=Version(staged)});
            using var response=await client.SendAsync(request);
            return (int)response.StatusCode;
        }
        Ensure((await Task.WhenAll(CompetingSuspend("Race A"),CompetingSuspend("Race B"))).Order().SequenceEqual(new[]{200,409}),"Concurrent unified transition must have one winner");
        staged=await Call(HttpMethod.Get,$"items/{stagedId}");
        Ensure(Version(staged)==2 && staged.GetProperty("status").GetString()=="SUSPENDED" && staged.GetProperty("physicalData").GetProperty("net_weight").GetString()=="3","Concurrent unified transition persisted once");
        await using(var db=Db()) {
            await db.Execute("CREATE FUNCTION masterdata.catalog_states_proof_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='catalog-items' AND NEW.tenant_id='"+tenant+"' THEN RAISE EXCEPTION 'proof audit failure'; END IF; RETURN NEW; END $$;CREATE TRIGGER catalog_states_proof_fail BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION masterdata.catalog_states_proof_fail()");
            try {
                await Call(HttpMethod.Put,$"items/{stagedId}/status",new {status="ACTIVE",expectedVersion=Version(staged)},500);
                Ensure((await Call(HttpMethod.Get,$"items/{stagedId}")).GetRawText()==staged.GetRawText(),"Failed status audit persisted transition/version");
                var config=await NumberingKernel.Read(db,tenant,"CATALOG_GOOD");
                var count=(long)(await db.Scalar("SELECT count(*) FROM masterdata.catalog_item WHERE tenant_id=@t",("t",tenant)))!;
                await Call(HttpMethod.Post,"items",new {values},500);
                Ensure(config==await NumberingKernel.Read(db,tenant,"CATALOG_GOOD"),"Failed active create audit consumed number");
                Ensure(count==(long)(await db.Scalar("SELECT count(*) FROM masterdata.catalog_item WHERE tenant_id=@t",("t",tenant)))!,"Failed active create audit persisted root");
            } finally {await db.Execute("DROP TRIGGER catalog_states_proof_fail ON foundation.audit_event;DROP FUNCTION masterdata.catalog_states_proof_fail()");}
        }
        suspended=await Call(HttpMethod.Put,$"items/{sid}",new {values=new {category_id=category,base_uom_id=pz},status="ACTIVE",expectedVersion=Version(suspended)});
        Ensure(Version(suspended)==2 && suspended.GetProperty("activated_at").ValueKind==JsonValueKind.String,"Suspended first activation through unified save");
        await app.StopAsync();
        Console.WriteLine("PASS catalog item states mapped HTTP");
    }
}
