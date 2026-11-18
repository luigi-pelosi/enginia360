using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Reflection;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.Extensions.Options;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Verification.Identity;

public static class LoginPreselectionSelfTests
{
    public static void Run(IServiceProvider services, Action<string,Action> test)
    {
        static void Assert(bool value,string message) { if(!value) throw new Exception(message); }
        static JsonElement Session(IdentityState state) => JsonSerializer.SerializeToElement(state.Session);
        if(Environment.GetEnvironmentVariable("LOGIN_PRESELECTION_DB_TESTS")=="true")
            test("login selection: fresh database validation revokes preference independently of identity",() => DatabaseRegression(services).GetAwaiter().GetResult());
        test("login selection: session exposes nullable preference separate from identity",() => {
            var global=new IdentityState(new User {IsSuperAdmin=true},"root","Root",[]);
            var session=Session(global);
            Assert(session.TryGetProperty("selectedTenantId",out var selected) && selected.ValueKind==JsonValueKind.Null,"Session must expose selectedTenantId:null for legacy/no-selection login");
            var property=typeof(IdentityState).GetProperty("SelectedTenantId");
            Assert(property != null,"Separate initial selection state missing");
            var tenant=Guid.NewGuid(); property!.SetValue(global,tenant);
            session=Session(global);
            Assert(session.GetProperty("selectedTenantId").GetGuid()==tenant && session.GetProperty("tenantId").ValueKind==JsonValueKind.Null && session.GetProperty("isSuperAdmin").GetBoolean(),"Selection changed global identity");
            var ctx=new DefaultHttpContext();
            try {global.Tenant(ctx,"companies"); throw new Exception("Selection supplied implicit authority/scope");} catch(ApiException e) when(e.Status==400) { }
            var other=Guid.NewGuid(); ctx.Request.QueryString=new QueryString("?tenantId="+other);
            Assert(global.Tenant(ctx,"companies")==other,"Selection must not restrict manual organization change");
            var ordinary=new IdentityState(new User {TenantId=tenant},"local","Local",[]); property.SetValue(ordinary,Guid.NewGuid());
            Assert(Session(ordinary).GetProperty("selectedTenantId").ValueKind==JsonValueKind.Null,"Ordinary session must ignore selected preference");
        });
        test("login selection: real protected cookie carries preference not role or tenant identity",() => {
            var issue=typeof(Security).GetMethods().SingleOrDefault(m=>m.Name=="Issue" && m.GetParameters().Length==3);
            Assert(issue != null,"Issue must accept separate selectedTenantId");
            using var scope=services.CreateScope();
            var options=scope.ServiceProvider.GetRequiredService<IOptionsMonitor<CookieAuthenticationOptions>>().Get(CookieAuthenticationDefaults.AuthenticationScheme);
            var tenant=Guid.NewGuid();
            AuthenticationTicket Ticket(User user,Guid? selected) {
                using var requestScope=services.CreateScope();
                var ctx=new DefaultHttpContext {RequestServices=requestScope.ServiceProvider}; ctx.Request.Scheme="https";
                ((Task)issue!.Invoke(null,[ctx,user,selected])!).GetAwaiter().GetResult();
                var header=ctx.Response.Headers.SetCookie.Single(h=>h!.StartsWith("enginia360.session="))!;
                var encoded=header.Split(';')[0].Split('=',2)[1];
                return options.TicketDataFormat.Unprotect(Uri.UnescapeDataString(encoded)) ?? throw new Exception("Real protected cookie unreadable");
            }
            var global=new User {IsSuperAdmin=true}; var ticket=Ticket(global,tenant);
            Assert(ticket.Principal.FindFirst("selected_tenant_id")?.Value==tenant.ToString(),"Protected preference claim missing");
            Assert(ticket.Principal.Claims.Count()==3,"Cookie must contain identity, stamp and preference only");
            Assert(ticket.Principal.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value==global.Id.ToString(),"Cookie identity changed");
            Assert(Ticket(global,null).Principal.FindFirst("selected_tenant_id")==null,"New login without code must not reuse old preference");
            Assert(Ticket(new User {TenantId=tenant},tenant).Principal.FindFirst("selected_tenant_id")==null,"Tenant user must not issue preference claim");
            Assert(Ticket(new User {TenantId=tenant,IsSuperAdmin=true},tenant).Principal.FindFirst("selected_tenant_id")==null,"Invalid global identity must not issue preference claim");
        });
    }
    private static async Task DatabaseRegression(IServiceProvider services)
    {
        static void Assert(bool value,string message) { if(!value) throw new Exception(message); }
        using var scope=services.CreateScope();
        var db=scope.ServiceProvider.GetRequiredService<AppDb>();
        await using var tx=await db.Database.BeginTransactionAsync();
        // Le scritture sintetiche sono annullate senza modificare utenze esistenti.
        var tenant=Guid.NewGuid(); var username="selection-"+Guid.NewGuid();
        await db.Execute("INSERT INTO foundation.tenant(id,code,name) VALUES(@id,@code,'Selection regression')",("id",tenant),("code",username));
        var root=new User {Username=username,FirstName="Selection",LastName="Regression",Email="selection@example.test",IsSuperAdmin=true,PasswordHash="fixture",MustChangePassword=false};
        db.Users.Add(root); await db.SaveChangesAsync();
        async Task<IdentityState?> Load(Guid? selected) { db.ChangeTracker.Clear(); return await Security.Load(db,root.Id,root.SecurityStamp.ToString(),selected); }
        var fresh=await Load(tenant);
        Assert(fresh?.SelectedTenantId==tenant && fresh.User.TenantId==null && fresh.User.IsSuperAdmin,"Active initial preference not restored separately");
        Assert((await Load(null))?.SelectedTenantId==null,"Legacy cookie must remain valid without preference");
        Assert((await Load(Guid.NewGuid()))?.SelectedTenantId==null,"Nonexistent preference must be cleared");
        await db.Execute("UPDATE foundation.tenant SET is_enabled=false WHERE id=@id",("id",tenant));
        fresh=await Load(tenant);
        Assert(fresh != null && fresh.User.IsSuperAdmin && fresh.User.TenantId==null && fresh.SelectedTenantId==null,"Disabled preference must not revoke global identity");
        await db.Execute("UPDATE foundation.tenant SET is_enabled=true WHERE id=@id",("id",tenant));
        await db.Execute("UPDATE foundation.\"user\" SET is_enabled=false WHERE id=@id",("id",root.Id));
        Assert(await Load(tenant)==null,"Disabled global identity accepted");
        await db.Execute("UPDATE foundation.\"user\" SET is_enabled=true,is_super_admin=false,tenant_id=@tenant WHERE id=@id",("id",root.Id),("tenant",tenant));
        fresh=await Load(tenant);
        Assert(fresh != null && !fresh.User.IsSuperAdmin && fresh.User.TenantId==tenant && fresh.SelectedTenantId==null,"Preference survived loss of global identity");
        Assert(await Security.Load(db,root.Id,Guid.NewGuid().ToString(),tenant)==null,"Stale security stamp accepted");
        await tx.RollbackAsync();
    }
}
