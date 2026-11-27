using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Numbering;
using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;
using Npgsql;
using static Enginia360.Modules.Catalog.CatalogItem;

namespace Enginia360.Modules.Catalog;

public static class CatalogItemEndpoints
{
    private static readonly string[] MainFields=["code","name","description","item_type_id","category_id","base_uom_id","brand_id"];
    private static readonly string[] IdentifierFields=["identifier_type","value","uom_id","is_primary"];
    private static readonly string[] UnitFields=["uom_id","conversion_numerator","conversion_denominator","is_active"];
    private static readonly string[] PhysicalFields=["net_weight","gross_weight","weight_uom_id","length","width","height","dimension_uom_id"];
    private const string RootSelect="SELECT i.*,t.kind FROM masterdata.catalog_item i JOIN masterdata.catalog_item_type t ON t.tenant_id=i.tenant_id AND t.id=i.item_type_id";

    public static void Map(WebApplication app)
    {
        CatalogEndpoints.MapBrands(app);
        app.MapGet("/api/catalog/item-options",Options);
        app.MapGet("/api/catalog/items",List);
        app.MapGet("/api/catalog/items/{id:guid}",Get);
        app.MapPost("/api/catalog/items",(HttpContext ctx,AppDb db,JsonElement body)=>Mutation(()=>Save(ctx,db,null,body)));
        app.MapPut("/api/catalog/items/{id:guid}",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Mutation(()=>Save(ctx,db,id,body)));
        app.MapPut("/api/catalog/items/{id:guid}/status",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Mutation(()=>Status(ctx,db,id,body)));
        foreach(var route in new[]{"identifiers","units"}) {
            var child=route;
            app.MapPost("/api/catalog/items/{id:guid}/"+child,(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Mutation(()=>SaveChild(ctx,db,id,child,null,body)));
            app.MapPut("/api/catalog/items/{id:guid}/"+child+"/{childId:guid}",(HttpContext ctx,AppDb db,Guid id,Guid childId,JsonElement body)=>Mutation(()=>SaveChild(ctx,db,id,child,childId,body)));
            app.MapDelete("/api/catalog/items/{id:guid}/"+child+"/{childId:guid}",(HttpContext ctx,AppDb db,Guid id,Guid childId)=>Mutation(()=>DeleteChild(ctx,db,id,child,childId)));
        }
        app.MapPut("/api/catalog/items/{id:guid}/physical-data",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Mutation(()=>Physical(ctx,db,id,body)));
        app.MapPost("/api/catalog/items/{id:guid}/convert",Convert);
    }

    private static async Task<IResult> Mutation(Func<Task<IResult>> action)
    {
        try {return await action();}
        catch(PostgresException e) when(e.SqlState=="23505") {
            var code=e.ConstraintName switch {
                "catalog_item_reserved_code_unique" or "catalog_item_code_unique"=>"catalog_item_code_reserved",
                "catalog_identifier_primary_unique"=>"identifier_primary_exists",
                "catalog_identifier_unique"=>"identifier_already_assigned",
                _=>"catalog_child_duplicate"
            };
            throw new ApiException(409,code);
        }
        catch(PostgresException e) when(e.SqlState=="23503" && e.ConstraintName=="catalog_company_default_unit") {throw new ApiException(409,"company_default_unit_in_use");}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(400,"invalid_catalog_reference");}
        catch(PostgresException e) when(e.SqlState=="23514") {throw Constraint(e.MessageText);}
    }
    private static ApiException Constraint(string message)=>message switch {
        "Tipologia non attiva"=>new(400,"inactive_item_type","item_type_id"),
        "Categoria non attiva"=>new(400,"inactive_category","category_id"),
        "Marchio non attivo"=>new(400,"inactive_brand","brand_id"),
        "Base universale richiesta"=>new(400,"universal_base_required","base_uom_id"),
        "Unita base non attiva"=>new(400,"inactive_base_unit","base_uom_id"),
        "Base utilizzata da unita o identificativi"=>new(409,"item_base_has_dependencies","base_uom_id"),
        "Rapporto unita non coerente con la base"=>new(400,"inconsistent_unit_ratio","conversion_numerator"),
        "Unita non attiva"=>new(400,"inactive_unit","uom_id"),
        "Unita identificativo non associata attiva" or "Identificativo dipendente da unita non associata attiva"=>new(400,"identifier_unit_not_associated","uom_id"),
        "Dati fisici solo per beni"=>new(400,"physical_data_goods_only","physicalData"),
        "Unita dati fisici non coerenti"=>new(400,"invalid_physical_units","weight_uom_id,dimension_uom_id"),
        "Unita peso non attiva"=>new(400,"inactive_unit","weight_uom_id"),
        "Unita dimensioni non attiva"=>new(400,"inactive_unit","dimension_uom_id"),
        "Attivazione: riferimenti attivi richiesti"=>new(400,"activation_requires_active_references"),
        "Codice modificabile solo se sospeso mai attivato e manuale"=>new(409,"item_code_immutable","code"),
        "Codice e base immutabili dopo attivazione"=>new(409,"activated_item_code_base_immutable","code,base_uom_id"),
        "Natura immutabile"=>new(409,"immutable_item_kind","item_type_id"),
        _=>new(400,"catalog_item_constraint_violation")
    };

