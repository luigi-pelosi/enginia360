using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Organizations;
using System.Net;
using System.Net.Http.Json;
using System.Reflection;
using System.Text.Json;

namespace Enginia360.Verification.Organizations;

public static class CommercialOrganizationLifecycleTests
{
    public static async Task Run(HttpClient client,AppDb db,Guid tenant,Guid admin,Action<Guid> actor,Guid owner,Guid a,Guid b,Guid site,Action<string,Action> test)
    {
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> run) => test("commercial: "+name,() => run().GetAwaiter().GetResult());
        async Task<bool> Applies(Guid t,Guid o,Guid c,Guid s) {
            var method=typeof(PurchasingCoverage).GetMethod("IsApplicableToSite",BindingFlags.Static|BindingFlags.Public|BindingFlags.NonPublic,null,new[]{typeof(AppDb),typeof(Guid),typeof(Guid),typeof(Guid),typeof(Guid)},null);
            Assert(method!=null,"Missing focused PurchasingCoverage.IsApplicableToSite.");
            return await (Task<bool>)method!.Invoke(null,new object[]{db,t,o,c,s})!;
        }
        var futureA=Guid.NewGuid(); var futureB=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.site(id,tenant_id,company_id,name,address,city,province,postal_code,country_code) VALUES(@s1,@t,@a,'Future A','Synthetic Road 42','Synthetic City','Synthetic Region','AB 12-X','GB'),(@s2,@t,@b,'Future B','Synthetic Road 42','Synthetic City','Synthetic Region','AB 12-X','GB')",("s1",futureA),("s2",futureB),("t",tenant),("a",a),("b",b));
        Case("all_sites includes future sites but selected_sites excludes future sites",async () => {
            Assert(await Applies(tenant,owner,a,futureA),"all_sites must include future matching sites.");
            Assert(await Applies(tenant,owner,b,site),"Selected configured site must apply.");
            Assert(!await Applies(tenant,owner,b,futureB),"Selected scope silently included future site.");
            Assert(!await Applies(tenant,owner,a,site),"Mismatched company/site applied.");
            Assert(!await Applies(Guid.NewGuid(),owner,a,futureA),"Foreign tenant applied.");
            Assert(!await Applies(tenant,Guid.NewGuid(),a,futureA),"Unknown owner applied.");
            Assert(!await Applies(tenant,owner,a,Guid.NewGuid()),"Unknown site applied.");
            using var created=await client.PostAsJsonAsync($"/api/data/purchasing-organizations?tenantId={tenant}",new {name="Unassigned eligibility"});
            var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            Assert(!await Applies(tenant,id,a,futureA),"Unassigned organization applied.");
        });
        foreach(var context in new[]{("tenant",tenant),("purchasing_organization",owner),("company",a),("site",futureA)})
        Case("inactive "+context.Item1+" disallows applicability but keeps coverage",async () => {
            await db.Execute($"UPDATE {SqlNames.Table(context.Item1)} SET is_enabled=false WHERE id=@id",("id",context.Item2));
            try {
                Assert(!await Applies(tenant,owner,a,futureA),"Inactive context still applicable.");
                using var response=await client.GetAsync($"/api/data/purchasing-organizations/{owner}/coverage?tenantId={tenant}");
                Assert(response.StatusCode==HttpStatusCode.OK,"Disabled context coverage must remain readable by global.");
                var coverage=(await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("coverage");
                Assert(coverage.GetArrayLength()==2,"Disabling context removed coverage.");
                using var saved=await client.PutAsJsonAsync($"/api/data/purchasing-organizations/{owner}/save?tenantId={tenant}",new {coverage});
                Assert(saved.StatusCode==HttpStatusCode.OK,"Inactive context configuration must remain maintainable.");
            } finally {await db.Execute($"UPDATE {SqlNames.Table(context.Item1)} SET is_enabled=true WHERE id=@id",("id",context.Item2));}
            Assert(await Applies(tenant,owner,a,futureA),"Reenabled context did not recover eligibility.");
        });
        async Task<Guid> Create(bool assigned=true) {
            var coverage=assigned ? new[]{new {companyId=b,siteScope="selected_sites",siteIds=new[]{site}}} : [];
            using var response=await client.PostAsJsonAsync($"/api/data/purchasing-organizations/save?tenantId={tenant}",new {values=new {name="Lifecycle"},coverage});
            Assert(response.StatusCode==HttpStatusCode.Created,"Lifecycle fixture create failed.");
            return (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
        }
        async Task<string> Snapshot(Guid id) => (string)(await db.Scalar("""
            SELECT jsonb_build_object('owner',(SELECT to_jsonb(t) FROM foundation.purchasing_organization t WHERE id=@o),
              'companies',(SELECT jsonb_agg(to_jsonb(t) ORDER BY company_id) FROM foundation.purchasing_organization_company t WHERE purchasing_organization_id=@o),
              'sites',(SELECT jsonb_agg(to_jsonb(t) ORDER BY company_id,site_id) FROM foundation.purchasing_organization_site t WHERE purchasing_organization_id=@o),
              'audit',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.audit_event t WHERE record_id=@o))::text
            """,("o",id)))!;
        Case("delete audit includes prior coverage even when empty",async () => {
            var id=await Create(false);
            using var response=await client.DeleteAsync($"/api/data/purchasing-organizations/{id}?tenantId={tenant}");
            Assert(response.StatusCode==HttpStatusCode.NoContent,"Unassigned delete failed.");
            var audit=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action='delete'",("id",id)))!);
            Assert(audit.GetProperty("coverage").GetArrayLength()==0 && audit.GetProperty("before").GetProperty("name").GetString()=="Lifecycle","Delete prior scope snapshot required.");
        });
        Case("delete-only authority removes own site then company composition and parent",async () => {
            var id=await Create();
            var user=new User {TenantId=tenant,Username="delete-"+Guid.NewGuid(),FirstName="Delete",LastName="Only",Email="delete@example.test",PasswordHash="fixture",MustChangePassword=false};
            db.Users.Add(user); await db.SaveChangesAsync();
            var role=Guid.NewGuid();
            await db.Execute("INSERT INTO foundation.role(id,tenant_id,name) VALUES(@r,@t,'Delete only'); INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r); INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code='purchasing-organizations.delete'",("r",role),("t",tenant),("u",user.Id));
            actor(user.Id);
            try {
                using var response=await client.DeleteAsync($"/api/data/purchasing-organizations/{id}");
                Assert(response.StatusCode==HttpStatusCode.NoContent,"Delete-only must suffice for aggregate; actual "+(int)response.StatusCode);
                Assert(await db.Scalar("SELECT id FROM foundation.purchasing_organization WHERE id=@id",("id",id))==null,"Owner survived delete.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.purchasing_organization_company WHERE purchasing_organization_id=@id",("id",id)))! == 0,"Company children survived.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.purchasing_organization_site WHERE purchasing_organization_id=@id",("id",id)))! == 0,"Site children survived.");
                var audit=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action='delete'",("id",id)))!);
                Assert(audit.GetProperty("coverage")[0].GetProperty("siteIds")[0].GetGuid()==site,"Delete audit lost prior coverage.");
            } finally {actor(admin);}
        });
        Case("other owner references reject delete and restore full composition",async () => {
            var id=await Create();
            await db.Execute("CREATE TABLE foundation.coverage_delete_reference(owner_id uuid REFERENCES foundation.purchasing_organization(id)); INSERT INTO foundation.coverage_delete_reference VALUES(@id)",("id",id));
            try {
                var before=await Snapshot(id);
                using var response=await client.DeleteAsync($"/api/data/purchasing-organizations/{id}?tenantId={tenant}");
                Assert(response.StatusCode==HttpStatusCode.Conflict,"Unrelated references must restrict deletion.");
                Assert(await Snapshot(id)==before,"Delete conflict lost composition or audit.");
            } finally {await db.Execute("DROP TABLE foundation.coverage_delete_reference");}
        });
        foreach(var deferred in new[]{false,true}) Case((deferred ? "deferred" : "immediate")+" delete audit failure restores composition",async () => {
            var id=await Create();
            await db.Execute("CREATE FUNCTION foundation.coverage_delete_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='purchasing-organizations' AND NEW.action='delete' THEN RAISE EXCEPTION 'fixture fault' USING ERRCODE='"+(deferred ? "P0001" : "23514")+"'; END IF; RETURN NEW; END $$");
            try {
                await db.Execute(deferred ? "CREATE CONSTRAINT TRIGGER coverage_delete_fault AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.coverage_delete_fault()" : "CREATE TRIGGER coverage_delete_fault BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.coverage_delete_fault()");
                var before=await Snapshot(id);
                using var response=await client.DeleteAsync($"/api/data/purchasing-organizations/{id}?tenantId={tenant}");
                Assert(response.StatusCode==(deferred ? HttpStatusCode.InternalServerError : HttpStatusCode.BadRequest),"Delete audit fault did not reach expected gate: "+response.StatusCode);
                Assert(await Snapshot(id)==before,"Delete audit failure lost composition.");
            } finally {await db.Execute("DROP TRIGGER IF EXISTS coverage_delete_fault ON foundation.audit_event; DROP FUNCTION foundation.coverage_delete_fault()");}
        });
    }
}
