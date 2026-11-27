using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public static class TaxRuleEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/rules",List);
        app.MapGet("/api/tax/rules/{id:guid}",Get);
        app.MapGet("/api/tax/rules/{id:guid}/versions",History);
        app.MapGet("/api/tax/rules/{id:guid}/permissions",Permissions);
        app.MapGet("/api/tax/rules/{id:guid}/conflicts",Conflicts);
        app.MapGet("/api/tax/rule-lookups",Lookups);
        app.MapPost("/api/tax/rules",async(HttpContext ctx,AppDb db,JsonElement body)=>Results.Json(await TaxRuleApplication.Create(ctx,db,await TaxRuleReferences.Tenant(ctx,db),body),statusCode:201));
        app.MapPut("/api/tax/rules/{id:guid}",async(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Results.Ok(await TaxRuleApplication.Update(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,body)));
        app.MapPost("/api/tax/rules/{id:guid}/versions",async(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Results.Json(await TaxRuleApplication.Draft(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,null,body),statusCode:201));
        app.MapPut("/api/tax/rules/{id:guid}/versions/{versionId:guid}",async(HttpContext ctx,AppDb db,Guid id,Guid versionId,JsonElement body)=>Results.Ok(await TaxRuleApplication.Draft(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,versionId,body)));
        app.MapPost("/api/tax/rules/{id:guid}/versions/{versionId:guid}/validate",async(HttpContext ctx,AppDb db,Guid id,Guid versionId,JsonElement body)=>Results.Ok(await TaxRuleApplication.Validate(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,versionId,Revision(Object(body,"expectedVersion")))));
        app.MapPost("/api/tax/rules/{id:guid}/versions/{versionId:guid}/publish",async(HttpContext ctx,AppDb db,Guid id,Guid versionId,JsonElement body)=>Results.Ok(await TaxRuleApplication.Transition(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,versionId,Revision(Object(body,"expectedVersion")),true)));
        app.MapPost("/api/tax/rules/{id:guid}/versions/{versionId:guid}/withdraw",async(HttpContext ctx,AppDb db,Guid id,Guid versionId,JsonElement body)=>Results.Ok(await TaxRuleApplication.Transition(ctx,db,await TaxRuleReferences.Tenant(ctx,db),id,versionId,Revision(Object(body,"expectedVersion")),false)));
        app.MapPost("/api/tax/rules/templates/install",Install);
    }
    private static async Task<IResult> Get(HttpContext ctx,AppDb db,Guid id)
    {var t=await TaxRuleReferences.Tenant(ctx,db);var root=await TaxRuleApplication.Read(db,t,id);await TaxRuleReferences.Action(ctx,db,t,root["company_id"] as Guid?,"tax-rules.read");return Results.Ok(root);}
    private static async Task<IResult> History(HttpContext ctx,AppDb db,Guid id)
    {var t=await TaxRuleReferences.Tenant(ctx,db);var root=await TaxRuleApplication.Read(db,t,id);await TaxRuleReferences.Action(ctx,db,t,root["company_id"] as Guid?,"tax-rules.read");var items=(IEnumerable<Dictionary<string,object?>>)root["versions"]!;return Results.Ok(new{items});}
    private static async Task<IResult> Permissions(HttpContext ctx,AppDb db,Guid id)
    {var t=await TaxRuleReferences.Tenant(ctx,db);var root=await TaxRuleApplication.Read(db,t,id);var permissions=await TaxRuleReferences.Permissions(ctx,db,t,root["company_id"] as Guid?);Require(permissions.Length>0,"forbidden",403);return Results.Ok(new{permissions});}
    private static async Task<IResult> Conflicts(HttpContext ctx,AppDb db,Guid id)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db);var root=TaxRuleApplication.Snapshot(await TaxRuleApplication.Read(db,t,id));await TaxRuleReferences.Action(ctx,db,t,root.CompanyId,"tax-rules.read");
        var versionId=QueryId(ctx,"version_id");Require(versionId!=null,"tax_field_required",field:"version_id");var version=root.Versions.SingleOrDefault(v=>v.Id==versionId)??throw new ApiException(404,"tax_rule_version_not_found","version_id");
        await TaxRuleReferences.RulesetLock(db,t,root.CountryId,root.TaxTypeId,version.OperationType);
        // Non esporre payload o condizioni di altre aziende senza autorizzazione.
        var conflicts=await TaxRuleApplication.Conflicts(db,root,version);var visible=new List<object>();foreach(var c in conflicts)if(await TaxRuleReferences.Allowed(ctx,db,t,c.CompanyId,"tax-rules.read"))visible.Add(new{ruleId=c.RuleId,versionId=c.Version.Id,priority=c.Version.Priority,validFrom=c.Version.ValidFrom,validTo=c.Version.ValidTo,companyId=c.CompanyId});
        return Results.Ok(new{conflicts=visible,hasRestrictedConflicts=visible.Count!=conflicts.Count});
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db);var company=QueryId(ctx,"company_id");var companies=await TaxRuleReferences.Companies(ctx,db,t,"tax-rules");var allowed=companies.Where(c=>((string[])c["permissions"]!).Contains("read")).Select(c=>(Guid)c["id"]!).ToArray();var shared=await TaxRuleReferences.Allowed(ctx,db,t,null,"tax-rules.read");
        Require(shared||allowed.Length>0,"forbidden",403);if(company!=null)Require(allowed.Contains(company.Value),"forbidden",403);
        var country=QueryId(ctx,"country_id");var type=QueryId(ctx,"tax_type_id");var date=QueryDate(ctx);var search=Search(ctx);var status=ctx.Request.Query["status"].ToString();Require(status is "" or "DRAFT" or "PUBLISHED" or "WITHDRAWN","tax_invalid_field",field:"status");var(page,size)=Paging(ctx);
        const string filter=" WHERE tenant_id=@t AND ((company_id IS NULL AND @shared) OR company_id=ANY(@companies::uuid[])) AND (@company::uuid IS NULL OR company_id=@company) AND (@country::uuid IS NULL OR country_id=@country) AND (@type::uuid IS NULL OR tax_type_id=@type) AND (@search='' OR strpos(lower(code||' '||name),lower(@search))>0) AND ((@status='' AND @date::date IS NULL) OR EXISTS(SELECT 1 FROM taxmanagement.tax_rule_versions v WHERE v.tenant_id=r.tenant_id AND v.tax_rule_id=r.id AND (@status='' OR v.status=@status) AND (@date::date IS NULL OR (v.valid_from<=@date AND (v.valid_to IS NULL OR v.valid_to>=@date)))))";
        var args=new (string Name,object? Value)[]{("t",t),("shared",shared),("companies",allowed),("company",company),("country",country),("type",type),("search",search),("status",status),("date",date),("n",size),("offset",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_rules r"+filter,args));var rows=await Rows(db,"SELECT id FROM taxmanagement.tax_rules r"+filter+" ORDER BY lower(code),id LIMIT @n OFFSET @offset",args);
        var items=new List<Dictionary<string,object?>>();foreach(var row in rows)items.Add(await TaxRuleApplication.Read(db,t,(Guid)row["id"]!));return Results.Ok(new{items,total,page,pageSize=size,has_more=(long)page*size<total});
    }
    private static async Task<IResult> Lookups(HttpContext ctx,AppDb db)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db);var permissions=await TaxRuleReferences.Permissions(ctx,db,t,null);var companies=await TaxRuleReferences.Companies(ctx,db,t,"tax-rules");Require(permissions.Length>0||companies.Count>0,"forbidden",403);
        var countries=await TaxRuleReferences.Bounded(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country ORDER BY name,id");var types=await TaxRuleReferences.Bounded(db,"SELECT id,code,name,is_active FROM taxmanagement.tax_types ORDER BY code,id");
        var codes=await TaxRuleReferences.Bounded(db,"SELECT id,country_id,tax_type_id,code,name,is_active,version FROM taxmanagement.tax_codes WHERE tenant_id=@t ORDER BY code,id",("t",t));
        var itemClassifications=await TaxRuleReferences.Bounded(db,"SELECT id,country_id,tax_type_id,code,name,is_active FROM taxmanagement.item_tax_classifications WHERE tenant_id=@t ORDER BY code,id",("t",t));var partnerClassifications=await TaxRuleReferences.Bounded(db,"SELECT id,country_id,tax_type_id,code,name,is_active FROM taxmanagement.partner_tax_classifications WHERE tenant_id=@t ORDER BY code,id",("t",t));var regimes=await TaxRuleReferences.Bounded(db,"SELECT id,country_id,tax_type_id,code,name,is_active,is_supported,valid_from,valid_to FROM taxmanagement.tax_regimes ORDER BY code,id");
        return Results.Ok(new{countries,types,companies,codes,itemClassifications,partnerClassifications,regimes,fields=TaxConditionFields.All,operators=new[]{"EQUALS","NOT_EQUALS","IN","NOT_IN","IS_TRUE","IS_FALSE"},permissions});
    }
    private static async Task<IResult> Install(HttpContext ctx,AppDb db,JsonElement body)
    {
        var t=await TaxRuleReferences.Tenant(ctx,db);var input=Object(body,"validFrom","company_id");var from=Date(input,"validFrom");var company=Id(input,"company_id");await TaxRuleReferences.Action(ctx,db,t,company,"tax-rules.install_templates");
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended(@k,0))",("k",$"tax-rule-templates:{t:D}:{company?.ToString("D")??"shared"}"));
        Require(from>=new DateOnly(2026,11,26),"tax_rule_template_prerequisite",field:"validFrom");
        var country=await db.Scalar("SELECT id FROM foundation.country WHERE iso_code='IT' AND is_enabled");var type=await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT' AND is_active");Require(country is Guid&&type is Guid,"tax_rule_template_prerequisite",409,"country_id");
        var countryId=(Guid)country!;var typeId=(Guid)type!;
        async Task<Guid> Prerequisite(string table,string code,bool regime=false){var id=await db.Scalar("SELECT id FROM taxmanagement."+table+" WHERE "+(regime?"":"tenant_id=@t AND ")+"country_id=@c AND tax_type_id=@type AND code=@code AND is_active"+(regime?" AND is_supported AND valid_from<=@date AND (valid_to IS NULL OR valid_to>=@date)":" FOR SHARE"),("t",t),("c",countryId),("type",typeId),("code",code),("date",from));Require(id is Guid,"tax_rule_template_prerequisite",409,code);return (Guid)id!;}
        var taxCode=await Prerequisite("tax_codes","VAT_STANDARD");var goods=await Prerequisite("item_tax_classifications","GENERAL_GOODS");var services=await Prerequisite("item_tax_classifications","GENERAL_SERVICES");var taxable=await Prerequisite("partner_tax_classifications","TAXABLE_PERSON");var privatePerson=await Prerequisite("partner_tax_classifications","NON_TAXABLE_PERSON");var regime=await Prerequisite("tax_regimes","ORDINARY",true);
        var codes=await TaxRuleReferences.Codes(db,t,new[]{taxCode},countryId,typeId);Require(codes.ContainsKey(taxCode),"tax_rule_template_prerequisite",409,"VAT_STANDARD");
        TaxFiscalVersion fiscal;try{fiscal=codes[taxCode].Aggregate.ResolveVersionAt(from,true);}catch(ApiException){throw new ApiException(409,"tax_rule_template_prerequisite","VAT_STANDARD");}
        Require(fiscal.Treatment=="TAXABLE"&&fiscal.Rate>0&&fiscal.TaxNatureCodeId==null,"tax_rule_template_prerequisite",409,"VAT_STANDARD");
        var created=new List<Dictionary<string,object?>>();var existing=new List<Guid>();
        foreach(var template in new[]{(Op:"SALE",Kind:"GOOD",B2B:true),(Op:"SALE",Kind:"GOOD",B2B:false),(Op:"SALE",Kind:"SERVICE",B2B:true),(Op:"SALE",Kind:"SERVICE",B2B:false),(Op:"PURCHASE",Kind:"GOOD",B2B:true),(Op:"PURCHASE",Kind:"SERVICE",B2B:true)}) {
            var code=$"IT_ORDINARY_{template.Op}_{template.Kind}_{(template.B2B?"B2B":"B2C")}";
            var id=await db.Scalar("SELECT id FROM taxmanagement.tax_rules WHERE tenant_id=@t AND company_id IS NOT DISTINCT FROM @company::uuid AND country_id=@c AND tax_type_id=@type AND lower(code)=lower(@code)",("t",t),("company",company),("c",countryId),("type",typeId),("code",code));if(id is Guid present){existing.Add(present);continue;}
            var conditions=new List<object>();void Eq(string field,object value)=>conditions.Add(new{field,@operator="EQUALS",value});
            Eq("company.taxRegime",regime);Eq("item.nature",template.Kind);Eq("item.taxClassification",template.Kind=="GOOD"?goods:services);Eq("partner.taxClassification",template.B2B?taxable:privatePerson);Eq("partner.actingAsTaxablePerson",template.B2B);
            Eq("transaction.operationType",template.Op);Eq("transaction.territorialScope","DOMESTIC");Eq("transaction.operationCategory",template.Kind=="GOOD"?"ORDINARY_MOVABLE_GOODS":"GENERAL_SERVICES");Eq("transaction.specialTaxTreatment","NONE");Eq("transaction.ordinaryVatTerritoryConfirmed",true);Eq("company.registrationCountry",countryId);Eq("company.establishmentCountry",countryId);Eq("partner.establishmentCountry",countryId);
            if(template.Kind=="GOOD"){Eq("transaction.dispatchCountry",countryId);Eq("transaction.destinationCountry",countryId);Eq("transaction.goodsCustomsStatus","NATIONAL_OR_UNION");}else Eq("transaction.serviceLocationCountry",countryId);
            var legal=from.Year<=2026?"DPR 633/1972 art. "+(template.Kind=="GOOD"?"7-bis":"7-ter"):"TU allegato D.Lgs. 10/2026 art. "+(template.Kind=="GOOD"?"15":"17");
            var payload=JsonSerializer.SerializeToElement(new{values=new{company_id=company,country_id=countryId,tax_type_id=typeId,code,name=code,description=(string?)null},versions=new[]{new{values=new{tax_code_id=taxCode,priority=100,operation_type=template.Op,legal_reference=legal,valid_from=from.ToString("yyyy-MM-dd"),valid_to=from.Year<=2026?"2026-12-31":(string?)null},conditions}}});
            created.Add(await TaxRuleApplication.Create(ctx,db,t,payload,"install_templates"));
        }
        return Results.Ok(new{created,existing});
    }
}
