using Enginia360.Infrastructure.Persistence;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Enginia360.Verification.Organizations;

public static class CommercialBoundaryTests
{
    public static async Task Run(HttpClient client,AppDb db,Guid tenant,Guid a,Guid b,Action<string,Action> test)
    {
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> run) => test("commercial: "+name,() => run().GetAwaiter().GetResult());
        Case("optional codes repeat nulls and enforce sales-company purchasing-tenant uniqueness",async () => {
            async Task Create(string resource,Guid? company,string? code,HttpStatusCode status) {
                var values=new Dictionary<string,object?> {["name"]="Code scope",["code"]=code};
                if(company.HasValue) values["company_id"]=company;
                using var response=await client.PostAsJsonAsync($"/api/data/{resource}?tenantId={tenant}",values);
                Assert(response.StatusCode==status,resource+" code scope incorrect: "+(int)response.StatusCode);
            }
            foreach(var resource in new[]{"sales-organizations","purchasing-organizations"}) {
                var company=resource=="sales-organizations" ? (Guid?)a : null;
                foreach(var code in new string?[]{null,""," \t ",null}) await Create(resource,company,code,HttpStatusCode.Created);
                await Create(resource,company," shared ",HttpStatusCode.Created);
                await Create(resource,company,"shared",HttpStatusCode.Conflict);
            }
            await Create("sales-organizations",b,"shared",HttpStatusCode.Created);
            var foreign=Guid.NewGuid(); var foreignCompany=Guid.NewGuid();
            await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Code other tenant'); INSERT INTO foundation.company(id,tenant_id,name) VALUES(@c,@t,'Foreign company')",("t",foreign),("code",foreign.ToString()),("c",foreignCompany));
            await Create("sales-organizations",foreignCompany,null,HttpStatusCode.BadRequest);
        });
        Case("500 companies and 500 total sites accepted at exact coverage boundaries",async () => {
            await db.Execute("INSERT INTO foundation.company(tenant_id,name) SELECT @t,'Coverage boundary '||i FROM generate_series(1,500) i",("t",tenant));
            var companies=new List<Guid>();
            await using(var command=await db.Command("SELECT id FROM foundation.company WHERE tenant_id=@t AND name LIKE 'Coverage boundary %' ORDER BY id",("t",tenant)))
            await using(var reader=await command.ExecuteReaderAsync()) while(await reader.ReadAsync()) companies.Add(reader.GetGuid(0));
            Assert(companies.Count==500,"Boundary companies fixture wrong.");
            using var response=await client.PostAsJsonAsync($"/api/data/purchasing-organizations/save?tenantId={tenant}",new {values=new {name="500 companies"},coverage=companies.Select(c => new {companyId=c,siteScope="all_sites",siteIds=Array.Empty<Guid>()}).ToArray()});
            Assert(response.StatusCode==HttpStatusCode.Created,"500 companies refused: "+await response.Content.ReadAsStringAsync());
            var owner=(await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.purchasing_organization_company WHERE purchasing_organization_id=@o",("o",owner)))! == 500,"500 companies not committed.");
            await db.Execute("INSERT INTO foundation.site(tenant_id,company_id,name,address,city,province,postal_code,country_code) SELECT @t,@c,'Coverage boundary '||i,'Synthetic Road 42','Synthetic City','Synthetic Region','AB 12-X','GB' FROM generate_series(1,500) i",("t",tenant),("c",a));
            var sites=new List<Guid>();
            await using(var command=await db.Command("SELECT id FROM foundation.site WHERE tenant_id=@t AND company_id=@c AND name LIKE 'Coverage boundary %' ORDER BY id",("t",tenant),("c",a)))
            await using(var reader=await command.ExecuteReaderAsync()) while(await reader.ReadAsync()) sites.Add(reader.GetGuid(0));
            Assert(sites.Count==500,"Boundary sites fixture wrong.");
            using var updated=await client.PutAsJsonAsync($"/api/data/purchasing-organizations/{owner}/save?tenantId={tenant}",new {coverage=new[]{new {companyId=a,siteScope="selected_sites",siteIds=sites}}});
            Assert(updated.StatusCode==HttpStatusCode.OK,"500 sites refused: "+await updated.Content.ReadAsStringAsync());
            var result=await client.GetFromJsonAsync<JsonElement>($"/api/data/purchasing-organizations/{owner}/coverage?tenantId={tenant}");
            Assert(result.GetProperty("coverage")[0].GetProperty("siteIds").EnumerateArray().Select(s => s.GetGuid()).SequenceEqual(sites),"500 sites canonical read incorrect.");
        });
        Case("legacy values-only save supports optional-code direct consumers",async () => {
            using var response=await client.PostAsJsonAsync($"/api/data/groups/save?tenantId={tenant}",new {values=new {name="No code group"}});
            Assert(response.StatusCode==HttpStatusCode.Created,"Name-only group save regressed.");
            Assert((await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").ValueKind==JsonValueKind.Null,"Missing code was generated.");
        });
    }
}
