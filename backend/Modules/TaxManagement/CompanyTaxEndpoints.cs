using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.CompanyTaxConfiguration;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
namespace Enginia360.Modules.TaxManagement;

public static class CompanyTaxEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/regimes",ListRegimes);
        app.MapGet("/api/tax/company-lookups",Lookups);
        app.MapGet("/api/tax/companies/{companyId:guid}/permissions",async(HttpContext ctx,AppDb db,Guid companyId)=>{
            var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);await CompanyTaxApplication.Company(db,tenant,companyId,false);
            return Results.Ok(new {permissions=await CompanyTaxAuthorization.Permissions(ctx,db,tenant,companyId)});
        });
        app.MapGet("/api/tax/companies/{companyId:guid}/configurations",async(HttpContext ctx,AppDb db,Guid companyId)=>{
            var tenant=await Gate(ctx,db,companyId,"read");await CompanyTaxApplication.Lock(db,tenant,false);
            var ids=await Rows(db,"SELECT id FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND company_id=@c ORDER BY tax_type_id,id",("t",tenant),("c",companyId));
            var items=new List<Dictionary<string,object?>>();foreach(var id in ids)items.Add(await CompanyTaxApplication.Read(db,tenant,(Guid)id["id"]!));return Results.Ok(new {items});
        });
        app.MapPost("/api/tax/companies/{companyId:guid}/configurations",async(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)=>{
            var tenant=await Gate(ctx,db,companyId,"create");return Results.Json(await CompanyTaxApplication.Create(ctx,db,tenant,companyId,CompanyTaxInput.Create(body)),statusCode:201);
        });
        const string root="/api/tax/company-configurations/{id:guid}";
        app.MapPut(root,async(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>{
            var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);var input=CompanyTaxInput.Update(body);
            return Results.Ok(await CompanyTaxApplication.Mutate(ctx,db,tenant,id,"update",input.ExpectedVersion,taxCode:input.TaxCode));
        });
        app.MapGet(root,async(HttpContext ctx,AppDb db,Guid id)=>{
            var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);await CompanyTaxApplication.Lock(db,tenant,false);var aggregate=await CompanyTaxApplication.Load(db,tenant,id);
            await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,aggregate.CompanyId,"read");await CompanyTaxApplication.Company(db,tenant,aggregate.CompanyId,false);
            return Results.Ok(await CompanyTaxApplication.Read(db,tenant,id));
        });
        foreach(var command in new[]{"activate","suspend"}) {
            var action=command;app.MapPost(root+"/"+action,async(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>{
                var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);var input=CompanyTaxInput.Object(body,"expectedVersion");
                return Results.Ok(await CompanyTaxApplication.Mutate(ctx,db,tenant,id,action,CompanyTaxInput.Version(input)));
            });
        }
        app.MapPost(root+"/registrations",async(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>{
            var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);var input=CompanyTaxInput.Object(body,"values","profiles","expectedVersion");
            var payload=JsonSerializer.SerializeToElement(input.Where(x=>x.Key!="expectedVersion").ToDictionary(x=>x.Key,x=>x.Value));
            return Results.Json(await CompanyTaxApplication.Mutate(ctx,db,tenant,id,"register",CompanyTaxInput.Version(input),registration:CompanyTaxInput.Registration(payload)),statusCode:201);
        });
        app.MapPost(root+"/registrations/{registrationId:guid}/close",async(HttpContext ctx,AppDb db,Guid id,Guid registrationId,JsonElement body)=>{
            var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);var input=CompanyTaxInput.Object(body,"valid_to","expectedVersion");
            return Results.Ok(await CompanyTaxApplication.Mutate(ctx,db,tenant,id,"close",CompanyTaxInput.Version(input),registrationId,end:CompanyTaxInput.Date(input,"valid_to")));
        });
        foreach(var scheduling in new[]{false,true}) {
            var schedule=scheduling;app.MapPost(root+"/registrations/{registrationId:guid}/regimes"+(schedule?"/schedule":""),async(HttpContext ctx,AppDb db,Guid id,Guid registrationId,JsonElement body)=>{
                var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);var input=CompanyTaxInput.Object(body,"values","expectedVersion");
                return Results.Json(await CompanyTaxApplication.Mutate(ctx,db,tenant,id,schedule?"schedule_regime":"assign_regime",CompanyTaxInput.Version(input),registrationId,profile:CompanyTaxInput.Profile(CompanyTaxInput.Required(input,"values"))),statusCode:schedule?200:201);
            });
        }
        app.MapGet("/api/tax/companies/{companyId:guid}/registrations",async(HttpContext ctx,AppDb db,Guid companyId)=>{
            var tenant=await Gate(ctx,db,companyId,"read");var date=CompanyTaxInput.Date(ctx.Request.Query["date"].ToString(),"date");var type=QueryId(ctx,"tax_type_id");var forNewUse=NewUse(ctx);
            return Results.Ok(new {items=await new CompanyTaxProfileResolver(db).List(tenant,companyId,type,date,forNewUse)});
        });
        app.MapGet("/api/tax/companies/{companyId:guid}/registrations/{registrationId:guid}/resolve",async(HttpContext ctx,AppDb db,Guid companyId,Guid registrationId)=>{
            var tenant=await Gate(ctx,db,companyId,"read");var date=CompanyTaxInput.Date(ctx.Request.Query["date"].ToString(),"date");return Results.Ok(await new CompanyTaxProfileResolver(db).Resolve(tenant,companyId,registrationId,date,NewUse(ctx)));
        });
    }
    private static async Task<Guid> Gate(HttpContext ctx,AppDb db,Guid company,string action)
    {
        var tenant=await CompanyTaxAuthorization.Tenant(ctx,db);await CompanyTaxAuthorization.RequireAction(ctx,db,tenant,company,action);await CompanyTaxApplication.Company(db,tenant,company,false);return tenant;
    }
    private static bool NewUse(HttpContext ctx)
    {
        if(!ctx.Request.Query.ContainsKey("forNewUse"))return false;
        Require(bool.TryParse(ctx.Request.Query["forNewUse"],out var value),"invalid_field",field:"forNewUse");return value;
    }
    private static Guid? QueryId(HttpContext ctx,string key)
    {
        var value=ctx.Request.Query[key].ToString();if(value.Length==0)return null;Require(Guid.TryParse(value,out var id) && id!=Guid.Empty,"invalid_id",field:key);return id;
    }
    private static int Number(HttpContext ctx,string key,int fallback,int max)
    {
        var text=ctx.Request.Query[key].ToString();if(text.Length==0)return fallback;Require(int.TryParse(text,System.Globalization.NumberStyles.None,System.Globalization.CultureInfo.InvariantCulture,out var n) && n>=1 && n<=max,"invalid_paging",field:key);return n;
    }
    private static async Task<IResult> ListRegimes(HttpContext ctx,AppDb db)
    {
        await Security.Authorize(ctx,"tax-regimes.read");await CompanyTaxAuthorization.Tenant(ctx,db);
        var page=Number(ctx,"page",1,100000);var size=Number(ctx,"pageSize",25,100);var country=QueryId(ctx,"country_id");var type=QueryId(ctx,"tax_type_id");
        var search=ctx.Request.Query["search"].ToString();Require(search.Length<=200 && !search.Any(c=>char.IsControl(c) || char.IsSurrogate(c)),"invalid_search",field:"search");
        bool? active=null;if(ctx.Request.Query.ContainsKey("is_active")){Require(bool.TryParse(ctx.Request.Query["is_active"],out var a),"invalid_field",field:"is_active");active=a;}
        const string where=" WHERE (@country::uuid IS NULL OR g.country_id=@country) AND (@type::uuid IS NULL OR g.tax_type_id=@type) AND (@active::boolean IS NULL OR g.is_active=@active) AND (@s='' OR strpos(lower(g.code||' '||g.name),lower(@s))>0)";
        var args=new (string Name,object? Value)[]{("country",country),("type",type),("active",active),("s",search),("size",size),("offset",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_regimes g"+where,args));
        var items=await Rows(db,"SELECT g.*,c.iso_code AS country_iso_code,t.code AS tax_type_code FROM taxmanagement.tax_regimes g JOIN foundation.country c ON c.id=g.country_id JOIN taxmanagement.tax_types t ON t.id=g.tax_type_id"+where+" ORDER BY c.iso_code,g.code,g.id LIMIT @size OFFSET @offset",args);
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> Lookups(HttpContext ctx,AppDb db)
    {
        var granted=false;foreach(var p in CompanyTaxAuthorization.Actions.Select(x=>CompanyTaxAuthorization.Resource+"."+x).Prepend("tax-regimes.read")) {
            try {await Security.Authorize(ctx,p);granted=true;break;}catch(ApiException e) when(e.Status==403){}
        }
        Require(granted,"forbidden",403);await CompanyTaxAuthorization.Tenant(ctx,db);
        var countries=await Rows(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country WHERE iso_code IN ('IT','DE','FR') ORDER BY name,id LIMIT 10001");
        var types=await Rows(db,"SELECT id,code,name,is_active FROM taxmanagement.tax_types ORDER BY code,id LIMIT 10001");
        var regimes=await Rows(db,"SELECT g.*,c.iso_code AS country_iso_code,t.code AS tax_type_code FROM taxmanagement.tax_regimes g JOIN foundation.country c ON c.id=g.country_id JOIN taxmanagement.tax_types t ON t.id=g.tax_type_id ORDER BY c.iso_code,g.code,g.id LIMIT 10001");
        Require(countries.Count<=10000 && types.Count<=10000 && regimes.Count<=10000,"lookup_limit_exceeded",409);
        foreach(var c in countries){var iso=(string)c["iso_code"]!;c["is_supported"]=CompanyTaxJurisdiction.SupportedCountries.Contains(iso,StringComparer.Ordinal);c["identifier_validation"]=CompanyTaxJurisdiction.ValidationLevel(iso);}
        var registrationTypesByCountry=countries.ToDictionary(c=>(string)c["iso_code"]!,c=>CompanyTaxJurisdiction.RegistrationTypes((string)c["iso_code"]!));
        return Results.Ok(new {countries,types,regimes,registrationTypesByCountry});
    }
}
