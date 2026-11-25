using Enginia360.Modules.Geography;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Enginia360.Verification.Shared;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Text.Json;
using System.Reflection;
namespace Enginia360.Verification.Organizations;
public static class SiteAddressSelfTests
{
    static void Assert(bool ok,string message) { if(!ok) throw new Exception(message); }
    static JsonElement Json(string text)=>JsonSerializer.Deserialize<JsonElement>(text);
    static void Reject(Action action,string code="validation_error") {try {action();} catch(ApiException e) when(e.Status==400 && e.Code==code) {return;} throw new Exception("Expected "+code);}
    public static void Fiscal(Action<string,Action> test)
    {
        var site=ResourceCatalog.Get("sites");
        foreach(var fieldName in new[]{"address","city","province","postal_code","country_code"})
            test("addresses: required field tracer "+fieldName,()=> {
                var payload=new {name="Synthetic site",company_id="00000000-0000-0000-0000-000000000001",tax_code="SYNTHETIC-TAX",address="Synthetic Road 42",city="Synthetic City",province="Synthetic Region",postal_code="AB 12-X",country_code="GB"};
                var values=ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(payload),true);
                Assert(values.ContainsKey(fieldName),"Complete payload must support "+fieldName);
                Assert(site.Fields.Single(f=>f.Name==fieldName).Required,"Required metadata missing: "+fieldName);
            });
        foreach(var fieldName in new[]{"address","city","province","postal_code","country_code"})
            test("addresses: required input create and patch cases "+fieldName,()=> {
                Dictionary<string,object?> Complete()=>new() {
                    ["name"]="Synthetic site",["company_id"]="00000000-0000-0000-0000-000000000001",["tax_code"]="SYNTHETIC-TAX",
                    ["address"]="Synthetic Road 42",["city"]="Synthetic City",["province"]="Synthetic Region",["postal_code"]="AB 12-X",["country_code"]="GB"
                };
                var complete=Complete();
                ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(complete),true);
                var missing=Complete(); missing.Remove(fieldName);
                Reject(()=>ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(missing),true));
                var patch=ResourceCatalog.Validate(site,Json("""{"name":"Renamed synthetic site"}"""),false);
                Assert(!patch.ContainsKey(fieldName),"Omitted patch must not overwrite "+fieldName);
                foreach(var blank in new string?[]{null,""," "," \t\r\n ","\u00a0\u2003"}) {
                    var invalid=Complete(); invalid[fieldName]=blank;
                    Reject(()=>ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(invalid),true));
                    Reject(()=>ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(new Dictionary<string,object?> {[fieldName]=blank}),false));
                }
                var replacement=fieldName=="country_code" ? "CA" : "Synthetic foreign value - 李 42";
                var update=ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(new Dictionary<string,object?> {[fieldName]=replacement}),false);
                Assert(update.Count==1 && Equals(update[fieldName],replacement),"Valid foreign patch changed "+fieldName);
            });
        test("addresses: site code immediately follows name and country select has 249",()=> {
            var names=site.Fields.Select(f=>f.Name).ToArray(); Assert(Array.IndexOf(names,"code")==Array.IndexOf(names,"name")+1,"Code not immediately after name");
            var country=site.Fields.Single(f=>f.Name=="country_code"); Assert(country.Type=="select" && country.Options?.Distinct().Count()==249,"Country select missing ISO249");
        });
        test("addresses: tax identity required on create after accepted complete payload",()=> {
            ResourceCatalog.Validate(site,Json("""{"name":"Site","company_id":"00000000-0000-0000-0000-000000000001","vat_number":" X ","address":"Synthetic Road 42","city":"Synthetic City","province":"Synthetic Region","postal_code":"AB 12-X","country_code":"GB"}"""),true);
            const string completeAddress="\"address\":\"Synthetic Road 42\",\"city\":\"Synthetic City\",\"province\":\"Synthetic Region\",\"postal_code\":\"AB 12-X\",\"country_code\":\"GB\"";
            foreach(var tax in new[]{"",",\"vat_number\":null,\"tax_code\":null",",\"vat_number\":\"  \",\"tax_code\":\" \",".TrimEnd(',')})
                Reject(()=>ResourceCatalog.Validate(site,Json("{\"name\":\"Site\",\"company_id\":\"00000000-0000-0000-0000-000000000001\","+completeAddress+tax+"}"),true),"tax_identity_required");
        });
        test("addresses: fiscal normalization and required country whitelist",()=> {
            var values=ResourceCatalog.Validate(site,Json("""{"vat_number":" X ","tax_code":" "}"""),false);
            Assert(Equals(values["vat_number"],"X") && values["tax_code"]==null && !values.ContainsKey("country_code"),"Normalization or omission changed");
            foreach(var blank in new string?[]{null,""," \t\n ","\u00a0\u2003"})
                Reject(()=>ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(new{country_code=blank}),false));
            Reject(()=>ResourceCatalog.Validate(site,Json("""{"country_code":"ZZ"}"""),false));
            foreach(var code in CountryCodes.All) ResourceCatalog.Validate(site,JsonSerializer.SerializeToElement(new{country_code=code}),false);
        });
        test("addresses: partial tax final state merge",()=> {
            var method=typeof(ResourceCatalog).GetMethod("ValidateTaxIdentity",BindingFlags.Public|BindingFlags.Static);
            Assert(method!=null,"Final state tax primitive missing");
            void Call(string patch,string previous) { try {method!.Invoke(null,[ResourceCatalog.Validate(site,Json(patch),false),Json(previous)]);} catch(TargetInvocationException e) when(e.InnerException!=null) {System.Runtime.ExceptionServices.ExceptionDispatchInfo.Capture(e.InnerException).Throw();} }
            Call("""{"vat_number":null}""","""{"vat_number":"X","tax_code":"Y"}""");
            Call("""{"name":"Renamed"}""","""{"vat_number":"X","tax_code":null}""");
            Reject(()=>Call("""{"vat_number":null}""","""{"vat_number":"X","tax_code":null}"""),"tax_identity_required");
        });
    }
    public static void Lookup(Action<string,Action> test,IServiceProvider services)
    {

        test("addresses: strict bounded local query whitelist",()=> {
            AddressLookup.Query Call(string query) {var ctx=new DefaultHttpContext();ctx.Request.QueryString=new(query);return AddressLookup.ParseQuery(ctx);}
            var parsed=Call("?field=city&text=%20Capua%20&language=it&countryCode=IT");
            Assert(parsed.Text=="Capua" && parsed.CountryCode=="IT","Query normalization changed");
            Assert(Call("?field=postal_code&text=001&countryCode=IT").Language=="it","Default language changed");
            foreach(var q in new[]{"?field=url&text=Capua","?field=city&text=ab","?field=city&text=Capua&countryCode=ZZ","?field=city&text=Capua&language=fr","?field=city&text=Capua&text=Rome","?field=city&text=Capua&unexpected=x","?field=city&text=Cap%00ua","?field=city&text="+new string('a',201),"?field=city&text=Capua&city="+new string('a',201),"?field=city&text=Capua&province="+new string('a',201)}) Reject(()=>Call(q));
        });
        test("addresses: local lookup requires create OR update not read or settings",()=> {
            foreach(var grants in new[]{new[]{"sites.create"},new[]{"sites.update"},new[]{"sites.read"},new[]{"settings.read"},Array.Empty<string>()}) {
                var ctx=new DefaultHttpContext{RequestServices=services};ctx.Items["identity"]=new IdentityState(new User{TenantId=Guid.NewGuid()},"fixture","Fixture",grants);
                var expected=grants.Contains("sites.create")||grants.Contains("sites.update");
                try {AddressLookup.Authorize(ctx).GetAwaiter().GetResult();Assert(expected,"Unexpected permission allowed");}
                catch(ApiException e) when(e.Status==403) {Assert(!expected,"Expected permission refused");}
            }
        });
        foreach(var endpoint in Environment.GetEnvironmentVariable("GEOGRAPHY_DB_TESTS")=="true" ? new[]{"autocomplete","countries"} : new[]{"autocomplete"}) {
            void Call(string query,IdentityState state) {
                using var scope=services.CreateScope();
                var ctx=new DefaultHttpContext {RequestServices=scope.ServiceProvider};
                ctx.Request.QueryString=new(query); ctx.Items["identity"]=state;
                var db=scope.ServiceProvider.GetRequiredService<Enginia360.Infrastructure.Persistence.AppDb>();
                if(endpoint=="autocomplete") AddressLookup.Prepare(ctx,db).GetAwaiter().GetResult();
                else global::Enginia360.Modules.Geography.Geography.Countries(ctx,db).GetAwaiter().GetResult();
            }
            string Query(string suffix)=>"?"+(endpoint=="autocomplete"?"field=address&text=Via%20Roma&":"")+suffix;
            void Expect(string query,IdentityState state,int status) {
                try {Call(query,state);} catch(ApiException e) when(e.Status==status) {return;}
                throw new Exception("Expected status "+status);
            }
            var tenant=Guid.NewGuid();
            IdentityState State(params string[] grants)=>new(new User {TenantId=tenant},"fixture","Fixture",grants);
            foreach(var resource in new[]{"sites","business-partners"}) foreach(var action in new[]{"create","update"})
                test($"addresses: {endpoint} exact {resource}.{action} target allowed",()=>Call(Query("resource="+resource),State(resource+"."+action)));
            foreach(var resource in new[]{"sites","business-partners"}) {
                test($"addresses: {endpoint} {resource} read-only rejected",()=>Expect(Query("resource="+resource),State(resource+".read"),403));
                var other=resource=="sites"?"business-partners":"sites";
                test($"addresses: {endpoint} {other} grants cannot cross explicit {resource}",()=>Expect(Query("resource="+resource),State(other+".create",other+".update"),403));
                test($"addresses: {endpoint} {resource} cross-tenant rejected",()=>Expect(Query("resource="+resource+"&tenantId="+Guid.NewGuid()),State(resource+".create"),403));
                test($"addresses: {endpoint} {resource} global requires explicit tenant",()=>Expect(Query("resource="+resource),new(new User {IsSuperAdmin=true},"fixture","Fixture",[]),400));
            }
            test($"addresses: {endpoint} legacy site default allowed",()=>Call(Query(""),State("sites.create")));
            test($"addresses: {endpoint} BP-only cannot use legacy site default",()=>Expect(Query(""),State("business-partners.create","business-partners.update"),403));
            foreach(var target in new[]{"unknown","users","sites.create","","Sites","%20sites%20","sites&resource=business-partners","sites%00"})
                test($"addresses: {endpoint} invalid resource {target} rejected before policy",()=>Expect(Query("resource="+target),State("sites.create","business-partners.create"),400));
            test($"addresses: {endpoint} unknown and duplicate query still rejected",()=> {
                Expect(Query("unexpected=x"),State("sites.create"),400);
                Expect(Query("tenantId="+tenant+"&tenantId="+tenant),State("sites.create"),400);
            });
        }
        test("addresses: handle consumes only prepared local reply",()=> {
            var ctx=new DefaultHttpContext();
            try {AddressLookup.Handle(ctx).GetAwaiter().GetResult();throw new Exception("Unprepared request accepted");}catch(ApiException e) when(e.Status==403) {}
            var reply=new AddressLookup.Reply([new("Roma · 00100","","Roma","RM","00100","IT","Lazio")],"");
            ctx.Items[typeof(AddressLookup.Reply)]=reply;
            var result=AddressLookup.Handle(ctx).GetAwaiter().GetResult();
            Assert(result is Microsoft.AspNetCore.Http.IValueHttpResult value && ReferenceEquals(value.Value,reply),"Prepared response changed");
            Assert(!ctx.Items.ContainsKey(typeof(AddressLookup.Reply)),"Prepared response not consumed");
            Assert(JsonSerializer.SerializeToElement(reply).GetProperty("attribution").GetString()=="","Unexpected attribution");
        });
    }
    public static void Run(IServiceProvider services)
    {
        var failed=0;var count=0;
        void Test(string name,Action action) {count++;try {action();Console.WriteLine("PASS "+name);}catch(Exception e) {failed++;Console.WriteLine("FAIL "+name+": "+e.Message);}}
        SiteClassificationSelfTests.Run(Test);OptionalCodeSelfTests.Run(Test);Lookup(Test,services);Fiscal(Test);
        Console.WriteLine($"Site address self-test: {count-failed}/{count} passed.");
        Environment.ExitCode=failed==0?0:1;
    }
}
