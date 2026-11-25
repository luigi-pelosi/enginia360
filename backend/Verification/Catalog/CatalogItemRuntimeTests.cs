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
public static class CatalogItemRuntimeTests
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
        var options=await Call(HttpMethod.Get,"item-options",permissions:"catalog-items.create");
        Ensure(options.GetProperty("numbering").GetProperty("GOOD").GetProperty("mode").GetString()=="AUTO","Options virtual numbering");
        await using(var db=Db()) Ensure((long)(await db.Scalar("SELECT count(*) FROM foundation.numbering_series WHERE tenant_id=@t",("t",tenant)))! == 0,"Options materialized numbering");
        var item=await Call(HttpMethod.Post,"items",new {values=new {name="Initial",item_type_id=good,category_id=category,base_uom_id=pz},units=new[]{new {uom_id=cf,conversion_numerator="2",conversion_denominator="3",is_active=true},new {uom_id=plt,conversion_numerator="1",conversion_denominator="3",is_active=true}},identifiers=new[]{new {identifier_type="GTIN",value="96385074",uom_id=cf,is_primary=true}},physicalData=new {net_weight="1.000000000001",gross_weight="2",weight_uom_id=kg}},201);
        var id=item.GetProperty("id").GetGuid();
        Ensure(Version(item)==1 && item.GetProperty("kind").GetString()=="GOOD","Create root version/kind");
        Ensure(item.GetProperty("physicalData").GetProperty("net_weight").GetString()=="1.000000000001","Physical decimal serialized as string");
        var combined=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Combined"},physicalData=new {net_weight="1.5"},expectedVersion=Version(item)});
        Ensure(Version(combined)==2 && combined.GetProperty("name").GetString()=="Combined" && combined.GetProperty("physicalData").GetProperty("net_weight").GetString()=="1.5","Combined update must persist both parts with one revision");
        item=combined;
        var converted=await Call(HttpMethod.Post,$"items/{id}/convert",new {sourceUnitId=cf,targetUnitId=plt,quantity="1"});
        Ensure(converted.GetProperty("quantity").GetString()=="2" && !converted.GetProperty("rounded").GetBoolean(),"Context conversion intermediate rounding");
        await Call(HttpMethod.Post,$"units/{cf}/convert",new {targetUnitId=pz,quantity="1"},400);
        var identifierId=item.GetProperty("identifiers")[0].GetProperty("id").GetGuid();
        item=await Call(HttpMethod.Put,$"items/{id}/identifiers/{identifierId}",new {values=new {value="036000291452"},expectedVersion=Version(item)});
        Ensure(Version(item)==3 && item.GetProperty("name").GetString()=="Combined" && item.GetProperty("identifiers")[0].GetProperty("id").GetGuid()==identifierId,"Child update changed main fields/id or failed version");
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Stale"},expectedVersion=1},409);
        await Call(HttpMethod.Put,$"items/{id}/status",new {status="ACTIVE",expectedVersion=Version(item)},403,"catalog-items.update");
        item=await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Renamed"},expectedVersion=Version(item)});
        item=await Call(HttpMethod.Put,$"items/{id}/status",new {status="ACTIVE",expectedVersion=Version(item)});
        Ensure(item.GetProperty("activated_at").ValueKind==JsonValueKind.String,"First activation missing");
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {code="OTHER"},expectedVersion=Version(item)},409);
        var unitId=item.GetProperty("units").EnumerateArray().Single(x=>x.GetProperty("uom_id").GetGuid()==cf).GetProperty("id").GetGuid();
        await Call(HttpMethod.Delete,$"items/{id}/units/{unitId}?expectedVersion={Version(item)}",status:400);
        item=await Call(HttpMethod.Put,$"items/{id}/physical-data",new {values=(object?)null,expectedVersion=Version(item)});
        Ensure(item.GetProperty("physicalData").ValueKind==JsonValueKind.Null,"Physical explicit removal");
        item=await Call(HttpMethod.Put,$"items/{id}/status",new {status="ARCHIVED",expectedVersion=Version(item)});
        await Call(HttpMethod.Post,$"items/{id}/identifiers",new {values=new {identifier_type="OEM",value="X"},expectedVersion=Version(item)},409);
        await using(var db=Db()) {
            await using var tx=await db.Database.BeginTransactionAsync();
            var config=await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE");
            await NumberingKernel.Save(db,tenant,"CATALOG_SERVICE",config with {Mode="MANUAL"});
            await tx.CommitAsync();
        }
        var serviceItem=await Call(HttpMethod.Post,"items",new {values=new {name="Service",code="SERVICE-OLD",item_type_id=service}},201);
        var serviceId=serviceItem.GetProperty("id").GetGuid();
        serviceItem=await Call(HttpMethod.Put,$"items/{serviceId}",new {values=new {code="SERVICE-NEW"},expectedVersion=Version(serviceItem)});
        await Call(HttpMethod.Put,$"items/{serviceId}",new {values=new {code="SERVICE-OLD"},expectedVersion=Version(serviceItem)},409);
        await Call(HttpMethod.Post,"items",new {values=new {name="Collision",code="SERVICE-OLD",item_type_id=service}},409);
        await Call(HttpMethod.Put,$"items/{serviceId}/physical-data",new {values=new {net_weight="1",weight_uom_id=kg},expectedVersion=Version(serviceItem)},400);
        await Call(HttpMethod.Put,$"items/{serviceId}/status",new {status="ACTIVE",expectedVersion=Version(serviceItem)},400);
        await Call(HttpMethod.Post,"items",new {values=new {name="Invalid GTIN",item_type_id=good,base_uom_id=pz},identifiers=new[]{new {identifier_type="GTIN",value="96385075"}}},400);
        var list=await Call(HttpMethod.Get,"items?search=036000291452&pageSize=1");
        Ensure(list.GetProperty("total").GetInt64()==1 && list.GetProperty("items").GetArrayLength()==1,"Identifier search/paging");
        var brand=await Call(HttpMethod.Post,"brands",new {values=new {name="Brand",code="BR",description="Description"}},201);
        Ensure(brand.GetProperty("description").GetString()=="Description","Brand description");
        await Call(HttpMethod.Put,$"brands/{brand.GetProperty("id").GetGuid()}",new {values=new {is_active=false},expectedVersion=brand.GetProperty("version").GetInt64()});
        var concurrent=await Task.WhenAll(
            Call(HttpMethod.Post,"items",new {values=new {name="Concurrent A",item_type_id=good}},201),
            Call(HttpMethod.Post,"items",new {values=new {name="Concurrent B",item_type_id=good}},201));
        Ensure(concurrent.Select(x=>x.GetProperty("code").GetString()).Distinct().Count()==2,"Concurrent automatic item codes collided");
        var implicitBase=await Call(HttpMethod.Post,"items",new {values=new {name="Implicit base",item_type_id=good,base_uom_id=pz},identifiers=new[]{new {identifier_type="OEM",value="IMPLICIT"}}},201);
        var implicitId=implicitBase.GetProperty("id").GetGuid();
        await Call(HttpMethod.Put,$"items/{implicitId}",new {values=new {base_uom_id=kg},expectedVersion=Version(implicitBase)},409);
        var physicalBase=await Call(HttpMethod.Post,"items",new {values=new {name="Physical base",item_type_id=good,base_uom_id=pz},physicalData=new {net_weight="1",weight_uom_id=kg}},201);
        await Call(HttpMethod.Put,$"items/{physicalBase.GetProperty("id").GetGuid()}",new {values=new {base_uom_id=kg},expectedVersion=Version(physicalBase)},409);
        var aggregate=await Call(HttpMethod.Post,"items",new {values=new {name="Atomic",item_type_id=good,base_uom_id=pz}},201);
        var aggregateId=aggregate.GetProperty("id").GetGuid();
        aggregate=await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Atomic physical"},physicalData=new {net_weight="3",weight_uom_id=kg},expectedVersion=Version(aggregate)},permissions:"catalog-items.update");
        Ensure(Version(aggregate)==2 && aggregate.GetProperty("physicalData").GetProperty("net_weight").GetString()=="3","Combined physical insert/version");
        await using(var db=Db()) {
            Ensure((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@id AND action='update'",("id",aggregateId)))! == 1,"Combined update must create exactly one audit");
            Ensure((bool)(await db.Scalar("SELECT details->'before' ? 'physicalData' AND details->'after'->'physicalData'->>'net_weight'='3' FROM foundation.audit_event WHERE record_id=@id AND action='update'",("id",aggregateId)))!,"Audit must capture physical before and after");
        }
        var stable=aggregate.GetRawText();
        await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Rejected"},physicalData=new {net_weight="5",gross_weight="1"},expectedVersion=Version(aggregate)},400);
        await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Stale"},physicalData=(object?)null,expectedVersion=1},409);
        await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {base_uom_id=kg},physicalData=(object?)null,expectedVersion=Version(aggregate)},409);
        Ensure((await Call(HttpMethod.Get,$"items/{aggregateId}")).GetRawText()==stable,"Rejected combined update changed aggregate");
        aggregate=await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Main only"},expectedVersion=Version(aggregate)});
        Ensure(Version(aggregate)==3 && aggregate.GetProperty("physicalData").GetProperty("net_weight").GetString()=="3","Absent physicalData must preserve row");
        aggregate=await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="No physical"},physicalData=(object?)null,expectedVersion=Version(aggregate)});
        Ensure(Version(aggregate)==4 && aggregate.GetProperty("physicalData").ValueKind==JsonValueKind.Null,"Combined physical delete/version");
        aggregate=await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Still absent"},physicalData=(object?)null,expectedVersion=Version(aggregate)});
        Ensure(Version(aggregate)==5 && aggregate.GetProperty("physicalData").ValueKind==JsonValueKind.Null,"Null on absent physical must still advance once");
        await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Denied"},physicalData=(object?)null,expectedVersion=Version(aggregate)},403,"catalog-items.read");
        async Task<int> ConcurrentUpdate(string name) {
            using var request=new HttpRequestMessage(HttpMethod.Put,$"/api/catalog/items/{aggregateId}");
            request.Headers.Add("X-Proof-Permissions","catalog-items.update");
            request.Content=JsonContent.Create(new {values=new {name},physicalData=new {net_weight="4",weight_uom_id=kg},expectedVersion=Version(aggregate)});
            using var response=await client.SendAsync(request);
            return (int)response.StatusCode;
        }
        var outcomes=await Task.WhenAll(ConcurrentUpdate("Race A"),ConcurrentUpdate("Race B"));
        Ensure(outcomes.Order().SequenceEqual(new[]{200,409}),"Concurrent combined writes must yield one success and one stale conflict");
        aggregate=await Call(HttpMethod.Get,$"items/{aggregateId}");
        Ensure(Version(aggregate)==6 && aggregate.GetProperty("physicalData").GetProperty("net_weight").GetString()=="4","Concurrent winner must persist one complete revision");
        await Call(HttpMethod.Put,$"items/{serviceId}",new {values=new {name="Reject service"},physicalData=new {net_weight="1",weight_uom_id=kg},expectedVersion=Version(serviceItem)},400);
        Ensure((await Call(HttpMethod.Get,$"items/{serviceId}")).GetRawText()==serviceItem.GetRawText(),"Service combined rejection changed aggregate");
        await Call(HttpMethod.Put,$"items/{id}",new {values=new {name="Archived rejection"},physicalData=(object?)null,expectedVersion=Version(item)},409);
        // Fallimento audit immediato: codice, contatore, figli e radice devono tornare identici.
        await using(var db=Db()) {
            await db.Execute("CREATE FUNCTION masterdata.catalog_items_proof_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='catalog-items' AND NEW.tenant_id='"+tenant+"' THEN RAISE EXCEPTION 'proof audit failure'; END IF; RETURN NEW; END $$;CREATE TRIGGER catalog_items_proof_fail BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION masterdata.catalog_items_proof_fail()");
            var before=await NumberingKernel.Read(db,tenant,"CATALOG_GOOD");
            var count=(long)(await db.Scalar("SELECT count(*) FROM masterdata.catalog_item WHERE tenant_id=@t",("t",tenant)))!;
            await Call(HttpMethod.Put,$"items/{aggregateId}",new {values=new {name="Audit rejected"},physicalData=new {net_weight="7",weight_uom_id=kg},expectedVersion=Version(aggregate)},500);
            Ensure((await Call(HttpMethod.Get,$"items/{aggregateId}")).GetRawText()==aggregate.GetRawText(),"Failed audit persisted combined update");
            await Call(HttpMethod.Post,"items",new {values=new {name="Audit rollback",item_type_id=good}},500);
            Ensure(before==await NumberingKernel.Read(db,tenant,"CATALOG_GOOD"),"Failed audit consumed number");
            Ensure(count==(long)(await db.Scalar("SELECT count(*) FROM masterdata.catalog_item WHERE tenant_id=@t",("t",tenant)))!,"Failed audit persisted item");
            await db.Execute("DROP TRIGGER catalog_items_proof_fail ON foundation.audit_event;DROP FUNCTION masterdata.catalog_items_proof_fail()");
        }
        await app.StopAsync();
        Console.WriteLine("PASS catalog items HTTP runtime: native policies, options, atomic aggregate, GTIN, version, contextual exact ratios, lifecycle, physical, brands, search and audit rollback (identity injected; cookie/CSRF excluded)");
    }
}
