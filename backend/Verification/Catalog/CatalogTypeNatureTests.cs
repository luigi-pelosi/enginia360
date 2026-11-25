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
public static class CatalogTypeNatureTests
{
    public static async Task Run(string connection)
    {
        var assertions=0;var requests=0;
        void Ensure(bool ok,string message) {assertions++;if(!ok) throw new Exception(message);}
        AppDb Db()=>new(new DbContextOptionsBuilder<AppDb>().UseNpgsql(connection).Options);
        var tenant=Guid.NewGuid();var actor=Guid.NewGuid();var category=Guid.NewGuid();
        Guid pz;
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Items runtime');INSERT INTO foundation.\"user\"(id,tenant_id,username,email,first_name,last_name) VALUES(@actor,@t,@username,'proof@example.test','SQL','Proof')",("t",tenant),("code",tenant.ToString()),("actor",actor),("username",actor.ToString()));
            await CatalogSeed.Seed(db,tenant,actor);
            await db.Execute("INSERT INTO masterdata.catalog_category(id,tenant_id,name) VALUES(@id,@t,'Categoria')",("id",category),("t",tenant));
            pz=(Guid)(await db.Scalar("SELECT id FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND code='PZ'",("t",tenant)))!;
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
            requests++;
            using var request=new HttpRequestMessage(method,"/api/catalog/"+path);
            request.Headers.Add("X-Proof-Permissions",permissions);
            if(body!=null) request.Content=JsonContent.Create(body);
            using var response=await client.SendAsync(request);
            var text=await response.Content.ReadAsStringAsync();
            Ensure((int)response.StatusCode==status,$"{method} {path}: expected {status}, got {(int)response.StatusCode}: {text}");
            return text.Length==0?default:JsonSerializer.Deserialize<JsonElement>(text);
        }
        async Task<JsonElement> NewType(string kind,string name="Unused",bool stock=false)=>await Call(HttpMethod.Post,"types",new {values=new {name,kind,default_track_stock=stock}},201,"catalog-types.create");
        async Task<JsonElement> ReadType(Guid id)=>await Call(HttpMethod.Get,$"types/{id}",permissions:"catalog-types.read");
        async Task<long> AuditCount(Guid id) {
            await using var db=Db();
            return (long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND record_id=@id AND resource='catalog-types'",("t",tenant),("id",id)))!;
        }
        foreach(var oldKind in new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"}) {
            foreach(var newKind in new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"}) {
                if(oldKind==newKind)continue;
                var row=await NewType(oldKind);var id=row.GetProperty("id").GetGuid();
                Ensure(row.TryGetProperty("canChangeKind",out var flag) && flag.GetBoolean(),"POST authoritative canChangeKind=true");
                var read=await ReadType(id);
                Ensure(read.GetProperty("canChangeKind").GetBoolean(),"Read-only type permission sufficient");
                var changed=await Call(HttpMethod.Put,$"types/{id}",new {values=new {kind=newKind},expectedVersion=1},permissions:"catalog-types.update");
                Ensure(changed.GetProperty("kind").GetString()==newKind && changed.GetProperty("canChangeKind").GetBoolean(),"Unused type changes nature with update permission only");
                Ensure(changed.GetProperty("version").GetInt64()==2,"Nature update increments version");
                if(oldKind=="GOOD" && newKind=="INTANGIBLE") {
                    Console.WriteLine("TYPE_NATURE_RESPONSE POST "+row.GetRawText());
                    Console.WriteLine("TYPE_NATURE_RESPONSE GET "+read.GetRawText());
                    Console.WriteLine("TYPE_NATURE_RESPONSE PUT "+changed.GetRawText());
                }
                var stale=await Call(HttpMethod.Put,$"types/{id}",new {values=new {kind=oldKind},expectedVersion=1},409,"catalog-types.update");
                Ensure(stale.GetProperty("error").GetString()=="stale_version","Stale version refused");
                Ensure((await ReadType(id)).GetProperty("kind").GetString()==newKind,"Stale edit does not change type");
                Ensure(await AuditCount(id)==2,"Exactly create/update audit; no stale audit");
                await using var db=Db();
                Ensure((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.audit_event WHERE tenant_id=@t AND record_id=@id AND action='update' AND details->'before'->>'kind'=@old AND details->'after'->>'kind'=@new AND NOT (details->'after' ? 'canChangeKind'))",("t",tenant),("id",id),("old",oldKind),("new",newKind)))!,"Changed nature audit includes only requested values");
            }
        }
        // Una tipologia modificata ancora inutilizzata usa la serie autonoma della nuova natura.
        var numberedKinds=new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"};
        foreach(var kind in numberedKinds) {
            var before=await Call(HttpMethod.Get,"numbering?kind="+kind);
            await Call(HttpMethod.Put,"numbering?kind="+kind,new {mode="AUTO",prefix=kind+"-",padding=4,nextNumber=73,version=before.GetProperty("version").GetInt64()});
        }
        var consumed=new HashSet<string>();
        foreach(var kind in numberedKinds) {
            var type=await NewType(kind=="GOOD"?"SERVICE":"GOOD");var id=type.GetProperty("id").GetGuid();
            await Call(HttpMethod.Put,$"types/{id}",new {values=new {kind},expectedVersion=1},permissions:"catalog-types.update");
            var row=await Call(HttpMethod.Post,"items",new {values=new {name="Changed nature numbering",item_type_id=id,category_id=category,base_uom_id=pz}},201);
            Ensure(row.GetProperty("code").GetString()==kind+"-0073","Changed type uses new nature's numbering");
            consumed.Add(kind);
            foreach(var other in numberedKinds) {
                var numbering=await Call(HttpMethod.Get,"numbering?kind="+other);
                Ensure(numbering.GetProperty("nextNumber").GetInt64()==(consumed.Contains(other)?74:73),"Other nature counters remain independent");
            }
        }
        foreach(var kind in new[]{"GOOD","INTANGIBLE","SERVICE","CHARGE"}) {
            foreach(var status in new[]{"ACTIVE","SUSPENDED","ARCHIVED"}) {
                var type=await NewType(kind,status);var id=type.GetProperty("id").GetGuid();
                var row=await Call(HttpMethod.Post,"items",new {values=new {name=status,item_type_id=id,category_id=category,base_uom_id=pz}},201);
                var item=row.GetProperty("id").GetGuid();
                if(status!="ACTIVE") {
                    await using var db=Db();await using var tx=await db.Database.BeginTransactionAsync();
                    await db.Execute("UPDATE masterdata.catalog_item SET status=@status,version=version+1 WHERE id=@id",("status",status),("id",item));await tx.CommitAsync();
                }
                Ensure(!(await ReadType(id)).GetProperty("canChangeKind").GetBoolean(),"Every reference status blocks nature changes without item/delete grants");
                var next=kind=="GOOD"?"SERVICE":"GOOD";
                var error=await Call(HttpMethod.Put,$"types/{id}",new {values=new {kind=next},expectedVersion=1},409,"catalog-types.update");
                Ensure(error.GetProperty("error").GetString()=="immutable_item_kind","Specific in-use kind code");
                var changed=await Call(HttpMethod.Put,$"types/{id}",new {values=new {name="Renamed",kind},expectedVersion=1},permissions:"catalog-types.update");
                Ensure(changed.GetProperty("kind").GetString()==kind && !changed.GetProperty("canChangeKind").GetBoolean() && changed.GetProperty("version").GetInt64()==2,"Same-kind referenced name updates remain valid");
                Ensure(await AuditCount(id)==2,"Rejected nature edit has no audit");
                await using var verifyDb=Db();
                Ensure((string)(await verifyDb.Scalar("SELECT t.kind FROM masterdata.catalog_item i JOIN masterdata.catalog_item_type t ON t.tenant_id=i.tenant_id AND t.id=i.item_type_id WHERE i.id=@id",("id",item)))! == kind,"Existing item nature never reinterpreted");
            }
        }
        var list=await Call(HttpMethod.Get,"types",permissions:"catalog-types.read");
        Ensure(list.GetProperty("items").EnumerateArray().All(x=>!x.TryGetProperty("canChangeKind",out _)),"No metadata added to list contract");
        var sample=await NewType("GOOD");var sampleId=sample.GetProperty("id").GetGuid();
        await Call(HttpMethod.Get,$"types/{sampleId}",status:403,permissions:"catalog-items.read");
        await Call(HttpMethod.Get,$"types/{sampleId}/deletion-check",status:403,permissions:"catalog-types.read");
        await Call(HttpMethod.Put,$"types/{sampleId}",new {values=new {canChangeKind=false},expectedVersion=1},400,"catalog-types.update");
        foreach(var kind in new[]{"INTANGIBLE","SERVICE","CHARGE"}) {
            var error=await Call(HttpMethod.Put,$"types/{sampleId}",new {values=new {kind,default_track_stock=true},expectedVersion=1},400,"catalog-types.update");
            Ensure(error.GetProperty("error").GetString()==(kind=="SERVICE"?"service_cannot_track_stock":"nonphysical_cannot_track_stock"),"Nonphysical stock invalid payload rejected");
        }
        Ensure((await ReadType(sampleId)).GetProperty("version").GetInt64()==1 && await AuditCount(sampleId)==1,"Validation errors leave version and audit unchanged");
        var foreign=Guid.NewGuid();
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Foreign');INSERT INTO masterdata.catalog_item_type(id,tenant_id,name,kind) VALUES(@id,@t,'Foreign','GOOD')",("t",foreign),("code",foreign.ToString()),("id",foreign));await tx.CommitAsync();
        }
        await Call(HttpMethod.Get,$"types/{foreign}",status:404,permissions:"catalog-types.read");
        await Call(HttpMethod.Put,$"types/{foreign}",new {values=new {kind="SERVICE"},expectedVersion=1},404,"catalog-types.update");
        await Call(HttpMethod.Get,$"types/{Guid.NewGuid()}",status:404,permissions:"catalog-types.read");
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("CREATE FUNCTION foundation.fail_type_nature_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='update' AND NEW.resource='catalog-types' THEN RAISE EXCEPTION 'proof audit'; END IF;RETURN NEW;END $$;CREATE TRIGGER proof_type_nature_audit BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.fail_type_nature_audit()");await tx.CommitAsync();
        }
        try {
            await Call(HttpMethod.Put,$"types/{sampleId}",new {values=new {kind="CHARGE"},expectedVersion=1},500,"catalog-types.update");
            var retained=await ReadType(sampleId);
            Ensure(retained.GetProperty("kind").GetString()=="GOOD" && retained.GetProperty("version").GetInt64()==1 && retained.GetProperty("canChangeKind").GetBoolean(),"Audit failure rolls back type nature/version");
            Ensure(await AuditCount(sampleId)==1,"Audit failure leaves no partial event");
        } finally {
            await using var db=Db();await using var tx=await db.Database.BeginTransactionAsync();
            await db.Execute("DROP TRIGGER proof_type_nature_audit ON foundation.audit_event;DROP FUNCTION foundation.fail_type_nature_audit()");await tx.CommitAsync();
        }
        await app.StopAsync();
        Console.WriteLine($"PASS catalog type nature mapped HTTP: {requests} requests, {assertions} assertions; 12 unused directed pairs, 12 nature/status combinations");
    }
}
