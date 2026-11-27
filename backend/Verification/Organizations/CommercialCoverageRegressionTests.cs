using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Organizations;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Enginia360.Verification.Organizations;

public static class CommercialCoverageRegressionTests
{
    public static async Task Run(HttpClient client,AppDb db,Guid tenant,Guid admin,Action<Guid> actor,Guid owner,Guid a,Guid b,Guid site,Action<string,Action> test)
    {
        void Assert(bool value,string message) {if(!value) throw new Exception(message);}
        void Case(string name,Func<Task> run) => test("commercial: "+name,() => run().GetAwaiter().GetResult());
        string Url(Guid id) => $"/api/data/purchasing-organizations/{id}/save?tenantId={tenant}";
        object Entry(Guid company,string mode,params Guid[] sites) => new {companyId=company,siteScope=mode,siteIds=sites};
        var coverage=new[]{Entry(a,"all_sites"),Entry(b,"selected_sites",site)};
        async Task<string> Snapshot() => (string)(await db.Scalar("""
            SELECT jsonb_build_object(
             'owners',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.purchasing_organization t),
             'sales',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.sales_organization t),
             'companies',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,purchasing_organization_id,company_id) FROM foundation.purchasing_organization_company t),
             'sites',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,purchasing_organization_id,company_id,site_id) FROM foundation.purchasing_organization_site t),
             'audit',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.audit_event t))::text
            """))!;
        async Task Refuse(HttpMethod method,string url,object payload,HttpStatusCode expected)
        {
            var before=await Snapshot();
            using var request=new HttpRequestMessage(method,url) {Content=payload is string raw ? new StringContent(raw,System.Text.Encoding.UTF8,"application/json") : JsonContent.Create(payload)};
            using var response=await client.SendAsync(request);
            Assert(response.StatusCode==expected,$"Expected {(int)expected}, actual {(int)response.StatusCode}: {await response.Content.ReadAsStringAsync()}");
            Assert(await Snapshot()==before,"Refusal changed owner, coverage or audit.");
        }
        var user=new User {TenantId=tenant,Username="coverage-"+Guid.NewGuid(),FirstName="Coverage",LastName="Writer",Email="coverage@example.test",PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(user); await db.SaveChangesAsync();
        var role=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.role(id,tenant_id,name) VALUES(@r,@t,'Coverage authority'); INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r)",("r",role),("t",tenant),("u",user.Id));
        async Task Grants(params string[] codes) => await db.Execute("DELETE FROM foundation.role_permission WHERE role_id=@r; INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code=ANY(@codes)",("r",role),("t",tenant),("codes",codes));
        Case("coverage-only authority has no profile or read gate and returns exact id",async () => {
            await Grants("purchasing-organizations.assign_scope"); actor(user.Id);
            try {
                using var response=await client.PutAsJsonAsync(Url(owner),new {coverage});
                Assert(response.StatusCode==HttpStatusCode.OK,"Scope-only writer denied.");
                var body=await response.Content.ReadFromJsonAsync<JsonElement>();
                Assert(body.EnumerateObject().Count()==1 && body.GetProperty("id").GetGuid()==owner,"Scope-only leaked profile.");
                using var read=await client.GetAsync($"/api/data/purchasing-organizations/{owner}/coverage");
                Assert(read.StatusCode==HttpStatusCode.Forbidden,"assign_scope granted read.");
                await Refuse(HttpMethod.Put,Url(owner),new {values=new {name="Forbidden"},coverage},HttpStatusCode.Forbidden);
            } finally {actor(admin);}
        });
        Case("profile-only updates and owner-read-only inspection need no reference authority",async () => {
            await Grants("purchasing-organizations.update"); actor(user.Id);
            try {
                using var response=await client.PutAsJsonAsync(Url(owner),new {values=new {description="Only profile"}});
                Assert(response.StatusCode==HttpStatusCode.OK,"Profile-only update requires assign scope.");
                await Refuse(HttpMethod.Put,Url(owner),new {coverage=Array.Empty<object>()},HttpStatusCode.Forbidden);
                await Grants("purchasing-organizations.read");
                using var read=await client.GetAsync($"/api/data/purchasing-organizations/{owner}/coverage");
                Assert(read.StatusCode==HttpStatusCode.OK,"Owner.read must suffice for identifiers, no companies/sites.read.");
            } finally {actor(admin);}
        });
        Case("all requested gates preflight before any write including explicit empty coverage",async () => {
            await db.Execute("""
                CREATE SEQUENCE foundation.coverage_write_probe;
                CREATE FUNCTION foundation.coverage_write_probe() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN PERFORM nextval('foundation.coverage_write_probe'); RETURN NEW; END $$;
                CREATE TRIGGER coverage_write_probe BEFORE INSERT OR UPDATE ON foundation.purchasing_organization FOR EACH ROW EXECUTE FUNCTION foundation.coverage_write_probe()
                """);
            actor(user.Id);
            try {
                foreach(var create in new[]{true,false}) foreach(var empty in new[]{true,false}) {
                    var profile=create ? "purchasing-organizations.create" : "purchasing-organizations.update";
                    foreach(var grant in new[]{profile,"purchasing-organizations.assign_scope"}) {
                        await Grants(grant);
                        await Refuse(create ? HttpMethod.Post : HttpMethod.Put,create ? $"/api/data/purchasing-organizations/save?tenantId={tenant}" : Url(owner),new {values=new {name="Denied"},coverage=empty ? Array.Empty<object>() : coverage},HttpStatusCode.Forbidden);
                    }
                }
                Assert(!(bool)(await db.Scalar("SELECT is_called FROM foundation.coverage_write_probe"))!,"DML happened before all authority gates.");
                await Grants("purchasing-organizations.update","purchasing-organizations.assign_scope");
                using var accepted=await client.PutAsJsonAsync(Url(owner),new {values=new {name="Combined"},coverage});
                Assert(accepted.StatusCode==HttpStatusCode.OK,"Combined exact grants denied.");
            } finally {actor(admin); await db.Execute("DROP TRIGGER coverage_write_probe ON foundation.purchasing_organization; DROP FUNCTION foundation.coverage_write_probe(); DROP SEQUENCE foundation.coverage_write_probe");}
        });
        Case("malformed coverage shape keys modes UUIDs duplicates and bounded totals refuse atomically",async () => {
            var valid=JsonSerializer.Serialize(Entry(a,"all_sites"));
            foreach(var raw in new[]{"null","{}","[null]","[{}]","["+valid+","+valid+"]",
                $"[{{\"companyId\":\"{a}\",\"companyId\":\"{a}\",\"siteScope\":\"all_sites\",\"siteIds\":[]}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":\"all_sites\",\"siteIds\":[],\"extra\":1}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":\"selected_sites\",\"siteIds\":[]}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":\"all_sites\",\"siteIds\":[\"{site}\"]}}]",
                $"[{{\"companyId\":\"{b}\",\"siteScope\":\"selected_sites\",\"siteIds\":[\"{site}\",\"{site}\"]}}]",
                $"[{{\"companyId\":\"{b}\",\"siteScope\":\"selected_sites\",\"siteIds\":[\"\\ud800\"]}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":\"ALL\",\"siteIds\":[]}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":null,\"siteIds\":[]}}]",
                $"[{{\"companyId\":\"{a}\",\"siteScope\":\"all_sites\",\"siteIds\":null}}]",
                "[{\"companyId\":\"00000000-0000-0000-0000-000000000000\",\"siteScope\":\"all_sites\",\"siteIds\":[]}]",
                "[{\"companyId\":\"bad\",\"siteScope\":\"all_sites\",\"siteIds\":[]}]",
                "[{\"\\ud800\":1}]"})
                await Refuse(HttpMethod.Put,Url(owner),"{\"values\":{\"name\":\"Must roll back\"},\"coverage\":"+raw+"}",HttpStatusCode.BadRequest);
            foreach(var payload in new object[]{new {coverage=new[]{Entry(a,"selected_sites",site)}},new {coverage=new[]{Entry(Guid.NewGuid(),"all_sites")}},new {coverage=Enumerable.Range(0,501).Select(_ => Entry(Guid.NewGuid(),"all_sites")).ToArray()},new {coverage=new[]{Entry(b,"selected_sites",Enumerable.Range(0,501).Select(_ => Guid.NewGuid()).ToArray())}},new {coverage=new[]{Entry(a,"selected_sites",Enumerable.Range(0,251).Select(_ => Guid.NewGuid()).ToArray()),Entry(b,"selected_sites",Enumerable.Range(0,250).Select(_ => Guid.NewGuid()).ToArray())}}})
                await Refuse(HttpMethod.Put,Url(owner),payload,HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Put,Url(owner),"{\"coverage\":[],\"coverage\":[]}",HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Post,$"/api/data/sales-organizations/save?tenantId={tenant}",new {values=new {name="Wrong resource",company_id=a},coverage=Array.Empty<object>()},HttpStatusCode.BadRequest);
        });
        foreach(var deferred in new[]{false,true}) Case(deferred ? "deferred coverage audit failure rolls back at commit" : "immediate coverage audit failure rolls back entire command",async () => {
            await db.Execute("CREATE FUNCTION foundation.coverage_audit_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='purchasing-organization-coverage' THEN RAISE EXCEPTION 'fixture fault' USING ERRCODE='"+(deferred ? "P0001" : "23514")+"'; END IF; RETURN NEW; END $$");
            try {
                await db.Execute(deferred ? "CREATE CONSTRAINT TRIGGER coverage_audit_fault AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.coverage_audit_fault()" : "CREATE TRIGGER coverage_audit_fault BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.coverage_audit_fault()");
                var expected=deferred ? HttpStatusCode.InternalServerError : HttpStatusCode.BadRequest;
                await Refuse(HttpMethod.Post,$"/api/data/purchasing-organizations/save?tenantId={tenant}",new {values=new {name="Rollback create"},coverage},expected);
                await Refuse(HttpMethod.Put,Url(owner),new {values=new {name="Rollback update"},coverage=Array.Empty<object>()},expected);
            } finally {await db.Execute("DROP TRIGGER IF EXISTS coverage_audit_fault ON foundation.audit_event; DROP FUNCTION foundation.coverage_audit_fault()");}
        });
        Case("owner profile coverage and audits commit with one xmin",async () => {
            using var response=await client.PutAsJsonAsync(Url(owner),new {values=new {name="Transaction"},coverage});
            Assert(response.StatusCode==HttpStatusCode.OK,"Combined save failed.");
            Assert((long)(await db.Scalar("""
                SELECT count(DISTINCT xid) FROM (
                  SELECT xmin::text xid FROM foundation.purchasing_organization WHERE id=@o
                  UNION ALL SELECT xmin::text FROM foundation.purchasing_organization_company WHERE purchasing_organization_id=@o
                  UNION ALL SELECT xmin::text FROM foundation.purchasing_organization_site WHERE purchasing_organization_id=@o
                  UNION ALL SELECT xmin::text FROM foundation.audit_event WHERE record_id=@o AND created_at=(SELECT max(created_at) FROM foundation.audit_event WHERE record_id=@o)) x
                """,("o",owner)))! == 1,"Writes committed in separate transactions.");
        });
        Case("new tenant always seeds finite61 including assign_scope",async () => {
            using var created=await client.PostAsJsonAsync("/api/data/tenants",new {name="Coverage other tenant",code="coverage-"+Guid.NewGuid()});
            var other=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.permission WHERE tenant_id=@t AND is_system",("t",other)))! == 61,"New tenant seed incomplete.");
            var foreign=Guid.NewGuid(); var foreignOwner=Guid.NewGuid(); var foreignSite=Guid.NewGuid();
            await db.Execute("INSERT INTO foundation.company(id,tenant_id,name) VALUES(@c,@t,'Foreign'); INSERT INTO foundation.site(id,tenant_id,company_id,name,address,city,province,postal_code,country_code) VALUES(@s,@t,@c,'Foreign site','Synthetic Road 42','Synthetic City','Synthetic Region','AB 12-X','GB'); INSERT INTO foundation.purchasing_organization(id,tenant_id,name) VALUES(@o,@t,'Foreign owner')",("c",foreign),("t",other),("o",foreignOwner),("s",foreignSite));
            await Refuse(HttpMethod.Put,Url(owner),new {values=new {name="Denied"},coverage=new[]{Entry(foreign,"all_sites")}},HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Put,Url(owner),new {coverage=new[]{Entry(b,"selected_sites",foreignSite)}},HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Put,Url(foreignOwner),new {coverage=Array.Empty<object>()},HttpStatusCode.NotFound);
            using var read=await client.GetAsync($"/api/data/purchasing-organizations/{foreignOwner}/coverage?tenantId={tenant}");
            Assert(read.StatusCode==HttpStatusCode.NotFound,"Foreign scope leaked.");
            await Grants("purchasing-organizations.assign_scope"); actor(user.Id);
            try {await Refuse(HttpMethod.Put,$"/api/data/purchasing-organizations/{owner}/save?tenantId={other}",new {coverage=Array.Empty<object>()},HttpStatusCode.Forbidden);}
            finally {actor(admin);}
        });
        Case("unassigned owner and explicit clearing are valid without implicit scopes",async () => {
            using var created=await client.PostAsJsonAsync($"/api/data/purchasing-organizations/save?tenantId={tenant}",new {values=new {name="Unassigned"}});
            Assert(created.StatusCode==HttpStatusCode.Created,"Owner without coverage is valid.");
            var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            var read=await client.GetFromJsonAsync<JsonElement>($"/api/data/purchasing-organizations/{id}/coverage?tenantId={tenant}");
            Assert(read.GetProperty("coverage").GetArrayLength()==0,"Implicit scope created.");
            using var cleared=await client.PutAsJsonAsync(Url(owner),new {coverage=Array.Empty<object>()});
            Assert(cleared.StatusCode==HttpStatusCode.OK,"Clear coverage rejected.");
            var audit=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@o AND action='replace_coverage' ORDER BY created_at DESC LIMIT 1",("o",owner)))!);
            Assert(audit.GetProperty("before").GetArrayLength()==2 && audit.GetProperty("after").GetArrayLength()==0,"Coverage before/after clearing incorrect.");
            using var restored=await client.PutAsJsonAsync(Url(owner),new {coverage});
            Assert(restored.IsSuccessStatusCode,"Coverage restore failed.");
        });
    }
}
