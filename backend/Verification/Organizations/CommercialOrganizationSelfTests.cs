using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Organizations;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Enginia360.Verification.Organizations;

public static class CommercialOrganizationTests
{
    public static async Task Run(HttpClient client,AppDb db,Guid tenant,Guid admin,Action<Guid> actor,Action<string,Action> test)
    {
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> run) => test("commercial: "+name,() => run().GetAwaiter().GetResult());
        var a=Guid.NewGuid(); var b=Guid.NewGuid(); var site=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.company(id,tenant_id,name) VALUES(@a,@t,'Company A'),(@b,@t,'Company B'); INSERT INTO foundation.site(id,tenant_id,company_id,name,tax_code,address,city,province,postal_code,country_code) VALUES(@s,@t,@b,'Site B','SYNTHETIC-TAX','Synthetic Road 42','Synthetic City','Synthetic Region','AB 12-X','GB')",("a",a),("b",b),("s",site),("t",tenant));
        object Entry(Guid company,string mode,params Guid[] sites) => new {companyId=company,siteScope=mode,siteIds=sites};
        var coverage=new[]{Entry(a,"all_sites"),Entry(b,"selected_sites",site)};
        var owner=Guid.Empty;
        Case("tracer2 POST save accepts two companies with distinct site modes",async () => {
            using var response=await client.PostAsJsonAsync($"/api/data/purchasing-organizations/save?tenantId={tenant}",new {values=new {name="Acquisti gruppo"},coverage});
            Assert(response.StatusCode==HttpStatusCode.Created,"Expected 201 valid coverage command, actual "+(int)response.StatusCode+": "+await response.Content.ReadAsStringAsync());
            var body=await response.Content.ReadFromJsonAsync<JsonElement>(); owner=body.GetProperty("id").GetGuid();
            Assert(body.GetProperty("name").GetString()=="Acquisti gruppo" && body.GetProperty("code").ValueKind==JsonValueKind.Null,"Public projection incorrect.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.purchasing_organization_company WHERE purchasing_organization_id=@id",("id",owner)))! == 2,"Both company coverage rows required.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.purchasing_organization_site WHERE purchasing_organization_id=@id AND site_id=@s",("id",owner),("s",site)))! == 1,"Selected site required.");
        });
        string ReadUrl(Guid id) => $"/api/data/purchasing-organizations/{id}/coverage?tenantId={tenant}";
        async Task<JsonElement> Details(Guid id,string action,string resource) => JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action=@action AND resource=@r ORDER BY created_at DESC LIMIT 1",("id",id),("action",action),("r",resource)))!);
        Case("GET coverage exact identifier-only canonical contract",async () => {
            using var response=await client.GetAsync(ReadUrl(owner));
            Assert(response.StatusCode==HttpStatusCode.OK,"Coverage GET must exist with owner.read.");
            var body=await response.Content.ReadFromJsonAsync<JsonElement>();
            Assert(body.EnumerateObject().Count()==1 && body.GetProperty("coverage").GetArrayLength()==2,"Exact envelope required.");
            foreach(var entry in body.GetProperty("coverage").EnumerateArray()) Assert(entry.EnumerateObject().Select(p => p.Name).Order().SequenceEqual(new[]{"companyId","siteIds","siteScope"}),"Scope GET must not expose profiles.");
            var audit=await Details(owner,"replace_coverage","purchasing-organization-coverage");
            Assert(audit.GetProperty("before").GetArrayLength()==0,"Initial coverage before must be empty.");
            Assert(JsonSerializer.Serialize(audit.GetProperty("after").Deserialize<PurchasingCoverage.Entry[]>())==JsonSerializer.Serialize(body.GetProperty("coverage").Deserialize<PurchasingCoverage.Entry[]>()),"Coverage snapshot must match canonical read.");
        });
        foreach(var resource in new[]{"sales-organizations","purchasing-organizations"}) foreach(var action in new[]{"create","update","delete"})
        Case($"{resource} {action} public before after snapshots",async () => {
                var values=new Dictionary<string,object?> {["name"]="Prima"};
                if(resource=="sales-organizations") values["company_id"]=a;
                using var created=await client.PostAsJsonAsync($"/api/data/{resource}?tenantId={tenant}",values);
                Assert(created.StatusCode==HttpStatusCode.Created,"Legacy create failed.");
                var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
                if(action!="create") {
                    using var changed=await client.PutAsJsonAsync($"/api/data/{resource}/{id}?tenantId={tenant}",new {name="Dopo"});
                    Assert(changed.IsSuccessStatusCode,"Legacy update failed.");
                }
                if(action=="delete") {
                    using var deleted=await client.DeleteAsync($"/api/data/{resource}/{id}?tenantId={tenant}");
                    Assert(deleted.StatusCode==HttpStatusCode.NoContent,"Unassigned organization delete failed.");
                }
                var details=await Details(id,action,resource);
                Assert(action=="create" ? details.GetProperty("before").ValueKind==JsonValueKind.Null : details.GetProperty("before").GetProperty("name").GetString()==(action=="delete" ? "Dopo" : "Prima"),"Before snapshot required.");
                Assert(action=="delete" ? details.GetProperty("after").ValueKind==JsonValueKind.Null : details.GetProperty("after").GetProperty("name").GetString()==(action=="create" ? "Prima" : "Dopo"),"After snapshot required.");
        });
        await CommercialCoverageRegressionTests.Run(client,db,tenant,admin,actor,owner,a,b,site,test);
        await CommercialOrganizationLifecycleTests.Run(client,db,tenant,admin,actor,owner,a,b,site,test);
        await CommercialBoundaryTests.Run(client,db,tenant,a,b,test);
    }
}
