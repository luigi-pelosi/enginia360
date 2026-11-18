using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Enginia360.Verification.Shared;

// Prove HTTP su PostgreSQL dedicato; cookie e CSRF spettano all'integrazione.
public static class UnifiedSaveTests
{
    public static async Task Run(HttpClient client,AppDb db,Guid tenant,Guid admin,Action<Guid> actor,Action<string,Action> test)
    {
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> run) => test("unified save: "+name,() => run().GetAwaiter().GetResult());
        var user=new User {TenantId=tenant,Username="save-"+Guid.NewGuid(),FirstName="Save",LastName="Test",Email="save@example.test",PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(user); await db.SaveChangesAsync();
        var role=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@id,@t,@code,'Save role')",("id",role),("t",tenant),("code",role.ToString()));
        var group=Guid.Empty;
        Case("POST group commits record two link sets and three audits together",async () => {
            using var response=await client.PostAsJsonAsync($"/api/data/groups/save?tenantId={tenant}",new {values=new {code="save-"+Guid.NewGuid(),name="Saved group"},links=new Dictionary<string,Guid[]> { ["group-users"]=[user.Id],["group-roles"]=[role] }});
            Assert(response.StatusCode==HttpStatusCode.Created,"Expected 201 for POST group save; actual "+response.StatusCode);
            var body=await response.Content.ReadFromJsonAsync<JsonElement>(); group=body.GetProperty("id").GetGuid();
            Assert(body.GetProperty("name").GetString()=="Saved group","Public record missing.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_group_member WHERE user_group_id=@id AND user_id=@u",("id",group),("u",user.Id)))! == 1,"User link missing.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_group_role WHERE user_group_id=@id AND role_id=@r",("id",group),("r",role)))! == 1,"Role link missing.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@id",("id",group)))! == 3,"Expected record and both relation audits in same commit.");
        });
        async Task<string> Snapshot() => (string)(await db.Scalar("""
            SELECT jsonb_build_object(
                'tenants',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.tenant t),
                'permissions',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.permission t),
                'groups',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.user_group t),
                'roles',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.role t),
                'users',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation."user" t),
                'members',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,user_group_id,user_id) FROM foundation.user_group_member t),
                'groupRoles',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,user_group_id,role_id) FROM foundation.user_group_role t),
                'userRoles',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,user_id,role_id) FROM foundation.user_role t),
                'grants',(SELECT jsonb_agg(to_jsonb(t) ORDER BY tenant_id,role_id,permission_id) FROM foundation.role_permission t),
                'audits',(SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM foundation.audit_event t))::text
            """))!;
        async Task Refuse(HttpMethod method,string url,object payload,HttpStatusCode status)
        {
            var before=await Snapshot();
            using var request=new HttpRequestMessage(method,url) {Content=payload is string raw ? new StringContent(raw,System.Text.Encoding.UTF8,"application/json") : JsonContent.Create(payload)};
            using var response=await client.SendAsync(request);
            Assert(response.StatusCode==status,$"Expected {(int)status}; actual {(int)response.StatusCode}: {await response.Content.ReadAsStringAsync()}");
            Assert(before==await Snapshot(),"Refused save left partial records, grants or audits.");
        }
        object GroupPayload(Guid target) => new {values=new {code="save-"+Guid.NewGuid(),name="Rollback group"},links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id],["group-roles"]=[target]}};
        string GroupUrl(Guid id) => $"/api/data/groups/{id}/save?tenantId={tenant}";
        Case("record links and audits have one PostgreSQL transaction ID",async () => {
            var transactions=(long)(await db.Scalar("""
                SELECT count(DISTINCT xid) FROM (
                    SELECT xmin::text xid FROM foundation.user_group WHERE id=@g
                    UNION ALL SELECT xmin::text FROM foundation.user_group_member WHERE user_group_id=@g
                    UNION ALL SELECT xmin::text FROM foundation.user_group_role WHERE user_group_id=@g
                    UNION ALL SELECT xmin::text FROM foundation.audit_event WHERE record_id=@g) s
                """,("g",group)))!;
            Assert(group!=Guid.Empty && transactions==1,"Mutations were not one transaction.");
        });
        Case("invalid second target rolls back inserted owner first relation and audit",async () =>
            await Refuse(HttpMethod.Post,$"/api/data/groups/save?tenantId={tenant}",GroupPayload(Guid.NewGuid()),HttpStatusCode.BadRequest));
        Case("combined update replaces both sets and returns public record",async () => {
            using var response=await client.PutAsJsonAsync(GroupUrl(group),new {values=new {name="Updated group"},links=new Dictionary<string,Guid[]> {["group-users"]=[],["group-roles"]=[]}});
            Assert(response.StatusCode==HttpStatusCode.OK,"Combined update failed.");
            Assert((await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("name").GetString()=="Updated group","Update response wrong.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_group_member WHERE user_group_id=@g",("g",group)))! == 0,"Members not replaced.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_group_role WHERE user_group_id=@g",("g",group)))! == 0,"Roles not replaced.");
            var details=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@g AND action='update'",("g",group)))!);
            Assert(details.GetProperty("before").GetProperty("name").GetString()=="Saved group" && details.GetProperty("after").GetProperty("name").GetString()=="Updated group","Snapshots not reused.");
        });
        Case("invalid second target rolls back update and first replacement",async () =>
            await Refuse(HttpMethod.Put,GroupUrl(group),new {values=new {name="Must roll back"},links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id],["group-roles"]=[Guid.NewGuid()]}},HttpStatusCode.BadRequest));
        foreach(var deferred in new[]{false,true}) Case(deferred ? "deferred audit failure rolls back entire command at commit" : "last relation audit failure rolls back all preceding writes",async () => {
            await db.Execute("""
                CREATE FUNCTION foundation.unified_save_audit_fault() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.resource='group-roles' THEN RAISE EXCEPTION 'fixture audit fault' USING ERRCODE='23514'; END IF; RETURN NEW; END $$
                """.Replace("23514",deferred ? "P0001" : "23514",StringComparison.Ordinal));
            var failure=deferred ? HttpStatusCode.InternalServerError : HttpStatusCode.BadRequest;
            try {
                await db.Execute(deferred
                    ? "CREATE CONSTRAINT TRIGGER unified_save_audit_fault AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.unified_save_audit_fault()"
                    : "CREATE TRIGGER unified_save_audit_fault BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.unified_save_audit_fault()");
                await Refuse(HttpMethod.Post,$"/api/data/groups/save?tenantId={tenant}",GroupPayload(role),failure);
                await Refuse(HttpMethod.Put,GroupUrl(group),new {values=new {name="Audit rollback"},links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id],["group-roles"]=[role]}},failure);
            } finally { await db.Execute("DROP TRIGGER IF EXISTS unified_save_audit_fault ON foundation.audit_event; DROP FUNCTION foundation.unified_save_audit_fault()"); }
        });
        var authorityRole=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@id,@t,@code,'Save authority'); INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@id)",("id",authorityRole),("t",tenant),("code",authorityRole.ToString()),("u",user.Id));
        async Task Grants(params string[] codes) => await db.Execute("DELETE FROM foundation.role_permission WHERE role_id=@r; INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code=ANY(@codes)",("r",authorityRole),("t",tenant),("codes",codes));
        Case("all create and update gates preflight before first write",async () => {
            // La sequenza non transazionale rivela anche scritture poi annullate.
            await db.Execute("""
                CREATE SEQUENCE foundation.unified_save_write_probe;
                CREATE FUNCTION foundation.unified_save_write_probe() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN PERFORM nextval('foundation.unified_save_write_probe'); RETURN NEW; END $$;
                CREATE TRIGGER unified_save_write_probe BEFORE INSERT OR UPDATE ON foundation.user_group FOR EACH ROW EXECUTE FUNCTION foundation.unified_save_write_probe()
                """);
            actor(user.Id);
            try {
                foreach(var create in new[]{true,false}) foreach(var missing in new[]{create ? "groups.create" : "groups.update","groups.assign_users","roles.assign"}) {
                    var required=new[]{create ? "groups.create" : "groups.update","groups.assign_users","roles.assign"};
                    await Grants(required.Where(c => c!=missing).ToArray());
                    await Refuse(create ? HttpMethod.Post : HttpMethod.Put,create ? "/api/data/groups/save" : $"/api/data/groups/{group}/save",GroupPayload(role),HttpStatusCode.Forbidden);
                }
                Assert(!(bool)(await db.Scalar("SELECT is_called FROM foundation.unified_save_write_probe"))!,"A write happened before every gate passed.");
                await Grants("groups.update");
                await Refuse(HttpMethod.Put,$"/api/data/groups/{group}/save",new {links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id]}},HttpStatusCode.Forbidden);
                await Grants("groups.assign_users","roles.assign");
                await Refuse(HttpMethod.Put,$"/api/data/groups/{group}/save",new {values=new {name="Denied"},links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id]}},HttpStatusCode.Forbidden);
            } finally {actor(admin); await db.Execute("DROP TRIGGER unified_save_write_probe ON foundation.user_group; DROP FUNCTION foundation.unified_save_write_probe(); DROP SEQUENCE foundation.unified_save_write_probe");}
        });
        Case("assignment-only actor saves omitted values without update and gets only id",async () => {
            await Grants("groups.assign_users","roles.assign"); actor(user.Id);
            try {
                var before=(long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@g AND action='update'",("g",group)))!;
                using var response=await client.PutAsJsonAsync($"/api/data/groups/{group}/save",new {links=new Dictionary<string,Guid[]> {["group-users"]=[user.Id],["group-roles"]=[role]}});
                Assert(response.StatusCode==HttpStatusCode.OK,"Assignment-only actor denied.");
                var body=await response.Content.ReadFromJsonAsync<JsonElement>();
                Assert(body.EnumerateObject().Count()==1 && body.GetProperty("id").GetGuid()==group,"Assignment-only response leaks anagraphic fields.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@g AND action='update'",("g",group)))! == before,"Assignment-only wrote record audit.");
                Assert((string)(await db.Scalar("SELECT name FROM foundation.user_group WHERE id=@g",("g",group)))! == "Updated group","Assignment-only changed profile.");
            } finally {actor(admin);}
        });
        Case("unknown duplicate null and empty command fields reject with no writes",async () => {
            foreach(var payload in new[]{"{}","[]","null","{\"values\":null}","{\"links\":null}","{\"values\":{}}","{\"links\":{}}","{\"values\":{},\"links\":{\"group-users\":[]}}","{\"extra\":{}}","{\"values\":{\"name\":\"a\"},\"values\":{\"name\":\"b\"}}","{\"links\":{},\"links\":{}}","{\"values\":{\"name\":\"a\",\"name\":\"b\"}}","{\"values\":{\"id\":\"injected\"}}","{\"links\":{\"unknown\":[]}}","{\"links\":{\"user-roles\":[]}}","{\"links\":{\"group-users\":[],\"group-users\":[]}}","{\"links\":{\"group-users\":null}}","{\"links\":{\"group-users\":{}}}"})
                await Refuse(HttpMethod.Put,GroupUrl(group),payload,HttpStatusCode.BadRequest);
            foreach(var payload in new[]{"{}","{\"links\":{\"group-users\":[]}}","{\"values\":{}}"})
                await Refuse(HttpMethod.Post,$"/api/data/groups/save?tenantId={tenant}",payload,HttpStatusCode.BadRequest);
        });
        Case("link UUID validation duplicates and max500 are preserved",async () => {
            foreach(var ids in new object[]{new[]{"bad"},new[]{Guid.Empty.ToString()},new[]{user.Id,user.Id},new object?[]{null},new[]{1},Enumerable.Range(0,501).Select(_ => Guid.NewGuid()).ToArray()})
                await Refuse(HttpMethod.Put,GroupUrl(group),new {links=new Dictionary<string,object> {["group-users"]=ids}},HttpStatusCode.BadRequest);
            using var response=await client.PutAsJsonAsync(GroupUrl(group),new {links=new Dictionary<string,Guid[]> {["group-users"]=[]}});
            Assert(response.StatusCode==HttpStatusCode.OK,"Empty set is valid replacement.");
        });
        var otherTenant=Guid.NewGuid(); var otherGroup=Guid.NewGuid(); var otherRole=Guid.NewGuid(); var otherUser=Guid.NewGuid();
        await db.Execute("""
            INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Other save tenant');
            INSERT INTO foundation.user_group(id,tenant_id,code,name) VALUES(@g,@t,'g','Other group');
            INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@r,@t,'r','Other role');
            INSERT INTO foundation."user"(id,tenant_id,username,first_name,last_name,email) VALUES(@u,@t,'u','Other','User','other@example.test')
            """,("t",otherTenant),("code",otherTenant.ToString()),("g",otherGroup),("r",otherRole),("u",otherUser));
        Case("cross-tenant owner and every target stay scoped",async () => {
            await Refuse(HttpMethod.Put,GroupUrl(otherGroup),new {links=new Dictionary<string,Guid[]> {["group-users"]=[]}},HttpStatusCode.NotFound);
            await Refuse(HttpMethod.Put,GroupUrl(group),new {links=new Dictionary<string,Guid[]> {["group-users"]=[otherUser]}},HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Post,$"/api/data/groups/save?tenantId={tenant}",GroupPayload(otherRole),HttpStatusCode.BadRequest);
            await Grants("groups.update"); actor(user.Id);
            try {await Refuse(HttpMethod.Put,$"/api/data/groups/{otherGroup}/save?tenantId={otherTenant}",new {values=new {name="Denied"}},HttpStatusCode.Forbidden);}
            finally {actor(admin);}
        });
        Case("global self remains readonly as owner and user target",async () => {
            await Refuse(HttpMethod.Put,$"/api/data/users/{admin}/save?tenantId={tenant}",new {values=new {first_name="Denied"}},HttpStatusCode.NotFound);
            await Refuse(HttpMethod.Put,$"/api/data/users/{admin}/save?tenantId={tenant}",new {links=new Dictionary<string,Guid[]> {["user-roles"]=[role]}},HttpStatusCode.NotFound);
            await Refuse(HttpMethod.Post,$"/api/data/groups/save?tenantId={tenant}",new {values=new {code="global-denied",name="Denied"},links=new Dictionary<string,Guid[]> {["group-users"]=[admin]}},HttpStatusCode.BadRequest);
        });
        var permission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.delete'",("t",tenant)))!;
        Case("catalog remains readonly on new routes even for global actor",async () => {
            await Refuse(HttpMethod.Post,$"/api/data/permissions/save?tenantId={tenant}",new {values=new {code="denied",name="Denied"}},HttpStatusCode.Forbidden);
            await Refuse(HttpMethod.Put,$"/api/data/permissions/{permission}/save?tenantId={tenant}",new {values=new {name="Denied"}},HttpStatusCode.Forbidden);
        });
        Case("role permissions and user roles reuse exact authorities without own-grant restriction",async () => {
            await Grants("roles.assign_permissions"); actor(user.Id);
            try {
                using var response=await client.PutAsJsonAsync($"/api/data/roles/{role}/save",new {links=new Dictionary<string,Guid[]> {["role-permissions"]=[permission]}});
                Assert(response.StatusCode==HttpStatusCode.OK,"Exact assign permission denied.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r AND permission_id=@p",("r",role),("p",permission)))! == 1,"Grant not persisted.");
                await Refuse(HttpMethod.Put,$"/api/data/users/{user.Id}/save",new {links=new Dictionary<string,Guid[]> {["user-roles"]=[role]}},HttpStatusCode.Forbidden);
                await Grants("roles.assign");
                using var assigned=await client.PutAsJsonAsync($"/api/data/users/{user.Id}/save",new {links=new Dictionary<string,Guid[]> {["user-roles"]=[authorityRole,role]}});
                Assert(assigned.StatusCode==HttpStatusCode.OK,"Exact user role authority denied.");
            } finally {actor(admin);}
        });
        Case("tenant save seeds immutable catalog and seed audit in same transaction",async () => {
            using var response=await client.PostAsJsonAsync("/api/data/tenants/save",new {values=new {code="save-tenant-"+Guid.NewGuid(),name="Saved tenant"}});
            Assert(response.StatusCode==HttpStatusCode.Created,"Tenant save failed.");
            var id=(await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.permission WHERE tenant_id=@t AND is_system",("t",id)))! == PermissionCatalog.Codes.Length,"Seed missing.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE tenant_id=@t",("t",id)))! == 0,"Seed grants created.");
            var details=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@t AND action='create'",("t",id)))!);
            Assert(details.GetProperty("permissionCatalog").GetArrayLength()==PermissionCatalog.Codes.Length,"Seed audit provenance missing.");
            Assert((long)(await db.Scalar("SELECT count(DISTINCT xid) FROM (SELECT xmin::text xid FROM foundation.tenant WHERE id=@t UNION ALL SELECT xmin::text FROM foundation.permission WHERE tenant_id=@t UNION ALL SELECT xmin::text FROM foundation.audit_event WHERE record_id=@t) s",("t",id)))! == 1,"Seed not in same commit.");
        });
        Case("valid limit of 500 distinct UUID targets is accepted",async () => {
            await db.Execute("INSERT INTO foundation.\"user\"(tenant_id,username,first_name,last_name,email) SELECT @t,'save-limit-'||i,'Limit','User','limit'||i||'@example.test' FROM generate_series(1,500) i",("t",tenant));
            var ids=new List<Guid>();
            await using(var cmd=await db.Command("SELECT id FROM foundation.\"user\" WHERE tenant_id=@t AND username LIKE 'save-limit-%' ORDER BY id",("t",tenant)))
            await using(var reader=await cmd.ExecuteReaderAsync()) while(await reader.ReadAsync()) ids.Add(reader.GetGuid(0));
            Assert(ids.Count==500,"Limit fixture not exact.");
            using var response=await client.PutAsJsonAsync(GroupUrl(group),new {links=new Dictionary<string,Guid[]> {["group-users"]=ids.ToArray()}});
            Assert(response.StatusCode==HttpStatusCode.OK,"500 valid IDs rejected.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_group_member WHERE user_group_id=@g",("g",group)))! == 500,"500 IDs not persisted.");
        });
        Case("users and roles create with links return only public projections",async () => {
            using var created=await client.PostAsJsonAsync($"/api/data/users/save?tenantId={tenant}",new {values=new {username="save-created-"+Guid.NewGuid(),first_name="Save",last_name="Created",email="created@example.test"},links=new Dictionary<string,Guid[]> {["user-roles"]=[role]}});
            Assert(created.StatusCode==HttpStatusCode.Created,"User combined create failed.");
            var body=await created.Content.ReadFromJsonAsync<JsonElement>(); var id=body.GetProperty("id").GetGuid();
            Assert(!body.TryGetProperty("password_hash",out _) && !body.TryGetProperty("security_stamp",out _),"User security fields exposed.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_role WHERE user_id=@u AND role_id=@r",("u",id),("r",role)))! == 1,"New user role not persisted.");
            using var updated=await client.PutAsJsonAsync($"/api/data/users/{id}/save?tenantId={tenant}",new {values=new {username="renamed-"+id},links=new Dictionary<string,Guid[]> {["user-roles"]=[]}});
            Assert(updated.StatusCode==HttpStatusCode.OK,"User combined update failed.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_role WHERE user_id=@u",("u",id)))! == 0,"User combined update kept role.");
            using var roleCreated=await client.PostAsJsonAsync($"/api/data/roles/save?tenantId={tenant}",new {values=new {code="save-role-"+Guid.NewGuid(),name="Created role"},links=new Dictionary<string,Guid[]> {["role-permissions"]=[permission]}});
            Assert(roleCreated.StatusCode==HttpStatusCode.Created,"Role combined create failed.");
            var roleId=(await roleCreated.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r AND permission_id=@p",("r",roleId),("p",permission)))! == 1,"New role grant not persisted.");
            using var roleUpdated=await client.PutAsJsonAsync($"/api/data/roles/{roleId}/save?tenantId={tenant}",new {values=new {name="Updated role"},links=new Dictionary<string,Guid[]> {["role-permissions"]=[]}});
            Assert(roleUpdated.StatusCode==HttpStatusCode.OK,"Role combined update failed.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r",("r",roleId)))! == 0,"Role combined update kept grant.");
        });
        Case("foreign and legacy permissions and foreign user roles reject atomically",async () => {
            await using(var tx=await db.Database.BeginTransactionAsync()) {
                await Security.Lock(db); await PermissionCatalog.Seed(db,otherTenant); await tx.CommitAsync();
            }
            var foreignPermission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t LIMIT 1",("t",otherTenant)))!;
            var legacy=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.write'",("t",tenant)))!;
            foreach(var target in new[]{foreignPermission,legacy})
                await Refuse(HttpMethod.Put,$"/api/data/roles/{role}/save?tenantId={tenant}",new {values=new {name="Denied"},links=new Dictionary<string,Guid[]> {["role-permissions"]=[target]}},HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Put,$"/api/data/users/{user.Id}/save?tenantId={tenant}",new {values=new {first_name="Denied"},links=new Dictionary<string,Guid[]> {["user-roles"]=[otherRole]}},HttpStatusCode.BadRequest);
        });
        Case("tenant seed rolls back together with failed create audit",async () => {
            await db.Execute("""
                CREATE FUNCTION foundation.unified_seed_audit_fault() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.resource='tenants' THEN RAISE EXCEPTION 'fixture seed audit fault' USING ERRCODE='23514'; END IF; RETURN NEW; END $$;
                CREATE TRIGGER unified_seed_audit_fault BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.unified_seed_audit_fault()
                """);
            try {await Refuse(HttpMethod.Post,"/api/data/tenants/save",new {values=new {code="save-seed-rollback",name="Denied"}},HttpStatusCode.BadRequest);}
            finally {await db.Execute("DROP TRIGGER unified_seed_audit_fault ON foundation.audit_event; DROP FUNCTION foundation.unified_seed_audit_fault()");}
        });
        Case("values-only save needs only its CRUD authority",async () => {
            await Grants("groups.update"); actor(user.Id);
            try {
                using var response=await client.PutAsJsonAsync($"/api/data/groups/{group}/save",new {values=new {description="Values only"}});
                Assert(response.StatusCode==HttpStatusCode.OK,"Values-only save requires unrelated assignment gate.");
            } finally {actor(admin);}
        });
        Case("self-disable and assignment complete under preflight identity then fresh load denies",async () => {
            await Grants("users.update","roles.assign"); actor(user.Id);
            try {
                using var response=await client.PutAsJsonAsync($"/api/data/users/{user.Id}/save",new {values=new {is_enabled=false},links=new Dictionary<string,Guid[]> {["user-roles"]=[role]}});
                Assert(response.StatusCode==HttpStatusCode.OK,"Preflight identity was reauthorized after self-disable.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.user_role WHERE user_id=@u AND role_id=@r",("u",user.Id),("r",role)))! == 1,"Self-disable lost combined role assignment.");
                db.ChangeTracker.Clear();
                Assert(await Security.Load(db,user.Id)==null,"Disabled actor still loads freshly.");
            } finally {actor(admin); await db.Execute("UPDATE foundation.\"user\" SET is_enabled=true WHERE id=@u",("u",user.Id)); db.ChangeTracker.Clear();}
        });
        foreach(var raw in new[]{"{\"values\":{\"name\":\"bad\\u0000value\"}}","{\"values\":{\"name\":\"bad\\ud800value\"}}","{\"links\":{\"group-users\":[\"\\ud800\"]}}","{\"\\ud800\":{}}","{\"values\":{\"\\ud800\":\"x\"}}","{\"links\":{\"\\ud800\":[]}}"})
            Case("escaped invalid JSON text is a 400: "+raw,async () => await Refuse(HttpMethod.Put,GroupUrl(group),raw,HttpStatusCode.BadRequest));
        Case("legacy CRUD and links remain equivalent after shared primitive refactor",async () => {
            using var response=await client.PostAsJsonAsync($"/api/data/groups?tenantId={tenant}",new {code="legacy-save-"+Guid.NewGuid(),name="Legacy"});
            Assert(response.StatusCode==HttpStatusCode.Created,"Legacy create status changed.");
            var id=(await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            using var update=await client.PutAsJsonAsync($"/api/data/groups/{id}?tenantId={tenant}",new {name="Legacy updated"});
            Assert(update.StatusCode==HttpStatusCode.OK && (await update.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("name").GetString()=="Legacy updated","Legacy update contract changed.");
            foreach(var name in new[]{"group-users","group-roles"}) {
                var target=name=="group-users" ? user.Id : role;
                using var replaced=await client.PutAsJsonAsync($"/api/links/{name}/{id}?tenantId={tenant}",new {ids=new[]{target}});
                Assert(replaced.StatusCode==HttpStatusCode.NoContent,"Legacy replacement status changed.");
                var read=await client.GetFromJsonAsync<JsonElement>($"/api/links/{name}/{id}?tenantId={tenant}");
                Assert(read.GetProperty("ids").EnumerateArray().Select(v => v.GetGuid()).SequenceEqual(new[]{target}),"Legacy replacement readback changed.");
            }
        });
    }
}
