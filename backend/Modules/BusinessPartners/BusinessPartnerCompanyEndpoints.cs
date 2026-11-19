using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Text.Json;
using Npgsql;
using Enginia360.Api.Resources;

namespace Enginia360.Modules.BusinessPartners;

// L'ambito aziendale deriva dal ruolo che concede il permesso, non dal prodotto
// tra permessi di sessione e aziende. La query vincola entrambe le concessioni allo stesso ruolo.
public static class CompanyAuthorization
{
    public static readonly string[] Actions=["read","create","update","use_customer","use_supplier"];
    public static bool Global(IdentityState state)=>state.User.IsEnabled && state.User.IsSuperAdmin && state.User.TenantId==null;
    private const string GrantSql="""
        SELECT DISTINCT rc.company_id,substring(p.code FROM length('business-partner-companies.')+1) AS action
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
        var sql=Global(state) ? "SELECT id,unnest(@actions::text[]) FROM foundation.company WHERE tenant_id=@tenant" : GrantSql;
        await using var cmd=await db.Command(sql,("user",state.User.Id),("tenant",tenant),("codes",Actions.Select(a=>"business-partner-companies."+a).ToArray()),("actions",Actions));
        await using var rows=await cmd.ExecuteReaderAsync();
        while(await rows.ReadAsync()) {var id=rows.GetGuid(0);if(!result.TryGetValue(id,out var actions))result[id]=actions=[];actions.Add(rows.GetString(1));}
        return result.ToDictionary(p=>p.Key,p=>Actions.Where(p.Value.Contains).ToArray());
    }
    public static async Task Require(HttpContext ctx,AppDb db,Guid tenant,Guid company,string action)
    {
        Check.Require(Actions.Contains(action,StringComparer.Ordinal),403,"forbidden");
        var scopes=await Resolve(db,Security.State(ctx),tenant);
        Check.Require(scopes.TryGetValue(company,out var actions) && actions.Contains(action,StringComparer.Ordinal),403,"forbidden");
    }
}

public static class BusinessPartnerCompanyEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapPost("/api/companies/{companyId:guid}/business-partners",Create);
        app.MapPatch("/api/companies/{companyId:guid}/business-partners/{bpId:guid}",(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,JsonElement body)=>Update(ctx,db,companyId,bpId,null,body));
        app.MapPut("/api/companies/{companyId:guid}/business-partners/{bpId:guid}/roles/{roleCode}",(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,string roleCode,JsonElement body)=>Update(ctx,db,companyId,bpId,roleCode,body));
        app.MapGet("/api/companies/{companyId:guid}/business-partners/{bpId:guid}",async(HttpContext ctx,AppDb db,Guid companyId,Guid bpId)=>{
            var tenant=await Gate(ctx,db,companyId,"read");return Results.Ok(await Read(db,Security.State(ctx),tenant,companyId,bpId));
        });
        app.MapGet("/api/data/business-partners/{bpId:guid}/companies",async(HttpContext ctx,AppDb db,Guid bpId)=>{
            await Security.Authorize(ctx,"business-partners.read");await Security.Authorize(ctx,"business-partner-companies.read");
            var state=Security.State(ctx);var tenant=state.Tenant(ctx,"business-partners")!.Value;
            await Resources.EnsureRow(db,Resources.Get("business-partners"),bpId,tenant);
            var grants=await CompanyAuthorization.Resolve(db,state,tenant);
            var ids=grants.Where(x=>x.Value.Contains("read")).Select(x=>x.Key).ToArray();
            return Results.Ok(new{items=await Query(db,grants,"cbp.tenant_id=@t AND cbp.business_partner_id=@b AND cbp.company_id=ANY(@ids::uuid[])",false,("t",tenant),("b",bpId),("ids",ids))});
        });
        app.MapGet("/api/companies/{companyId:guid}/business-partners/{bpId:guid}/eligibility/{roleCode}",async(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,string roleCode)=>{
            BusinessPartnerEligibility.ValidateRole(roleCode);
            var tenant=await Gate(ctx,db,companyId,roleCode=="CUSTOMER" ? "use_customer" : "use_supplier");
            return Results.Ok(new{usable=await BusinessPartnerEligibility.IsEligible(db,tenant,companyId,bpId,roleCode)});
        });
        app.MapGet("/api/companies/{companyId:guid}/business-partners",(HttpContext ctx,AppDb db,Guid companyId)=>List(ctx,db,companyId));
        app.MapGet("/api/business-partner-companies",(HttpContext ctx,AppDb db)=>List(ctx,db,null));
        app.MapGet("/api/business-partner-companies/options",async(HttpContext ctx,AppDb db)=>{
            var state=Security.State(ctx);var tenant=state.Tenant(ctx,"business-partners")!.Value;
            var grants=await CompanyAuthorization.Resolve(db,state,tenant);
            await using var cmd=await db.Command("SELECT to_jsonb(c)::text FROM foundation.company c WHERE c.tenant_id=@t AND c.id=ANY(@ids::uuid[]) ORDER BY lower(c.name),c.id",("t",tenant),("ids",grants.Keys.ToArray()));
            await using var reader=await cmd.ExecuteReaderAsync();var items=new List<object>();
            while(await reader.ReadAsync()) {var c=JsonSerializer.Deserialize<JsonElement>(reader.GetString(0));var id=c.GetProperty("id").GetGuid();items.Add(new{id,name=c.GetProperty("name"),code=c.GetProperty("code"),is_enabled=c.GetProperty("is_enabled"),permissions=grants[id]});}
            return Results.Ok(new{items});
        });
    }
    private const string UsableRole="((cr.role_code='CUSTOMER' AND cbp.company_id=ANY(@customer::uuid[])) OR (cr.role_code='SUPPLIER' AND cbp.company_id=ANY(@supplier::uuid[])))";
    private const string Projection="""
        (to_jsonb(cbp)||jsonb_build_object('company_name',c.name,
        'roles',COALESCE((SELECT jsonb_agg(jsonb_build_object('id',cr.id,'role_code',cr.role_code,'status',cr.status,'created_at',cr.created_at,'updated_at',cr.updated_at) ORDER BY cr.role_code) FROM masterdata.company_business_partner_role cr WHERE cr.tenant_id=cbp.tenant_id AND cr.company_business_partner_id=cbp.id),'[]'::jsonb),
        'usable_roles',COALESCE((SELECT jsonb_agg(cr.role_code ORDER BY cr.role_code) FROM masterdata.company_business_partner_role cr WHERE cr.tenant_id=cbp.tenant_id AND cr.company_business_partner_id=cbp.id AND
        """+" "+BusinessPartnerEligibility.ActiveStates+" AND "+UsableRole+"),'[]'::jsonb)))";
    private static (string Name,object? Value)[] UseParameters(Dictionary<Guid,string[]> grants)=>[
        ("customer",grants.Where(x=>x.Value.Contains("use_customer")).Select(x=>x.Key).ToArray()),
        ("supplier",grants.Where(x=>x.Value.Contains("use_supplier")).Select(x=>x.Key).ToArray())];
    private static async Task<List<JsonElement>> Query(AppDb db,Dictionary<Guid,string[]> grants,string where,bool includePartner,params (string Name,object? Value)[] values)
    {
        var projection=Projection+(includePartner ? "||jsonb_build_object('bp_code',b.code,'bp_name',COALESCE(b.legal_name,concat_ws(' ',b.first_name,b.last_name)),'bp_status',b.status)" : "");
        await using var cmd=await db.Command("SELECT ("+projection+")::text "+BusinessPartnerEligibility.Joins+" WHERE "+where,values.Concat(UseParameters(grants)).ToArray());
        await using var reader=await cmd.ExecuteReaderAsync();var items=new List<JsonElement>();while(await reader.ReadAsync())items.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));return items;
    }
    private static async Task<JsonElement> Read(AppDb db,IdentityState state,Guid tenant,Guid company,Guid partner)
    {
        var grants=await CompanyAuthorization.Resolve(db,state,tenant);
        var items=await Query(db,grants,"cbp.tenant_id=@t AND cbp.company_id=@c AND cbp.business_partner_id=@b",false,("t",tenant),("c",company),("b",partner));
        Check.Require(items.Count==1,404,"not_found");return items[0];
    }
    private static string Parameter(HttpContext ctx,string key)
    {
        var values=ctx.Request.Query[key];Check.Require(values.Count<=1);return values.ToString();
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db,Guid? companyId)
    {
        await Security.Authorize(ctx,"business-partners.read");
        await Security.Authorize(ctx,"business-partner-companies.read");
        var state=Security.State(ctx);
        // L'azienda esplicita mantiene il gate: un ambito negato non diventa una lettura generale.
        var tenant=companyId.HasValue ? await Gate(ctx,db,companyId.Value,"read") : state.Tenant(ctx,"business-partners")!.Value;
        var grants=await CompanyAuthorization.Resolve(db,state,tenant);
        var ids=companyId.HasValue ? new[]{companyId.Value} : grants.Where(x=>x.Value.Contains("read")).Select(x=>x.Key).ToArray();
        var role=Parameter(ctx,"role");if(role.Length>0)BusinessPartnerEligibility.ValidateRole(role);
        var usableText=Parameter(ctx,"usableOnly");Check.Require(usableText is "" or "true" or "false");var usable=usableText=="true";
        var search=Parameter(ctx,"search");Check.Require(search.Length<=200 && !search.Any(char.IsControl));
        int Number(string key,int fallback,int max){var text=Parameter(ctx,key);if(text=="")return fallback;Check.Require(int.TryParse(text,out var number) && number>=1 && number<=max);return number;}
        var page=Number("page",1,100000);var pageSize=Number("pageSize",25,100);
        var where="cbp.tenant_id=@t AND cbp.company_id=ANY(@ids::uuid[]) AND (@search='' OR strpos(lower(concat_ws(' ',b.code,b.legal_name,b.first_name,b.last_name)),lower(@search))>0) AND "+
            "((@role='' AND NOT @usable) OR EXISTS(SELECT 1 FROM masterdata.company_business_partner_role cr WHERE cr.tenant_id=cbp.tenant_id AND cr.company_business_partner_id=cbp.id AND (@role='' OR cr.role_code=@role) AND (NOT @usable OR ("+BusinessPartnerEligibility.ActiveStates+" AND "+UsableRole+"))))";
        (string Name,object? Value)[] values=[("t",tenant),("ids",ids),("role",role),("search",search),("usable",usable)];
        var total=(long)(await db.Scalar("SELECT count(*) "+BusinessPartnerEligibility.Joins+" WHERE "+where,values.Concat(UseParameters(grants)).ToArray()))!;
        var items=await Query(db,grants,where+" ORDER BY cbp.created_at,cbp.id LIMIT @size OFFSET @offset",true,values.Concat(new (string Name,object? Value)[]{("size",pageSize),("offset",(page-1)*pageSize)}).ToArray());
        return Results.Ok(new{items,total,page,pageSize});
    }
    private static async Task<Guid> Gate(HttpContext ctx,AppDb db,Guid company,string action)
    {
        await Security.Authorize(ctx,"business-partners.read");
        await Security.Authorize(ctx,"business-partner-companies."+action);
        var tenant=Security.State(ctx).Tenant(ctx,"business-partners")!.Value;
        await CompanyAuthorization.Require(ctx,db,tenant,company,action);return tenant;
    }
    private static async Task<IResult> Update(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,string? role,JsonElement body)
    {
        var tenant=await Gate(ctx,db,companyId,"update");var state=Security.State(ctx);
        if(role!=null)BusinessPartnerEligibility.ValidateRole(role);
        var input=PartnerInput.Object(body,"status","expectedVersion");var status=PartnerInput.Choice(input,"status","ACTIVE","BLOCKED");
        var expected=PartnerInput.Integer(input,"expectedVersion",1,9007199254740991);
        var id=await db.Scalar("SELECT id FROM masterdata.company_business_partner WHERE tenant_id=@t AND company_id=@c AND business_partner_id=@b FOR UPDATE",("t",tenant),("c",companyId),("b",bpId));
        Check.Require(id is Guid,404,"not_found");
        var before=await Read(db,state,tenant,companyId,bpId);
        Check.Require(before.GetProperty("version").GetInt64()==expected,409,"stale_version");Check.Require(expected<9007199254740991,409,"version_exhausted");
        if(role==null)await db.Execute("UPDATE masterdata.company_business_partner SET status=@status,version=version+1 WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id),("status",status));
        else {
            await db.Execute("INSERT INTO masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code,status) VALUES(@t,@id,@role,@status) ON CONFLICT(tenant_id,company_business_partner_id,role_code) DO UPDATE SET status=EXCLUDED.status",("t",tenant),("id",id),("role",role),("status",status));
            await db.Execute("UPDATE masterdata.company_business_partner SET version=version+1 WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id));
        }
        var after=await Read(db,state,tenant,companyId,bpId);await db.Audit(state.User.Id,tenant,role==null ? "update" : "set_role","business-partner-companies",(Guid)id!,new{before,after,roleCode=role});
        return Results.Ok(after);
    }
    private static async Task<IResult> Create(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)
    {
        var tenant=await Gate(ctx,db,companyId,"create");var state=Security.State(ctx);
        var input=PartnerInput.Object(body,"businessPartnerId","roles");
        var text=PartnerInput.Text(input,"businessPartnerId",36,true)!;Check.Require(Guid.TryParseExact(text,"D",out var bp) && bp!=Guid.Empty);
        await Resources.EnsureRow(db,Resources.Get("business-partners"),bp,tenant);
        var roles=new HashSet<string>(StringComparer.Ordinal);
        if(input.TryGetValue("roles",out var raw))foreach(var item in PartnerInput.Array(raw,2)){var role=Resources.ReadString(item);BusinessPartnerEligibility.ValidateRole(role);Check.Require(roles.Add(role));}
        Check.Require(!(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.company_business_partner WHERE tenant_id=@t AND company_id=@c AND business_partner_id=@b)",("t",tenant),("c",companyId),("b",bp)))!,409,"company_partner_exists");
        var id=Guid.NewGuid();
        try {await db.Execute("INSERT INTO masterdata.company_business_partner(id,tenant_id,company_id,business_partner_id) VALUES(@id,@t,@c,@b)",("id",id),("t",tenant),("c",companyId),("b",bp));}
        catch(PostgresException e)when(e.SqlState=="23505" && e.ConstraintName=="company_business_partner_unique"){throw new ApiException(409,"company_partner_exists");}
        foreach(var role in roles)await db.Execute("INSERT INTO masterdata.company_business_partner_role(tenant_id,company_business_partner_id,role_code) VALUES(@t,@id,@role)",("t",tenant),("id",id),("role",role));
        var after=await Read(db,state,tenant,companyId,bp);await db.Audit(state.User.Id,tenant,"create","business-partner-companies",id,new{before=(JsonElement?)null,after});
        return Results.Json(after,statusCode:201);
    }
}
