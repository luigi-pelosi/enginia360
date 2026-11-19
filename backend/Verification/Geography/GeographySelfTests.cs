using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Geography;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using GeographyCatalog = global::Enginia360.Modules.Geography.Geography;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Text.Json;
namespace Enginia360.Verification.Geography;

public static class GeographySelfTests
{
    public static void Run(IServiceProvider services)
    {
        var failed=0; var count=0;
        void Test(string name,Action action) {count++; try {action(); Console.WriteLine("PASS "+name);} catch(Exception) {failed++; Console.WriteLine("FAIL "+name);} }
        void Assert(bool condition) {if(!condition) throw new Exception("Geography assertion failed.");}
        void Reject(Action action,int status=400) {try {action();} catch(ApiException e) when(e.Status==status) {return;} throw new Exception("Expected refusal.");}
        Test("global country city public primitives without tenant or technical code",()=> {
            foreach(var key in new[]{"countries","cities"}) {
                var r=ResourceCatalog.Get(key);
                Assert(ResourceCatalog.Scope(r)=="true" && !ResourceCatalog.Projection(r).Contains("tenant_id") && !ResourceCatalog.Projection(r).Contains("istat_code"));
                var state=new IdentityState(new User {TenantId=Guid.NewGuid()},"a","A",[]);
                var ctx=new DefaultHttpContext(); ctx.Request.QueryString=new QueryString("?tenantId=ignored");
                Assert(state.Tenant(ctx,key)==null);
            }
            Assert(PermissionCatalog.Codes.Length==61 && !PermissionCatalog.Codes.Any(c=>c.StartsWith("countries.") || c.StartsWith("cities.")));
            Assert(ResourceCatalog.Scope(ResourceCatalog.Get("users")).Contains("NOT is_super_admin"));
        });
        Test("global geography reads authenticated writes native global policy only",()=> {
            foreach(var key in new[]{"countries","cities"}) foreach(var global in new[]{false,true}) {
                using var scope=services.CreateScope();
                var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
                ctx.Items["identity"]=new IdentityState(new User {TenantId=global?null:Guid.NewGuid(),IsSuperAdmin=global},"a","A",[]);
                Security.AuthorizeResource(ctx,ResourceCatalog.Get(key),"read").GetAwaiter().GetResult();
                foreach(var action in new[]{"create","update","delete"}) {
                    if(global) Security.AuthorizeResource(ctx,ResourceCatalog.Get(key),action).GetAwaiter().GetResult();
                    else Reject(()=>Security.AuthorizeResource(ctx,ResourceCatalog.Get(key),action).GetAwaiter().GetResult(),403);
                }
                Reject(()=>Security.AuthorizeResource(ctx,ResourceCatalog.Get(key),"write").GetAwaiter().GetResult(),403);
            }
        });
        Test("geography validates ISO and hides importer field while site region optional",()=> {
            var country=ResourceCatalog.Get("countries");
            ResourceCatalog.Validate(country,JsonSerializer.SerializeToElement(new {name="Italia",iso_code="IT"}),true);
            foreach(var iso in new[]{"ZZ","it","ITA",""}) Reject(()=>ResourceCatalog.Validate(country,JsonSerializer.SerializeToElement(new {iso_code=iso}),false));
            var city=ResourceCatalog.Get("cities");
            ResourceCatalog.Validate(city,JsonSerializer.SerializeToElement(new {name="Forlì",postal_code="00100",country_id=Guid.NewGuid()}),true);
            Reject(()=>ResourceCatalog.Validate(city,JsonSerializer.SerializeToElement(new {istat_code="001001"}),false));
            ResourceCatalog.Validate(ResourceCatalog.Get("sites"),JsonSerializer.SerializeToElement(new {region=(string?)null}),false);
        });

        object? Invoke(string method,params object[] args) {
            var type=typeof(GeographyCatalog);
            var member=type?.GetMethod(method);
            Assert(member!=null);
            try {return member!.Invoke(null,args);} catch(System.Reflection.TargetInvocationException e) when(e.InnerException!=null) {throw e.InnerException;}
        }
        Test("metadata readonly is dynamic only for global catalogs",()=> {
            var method=typeof(ResourceCatalog).GetMethod("MetaReadOnly")!;
            foreach(var key in new[]{"countries","cities"}) {
                Assert((bool)method.Invoke(null,new object[]{ResourceCatalog.Get(key),new User {TenantId=Guid.NewGuid()}})!);
                Assert(!(bool)method.Invoke(null,new object[]{ResourceCatalog.Get(key),new User {IsSuperAdmin=true}})!);
            }
        });
        Test("local suggestion full label explicit clear region and no invented street",()=> {
            var row=JsonSerializer.SerializeToElement(new {name="Forlì",postal_code="47121",province="FC",region=(string?)null,iso_code="IT",country_name="Italia"});
            var item=(AddressLookup.Item)Invoke("LocalItem",row)!;
            Assert(item.address=="" && item.city=="Forlì" && item.postalCode=="47121" && item.region=="" && item.countryCode=="IT");
            Assert(item.label.Contains("Forlì") && item.label.Contains("47121") && item.label.Contains("FC") && item.label.Contains("Italia"));
        });
        Test("trusted import validates all fields duplicate technical and natural identity",()=> {
            JsonElement Rows(params object[] rows)=>JsonSerializer.SerializeToElement(rows);
            var valid=new {name="Forlì",postal_code="47121",province="FC",region="Emilia-Romagna",country_iso_code="IT",istat_code="040012"};
            Assert(((Array)Invoke("ParseImport",Rows(valid))!).Length==1);
            foreach(var field in new[]{"name","postal_code","province","region","country_iso_code","istat_code"}) {
                var map=JsonSerializer.Deserialize<Dictionary<string,object?>>(JsonSerializer.Serialize(valid))!;
                map.Remove(field); Reject(()=>Invoke("ParseImport",Rows(map)));
                foreach(var value in new string?[]{null,""," ","\u0000"}) {map[field]=value;Reject(()=>Invoke("ParseImport",Rows(map)));}
            }
            foreach(var pair in new[]{("postal_code","1234"),("postal_code","123456"),("postal_code","１２３４５"),("istat_code","12345"),("country_iso_code","FR")}) {
                var map=JsonSerializer.Deserialize<Dictionary<string,object?>>(JsonSerializer.Serialize(valid))!;map[pair.Item1]=pair.Item2;
                Reject(()=>Invoke("ParseImport",Rows(map)));
            }
            Reject(()=>Invoke("ParseImport",Rows(valid,valid)));
            Reject(()=>Invoke("ParseImport",JsonSerializer.SerializeToElement(new {items=new[]{valid}})));
            Reject(()=>Invoke("ParseImport",Rows()));
            var extra=JsonSerializer.Deserialize<Dictionary<string,object?>>(JsonSerializer.Serialize(valid))!;extra["extra"]="unexpected";
            Reject(()=>Invoke("ParseImport",Rows(extra)));
            var next=JsonSerializer.Deserialize<Dictionary<string,object?>>(JsonSerializer.Serialize(valid))!; next["postal_code"]="47122";
            Assert(((Array)Invoke("ParseImport",Rows(valid,next))!).Length==2);
        });
        Test("country ISO identity cannot change while cities reference it",()=> {
            var before=JsonSerializer.SerializeToElement(new {iso_code="IT"});
            Invoke("ValidateCountryIdentity",new Dictionary<string,object?>{{"iso_code","IT"}},before,true);
            Invoke("ValidateCountryIdentity",new Dictionary<string,object?>{{"name","Italia"}},before,true);
            Reject(()=>Invoke("ValidateCountryIdentity",new Dictionary<string,object?>{{"iso_code","FR"}},before,true),409);
            Invoke("ValidateCountryIdentity",new Dictionary<string,object?>{{"iso_code","FR"}},before,false);
        });
        Test("catalog list search includes postal province region without SQL wildcard",()=> {
            var expression=(string)Invoke("SearchExpression",ResourceCatalog.Get("cities"))!;
            Assert(expression.Contains("postal_code") && expression.Contains("province") && expression.Contains("region"));
        });
        Test("local address has no invented streets and does not open database",()=> {
            var options=new Microsoft.EntityFrameworkCore.DbContextOptionsBuilder<AppDb>();
            Microsoft.EntityFrameworkCore.NpgsqlDbContextOptionsBuilderExtensions.UseNpgsql(options,"Host=unused;Database=unused;Username=unused");
            using var db=new AppDb(options.Options);
            var type=typeof(GeographyCatalog)!;
            var task=(Task<AddressLookup.Reply>)type.GetMethod("Local")!.Invoke(null,new object[]{db,new AddressLookup.Query("address","Via Roma","IT","Roma","RM","it"),CancellationToken.None})!;
            var reply=task.GetAwaiter().GetResult(); Assert(reply.items.Length==0 && reply.attribution=="");
        });
        Test("global catalog disabled and tenant impostor cannot read or mutate",()=> {
            foreach(var key in new[]{"countries","cities"}) foreach(var user in new[]{new User {IsEnabled=false,TenantId=Guid.NewGuid()},new User {IsSuperAdmin=true,TenantId=Guid.NewGuid()},new User {IsSuperAdmin=false,TenantId=null}}) {
                using var scope=services.CreateScope();var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
                ctx.Items["identity"]=new IdentityState(user,"a","A",[key+".read",key+".update"]);
                foreach(var action in new[]{"read","create","update","delete"}) Reject(()=>Security.AuthorizeResource(ctx,ResourceCatalog.Get(key),action).GetAwaiter().GetResult(),403);
            }
        });
        Test("import rejects technical and normalized natural collisions and duplicate JSON keys",()=> {
            var valid=new {name="Forlì",postal_code="47121",province="FC",region="Emilia-Romagna",country_iso_code="IT",istat_code="040012"};
            var duplicateNatural=new {name="FORLÌ",postal_code="47121",province="fc",region="Emilia-Romagna",country_iso_code="IT",istat_code="040013"};
            var duplicateTechnical=new {name="Edited name",postal_code="47121",province="FC",region="Emilia-Romagna",country_iso_code="IT",istat_code="040012"};
            Reject(()=>Invoke("ParseImport",JsonSerializer.SerializeToElement(new object[]{valid,duplicateNatural})));
            Reject(()=>Invoke("ParseImport",JsonSerializer.SerializeToElement(new object[]{valid,duplicateTechnical})));
            using var doc=JsonDocument.Parse("["+JsonSerializer.Serialize(valid).Replace("\"name\":","\"name\":\"duplicate\",\"name\":")+"]");
            Reject(()=>Invoke("ParseImport",doc.RootElement));
        });
        Console.WriteLine($"Geography self-test: {count-failed}/{count} passed.");
        if(failed>0) Environment.ExitCode=1;
    }
}
