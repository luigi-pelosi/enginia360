using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Organizations;
using Enginia360.Shared.Validation;
using GeographyCatalog = global::Enginia360.Modules.Geography.Geography;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using NpgsqlTypes;

namespace Enginia360.Api.Resources;

public static class DataEndpoints
{
    public static void Map(WebApplication app)
    {
        Enginia360.Modules.BusinessPartners.BusinessPartnerEndpoints.Map(app);
        Enginia360.Modules.Numbering.BusinessPartnerNumbering.Map(app);
        app.MapGet("/api/resources",(HttpContext ctx) => Results.Ok(Resources.All.Values.Select(r => new {r.Key,r.Fields,ReadOnly=Resources.MetaReadOnly(r,Security.State(ctx).User)})));
        app.MapGet("/api/data/{resource}",async (HttpContext ctx,AppDb db,string resource) => {
            var r=Resources.Get(resource); var state=Security.State(ctx); await Security.AuthorizeResource(ctx,r,"read");
            var tenant=state.Tenant(ctx,resource);
            var page=ParseInt(ctx,"page",1,1,100000); var size=ParseInt(ctx,"pageSize",25,1,100);
            var search=ctx.Request.Query["search"].ToString(); Check.Require(search.Length <=200 && !search.Contains('\0'));
            var searchField=GeographyCatalog.SearchExpression(r);
            var scope=Resources.ListScope(r,state.User);
            var match=Resources.IsGlobalMaster(resource) ? $"strpos({GeographyCatalog.FoldSearch(searchField)},{GeographyCatalog.FoldSearch("@search")}) > 0" : $"strpos(lower({searchField}),lower(@search)) > 0";
            var where=$"{scope} AND (@search='' OR {match})";
            var total=await db.Scalar($"SELECT count(*) FROM {SqlNames.Table(r.Table)} WHERE {where}",("tenant",tenant),("search",search),("viewer",state.User.Id));
            var order=Resources.IsGlobalMaster(resource) ? "lower(name),"+(resource=="cities" ? "postal_code," : "iso_code,")+"id" : "created_at,id";
            await using var cmd=await db.Command($"SELECT {Resources.Projection(r)} FROM {SqlNames.Table(r.Table)} t WHERE {where} ORDER BY {order} LIMIT @size OFFSET @offset",("tenant",tenant),("search",search),("viewer",state.User.Id),("size",size),("offset",(page-1)*size));
            await using var reader=await cmd.ExecuteReaderAsync(); var items=new List<JsonElement>();
            while(await reader.ReadAsync()) items.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));
            return Results.Ok(new {items,total,page,pageSize=size});
        });
        app.MapPost("/api/data/{resource}/save",(HttpContext ctx,AppDb db,string resource,JsonElement body) => Save(ctx,db,resource,null,body));
        app.MapPut("/api/data/{resource}/{id:guid}/save",(HttpContext ctx,AppDb db,string resource,Guid id,JsonElement body) => Save(ctx,db,resource,id,body));
        app.MapGet("/api/data/purchasing-organizations/{id:guid}/coverage",async (HttpContext ctx,AppDb db,Guid id) => {
            await Security.Authorize(ctx,"purchasing-organizations.read");
            var tenant=Security.State(ctx).Tenant(ctx,"purchasing-organizations")!.Value;
            await Resources.EnsureRow(db,Resources.Get("purchasing-organizations"),id,tenant);
            return Results.Ok(new {coverage=await PurchasingCoverage.Read(db,tenant,id)});
        });
        app.MapPost("/api/data/{resource}",async (HttpContext ctx,AppDb db,string resource,JsonElement body) => {
            var r=Resources.Get(resource); var state=Security.State(ctx); await Security.AuthorizeResource(ctx,r,"create"); var tenant=state.Tenant(ctx,resource);
            var after=await Create(db,r,state,tenant,Resources.Validate(r,body,true));
            return Results.Json(after,statusCode:201);
        });
        app.MapPut("/api/data/{resource}/{id:guid}",async (HttpContext ctx,AppDb db,string resource,Guid id,JsonElement body) => {
            var r=Resources.Get(resource); var state=Security.State(ctx); await Security.AuthorizeResource(ctx,r,"update"); var tenant=state.Tenant(ctx,resource);
            var after=await Update(db,r,state,tenant,id,Resources.Validate(r,body,false));
            return Results.Ok(after);
        });
        app.MapDelete("/api/data/{resource}/{id:guid}",async (HttpContext ctx,AppDb db,string resource,Guid id) => {
            var r=Resources.Get(resource); var state=Security.State(ctx); await Security.AuthorizeResource(ctx,r,"delete"); var tenant=state.Tenant(ctx,resource);
            var before=HasSnapshots(resource) ? await Resources.Row(db,r,id,tenant) : null;
            PurchasingCoverage.Entry[]? coverage=null;
            if(resource=="purchasing-organizations") {
                Check.Require(before.HasValue,404,"not_found");
                coverage=await PurchasingCoverage.Read(db,tenant!.Value,id);
                await PurchasingCoverage.Remove(db,tenant.Value,id);
            }
            // Solo le voci applicative vengono rimosse: ogni altro riferimento resta RESTRICT.
            if(resource == "tenants") await db.Execute("DELETE FROM foundation.permission WHERE tenant_id=@id AND is_system",("id",id));
            var changed=await db.Execute($"DELETE FROM {SqlNames.Table(r.Table)} WHERE id=@id AND {Resources.Scope(r)}",("id",id),("tenant",tenant));
            Check.Require(changed==1,404,"not_found");
            object? details=coverage!=null ? new {before,after=(JsonElement?)null,coverage}
                : HasSnapshots(resource) ? new {before,after=(JsonElement?)null} : null;
            await db.Audit(state.User.Id,tenant,"delete",resource,id,details);
            return Results.NoContent();
        });
        app.MapGet("/api/links/{relation}/{ownerId:guid}",async (HttpContext ctx,AppDb db,string relation,Guid ownerId) => {
            Check.Require(Resources.Links.TryGetValue(relation,out var link),404,"not_found");
            var state=Security.State(ctx); await Security.Authorize(ctx,link!.OwnerResource+".read"); var tenant=state.Tenant(ctx,link.OwnerResource);
            await Resources.EnsureRow(db,Resources.Get(link.OwnerResource),ownerId,tenant);
            var ids=await LinkIds(db,link,ownerId,tenant,true);
            return Results.Ok(new {ids});
        });
        app.MapPut("/api/links/{relation}/{ownerId:guid}",async (HttpContext ctx,AppDb db,string relation,Guid ownerId,JsonElement body) => {
            Check.Require(Resources.Links.TryGetValue(relation,out var link),404,"not_found");
            var state=Security.State(ctx); await Security.Authorize(ctx,link!.Permission); var tenant=state.Tenant(ctx,link.OwnerResource);
            Check.Require(body.ValueKind == JsonValueKind.Object && body.EnumerateObject().Count()==1 && body.TryGetProperty("ids",out _));
            var ids=ParseLinkIds(body.GetProperty("ids"));
            await ReplaceLinks(db,link,relation,state,tenant,ownerId,ids);
            return Results.NoContent();
        });
    }
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,string resource,Guid? ownerId,JsonElement body)
    {
        var r=Resources.Get(resource); var state=Security.State(ctx);
        var create=!ownerId.HasValue;
        Check.Require(!r.ReadOnly,403,"forbidden");
        Check.Require(body.ValueKind==JsonValueKind.Object);
        JsonElement? valuesBody=null; JsonElement? linksBody=null; PurchasingCoverage.Entry[]? coverage=null;
        var names=new HashSet<string>(StringComparer.Ordinal);
        foreach(var prop in body.EnumerateObject())
        {
            var name=Resources.ReadName(prop);
            Check.Require(names.Add(name) && name is "values" or "links" or "coverage");
            if(name=="coverage") {
                Check.Require(resource=="purchasing-organizations");
                coverage=PurchasingCoverage.Parse(prop.Value); continue;
            }
            Check.Require(prop.Value.ValueKind==JsonValueKind.Object);
            if(name=="values") valuesBody=prop.Value; else linksBody=prop.Value;
        }
        Check.Require(ownerId.HasValue || valuesBody.HasValue);
        var links=new Dictionary<string,HashSet<Guid>>(StringComparer.Ordinal);
        if(linksBody.HasValue) foreach(var prop in linksBody.Value.EnumerateObject())
        {
            var name=Resources.ReadName(prop);
            Check.Require(!links.ContainsKey(name) && Resources.Links.TryGetValue(name,out var relation) && relation.OwnerResource==resource);
            links.Add(name,ParseLinkIds(prop.Value));
        }
        Check.Require(valuesBody.HasValue || links.Count>0 || coverage!=null);
        // Tutti i gate precedono letture/scritture; l'identità resta quella fresca sotto lock middleware.
        if(valuesBody.HasValue) await Security.AuthorizeResource(ctx,r,ownerId.HasValue ? "update" : "create");
        foreach(var name in links.Keys) await Security.Authorize(ctx,Resources.Links[name].Permission);
        if(coverage!=null) await Security.Authorize(ctx,PurchasingCoverage.Permission);
        var tenant=state.Tenant(ctx,resource);
        var values=valuesBody.HasValue ? Resources.Validate(r,valuesBody.Value,!ownerId.HasValue) : null;
        JsonElement? after=null;
        if(!ownerId.HasValue)
        {
            after=await Create(db,r,state,tenant,values!);
            ownerId=after.Value.GetProperty("id").GetGuid();
        }
        else if(values != null) after=await Update(db,r,state,tenant,ownerId.Value,values);
        foreach(var (name,ids) in links) await ReplaceLinks(db,Resources.Links[name],name,state,tenant,ownerId.Value,ids);
        if(coverage!=null) await PurchasingCoverage.Replace(db,state,tenant!.Value,ownerId.Value,coverage);
        return after.HasValue ? Results.Json(after,statusCode:create ? 201 : 200)
            : Results.Ok(new {id=ownerId.Value});
    }
    private static HashSet<Guid> ParseLinkIds(JsonElement list)
    {
        Check.Require(list.ValueKind==JsonValueKind.Array && list.GetArrayLength()<=500);
        var ids=new HashSet<Guid>();
        foreach(var v in list.EnumerateArray()) {Check.Require(Guid.TryParse(Resources.ReadString(v),out var id) && id != Guid.Empty && ids.Add(id));}
        return ids;
    }
    private static async Task<JsonElement> Create(AppDb db,Resource r,IdentityState state,Guid? tenant,Dictionary<string,object?> values)
    {
        var resource=r.Key;
        await Resources.ValidateReferences(db,r,values,tenant);
        var id=Guid.NewGuid();
        var fields=values.Keys.ToList();
        await using var cmd=await db.Command("SELECT 1");
        AddValues(cmd,r,values);
        cmd.Parameters.AddWithValue("id",id);
        if(resource != "tenants" && !Resources.IsGlobalMaster(resource)) {fields.Add("tenant_id"); cmd.Parameters.AddWithValue("tenant_id",tenant!.Value);}
        fields.Add("id");
        cmd.CommandText=$"INSERT INTO {SqlNames.Table(r.Table)} ({string.Join(',',fields)}) VALUES ({string.Join(',',fields.Select(x => "@"+x))})";
        await cmd.ExecuteNonQueryAsync();
        if(resource == "tenants") await PermissionCatalog.Seed(db,id);
        var after=await Resources.Row(db,r,id,tenant);
        object? details=HasSnapshots(resource) ? new {before=(JsonElement?)null,after}
            : resource == "tenants" ? new {permissionCatalog=PermissionCatalog.Codes} : null;
        await db.Audit(state.User.Id,tenant,"create",resource,id,details);
        return after!.Value;
    }
    private static async Task<JsonElement> Update(AppDb db,Resource r,IdentityState state,Guid? tenant,Guid id,Dictionary<string,object?> values)
    {
        var resource=r.Key;
        await Resources.EnsureRow(db,r,id,tenant); await Resources.ValidateReferences(db,r,values,tenant);
        var before=HasSnapshots(resource) ? await Resources.Row(db,r,id,tenant) : null;
        if(resource == "countries" && values.ContainsKey("iso_code"))
            GeographyCatalog.ValidateCountryIdentity(values,before!.Value,(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.city WHERE country_id=@id)",("id",id)))!);
        if(resource == "sites") Resources.ValidateTaxIdentity(values,before);
        var revoke=resource == "users" && (values.ContainsKey("username") || values.ContainsKey("is_enabled"))
            ? ",security_stamp=gen_random_uuid()" : "";
        await using var cmd=await db.Command($"UPDATE {SqlNames.Table(r.Table)} SET {string.Join(',',values.Keys.Select(f => f+"=@"+f))}{revoke} WHERE id=@id AND {Resources.Scope(r)}",("id",id),("tenant",tenant));
        AddValues(cmd,r,values); Check.Require(await cmd.ExecuteNonQueryAsync()==1,404,"not_found");
        // La stessa identità può essere già tracciata dal middleware: riallineare tutti i valori.
        if(resource == "users")
            foreach(var entry in db.ChangeTracker.Entries<User>().Where(e => e.Entity.Id==id).ToArray())
                await entry.ReloadAsync();
        var after=await Resources.Row(db,r,id,tenant);
        await db.Audit(state.User.Id,tenant,"update",resource,id,HasSnapshots(resource) ? new {before,after} : null);
        return after!.Value;
    }
    private static bool HasSnapshots(string resource) => Resources.IsGlobalMaster(resource) || resource is "sites" or "roles" or "groups" or "sales-organizations" or "purchasing-organizations";
    private static async Task ReplaceLinks(AppDb db,Relation link,string relation,IdentityState state,Guid? tenant,Guid ownerId,HashSet<Guid> ids)
    {
        await Resources.EnsureRow(db,Resources.Get(link.OwnerResource),ownerId,tenant);
        foreach(var id in ids) Check.Require(await Resources.Row(db,Resources.Get(link.TargetResource),id,tenant) != null);
        var beforeIds=await LinkIds(db,link,ownerId,tenant);
        await db.Execute($"DELETE FROM {SqlNames.Table(link.Table)} WHERE tenant_id=@tenant AND {link.OwnerColumn}=@id",("tenant",tenant),("id",ownerId));
        foreach(var id in ids) await db.Execute($"INSERT INTO {SqlNames.Table(link.Table)}(tenant_id,{link.OwnerColumn},{link.TargetColumn}) VALUES (@tenant,@owner,@id)",("tenant",tenant),("owner",ownerId),("id",id));
        await db.Audit(state.User.Id,tenant,"replace_links",relation,ownerId,new {beforeIds,afterIds=ids.Order().ToArray()});
    }
    private static async Task<Guid[]> LinkIds(AppDb db,Relation link,Guid owner,Guid? tenant,bool visibleOnly=false)
    {
        var visible=visibleOnly ? $" AND {link.TargetColumn} IN (SELECT id FROM {SqlNames.Table(Resources.Get(link.TargetResource).Table)} WHERE {Resources.Scope(Resources.Get(link.TargetResource))})" : "";
        await using var cmd=await db.Command($"SELECT {link.TargetColumn} FROM {SqlNames.Table(link.Table)} WHERE tenant_id=@tenant AND {link.OwnerColumn}=@id{visible} ORDER BY {link.TargetColumn}",("tenant",tenant),("id",owner));
        await using var reader=await cmd.ExecuteReaderAsync(); var ids=new List<Guid>();
        while(await reader.ReadAsync()) ids.Add(reader.GetGuid(0));
        return ids.ToArray();
    }
    private static int ParseInt(HttpContext ctx,string key,int fallback,int min,int max)
    {
        var text=ctx.Request.Query[key].ToString(); if(text.Length==0) return fallback;
        Check.Require(int.TryParse(text,out var result) && result>=min && result<=max); return result;
    }
    private static void AddValues(NpgsqlCommand cmd,Resource r,Dictionary<string,object?> values)
    {
        foreach(var (key,value) in values)
        {
            var type=r.Fields.Single(f => f.Name==key).Type;
            cmd.Parameters.Add(new NpgsqlParameter(key,type switch { "multiselect" => NpgsqlDbType.Array | NpgsqlDbType.Text,"date" => NpgsqlDbType.Date,"boolean" => NpgsqlDbType.Boolean,"reference" => NpgsqlDbType.Uuid,"json" => NpgsqlDbType.Jsonb,_ => NpgsqlDbType.Text }) {Value=value ?? DBNull.Value});
        }
    }
}
