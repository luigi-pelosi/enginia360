using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;
using static Enginia360.Modules.Catalog.CatalogItem;
using Values=Enginia360.Modules.Catalog.CatalogItemCompany.Values;

namespace Enginia360.Modules.Catalog;

// Transazione e lock di sicurezza sono quelli del middleware; il lock catalogo precede le righe.
public static class CatalogItemCompanyEndpoints
{
    private const string Joins=" FROM masterdata.catalog_item_company x JOIN foundation.company c ON c.tenant_id=x.tenant_id AND c.id=x.company_id JOIN masterdata.catalog_item i ON i.tenant_id=x.tenant_id AND i.id=x.item_id JOIN masterdata.catalog_item_type t ON t.tenant_id=i.tenant_id AND t.id=i.item_type_id ";
    private const string EffectiveEnabled="i.status='ACTIVE' AND c.is_enabled AND x.is_enabled";
    private const string CanSell=EffectiveEnabled+" AND x.is_sellable";
    private const string CanPurchase=EffectiveEnabled+" AND x.is_purchasable";
    private const string CanTrackStock=EffectiveEnabled+" AND x.track_stock AND t.kind='GOOD'";
    private const string Projection=$"""
        (to_jsonb(x)||jsonb_build_object(
          'company_name',c.name,'company_is_enabled',c.is_enabled,
          'item_code',i.code,'item_name',i.name,'item_status',i.status,'kind',t.kind,'base_uom_id',i.base_uom_id,
          'effective_sales_uom_id',coalesce(x.default_sales_uom_id,i.base_uom_id),
          'effective_purchase_uom_id',coalesce(x.default_purchase_uom_id,i.base_uom_id),
          'canSell',{CanSell},
          'canPurchase',{CanPurchase},
          'canTrackStock',{CanTrackStock}))::text
        """;
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/catalog/item-companies/options",Options);
        app.MapGet("/api/catalog/item-companies/item-options/{itemId:guid}",ItemOptions);
        app.MapGet("/api/catalog/items/{itemId:guid}/companies",ItemCompanies);
        app.MapGet("/api/catalog/item-companies",(HttpContext ctx,AppDb db)=>List(ctx,db,null));
        app.MapGet("/api/companies/{companyId:guid}/catalog/items",(HttpContext ctx,AppDb db,Guid companyId)=>List(ctx,db,companyId));
        app.MapGet("/api/companies/{companyId:guid}/catalog/items/{itemId:guid}",Get);
        app.MapPut("/api/companies/{companyId:guid}/catalog/items/{itemId:guid}",(HttpContext ctx,AppDb db,Guid companyId,Guid itemId,JsonElement body)=>Mutation(()=>Save(ctx,db,companyId,itemId,body,false)));
        app.MapPatch("/api/companies/{companyId:guid}/catalog/items/{itemId:guid}",(HttpContext ctx,AppDb db,Guid companyId,Guid itemId,JsonElement body)=>Mutation(()=>Save(ctx,db,companyId,itemId,body,true)));
        app.MapPost("/api/catalog/item-companies/bulk-enable",(HttpContext ctx,AppDb db,JsonElement body)=>Mutation(()=>Bulk(ctx,db,null,body)));
        app.MapPost("/api/companies/{companyId:guid}/catalog/items/bulk-enable",(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)=>Mutation(()=>Bulk(ctx,db,companyId,body)));
    }
    private static async Task<IResult> Mutation(Func<Task<IResult>> action)
    {
        try {return await action();}
        catch(PostgresException e) when(e.SqlState=="23505") {throw new ApiException(409,"company_item_exists");}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(400,"invalid_catalog_reference");}
        catch(PostgresException e) when(e.SqlState=="23514") {throw new ApiException(400,"catalog_item_company_constraint_violation");}
    }
    private static async Task<Guid> Tenant(HttpContext ctx,AppDb db)
    {
        Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var tenant=Security.State(ctx).Tenant(ctx,"catalog")!.Value;
        Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.tenant WHERE id=@t AND is_enabled)",("t",tenant)))!,404,"not_found");
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||@t::text,0))",("t",tenant));
        return tenant;
    }
    private static async Task<List<JsonElement>> JsonRows(AppDb db,string sql,params (string Name,object? Value)[] args)
    {
        await using var cmd=await db.Command(sql,args);
        await using var reader=await cmd.ExecuteReaderAsync();
        var rows=new List<JsonElement>();
        while(await reader.ReadAsync())rows.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));
        return rows;
    }
    private static Task<List<JsonElement>> Query(AppDb db,string where,params (string Name,object? Value)[] args)=>JsonRows(db,"SELECT "+Projection+Joins+" WHERE "+where,args);
    private static async Task<JsonElement> Read(AppDb db,Guid tenant,Guid company,Guid item)
    {
        var rows=await Query(db,"x.tenant_id=@t AND x.company_id=@c AND x.item_id=@i",("t",tenant),("c",company),("i",item));
        Require(rows.Count==1,404,"not_found");return rows[0];
    }
    private static async Task<bool> Company(AppDb db,Guid tenant,Guid company,bool locked=false)
    {
        var enabled=await db.Scalar("SELECT is_enabled FROM foundation.company WHERE tenant_id=@t AND id=@c"+(locked?" FOR SHARE":""),("t",tenant),("c",company));
        Require(enabled is bool,404,"not_found");return (bool)enabled!;
    }
    private static async Task<JsonElement> Item(AppDb db,Guid tenant,Guid item,bool locked=false)
    {
        var rows=await JsonRows(db,"SELECT jsonb_build_object('id',i.id,'code',i.code,'name',i.name,'status',i.status,'kind',t.kind,'base_uom_id',i.base_uom_id,'default_sellable',t.default_sellable,'default_purchasable',t.default_purchasable,'default_track_stock',t.default_track_stock)::text FROM masterdata.catalog_item i JOIN masterdata.catalog_item_type t ON t.tenant_id=i.tenant_id AND t.id=i.item_type_id WHERE i.tenant_id=@t AND i.id=@i"+(locked?" FOR UPDATE OF i":""),("t",tenant),("i",item));
        Require(rows.Count==1,404,"not_found");return rows[0];
    }
    private static Values Defaults(JsonElement item)=>CatalogItemCompany.Defaults(item.GetProperty("default_sellable").GetBoolean(),item.GetProperty("default_purchasable").GetBoolean(),item.GetProperty("default_track_stock").GetBoolean(),item.GetProperty("kind").GetString()!);
    private static Values Config(JsonElement row)=>new(row.GetProperty("is_enabled").GetBoolean(),row.GetProperty("is_sellable").GetBoolean(),row.GetProperty("is_purchasable").GetBoolean(),row.GetProperty("track_stock").GetBoolean(),NullableId(row,"default_sales_uom_id"),NullableId(row,"default_purchase_uom_id"));
    private static Guid? NullableId(JsonElement row,string key)=>row.GetProperty(key).ValueKind==JsonValueKind.Null?null:row.GetProperty(key).GetGuid();
    private static async Task<JsonElement?> Existing(AppDb db,Guid tenant,Guid company,Guid item,bool locked)
    {
        var rows=await JsonRows(db,"SELECT to_jsonb(x)::text FROM masterdata.catalog_item_company x WHERE tenant_id=@t AND company_id=@c AND item_id=@i"+(locked?" FOR UPDATE":""),("t",tenant),("c",company),("i",item));
        return rows.Count==0?null:rows[0];
    }
    private static async Task<IResult> Options(HttpContext ctx,AppDb db)
    {
        var tenant=await Tenant(ctx,db);
        var grants=await CatalogCompanyAuthorization.Resolve(db,Security.State(ctx),tenant);
        Require(grants.Count>0 || CatalogCompanyAuthorization.Global(Security.State(ctx)),403,"forbidden");
        await Security.Authorize(ctx,"catalog-item-companies."+(grants.Values.SelectMany(x=>x).FirstOrDefault()??"read"));
        // Metadati strettamente necessari al selettore, senza company.read.
        var rows=await JsonRows(db,"""
            SELECT jsonb_build_object('id',c.id,'name',c.name,'code',c.code,'is_enabled',c.is_enabled,
              'legal_address',(SELECT jsonb_build_object('address',s.address,'postal_code',s.postal_code,
                'city',s.city,'province',s.province,'country_code',s.country_code)
                FROM foundation.site s WHERE s.tenant_id=c.tenant_id AND s.company_id=c.id
                  AND s.site_type='LEGAL' AND s.is_enabled ORDER BY s.created_at,s.id LIMIT 1))::text
            FROM foundation.company c WHERE c.tenant_id=@t AND c.id=ANY(@ids::uuid[]) ORDER BY lower(c.name),c.id
            """,("t",tenant),("ids",grants.Keys.ToArray()));
        var items=rows.Select(row=>new {id=row.GetProperty("id").GetGuid(),name=row.GetProperty("name"),code=row.GetProperty("code"),is_enabled=row.GetProperty("is_enabled"),legal_address=row.GetProperty("legal_address"),permissions=grants[row.GetProperty("id").GetGuid()]});
        return Results.Ok(new {items});
    }
    private static async Task<List<JsonElement>> Units(AppDb db,Guid tenant,Guid item)
        =>await JsonRows(db,"SELECT jsonb_build_object('id',u.id,'name',u.name,'code',u.code,'is_active',u.is_active)::text FROM masterdata.catalog_unit_of_measure u JOIN masterdata.catalog_item i ON i.tenant_id=u.tenant_id AND i.id=@i WHERE u.tenant_id=@t AND u.is_active AND (u.id=i.base_uom_id OR EXISTS(SELECT 1 FROM masterdata.catalog_item_unit iu WHERE iu.tenant_id=i.tenant_id AND iu.item_id=i.id AND iu.uom_id=u.id AND iu.is_active)) ORDER BY lower(u.name),u.id",("t",tenant),("i",item));
    private static async Task<IResult> ItemOptions(HttpContext ctx,AppDb db,Guid itemId)
    {
        var tenant=await Tenant(ctx,db);
        var grants=await CatalogCompanyAuthorization.Resolve(db,Security.State(ctx),tenant);
        Require(grants.Count>0 || CatalogCompanyAuthorization.Global(Security.State(ctx)),403,"forbidden");
        await Security.Authorize(ctx,"catalog-item-companies."+(grants.Values.SelectMany(x=>x).FirstOrDefault()??"read"));
        // Il solo lettore/editor non puo enumerare anagrafiche tenant non associate.
        var create=grants.Any(x=>x.Value.Contains("create"));
        if(!create && !CatalogCompanyAuthorization.Global(Security.State(ctx))) {
            var ids=grants.Where(x=>x.Value.Contains("read") || x.Value.Contains("update")).Select(x=>x.Key).ToArray();
            Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.catalog_item_company WHERE tenant_id=@t AND item_id=@i AND company_id=ANY(@ids::uuid[]))",("t",tenant),("i",itemId),("ids",ids)))!,404,"not_found");
        }
        var root=await Item(db,tenant,itemId);
        var defaults=Defaults(root);
        return Results.Ok(new {item=new {id=itemId,code=root.GetProperty("code"),name=root.GetProperty("name"),status=root.GetProperty("status"),kind=root.GetProperty("kind"),base_uom_id=root.GetProperty("base_uom_id")},defaults=new {is_sellable=defaults.IsSellable,is_purchasable=defaults.IsPurchasable,track_stock=defaults.TrackStock},units=await Units(db,tenant,itemId)});
    }
    private static async Task<IResult> ItemCompanies(HttpContext ctx,AppDb db,Guid itemId)
    {
        await Security.Authorize(ctx,"catalog-items.read");
        await Security.Authorize(ctx,"catalog-item-companies.read");
        var tenant=await Tenant(ctx,db);_=await Item(db,tenant,itemId);
        var grants=await CatalogCompanyAuthorization.Resolve(db,Security.State(ctx),tenant);
        var ids=grants.Where(x=>x.Value.Contains("read")).Select(x=>x.Key).ToArray();
        return Results.Ok(new {items=await Query(db,"x.tenant_id=@t AND x.item_id=@i AND x.company_id=ANY(@ids::uuid[]) ORDER BY lower(c.name),x.id",("t",tenant),("i",itemId),("ids",ids))});
    }
    private static async Task<IResult> Get(HttpContext ctx,AppDb db,Guid companyId,Guid itemId)
    {
        var tenant=await Tenant(ctx,db);_=await Company(db,tenant,companyId);
        await CatalogCompanyAuthorization.Require(ctx,db,tenant,companyId,"read");
        return Results.Ok(await Read(db,tenant,companyId,itemId));
    }
    private static string Parameter(HttpContext ctx,string key)
    {
        foreach(var actual in ctx.Request.Query.Keys)
            Require(!string.Equals(actual,key,StringComparison.OrdinalIgnoreCase) || actual==key,400,"invalid_query",actual);
        var values=ctx.Request.Query[key];Require(values.Count<=1,400,"invalid_query",key);return values.ToString();
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db,Guid? companyId)
    {
        await Security.Authorize(ctx,"catalog-item-companies.read");
        var tenant=await Tenant(ctx,db);
        var selected=Parameter(ctx,"companyId");
        if(selected.Length>0) {
            Require(Guid.TryParseExact(selected,"D",out var id) && id!=Guid.Empty,400,"invalid_company","companyId");
            Require(companyId==null || companyId==id,400,"invalid_company","companyId");companyId=id;
        }
        if(companyId.HasValue) {_=await Company(db,tenant,companyId.Value);await CatalogCompanyAuthorization.Require(ctx,db,tenant,companyId.Value,"read");}
        var grants=await CatalogCompanyAuthorization.Resolve(db,Security.State(ctx),tenant);
        var ids=companyId.HasValue?[companyId.Value]:grants.Where(x=>x.Value.Contains("read")).Select(x=>x.Key).ToArray();
        int Number(string key,int fallback,int max) {var text=Parameter(ctx,key);if(text=="")return fallback;Require(int.TryParse(text,NumberStyles.None,CultureInfo.InvariantCulture,out var n) && n>=1 && n<=max,400,"invalid_paging",key);return n;}
        var page=Number("page",1,100000);var size=Number("pageSize",25,100);
        var search=Parameter(ctx,"search").Trim();Require(search.Length<=200 && !search.Any(char.IsControl),400,"invalid_search");
        var kind=Parameter(ctx,"kind");Require(kind is "" or "GOOD" or "INTANGIBLE" or "SERVICE" or "CHARGE",400,"invalid_item_kind");
        var enabled=Parameter(ctx,"enabled");Require(enabled is "" or "ALL" or "ENABLED" or "DISABLED",400,"invalid_enabled_filter");
        string Capability(string key) {var value=Parameter(ctx,key);Require(value is "" or "ALL" or "YES" or "NO",400,"invalid_capability_filter",key);return value;}
        var canSell=Capability("canSell");var canPurchase=Capability("canPurchase");var canTrackStock=Capability("canTrackStock");
        const string where="x.tenant_id=@t AND x.company_id=ANY(@ids::uuid[]) AND (@kind='' OR t.kind=@kind) AND (@enabled IN ('','ALL') OR x.is_enabled=(@enabled='ENABLED')) AND (@search='' OR strpos(lower(i.name),lower(@search))>0 OR strpos(lower(i.code),lower(@search))>0)"
            +" AND (@canSell IN ('','ALL') OR ("+CanSell+")=(@canSell='YES'))"
            +" AND (@canPurchase IN ('','ALL') OR ("+CanPurchase+")=(@canPurchase='YES'))"
            +" AND (@canTrackStock IN ('','ALL') OR ("+CanTrackStock+")=(@canTrackStock='YES'))";
        (string Name,object? Value)[] args=[("t",tenant),("ids",ids),("kind",kind),("enabled",enabled),("search",search),("canSell",canSell),("canPurchase",canPurchase),("canTrackStock",canTrackStock),("size",size),("offset",(page-1)*size)];
        var total=(long)(await db.Scalar("SELECT count(*)"+Joins+" WHERE "+where,args))!;
        return Results.Ok(new {items=await Query(db,where+" ORDER BY lower(i.name),i.id,c.id LIMIT @size OFFSET @offset",args),total,page,pageSize=size});
    }
    private static async Task ValidateUnits(AppDb db,Guid tenant,Guid item,Values after,Values? before)
    {
        foreach(var (field,id,old) in new[]{("default_sales_uom_id",after.DefaultSalesUomId,before?.DefaultSalesUomId),("default_purchase_uom_id",after.DefaultPurchaseUomId,before?.DefaultPurchaseUomId)}) {
            if(id==null || id==old)continue;
            var valid=await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.catalog_unit_of_measure u JOIN masterdata.catalog_item i ON i.tenant_id=u.tenant_id AND i.id=@i WHERE u.tenant_id=@t AND u.id=@u AND u.is_active AND (u.id=i.base_uom_id OR EXISTS(SELECT 1 FROM masterdata.catalog_item_unit iu WHERE iu.tenant_id=i.tenant_id AND iu.item_id=i.id AND iu.uom_id=u.id AND iu.is_active)))",("t",tenant),("i",item),("u",id));
            Require((bool)valid!,400,"invalid_company_item_unit",field);
        }
    }
    private static async Task Write(HttpContext ctx,AppDb db,Guid tenant,Guid company,Guid item,Values data,JsonElement? before)
    {
        var id=before?.GetProperty("id").GetGuid()??Guid.NewGuid();
        var args=data.Snapshot().Select(x=>(Name:x.Key,Value:x.Value)).Concat(new (string Name,object? Value)[]{("id",id),("t",tenant),("c",company),("i",item)}).ToArray();
        if(before==null)
            await db.Execute("INSERT INTO masterdata.catalog_item_company(id,tenant_id,company_id,item_id,is_enabled,is_sellable,is_purchasable,track_stock,default_sales_uom_id,default_purchase_uom_id) VALUES(@id,@t,@c,@i,@is_enabled,@is_sellable,@is_purchasable,@track_stock,@default_sales_uom_id::uuid,@default_purchase_uom_id::uuid)",args);
        else
            await db.Execute("UPDATE masterdata.catalog_item_company SET is_enabled=@is_enabled,is_sellable=@is_sellable,is_purchasable=@is_purchasable,track_stock=@track_stock,default_sales_uom_id=@default_sales_uom_id::uuid,default_purchase_uom_id=@default_purchase_uom_id::uuid,version=version+1,updated_at=clock_timestamp() WHERE tenant_id=@t AND id=@id",args);
        var after=(await Existing(db,tenant,company,item,false))!.Value;
        await db.Audit(Security.State(ctx).User.Id,tenant,before==null?"create":"update","catalog-item-companies",id,new {item_id=item,company_id=company,version=after.GetProperty("version").GetInt64(),before=before.HasValue?Config(before.Value).Snapshot():null,after=data.Snapshot()});
    }
    // Conseguenza dell'archiviazione globale: nessun gate o filtro di ambito aziendale.
    // Il chiamante possiede gia il lock catalogo tenant e quello della radice archiviata.
    internal static async Task DisableForArchivedItem(HttpContext ctx,AppDb db,Guid tenant,Guid item)
    {
        Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var enabled=await JsonRows(db,"SELECT to_jsonb(x)::text FROM masterdata.catalog_item_company x WHERE tenant_id=@t AND item_id=@i AND is_enabled ORDER BY company_id,id FOR UPDATE",("t",tenant),("i",item));
        // Verificare tutte le revisioni prima della prima scrittura/audit aziendale.
        foreach(var before in enabled)
            Require(before.GetProperty("version").GetInt64()<MaxVersion,409,"version_exhausted");
        foreach(var before in enabled)
            await Write(ctx,db,tenant,before.GetProperty("company_id").GetGuid(),item,Config(before) with {IsEnabled=false},before);
    }
    // Parser condiviso con le prove native: nessuna coercizione o campo di revisione.
    internal static (Guid Company,Dictionary<string,JsonElement> Values)[] ParseCreationCompanies(JsonElement companies)
    {
        var rows=PartnerInput.Array(companies,100);
        var seen=new HashSet<Guid>();
        var result=new List<(Guid Company,Dictionary<string,JsonElement> Values)>();
        foreach(var row in rows) {
            var input=PartnerInput.Object(row,"company_id","values");
            Require(input.TryGetValue("company_id",out var rawId) && rawId.ValueKind==JsonValueKind.String,400,"invalid_company","company_id");
            Require(Guid.TryParseExact(rawId.GetString(),"D",out var company) && company!=Guid.Empty,400,"invalid_company","company_id");
            Require(seen.Add(company),400,"duplicate_company","company_id");
            Require(input.TryGetValue("values",out var values),400,"values_required");
            result.Add((company,PartnerInput.Object(values,CatalogItemCompany.Fields)));
        }
        return result.OrderBy(x=>x.Company).ToArray();
    }
    // Solo il POST della nuova radice chiama questo comando; nessun HTTP o commit autonomo.
    internal static async Task CreateForItem(HttpContext ctx,AppDb db,Guid tenant,Guid itemId,JsonElement companies)
    {
        Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var selected=ParseCreationCompanies(companies);
        if(selected.Length==0)return;
        var root=await Item(db,tenant,itemId,true);
        var defaults=Defaults(root);
        var pending=new List<(Guid Company,Values Data)>();
        foreach(var selection in selected) {
            // Come negli handler indipendenti, una company esterna al tenant e 404.
            var enabled=await Company(db,tenant,selection.Company,true);
            await CatalogCompanyAuthorization.Require(ctx,db,tenant,selection.Company,"create");
            var existing=await Existing(db,tenant,selection.Company,itemId,true);
            Require(!existing.HasValue,409,"company_item_exists");
            var merged=CatalogItemCompany.Merge(defaults,selection.Values,root.GetProperty("kind").GetString()!);
            CatalogItemCompany.CheckMutable(null,merged,root.GetProperty("status").GetString()!,enabled);
            await ValidateUnits(db,tenant,itemId,merged,null);
            pending.Add((selection.Company,merged));
        }
        foreach(var entry in pending)
            await Write(ctx,db,tenant,entry.Company,itemId,entry.Data,null);
    }
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Guid companyId,Guid itemId,JsonElement body,bool patch)
    {
        var tenant=await Tenant(ctx,db);
        // Existence checked before scope resolution so global foreign-company routes are 404.
        var companyEnabled=await Company(db,tenant,companyId,true);
        var root=await Item(db,tenant,itemId,true);
        var before=await Existing(db,tenant,companyId,itemId,true);
        Require(!patch || before.HasValue,404,"not_found");
        await CatalogCompanyAuthorization.Require(ctx,db,tenant,companyId,before.HasValue?"update":"create");
        var input=PartnerInput.Object(body,"values","expectedVersion");
        Require(input.TryGetValue("values",out var raw),400,"values_required");
        var values=PartnerInput.Object(raw,CatalogItemCompany.Fields);
        var expected=PartnerInput.Integer(input,"expectedVersion",0,MaxVersion);
        var actual=before?.GetProperty("version").GetInt64()??0;
        CatalogItemCompany.CheckVersion(expected,actual);
        var old=before.HasValue?Config(before.Value):null;
        var merged=CatalogItemCompany.Merge(old??Defaults(root),values,root.GetProperty("kind").GetString()!);
        CatalogItemCompany.CheckMutable(old,merged,root.GetProperty("status").GetString()!,companyEnabled);
        if(old==merged)return Results.Ok(await Read(db,tenant,companyId,itemId));
        Require(actual<MaxVersion,409,"version_exhausted");
        await ValidateUnits(db,tenant,itemId,merged,old);
        await Write(ctx,db,tenant,companyId,itemId,merged,before);
        return Results.Json(await Read(db,tenant,companyId,itemId),statusCode:before.HasValue?200:201);
    }
    private static Guid[] Ids(Dictionary<string,JsonElement> input,string field)
    {
        Require(input.TryGetValue(field,out var value),400,"field_required",field);
        var values=PartnerInput.Array(value,100);Require(values.Length>=1,400,"invalid_bulk_selection",field);
        var result=new HashSet<Guid>();
        foreach(var v in values) {
            Require(v.ValueKind==JsonValueKind.String,400,"invalid_bulk_selection",field);
            string? text;try {text=v.GetString();}catch(InvalidOperationException) {throw new ApiException(400,"invalid_bulk_selection",field);}
            Require(Guid.TryParseExact(text,"D",out var id) && id!=Guid.Empty && result.Add(id),400,"invalid_bulk_selection",field);
        }
        return result.Order().ToArray();
    }
    private static async Task<IResult> Bulk(HttpContext ctx,AppDb db,Guid? companyId,JsonElement body)
    {
        var tenant=await Tenant(ctx,db);
        await Security.Authorize(ctx,"catalog-item-companies.create");
        var input=PartnerInput.Object(body,companyId.HasValue?["itemIds"]:["itemIds","companyIds"]);
        var items=Ids(input,"itemIds");var companies=companyId.HasValue?[companyId.Value]:Ids(input,"companyIds");
        Require(items.Length*companies.Length<=500,400,"bulk_limit_exceeded");
        // Tutti i gate precedono ogni INSERT/audit, anche per coppie gia presenti.
        foreach(var company in companies) {
            var enabled=await Company(db,tenant,company);
            await CatalogCompanyAuthorization.Require(ctx,db,tenant,company,"create");
            Require(enabled,409,"company_disabled");
        }
        var roots=new Dictionary<Guid,JsonElement>();
        foreach(var item in items) {
            var root=await Item(db,tenant,item,true);
            Require(root.GetProperty("status").GetString()!="ARCHIVED",409,"archived_item");
            roots[item]=root;
        }
        foreach(var company in companies)Require(await Company(db,tenant,company,true),409,"company_disabled");
        var pairs=new List<(Guid Item,Guid Company,JsonElement? Before)>();
        foreach(var item in items)foreach(var company in companies)pairs.Add((item,company,await Existing(db,tenant,company,item,true)));
        var created=0;
        foreach(var pair in pairs)if(pair.Before==null) {await Write(ctx,db,tenant,pair.Company,pair.Item,Defaults(roots[pair.Item]),null);created++;}
        var rows=await Query(db,"x.tenant_id=@t AND x.item_id=ANY(@items::uuid[]) AND x.company_id=ANY(@companies::uuid[]) ORDER BY x.item_id,x.company_id",("t",tenant),("items",items),("companies",companies));
        return Results.Ok(new {created,unchanged=pairs.Count-created,items=rows});
    }
}
