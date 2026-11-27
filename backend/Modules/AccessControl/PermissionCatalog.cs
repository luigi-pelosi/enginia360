using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using Microsoft.AspNetCore.Authorization;

namespace Enginia360.Modules.AccessControl;

public static class PermissionCatalog
{
    public const string GlobalPolicy = "GlobalAdministration";
    public static readonly string[] Codes = ResourceCatalog.All.Values
        .Where(r => r.Key is not "tenants" and not "permissions" && !ResourceCatalog.IsGlobalMaster(r.Key))
        .SelectMany(r => (r.Key == "business-partners" ? new[] { "read", "create", "update" } : new[] { "read", "create", "update", "delete" }).Select(a => r.Key + "." + a))
        .Concat(ResourceCatalog.All.Values.Where(r => ResourceCatalog.IsGlobalMaster(r.Key)).Select(r => r.Key + ".read"))
        .Concat(new[] { "catalog-units.read", "catalog-units.create", "catalog-units.update",
            "catalog-categories.read", "catalog-categories.create", "catalog-categories.update", "catalog-categories.delete",
            "catalog-types.read", "catalog-types.create", "catalog-types.update", "catalog-types.delete", "catalog-numbering.read", "catalog-numbering.update",
            "catalog-items.read", "catalog-items.create", "catalog-items.update", "catalog-items.activate", "catalog-items.deactivate", "catalog-items.archive",
            "catalog-brands.read", "catalog-brands.create", "catalog-brands.update",
            "catalog-item-companies.read", "catalog-item-companies.create", "catalog-item-companies.update" })
        .Concat(new[] { "tax-codes.read", "tax-codes.create", "tax-codes.update", "tax-codes.schedule",
            "tax-codes.deactivate", "tax-codes.reactivate", "tax-codes.install_templates", "tax-types.read", "tax-nature-codes.read" })
        .Concat(new[] { "tax-item-classifications", "tax-partner-classifications" }
            .SelectMany(resource => new[] { "read", "create", "update", "deactivate", "reactivate", "install_templates" }.Select(action => resource + "." + action)))
        .Concat(new[] { "tax-item-profiles", "tax-partner-profiles" }
            .SelectMany(resource => new[] { "read", "assign", "schedule" }.Select(action => resource + "." + action)))
        .Append("tax-regimes.read")
        .Concat(new[] { "read", "create", "update", "validate", "publish", "withdraw", "install_templates" }
            .Select(action => "tax-rules." + action))
        .Concat(new[] { "read", "simulate", "determine" }.Select(action => "tax-determination." + action))
        .Concat(new[] { "read", "simulate", "calculate" }.Select(action => "tax-calculation." + action))
        .Concat(new[] { "read", "create", "update", "activate", "suspend", "register", "close", "assign_regime", "schedule_regime" }
            .Select(action => "company-tax-configurations." + action))
        .Concat(ResourceCatalog.Links.Values.Select(r => r.Permission)).Concat(new[]{"payment-methods.read","payment-methods.create","payment-methods.update","payment-terms.read","payment-terms.create","payment-terms.update","payment-settings.read","payment-settings.update","payment-partner-defaults.read","payment-partner-defaults.update","payment-schedule.preview","payment-resolution.read"}).Concat(new[]{"roles.assign_companies","business-partner-companies.read","business-partner-companies.create","business-partner-companies.update","business-partner-companies.use_customer","business-partner-companies.use_supplier"}).Append("business-partner-numbering.read").Append("business-partner-numbering.update").Append("purchasing-organizations.assign_scope").Append("permissions.read").Append("users.reset_password").Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();
    public static async Task Seed(AppDb db,Guid tenantId)
    {
        // Il chiamante possiede transazione e lock; nessun ruolo o grant viene creato.
        Check.Require(db.Database.CurrentTransaction != null,500,"server_error");
        await db.Execute("""
            INSERT INTO foundation.permission(tenant_id,code,name,is_system)
            SELECT @tenant,code,code,true FROM unnest(@codes::text[]) code
            ON CONFLICT(tenant_id,code) DO UPDATE SET is_system=true
            WHERE NOT foundation.permission.is_system
            """,("tenant",tenantId),("codes",Codes));
    }
    public static bool Contains(string code) => Array.BinarySearch(Codes,code,StringComparer.Ordinal) >= 0;
    public static bool Grants(IdentityState state,string code) => Contains(code) && state.User.IsEnabled
        && (state.User.IsSuperAdmin && state.User.TenantId == null
            || !state.User.IsSuperAdmin && state.User.TenantId != null && state.Permissions.Contains(code,StringComparer.Ordinal));
    public static void Configure(IServiceCollection services)
    {
        services.AddAuthorization(options => {
            foreach(var code in Codes) options.AddPolicy(code,p => p.AddRequirements(new PermissionRequirement(code)));
            options.AddPolicy(GlobalPolicy,p => p.AddRequirements(new GlobalAdministrationRequirement()));
        });
        services.AddScoped<IAuthorizationHandler,PermissionHandler>();
    }
}

public sealed record PermissionRequirement(string Code) : IAuthorizationRequirement;
public sealed record GlobalAdministrationRequirement : IAuthorizationRequirement;
public sealed class PermissionHandler : IAuthorizationHandler
{
    public Task HandleAsync(AuthorizationHandlerContext context)
    {
        // Il cookie identifica la sessione; l'autorità proviene esclusivamente dallo stato fresco sotto lock.
        if(context.Resource is not HttpContext http || http.Items["identity"] is not IdentityState state) return Task.CompletedTask;
        foreach(var requirement in context.PendingRequirements.ToArray())
        {
            if(requirement is PermissionRequirement permission && PermissionCatalog.Grants(state,permission.Code)
                || requirement is GlobalAdministrationRequirement && state.User.IsEnabled && state.User.IsSuperAdmin && state.User.TenantId == null)
                context.Succeed(requirement);
        }
        return Task.CompletedTask;
    }
}
