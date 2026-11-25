using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Catalog;

// Ogni permesso e ambito aziendale devono essere concessi dallo stesso ruolo attivo.
public static class CatalogCompanyAuthorization
{
    public static readonly string[] Actions=["read","create","update"];
    public static bool Global(IdentityState state)=>state.User.IsEnabled && state.User.IsSuperAdmin && state.User.TenantId==null;
    private const string GrantSql="""
        SELECT DISTINCT rc.company_id,substring(p.code FROM length('catalog-item-companies.')+1)
        FROM foundation.role_company rc
        JOIN foundation.role r ON r.tenant_id=rc.tenant_id AND r.id=rc.role_id AND r.is_enabled
        JOIN foundation.role_permission rp ON rp.tenant_id=r.tenant_id AND rp.role_id=r.id
        JOIN foundation.permission p ON p.tenant_id=rp.tenant_id AND p.id=rp.permission_id AND p.is_enabled AND p.is_system
        JOIN foundation."user" u ON u.tenant_id=r.tenant_id AND u.id=@user AND u.is_enabled AND NOT u.is_super_admin
        JOIN foundation.tenant t ON t.id=u.tenant_id AND t.is_enabled
        WHERE rc.tenant_id=@tenant AND p.code=ANY(@codes::text[]) AND (
          EXISTS(SELECT 1 FROM foundation.user_role ur WHERE ur.tenant_id=r.tenant_id AND ur.role_id=r.id AND ur.user_id=u.id)
          OR EXISTS(SELECT 1 FROM foundation.user_group_role gr
            JOIN foundation.user_group g ON g.tenant_id=gr.tenant_id AND g.id=gr.user_group_id AND g.is_enabled
            JOIN foundation.user_group_member gm ON gm.tenant_id=g.tenant_id AND gm.user_group_id=g.id AND gm.user_id=u.id
            WHERE gr.tenant_id=r.tenant_id AND gr.role_id=r.id))
        """;
    public static async Task<Dictionary<Guid,string[]>> Resolve(AppDb db,IdentityState state,Guid tenant)
    {
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        Check.Require(state.User.IsEnabled && (Global(state) || !state.User.IsSuperAdmin && state.User.TenantId==tenant),403,"forbidden");
        var result=new Dictionary<Guid,List<string>>();
        var sql=Global(state)?"SELECT id,unnest(@actions::text[]) FROM foundation.company WHERE tenant_id=@tenant":GrantSql;
        await using var cmd=await db.Command(sql,("tenant",tenant),("user",state.User.Id),("codes",Actions.Select(a=>"catalog-item-companies."+a).ToArray()),("actions",Actions));
        await using var rows=await cmd.ExecuteReaderAsync();
        while(await rows.ReadAsync()) {
            var id=rows.GetGuid(0);
            if(!result.TryGetValue(id,out var actions))result[id]=actions=[];
            actions.Add(rows.GetString(1));
        }
        return result.ToDictionary(x=>x.Key,x=>Actions.Where(x.Value.Contains).ToArray());
    }
    public static async Task Require(HttpContext ctx,AppDb db,Guid tenant,Guid company,string action)
    {
        Check.Require(Actions.Contains(action,StringComparer.Ordinal),403,"forbidden");
        await Security.Authorize(ctx,"catalog-item-companies."+action);
        var grants=await Resolve(db,Security.State(ctx),tenant);
        Check.Require(grants.TryGetValue(company,out var actions) && actions.Contains(action,StringComparer.Ordinal),403,"forbidden");
    }
}
