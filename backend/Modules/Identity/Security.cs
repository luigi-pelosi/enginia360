using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Modules.Identity;

public sealed record IdentityState(User User, string Username, string DisplayName, string[] Permissions)
{
    public Guid? SelectedTenantId { get; init; }
    public object Session => new { id = User.Id, username = Username, displayName = User.FullName, preferredLanguage = User.PreferredLanguage,
        isSuperAdmin = User.IsSuperAdmin, tenantId = User.TenantId,
        selectedTenantId = User.IsSuperAdmin && User.TenantId == null ? SelectedTenantId : null,
        mustChangePassword = User.MustChangePassword, permissions = Permissions };
    public void Authorize(string resource, string operation)
    {
        Check.Require(resource == "tenants" ? User.IsEnabled && User.IsSuperAdmin && User.TenantId == null && operation is "read" or "create" or "update" or "delete"
            : ResourceCatalog.IsGlobalMaster(resource) && operation != "read"
                ? User.IsEnabled && User.IsSuperAdmin && User.TenantId == null && operation is "create" or "update" or "delete"
            : PermissionCatalog.Grants(this,resource+"."+operation),403,"forbidden");
    }
    public Guid? Tenant(HttpContext ctx, string resource)
    {
        if (ResourceCatalog.IsGlobalMaster(resource)) return null;
        if (resource == "tenants") { Authorize(resource,"read"); return null; }
        var input = ctx.Request.Query["tenantId"].ToString();
        Guid? requested = null;
        if (input.Length > 0) { Check.Require(Guid.TryParse(input,out var parsed) && parsed != Guid.Empty); requested = parsed; }
        if (User.IsSuperAdmin && User.TenantId == null) { Check.Require(requested != null); return requested; }
        Check.Require(requested == null || requested == User.TenantId,403,"forbidden");
        return User.TenantId;
    }
}