    private static async Task<Guid> Gate(HttpContext ctx,AppDb db,string permission)
    {
        await Security.Authorize(ctx,permission);
        return await Tenant(ctx,db);
    }
    private static async Task<Guid> Tenant(HttpContext ctx,AppDb db)
    {
        Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var tenant=Security.State(ctx).Tenant(ctx,"catalog")!.Value;
        Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.tenant WHERE id=@t AND is_enabled)",("t",tenant)))!,404,"not_found");
        // Stesso ordine di lock dei cataloghi e del numeratore; nessuna scrittura anticipata.
        await db.Execute("SELECT pg_advisory_xact_lock(hashtextextended('catalog:'||@t::text,0))",("t",tenant));
        return tenant;
    }
    private static async Task<List<Dictionary<string,object?>>> Rows(AppDb db,string sql,params (string Name,object? Value)[] parameters)
    {
        var rows=new List<Dictionary<string,object?>>();
        await using var cmd=await db.Command(sql,parameters);
        await using var reader=await cmd.ExecuteReaderAsync();
        while(await reader.ReadAsync()) {
            var row=new Dictionary<string,object?>();
            for(var i=0;i<reader.FieldCount;i++) {
                object? value=reader.IsDBNull(i)?null:reader.GetValue(i);
                if(value is decimal number) value=CatalogItem.Decimal(number);
                row[reader.GetName(i)]=value;
            }
            rows.Add(row);
        }
        return rows;
    }
    private static async Task<Dictionary<string,object?>> Root(AppDb db,Guid tenant,Guid id,bool locked=false)
    {
        var row=(await Rows(db,RootSelect+" WHERE i.tenant_id=@t AND i.id=@id"+(locked?" FOR UPDATE OF i":""),("t",tenant),("id",id))).SingleOrDefault();
        Require(row!=null,404,"not_found");
        row!["identifiers"]=await Rows(db,"SELECT * FROM masterdata.catalog_item_identifier WHERE tenant_id=@t AND item_id=@id ORDER BY identifier_type,is_primary DESC,id",("t",tenant),("id",id));
        row["units"]=await Rows(db,"SELECT * FROM masterdata.catalog_item_unit WHERE tenant_id=@t AND item_id=@id ORDER BY id",("t",tenant),("id",id));
        row["physicalData"]=(await Rows(db,"SELECT * FROM masterdata.catalog_item_physical_data WHERE tenant_id=@t AND item_id=@id",("t",tenant),("id",id))).SingleOrDefault();
        return row;
    }
    private static async Task<IResult> Get(HttpContext ctx,AppDb db,Guid id)
    {
        var tenant=await Gate(ctx,db,"catalog-items.read");
        return Results.Ok(await Root(db,tenant,id));
    }
    private static int QueryNumber(HttpContext ctx,string key,int fallback,int max)
    {
        var text=ctx.Request.Query[key].ToString();
        if(text.Length==0) return fallback;
        Require(int.TryParse(text,NumberStyles.None,CultureInfo.InvariantCulture,out var n) && n>=1 && n<=max,400,"invalid_paging");
        return n;
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db)
    {
        var tenant=await Gate(ctx,db,"catalog-items.read");
        var page=QueryNumber(ctx,"page",1,100000);var size=QueryNumber(ctx,"pageSize",25,100);
        var search=ctx.Request.Query["search"].ToString().Trim();
        Require(search.Length<=200 && !search.Any(char.IsControl),400,"invalid_search");
        var status=ctx.Request.Query["status"].ToString();var kind=ctx.Request.Query["kind"].ToString();
        Require(status is "" or "ACTIVE" or "SUSPENDED" or "ARCHIVED",400,"invalid_item_status");
        Require(kind is "" or "GOOD" or "INTANGIBLE" or "SERVICE" or "CHARGE",400,"invalid_item_kind");
        var typeText=ctx.Request.Query["itemTypeId"].ToString();
        Guid? itemTypeId=null;
        if(typeText.Length>0)
        {
            Require(Guid.TryParseExact(typeText,"D",out var parsed) && parsed!=Guid.Empty,400,"invalid_item_type","itemTypeId");
            itemTypeId=Guid.ParseExact(typeText,"D");
        }
        const string where=" WHERE i.tenant_id=@t AND (@status='' OR i.status=@status) AND (@kind='' OR t.kind=@kind) AND (CAST(@itemTypeId AS uuid) IS NULL OR i.item_type_id=@itemTypeId) AND (@search='' OR strpos(lower(i.name),lower(@search))>0 OR strpos(lower(i.code),lower(@search))>0 OR EXISTS(SELECT 1 FROM masterdata.catalog_item_identifier x WHERE x.tenant_id=i.tenant_id AND x.item_id=i.id AND (strpos(lower(x.value),lower(@search))>0 OR strpos(lower(x.normalized_value),lower(@search))>0)))";
        var parameters=new (string Name,object? Value)[]{("t",tenant),("status",status),("kind",kind),("itemTypeId",itemTypeId),("search",search),("limit",size),("offset",(page-1)*size)};
        var total=System.Convert.ToInt64(await db.Scalar("SELECT count(*) FROM ("+RootSelect+where+") q",parameters),CultureInfo.InvariantCulture);
        var items=await Rows(db,RootSelect+where+" ORDER BY lower(i.name),i.id LIMIT @limit OFFSET @offset",parameters);
        return Results.Ok(new {items,total,page,pageSize=size});
    }
    private static async Task<IResult> Options(HttpContext ctx,AppDb db)
    {
        // Nessuna autorita amministrativa sui riferimenti; solo il contesto minimo del form.
        var state=Security.State(ctx);
        var permission=new[]{"catalog-items.read","catalog-items.create","catalog-items.update"}.FirstOrDefault(code=>PermissionCatalog.Grants(state,code));
        Require(permission!=null,403,"forbidden");
        var tenant=await Gate(ctx,db,permission!);
        var types=await Rows(db,"SELECT id,name,code,kind,is_active,default_sellable,default_purchasable,default_track_stock FROM masterdata.catalog_item_type WHERE tenant_id=@t ORDER BY lower(name),id",("t",tenant));
        var categories=await Rows(db,"SELECT id,name,parent_id,is_active FROM masterdata.catalog_category WHERE tenant_id=@t ORDER BY lower(name),id",("t",tenant));
        var units=await Rows(db,"SELECT id,name,code,dimension,conversion_scope,factor_to_base,decimal_places,is_base,is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t ORDER BY lower(name),id",("t",tenant));
        var brands=await Rows(db,"SELECT id,name,code,is_active FROM masterdata.catalog_brand WHERE tenant_id=@t ORDER BY lower(name),id",("t",tenant));
        // Chiavi discriminatorie mai trasformate dal serializzatore camelCase.
        var good=await NumberingKernel.Read(db,tenant,"CATALOG_GOOD");var service=await NumberingKernel.Read(db,tenant,"CATALOG_SERVICE");
        var intangible=await NumberingKernel.Read(db,tenant,"CATALOG_INTANGIBLE");var charge=await NumberingKernel.Read(db,tenant,"CATALOG_CHARGE");
        return Results.Ok(new {types,categories,units,brands,numbering=new Dictionary<string,object> {
            ["GOOD"]=new {mode=good.Mode},["INTANGIBLE"]=new {mode=intangible.Mode},
            ["SERVICE"]=new {mode=service.Mode},["CHARGE"]=new {mode=charge.Mode}
        }});
    }

    private static Dictionary<string,JsonElement> Values(Dictionary<string,JsonElement> input,string[] fields)
    {
        Require(input.TryGetValue("values",out var value),400,"values_required");
        return PartnerInput.Object(value,fields);
    }
    private static string? Text(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,int max,bool required=false)
        =>values.ContainsKey(key)?PartnerInput.Text(values,key,max,required,key):before?.GetValueOrDefault(key) as string ?? (required?throw new ApiException(400,"field_required",key):null);
    private static Guid? Reference(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,bool required=false)
    {
        if(!values.TryGetValue(key,out var raw)) {
            var prior=before?.GetValueOrDefault(key) as Guid?;
            Require(!required || prior.HasValue,400,"field_required",key);return prior;
        }
        if(raw.ValueKind==JsonValueKind.Null) {Require(!required,400,"field_required",key);return null;}
        var text=PartnerInput.Text(values,key,36,true,key);
        Require(Guid.TryParseExact(text,"D",out var id) && id!=Guid.Empty,400,"invalid_catalog_reference",key);
        return id;
    }
    private static bool Flag(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,bool fallback)
        =>values.ContainsKey(key)?PartnerInput.Flag(values,key,key):before?.GetValueOrDefault(key) is bool old?old:fallback;
    private static decimal? Number(Dictionary<string,JsonElement> values,string key,Dictionary<string,object?>? before,bool positive)
    {
        var text=Text(values,key,before,30,positive);
        if(text==null) return null;
        if(!positive) return NonNegative(text,key);
        try {return CatalogConversion.Parse(text,true);}
        catch(ApiException) {throw new ApiException(400,"invalid_unit_ratio",key);}
    }
    private static long Expected(Dictionary<string,JsonElement> input)=>PartnerInput.Integer(input,"expectedVersion",1,MaxVersion);
    private static void Version(Dictionary<string,object?> root,long expected)
    {
        Require((long)root["version"]! == expected,409,"stale_version");
        Require(expected<MaxVersion,409,"version_exhausted");
        Require((string)root["status"]! != "ARCHIVED",409,"item_archived");
    }
    private static string Cast(string key)=>key.EndsWith("_id",StringComparison.Ordinal)?"::uuid":key is "conversion_numerator" or "conversion_denominator" or "net_weight" or "gross_weight" or "length" or "width" or "height"?"::numeric":key is "is_primary" or "is_active"?"::boolean":"::text";
    private static async Task Write(AppDb db,string table,Guid tenant,Guid item,Guid? child,Dictionary<string,object?> data,bool insert,bool root=false,bool physical=false,bool incrementRoot=true)
    {
        // table e colonne provengono esclusivamente dalle whitelist private, mai dal client.
        var parameters=data.Select(x=>(Name:x.Key,Value:x.Value)).ToList();
        parameters.Add(("tenant",tenant));parameters.Add(("record",root?item:child));parameters.Add(("parent",item));
        string Param(string key)=>"@"+key+Cast(key);
        if(insert) {
            var ids=physical?"tenant_id,item_id":"id,tenant_id"+(root?"":",item_id");
            var args=physical?"@tenant,@parent":"@record::uuid,@tenant"+(root?"":",@parent");
            await db.Execute("INSERT INTO masterdata."+table+"("+ids+","+string.Join(',',data.Keys)+") VALUES("+args+","+string.Join(',',data.Keys.Select(Param))+")",parameters.ToArray());
        } else {
            var where=physical?"item_id=@parent":"id=@record::uuid"+(root?"":" AND item_id=@parent");
            await db.Execute("UPDATE masterdata."+table+" SET "+string.Join(',',data.Keys.Select(k=>k+"="+Param(k)))+(root && incrementRoot?",version=version+1":"")+" WHERE tenant_id=@tenant AND "+where,parameters.ToArray());
        }
    }
    private static async Task Validate(AppDb db,Guid tenant,Guid id,bool activation=false)
        =>_ = await db.Scalar("SELECT masterdata.check_catalog_item(@t,@id,@activation)",("t",tenant),("id",id),("activation",activation));
    private static Dictionary<string,object?> MainValues(Dictionary<string,JsonElement> values,Dictionary<string,object?>? before)=>new() {
        ["name"]=Text(values,"name",before,200,true),["description"]=Text(values,"description",before,2000),
        ["item_type_id"]=Reference(values,"item_type_id",before,true),["category_id"]=Reference(values,"category_id",before,true),
        ["base_uom_id"]=Reference(values,"base_uom_id",before,true),["brand_id"]=Reference(values,"brand_id",before)
    };
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Guid? id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,id.HasValue?"catalog-items.update":"catalog-items.create");
        ClassificationTimeline.Require(!id.HasValue || body.ValueKind!=JsonValueKind.Object || !body.TryGetProperty("taxProfiles",out _),"tax_profile_initial_only",field:"taxProfiles");
        var input=PartnerInput.Object(body,id.HasValue?["values","expectedVersion","physicalData","status"]:["values","identifiers","units","physicalData","status","companies","taxProfiles"]);
        var values=Values(input,MainFields);
        var before=id.HasValue?await Root(db,tenant,id.Value,true):null;
        if(before!=null) Version(before,Expected(input));
        var currentStatus=before?["status"] as string;
        var requestedStatus=input.ContainsKey("status")?PartnerInput.Choice(input,"status","ACTIVE","SUSPENDED","ARCHIVED"):currentStatus??"ACTIVE";
        Require(id.HasValue || requestedStatus!="ARCHIVED",400,"invalid_item_status","status");
        var transition=id.HasValue && requestedStatus!=currentStatus;
        var activating=requestedStatus=="ACTIVE" && (!id.HasValue || transition);
        if(!id.HasValue && activating) await Gate(ctx,db,"catalog-items.activate");
        if(transition) {
            var permission=TransitionPermission(currentStatus!,requestedStatus);
            await Gate(ctx,db,permission);
        }
        var data=MainValues(values,before);var record=id??Guid.NewGuid();
        var type=(Guid)data["item_type_id"]!;
        var kind=await db.Scalar("SELECT kind FROM masterdata.catalog_item_type WHERE tenant_id=@t AND id=@type",("t",tenant),("type",type)) as string;
        Require(kind!=null,400,"invalid_item_type","item_type_id");
        // Il codice manuale va verificato esattamente come ricevuto, senza Trim o normalizzazioni.
        var code=before?.GetValueOrDefault("code") as string;
        if(values.TryGetValue("code",out var suppliedCode)) {
            Require(suppliedCode.ValueKind is JsonValueKind.String or JsonValueKind.Null,400,"invalid_field_value","code");
            code=suppliedCode.ValueKind==JsonValueKind.Null?null:suppliedCode.GetString();
            if(code=="") code=null;
        }
        if(before==null) {
            var config=await NumberingKernel.Read(db,tenant,"CATALOG_"+kind);
            if(config.Mode=="MANUAL" && code!=null) ValidateManualCode(code);
            data["code"]=await NumberingKernel.Allocate(db,tenant,"CATALOG_"+kind,code);
        }
        else {
            Require(kind==(string)before["kind"]!,409,"immutable_item_kind","item_type_id");
            Require(code!=null,400,"field_required","code");
            if(code!=(string)before["code"]!) {
                var config=await NumberingKernel.Read(db,tenant,"CATALOG_"+kind);
                Require((string)before["status"]! == "SUSPENDED" && before["activated_at"]==null && config.Mode=="MANUAL",409,"item_code_immutable","code");
                ValidateManualCode(code!);
            }
            if(before["activated_at"]!=null) Require(Equals(data["base_uom_id"],before["base_uom_id"]),409,"activated_item_code_base_immutable","base_uom_id");
            data["code"]=code;
        }
        var hasPhysical=id.HasValue && input.TryGetValue("physicalData",out _);
        var physicalValue=hasPhysical?input["physicalData"]:default;
        var oldPhysical=before?.GetValueOrDefault("physicalData") as Dictionary<string,object?>;
        // A child row mutation increments the root via its existing database trigger.
        var childWillWrite=hasPhysical && (physicalValue.ValueKind!=JsonValueKind.Null || oldPhysical!=null);
        var archiving=transition && requestedStatus=="ARCHIVED";
        // I dati obbligatori sono comuni a tutti gli stati; l'archivio segue le modifiche ai figli.
        if(!archiving) data["status"]=requestedStatus;
        await Write(db,"catalog_item",tenant,record,null,data,!id.HasValue,true,incrementRoot:!childWillWrite);
        if(hasPhysical) {
            if(physicalValue.ValueKind==JsonValueKind.Null) {
                if(oldPhysical!=null) await db.Execute("DELETE FROM masterdata.catalog_item_physical_data WHERE tenant_id=@t AND item_id=@id",("t",tenant),("id",record));
            } else {
                Require(CatalogItemKind.SupportsPhysicalData(kind),400,"physical_data_goods_only","physicalData");
                await WritePhysical(db,tenant,record,PartnerInput.Object(physicalValue,PhysicalFields),oldPhysical);
            }
        }
        if(!id.HasValue) {
            // Le associazioni precedono gli identificativi che possono dipendere da esse.
            if(input.TryGetValue("units",out var units)) foreach(var unit in PartnerInput.Array(units)) await WriteChild(db,tenant,record,"units",null,PartnerInput.Object(unit,UnitFields),null);
            if(input.TryGetValue("identifiers",out var identifiers)) foreach(var identifier in PartnerInput.Array(identifiers)) await WriteChild(db,tenant,record,"identifiers",null,PartnerInput.Object(identifier,IdentifierFields),null);
            if(input.TryGetValue("physicalData",out var physical) && physical.ValueKind!=JsonValueKind.Null) {
                Require(CatalogItemKind.SupportsPhysicalData(kind),400,"physical_data_goods_only","physicalData");
                await WritePhysical(db,tenant,record,PartnerInput.Object(physical,PhysicalFields),null);
            }
            if(input.TryGetValue("taxProfiles",out var taxProfiles))
                await TaxClassificationApplication.AssignInitial(ctx,db,ClassificationKind.Item,tenant,record,taxProfiles);
            // Configurazioni opt-in nella stessa transazione, dopo le unita alternative.
            if(input.TryGetValue("companies",out var companies))
                await CatalogItemCompanyEndpoints.CreateForItem(ctx,db,tenant,record,companies);
        }
        if(archiving) {
            await db.Execute("UPDATE masterdata.catalog_item SET status='ARCHIVED' WHERE tenant_id=@t AND id=@id",("t",tenant),("id",record));
            await CatalogItemCompanyEndpoints.DisableForArchivedItem(ctx,db,tenant,record);
        }
        await Validate(db,tenant,record,activating);
        var after=await Root(db,tenant,record);
        object? auditBefore=before==null?null:MainFields.ToDictionary(k=>k,k=>before.GetValueOrDefault(k));
        object auditAfter=id.HasValue?MainFields.ToDictionary(k=>k,k=>after.GetValueOrDefault(k)):after;
        if(hasPhysical) {
            ((Dictionary<string,object?>)auditBefore!)["physicalData"]=oldPhysical;
            ((Dictionary<string,object?>)auditAfter)["physicalData"]=after["physicalData"];
        }
        await db.Audit(Security.State(ctx).User.Id,tenant,id.HasValue?"update":"create","catalog-items",record,new {version=after["version"],before=auditBefore,after=auditAfter});
        if(transition || activating)
            await db.Audit(Security.State(ctx).User.Id,tenant,requestedStatus switch {"ACTIVE"=>"activate","SUSPENDED"=>"deactivate",_=>"archive"},"catalog-items",record,new {version=after["version"],before=new {status=currentStatus,activated_at=before?.GetValueOrDefault("activated_at")},after=new {status=after["status"],activated_at=after["activated_at"]}});
        return Results.Json(after,statusCode:id.HasValue?200:201);
    }
    private static async Task<IResult> Status(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        // Scegliere la policy dall'azione, non attribuire update come autorita di transizione.
        var input=PartnerInput.Object(body,"status","expectedVersion");
        var status=PartnerInput.Choice(input,"status","ACTIVE","SUSPENDED","ARCHIVED");
        var permission="catalog-items."+(status switch {"ACTIVE"=>"activate","SUSPENDED"=>"deactivate",_=>"archive"});
        var tenant=await Gate(ctx,db,permission);
        var before=await Root(db,tenant,id,true);Version(before,Expected(input));
        _=TransitionPermission((string)before["status"]!,status);
        _=MainValues(new(),before);
        await db.Execute("UPDATE masterdata.catalog_item SET status=@status,activated_at=CASE WHEN @status='ACTIVE' THEN coalesce(activated_at,now()) ELSE activated_at END,version=version+1 WHERE tenant_id=@t AND id=@id",("status",status),("t",tenant),("id",id));
        if(status=="ARCHIVED") await CatalogItemCompanyEndpoints.DisableForArchivedItem(ctx,db,tenant,id);
        await Validate(db,tenant,id,status=="ACTIVE");
        var after=await Root(db,tenant,id);
        await db.Audit(Security.State(ctx).User.Id,tenant,status switch {"ACTIVE"=>"activate","SUSPENDED"=>"deactivate",_=>"archive"},"catalog-items",id,new {version=after["version"],before=new {status=before["status"],activated_at=before["activated_at"]},after=new {status=after["status"],activated_at=after["activated_at"]}});
        return Results.Ok(after);
    }

    private static string ChildTable(string route)=>route=="units"?"catalog_item_unit":"catalog_item_identifier";
    private static List<Dictionary<string,object?>> Children(Dictionary<string,object?> root,string route)=>(List<Dictionary<string,object?>>)root[route]!;
    private static Dictionary<string,object?>? FindChild(Dictionary<string,object?> root,string route,Guid? id)
    {
        if(!id.HasValue) return null;
        var row=Children(root,route).SingleOrDefault(x=>(Guid)x["id"]! == id.Value);
        Require(row!=null,404,"not_found");return row;
    }
    private static async Task WriteChild(AppDb db,Guid tenant,Guid item,string route,Guid? id,Dictionary<string,JsonElement> values,Dictionary<string,object?>? before)
    {
        Dictionary<string,object?> data;
        if(route=="units") {
            data=new() {["uom_id"]=Reference(values,"uom_id",before,true),["conversion_numerator"]=Number(values,"conversion_numerator",before,true),["conversion_denominator"]=Number(values,"conversion_denominator",before,true),["is_active"]=Flag(values,"is_active",before,true)};
        } else {
            var type=Text(values,"identifier_type",before,10,true)!;var value=Text(values,"value",before,200,true)!;
            data=new() {["identifier_type"]=type,["value"]=value,["normalized_value"]=NormalizeIdentifier(type,value),["uom_id"]=Reference(values,"uom_id",before),["is_primary"]=Flag(values,"is_primary",before,false)};
        }
        await Write(db,ChildTable(route),tenant,item,id??Guid.NewGuid(),data,!id.HasValue);
    }
    private static async Task<IResult> SaveChild(HttpContext ctx,AppDb db,Guid id,string route,Guid? childId,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"catalog-items.update");
        var input=PartnerInput.Object(body,"values","expectedVersion");
        var root=await Root(db,tenant,id,true);Version(root,Expected(input));
        var before=FindChild(root,route,childId);
        var values=Values(input,route=="units"?UnitFields:IdentifierFields);
        await WriteChild(db,tenant,id,route,childId,values,before);
        return await ChildResult(ctx,db,tenant,id,route,root,childId.HasValue?"update":"create");
    }
    private static async Task<IResult> DeleteChild(HttpContext ctx,AppDb db,Guid id,string route,Guid childId)
    {
        var tenant=await Gate(ctx,db,"catalog-items.update");
        var root=await Root(db,tenant,id,true);
        Require(long.TryParse(ctx.Request.Query["expectedVersion"],NumberStyles.None,CultureInfo.InvariantCulture,out var expected) && expected>=1 && expected<=MaxVersion,400,"expected_version_required");
        Version(root,expected);_=FindChild(root,route,childId);
        await db.Execute("DELETE FROM masterdata."+ChildTable(route)+" WHERE tenant_id=@t AND item_id=@id AND id=@child",("t",tenant),("id",id),("child",childId));
        return await ChildResult(ctx,db,tenant,id,route,root,"delete");
    }
    private static async Task<IResult> ChildResult(HttpContext ctx,AppDb db,Guid tenant,Guid id,string part,Dictionary<string,object?> before,string operation)
    {
        await Validate(db,tenant,id);
        var after=await Root(db,tenant,id);
        await db.Audit(Security.State(ctx).User.Id,tenant,"update","catalog-items",id,new {version=after["version"],part,operation,before=before[part],after=after[part]});
        return Results.Ok(after);
    }
    private static async Task WritePhysical(AppDb db,Guid tenant,Guid id,Dictionary<string,JsonElement> values,Dictionary<string,object?>? before)
    {
        var data=PhysicalFields.ToDictionary(k=>k,k=>k.EndsWith("_id",StringComparison.Ordinal)?(object?)Reference(values,k,before):Number(values,k,before,false));
        var net=data["net_weight"] as decimal?;var gross=data["gross_weight"] as decimal?;
        Require(!net.HasValue || !gross.HasValue || gross>=net,400,"gross_weight_below_net","gross_weight");
        Require((net==null && gross==null) || data["weight_uom_id"]!=null,400,"weight_unit_required","weight_uom_id");
        Require((data["length"]==null && data["width"]==null && data["height"]==null) || data["dimension_uom_id"]!=null,400,"dimension_unit_required","dimension_uom_id");
        await Write(db,"catalog_item_physical_data",tenant,id,null,data,before==null,physical:true);
    }
    private static async Task<IResult> Physical(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"catalog-items.update");
        var input=PartnerInput.Object(body,"values","expectedVersion");
        var root=await Root(db,tenant,id,true);Version(root,Expected(input));
        Require(input.TryGetValue("values",out var value),400,"values_required");
        if(value.ValueKind==JsonValueKind.Null) {
            var deleted=await db.Execute("DELETE FROM masterdata.catalog_item_physical_data WHERE tenant_id=@t AND item_id=@id",("t",tenant),("id",id));
            if(deleted==0) await db.Execute("UPDATE masterdata.catalog_item SET version=version+1 WHERE tenant_id=@t AND id=@id",("t",tenant),("id",id));
        } else {
            Require(CatalogItemKind.SupportsPhysicalData((string)root["kind"]!),400,"physical_data_goods_only","physicalData");
            await WritePhysical(db,tenant,id,PartnerInput.Object(value,PhysicalFields),root["physicalData"] as Dictionary<string,object?>);
        }
        return await ChildResult(ctx,db,tenant,id,"physicalData",root,"update");
    }
    private static async Task<(string Numerator,string Denominator,int Places)> Ratio(AppDb db,Guid tenant,Dictionary<string,object?> root,Guid unit)
    {
        Require(root["base_uom_id"] is Guid,400,"item_base_unit_required","base_uom_id");
        var u=(await Rows(db,"SELECT decimal_places,is_active FROM masterdata.catalog_unit_of_measure WHERE tenant_id=@t AND id=@id",("t",tenant),("id",unit))).SingleOrDefault();
        Require(u!=null,400,"unit_not_associated","uom_id");
        Require((bool)u!["is_active"]!,400,"inactive_unit","uom_id");
        if((Guid)root["base_uom_id"]! == unit) return ("1","1",(int)u["decimal_places"]!);
        var association=Children(root,"units").SingleOrDefault(x=>(Guid)x["uom_id"]! == unit && (bool)x["is_active"]!);
        Require(association!=null,400,"unit_not_associated","uom_id");
        return ((string)association!["conversion_numerator"]!,(string)association["conversion_denominator"]!,(int)u["decimal_places"]!);
    }
    private static async Task<IResult> Convert(HttpContext ctx,AppDb db,Guid id,JsonElement body)
    {
        var tenant=await Gate(ctx,db,"catalog-items.read");
        var root=await Root(db,tenant,id);
        var input=PartnerInput.Object(body,"sourceUnitId","targetUnitId","quantity");
        var source=Reference(input,"sourceUnitId",null,true)!.Value;var target=Reference(input,"targetUnitId",null,true)!.Value;
        var a=await Ratio(db,tenant,root,source);var b=await Ratio(db,tenant,root,target);
        var quantity=PartnerInput.Text(input,"quantity",30,true,"quantity")!;
        var result=CatalogConversion.ConvertRatios(quantity,a.Numerator,a.Denominator,b.Numerator,b.Denominator,b.Places);
        return Results.Ok(new {quantity=result.Quantity,unroundedQuantity=result.UnroundedQuantity,rounded=result.Rounded,decimalPlaces=result.DecimalPlaces});
    }
}
