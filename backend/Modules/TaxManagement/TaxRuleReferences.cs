using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public static class TaxRuleReferences
{
    public static readonly string[] RuleActions=["read","create","update","validate","publish","withdraw","install_templates"];
    public static readonly string[] DeterminationActions=["read","simulate","determine"];
    public static readonly string[] CalculationActions=["read","simulate","calculate"];
    public static async Task<Guid> Tenant(HttpContext ctx,AppDb db,string resource="tax-rules")
    {
        Require(db.Database.CurrentTransaction!=null,"transaction_required",500);
        var state=Security.State(ctx);var tenant=state.Tenant(ctx,resource);
        Require(tenant.HasValue,"tax_tenant_required",field:"tenantId");
        Require(state.User.IsEnabled && (CompanyTaxAuthorization.Global(state)||!state.User.IsSuperAdmin&&state.User.TenantId==tenant),"forbidden",403);
        Require(await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@t AND is_enabled",("t",tenant)) is Guid,"not_found",404,"tenantId");return tenant!.Value;
    }
    public static async Task<bool> Allowed(HttpContext ctx,AppDb db,Guid tenant,Guid? company,string permission)
    {
        if(company==null){try{await Security.Authorize(ctx,permission);return true;}catch(ApiException e) when(e.Status==403){return false;}}
        try{await Security.Authorize(ctx,"companies.read");}catch(ApiException e) when(e.Status==403){return false;}
        if(CompanyTaxAuthorization.Global(Security.State(ctx)))return true;
        return await db.Scalar("""
            SELECT EXISTS(SELECT 1 FROM foundation.role_company rc
            JOIN foundation.role r ON r.tenant_id=rc.tenant_id AND r.id=rc.role_id AND r.is_enabled
            JOIN foundation.role_permission rp ON rp.tenant_id=r.tenant_id AND rp.role_id=r.id
            JOIN foundation.permission p ON p.tenant_id=rp.tenant_id AND p.id=rp.permission_id AND p.is_enabled AND p.is_system
            JOIN foundation."user" u ON u.tenant_id=r.tenant_id AND u.id=@u AND u.is_enabled AND NOT u.is_super_admin
            WHERE rc.tenant_id=@t AND rc.company_id=@c AND p.code=@p AND (
            EXISTS(SELECT 1 FROM foundation.user_role ur WHERE ur.tenant_id=r.tenant_id AND ur.role_id=r.id AND ur.user_id=u.id)
            OR EXISTS(SELECT 1 FROM foundation.user_group_role gr JOIN foundation.user_group g ON g.tenant_id=gr.tenant_id AND g.id=gr.user_group_id AND g.is_enabled
            JOIN foundation.user_group_member gm ON gm.tenant_id=g.tenant_id AND gm.user_group_id=g.id AND gm.user_id=u.id WHERE gr.tenant_id=r.tenant_id AND gr.role_id=r.id)))
            """,("t",tenant),("c",company),("u",Security.State(ctx).User.Id),("p",permission)) is true;
    }
    public static async Task Action(HttpContext ctx,AppDb db,Guid tenant,Guid? company,string permission)
    {Require(await Allowed(ctx,db,tenant,company,permission),"forbidden",403);}
    public static async Task<string[]> Permissions(HttpContext ctx,AppDb db,Guid t,Guid? company,string resource="tax-rules")
    {
        var actions=resource switch {"tax-rules"=>RuleActions,"tax-calculation"=>CalculationActions,_=>DeterminationActions};
        var result=new List<string>();foreach(var a in actions)if(await Allowed(ctx,db,t,company,resource+"."+a))result.Add(a);return result.ToArray();
    }
    public static Task RulesetLock(AppDb db,Guid tenant,Guid country,Guid type,string operation,bool write=false)
        =>db.Execute("SELECT "+(write?"pg_advisory_xact_lock":"pg_advisory_xact_lock_shared")+"(hashtextextended(@k,0))",("k",$"tax-determination:rules:{tenant:D}:{country:D}:{type:D}:{operation}"));
    public static async Task<List<Dictionary<string,object?>>> Bounded(AppDb db,string sql,params (string Name,object? Value)[] args)
    {var rows=await Rows(db,sql+" LIMIT 10001",args);Require(rows.Count<=10000,"tax_lookup_limit_exceeded",409);return rows;}
    public static async Task<List<Dictionary<string,object?>>> Companies(HttpContext ctx,AppDb db,Guid tenant,string resource)
    {
        var rows=await Bounded(db,"SELECT id,code,name,is_enabled FROM foundation.company WHERE tenant_id=@t ORDER BY name,id",("t",tenant));var result=new List<Dictionary<string,object?>>();
        foreach(var row in rows){var permissions=await Permissions(ctx,db,tenant,(Guid)row["id"]!,resource);if(permissions.Length>0){row["permissions"]=permissions;result.Add(row);}}return result;
    }
    public static async Task<IReadOnlyList<TaxRuleIssue>> Validate(AppDb db,TaxRuleSnapshot root,TaxRuleVersion version,bool supported=true)
    {
        var issues=TaxRuleValidator.Validate(root,version).ToList();
        var code=await db.Scalar("SELECT id FROM taxmanagement.tax_codes WHERE tenant_id=@t AND id=@id AND country_id=@c AND tax_type_id=@type AND is_active FOR SHARE",("t",root.TenantId),("id",version.TaxCodeId),("c",root.CountryId),("type",root.TaxTypeId));
        if(code is not Guid)issues.Add(new("tax_rule_invalid_reference","tax_code_id"));
        if(await db.Scalar("SELECT id FROM foundation.country WHERE id=@id AND is_enabled",("id",root.CountryId)) is not Guid)issues.Add(new("tax_rule_invalid_reference","country_id"));
        if(await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE id=@id AND code='VAT' AND is_active",("id",root.TaxTypeId)) is not Guid)issues.Add(new("tax_rule_type_not_supported","tax_type_id"));
        foreach(var condition in version.Conditions.OrderBy(x=>x.Field,StringComparer.Ordinal).ThenBy(x=>x.Id)) {
            var metadata=TaxConditionFields.All.SingleOrDefault(f=>f.Key==condition.Field);if(metadata==null)continue;
            if(supported&&!metadata.Available)issues.Add(new("tax_rule_field_unavailable",condition.Field));
            if(metadata.Type!="REFERENCE")continue;
            var values=condition.Value.ValueKind==JsonValueKind.Array?condition.Value.EnumerateArray().ToArray():new[]{condition.Value};
            foreach(var raw in values){if(raw.ValueKind!=JsonValueKind.String||!Guid.TryParseExact(raw.GetString(),"D",out var id))continue;
                var sql=metadata.Reference switch {
                    "countries"=>"SELECT id FROM foundation.country WHERE id=@id AND is_enabled",
                    "regimes"=>"SELECT id FROM taxmanagement.tax_regimes WHERE id=@id AND country_id=@c AND tax_type_id=@type AND is_active AND is_supported",
                    "itemClassifications"=>"SELECT id FROM taxmanagement.item_tax_classifications WHERE tenant_id=@t AND id=@id AND country_id=@c AND tax_type_id=@type AND is_active FOR SHARE",
                    "partnerClassifications"=>"SELECT id FROM taxmanagement.partner_tax_classifications WHERE tenant_id=@t AND id=@id AND country_id=@c AND tax_type_id=@type AND is_active FOR SHARE",_=>null};
                if(sql==null || await db.Scalar(sql,("id",id),("t",root.TenantId),("c",root.CountryId),("type",root.TaxTypeId)) is not Guid)issues.Add(new("tax_rule_invalid_reference",condition.Field));
            }
        }
        return issues;
    }
    public static async Task<Dictionary<Guid,DeterminationTaxCode>> Codes(AppDb db,Guid tenant,IEnumerable<Guid> ids,Guid country,Guid type)
    {
        var result=new Dictionary<Guid,DeterminationTaxCode>();foreach(var id in ids.Distinct().Order()) {
            var r=(await Rows(db,"SELECT r.*,t.code AS type_code,t.is_active AS type_active FROM taxmanagement.tax_codes r JOIN taxmanagement.tax_types t ON t.id=r.tax_type_id WHERE r.tenant_id=@t AND r.id=@id FOR SHARE OF r",("t",tenant),("id",id))).SingleOrDefault();
            if(r==null)continue;Require((Guid)r["country_id"]! == country && (Guid)r["tax_type_id"]! == type,"tax_rule_invalid_reference",409,"tax_code_id");
            var versions=await Rows(db,"SELECT * FROM taxmanagement.tax_code_versions WHERE tenant_id=@t AND tax_code_id=@id ORDER BY valid_from,id",("t",tenant),("id",id));if(versions.Count==0)continue;
            var aggregate=new TaxCode(id,tenant,(long)r["version"]!,(bool)r["is_active"]!,(bool)r["type_active"]!&&(string)r["type_code"]! == "VAT",versions.Select(v=>new TaxFiscalVersion((Guid)v["id"]!,(decimal)v["rate"]!,(string)v["treatment"]!,v["tax_nature_code_id"] as Guid?,v["legal_reference"] as string,(DateOnly)v["valid_from"]!,v["valid_to"] as DateOnly?)));
            result.Add(id,new(country,type,(string)r["code"]!,aggregate));
        }return result;
    }
}
