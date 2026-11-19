using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Text.Json;

namespace Enginia360.Modules.AccessControl;

public static class RoleCompanyEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/roles/{roleId:guid}/companies",async(HttpContext ctx,AppDb db,Guid roleId)=>{
            await Security.Authorize(ctx,"roles.read");await Security.Authorize(ctx,"companies.read");
            var tenant=Security.State(ctx).Tenant(ctx,"roles")!.Value;
            await Resources.EnsureRow(db,Resources.Get("roles"),roleId,tenant);
            return Results.Ok(new{companyIds=await Read(db,tenant,roleId)});
        });
        app.MapPut("/api/roles/{roleId:guid}/companies",async(HttpContext ctx,AppDb db,Guid roleId,JsonElement body)=>{
            await Security.Authorize(ctx,"roles.assign_companies");var state=Security.State(ctx);var tenant=state.Tenant(ctx,"roles")!.Value;
            await Resources.EnsureRow(db,Resources.Get("roles"),roleId,tenant);
            var input=PartnerInput.Object(body,"companyIds");Check.Require(input.TryGetValue("companyIds",out var raw));
            var ids=new HashSet<Guid>();foreach(var item in PartnerInput.Array(raw,1000)) {var text=Resources.ReadString(item);Check.Require(Guid.TryParseExact(text,"D",out var id) && id!=Guid.Empty && ids.Add(id));}
            var count=(long)(await db.Scalar("SELECT count(*) FROM foundation.company WHERE tenant_id=@t AND id=ANY(@ids::uuid[])",("t",tenant),("ids",ids.ToArray())))!;
            Check.Require(count==ids.Count);
            var beforeIds=await Read(db,tenant,roleId);
            // Conserva le date delle assegnazioni invariate; qui sono ammesse revoche e sostituzioni.
            await db.Execute("DELETE FROM foundation.role_company WHERE tenant_id=@t AND role_id=@r AND NOT(company_id=ANY(@ids::uuid[])); INSERT INTO foundation.role_company(tenant_id,role_id,company_id) SELECT @t,@r,id FROM unnest(@ids::uuid[]) id ON CONFLICT DO NOTHING",("t",tenant),("r",roleId),("ids",ids.ToArray()));
            var afterIds=await Read(db,tenant,roleId);
            await db.Audit(state.User.Id,tenant,"assign_companies","role-companies",roleId,new{beforeIds,afterIds});
            return Results.Ok(new{companyIds=afterIds});
        });
    }
    private static async Task<Guid[]> Read(AppDb db,Guid tenant,Guid role)
    {
        await using var cmd=await db.Command("SELECT company_id FROM foundation.role_company WHERE tenant_id=@t AND role_id=@r ORDER BY company_id",("t",tenant),("r",role));
        await using var reader=await cmd.ExecuteReaderAsync();var result=new List<Guid>();while(await reader.ReadAsync())result.Add(reader.GetGuid(0));return result.ToArray();
    }
}
