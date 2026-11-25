using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Enginia360.Verification.AccessControl;

// Only run against a disposable database clone. Never a production/live connection.
public static class RoleUnifiedSaveRuntimeTests
{
    public static void Run(string connection,Action<string,Action> test)
    {
        if(Environment.GetEnvironmentVariable("ENGINIA360_ROLE_UNIFIED_ISOLATED")!="1")
            throw new InvalidOperationException("Explicit disposable-database opt-in required.");
        RunAsync(connection,test).GetAwaiter().GetResult();
    }
    private static async Task RunAsync(string connection,Action<string,Action> test)
    {
        var builder=WebApplication.CreateBuilder(); builder.Logging.ClearProviders();
        builder.WebHost.UseUrls("http://127.0.0.1:0");
        builder.Services.AddDbContext<AppDb>(o=>o.UseNpgsql(connection)); PermissionCatalog.Configure(builder.Services);
        await using var app=builder.Build();
        using var setup=app.Services.CreateScope(); var db=setup.ServiceProvider.GetRequiredService<AppDb>();
        var admin=new User {Username="role-unified-"+Guid.NewGuid(),FirstName="Role",LastName="Admin",Email="admin@example.test",IsSuperAdmin=true,PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(admin); await db.SaveChangesAsync(); var actor=admin.Id;
        app.Use(async(ctx,next)=> {
            var rd=ctx.RequestServices.GetRequiredService<AppDb>(); await using var tx=await rd.Database.BeginTransactionAsync();
            await Security.Lock(rd); ctx.Items["identity"]=(await Security.Load(rd,actor))!;
            var original=ctx.Response.Body; await using var buffer=new MemoryStream(); ctx.Response.Body=buffer;
            try {
                await next(); if(ctx.Response.StatusCode<400) await tx.CommitAsync(); else await tx.RollbackAsync();
                ctx.Response.Body=original; buffer.Position=0; await buffer.CopyToAsync(original);
            } catch(Exception ex) {
                if(rd.Database.GetDbConnection().State==System.Data.ConnectionState.Open)
                    try {await tx.RollbackAsync();} catch(InvalidOperationException) { }
                ctx.Response.Body=original; ctx.Response.Clear();
                ctx.Response.StatusCode=ex switch {ApiException e=>e.Status,PostgresException p when p.SqlState=="23514"=>400,_=>500};
                await ctx.Response.WriteAsJsonAsync(new{code="fixture_refusal"});
            } finally {ctx.Response.Body=original;}
        });
        DataEndpoints.Map(app); await app.StartAsync();
        using var client=new HttpClient {BaseAddress=new Uri(app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single())};
        void Assert(bool value,string message) {if(!value) throw new Exception(message);}
        void Case(string name,Func<Task> run)=>test("role unified runtime: "+name,()=>run().GetAwaiter().GetResult());
        var tenant=Guid.NewGuid(); var foreign=Guid.NewGuid(); var company=Guid.NewGuid(); var company2=Guid.NewGuid(); var foreignCompany=Guid.NewGuid(); var foreignRole=Guid.NewGuid();
        await db.Execute("""
            INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Unified role'),(@f,@foreignCode,'Foreign unified role');
            INSERT INTO foundation.company(id,tenant_id,name) VALUES(@c,@t,'First'),(@c2,@t,'Second'),(@fc,@f,'Foreign');
            INSERT INTO foundation.role(id,tenant_id,name) VALUES(@fr,@f,'Foreign role')
            """,("t",tenant),("f",foreign),("code",tenant.ToString()),("foreignCode",foreign.ToString()),("c",company),("c2",company2),("fc",foreignCompany),("fr",foreignRole));
        await using(var tx=await db.Database.BeginTransactionAsync()) {await Security.Lock(db); await PermissionCatalog.Seed(db,tenant); await PermissionCatalog.Seed(db,foreign); await tx.CommitAsync();}
        var permission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='roles.assign_companies'",("t",tenant)))!;
        var foreignPermission=(Guid)(await db.Scalar("SELECT id FROM foundation.permission WHERE tenant_id=@t AND code='roles.read'",("t",foreign)))!;
        var user=new User {TenantId=tenant,Username="role-unified-member-"+Guid.NewGuid(),FirstName="Role",LastName="Member",Email="member@example.test",PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(user); await db.SaveChangesAsync();
        var authority=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.role(id,tenant_id,name) VALUES(@r,@t,'Authority'); INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r)",("r",authority),("t",tenant),("u",user.Id));
        async Task Grants(params string[] codes)=>await db.Execute("DELETE FROM foundation.role_permission WHERE role_id=@r; INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code=ANY(@codes)",("r",authority),("t",tenant),("codes",codes));
        string Url(Guid? id=null)=>id.HasValue ? $"/api/data/roles/{id}/save?tenantId={tenant}" : $"/api/data/roles/save?tenantId={tenant}";
        object Payload(string name,Guid[] companies,Guid[]? permissions=null)=>new {values=new{name},links=new Dictionary<string,Guid[]> {["role-permissions"]=permissions??[permission]},companyIds=companies};
        async Task<JsonElement> Send(HttpMethod method,string url,object payload,HttpStatusCode expected)
        {
            using var request=new HttpRequestMessage(method,url) {Content=payload is string raw ? new StringContent(raw,System.Text.Encoding.UTF8,"application/json") : JsonContent.Create(payload)};
            using var response=await client.SendAsync(request); var text=await response.Content.ReadAsStringAsync();
            Assert(response.StatusCode==expected,$"Expected {expected}, actual {response.StatusCode}: {text}");
            return JsonSerializer.Deserialize<JsonElement>(text);
        }
        async Task<string> Snapshot()=>(string)(await db.Scalar("""
            SELECT jsonb_build_object(
              'roles',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM foundation.role x WHERE tenant_id=ANY(@ts)),
              'grants',(SELECT jsonb_agg(to_jsonb(x) ORDER BY role_id,permission_id) FROM foundation.role_permission x WHERE tenant_id=ANY(@ts)),
              'companies',(SELECT jsonb_agg(to_jsonb(x) ORDER BY role_id,company_id) FROM foundation.role_company x WHERE tenant_id=ANY(@ts)),
              'audit',(SELECT jsonb_agg(to_jsonb(x) ORDER BY id) FROM foundation.audit_event x WHERE tenant_id=ANY(@ts)))::text
            """,("ts",new[]{tenant,foreign})))!;
        async Task Refuse(HttpMethod method,string url,object payload,HttpStatusCode expected)
        {
            var before=await Snapshot(); await Send(method,url,payload,expected);
            Assert(before==await Snapshot(),"Refused command changed role, grants, companies or audits.");
        }
        async Task CheckCompanies(Guid role,params Guid[] ids)=>Assert((await RoleCompanyEndpoints.Read(db,tenant,role)).SequenceEqual(ids.Order()),"Company replacement mismatch.");
        Guid role=Guid.Empty;
        Case("create commits role permission companies and separate audits in one transaction",async()=> {
            var body=await Send(HttpMethod.Post,Url(),Payload("Created",[company]),HttpStatusCode.Created); role=body.GetProperty("id").GetGuid();
            Assert(body.GetProperty("name").GetString()=="Created" && body.TryGetProperty("is_enabled",out _),"Standard record missing.");
            await CheckCompanies(role,company);
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.role_permission WHERE role_id=@r AND permission_id=@p",("r",role),("p",permission)))! == 1,"Permission missing.");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE record_id=@r",("r",role)))! == 3,"Expected three distinct audits.");
            Assert((long)(await db.Scalar("SELECT count(DISTINCT xid) FROM (SELECT xmin::text xid FROM foundation.role WHERE id=@r UNION ALL SELECT xmin::text FROM foundation.role_permission WHERE role_id=@r UNION ALL SELECT xmin::text FROM foundation.role_company WHERE role_id=@r UNION ALL SELECT xmin::text FROM foundation.audit_event WHERE record_id=@r) x",("r",role)))! == 1,"Mutations not atomic.");
            var detail=JsonSerializer.Deserialize<JsonElement>((string)(await db.Scalar("SELECT details::text FROM foundation.audit_event WHERE record_id=@r AND resource='role-companies'",("r",role)))!);
            Assert(detail.GetProperty("beforeIds").GetArrayLength()==0 && detail.GetProperty("afterIds")[0].GetGuid()==company,"Company audit snapshots wrong.");
        });
        Case("update returns standard record and omission preserves company links",async()=> {
            var body=await Send(HttpMethod.Put,Url(role),Payload("Updated",[company2],[]),HttpStatusCode.OK);
            Assert(body.GetProperty("name").GetString()=="Updated","Full update response wrong."); await CheckCompanies(role,company2);
            await Send(HttpMethod.Put,Url(role),new {values=new {description="Omitted companies"}},HttpStatusCode.OK); await CheckCompanies(role,company2);
            var linksOnly=await Send(HttpMethod.Put,Url(role),new {links=new Dictionary<string,Guid[]> {["role-permissions"]=[]}},HttpStatusCode.OK);
            Assert(linksOnly.EnumerateObject().Count()==1 && linksOnly.GetProperty("id").GetGuid()==role,"Links-only exposes fields."); await CheckCompanies(role,company2);
        });
        Case("company-only exact authority returns only id without roles.update",async()=> {
            await Grants("roles.assign_companies"); actor=user.Id;
            try {
                var body=await Send(HttpMethod.Put,Url(role),new {companyIds=new[]{company}},HttpStatusCode.OK);
                Assert(body.EnumerateObject().Count()==1 && body.GetProperty("id").GetGuid()==role,"Companies-only exposes fields.");
                await CheckCompanies(role,company);
                await Refuse(HttpMethod.Put,Url(role),Payload("Forbidden",[company]),HttpStatusCode.Forbidden);
                await Refuse(HttpMethod.Put,Url(role),new {links=new Dictionary<string,Guid[]> {["role-permissions"]=[]},companyIds=Array.Empty<Guid>()},HttpStatusCode.Forbidden);
                await Send(HttpMethod.Put,Url(role),new {companyIds=Array.Empty<Guid>()},HttpStatusCode.OK); await CheckCompanies(role);
            } finally {actor=admin.Id;}
        });
        Case("assign-permissions cannot bootstrap company authority in the same save",async()=> {
            await Grants("roles.assign_permissions"); actor=user.Id;
            try {await Refuse(HttpMethod.Put,Url(authority),new {links=new Dictionary<string,Guid[]> {["role-permissions"]=new[]{permission}},companyIds=new[]{company}},HttpStatusCode.Forbidden);}
            finally {actor=admin.Id;}
        });
        Case("known tenant role required even for empty links-only and companies-only",async()=> {
            foreach(var target in new[]{Guid.NewGuid(),foreignRole}) {
                await Refuse(HttpMethod.Put,Url(target),new {companyIds=Array.Empty<Guid>()},HttpStatusCode.NotFound);
                await Refuse(HttpMethod.Put,Url(target),new {links=new Dictionary<string,Guid[]> {["role-permissions"]=[]}},HttpStatusCode.NotFound);
            }
        });
        Case("company target validation and all gates precede any DML",async()=> {
            await db.Execute("""
                CREATE SEQUENCE foundation.role_unified_write_probe;
                CREATE FUNCTION foundation.role_unified_write_probe() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM nextval('foundation.role_unified_write_probe'); RETURN NEW; END $$;
                CREATE TRIGGER role_unified_write_probe BEFORE INSERT OR UPDATE ON foundation.role FOR EACH ROW EXECUTE FUNCTION foundation.role_unified_write_probe();
                CREATE TRIGGER role_unified_write_probe BEFORE INSERT OR DELETE ON foundation.role_permission FOR EACH ROW EXECUTE FUNCTION foundation.role_unified_write_probe()
                """);
            try {
                foreach(var create in new[]{true,false}) {
                    foreach(var target in new[]{Guid.NewGuid(),foreignCompany}) await Refuse(create ? HttpMethod.Post : HttpMethod.Put,Url(create ? null : role),Payload("Invalid company",[target]),HttpStatusCode.BadRequest);
                    await Refuse(create ? HttpMethod.Post : HttpMethod.Put,Url(create ? null : role),Payload("Foreign permission",[company],[foreignPermission]),HttpStatusCode.BadRequest);
                }
                foreach(var create in new[]{true,false}) foreach(var missing in new[]{create ? "roles.create" : "roles.update","roles.assign_permissions","roles.assign_companies"}) {
                    // Disable the probe only for fixture authority changes, then re-enable it for the command.
                    await db.Execute("ALTER TABLE foundation.role_permission DISABLE TRIGGER role_unified_write_probe");
                    try {await Grants(new[]{create ? "roles.create" : "roles.update","roles.assign_permissions","roles.assign_companies"}.Where(x=>x!=missing).ToArray());}
                    finally {await db.Execute("ALTER TABLE foundation.role_permission ENABLE TRIGGER role_unified_write_probe");}
                    actor=user.Id;
                    try {await Refuse(create ? HttpMethod.Post : HttpMethod.Put,Url(create ? null : role),Payload("Missing gate",[company]),HttpStatusCode.Forbidden);}
                    finally {actor=admin.Id;}
                }
                Assert(!(bool)(await db.Scalar("SELECT is_called FROM foundation.role_unified_write_probe"))!,"A gate or tenant target was validated after DML.");
            } finally {await db.Execute("DROP TRIGGER role_unified_write_probe ON foundation.role; DROP TRIGGER role_unified_write_probe ON foundation.role_permission; DROP FUNCTION foundation.role_unified_write_probe(); DROP SEQUENCE foundation.role_unified_write_probe");}
        });
        foreach(var deferred in new[]{false,true}) Case(deferred ? "late deferred company audit failure rolls back create and update at commit" : "last company audit failure rolls back create and update",async()=> {
            await db.Execute("""
                CREATE FUNCTION foundation.role_unified_audit_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.resource='role-companies' THEN RAISE EXCEPTION 'fixture audit fault' USING ERRCODE='23514'; END IF; RETURN NEW; END $$
                """.Replace("23514",deferred ? "P0001" : "23514",StringComparison.Ordinal));
            try {
                await db.Execute(deferred ? "CREATE CONSTRAINT TRIGGER role_unified_audit_fault AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.role_unified_audit_fault()" : "CREATE TRIGGER role_unified_audit_fault BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.role_unified_audit_fault()");
                foreach(var create in new[]{true,false}) await Refuse(create ? HttpMethod.Post : HttpMethod.Put,Url(create ? null : role),Payload("Audit must rollback",[company2]),deferred ? HttpStatusCode.InternalServerError : HttpStatusCode.BadRequest);
            } finally {await db.Execute("DROP TRIGGER role_unified_audit_fault ON foundation.audit_event; DROP FUNCTION foundation.role_unified_audit_fault()");}
        });
        Case("legacy PUT response audit and preserved assignment timestamps remain compatible",async()=> {
            var url=$"/api/roles/{role}/companies?tenantId={tenant}";
            var body=await Send(HttpMethod.Put,url,new {companyIds=new[]{company}},HttpStatusCode.OK);
            Assert(body.EnumerateObject().Count()==1 && body.GetProperty("companyIds")[0].GetGuid()==company,"Legacy response changed.");
            var created=await db.Scalar("SELECT created_at FROM foundation.role_company WHERE role_id=@r AND company_id=@c",("r",role),("c",company));
            await Send(HttpMethod.Put,Url(role),new {companyIds=new[]{company}},HttpStatusCode.OK);
            Assert(Equals(created,await db.Scalar("SELECT created_at FROM foundation.role_company WHERE role_id=@r AND company_id=@c",("r",role),("c",company))),"Unchanged assignment timestamp rewritten.");
            await Refuse(HttpMethod.Put,url,new {companyIds=new[]{foreignCompany}},HttpStatusCode.BadRequest);
        });
        Case("1000 companies accepted in unified and compatibility routes; 1001 rejected",async()=> {
            var ids=Enumerable.Range(0,1000).Select(_=>Guid.NewGuid()).ToArray();
            await db.Execute("INSERT INTO foundation.company(id,tenant_id,name) SELECT id,@t,'Limit' FROM unnest(@ids::uuid[]) id",("t",tenant),("ids",ids));
            foreach(var url in new[]{Url(role),$"/api/roles/{role}/companies?tenantId={tenant}"}) {
                await Send(HttpMethod.Put,url,new {companyIds=ids},HttpStatusCode.OK); await CheckCompanies(role,ids);
                await Refuse(HttpMethod.Put,url,new {companyIds=ids.Append(company).ToArray()},HttpStatusCode.BadRequest);
            }
        });
        Case("malformed arrays duplicate properties unknown fields and resource mismatch reject unchanged",async()=> {
            foreach(var raw in new[]{"{\"companyIds\":null}","{\"companyIds\":[],\"companyIds\":[]}","{\"companyIds\":[null]}","{\"companyIds\":[42]}","{\"companyIds\":[\"bad\"]}",JsonSerializer.Serialize(new {companyIds=new[]{company,company}}),"{\"companyIds\":[],\"unknown\":[]}","{\"values\":{},\"companyIds\":[]}"}) await Refuse(HttpMethod.Put,Url(role),raw,HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Post,Url(),new {companyIds=Array.Empty<Guid>()},HttpStatusCode.BadRequest);
            await Refuse(HttpMethod.Put,$"/api/data/groups/{role}/save?tenantId={tenant}",new {companyIds=Array.Empty<Guid>()},HttpStatusCode.BadRequest);
        });
        await app.StopAsync();
    }
}
