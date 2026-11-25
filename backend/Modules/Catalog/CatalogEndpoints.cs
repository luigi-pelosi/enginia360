using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Numbering;
using Enginia360.Shared.Validation;
using Npgsql;

namespace Enginia360.Modules.Catalog;

public static class CatalogEndpoints
{
    private const long MaxVersion=9007199254740991;
    private sealed record Resource(string Name,string Table,string[] Fields);
    private static readonly Resource Units=new("catalog-units","masterdata.catalog_unit_of_measure",["code","name","dimension","conversion_scope","factor_to_base","decimal_places","is_base","is_active"]);
    private static readonly Resource Categories=new("catalog-categories","masterdata.catalog_category",["code","name","description","parent_id","sort_order","is_active"]);
    private static readonly Resource Types=new("catalog-types","masterdata.catalog_item_type",["code","name","kind","default_sellable","default_purchasable","default_track_stock","is_active"]);
    private static async Task<Guid> Gate(HttpContext ctx,AppDb db,string permission)
    {
        await Security.Authorize(ctx,permission);
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var tenant=Security.State(ctx).Tenant(ctx,"catalog")!.Value;
        Check.Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.tenant WHERE id=@t AND is_enabled)",("t",tenant)))!,404,"not_found");
        return tenant;
    }
    public static void Map(WebApplication app)
    {
        MapResource(app,"units",Units);MapResource(app,"categories",Categories);MapResource(app,"types",Types);
        app.MapGet("/api/catalog/categories/tree",Tree);
        app.MapDelete("/api/catalog/categories/{id:guid}",DeleteCategory);
        app.MapGet("/api/catalog/types/{id:guid}/deletion-check",TypeDeletionCheck);
        app.MapDelete("/api/catalog/types/{id:guid}",DeleteType);
        app.MapPost("/api/catalog/units/{id:guid}/convert",ConvertUnit);
        app.MapGet("/api/catalog/numbering",async(HttpContext ctx,AppDb db)=>{
            var tenant=await Gate(ctx,db,"catalog-numbering.read");var entity=Kind(ctx);
            return Results.Ok(BusinessPartnerNumbering.Public(await NumberingKernel.Read(db,tenant,entity)));
        });
        app.MapPut("/api/catalog/numbering",async(HttpContext ctx,AppDb db,JsonElement body)=>{
            var tenant=await Gate(ctx,db,"catalog-numbering.update");var entity=Kind(ctx);
            var input=PartnerInput.Object(body,"mode","prefix","padding","nextNumber","version");
            var mode=PartnerInput.Choice(input,"mode","AUTO","MANUAL");
            Check.Require(input.TryGetValue("prefix",out var prefix) && prefix.ValueKind==JsonValueKind.String);
            var text=prefix.GetString()!;Check.Require(text.Length<=32 && text.All(c=>c is >= ' ' and <= '~'));
            var padding=(int)PartnerInput.Integer(input,"padding",1,15);
            var next=PartnerInput.Integer(input,"nextNumber",1,NumberingKernel.Maximum+1);
            var version=PartnerInput.Integer(input,"version",0,MaxVersion-1);
            var before=await NumberingKernel.Read(db,tenant,entity);
            var after=await NumberingKernel.Save(db,tenant,entity,new(mode,text,padding,next,version));
            if(after!=before) await db.Audit(Security.State(ctx).User.Id,tenant,"update","catalog-numbering",null,new {kind=entity,before=BusinessPartnerNumbering.Public(before),after=BusinessPartnerNumbering.Public(after)});
            return Results.Ok(BusinessPartnerNumbering.Public(after));
        });
    }
    public static void MapBrands(WebApplication app)
        =>MapResource(app,"brands",new Resource("catalog-brands","masterdata.catalog_brand",["code","name","description","is_active"]));
    private static string Kind(HttpContext ctx)=>ctx.Request.Query["kind"].ToString() switch {"GOOD"=>"CATALOG_GOOD","INTANGIBLE"=>"CATALOG_INTANGIBLE","SERVICE"=>"CATALOG_SERVICE","CHARGE"=>"CATALOG_CHARGE",_=>throw new ApiException(400,"invalid_numbering_kind")};
    private static void MapResource(WebApplication app,string route,Resource resource)
    {
        app.MapGet("/api/catalog/"+route,async(HttpContext ctx,AppDb db)=>await List(ctx,db,resource));
        app.MapGet("/api/catalog/"+route+"/{id:guid}",async(HttpContext ctx,AppDb db,Guid id)=>{
            var tenant=await Gate(ctx,db,resource.Name+".read");var item=await Read(db,resource,tenant,id);
            Check.Require(item!=null,404,"not_found");return Results.Ok(item);
        });
        app.MapPost("/api/catalog/"+route,(HttpContext ctx,AppDb db,JsonElement body)=>Save(ctx,db,resource,null,body));
        app.MapPut("/api/catalog/"+route+"/{id:guid}",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Save(ctx,db,resource,id,body));
    }
    private static int QueryInt(HttpContext ctx,string key,int fallback,int min,int max)
    {
        var s=ctx.Request.Query[key].ToString();if(s.Length==0)return fallback;
        Check.Require(int.TryParse(s,NumberStyles.None,CultureInfo.InvariantCulture,out var n) && n>=min && n<=max,400,"invalid_paging");return n;
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db,Resource resource)
    {
        var tenant=await Gate(ctx,db,resource.Name+".read");
        var page=QueryInt(ctx,"page",1,1,100000);var size=QueryInt(ctx,"pageSize",25,1,100);
        var search=ctx.Request.Query["search"].ToString().Trim();Check.Require(search.Length<=200 && !search.Any(char.IsControl));
        var where=" WHERE tenant_id=@t AND (@search='' OR strpos(lower(name),lower(@search))>0 OR strpos(lower(coalesce(code,'')),lower(@search))>0)";
        var total=System.Convert.ToInt64(await db.Scalar("SELECT count(*) FROM "+resource.Table+where,("t",tenant),("search",search)),CultureInfo.InvariantCulture);
        var items=await Rows(db,resource,"SELECT * FROM "+resource.Table+where+" ORDER BY lower(name),id LIMIT @limit OFFSET @offset",("t",tenant),("search",search),("limit",size),("offset",(page-1)*size));
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<List<Dictionary<string,object?>>> Rows(AppDb db,Resource resource,string sql,params (string Name,object? Value)[] parameters)
    {
        var result=new List<Dictionary<string,object?>>();await using var cmd=await db.Command(sql,parameters);await using var r=await cmd.ExecuteReaderAsync();
        while(await r.ReadAsync()) {
            var row=new Dictionary<string,object?>();
            for(var i=0;i<r.FieldCount;i++) row[r.GetName(i)]=r.IsDBNull(i)?null:r.GetName(i)=="factor_to_base"?r.GetDecimal(i).ToString("0.############",CultureInfo.InvariantCulture):r.GetValue(i);
            result.Add(row);
        }
        return result;
    }
    private static async Task<Dictionary<string,object?>?> Read(AppDb db,Resource resource,Guid tenant,Guid id,bool locked=false)
    {
        // Riga e metadato provengono dallo stesso snapshot; nessun permesso articoli richiesto.
        var metadata=resource==Types?",NOT EXISTS(SELECT 1 FROM masterdata.catalog_item i WHERE i.tenant_id=t.tenant_id AND i.item_type_id=t.id) AS \"canChangeKind\"":"";
        return (await Rows(db,resource,"SELECT t.*"+metadata+" FROM "+resource.Table+" t WHERE t.tenant_id=@t AND t.id=@id"+(locked?" FOR UPDATE OF t":""),("t",tenant),("id",id))).SingleOrDefault();
    }
    private static string? Text(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,int max,bool required=false)
        =>values.ContainsKey(key)?PartnerInput.Text(values,key,max,required,key):before?.GetValueOrDefault(key) as string ?? (required?throw new ApiException(400,"field_required",key):null);
    private static bool Flag(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,bool fallback)
        =>values.ContainsKey(key)?PartnerInput.Flag(values,key,key):before?.GetValueOrDefault(key) is bool old?old:fallback;
    private static long Integer(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,long min,long max,long fallback)
        =>values.ContainsKey(key)?PartnerInput.Integer(values,key,min,max):before?.GetValueOrDefault(key) is object old?System.Convert.ToInt64(old,CultureInfo.InvariantCulture):fallback;
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Resource resource,Guid? id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,resource.Name+(id.HasValue?".update":".create"));
        var input=PartnerInput.Object(body,id.HasValue?["values","expectedVersion"]:["values"]);
        Check.Require(input.TryGetValue("values",out var raw));var values=PartnerInput.Object(raw,resource.Fields);
        // Prima della riga: stesso ordine di lock di creazione articoli ed eliminazione tipi.
        if(resource==Types && id.HasValue)
            await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||@t::text,0))",("t",tenant));
        var before=id.HasValue?await Read(db,resource,tenant,id.Value,true):null;
        if(id.HasValue) {
            Check.Require(before!=null,404,"not_found");var expected=PartnerInput.Integer(input,"expectedVersion",1,MaxVersion);
            Check.Require(expected==(long)before!["version"]!,409,"stale_version");Check.Require(expected<MaxVersion,409,"version_exhausted");
        }
        var data=new Dictionary<string,object?> {
            ["code"]=Text(values,"code",before,30,resource==Units),["name"]=Text(values,"name",before,200,true),
            ["is_active"]=Flag(values,"is_active",before,true)
        };
        if(resource==Units) {
            var dimension=Text(values,"dimension",before,20,true)!;
            Check.Require(new[]{"COUNT","MASS","LENGTH","VOLUME","TIME","AREA"}.Contains(dimension),400,"invalid_unit_dimension");
            var scope=Text(values,"conversion_scope",before,20)??"UNIVERSAL";
            Check.Require(scope is "UNIVERSAL" or "ITEM",400,"invalid_conversion_scope");
            var factor=Text(values,"factor_to_base",before,30,scope=="UNIVERSAL");
            decimal? parsed=factor==null?null:CatalogConversion.Parse(factor,true);
            Check.Require(scope!="ITEM" || parsed==null,400,"item_unit_global_factor_forbidden");
            data["conversion_scope"]=scope;
            var isBase=Flag(values,"is_base",before,false);
            data["dimension"]=dimension;data["factor_to_base"]=parsed;data["is_base"]=isBase;
            data["decimal_places"]=(int)Integer(values,"decimal_places",before,0,12,0);
            Check.Require(!isBase || parsed==1,400,"invalid_base_factor");
            if(before!=null) Check.Require(dimension==(string)before["dimension"]! && scope==(string)before["conversion_scope"]! && parsed==(before["factor_to_base"] is string oldFactor?CatalogConversion.Parse(oldFactor,true):(decimal?)null) && isBase==(bool)before["is_base"]!,409,"immutable_unit_definition");
            Check.Require(scope!="ITEM" || !isBase,400,"item_unit_cannot_be_base");
            // Verifica anticipata per un errore utile; il constraint differito protegge il commit SQL.
            if(scope=="UNIVERSAL" && (bool)data["is_active"]! && !isBase) Check.Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND dimension=@dimension AND is_base AND is_active)",("t",tenant),("dimension",dimension)))!,409,"active_base_required");
            if(isBase && !(bool)data["is_active"]!) Check.Require(!(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND dimension=@dimension AND id<>@id AND is_active AND conversion_scope='UNIVERSAL')",("t",tenant),("dimension",dimension),("id",id??Guid.Empty)))!,409,"active_base_required");
        } else if(resource==Categories) {
            data["description"]=Text(values,"description",before,2000);
            Guid? parent=before?.GetValueOrDefault("parent_id") as Guid?;
            if(values.TryGetValue("parent_id",out var p)) {
                parent=null;
                if(p.ValueKind!=JsonValueKind.Null) {Check.Require(p.ValueKind==JsonValueKind.String && Guid.TryParse(p.GetString(),out var parsedParent) && parsedParent!=Guid.Empty,400,"invalid_category_parent");parent=Guid.Parse(p.GetString()!);}
            }
            Check.Require(parent==null || parent!=id,400,"category_cycle");
            if(parent.HasValue) Check.Require(await Read(db,Categories,tenant,parent.Value)!=null,400,"invalid_category_parent");
            data["parent_id"]=parent;data["sort_order"]=(int)Integer(values,"sort_order",before,int.MinValue,int.MaxValue,0);
        } else if(resource==Types) {
            var kind=Text(values,"kind",before,10,true)!;Check.Require(kind is "GOOD" or "INTANGIBLE" or "SERVICE" or "CHARGE",400,"invalid_item_kind");
            if(before!=null && kind!=(string)before["kind"]!) Check.Require(!await TypeInUse(db,tenant,id!.Value),409,"immutable_item_kind");
            data["kind"]=kind;data["default_sellable"]=Flag(values,"default_sellable",before,true);
            data["default_purchasable"]=Flag(values,"default_purchasable",before,true);data["default_track_stock"]=Flag(values,"default_track_stock",before,false);
            Check.Require(CatalogItemKind.SupportsStock(kind) || !(bool)data["default_track_stock"]!,400,kind=="SERVICE"?"service_cannot_track_stock":"nonphysical_cannot_track_stock");
        }
        if(resource.Name=="catalog-brands") data["description"]=Text(values,"description",before,2000);
        var record=id??Guid.NewGuid();var parameters=new List<(string Name,object? Value)> {("id",record),("tenant",tenant)};
        foreach(var entry in data)parameters.Add((entry.Key,entry.Value));
        string Parameter(string key)=>"@"+key+(key=="parent_id"?"::uuid":key is "code" or "description"?"::text":key=="factor_to_base"?"::numeric":"");
        try {
            if(!id.HasValue) await db.Execute("INSERT INTO "+resource.Table+"(id,tenant_id,"+string.Join(',',data.Keys)+") VALUES(@id,@tenant,"+string.Join(',',data.Keys.Select(Parameter))+")",parameters.ToArray());
            else await db.Execute("UPDATE "+resource.Table+" SET "+string.Join(',',data.Keys.Select(k=>k+"="+Parameter(k)))+",version=version+1 WHERE tenant_id=@tenant AND id=@id",parameters.ToArray());
        } catch(PostgresException e) when(e.SqlState=="23505") {throw new ApiException(409,"catalog_code_or_base_exists");}
        catch(PostgresException e) when(e.SqlState=="23503" && e.ConstraintName=="catalog_company_default_unit") {throw new ApiException(409,"company_default_unit_in_use");}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(400,"invalid_category_parent");}
        catch(PostgresException e) when(e.SqlState=="23514") {throw new ApiException(400,resource==Categories?"category_cycle":"catalog_constraint_violation");}
        var after=await Read(db,resource,tenant,record);
        var auditFields=id.HasValue?values.Keys:resource.Fields.AsEnumerable();
        var auditBefore=before==null?null:auditFields.ToDictionary(key=>key,key=>before.GetValueOrDefault(key));
        var auditAfter=auditFields.ToDictionary(key=>key,key=>after!.GetValueOrDefault(key));
        await db.Audit(Security.State(ctx).User.Id,tenant,id.HasValue?"update":"create",resource.Name,record,new {version=after!["version"],before=auditBefore,after=auditAfter});
        return Results.Json(after,statusCode:id.HasValue?200:201);
    }
    private static async Task<bool> TypeInUse(AppDb db,Guid tenant,Guid id)
        =>(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.catalog_item WHERE tenant_id=@t AND item_type_id=@id)",("t",tenant),("id",id)))!;
    private static async Task<IResult> TypeDeletionCheck(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"catalog-types.delete");
        Check.Require(await Read(db,Types,tenant,id)!=null,404,"not_found");
        return Results.Ok(new {canDelete=!await TypeInUse(db,tenant,id)});
    }
    private static async Task<IResult> DeleteType(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"catalog-types.delete");
        // Stesso confine delle guardie SQL, acquisito PRIMA del lock sulla radice.
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||@t::text,0))",("t",tenant));
        var item=await Read(db,Types,tenant,id,true);Check.Require(item!=null,404,"not_found");
        var raw=ctx.Request.Query["expectedVersion"].ToString();
        Check.Require(long.TryParse(raw,NumberStyles.None,CultureInfo.InvariantCulture,out var expected) && expected>=1 && expected<=MaxVersion,400,"expected_version_required");
        Check.Require(expected==(long)item!["version"]!,409,"stale_version");
        Check.Require(!await TypeInUse(db,tenant,id),409,"item_type_in_use");
        try {await db.Execute("DELETE FROM masterdata.catalog_item_type WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id));}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(409,"item_type_in_use");}
        await db.Audit(Security.State(ctx).User.Id,tenant,"delete",Types.Name,id,new {version=expected,before=Types.Fields.ToDictionary(key=>key,key=>item.GetValueOrDefault(key)),after=(object?)null});
        return Results.NoContent();
    }
    private static async Task<IResult> DeleteCategory(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"catalog-categories.delete");
        var item=await Read(db,Categories,tenant,id,true);Check.Require(item!=null,404,"not_found");
        var raw=ctx.Request.Query["expectedVersion"].ToString();
        Check.Require(long.TryParse(raw,NumberStyles.None,CultureInfo.InvariantCulture,out var expected) && expected>=1 && expected<=MaxVersion,400,"expected_version_required");
        Check.Require(expected==(long)item!["version"]!,409,"stale_version");
        try {await db.Execute("DELETE FROM masterdata.catalog_category WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id));}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(409,"category_has_children");}
        await db.Audit(Security.State(ctx).User.Id,tenant,"delete",Categories.Name,id,new {version=expected,before=Categories.Fields.ToDictionary(key=>key,key=>item.GetValueOrDefault(key)),after=(object?)null});return Results.NoContent();
    }
    private static async Task<IResult> Tree(HttpContext ctx,AppDb db)
    {
        var tenant=await Gate(ctx,db,"catalog-categories.read");
        var raw=ctx.Request.Query["parentId"].ToString();Guid? parent=null;
        if(raw.Length>0) {Check.Require(Guid.TryParse(raw,out var parsed) && parsed!=Guid.Empty,400,"invalid_category_parent");parent=Guid.Parse(raw);Check.Require(await Read(db,Categories,tenant,parent.Value)!=null,404,"not_found");}
        // Senza selettore: albero piatto completo, senza ricorsione JSON. Con parentId: figli diretti.
        var items=await Rows(db,Categories,"SELECT * FROM masterdata.catalog_category WHERE tenant_id=@t"+(parent.HasValue?" AND parent_id=@parent":"")+" ORDER BY sort_order,lower(name),id",("t",tenant),("parent",parent));
        return Results.Ok(new {items});
    }
    private static async Task<IResult> ConvertUnit(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"catalog-units.read");var input=PartnerInput.Object(body,"targetUnitId","quantity");
        Check.Require(input.TryGetValue("targetUnitId",out var target) && target.ValueKind==JsonValueKind.String && Guid.TryParse(target.GetString(),out _),400,"invalid_target_unit");
        var source=await Read(db,Units,tenant,id);var destination=await Read(db,Units,tenant,Guid.Parse(target.GetString()!));
        Check.Require(source!=null && destination!=null,404,"not_found");
        Check.Require((string)source!["conversion_scope"]! == "UNIVERSAL" && (string)destination!["conversion_scope"]! == "UNIVERSAL",400,"item_unit_requires_item_conversion");
        Check.Require((bool)source!["is_active"]! && (bool)destination!["is_active"]!,400,"inactive_unit");
        Check.Require((string)source["dimension"]! == (string)destination!["dimension"]!,400,"incompatible_unit_dimensions");
        var quantity=PartnerInput.Text(input,"quantity",30,true,"quantity")!;
        var result=CatalogConversion.Convert(quantity,(string)source["factor_to_base"]!,(string)destination["factor_to_base"]!,(int)destination["decimal_places"]!);
        return Results.Ok(new {quantity=result.Quantity,unroundedQuantity=result.UnroundedQuantity,rounded=result.Rounded,decimalPlaces=result.DecimalPlaces});
    }
}
