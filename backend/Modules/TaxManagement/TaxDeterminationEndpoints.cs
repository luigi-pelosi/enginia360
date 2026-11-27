using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public static class TaxDeterminationEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/determination-lookups",Lookups);
        app.MapGet("/api/tax/determination-options",Options);
        app.MapPost("/api/tax/determinations/simulate",(HttpContext ctx,AppDb db,JsonElement body)=>Determine(ctx,db,body,true));
        app.MapPost("/api/tax/determinations",(HttpContext ctx,AppDb db,JsonElement body)=>Determine(ctx,db,body,false));
    }
    private static async Task<IResult> Determine(HttpContext ctx,AppDb db,JsonElement body,bool simulation)
    {
        var request=TaxDeterminationInput.Parse(body,simulation);var tenant=await TaxRuleReferences.Tenant(ctx,db,"tax-determination");
        var outcome=await TaxDeterminationApplication.Evaluate(ctx,db,tenant,request,simulation);
        return simulation||outcome.Outcome=="SUCCESS"?Results.Ok(outcome):Results.Json(new{error="tax_determination_"+outcome.Outcome.ToLowerInvariant(),outcome=outcome.Outcome,result=outcome.Result,trace=outcome.Trace,isSimulation=false},statusCode:422);
    }
    private static async Task<IResult> Lookups(HttpContext ctx,AppDb db)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db,"tax-determination");var companies=await TaxRuleReferences.Companies(ctx,db,t,"tax-determination");var read=await TaxRuleReferences.Allowed(ctx,db,t,null,"tax-determination.read");Require(read||companies.Count>0,"forbidden",403);
        var company=QueryId(ctx,"company_id");var date=QueryDate(ctx);var type=QueryId(ctx,"tax_type_id");
        var countries=await TaxRuleReferences.Bounded(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country ORDER BY name,id");var types=await TaxRuleReferences.Bounded(db,"SELECT id,code,name,is_active FROM taxmanagement.tax_types ORDER BY code,id");
        var registrations=new List<Dictionary<string,object?>>();string[] permissions=[];
        if(company!=null){
            await TaxRuleReferences.Action(ctx,db,t,company,"tax-determination.read");await CompanyTaxAuthorization.RequireAction(ctx,db,t,company.Value,"read");permissions=await TaxRuleReferences.Permissions(ctx,db,t,company,"tax-determination");
            Require(date!=null&&type!=null,"tax_field_required",field:date==null?"date":"tax_type_id");
            foreach(var registration in await new CompanyTaxProfileResolver(db).List(t,company.Value,type,date!.Value,true)){
                registration.Remove("tax_identifier");registrations.Add(registration);
            }
        }
        return Results.Ok(new{companies,countries,types,registrations,permissions,operationTypes=new[]{"SALE","PURCHASE"},operationCategories=new[]{"ORDINARY_MOVABLE_GOODS","GENERAL_SERVICES"},specialTaxTreatments=new[]{"NONE","REVERSE_CHARGE","SPLIT_PAYMENT","EXEMPT","MARGIN","OTHER"},goodsCustomsStatuses=new[]{"NATIONAL_OR_UNION","OTHER"},technicalCoverageFrom="2026-11-26"});
    }
    private static async Task<IResult> Options(HttpContext ctx,AppDb db)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db,"tax-determination");var company=QueryId(ctx,"company_id");Require(company!=null,"tax_field_required",field:"company_id");await TaxRuleReferences.Action(ctx,db,t,company,"tax-determination.read");
        var kind=ctx.Request.Query["kind"].ToString();Require(kind is "item" or "partner","tax_invalid_field",field:"kind");
        await Enginia360.Modules.Identity.Security.Authorize(ctx,kind=="item"?"catalog-items.read":"business-partners.read");await CompanyTaxApplication.Company(db,t,company!.Value,false);
        var(page,size)=Paging(ctx);var search=Search(ctx);var table=kind=="item"?"catalog_item":"business_partner";var label=kind=="item"?"name":"coalesce(legal_name,nullif(concat_ws(' ',first_name,last_name),''),code)";
        var filter=" WHERE tenant_id=@t AND status<>'ARCHIVED' AND (@s='' OR strpos(lower(code||' '||"+label+"),lower(@s))>0)";
        var args=new (string Name,object? Value)[]{("t",t),("s",search),("n",size),("offset",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM masterdata."+table+filter,args));var items=await Rows(db,"SELECT id,code,"+label+" AS name,status,version FROM masterdata."+table+filter+" ORDER BY lower("+label+"),id LIMIT @n OFFSET @offset",args);
        if(kind=="partner")foreach(var item in items)item["tax_identifiers"]=await Rows(db,"SELECT i.id,i.identifier_type,i.country_code,c.id AS country_id FROM masterdata.business_partner_tax_identifier i LEFT JOIN foundation.country c ON c.iso_code=i.country_code WHERE i.tenant_id=@t AND i.business_partner_id=@id ORDER BY i.id",("t",t),("id",item["id"]));
        return Results.Ok(new{items,total,page,pageSize=size,has_more=(long)page*size<total});
    }
}
