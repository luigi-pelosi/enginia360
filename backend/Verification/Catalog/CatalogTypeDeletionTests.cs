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
public static class CatalogTypeDeletionTests
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
                await db.Execute("SET LOCAL ROLE enginia360_app");
                await next(ctx);
                await tx.CommitAsync();
                buffered.Position=0;ctx.Response.Body=response;await buffered.CopyToAsync(response);
            } catch(Npgsql.PostgresException) {
                await tx.RollbackAsync();ctx.Response.Body=response;ctx.Response.Clear();ctx.Response.StatusCode=500;
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
        const string deletePermission="catalog-types.delete";
        async Task<JsonElement> CheckType(Guid id)=>await Call(HttpMethod.Get,$"types/{id}/deletion-check",permissions:deletePermission);
        async Task Delete(Guid id,long version=1,int status=204)=>await Call(HttpMethod.Delete,$"types/{id}?expectedVersion={version}",status:status,permissions:deletePermission);
        foreach(var kind in new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"}) {
            var row=await Call(HttpMethod.Post,"types",new {values=new {name="Delete "+kind,kind}},201);
            var id=row.GetProperty("id").GetGuid();
            Ensure((await CheckType(id)).GetProperty("canDelete").GetBoolean(),"Unused allowed");
            Ensure((await CheckType(id)).EnumerateObject().Count()==1,"No counts leaked");
            Ensure((await Call(HttpMethod.Get,$"types/{id}")).GetProperty("version").GetInt64()==1,"GET did not mutate version");
            await Call(HttpMethod.Get,$"types/{id}/deletion-check",status:403,permissions:"catalog-items.read");
            await Call(HttpMethod.Delete,$"types/{id}?expectedVersion=1",status:403,permissions:"catalog-types.update");
            await Delete(id,2,409);
            await Call(HttpMethod.Delete,$"types/{id}",status:400,permissions:deletePermission);
            await Delete(id);
            await Call(HttpMethod.Get,$"types/{id}/deletion-check",status:404,permissions:deletePermission);
            await using var db=Db();
            Ensure((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.audit_event WHERE tenant_id=@t AND record_id=@id AND action='delete' AND resource='catalog-types' AND details->'after'='null'::jsonb AND details->'before'->>'kind'=@kind)",("t",tenant),("id",id),("kind",kind)))!,"Minimized delete audit");
        }
        foreach(var status in new[]{"ACTIVE","SUSPENDED","ARCHIVED"}) {
            var type=await Call(HttpMethod.Post,"types",new {values=new {name=status,kind="GOOD"}},201);
            var id=type.GetProperty("id").GetGuid();
            var row=await Call(HttpMethod.Post,"items",new {values=new {name=status,item_type_id=id,category_id=category,base_uom_id=pz}},201);
            var item=row.GetProperty("id").GetGuid();
            if(status!="ACTIVE") {
                await using var db=Db();await using var tx=await db.Database.BeginTransactionAsync();
                await db.Execute("UPDATE masterdata.catalog_item SET status=@status,version=version+1 WHERE id=@id",("status",status),("id",item));await tx.CommitAsync();
            }
            Ensure(!(await CheckType(id)).GetProperty("canDelete").GetBoolean(),"Every status blocks");
            var error=await Call(HttpMethod.Delete,$"types/{id}?expectedVersion=1",status:409,permissions:deletePermission);
            Ensure(error.GetProperty("error").GetString()=="item_type_in_use","Specific in-use code");
        }
        var foreign=Guid.NewGuid();
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Foreign');INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES(@id,@t,'Foreign','GOOD')",("t",foreign),("code",foreign.ToString()),("id",foreign));await tx.CommitAsync();
        }
        await Call(HttpMethod.Get,$"types/{foreign}/deletion-check",status:404,permissions:deletePermission);
        await Delete(foreign,status:404);
        var rollback=await Call(HttpMethod.Post,"types",new {values=new {name="Audit rollback",kind="CHARGE"}},201);
        var rollbackId=rollback.GetProperty("id").GetGuid();
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("CREATE FUNCTION foundation.fail_type_delete_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='delete' AND NEW.resource='catalog-types' THEN RAISE EXCEPTION 'proof audit'; END IF;RETURN NEW;END $$;CREATE TRIGGER proof_type_delete_audit BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.fail_type_delete_audit()");await tx.CommitAsync();
        }
        await Delete(rollbackId,status:500);
        Ensure((await CheckType(rollbackId)).GetProperty("canDelete").GetBoolean(),"Audit error rolls delete back");
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();await db.Execute("DROP TRIGGER proof_type_delete_audit ON foundation.audit_event;DROP FUNCTION foundation.fail_type_delete_audit()");await tx.CommitAsync();
        }
        await app.StopAsync();
        Console.WriteLine("PASS catalog type deletion mapped HTTP");
    }
}
