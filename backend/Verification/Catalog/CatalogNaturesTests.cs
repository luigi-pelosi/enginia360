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
public static class CatalogNaturesTests
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
        async Task<JsonElement> Call(HttpMethod method,string path,object? body=null,int status=200,string permissions="catalog-items.read,catalog-items.create,catalog-items.update,catalog-items.activate,catalog-items.deactivate,catalog-items.archive,catalog-brands.read,catalog-brands.create,catalog-brands.update,catalog-units.read,catalog-units.create,catalog-types.read,catalog-types.create,catalog-types.update,catalog-numbering.read,catalog-numbering.update") {
            using var request=new HttpRequestMessage(method,"/api/catalog/"+path);
            request.Headers.Add("X-Proof-Permissions",permissions);
            if(body!=null) request.Content=JsonContent.Create(body);
            using var response=await client.SendAsync(request);
            var text=await response.Content.ReadAsStringAsync();
            Ensure((int)response.StatusCode==status,$"{method} {path}: expected {status}, got {(int)response.StatusCode}: {text}");
            return text.Length==0?default:JsonSerializer.Deserialize<JsonElement>(text);
        }
        var kinds=new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"};
        var prefixes=new[]{"ART-","IMM-","SRV-","ONR-"};
        var types=new Dictionary<string,Guid>();
        Ensure(NumberingKernel.Prefix("BUSINESS_PARTNER")=="BP-","BP prefix unchanged");
        var options=await Call(HttpMethod.Get,"item-options");
        Ensure(options.GetProperty("numbering").EnumerateObject().Select(x=>x.Name).Order().SequenceEqual(kinds.Order()),"Four uppercase numbering keys");
        // I nuovi tenant conservano soltanto i due default minimi storici.
        Ensure(options.GetProperty("types").GetArrayLength()==2,"No new nature seed");
        foreach(var kind in kinds) {
            var type=await Call(HttpMethod.Post,"types",new {values=new {name="Nature "+kind,kind,default_sellable=false,default_purchasable=true}},201);
            types[kind]=type.GetProperty("id").GetGuid();
            Ensure(!type.GetProperty("default_sellable").GetBoolean() && type.GetProperty("default_purchasable").GetBoolean(),"Flags configurable");
            await Call(HttpMethod.Put,$"types/{types[kind]}",new {values=new {kind=kind=="GOOD"?"SERVICE":"GOOD"},expectedVersion=1},409);
            if(kind!="GOOD") {
                var error=await Call(HttpMethod.Post,"types",new {values=new {name="Stock forbidden",kind,default_track_stock=true}},400);
                Ensure(error.GetProperty("error").GetString()==(kind=="SERVICE"?"service_cannot_track_stock":"nonphysical_cannot_track_stock"),"Specific stock rejection");
                await Call(HttpMethod.Put,$"types/{types[kind]}",new {values=new {default_track_stock=true},expectedVersion=1},400);
            }
        }
        await Call(HttpMethod.Post,"types",new {values=new {name="Invalid",kind="GOODS"}},400);
        await Call(HttpMethod.Post,"types",new {values=new {name="Too long",kind="INTANGIBLEX"}},400);
        await Call(HttpMethod.Get,"numbering?kind=GOODS",status:400);
        await Call(HttpMethod.Get,"items?kind=GOODS",status:400);
        for(var n=0;n<kinds.Length;n++) {
            var kind=kinds[n];var type=types[kind];
            var config=await Call(HttpMethod.Get,"numbering?kind="+kind);
            Ensure(config.GetProperty("prefix").GetString()==prefixes[n] && config.GetProperty("nextNumber").GetInt64()==1 && config.GetProperty("padding").GetInt32()==6 && config.GetProperty("mode").GetString()=="AUTO","Independent defaults");
            for(var sequence=1;sequence<=2;sequence++) {
                var row=await Call(HttpMethod.Post,"items",new {values=new {name="Item "+kind,item_type_id=type,category_id=category,base_uom_id=pz}},201);
                Ensure(row.GetProperty("code").GetString()==prefixes[n]+sequence.ToString("D6") && row.GetProperty("kind").GetString()==kind,"Independent auto allocation");
                var id=row.GetProperty("id").GetGuid();
                await Call(HttpMethod.Put,$"items/{id}",new {values=new {item_type_id=types[kind=="GOOD"?"CHARGE":"GOOD"]},expectedVersion=1},409);
                // Una tipologia della stessa natura resta modificabile anche dopo attivazione.
                var alternative=await Call(HttpMethod.Post,"types",new {values=new {name="Alternative "+kind,kind}},201);
                row=await Call(HttpMethod.Put,$"items/{id}",new {values=new {item_type_id=alternative.GetProperty("id").GetGuid()},expectedVersion=1});
                if(kind!="GOOD") {
                    await Call(HttpMethod.Put,$"items/{id}/physical-data",new {values=new {net_weight="1",weight_uom_id=kg},expectedVersion=2},400);
                    await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Physical denied"},physicalData=new {net_weight="1",weight_uom_id=kg},expectedVersion=2},400);
                }
            }
            var list=await Call(HttpMethod.Get,"items?kind="+kind);
            Ensure(list.GetProperty("total").GetInt64()==2 && list.GetProperty("items").EnumerateArray().All(x=>x.GetProperty("kind").GetString()==kind),"Four list filters");
            config=await Call(HttpMethod.Get,"numbering?kind="+kind);
            Ensure(config.GetProperty("nextNumber").GetInt64()==3,"Only selected series advances");
            if(kind!="GOOD") {
                await Call(HttpMethod.Post,"items",new {values=new {name="Physical denied",item_type_id=type,category_id=category,base_uom_id=pz},physicalData=new {net_weight="1",weight_uom_id=kg}},400);
                Ensure((await Call(HttpMethod.Get,"numbering?kind="+kind)).GetProperty("nextNumber").GetInt64()==3,"Rejected physical rolls back numbering");
            }
        }
        tenant=Guid.NewGuid();category=Guid.NewGuid();
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Manual proof')",("t",tenant),("code",tenant.ToString()));
            await CatalogSeed.Seed(db,tenant,actor);
            await db.Execute("INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES(@c,@t,'Manual')",("c",category),("t",tenant));
            pz=(Guid)(await db.Scalar("SELECT id FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND code='PZ'",("t",tenant)))!;
            await tx.CommitAsync();
        }
        foreach(var kind in kinds) {
            var type=await Call(HttpMethod.Post,"types",new {values=new {name=kind,kind}},201);
            await Call(HttpMethod.Put,"numbering?kind="+kind,new {mode="MANUAL",prefix="",padding=6,nextNumber=1,version=0});
            var vals=new {name="Manual "+kind,item_type_id=type.GetProperty("id").GetGuid(),category_id=category,base_uom_id=pz,code=kind=="GOOD"?"SHARED":kind};
            var row=await Call(HttpMethod.Post,"items",new {values=vals,status="SUSPENDED"},201);
            if(kind!="GOOD") await Call(HttpMethod.Post,"items",new {values=new {name="Collision",item_type_id=type.GetProperty("id").GetGuid(),category_id=category,base_uom_id=pz,code="shared"}},409);
            var config=await Call(HttpMethod.Get,"numbering?kind="+kind);
            Ensure(config.GetProperty("nextNumber").GetInt64()==1 && config.GetProperty("mode").GetString()=="MANUAL","Manual counter unchanged");
            await Call(HttpMethod.Post,"items",new {values=new {name="Missing manual",item_type_id=type.GetProperty("id").GetGuid(),category_id=category,base_uom_id=pz}},400);
        }
        await app.StopAsync();
        Console.WriteLine("PASS catalog natures mapped HTTP");
    }
}
