using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Enginia360.Verification.Shared;

// Solo fixture isolate: autenticazione sintetica; pipeline transazionale e policy reali.
public static class BusinessPartnerTests
{
    public static void Run(string connection,Action<string,Action> test) => RunAsync(connection,test).GetAwaiter().GetResult();
    private static async Task RunAsync(string connection,Action<string,Action> test)
    {
        var builder=WebApplication.CreateBuilder();
        builder.Logging.ClearProviders(); builder.WebHost.UseUrls("http://127.0.0.1:0");
        builder.Services.AddDbContext<AppDb>(o=>o.UseNpgsql(connection));
        PermissionCatalog.Configure(builder.Services);
        await using var app=builder.Build();
        using var setup=app.Services.CreateScope(); var db=setup.ServiceProvider.GetRequiredService<AppDb>();
        var tenant=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'BP proof')",("id",tenant),("code",tenant.ToString()));
        var admin=new User {Username="bp-"+Guid.NewGuid(),FirstName="Test",LastName="Admin",Email="bp@example.test",IsSuperAdmin=true,PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(admin); await db.SaveChangesAsync();
        string[]? grants=null;
        app.Use(async(ctx,next)=>{
            try {
                var requestDb=ctx.RequestServices.GetRequiredService<AppDb>();
                await using var tx=await requestDb.Database.BeginTransactionAsync(); await Security.Lock(requestDb);
                ctx.Items["identity"]=grants==null ? new IdentityState(admin,"proof","Proof",[]) : new IdentityState(new User {Id=admin.Id,TenantId=tenant,IsEnabled=true},"proof","Proof",grants);
                var original=ctx.Response.Body; await using var buffer=new MemoryStream(); ctx.Response.Body=buffer;
                try { await next(); if(ctx.Response.StatusCode<400) await tx.CommitAsync(); else await tx.RollbackAsync(); ctx.Response.Body=original; buffer.Position=0; await buffer.CopyToAsync(original); }
                finally {ctx.Response.Body=original;}
            } catch(Exception e) {
                var (status,code)=e switch {ApiException a=>(a.Status,a.Code),PostgresException p when p.SqlState=="23505"=>(409,"conflict"),_=>(500,e.GetType().Name)};
                ctx.Response.Clear(); ctx.Response.StatusCode=status; await ctx.Response.WriteAsJsonAsync(e is ApiException {Field:not null} api ? (object)new{code,field=api.Field} : new{code});
            }
        });
        DataEndpoints.Map(app);
        await app.StartAsync(); using var client=new HttpClient {BaseAddress=new Uri(app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single())};
        var suffix="?tenantId="+tenant;
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> action)=>test("BP "+name,()=>action().GetAwaiter().GetResult());
        Case("numbering read exposes virtual defaults",async()=>{
            using var response=await client.GetAsync("/api/business-partner-numbering"+suffix);
            Assert((int)response.StatusCode==200,"Expected virtual default, got "+response.StatusCode);
            var value=await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert(value.GetProperty("mode").GetString()=="AUTO" && value.GetProperty("prefix").GetString()=="BP-" && value.GetProperty("padding").GetInt32()==6 && value.GetProperty("nextNumber").GetInt64()==1 && value.GetProperty("version").GetInt64()==0,"Wrong defaults");
        });
        Case("numbering saves explicit configuration and stale version refuses",async()=>{
            using var saved=await client.PutAsJsonAsync("/api/business-partner-numbering"+suffix,new{mode="AUTO",prefix="BP-",padding=6,nextNumber=1,version=0});
            Assert((int)saved.StatusCode==200,"Save failed: "+await saved.Content.ReadAsStringAsync());
            using var stale=await client.PutAsJsonAsync("/api/business-partner-numbering"+suffix,new{mode="AUTO",prefix="BP-",padding=6,nextNumber=1,version=0});
            Assert((int)stale.StatusCode==409,"Stale numbering accepted");
        });
        Case("prefixed Italian VAT returns precise safe code and field",async()=>{
            var before=await client.GetStringAsync("/api/business-partner-numbering"+suffix);
            using var response=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="VAT screenshot"},taxIdentifiers=new[]{new{country_code="IT",identifier_type="VAT",value="IT12345678901"}}});
            var body=await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert((int)response.StatusCode==400,"Prefixed VAT must remain invalid");
            Assert(body.GetProperty("code").GetString()=="invalid_italian_vat","Expected invalid_italian_vat, got "+body.GetRawText());
            Assert(body.TryGetProperty("field",out var field) && field.GetString()=="taxIdentifiers[0].value","Missing exact VAT field");
            Assert(body.EnumerateObject().Count()==2,"Validation response leaks detail");
            Assert(before==await client.GetStringAsync("/api/business-partner-numbering"+suffix),"Invalid VAT consumed numbering");
        });
        Case("optional exception field preserves legacy and malformed-shape responses",async()=>{
            var legacy=new ApiException(409,"legacy_code");
            Assert(legacy.Status==409 && legacy.Code=="legacy_code" && legacy.Field==null && legacy.Message=="legacy_code","Legacy constructor changed");
            using var response=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Shape"},unknown="must-not-be-echoed"});
            var result=await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert((int)response.StatusCode==400 && result.GetRawText()=="{\"code\":\"validation_error\"}","Generic errors must omit field and submitted values");
        });
        void Invalid(string name,string patch,string code,string field,int status=400)=>Case("precise "+name,async()=>{
            var payload=JsonNode.Parse("""{"values":{"kind":"ORGANIZATION","legal_name":"Validation proof"}}""")!.AsObject();
            foreach(var entry in JsonNode.Parse(patch)!.AsObject()) payload[entry.Key]=entry.Value?.DeepClone();
            var before=await client.GetStringAsync("/api/business-partner-numbering"+suffix);
            var count=(long)(await db.Scalar("SELECT count(*) FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!;
            var audit=(long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND resource='business-partners'",("t",tenant)))!;
            using var response=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,payload);
            var result=await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert((int)response.StatusCode==status && result.GetProperty("code").GetString()==code && result.TryGetProperty("field",out var actual) && actual.GetString()==field,"Expected "+status+" "+code+" at "+field+", got "+result.GetRawText());
            Assert(result.EnumerateObject().Count()==2,"Only code and field may be exposed");
            Assert(before==await client.GetStringAsync("/api/business-partner-numbering"+suffix),"Invalid save changed numbering");
            Assert(count==(long)(await db.Scalar("SELECT count(*) FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!,"Invalid save committed aggregate");
            Assert(audit==(long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND resource='business-partners'",("t",tenant)))!,"Invalid save committed audit");
        });
        foreach(var key in new[]{"country_code","identifier_type","value"}) foreach(var missing in new[]{true,false}) {
            var row=JsonNode.Parse("""{"country_code":"IT","identifier_type":"VAT","value":"12345678901"}""")!.AsObject();
            if(missing) row.Remove(key); else row[key]=" ";
            Invalid("tax required "+key+missing,new JsonObject{["taxIdentifiers"]=new JsonArray(row)}.ToJsonString(),"tax_identifier_required","taxIdentifiers[0]."+key);
        }
        Invalid("tax country", """{"taxIdentifiers":[{"country_code":"ZZ","identifier_type":"VAT","value":"12345678901"}]}""","invalid_country_code","taxIdentifiers[0].country_code");
        Invalid("tax country length", """{"taxIdentifiers":[{"country_code":"ITA","identifier_type":"VAT","value":"12345678901"}]}""","invalid_country_code","taxIdentifiers[0].country_code");
        Invalid("tax country type", """{"taxIdentifiers":[{"country_code":1,"identifier_type":"VAT","value":"12345678901"}]}""","invalid_country_code","taxIdentifiers[0].country_code");
        Invalid("tax type", """{"taxIdentifiers":[{"country_code":"IT","identifier_type":"OTHER","value":"12345678901"}]}""","invalid_tax_identifier_type","taxIdentifiers[0].identifier_type");
        Invalid("tax empty normalized", """{"taxIdentifiers":[{"country_code":"FR","identifier_type":"FOREIGN_TAX_ID","value":" - . "}]}""","invalid_tax_identifier","taxIdentifiers[0].value");
        Invalid("tax malformed value", """{"taxIdentifiers":[{"country_code":"IT","identifier_type":"VAT","value":123}]}""","invalid_field_value","taxIdentifiers[0].value");
        Invalid("tax normalized mismatch", """{"taxIdentifiers":[{"country_code":"IT","identifier_type":"VAT","value":"12345678901","normalized_value":"OTHER"}]}""","tax_identifier_normalization_mismatch","taxIdentifiers[0].normalized_value");
        Invalid("Italian fiscal syntax", """{"taxIdentifiers":[{"country_code":"IT","identifier_type":"FISCAL_CODE","value":"NOTFISCAL"}]}""","invalid_italian_fiscal_code","taxIdentifiers[0].value");
        Invalid("tax repeated in same payload", """{"taxIdentifiers":[{"country_code":"FR","identifier_type":"FOREIGN_TAX_ID","value":"ABC"},{"country_code":"FR","identifier_type":"FOREIGN_TAX_ID","value":"A-B.C"}]}""","duplicate_tax_identifier","taxIdentifiers[1].value",409);
        Invalid("organization name required", """{"values":{"kind":"ORGANIZATION"}}""","business_partner_name_required","values.legal_name");
        Invalid("organization names mismatch", """{"values":{"kind":"ORGANIZATION","legal_name":"Name","first_name":"Wrong"}}""","business_partner_names_mismatch","values.first_name");
        Invalid("person legal name mismatch", """{"values":{"kind":"PERSON","first_name":"Name","legal_name":"Wrong"}}""","business_partner_names_mismatch","values.legal_name");
        Invalid("draft person requires a name", """{"values":{"kind":"PERSON"}}""","business_partner_name_required","values.first_name");
        Invalid("active person requires surname", """{"values":{"kind":"PERSON","status":"ACTIVE","first_name":"Name"}}""","business_partner_name_required","values.last_name");
        Invalid("kind required", """{"values":{"legal_name":"Name"}}""","field_required","values.kind");
        Invalid("kind choice", """{"values":{"kind":"OTHER","legal_name":"Name"}}""","invalid_choice","values.kind");
        Invalid("name type", """{"values":{"kind":"ORGANIZATION","legal_name":42}}""","invalid_field_value","values.legal_name");
        Invalid("name limit",new JsonObject{["values"]=new JsonObject{["kind"]="ORGANIZATION",["legal_name"]=new string('x',501)}}.ToJsonString(),"field_too_long","values.legal_name");
        foreach(var key in new[]{"street","postal_code","city","country_code"}) {
            var row=JsonNode.Parse("""{"street":"Via Prova","postal_code":"00100","city":"Roma","country_code":"IT"}""")!.AsObject();row.Remove(key);
            Invalid("address required "+key,new JsonObject{["addresses"]=new JsonArray(row)}.ToJsonString(),"business_partner_address_required","addresses[0]."+key);
        }
        Invalid("address usage repeated", """{"addresses":[{"street":"Via","postal_code":"00100","city":"Roma","country_code":"IT","usages":[{"usage":"BILLING"},{"usage":"BILLING"}]}]}""","duplicate_address_usage","addresses[0].usages[1].usage");
        Invalid("default address repeated", """{"addresses":[{"street":"Via","postal_code":"00100","city":"Roma","country_code":"IT","usages":[{"usage":"BILLING","is_default":true}]},{"street":"Via 2","postal_code":"00100","city":"Roma","country_code":"IT","usages":[{"usage":"BILLING","is_default":true}]}]}""","duplicate_default_address","addresses[1].usages[0].is_default");
        foreach(var type in new[]{"EMAIL","PEC","PHONE","MOBILE","WEBSITE"}) {
            var code=type is "EMAIL" or "PEC" ? "invalid_contact_email" : type is "PHONE" or "MOBILE" ? "invalid_contact_phone" : "invalid_contact_website";
            Invalid("contact "+type,new JsonObject{["contactChannels"]=new JsonArray(new JsonObject{["channel_type"]=type,["value"]="invalid"})}.ToJsonString(),code,"contactChannels[0].value");
        }
        Invalid("primary contact repeated", """{"contactChannels":[{"channel_type":"EMAIL","value":"a@example.test","is_primary":true},{"channel_type":"EMAIL","value":"b@example.test","is_primary":true}]}""","duplicate_primary_contact","contactChannels[1].is_primary");
        Case("creates complete BP aggregate and allocates immutable code",async()=>{
            using var created=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Prova SRL",status="ACTIVE"},taxIdentifiers=new[]{new{country_code="IT",identifier_type="VAT",value="12345678901"}},addresses=new[]{new{street="Via Prova",street_number="1",postal_code="00100",city="Roma",province="RM",country_code="IT",usages=new[]{new{usage="BILLING",is_default=true}}}},contactChannels=new[]{new{channel_type="EMAIL",value="test@example.test",is_primary=true}}});
            Assert((int)created.StatusCode==201,"Create failed: "+await created.Content.ReadAsStringAsync());
            var value=await created.Content.ReadFromJsonAsync<JsonElement>();
            Assert(value.GetProperty("code").GetString()=="BP-000001" && value.GetProperty("version").GetInt64()==1 && value.GetProperty("tax_identifiers").GetArrayLength()==1 && value.GetProperty("addresses")[0].GetProperty("usages")[0].GetProperty("is_default").GetBoolean(),"Aggregate response incorrect");
        });
        Case("update aggregate preserves omitted sets and rejects stale version",async()=>{
            var id=(Guid)(await db.Scalar("SELECT id FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!;
            using var updated=await client.PutAsJsonAsync($"/api/data/business-partners/{id}/save"+suffix,new{values=new{legal_name="Updated"},expectedVersion=1});
            Assert((int)updated.StatusCode==200,"Update failed: "+await updated.Content.ReadAsStringAsync());
            var value=await updated.Content.ReadFromJsonAsync<JsonElement>();
            Assert(value.GetProperty("version").GetInt64()==2 && value.GetProperty("tax_identifiers").GetArrayLength()==1,"Lost nested data or version");
            using var stale=await client.PutAsJsonAsync($"/api/data/business-partners/{id}/save"+suffix,new{values=new{legal_name="Stale"},expectedVersion=1});
            Assert((int)stale.StatusCode==409,"Stale version accepted");
            using var read=await client.GetAsync($"/api/data/business-partners/{id}"+suffix);
            Assert((int)read.StatusCode==200,"Detail read missing");
        });
        Case("search covers contact and code with literal wildcards",async()=>{
            using var response=await client.GetAsync("/api/data/business-partners"+suffix+"&search=test%40example.test");
            Assert((int)response.StatusCode==200,"Search failed");
            var value=await response.Content.ReadFromJsonAsync<JsonElement>();Assert(value.GetProperty("total").GetInt64()==1,"Contact not found");
        });
        Case("generic writes and physical deletion cannot bypass aggregate",async()=>{
            using var created=await client.PostAsJsonAsync("/api/data/business-partners"+suffix,new{kind="ORGANIZATION",legal_name="Bypass",code="BYPASS"});
            Assert((int)created.StatusCode is 405 or 409,"Generic bypass accepted: "+created.StatusCode);
            var id=(Guid)(await db.Scalar("SELECT id FROM masterdata.business_partner WHERE tenant_id=@t ORDER BY created_at LIMIT 1",("t",tenant)))!;
            using var deleted=await client.DeleteAsync($"/api/data/business-partners/{id}"+suffix);
            Assert((int)deleted.StatusCode is 405 or 409,"Physical deletion not controlled: "+deleted.StatusCode);
        });
        Case("fiscal duplicate rollback preserves allocation and audit",async()=>{
            var before=await client.GetFromJsonAsync<JsonElement>("/api/business-partner-numbering"+suffix);
            var audit=(long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND resource='business-partners'",("t",tenant)))!;
            using var duplicate=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="PERSON",first_name="Mario",last_name="Rossi"},taxIdentifiers=new[]{new{country_code="IT",identifier_type="VAT",value="12345 678901"}}});
            var error=await duplicate.Content.ReadFromJsonAsync<JsonElement>();
            Assert((int)duplicate.StatusCode==409 && error.GetProperty("code").GetString()=="duplicate_tax_identifier" && error.GetProperty("field").GetString()=="taxIdentifiers[0].value","Duplicate normalized fiscal identity accepted or missing field");
            var after=await client.GetFromJsonAsync<JsonElement>("/api/business-partner-numbering"+suffix);
            Assert(before.GetRawText()==after.GetRawText(),"Failed aggregate consumed numbering");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND resource='business-partners'",("t",tenant)))! == audit,"Failed aggregate audited as success");
        });
        Case("validation preserves aggregate on invalid nested replacements",async()=>{
            var id=(Guid)(await db.Scalar("SELECT id FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!;
            var before=await client.GetStringAsync($"/api/data/business-partners/{id}"+suffix);
            foreach(var bad in new[]{"not-email","x@@example.test"}) {
                using var response=await client.PutAsJsonAsync($"/api/data/business-partners/{id}/save"+suffix,new{values=new{legal_name="Must roll back"},expectedVersion=2,contactChannels=new[]{new{channel_type="EMAIL",value=bad}}});
                Assert((int)response.StatusCode==400,"Bad channel accepted");
                Assert(await client.GetStringAsync($"/api/data/business-partners/{id}"+suffix)==before,"Partial update committed");
            }
            using var clear=await client.PutAsJsonAsync($"/api/data/business-partners/{id}/save"+suffix,new{values=new{},expectedVersion=2,contactChannels=Array.Empty<object>(),addresses=Array.Empty<object>()});
            Assert((int)clear.StatusCode==200,"Clear failed");
            var value=await clear.Content.ReadFromJsonAsync<JsonElement>();
            Assert(value.GetProperty("contact_channels").GetArrayLength()==0 && value.GetProperty("addresses").GetArrayLength()==0 && value.GetProperty("tax_identifiers").GetArrayLength()==1,"Omission/empty distinction lost");
        });
        Case("precise permissions permit create without numbering read",async()=>{
            grants=["business-partners.create"];
            try {
                using var forbidden=await client.GetAsync("/api/business-partner-numbering"+suffix);Assert((int)forbidden.StatusCode==403,"Create grants numbering read");
                using var created=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="PERSON",first_name="Draft only"}});
                Assert((int)created.StatusCode==201,"Create improperly requires numbering/read");
                using var listing=await client.GetAsync("/api/data/business-partners"+suffix);Assert((int)listing.StatusCode==403,"Create grants read");
            } finally {grants=null;}
        });
        Case("numbering freezes after first allocation",async()=>{
            var config=await client.GetFromJsonAsync<JsonElement>("/api/business-partner-numbering"+suffix);
            using var rejected=await client.PutAsJsonAsync("/api/business-partner-numbering"+suffix,new{mode="AUTO",prefix="CHANGED-",padding=6,nextNumber=config.GetProperty("nextNumber").GetInt64(),version=config.GetProperty("version").GetInt64()});
            Assert((int)rejected.StatusCode==409 && (await rejected.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()=="numbering_in_use","Used format changed");
        });
        Case("concurrent allocations unique on distinct requests",async()=>{
            var tasks=Enumerable.Range(0,8).Select(async n=>{
                using var response=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Concurrent "+n}});
                Assert((int)response.StatusCode==201,"Concurrent create failed");return (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()!;
            });
            var codes=await Task.WhenAll(tasks);Assert(codes.Distinct().Count()==8,"Allocated duplicate code");
        });
        Case("audit failure rolls back aggregate code counter and version",async()=>{
            var before=await client.GetStringAsync("/api/business-partner-numbering"+suffix);
            var count=(long)(await db.Scalar("SELECT count(*) FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!;
            var tag="bp_audit_"+Guid.NewGuid().ToString("N");
            await db.Execute($"CREATE FUNCTION foundation.{tag}() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RAISE EXCEPTION ''Fixture audit refusal''; END'; CREATE TRIGGER {tag} BEFORE INSERT ON foundation.audit_event FOR EACH ROW WHEN (NEW.tenant_id='{tenant}'::uuid AND NEW.resource='business-partners') EXECUTE FUNCTION foundation.{tag}()");
            try {
                using var response=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Must roll back"}});
                Assert((int)response.StatusCode==500,"Fixture failed to exercise audit rollback");
                Assert(before==await client.GetStringAsync("/api/business-partner-numbering"+suffix),"Audit failure consumed numbering");
                Assert(count==(long)(await db.Scalar("SELECT count(*) FROM masterdata.business_partner WHERE tenant_id=@t",("t",tenant)))!,"Audit failure committed partner");
            } finally {await db.Execute($"DROP TRIGGER {tag} ON foundation.audit_event; DROP FUNCTION foundation.{tag}()");}
        });
        Case("manual codes mandatory immutable and never reusable after archival",async()=>{
            var original=suffix;var other=Guid.NewGuid();await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'Manual proof')",("id",other),("code",other.ToString()));suffix="?tenantId="+other;
            try {
                using var config=await client.PutAsJsonAsync("/api/business-partner-numbering"+suffix,new{mode="MANUAL",prefix="X-",padding=4,nextNumber=50,version=0});Assert((int)config.StatusCode==200,"Manual config failed");
                using var missing=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Missing code"}});Assert((int)missing.StatusCode==400,"Manual code not required");
                using var create=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Manual",code="EXTERNAL",status="ARCHIVED"}});Assert((int)create.StatusCode==201,"Manual create failed");
                var value=await create.Content.ReadFromJsonAsync<JsonElement>();
                using var immutable=await client.PutAsJsonAsync($"/api/data/business-partners/{value.GetProperty("id").GetGuid()}/save"+suffix,new{values=new{code="NEW"},expectedVersion=1});
                Assert((int)immutable.StatusCode==409 && (await immutable.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()=="business_partner_code_immutable","Code changed");
                using var duplicate=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Reuse",code="external"}});Assert((int)duplicate.StatusCode==409,"Archived code reused");
            } finally {suffix=original;}
        });
        Case("maximum allocation exhausts safely without wraparound",async()=>{
            var original=suffix;var other=Guid.NewGuid();await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'Exhaustion proof')",("id",other),("code",other.ToString()));suffix="?tenantId="+other;
            try {
                using var config=await client.PutAsJsonAsync("/api/business-partner-numbering"+suffix,new{mode="AUTO",prefix="LAST-",padding=15,nextNumber=999999999999999L,version=0});Assert((int)config.StatusCode==200,"Boundary config failed");
                using var create=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Last"}});Assert((int)create.StatusCode==201,"Last number failed");
                Assert((await create.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()=="LAST-999999999999999","Last code wrong");
                var before=await client.GetStringAsync("/api/business-partner-numbering"+suffix);
                using var exhausted=await client.PostAsJsonAsync("/api/data/business-partners/save"+suffix,new{values=new{kind="ORGANIZATION",legal_name="Exhausted"}});
                Assert((int)exhausted.StatusCode==409 && (await exhausted.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()=="numbering_exhausted","Exhaustion not controlled");
                Assert(before==await client.GetStringAsync("/api/business-partner-numbering"+suffix),"Exhausted counter changed");
            } finally {suffix=original;}
        });
        await app.StopAsync();
    }
}
