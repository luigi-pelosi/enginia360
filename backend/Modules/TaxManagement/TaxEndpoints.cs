using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;

namespace Enginia360.Modules.TaxManagement;

public static class TaxEndpoints
{
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/tax/countries",Countries);
        app.MapGet("/api/tax/lookups",Lookups);
        app.MapGet("/api/tax/types",Types);
        app.MapGet("/api/tax/nature-codes",Natures);
        app.MapGet("/api/tax/codes",List);
        app.MapGet("/api/tax/codes/{id:guid}",Get);
        app.MapGet("/api/tax/codes/{id:guid}/versions",History);
        app.MapGet("/api/tax/codes/{id:guid}/audit",AuditList);
        app.MapGet("/api/tax/codes/{id:guid}/resolve",Resolve);
        app.MapPost("/api/tax/codes",Create);
        app.MapPut("/api/tax/codes/{id:guid}",Update);
        app.MapPost("/api/tax/codes/{id:guid}/versions",Schedule);
        app.MapPost("/api/tax/codes/{id:guid}/deactivate",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>SetActive(ctx,db,id,body,false));
        app.MapPost("/api/tax/codes/{id:guid}/reactivate",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>SetActive(ctx,db,id,body,true));
        app.MapPost("/api/tax/codes/templates/install",Install);
    }
    private static async Task<Guid> Gate(HttpContext ctx,AppDb db,string permission)
    {
        await Security.Authorize(ctx,permission);
        TaxRules.Require(db.Database.CurrentTransaction!=null,"server_error",500);
        var tenant=Security.State(ctx).Tenant(ctx,"tax-codes");
        TaxRules.Require(tenant!=null,"tax_tenant_required");
        TaxRules.Require(await db.Scalar("SELECT id FROM foundation.tenant WHERE id=@t AND is_enabled",("t",tenant)) is Guid,"not_found",404);
        return tenant!.Value;
    }
    private static async Task<List<Dictionary<string,object?>>> Rows(AppDb db,string sql,params (string Name,object? Value)[] parameters)
    {
        var rows=new List<Dictionary<string,object?>>();
        await using var cmd=await db.Command(sql,parameters);await using var reader=await cmd.ExecuteReaderAsync();
        while(await reader.ReadAsync()) {
            var row=new Dictionary<string,object?>();
            for(var i=0;i<reader.FieldCount;i++) {
                object? value=reader.IsDBNull(i)?null:reader.GetValue(i);
                if(value is decimal rate) value=TaxRules.RateText(rate);
                if(reader.GetName(i)=="details" && value is string json) value=JsonSerializer.Deserialize<JsonElement>(json);
                row[reader.GetName(i)]=value;
            }
            rows.Add(row);
        }
        return rows;
    }
    private static int Number(HttpContext ctx,string name,int fallback,int max)
    {
        var value=ctx.Request.Query[name].ToString();if(value.Length==0)return fallback;
        TaxRules.Require(int.TryParse(value,NumberStyles.None,CultureInfo.InvariantCulture,out var n) && n>=1 && n<=max,"tax_invalid_paging");return n;
    }
    private static (int Page,int Size) Paging(HttpContext ctx)=>(Number(ctx,"page",1,100000),Number(ctx,"pageSize",25,100));
    private static string Search(HttpContext ctx)
    {
        var value=ctx.Request.Query["search"].ToString().Trim();
        TaxRules.Require(value.Length<=200 && !value.Any(char.IsControl),"tax_invalid_search");return value;
    }
    private static Guid? QueryId(HttpContext ctx,string name)
    {
        var value=ctx.Request.Query[name].ToString();
        var alias=name switch {"country_id"=>"countryId","tax_type_id"=>"taxTypeId",_=>name};
        if(alias!=name && ctx.Request.Query.ContainsKey(alias)) {
            var other=ctx.Request.Query[alias].ToString();
            TaxRules.Require(value.Length==0 || value==other,"tax_invalid_id",field:name);value=other;
        }
        if(value.Length==0)return null;
        TaxRules.Require(Guid.TryParse(value,out var id) && id!=Guid.Empty,"tax_invalid_id",field:name);return id;
    }
    private static async Task<IResult> Countries(HttpContext ctx,AppDb db)
    {
        string? granted=null;
        foreach(var permission in new[]{"tax-codes.read","tax-codes.create","tax-codes.update"}) {
            try {await Security.Authorize(ctx,permission);granted=permission;break;}
            catch(ApiException e) when(e.Status==403) { }
        }
        TaxRules.Require(granted!=null,"forbidden",403);
        await Gate(ctx,db,granted!);
        var items=await LookupRows(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country ORDER BY name,id");
        return Results.Ok(new {items});
    }
    private static async Task<List<Dictionary<string,object?>>> LookupRows(AppDb db,string sql)
    {
        // One extra row detects overflow; never present a silently incomplete selector.
        var rows=await Rows(db,sql+" LIMIT 10001");
        TaxRules.Require(rows.Count<=10000,"tax_lookup_limit_exceeded",409);
        return rows;
    }
    private static async Task<IResult> Lookups(HttpContext ctx,AppDb db)
    {
        string? granted=null;
        foreach(var permission in new[]{"tax-codes.read","tax-codes.create","tax-codes.update","tax-codes.schedule"}) {
            try {await Security.Authorize(ctx,permission);granted=permission;break;}
            catch(ApiException e) when(e.Status==403) { }
        }
        TaxRules.Require(granted!=null,"forbidden",403);
        await Gate(ctx,db,granted!);
        // System catalogs only. Disabled entries remain visible for historical configuration.
        var countries=await LookupRows(db,"SELECT id,iso_code,name,is_enabled FROM foundation.country ORDER BY name,id");
        var types=await LookupRows(db,"SELECT id,code,name,is_active FROM taxmanagement.tax_types ORDER BY code,id");
        var natureCodes=await LookupRows(db,"SELECT n.*,c.iso_code AS country_iso_code FROM taxmanagement.tax_nature_codes n JOIN foundation.country c ON c.id=n.country_id ORDER BY c.iso_code,n.code,n.id");
        return Results.Ok(new {countries,types,natureCodes});
    }
    private static async Task<IResult> Types(HttpContext ctx,AppDb db)
    {
        await Gate(ctx,db,"tax-types.read");var (page,size)=Paging(ctx);var search=Search(ctx);
        const string filter=" WHERE (@s='' OR strpos(lower(code||' '||name),lower(@s))>0)";
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_types"+filter,("s",search)));
        var items=await Rows(db,"SELECT * FROM taxmanagement.tax_types"+filter+" ORDER BY code,id LIMIT @n OFFSET @o",("s",search),("n",size),("o",(page-1)*size));
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> Natures(HttpContext ctx,AppDb db)
    {
        await Gate(ctx,db,"tax-nature-codes.read");var (page,size)=Paging(ctx);var search=Search(ctx);var country=QueryId(ctx,"country_id");
        DateOnly? date=null;if(ctx.Request.Query.ContainsKey("date")) date=TaxRules.ParseDate(ctx.Request.Query["date"].ToString());
        const string filter=" WHERE (@country::uuid IS NULL OR n.country_id=@country) AND (@date::date IS NULL OR (n.valid_from<=@date AND (n.valid_to IS NULL OR n.valid_to>=@date))) AND (@s='' OR strpos(lower(n.code||' '||n.description),lower(@s))>0)";
        var args=new (string Name,object? Value)[]{("country",country),("date",date),("s",search),("n",size),("o",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_nature_codes n"+filter,("country",country),("date",date),("s",search)));
        var items=await Rows(db,"SELECT n.*,c.iso_code AS country_iso_code FROM taxmanagement.tax_nature_codes n JOIN foundation.country c ON c.id=n.country_id"+filter+" ORDER BY c.iso_code,n.code,n.id LIMIT @n OFFSET @o",args);
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db)
    {
        var tenant=await Gate(ctx,db,"tax-codes.read");var (page,size)=Paging(ctx);var search=Search(ctx);
        var type=QueryId(ctx,"tax_type_id");var country=QueryId(ctx,"country_id");bool? active=null;
        if(ctx.Request.Query.ContainsKey("is_active")) {TaxRules.Require(bool.TryParse(ctx.Request.Query["is_active"],out var flag),"tax_invalid_field",field:"is_active");active=flag;}
        const string filter=" WHERE r.tenant_id=@t AND (@s='' OR strpos(lower(r.code||' '||r.name),lower(@s))>0) AND (@type::uuid IS NULL OR r.tax_type_id=@type) AND (@country::uuid IS NULL OR r.country_id=@country) AND (@active::boolean IS NULL OR r.is_active=@active)";
        DateOnly? date=null;if(ctx.Request.Query.ContainsKey("date")) date=TaxRules.ParseDate(ctx.Request.Query["date"].ToString());
        var args=new (string Name,object? Value)[]{("t",tenant),("s",search),("type",type),("country",country),("active",active),("date",date),("n",size),("o",(page-1)*size)};
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_codes r"+filter,("t",tenant),("s",search),("type",type),("country",country),("active",active)));
        // Data esplicita: mai mostrare un'aliquota futura come se fosse già efficace.
        var items=await Rows(db,"SELECT r.*,c.iso_code AS country_code,t.code AS tax_type_code,v.rate,v.treatment,nc.code AS tax_nature_code FROM taxmanagement.tax_codes r JOIN foundation.country c ON c.id=r.country_id JOIN taxmanagement.tax_types t ON t.id=r.tax_type_id LEFT JOIN taxmanagement.tax_code_versions v ON v.tenant_id=r.tenant_id AND v.tax_code_id=r.id AND @date::date IS NOT NULL AND v.valid_from<=@date AND (v.valid_to IS NULL OR v.valid_to>=@date) LEFT JOIN taxmanagement.tax_nature_codes nc ON nc.id=v.tax_nature_code_id"+filter+" ORDER BY lower(r.code),r.id LIMIT @n OFFSET @o",args);
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<Dictionary<string,object?>> Root(AppDb db,Guid tenant,Guid id,bool locked=false)
    {
        var row=(await Rows(db,"SELECT r.*,c.iso_code AS country_code,c.iso_code AS country_iso_code,t.code AS tax_type_code,t.is_active AS tax_type_active FROM taxmanagement.tax_codes r JOIN foundation.country c ON c.id=r.country_id JOIN taxmanagement.tax_types t ON t.id=r.tax_type_id WHERE r.tenant_id=@t AND r.id=@id"+(locked?" FOR UPDATE OF r":""),("t",tenant),("id",id))).SingleOrDefault();
        return row??throw new ApiException(404,"tax_not_found");
    }
    private static Task<List<Dictionary<string,object?>>> Versions(AppDb db,Guid tenant,Guid id)
        =>Rows(db,"SELECT v.*,n.code AS tax_nature_code FROM taxmanagement.tax_code_versions v LEFT JOIN taxmanagement.tax_nature_codes n ON n.id=v.tax_nature_code_id WHERE v.tenant_id=@t AND v.tax_code_id=@id ORDER BY v.valid_from,v.id",("t",tenant),("id",id));
    private static TaxFiscalVersion Fiscal(Dictionary<string,object?> row)=>new((Guid)row["id"]!,TaxRules.ParseRate((string)row["rate"]!),(string)row["treatment"]!,row["tax_nature_code_id"] as Guid?,row["legal_reference"] as string,(DateOnly)row["valid_from"]!,row["valid_to"] as DateOnly?);
    private static TaxCode Aggregate(Dictionary<string,object?> root,IEnumerable<Dictionary<string,object?>> versions)
        =>new((Guid)root["id"]!,(Guid)root["tenant_id"]!,(long)root["version"]!,
            (bool)root["is_active"]!,(bool)root["tax_type_active"]! && (string)root["tax_type_code"]! == "VAT",versions.Select(Fiscal));
    private static async Task<Dictionary<string,object?>> Detail(AppDb db,Guid tenant,Guid id)
    {var root=await Root(db,tenant,id);root["versions"]=await Versions(db,tenant,id);return root;}
    private static async Task<IResult> Get(HttpContext ctx,AppDb db,Guid id)
    {var tenant=await Gate(ctx,db,"tax-codes.read");return Results.Ok(await Detail(db,tenant,id));}
    private static async Task<IResult> History(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"tax-codes.read");await Root(db,tenant,id);var (page,size)=Paging(ctx);
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_code_versions WHERE tenant_id=@t AND tax_code_id=@id",("t",tenant),("id",id)));
        var items=await Rows(db,"SELECT v.*,n.code AS tax_nature_code FROM taxmanagement.tax_code_versions v LEFT JOIN taxmanagement.tax_nature_codes n ON n.id=v.tax_nature_code_id WHERE v.tenant_id=@t AND v.tax_code_id=@id ORDER BY v.valid_from,v.id LIMIT @n OFFSET @o",("t",tenant),("id",id),("n",size),("o",(page-1)*size));
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> AuditList(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"tax-codes.read");await Root(db,tenant,id);var (page,size)=Paging(ctx);
        var total=Convert.ToInt64(await db.Scalar("SELECT count(*) FROM taxmanagement.tax_audit_events WHERE tenant_id=@t AND tax_code_id=@id",("t",tenant),("id",id)));
        var items=await Rows(db,"SELECT * FROM taxmanagement.tax_audit_events WHERE tenant_id=@t AND tax_code_id=@id ORDER BY created_at DESC,id DESC LIMIT @n OFFSET @o",("t",tenant),("id",id),("n",size),("o",(page-1)*size));
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> Resolve(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"tax-codes.read");var root=await Root(db,tenant,id);
        var date=TaxRules.ParseDate(ctx.Request.Query["date"].ToString());var forNewUse=false;
        if(ctx.Request.Query.ContainsKey("forNewUse")) TaxRules.Require(bool.TryParse(ctx.Request.Query["forNewUse"],out forNewUse),"tax_invalid_field",field:"forNewUse");
        var versions=await Versions(db,tenant,id);
        var resolved=Aggregate(root,versions).ResolveVersionAt(date,forNewUse);
        var version=versions.Single(v=>(Guid)v["id"]! == resolved.Id);
        version["tax_code"]=root;version["date"]=date;version["forNewUse"]=forNewUse;
        return Results.Ok(version);
    }
    private static async Task ValidateFiscal(AppDb db,Guid country,string iso,TaxFiscalVersion version)
    {
        TaxNature? nature=null;
        if(version.TaxNatureCodeId is Guid id) {
            var row=(await Rows(db,"SELECT * FROM taxmanagement.tax_nature_codes WHERE id=@id",("id",id))).SingleOrDefault();
            TaxRules.Require(row!=null,"tax_invalid_nature");
            nature=new(id,(Guid)row!["country_id"]!,(string)row["scheme"]!,(string)row["code"]!,(DateOnly)row["valid_from"]!,row["valid_to"] as DateOnly?);
        }
        TaxRules.Validate(version,iso,country,nature);
    }
    private static async Task InsertVersion(AppDb db,Guid tenant,Guid root,Guid actor,TaxFiscalVersion v)
        =>await db.Execute("INSERT INTO taxmanagement.tax_code_versions(id,tenant_id,tax_code_id,rate,treatment,tax_nature_code_id,legal_reference,valid_from,valid_to,created_at,created_by) VALUES(@id,@t,@root,@rate,@treatment,@nature::uuid,@legal::text,@from,@to::date,clock_timestamp(),@actor)",("id",v.Id),("t",tenant),("root",root),("rate",v.Rate),("treatment",v.Treatment),("nature",v.TaxNatureCodeId),("legal",v.LegalReference),("from",v.ValidFrom),("to",v.ValidTo),("actor",actor));
    private static async Task Audit(HttpContext ctx,AppDb db,Guid tenant,Guid id,string action,object details)
    {
        var actor=Security.State(ctx).User.Id;
        await db.Audit(actor,tenant,action,"tax-codes",id,details);
        await db.Execute("INSERT INTO taxmanagement.tax_audit_events(id,tenant_id,tax_code_id,actor_id,action,details,created_at) VALUES(@event,@t,@id,@actor,@action,@details::jsonb,clock_timestamp())",("event",Guid.NewGuid()),("t",tenant),("id",id),("actor",actor),("action",action),("details",JsonSerializer.Serialize(details)));
    }
    private static async Task<Dictionary<string,object?>> CreateCore(HttpContext ctx,AppDb db,Guid tenant,Dictionary<string,JsonElement> values,IReadOnlyList<TaxFiscalVersion> versions,string action)
    {
        var code=TaxInput.Code(values);var name=TaxInput.Text(values,"name",150,true)!;var description=TaxInput.Text(values,"description",10000);
        var type=TaxInput.Id(values,"tax_type_id",true)!.Value;var country=TaxInput.Id(values,"country_id",true)!.Value;var active=TaxInput.Flag(values,"is_active",true);
        TaxRules.Require(await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE id=@id AND code='VAT' AND is_active",("id",type)) is Guid,"tax_type_not_supported");
        var iso=await db.Scalar("SELECT iso_code FROM foundation.country WHERE id=@id",("id",country)) as string;
        TaxRules.Require(iso!=null,"tax_invalid_country");
        TaxRules.Require(versions.Count>=1 && versions.Count<=100,"tax_versions_required");
        foreach(var version in versions) await ValidateFiscal(db,country,iso!,version);
        var sorted=versions.OrderBy(v=>v.ValidFrom).ToArray();
        for(var i=1;i<sorted.Length;i++) TaxRules.Require(!TaxRules.Overlaps(sorted[i-1].ValidFrom,sorted[i-1].ValidTo,sorted[i].ValidFrom,sorted[i].ValidTo),"tax_version_overlap",409);
        var id=Guid.NewGuid();
        try {
            await db.Execute("INSERT INTO taxmanagement.tax_codes(id,tenant_id,tax_type_id,country_id,code,name,description,is_active,version,created_at,updated_at) VALUES(@id,@t,@type,@country,@code,@name,@description::text,@active,1,clock_timestamp(),clock_timestamp())",("id",id),("t",tenant),("type",type),("country",country),("code",code),("name",name),("description",description),("active",active));
            foreach(var version in sorted) await InsertVersion(db,tenant,id,Security.State(ctx).User.Id,version);
        } catch(PostgresException e) when(e.SqlState=="23505") {throw new ApiException(409,"tax_code_exists");}
        catch(PostgresException e) when(e.SqlState=="23P01") {throw new ApiException(409,"tax_version_overlap");}
        var after=await Detail(db,tenant,id);await Audit(ctx,db,tenant,id,action,new {before=(object?)null,after});return after;
    }
    private static async Task<IResult> Create(HttpContext ctx,AppDb db,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"tax-codes.create");var input=TaxInput.Object(body,"values","versions");
        var values=TaxInput.Object(TaxInput.Required(input,"values"),"code","name","description","tax_type_id","country_id","is_active");
        var raw=TaxInput.Required(input,"versions");TaxRules.Require(raw.ValueKind==JsonValueKind.Array && raw.GetArrayLength()>=1 && raw.GetArrayLength()<=100,"tax_versions_required");
        var versions=raw.EnumerateArray().Select(TaxInput.Fiscal).ToArray();
        return Results.Json(await CreateCore(ctx,db,tenant,values,versions,"create"),statusCode:201);
    }
    private static async Task<IResult> Update(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"tax-codes.update");var input=TaxInput.Object(body,"values","expectedVersion");
        var values=TaxInput.Object(TaxInput.Required(input,"values"),"name","description");TaxRules.Require(values.Count>0,"tax_empty_update");
        var before=await Root(db,tenant,id,true);TaxRules.CheckRevision(TaxInput.Revision(input),(long)before["version"]!);
        var name=values.ContainsKey("name")?TaxInput.Text(values,"name",150,true):(string)before["name"]!;
        var description=values.ContainsKey("description")?TaxInput.Text(values,"description",10000):before["description"] as string;
        await db.Execute("UPDATE taxmanagement.tax_codes SET name=@name,description=@description::text,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",("name",name),("description",description),("t",tenant),("id",id));
        var after=await Detail(db,tenant,id);await Audit(ctx,db,tenant,id,"update",TaxAuditChanges.Metadata(before,after));return Results.Ok(after);
    }
    private static async Task<IResult> Schedule(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"tax-codes.schedule");var input=TaxInput.Object(body,"values","expectedVersion");var next=TaxInput.Fiscal(TaxInput.Required(input,"values"));
        var root=await Root(db,tenant,id,true);
        var before=await Versions(db,tenant,id);
        var plan=Aggregate(root,before).PlanVersion(next,TaxInput.Revision(input));
        await ValidateFiscal(db,(Guid)root["country_id"]!,(string)root["country_iso_code"]!,next);
        try {
            if(plan.PredecessorId!=null) await db.Execute("UPDATE taxmanagement.tax_code_versions SET valid_to=@to WHERE tenant_id=@t AND tax_code_id=@root AND id=@id",("to",plan.PredecessorValidTo),("t",tenant),("root",id),("id",plan.PredecessorId));
            await InsertVersion(db,tenant,id,Security.State(ctx).User.Id,next);
            await db.Execute("UPDATE taxmanagement.tax_codes SET version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id));
        } catch(PostgresException e) when(e.SqlState=="23P01") {throw new ApiException(409,"tax_version_overlap");}
        var after=await Detail(db,tenant,id);
        var predecessor=before.SingleOrDefault(v=>v["id"] as Guid?==plan.PredecessorId);
        await Audit(ctx,db,tenant,id,"schedule",new {
            before=new {version=root["version"],predecessor=predecessor==null?null:new {id=predecessor["id"],valid_to=predecessor["valid_to"]}},
            after=new {version=after["version"],predecessor=predecessor==null?null:new {id=predecessor["id"],valid_to=(object?)plan.PredecessorValidTo},fiscalVersion=TaxAuditChanges.Fiscal(next)}
        });return Results.Ok(after);
    }
    private static async Task<IResult> SetActive(HttpContext ctx,AppDb db,Guid id,JsonElement body,bool active)
    {
        var tenant=await Gate(ctx,db,active?"tax-codes.reactivate":"tax-codes.deactivate");var input=TaxInput.Object(body,"expectedVersion");
        var before=await Root(db,tenant,id,true);TaxRules.CheckRevision(TaxInput.Revision(input),(long)before["version"]!);
        if(active) TaxRules.Require((string)before["tax_type_code"]! == "VAT" && (bool)before["tax_type_active"]!,"tax_type_not_supported",409);
        if((bool)before["is_active"]! == active) return Results.Ok(await Detail(db,tenant,id));
        await db.Execute("UPDATE taxmanagement.tax_codes SET is_active=@active,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",("active",active),("t",tenant),("id",id));
        var after=await Detail(db,tenant,id);await Audit(ctx,db,tenant,id,active?"reactivate":"deactivate",new {before=new {is_active=before["is_active"],version=before["version"]},after=new {is_active=after["is_active"],version=after["version"]}});return Results.Ok(after);
    }
    private static async Task<IResult> Install(HttpContext ctx,AppDb db,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"tax-codes.install_templates");var input=TaxInput.Object(body,"validFrom");var from=TaxInput.Date(input,"validFrom");
        // L'azione esplicita installa configurazione: nessuna data fiscale viene inventata.
        var country=await db.Scalar("SELECT id FROM foundation.country WHERE iso_code='IT'") as Guid?;
        TaxRules.Require(country!=null,"tax_italy_country_required",409);
        var type=await db.Scalar("SELECT id FROM taxmanagement.tax_types WHERE code='VAT' AND is_active") as Guid?;
        TaxRules.Require(type!=null,"tax_type_not_supported",409);
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended('tax-templates:'||@t::text,0))",("t",tenant));
        var installed=new List<Dictionary<string,object?>>();var skipped=new List<string>();
        foreach(var template in TaxTemplates.Italian) {
            if(await db.Scalar("SELECT id FROM taxmanagement.tax_codes WHERE tenant_id=@t AND country_id=@country AND tax_type_id=@type AND lower(code)=lower(@code)",("t",tenant),("country",country),("type",type),("code",template.Code)) is Guid) {skipped.Add(template.Code);continue;}
            Guid? nature=null;
            if(template.Nature!=null) {
                var choices=await Rows(db,"SELECT id FROM taxmanagement.tax_nature_codes WHERE country_id=@country AND scheme='FATTURAPA' AND code=@code AND valid_from<=@from AND valid_to IS NULL",("country",country),("code",template.Nature),("from",from));
                TaxRules.Require(choices.Count==1,"tax_template_nature_unavailable",409);nature=(Guid)choices[0]["id"]!;
            }
            var values=TaxInput.Object(JsonSerializer.SerializeToElement(new {code=template.Code,name=template.Name,tax_type_id=type,country_id=country}),"code","name","tax_type_id","country_id");
            var version=new TaxFiscalVersion(Guid.NewGuid(),template.Rate,template.Treatment,nature,null,from,null);
            installed.Add(await CreateCore(ctx,db,tenant,values,[version],"install_template"));
        }
        return Results.Ok(new {items=installed,installed=installed.Count,skipped=skipped.Count,skippedCodes=skipped,validFrom=from});
    }
}