public static class Security
{
    public const string SelectedTenantClaim = "selected_tenant_id";
    public const long LockKey = 3607902026;
    public static readonly PasswordHasher<User> Hasher = new(Microsoft.Extensions.Options.Options.Create(new PasswordHasherOptions { IterationCount = 210000 }));
    public static async Task<IdentityState?> Load(AppDb db, Guid id, string? stamp = null, Guid? selectedTenantId = null)
    {
        var a = await db.Users.SingleOrDefaultAsync(x => x.Id == id);
        if (a == null || a.PasswordHash == null || !a.IsEnabled || stamp != null && a.SecurityStamp.ToString() != stamp) return null;
        if (a.TenantId == null)
        {
            if (!a.IsSuperAdmin) return null;
            // Preselezione iniziale della UI, non identità, autorizzazione o filtro implicito.
            var selected = selectedTenantId != null && await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@tenant AND is_enabled",("tenant",selectedTenantId)) is Guid
                ? selectedTenantId : null;
            return new(a,a.Username,a.FullName,[]) { SelectedTenantId=selected };
        }
        if (a.IsSuperAdmin || await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@tenant AND is_enabled",("tenant",a.TenantId)) is not Guid) return null;
        const string sql = """
            SELECT DISTINCT p.code FROM foundation.permission p
            JOIN foundation.role_permission rp ON rp.tenant_id=p.tenant_id AND rp.permission_id=p.id
            JOIN foundation.role r ON r.tenant_id=rp.tenant_id AND r.id=rp.role_id AND r.is_enabled
            WHERE p.tenant_id=@tenant AND p.is_enabled AND p.is_system AND (
                EXISTS (SELECT 1 FROM foundation.user_role ur WHERE ur.tenant_id=r.tenant_id AND ur.role_id=r.id AND ur.user_id=@user)
                OR EXISTS (SELECT 1 FROM foundation.user_group_role gr
                    JOIN foundation.user_group g ON g.tenant_id=gr.tenant_id AND g.id=gr.user_group_id AND g.is_enabled
                    JOIN foundation.user_group_member gm ON gm.tenant_id=g.tenant_id AND gm.user_group_id=g.id
                    WHERE gr.tenant_id=r.tenant_id AND gr.role_id=r.id AND gm.user_id=@user))
            ORDER BY p.code
            """;
        await using var permissions = await db.Command(sql,("tenant",a.TenantId),("user",a.Id));
        await using var rows = await permissions.ExecuteReaderAsync();
        var codes = new List<string>();
        while (await rows.ReadAsync()) {var code=rows.GetString(0); if(PermissionCatalog.Contains(code)) codes.Add(code);}
        return new(a,a.Username,a.FullName,codes.ToArray());
    }
    public static IdentityState State(HttpContext ctx) => (IdentityState)ctx.Items["identity"]!;
    public static async Task Authorize(HttpContext ctx,string code)
    {
        Check.Require(code == PermissionCatalog.GlobalPolicy || PermissionCatalog.Contains(code),403,"forbidden");
        var service=ctx.RequestServices.GetRequiredService<Microsoft.AspNetCore.Authorization.IAuthorizationService>();
        Check.Require((await service.AuthorizeAsync(ctx.User,ctx,code)).Succeeded,403,"forbidden");
    }
    public static Task AuthorizeResource(HttpContext ctx,Resource resource,string action)
    {
        Check.Require(action is "read" or "create" or "update" or "delete",403,"forbidden");
        Check.Require(!resource.ReadOnly || action == "read",403,"forbidden");
        // Cataloghi globali: lettura esplicita tenant, manutenzione soltanto globale.
        return Authorize(ctx,resource.Key == "tenants" || ResourceCatalog.IsGlobalMaster(resource.Key) && action != "read"
            ? PermissionCatalog.GlobalPolicy : resource.Key+"."+action);
    }
    public static async Task Issue(HttpContext ctx, User a, Guid? selectedTenantId = null)
    {
        var identity = new ClaimsIdentity(new[] { new Claim(ClaimTypes.NameIdentifier,a.Id.ToString()), new Claim("stamp",a.SecurityStamp.ToString()) },CookieAuthenticationDefaults.AuthenticationScheme);
        if (a.IsSuperAdmin && a.TenantId == null && selectedTenantId != null)
            identity.AddClaim(new Claim(SelectedTenantClaim,selectedTenantId.Value.ToString()));
        await ctx.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme,new ClaimsPrincipal(identity),new AuthenticationProperties { IsPersistent = false, AllowRefresh = false });
    }
    public static async Task Lock(AppDb db) => await db.Execute("SELECT pg_advisory_xact_lock(@key)",("key",LockKey));
    public static async Task Bootstrap(IServiceProvider services, string path)
    {
        // Il file privato viene letto solo dal comando esplicito, mai dalla configurazione web.
        var file = new FileInfo(path);
        Check.Require(file.Exists && file.Length <= 8192);
        if (!OperatingSystem.IsWindows())
            Check.Require((File.GetUnixFileMode(path) & (UnixFileMode.GroupRead | UnixFileMode.GroupWrite | UnixFileMode.GroupExecute | UnixFileMode.OtherRead | UnixFileMode.OtherWrite | UnixFileMode.OtherExecute)) == 0);
        var input = System.Text.Json.JsonSerializer.Deserialize<BootstrapInput>(await File.ReadAllTextAsync(path),new System.Text.Json.JsonSerializerOptions { PropertyNameCaseInsensitive=true, UnmappedMemberHandling=System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow })!;
        Check.Require(input != null && !string.IsNullOrWhiteSpace(input.Username) && input.Username.Length <= 500);
        Check.Password(input!.Password);
        var profile=ResourceCatalog.Validate(ResourceCatalog.Get("users"),System.Text.Json.JsonSerializer.SerializeToElement(new {
            username=input.Username, first_name=input.FirstName, last_name=input.LastName, email=input.Email
        }),true);
        using var scope = services.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<AppDb>();
        await using var tx = await db.Database.BeginTransactionAsync();
        await Lock(db);
        Check.Require(!await db.Users.AnyAsync(a => a.TenantId == null),409,"conflict");
        var user = new User { Username=input.Username,FirstName=(string)profile["first_name"]!,LastName=(string)profile["last_name"]!,Email=(string)profile["email"]!,IsSuperAdmin=true };
        user.PasswordHash = Hasher.HashPassword(user,input.Password);
        db.Users.Add(user);
        await db.SaveChangesAsync();
        await db.Audit(user.Id,null,"bootstrap","users",user.Id);
        await tx.CommitAsync();
        Console.WriteLine("Bootstrap completed.");
    }
    public sealed record BootstrapInput(string Username,string FirstName,string LastName,string Email,string Password);
}
