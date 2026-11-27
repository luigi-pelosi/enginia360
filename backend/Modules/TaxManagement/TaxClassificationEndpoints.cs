using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.ClassificationTimeline;

namespace Enginia360.Modules.TaxManagement;

public static class TaxClassificationEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/classification-lookups",Lookups);
        foreach(var k in new[]{ClassificationKind.Item,ClassificationKind.Partner}) {
            var kind=k;var path="/api/tax/"+kind.Name+"-classifications";
            app.MapGet(path,(HttpContext ctx,AppDb db)=>List(ctx,db,kind));
            app.MapGet(path+"/{id:guid}",(HttpContext ctx,AppDb db,Guid id)=>Get(ctx,db,kind,id));
            app.MapPost(path,(HttpContext ctx,AppDb db,JsonElement body)=>Create(ctx,db,kind,body));
            app.MapPut(path+"/{id:guid}",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Update(ctx,db,kind,id,body));
            app.MapPost(path+"/{id:guid}/deactivate",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>SetActive(ctx,db,kind,id,body,false));
            app.MapPost(path+"/{id:guid}/reactivate",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>SetActive(ctx,db,kind,id,body,true));
            app.MapPost(path+"/templates/install",(HttpContext ctx,AppDb db,JsonElement body)=>Install(ctx,db,kind,body));
            var profiles="/api/tax/"+kind.Subjects+"/{subjectId:guid}/profiles";
            app.MapGet(profiles,(HttpContext ctx,AppDb db,Guid subjectId)=>GetProfiles(ctx,db,kind,subjectId));
            app.MapPost(profiles,(HttpContext ctx,AppDb db,Guid subjectId,JsonElement body)=>WriteProfile(ctx,db,kind,subjectId,body,false));
            app.MapPost(profiles+"/schedule",(HttpContext ctx,AppDb db,Guid subjectId,JsonElement body)=>WriteProfile(ctx,db,kind,subjectId,body,true));
            app.MapGet(profiles+"/resolve",(HttpContext ctx,AppDb db,Guid subjectId)=>Resolve(ctx,db,kind,subjectId));
        }
    }
    private static Task<Guid> ClassGate(HttpContext ctx,AppDb db,ClassificationKind kind,string action)=>Gate(ctx,db,kind.ClassificationResource+"."+action,kind.ClassificationResource);
    private static async Task<Guid> ProfileGate(HttpContext ctx,AppDb db,ClassificationKind kind,string action)
    {
        var tenant=await Gate(ctx,db,kind.ProfileResource+"."+action,kind.ProfileResource);
        await Security.Authorize(ctx,kind.BaseRead);return tenant;
    }
    private static int Number(HttpContext ctx,string field,int fallback,int max)
    {
        var value=ctx.Request.Query[field].ToString();if(value.Length==0)return fallback;
        Require(int.TryParse(value,NumberStyles.None,CultureInfo.InvariantCulture,out var n) && n>=1 && n<=max,"tax_classification_invalid_paging",field:field);return n;
    }
    private static (int Page,int Size) Paging(HttpContext ctx)=>(Number(ctx,"page",1,100000),Number(ctx,"pageSize",25,100));
    private static Guid? QueryId(HttpContext ctx,string field,bool required=false)
    {
        var value=ctx.Request.Query[field].ToString();
        if(value.Length==0 && !required)return null;
        Require(Guid.TryParse(value,out var id) && id!=Guid.Empty,"tax_classification_invalid_id",field:field);return id;
    }
    private static async Task<IResult> Lookups(HttpContext ctx,AppDb db)
    {
        var kind=ClassificationKind.Parse(ctx.Request.Query["kind"].ToString());
        string? granted=null;
        foreach(var p in new[]{kind.ClassificationResource+".read",kind.ClassificationResource+".create",kind.ClassificationResource+".update",kind.ClassificationResource+".install_templates",kind.ProfileResource+".read",kind.ProfileResource+".assign",kind.ProfileResource+".schedule"}) {
            try {await Security.Authorize(ctx,p);granted=p;break;}catch(ApiException e) when(e.Status==403) {}
        }
        Require(granted!=null,"forbidden",403);
        var tenant=await Gate(ctx,db,granted!,kind.ClassificationResource);
        var countries=await Rows(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country ORDER BY name,id LIMIT 10001");
        var types=await Rows(db,"SELECT id,code,name,is_active FROM taxmanagement.tax_types ORDER BY code,id LIMIT 10001");
        var classifications=await Rows(db,"SELECT c.*,g.iso_code AS country_iso_code,t.code AS tax_type_code FROM taxmanagement."+kind.ClassificationTable+" c JOIN foundation.country g ON g.id=c.country_id JOIN taxmanagement.tax_types t ON t.id=c.tax_type_id WHERE c.tenant_id=@t ORDER BY lower(c.code),c.id LIMIT 10001",("t",tenant));
        Require(countries.Count<=10000 && types.Count<=10000 && classifications.Count<=10000,"tax_classification_lookup_limit_exceeded",409,"kind");
        return Results.Ok(new {countries,types,classifications});
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db,ClassificationKind kind)
    {
        var tenant=await ClassGate(ctx,db,kind,"read");var (page,size)=Paging(ctx);
        var search=ctx.Request.Query["search"].ToString().Trim();Require(search.Length<=200 && !search.Any(char.IsControl),"tax_classification_invalid_search",field:"search");
        var country=QueryId(ctx,"country_id");var type=QueryId(ctx,"tax_type_id");bool? active=null;
        if(ctx.Request.Query.ContainsKey("is_active")) {Require(bool.TryParse(ctx.Request.Query["is_active"],out var flag),"tax_classification_invalid_field",field:"is_active");active=flag;}
        const string where=" WHERE c.tenant_id=@t AND (@s='' OR strpos(lower(c.code||' '||c.name),lower(@s))>0) AND (@country::uuid IS NULL OR c.country_id=@country) AND (@type::uuid IS NULL OR c.tax_type_id=@type) AND (@active::boolean IS NULL OR c.is_active=@active)";
        var args=new (string Name,object? Value)[]{("t",tenant),("s",search),("country",country),("type",type),("active",active),("n",size),("o",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement."+kind.ClassificationTable+" c"+where,args));
        var items=await Rows(db,"SELECT c.*,g.iso_code AS country_iso_code,t.code AS tax_type_code FROM taxmanagement."+kind.ClassificationTable+" c JOIN foundation.country g ON g.id=c.country_id JOIN taxmanagement.tax_types t ON t.id=c.tax_type_id"+where+" ORDER BY lower(c.code),c.id LIMIT @n OFFSET @o",args);
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> Get(HttpContext ctx,AppDb db,ClassificationKind kind,Guid id)
    {var tenant=await ClassGate(ctx,db,kind,"read");return Results.Ok(await Classification(db,kind,tenant,id));}
    private static async Task<Dictionary<string,object?>> CreateCore(HttpContext ctx,AppDb db,ClassificationKind kind,Guid tenant,Dictionary<string,JsonElement> values,string action)
    {
        var code=ClassificationInput.Code(values);var name=ClassificationInput.Text(values,"name",150,true)!;var description=ClassificationInput.Text(values,"description",10000);
        var country=ClassificationInput.Id(values,"country_id","tax_classification");var type=ClassificationInput.Id(values,"tax_type_id","tax_classification");
        await ValidateScope(db,country,type);var id=Guid.NewGuid();
        try {
            await db.Execute("INSERT INTO taxmanagement."+kind.ClassificationTable+"(id,tenant_id,country_id,tax_type_id,code,name,description,is_active,version,created_at,updated_at) VALUES(@id,@t,@country,@type,@code,@name,@description::text,true,1,clock_timestamp(),clock_timestamp())",("id",id),("t",tenant),("country",country),("type",type),("code",code),("name",name),("description",description));
        }catch(PostgresException e) when(e.SqlState=="23505") {throw new ApiException(409,"tax_classification_code_exists","code");}
        var after=await Classification(db,kind,tenant,id);await db.Audit(Security.State(ctx).User.Id,tenant,action,kind.ClassificationResource,id,new {before=(object?)null,after});return after;
    }
    private static async Task<IResult> Create(HttpContext ctx,AppDb db,ClassificationKind kind,JsonElement body)
    {
        var tenant=await ClassGate(ctx,db,kind,"create");var input=ClassificationInput.Object(body,"tax_classification","values");
        var values=ClassificationInput.Object(ClassificationInput.Required(input,"values","tax_classification"),"tax_classification","code","name","description","country_id","tax_type_id");
        return Results.Json(await CreateCore(ctx,db,kind,tenant,values,"create"),statusCode:201);
    }
    private static async Task<IResult> Update(HttpContext ctx,AppDb db,ClassificationKind kind,Guid id,JsonElement body)
    {
        var tenant=await ClassGate(ctx,db,kind,"update");var input=ClassificationInput.Object(body,"tax_classification","values","expectedVersion");
        var values=ClassificationInput.Object(ClassificationInput.Required(input,"values","tax_classification"),"tax_classification","name","description");Require(values.Count>0,"tax_classification_empty_update",field:"values");
        var before=await Classification(db,kind,tenant,id,true);TaxClassificationApplication.Identity(before).CheckMutation(ClassificationInput.Revision(input,"tax_classification"));
        var name=values.ContainsKey("name")?ClassificationInput.Text(values,"name",150,true):(string)before["name"]!;
        var description=values.ContainsKey("description")?ClassificationInput.Text(values,"description",10000):before["description"] as string;
        await db.Execute("UPDATE taxmanagement."+kind.ClassificationTable+" SET name=@name,description=@description::text,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",("name",name),("description",description),("t",tenant),("id",id));
        var after=await Classification(db,kind,tenant,id);await db.Audit(Security.State(ctx).User.Id,tenant,"update",kind.ClassificationResource,id,new {before=new {name=before["name"],description=before["description"],version=before["version"]},after=new {name=after["name"],description=after["description"],version=after["version"]}});return Results.Ok(after);
    }
    private static async Task<IResult> SetActive(HttpContext ctx,AppDb db,ClassificationKind kind,Guid id,JsonElement body,bool active)
    {
        var action=active?"reactivate":"deactivate";var tenant=await ClassGate(ctx,db,kind,action);var input=ClassificationInput.Object(body,"tax_classification","expectedVersion");
        var before=await Classification(db,kind,tenant,id,true);TaxClassificationApplication.Identity(before).CheckMutation(ClassificationInput.Revision(input,"tax_classification"),active);
        if((bool)before["is_active"]! == active)return Results.Ok(before);
        await db.Execute("UPDATE taxmanagement."+kind.ClassificationTable+" SET is_active=@active,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",("active",active),("t",tenant),("id",id));
        var after=await Classification(db,kind,tenant,id);await db.Audit(Security.State(ctx).User.Id,tenant,action,kind.ClassificationResource,id,new {before=new {is_active=before["is_active"],version=before["version"]},after=new {is_active=after["is_active"],version=after["version"]}});return Results.Ok(after);
    }
    private static async Task<IResult> Install(HttpContext ctx,AppDb db,ClassificationKind kind,JsonElement body)
    {
        var tenant=await ClassGate(ctx,db,kind,"install_templates");var input=ClassificationInput.Object(body,"tax_classification","country_id","tax_type_id");
        var country=ClassificationInput.Id(input,"country_id","tax_classification");var type=ClassificationInput.Id(input,"tax_type_id","tax_classification");await ValidateScope(db,country,type);
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended(@key,0))",("key","tax-classification-templates:"+kind.Name+":"+tenant+":"+country+":"+type));
        var installed=0;var skipped=0;
        foreach(var template in ClassificationTemplates.For(kind)) {
            if(await db.Scalar("SELECT id FROM taxmanagement."+kind.ClassificationTable+" WHERE tenant_id=@t AND country_id=@country AND tax_type_id=@type AND lower(code)=lower(@code)",("t",tenant),("country",country),("type",type),("code",template.Code)) is Guid) {skipped++;continue;}
            var values=ClassificationInput.Object(JsonSerializer.SerializeToElement(new {code=template.Code,name=template.Name,country_id=country,tax_type_id=type}),"tax_classification","code","name","country_id","tax_type_id");
            await CreateCore(ctx,db,kind,tenant,values,"install_template");installed++;
        }
        return Results.Ok(new {installed,skipped});
    }
    private static async Task<object> ProfilePage(HttpContext ctx,AppDb db,ClassificationKind kind,Guid tenant,Guid subject)
    {
        var (page,size)=Paging(ctx);var country=QueryId(ctx,"country_id");var type=QueryId(ctx,"tax_type_id");
        var where=" WHERE p.tenant_id=@t AND p."+kind.SubjectColumn+"=@subject AND (@country::uuid IS NULL OR p.country_id=@country) AND (@type::uuid IS NULL OR p.tax_type_id=@type)";
        var args=new (string Name,object? Value)[]{("t",tenant),("subject",subject),("country",country),("type",type),("n",size),("o",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement."+kind.ProfileTable+" p"+where,args));
        var version=Convert.ToInt64(await db.Scalar("SELECT coalesce(max(revision),0) FROM taxmanagement."+kind.ProfileTable+" WHERE tenant_id=@t AND "+kind.SubjectColumn+"=@subject",("t",tenant),("subject",subject)));
        var items=await Rows(db,"SELECT p.*,c.code AS classification_code,c.name AS classification_name,c.is_active AS classification_is_active FROM taxmanagement."+kind.ProfileTable+" p JOIN taxmanagement."+kind.ClassificationTable+" c ON c.tenant_id=p.tenant_id AND c.id=p."+kind.ClassificationColumn+where+" ORDER BY p.valid_from,p.revision LIMIT @n OFFSET @o",args);
        return new {items,total,page,pageSize=size,version};
    }
    private static async Task<IResult> GetProfiles(HttpContext ctx,AppDb db,ClassificationKind kind,Guid subject)
    {
        var tenant=await ProfileGate(ctx,db,kind,"read");await ClassificationSubjectReference.Require(db,kind,tenant,subject,false);await Lock(db,kind,tenant,subject,false);
        return Results.Ok(await ProfilePage(ctx,db,kind,tenant,subject));
    }
    private static async Task<IResult> WriteProfile(HttpContext ctx,AppDb db,ClassificationKind kind,Guid subject,JsonElement body,bool schedule)
    {
        var tenant=await ProfileGate(ctx,db,kind,schedule?"schedule":"assign");
        var input=ClassificationInput.Object(body,"tax_profile","values","expectedVersion");var next=ClassificationInput.Profile(ClassificationInput.Required(input,"values","tax_profile"),kind);var expected=ClassificationInput.Revision(input,"tax_profile");
        // Validare i filtri della risposta prima della modifica: una query malformata non deve salvare dati.
        _=Paging(ctx);_=QueryId(ctx,"country_id");_=QueryId(ctx,"tax_type_id");
        await ClassificationSubjectReference.Require(db,kind,tenant,subject,true);await Lock(db,kind,tenant,subject);
        await Assign(ctx,db,kind,tenant,subject,next,expected,schedule);
        return Results.Json(await ProfilePage(ctx,db,kind,tenant,subject),statusCode:schedule?200:201);
    }
    private static async Task<IResult> Resolve(HttpContext ctx,AppDb db,ClassificationKind kind,Guid subject)
    {
        var tenant=await ProfileGate(ctx,db,kind,"read");var country=QueryId(ctx,"country_id",true)!.Value;var type=QueryId(ctx,"tax_type_id",true)!.Value;var date=ClassificationInput.Date(ctx.Request.Query["date"].ToString(),"date");
        ITaxClassificationResolver resolver=new TaxClassificationResolver(db);
        return Results.Ok(kind==ClassificationKind.Item?await resolver.ResolveItem(tenant,subject,country,type,date):await resolver.ResolvePartner(tenant,subject,country,type,date));
    }
}
