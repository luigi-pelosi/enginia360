using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Enginia360.Verification.Organizations;
using Enginia360.Verification.Shared;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Enginia360.Verification.AccessControl;

// Fixture HTTP isolata: usa endpoint e handler reali, senza cookie/CSRF (verificati dall'integrazione).
public static class RbacTests
{
    public static void Run(string connection,Action<string,Action> test) => RunAsync(connection,test).GetAwaiter().GetResult();
    private static async Task RunAsync(string connection,Action<string,Action> test)
    {
        var builder=WebApplication.CreateBuilder();
        builder.Logging.ClearProviders();
        builder.WebHost.UseUrls("http://127.0.0.1:0");
        builder.Services.AddDbContext<AppDb>(o => o.UseNpgsql(connection));
        PermissionCatalog.Configure(builder.Services);
        await using var app=builder.Build();
        using var setup=app.Services.CreateScope();
        var db=setup.ServiceProvider.GetRequiredService<AppDb>();
        var admin=new User {Username="test-"+Guid.NewGuid(),FirstName="Test",LastName="Admin",Email="admin@example.test",IsSuperAdmin=true,PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(admin); await db.SaveChangesAsync();
        var actor=admin.Id;
        app.Use(async (ctx,next) => {
            var requestDb=ctx.RequestServices.GetRequiredService<AppDb>();
            await using var tx=await requestDb.Database.BeginTransactionAsync();
            await Security.Lock(requestDb);
            ctx.Items["identity"]=(await Security.Load(requestDb,actor))!;
            // Come in Program: nessuna risposta pubblicata prima del commit, inclusi errori differiti.
            var original=ctx.Response.Body;
            await using var buffer=new MemoryStream(); ctx.Response.Body=buffer;
            try {
                await next();
                if(ctx.Response.StatusCode<400) await tx.CommitAsync(); else await tx.RollbackAsync();
                ctx.Response.Body=original; buffer.Position=0; await buffer.CopyToAsync(original);
            }
            catch(Exception e) {
                // Il server può aver già annullato la transazione su un vincolo differito.
                if(requestDb.Database.GetDbConnection().State==System.Data.ConnectionState.Open)
                    try {await tx.RollbackAsync();} catch(InvalidOperationException) { }
                ctx.Response.Body=original; ctx.Response.Clear();
                var (status,code)=e switch {
                    ApiException a => (a.Status,a.Code),
                    PostgresException p when p.SqlState is "23503" or "23505" => (409,"conflict"),
                    PostgresException p when p.SqlState is "23514" or "23502" or "22001" or "22P02" or "22P05" => (400,"validation_error"),
                    _ => (500,"server_error")
                };
                ctx.Response.StatusCode=status; await ctx.Response.WriteAsJsonAsync(new {code});
            }
            finally {ctx.Response.Body=original;}
        });
        DataEndpoints.Map(app); AuthEndpoints.Map(app);
        await app.StartAsync();
        var address=app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single();
        using var client=new HttpClient {BaseAddress=new Uri(address)};
        var tenant=Guid.Empty;
        void Assert(bool ok,string message) {if(!ok) throw new Exception(message);}
        void Case(string name,Func<Task> action) => test(name,() => action().GetAwaiter().GetResult());
        Case("HTTP new tenant seeds exact finite catalog without grants",async () => {
            using var response=await client.PostAsJsonAsync("/api/data/tenants",new {code="test-"+Guid.NewGuid(),name="RBAC test"});
            Assert(response.StatusCode==HttpStatusCode.Created,"Tenant create status: "+response.StatusCode+" "+await response.Content.ReadAsStringAsync());
            tenant=(await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            var count=(long)(await db.Scalar("SELECT count(*) FROM foundation.permission WHERE tenant_id=@tenant AND is_system",("tenant",tenant)))!;
            Assert(count==PermissionCatalog.Codes.Length,"Seed count expected "+PermissionCatalog.Codes.Length+", actual "+count);
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE tenant_id=@tenant",("tenant",tenant)))! == 0,"Implicit grants created.");
        });
        Case("fresh load unions direct and active group grants and ignores legacy",async () => {
            var user=new User {TenantId=tenant,Username="member",FirstName="Test",LastName="User",Email="member@example.test",PasswordHash="fixture",MustChangePassword=false};
            db.Users.Add(user); await db.SaveChangesAsync();
            var direct=Guid.NewGuid(); var groupRole=Guid.NewGuid(); var group=Guid.NewGuid();
            foreach(var role in new[]{direct,groupRole}) await db.Execute("INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@id,@t,@code,'test')",("id",role),("t",tenant),("code",role.ToString()));
            await db.Execute("INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r)",("t",tenant),("u",user.Id),("r",direct));
            await db.Execute("INSERT INTO foundation.user_group(id,tenant_id,code,name) VALUES(@id,@t,'g','g'); INSERT INTO foundation.user_group_member(tenant_id,user_group_id,user_id) VALUES(@t,@id,@u); INSERT INTO foundation.user_group_role(tenant_id,user_group_id,role_id) VALUES(@t,@id,@r)",("id",group),("t",tenant),("u",user.Id),("r",groupRole));
            await db.Execute("UPDATE foundation.permission SET is_system=false WHERE tenant_id=@t AND code='sites.read'; INSERT INTO foundation.permission(tenant_id,code,name) VALUES(@t,'companies.write','legacy')",("t",tenant));
            await db.Execute("INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code IN ('companies.create','sites.read','companies.write')",("t",tenant),("r",direct));
            await db.Execute("INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code='companies.read'",("t",tenant),("r",groupRole));
            async Task<string[]> Grants() {using var s=app.Services.CreateScope(); return (await Security.Load(s.ServiceProvider.GetRequiredService<AppDb>(),user.Id))!.Permissions;}
            Assert((await Grants()).SequenceEqual(new[]{"companies.create","companies.read"}),"Fresh grants contain legacy/non-system or miss union.");
            await db.Execute("UPDATE foundation.permission SET is_enabled=false WHERE tenant_id=@t AND code='companies.read'",("t",tenant));
            Assert((await Grants()).SequenceEqual(new[]{"companies.create"}),"Disabled permission still grants.");
            await db.Execute("UPDATE foundation.permission SET is_enabled=true WHERE tenant_id=@t AND code='companies.read'",("t",tenant));
            await db.Execute("UPDATE foundation.user_group SET is_enabled=false WHERE id=@id",("id",group));
            Assert((await Grants()).SequenceEqual(new[]{"companies.create"}),"Disabled group still grants.");
            await db.Execute("UPDATE foundation.role SET is_enabled=false WHERE id=@id",("id",direct));
            Assert((await Grants()).Length==0,"Disabled role still grants.");
            await db.Execute("UPDATE foundation.\"user\" SET is_enabled=false WHERE id=@id",("id",user.Id));
            using(var s=app.Services.CreateScope()) Assert(await Security.Load(s.ServiceProvider.GetRequiredService<AppDb>(),user.Id)==null,"Disabled user loads.");
            await db.Execute("UPDATE foundation.\"user\" SET is_enabled=true WHERE id=@id; UPDATE foundation.tenant SET is_enabled=false WHERE id=@t",("id",user.Id),("t",tenant));
            using(var s=app.Services.CreateScope()) Assert(await Security.Load(s.ServiceProvider.GetRequiredService<AppDb>(),user.Id)==null,"Disabled tenant loads.");
            await db.Execute("UPDATE foundation.tenant SET is_enabled=true WHERE id=@t",("t",tenant));
        });
        Case("HTTP role permission inspection hides legacy and replacement removes it",async () => {
            var role=Guid.NewGuid();
            await db.Execute("INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@id,@t,@code,'test')",("id",role),("t",tenant),("code",role.ToString()));
            await db.Execute("INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code IN ('companies.read','companies.write')",("t",tenant),("r",role));
            var read=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.read'",("t",tenant)))!;
            var legacy=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.write'",("t",tenant)))!;
            var url=$"/api/links/role-permissions/{role}?tenantId={tenant}";
            var result=await client.GetFromJsonAsync<JsonElement>(url);
            Assert(result.GetProperty("ids").EnumerateArray().Select(x => x.GetGuid()).SequenceEqual(new[]{read}),"Legacy permission exposed through GET links.");
            using var rejected=await client.PutAsJsonAsync(url,new {ids=new[]{legacy}});
            Assert(rejected.StatusCode==HttpStatusCode.BadRequest,"Legacy assignment accepted.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r",("r",role)))! == 2,"Invalid replacement changed rows.");
            using var replaced=await client.PutAsJsonAsync(url,new {ids=new[]{read}});
            Assert(replaced.StatusCode==HttpStatusCode.NoContent,"Valid replacement rejected.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r",("r",role)))! == 1,"Replacement retained legacy.");
        });
        Case("HTTP administrative CRUD audit has public before after snapshots",async () => {
            foreach(var resource in new[]{"roles","groups"}) {
                using var created=await client.PostAsJsonAsync($"/api/data/{resource}?tenantId={tenant}",new {code="audit-"+Guid.NewGuid(),name="Prima \"è\""});
                Assert(created.StatusCode==HttpStatusCode.Created,"Create failed.");
                var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
                async Task<JsonElement> Details(string action) {
                    var text=await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action=@action AND resource=@r ORDER BY created_at DESC LIMIT 1",("id",id),("action",action),("r",resource));
                    Assert(text is string,"Missing audit details: "+resource+" "+action); return JsonSerializer.Deserialize<JsonElement>((string)text!);
                }
                var create=await Details("create");
                Assert(create.GetProperty("before").ValueKind==JsonValueKind.Null && create.GetProperty("after").GetProperty("name").GetString()=="Prima \"è\"","Create snapshot wrong.");
                using var updated=await client.PutAsJsonAsync($"/api/data/{resource}/{id}?tenantId={tenant}",new {name="Dopo"});
                Assert(updated.StatusCode==HttpStatusCode.OK,"Update failed.");
                var update=await Details("update");
                Assert(update.GetProperty("before").GetProperty("name").GetString()=="Prima \"è\"" && update.GetProperty("after").GetProperty("name").GetString()=="Dopo","Update snapshots wrong.");
                using var deleted=await client.DeleteAsync($"/api/data/{resource}/{id}?tenantId={tenant}");
                Assert(deleted.StatusCode==HttpStatusCode.NoContent,"Delete failed.");
                var delete=await Details("delete");
                Assert(delete.GetProperty("before").GetProperty("name").GetString()=="Dopo" && delete.GetProperty("after").ValueKind==JsonValueKind.Null,"Delete snapshots wrong.");
                Assert(!delete.GetRawText().Contains("password",StringComparison.OrdinalIgnoreCase),"Credential leaked into audit.");
            }
        });
        Case("HTTP relation audit records replaced sets and tenant seed provenance",async () => {
            var role=(Guid)(await db.Scalar("SELECT id FROM foundation.role WHERE tenant_id=@t LIMIT 1",("t",tenant)))!;
            var before=(long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r",("r",role)))!;
            using var response=await client.PutAsJsonAsync($"/api/links/role-permissions/{role}?tenantId={tenant}",new {ids=Array.Empty<Guid>()});
            Assert(response.StatusCode==HttpStatusCode.NoContent,"Replacement failed.");
            var text=await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action='replace_links' ORDER BY created_at DESC LIMIT 1",("id",role));
            Assert(text is string,"Missing relation details.");
            var details=JsonSerializer.Deserialize<JsonElement>((string)text!);
            Assert(details.GetProperty("beforeIds").GetArrayLength()==before && details.GetProperty("afterIds").GetArrayLength()==0,"Replaced sets wrong.");
            var seed=await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action='create' AND resource='tenants'",("id",tenant));
            Assert(seed is string && JsonSerializer.Deserialize<JsonElement>((string)seed).GetProperty("permissionCatalog").GetArrayLength()==PermissionCatalog.Codes.Length,"Tenant catalog provenance missing.");
        });
        foreach(var action in new[]{"update","delete"}) Case("HTTP audit "+action+" has public details",async () => {
            using var created=await client.PostAsJsonAsync($"/api/data/groups?tenantId={tenant}",new {code="audit-"+Guid.NewGuid(),name="Prima"});
            var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            using var changed=action=="update" ? await client.PutAsJsonAsync($"/api/data/groups/{id}?tenantId={tenant}",new {name="Dopo"}) : await client.DeleteAsync($"/api/data/groups/{id}?tenantId={tenant}");
            Assert(changed.IsSuccessStatusCode,"Mutation failed.");
            Assert(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action=@action",("id",id),("action",action)) is string,"Missing "+action+" audit details.");
        });
        Case("HTTP tenant audit includes catalog seed",async () => {
            var seed=await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@id AND action='create' AND resource='tenants'",("id",tenant));
            Assert(seed is string && JsonSerializer.Deserialize<JsonElement>((string)seed).GetProperty("permissionCatalog").GetArrayLength()==PermissionCatalog.Codes.Length,"Tenant catalog provenance missing.");
        });
        foreach(var mode in new[]{"empty","business","legacy","grant"}) Case("HTTP tenant deletion preserves RESTRICT and catalog rollback: "+mode,async () => {
            using var created=await client.PostAsJsonAsync("/api/data/tenants",new {code="delete-"+Guid.NewGuid(),name="Delete test"});
            var id=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
            if(mode=="business") await db.Execute("INSERT INTO foundation.company(tenant_id,code,name) VALUES(@t,'c','c')",("t",id));
            if(mode=="legacy") await db.Execute("INSERT INTO foundation.permission(tenant_id,code,name) VALUES(@t,'legacy.custom','legacy')",("t",id));
            if(mode=="grant") await db.Execute("WITH r AS (INSERT INTO foundation.role(tenant_id,code,name) VALUES(@t,'r','r') RETURNING id) INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,r.id,p.id FROM r CROSS JOIN foundation.permission p WHERE p.tenant_id=@t AND p.code='companies.read'",("t",id));
            using var deleted=await client.DeleteAsync($"/api/data/tenants/{id}");
            Assert(deleted.StatusCode==(mode=="empty" ? HttpStatusCode.NoContent : HttpStatusCode.Conflict),"Unexpected tenant deletion status: "+deleted.StatusCode);
            var remains=await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@id",("id",id)) is Guid;
            Assert(remains==(mode!="empty"),"Wrong tenant persistence.");
            var count=(long)(await db.Scalar("SELECT count(*) FROM foundation.permission WHERE tenant_id=@t AND is_system",("t",id)))!;
            Assert(count==(mode=="empty" ? 0 : PermissionCatalog.Codes.Length),"Catalog removal not atomic.");
            var audit=(long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@id AND action='delete' AND resource='tenants'",("id",id)))!;
            Assert(audit==(mode=="empty" ? 1 : 0),"Wrong committed deletion audit.");
        });
        Case("HTTP exact fresh grants protect CRUD reset and relation paths",async () => {
            var user=new User {TenantId=tenant,Username="http-exact",FirstName="Test",LastName="Exact",Email="exact@example.test",PasswordHash="fixture",MustChangePassword=false};
            db.Users.Add(user); await db.SaveChangesAsync();
            var role=Guid.NewGuid(); var targetRole=Guid.NewGuid();
            foreach(var r in new[]{role,targetRole}) await db.Execute("INSERT INTO foundation.role(id,tenant_id,code,name) VALUES(@id,@t,@code,'HTTP exact')",("id",r),("t",tenant),("code",r.ToString()));
            await db.Execute("INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r)",("t",tenant),("u",user.Id),("r",role));
            async Task Set(params string[] codes) {
                await db.Execute("DELETE FROM foundation.role_permission WHERE tenant_id=@t AND role_id=@r; INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code=ANY(@codes)",("t",tenant),("r",role),("codes",codes));
            }
            actor=user.Id;
            try {
                await Set("companies.create");
                using var created=await client.PostAsJsonAsync("/api/data/companies",new {code="http-exact",name="HTTP exact"});
                Assert(created.StatusCode==HttpStatusCode.Created,"Create-only actor cannot create.");
                var company=(await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid();
                using var update=await client.PutAsJsonAsync($"/api/data/companies/{company}",new {name="Forbidden"});
                Assert(update.StatusCode==HttpStatusCode.Forbidden,"Create-only actor updated.");
                await Set("users.update");
                using var resetDenied=await client.PutAsJsonAsync($"/api/users/{user.Id}/password",new {newPassword="test-reset-password-long"});
                Assert(resetDenied.StatusCode==HttpStatusCode.Forbidden,"Update grants reset.");
                await Set("users.reset_password");
                using var profileDenied=await client.PutAsJsonAsync($"/api/data/users/{user.Id}",new {first_name="Forbidden"});
                Assert(profileDenied.StatusCode==HttpStatusCode.Forbidden,"Reset grants profile update.");
                using var reset=await client.PutAsJsonAsync($"/api/users/{user.Id}/password",new {newPassword="test-reset-password-long"});
                Assert(reset.StatusCode==HttpStatusCode.NoContent,"Exact reset denied.");
                var hash=(string)(await db.Scalar("SELECT password_hash FROM foundation.\"user\" WHERE id=@id",("id",user.Id)))!;
                Assert(Security.Hasher.VerifyHashedPassword(user,hash,"test-reset-password-long") != Microsoft.AspNetCore.Identity.PasswordVerificationResult.Failed,"Reset not persisted.");
                await Set("users.read");
                using var inspect=await client.GetAsync($"/api/links/user-roles/{user.Id}");
                Assert(inspect.StatusCode==HttpStatusCode.OK,"Read-only actor cannot inspect roles.");
                using var assignDenied=await client.PutAsJsonAsync($"/api/links/user-roles/{user.Id}",new {ids=new[]{targetRole}});
                Assert(assignDenied.StatusCode==HttpStatusCode.Forbidden,"Read grants role assignment.");
                await Set("roles.assign_permissions");
                var permission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.delete'",("t",tenant)))!;
                using var assign=await client.PutAsJsonAsync($"/api/links/role-permissions/{targetRole}",new {ids=new[]{permission}});
                Assert(assign.StatusCode==HttpStatusCode.NoContent,"Unexpected own-permissions restriction.");
                Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r AND permission_id=@p",("r",targetRole),("p",permission)))! == 1,"Assignment not persisted.");
                await Set("companies.write");
                using var legacy=await client.PostAsJsonAsync("/api/data/companies",new {code="legacy-denied",name="Denied"});
                Assert(legacy.StatusCode==HttpStatusCode.Forbidden,"Legacy write became effective.");
            } finally {actor=admin.Id;}
        });
        Case("HTTP catalog mutations denied even global and seed preserves disabled identity",async () => {
            var permission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='companies.read'",("t",tenant)))!;
            foreach(var method in new[]{HttpMethod.Post,HttpMethod.Put,HttpMethod.Delete}) {
                using var request=new HttpRequestMessage(method,$"/api/data/permissions{(method==HttpMethod.Post ? "" : "/"+permission)}?tenantId={tenant}");
                if(method!=HttpMethod.Delete) request.Content=JsonContent.Create(new {code="injection",name="injection"});
                using var response=await client.SendAsync(request);
                Assert(response.StatusCode==HttpStatusCode.Forbidden,"Global mutated catalog via "+method);
            }
            await db.Execute("UPDATE foundation.permission SET is_enabled=false WHERE id=@id",("id",permission));
            await using(var tx=await db.Database.BeginTransactionAsync()) {await Security.Lock(db); await PermissionCatalog.Seed(db,tenant); await tx.CommitAsync();}
            Assert((bool)(await db.Scalar("SELECT NOT is_enabled FROM foundation.permission WHERE id=@id AND tenant_id=@t",("id",permission),("t",tenant)))!,"Seed re-enabled/replaced disabled permission.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.permission WHERE tenant_id=@t AND is_system",("t",tenant)))! == PermissionCatalog.Codes.Length,"Idempotent seed duplicated codes.");
        });
        await CommercialOrganizationTests.Run(client,db,tenant,admin.Id,id => actor=id,test);
        await UnifiedSaveTests.Run(client,db,tenant,admin.Id,id => actor=id,test);
        await app.StopAsync();
    }
}
