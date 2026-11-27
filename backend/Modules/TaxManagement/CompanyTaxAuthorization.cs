using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using static Enginia360.Modules.TaxManagement.CompanyTaxConfiguration;
namespace Enginia360.Modules.TaxManagement;

/// <summary>Il permesso e l'ambito company devono appartenere allo stesso ruolo abilitato.</summary>
public static class CompanyTaxAuthorization
{
    public static readonly string[] Actions=["read","create","update","activate","suspend","register","close","assign_regime","schedule_regime"];
    public const string Resource="company-tax-configurations";
    public static bool Global(IdentityState state)=>state.User.IsEnabled && state.User.IsSuperAdmin && state.User.TenantId==null;
    private const string GrantSql="""
        SELECT DISTINCT r.id AS role_id, substring(p.code FROM length('company-tax-configurations.')+1) AS action
        FROM foundation.role_company rc
        JOIN foundation.role r ON r.tenant_id=rc.tenant_id AND r.id=rc.role_id AND r.is_enabled
        JOIN foundation.role_permission rp ON rp.tenant_id=r.tenant_id AND rp.role_id=r.id
        JOIN foundation.permission p ON p.tenant_id=rp.tenant_id AND p.id=rp.permission_id AND p.is_enabled AND p.is_system
        JOIN foundation."user" u ON u.tenant_id=r.tenant_id AND u.id=@user AND u.is_enabled AND NOT u.is_super_admin
        JOIN foundation.tenant t ON t.id=u.tenant_id AND t.is_enabled
        WHERE rc.tenant_id=@tenant AND rc.company_id=@company AND p.code=ANY(@codes::text[]) AND (
            EXISTS(SELECT 1 FROM foundation.user_role ur WHERE ur.tenant_id=r.tenant_id AND ur.role_id=r.id AND ur.user_id=u.id)
            OR EXISTS(SELECT 1 FROM foundation.user_group_role gr
                JOIN foundation.user_group g ON g.tenant_id=gr.tenant_id AND g.id=gr.user_group_id AND g.is_enabled
                JOIN foundation.user_group_member gm ON gm.tenant_id=g.tenant_id AND gm.user_group_id=g.id AND gm.user_id=u.id
                WHERE gr.tenant_id=r.tenant_id AND gr.role_id=r.id))
        """;
    public static async Task<Guid> Tenant(HttpContext ctx,AppDb db)
    {
        Require(db.Database.CurrentTransaction!=null,"transaction_required",500);
        var state=Security.State(ctx);var tenant=state.Tenant(ctx,Resource);
        Require(tenant!=null,"tenant_required",field:"tenantId");
        Require(state.User.IsEnabled && (Global(state) || !state.User.IsSuperAdmin && state.User.TenantId==tenant),"forbidden",403);
        Require(await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@t AND is_enabled",("t",tenant)) is Guid,"tenant_not_found",404,"tenantId");return tenant!.Value;
    }
    public static async Task<string[]> Permissions(HttpContext ctx,AppDb db,Guid tenant,Guid company)
    {
        await Security.Authorize(ctx,"companies.read");
        if(Global(Security.State(ctx)))return Actions.ToArray();
        var rows=await TaxClassificationApplication.Rows(db,GrantSql,("tenant",tenant),("company",company),("user",Security.State(ctx).User.Id),("codes",Actions.Select(x=>Resource+"."+x).ToArray()));
        return ProjectPermissions(rows.Select(r=>((Guid)r["role_id"]!,(string)r["action"]!)));
    }
    internal static string[] ProjectPermissions(IEnumerable<(Guid RoleId,string Action)> scopedGrants)
    {
        // GrantSql filtra gia le appartenenze abilitate e l'esatto ambito aziendale.
        // Non combinare register di un ruolo con assign_regime di un altro ruolo.
        var roles=scopedGrants.GroupBy(x=>x.RoleId).Select(g=>g.Select(x=>x.Action).ToHashSet(StringComparer.Ordinal)).ToArray();
        return Actions.Where(action=>roles.Any(grants=>grants.Contains(action) && (action!="register" || grants.Contains("assign_regime")))).ToArray();
    }
    public static async Task RequireAction(HttpContext ctx,AppDb db,Guid tenant,Guid company,string action)
    {
        Require(Actions.Contains(action,StringComparer.Ordinal),"forbidden",403);
        Require((await Permissions(ctx,db,tenant,company)).Contains(action,StringComparer.Ordinal),"forbidden",403);
    }
}
