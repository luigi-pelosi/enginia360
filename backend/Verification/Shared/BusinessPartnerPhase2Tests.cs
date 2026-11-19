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

namespace Enginia360.Verification.Shared;

// Solo DB isolato: policy reali, identità e ruoli freschi, transazione e lock di richiesta.
// L'autenticazione sintetica non costituisce una prova di cookie o antiforgery.
public static class BusinessPartnerPhase2Tests
{
    public static async Task Run(string connection)
    {
        var builder=WebApplication.CreateBuilder();builder.Logging.ClearProviders();builder.WebHost.UseUrls("http://127.0.0.1:0");
        builder.Services.AddDbContext<AppDb>(o=>o.UseNpgsql(connection));PermissionCatalog.Configure(builder.Services);
        await using var app=builder.Build();using var setup=app.Services.CreateScope();var db=setup.ServiceProvider.GetRequiredService<AppDb>();
        var tenant=Guid.NewGuid();var company=Guid.NewGuid();var service=Guid.NewGuid();var partner=Guid.NewGuid();var tradingRole=Guid.NewGuid();var serviceRole=Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@t,@code,'Phase2')",("t",tenant),("code",tenant.ToString()));
        await db.Execute("INSERT INTO foundation.company(id,tenant_id,name) VALUES(@c,@t,'Trading'),(@s,@t,'Service'); INSERT INTO masterdata.business_partner(id,tenant_id,kind,status,code,legal_name) VALUES(@b,@t,'ORGANIZATION','ACTIVE','BP-1','Shared identity'); INSERT INTO foundation.role(id,tenant_id,name) VALUES(@r,@t,'Read Trading'),(@q,@t,'Update Service')",("t",tenant),("c",company),("s",service),("b",partner),("r",tradingRole),("q",serviceRole));
        var user=new User {TenantId=tenant,Username="phase2-"+Guid.NewGuid(),FirstName="Proof",LastName="User",Email="proof@example.test",PasswordHash="fixture",MustChangePassword=false};
        var global=new User {Username="phase2-global-"+Guid.NewGuid(),FirstName="Proof",LastName="Global",Email="proof@example.test",PasswordHash="fixture",IsSuperAdmin=true,MustChangePassword=false};
        db.Users.AddRange(user,global);await db.SaveChangesAsync();var actor=user.Id;
        app.Use(async(ctx,next)=>{
            try {
                var rd=ctx.RequestServices.GetRequiredService<AppDb>();await using var tx=await rd.Database.BeginTransactionAsync();await Security.Lock(rd);
                ctx.Items["identity"]=(await Security.Load(rd,actor))!;
                var original=ctx.Response.Body;await using var buffer=new MemoryStream();ctx.Response.Body=buffer;
                try {await next();if(ctx.Response.StatusCode<400) await tx.CommitAsync();else await tx.RollbackAsync();ctx.Response.Body=original;buffer.Position=0;await buffer.CopyToAsync(original);}finally {ctx.Response.Body=original;}
            }catch(Exception e){var (status,code)=e switch {ApiException a=>(a.Status,a.Code),PostgresException p when p.SqlState=="23505"=>(409,"conflict"),_=>(500,e.GetType().Name)};ctx.Response.Clear();ctx.Response.StatusCode=status;await ctx.Response.WriteAsJsonAsync(new{code});}
        });
        DataEndpoints.Map(app);await app.StartAsync();using var client=new HttpClient {BaseAddress=new Uri(app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single())};
        var suffix="?tenantId="+tenant;var root=$"/api/companies/{company}/business-partners";var options="/api/business-partner-companies/options"+suffix;
        void Assert(bool valid,string message){if(!valid)throw new Exception(message);}
        async Task Status(HttpResponseMessage response,int expected){Assert((int)response.StatusCode==expected,$"Expected {expected}, got {response.StatusCode}: {await response.Content.ReadAsStringAsync()}");}
        async Task Case(string name,Func<Task> test){await test();Console.WriteLine("PASS phase2 "+name);}
        // La lettura generica delle aziende non concede un ambito operativo aziendale.
        await db.Execute("INSERT INTO foundation.permission(tenant_id,code,name,is_system) VALUES(@t,'companies.read','Generic company read',true); INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code='companies.read'; INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r)",("t",tenant),("r",tradingRole),("u",user.Id));
        await Case("no assigned scope yields no companies even for generic company readers",async()=>{
            using var response=await client.GetAsync(options);await Status(response,200);var body=await response.Content.ReadFromJsonAsync<JsonElement>();Assert(body.GetProperty("items").GetArrayLength()==0,"Unassigned companies leaked");
        });
        await Case("finite scoped permission catalog",()=>{
            foreach(var code in new[]{"roles.assign_companies","business-partner-companies.read","business-partner-companies.create","business-partner-companies.update","business-partner-companies.use_customer","business-partner-companies.use_supplier"})Assert(PermissionCatalog.Contains(code),"Missing finite permission "+code);
            Assert(!PermissionCatalog.Contains("business-partner-companies.delete"),"Delete must not be granted");return Task.CompletedTask;
        });
        await using(var tx=await db.Database.BeginTransactionAsync()){await Security.Lock(db);await PermissionCatalog.Seed(db,tenant);await tx.CommitAsync();}
        await db.Execute("INSERT INTO foundation.user_role(tenant_id,user_id,role_id) VALUES(@t,@u,@r),(@t,@u,@q) ON CONFLICT DO NOTHING; INSERT INTO foundation.role_company(tenant_id,role_id,company_id) VALUES(@t,@r,@c),(@t,@q,@s); INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code IN ('business-partners.read','business-partner-companies.read'); INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@q,id FROM foundation.permission WHERE tenant_id=@t AND code='business-partner-companies.update'",("t",tenant),("u",user.Id),("r",tradingRole),("q",serviceRole),("c",company),("s",service));
        await Case("read Trading and update Service are not a cross product",async()=>{
            var body=await client.GetFromJsonAsync<JsonElement>(options);var items=body.GetProperty("items").EnumerateArray().ToArray();Assert(items.Length==2,"Expected exactly scoped companies");
            Assert(items.Single(x=>x.GetProperty("id").GetGuid()==company).GetProperty("permissions").GetRawText()=="[\"read\"]","Update leaked into Trading");
            Assert(items.Single(x=>x.GetProperty("id").GetGuid()==service).GetProperty("permissions").GetRawText()=="[\"update\"]","Read leaked into Service");
        });
        await Case("company assignment is a separate atomic audited administration endpoint",async()=>{
            var url=$"/api/roles/{tradingRole}/companies"+suffix;
            using(var denied=await client.PutAsJsonAsync(url,new{companyIds=new[]{company,service}}))await Status(denied,403);
            actor=global.Id;
            using(var saved=await client.PutAsJsonAsync(url,new{companyIds=new[]{company,service}}))Assert((int)saved.StatusCode is 200 or 204,"Assignment route missing or failed: "+await saved.Content.ReadAsStringAsync());
            var read=await client.GetFromJsonAsync<JsonElement>(url);Assert(read.GetProperty("companyIds").GetArrayLength()==2,"Assignment replacement lost company");
            using(var invalid=await client.PutAsJsonAsync(url,new{companyIds=new[]{Guid.NewGuid()}}))await Status(invalid,400);
            read=await client.GetFromJsonAsync<JsonElement>(url);Assert(read.GetProperty("companyIds").GetArrayLength()==2,"Invalid assignment partially committed");
            using(var saved=await client.PutAsJsonAsync(url,new{companyIds=new[]{company}}))Assert((int)saved.StatusCode is 200 or 204,"Restore scope failed");
            Assert((long)(await db.Scalar("SELECT count(*) FROM foundation.audit_event WHERE tenant_id=@t AND resource='role-companies' AND record_id=@r",("t",tenant),("r",tradingRole)))! ==2,"Assignment audit missing");actor=user.Id;
        });
        JsonElement relation=default;
        await Case("create independent relation with stable roles and shared identity",async()=>{
            using(var denied=await client.PostAsJsonAsync(root+suffix,new{businessPartnerId=partner,roles=new[]{"CUSTOMER","SUPPLIER"}}))await Status(denied,403);
            actor=global.Id;
            using(var response=await client.PostAsJsonAsync(root+suffix,new{businessPartnerId=partner,roles=new[]{"CUSTOMER","SUPPLIER"}})){await Status(response,201);relation=await response.Content.ReadFromJsonAsync<JsonElement>();}
            Assert(relation.GetProperty("roles").GetArrayLength()==2 && relation.GetProperty("usable_roles").GetArrayLength()==2 && relation.GetProperty("version").GetInt64()==1,"Created relation incorrect");
            using(var duplicate=await client.PostAsJsonAsync(root+suffix,new{businessPartnerId=partner})) {await Status(duplicate,409);Assert((await duplicate.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("code").GetString()=="company_partner_exists","Wrong duplicate code");}
            Assert((long)(await db.Scalar("SELECT version FROM masterdata.business_partner WHERE id=@b",("b",partner)))! ==1,"Commercial change revised core identity");
        });
        await Case("scoped historical reads and exact relation do not leak other companies",async()=>{
            actor=global.Id;
            using(var created=await client.PostAsJsonAsync($"/api/companies/{service}/business-partners"+suffix,new{businessPartnerId=partner,roles=Array.Empty<string>()}))await Status(created,201);
            using(var exact=await client.GetAsync(root+"/"+partner+suffix)){await Status(exact,200);Assert((await exact.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetGuid()==relation.GetProperty("id").GetGuid(),"Wrong exact relation");}
            actor=user.Id;
            using(var denied=await client.GetAsync($"/api/companies/{service}/business-partners"+suffix))await Status(denied,403);
            var rows=await client.GetFromJsonAsync<JsonElement>($"/api/data/business-partners/{partner}/companies"+suffix);
            Assert(rows.GetProperty("items").GetArrayLength()==1 && rows.GetProperty("items")[0].GetProperty("company_id").GetGuid()==company,"Hidden company leaked from BP view");
            var listing=await client.GetFromJsonAsync<JsonElement>(root+suffix+"&role=CUSTOMER&usableOnly=false&search=Shared&page=1&pageSize=1");Assert(listing.GetProperty("total").GetInt64()==1 && listing.GetProperty("items")[0].GetProperty("bp_name").GetString()=="Shared identity","Wrong company list");
            listing=await client.GetFromJsonAsync<JsonElement>(root+suffix+"&role=CUSTOMER&usableOnly=true");Assert(listing.GetProperty("total").GetInt64()==0,"Read-only actor gained use");
            foreach(var query in new[]{"role=PROSPECT","usableOnly=1","page=0","pageSize=101","role=CUSTOMER&role=SUPPLIER"})using(var invalid=await client.GetAsync(root+suffix+"&"+query))await Status(invalid,400);
            actor=global.Id;
        });
        await Case("role blocking preserves stable history and increments only relation revision",async()=>{
            var url=root+"/"+partner+"/roles/CUSTOMER"+suffix;
            actor=user.Id;using(var denied=await client.PutAsJsonAsync(url,new{status="BLOCKED",expectedVersion=1}))await Status(denied,403);actor=global.Id;
            using(var updated=await client.PutAsJsonAsync(url,new{status="BLOCKED",expectedVersion=1})){await Status(updated,200);var after=await updated.Content.ReadFromJsonAsync<JsonElement>();Assert(after.GetProperty("version").GetInt64()==2 && after.GetProperty("usable_roles").GetRawText()=="[\"SUPPLIER\"]","Customer block affected supplier or revision");Assert(after.GetProperty("roles")[0].GetProperty("id").GetGuid()==relation.GetProperty("roles")[0].GetProperty("id").GetGuid(),"Role ID replaced");relation=after;}
            using(var stale=await client.PutAsJsonAsync(url,new{status="ACTIVE",expectedVersion=1}))await Status(stale,409);
            using(var bad=await client.PutAsJsonAsync(root+"/"+partner+"/roles/PROSPECT"+suffix,new{status="ACTIVE",expectedVersion=2}))await Status(bad,400);
            using(var patched=await client.PatchAsJsonAsync(root+"/"+partner+suffix,new{status="BLOCKED",expectedVersion=2})){await Status(patched,200);relation=await patched.Content.ReadFromJsonAsync<JsonElement>();Assert(relation.GetProperty("usable_roles").GetArrayLength()==0 && relation.GetProperty("version").GetInt64()==3,"Blocked relation still usable");}
            Assert((long)(await db.Scalar("SELECT version FROM masterdata.business_partner WHERE id=@b",("b",partner)))! ==1,"Relationship update changed BP revision");
        });
        await Case("insert then reactivate role on independent relationship preserves ID and created_at",async()=>{
            var url=$"/api/companies/{service}/business-partners/{partner}/roles/SUPPLIER"+suffix;
            using var first=await client.PutAsJsonAsync(url,new{status="BLOCKED",expectedVersion=1});await Status(first,200);var before=await first.Content.ReadFromJsonAsync<JsonElement>();
            using var second=await client.PutAsJsonAsync(url,new{status="ACTIVE",expectedVersion=2});await Status(second,200);var after=await second.Content.ReadFromJsonAsync<JsonElement>();
            Assert(before.GetProperty("roles")[0].GetProperty("id").GetGuid()==after.GetProperty("roles")[0].GetProperty("id").GetGuid() && before.GetProperty("roles")[0].GetProperty("created_at").GetString()==after.GetProperty("roles")[0].GetProperty("created_at").GetString(),"Historical role identity replaced");
        });
        await Case("eligibility endpoint separates exact use authority from business state",async()=>{
            var url=$"/api/companies/{service}/business-partners/{partner}/eligibility/SUPPLIER"+suffix;
            actor=user.Id;using(var denied=await client.GetAsync(url))await Status(denied,403);actor=global.Id;
            using(var eligible=await client.GetAsync(url)){await Status(eligible,200);Assert((await eligible.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("usable").GetBoolean(),"Active supplier in active company unusable");}
            await db.Execute("UPDATE foundation.company SET is_enabled=false WHERE id=@id",("id",service));
            var disabled=await client.GetFromJsonAsync<JsonElement>(url);Assert(!disabled.GetProperty("usable").GetBoolean(),"Disabled company usable");
            await db.Execute("UPDATE foundation.company SET is_enabled=true WHERE id=@id",("id",service));
            using var missing=await client.GetAsync($"/api/companies/{service}/business-partners/{Guid.NewGuid()}/eligibility/SUPPLIER"+suffix);await Status(missing,200);Assert(!(await missing.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("usable").GetBoolean(),"Missing relation usable");
        });
        await Case("group-bound grants are fresh and group disable revokes update without losing direct read",async()=>{
            var group=Guid.NewGuid();var role=Guid.NewGuid();
            await db.Execute("INSERT INTO foundation.user_group(id,tenant_id,name) VALUES(@g,@t,'Scoped proof'); INSERT INTO foundation.role(id,tenant_id,name) VALUES(@r,@t,'Group Trading'); INSERT INTO foundation.role_company(tenant_id,role_id,company_id) VALUES(@t,@r,@c); INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) SELECT @t,@r,id FROM foundation.permission WHERE tenant_id=@t AND code IN ('business-partner-companies.update','business-partner-companies.use_supplier'); INSERT INTO foundation.user_group_member(tenant_id,user_group_id,user_id) VALUES(@t,@g,@u); INSERT INTO foundation.user_group_role(tenant_id,user_group_id,role_id) VALUES(@t,@g,@r)",("g",group),("r",role),("c",company),("t",tenant),("u",user.Id));
            actor=user.Id;var url=root+"/"+partner+suffix;
            using(var changed=await client.PatchAsJsonAsync(url,new{status="ACTIVE",expectedVersion=3}))await Status(changed,200);
            var active=await client.GetFromJsonAsync<JsonElement>(url);Assert(active.GetProperty("usable_roles").GetRawText()=="[\"SUPPLIER\"]","Group use permission missing or customer leaked");
            await db.Execute("UPDATE foundation.user_group SET is_enabled=false WHERE id=@g",("g",group));
            using(var denied=await client.PatchAsJsonAsync(url,new{status="BLOCKED",expectedVersion=4}))await Status(denied,403);
            var read=await client.GetFromJsonAsync<JsonElement>(url);Assert(read.GetProperty("usable_roles").GetArrayLength()==0 && read.GetProperty("version").GetInt64()==4,"Group revoke stale or direct read lost");
            await db.Execute("UPDATE foundation.user_group SET is_enabled=true WHERE id=@g; DELETE FROM foundation.user_group_role WHERE role_id=@r",("g",group),("r",role));
            using(var denied=await client.PatchAsJsonAsync(url,new{status="BLOCKED",expectedVersion=4}))await Status(denied,403);actor=global.Id;
        });
        await Case("concurrent role updates share one relation revision",async()=>{
            var url=root+"/"+partner;
            var responses=await Task.WhenAll(client.PutAsJsonAsync(url+"/roles/CUSTOMER"+suffix,new{status="ACTIVE",expectedVersion=4}),client.PutAsJsonAsync(url+"/roles/SUPPLIER"+suffix,new{status="BLOCKED",expectedVersion=4}));
            try {Assert(responses.Select(x=>(int)x.StatusCode).Order().SequenceEqual(new[]{200,409}),"Concurrent commands did not arbitrate revision");}finally{foreach(var response in responses)response.Dispose();}
            relation=await client.GetFromJsonAsync<JsonElement>(url+suffix);Assert(relation.GetProperty("version").GetInt64()==5,"Concurrent commands incremented twice");
        });
        foreach(var deferred in new[]{false,true})await Case((deferred ? "deferred" : "immediate")+" audit refusal rolls back relation role and company assignment",async()=>{
            var function="phase2_audit_"+Guid.NewGuid().ToString("N");var url=root+"/"+partner;
            var before=await client.GetStringAsync(url+suffix);var scope=$"/api/roles/{tradingRole}/companies"+suffix;var beforeScope=await client.GetStringAsync(scope);
            await db.Execute($"CREATE FUNCTION foundation.{function}() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN RAISE EXCEPTION ''Fixture refusal''; END'; CREATE {(deferred ? "CONSTRAINT " : "")}TRIGGER {function} {(deferred ? "AFTER" : "BEFORE")} INSERT ON foundation.audit_event {(deferred ? "DEFERRABLE INITIALLY DEFERRED" : "")} FOR EACH ROW WHEN (NEW.tenant_id='{tenant}'::uuid) EXECUTE FUNCTION foundation.{function}()");
            try {
                using(var refused=await client.PutAsJsonAsync(url+"/roles/SUPPLIER"+suffix,new{status="BLOCKED",expectedVersion=5}))await Status(refused,500);
                Assert(before==await client.GetStringAsync(url+suffix),"Audit failure committed relationship/role");
                using(var refused=await client.PutAsJsonAsync(scope,new{companyIds=new[]{service}}))await Status(refused,500);
                Assert(beforeScope==await client.GetStringAsync(scope),"Audit failure committed role-company scope");
            }finally {await db.Execute($"DROP TRIGGER {function} ON foundation.audit_event; DROP FUNCTION foundation.{function}()");}
        });
        Console.WriteLine("PASS phase2 executed catalog count="+PermissionCatalog.Codes.Length);
        await app.StopAsync();
    }
}
