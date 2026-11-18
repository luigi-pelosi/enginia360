using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Modules.Geography;

public static class Geography
{
    public const string CountriesPath="/api/addresses/countries";
    public sealed record ImportRow(string Name,string PostalCode,string Province,string Region,string IstatCode);
    // Espressioni statiche: i valori cercati restano parametri SQL, senza nuove estensioni.
    public static string FoldSearch(string expression) => $"translate(lower({expression}),'àáâäèéêëìíîïòóôöùúûüçñ','aaaaeeeeiiiioooouuuucn')";
    public static string SearchExpression(Resource r) => r.Key switch {
        "cities" => "concat_ws(' ',name,postal_code,province,region)",
        "countries" => "concat_ws(' ',name,iso_code)",
        "users" => "concat_ws(' ',first_name,last_name)",
        _ => r.Fields.First(f=>f.Name is "name" or "key").Name
    };
    public static void ValidateCountryIdentity(Dictionary<string,object?> values,JsonElement before,bool hasCities)
    {
        if(values.TryGetValue("iso_code",out var iso))
            Check.Require(!hasCities || Equals(iso,before.GetProperty("iso_code").GetString()),409,"conflict");
    }
    public static AddressLookup.Item LocalItem(JsonElement row)
    {
        string Read(string name)=>row.TryGetProperty(name,out var v) && v.ValueKind==JsonValueKind.String ? v.GetString()! : "";
        var name=Read("name"); var postal=Read("postal_code"); var province=Read("province");
        return new(string.Join(" · ",new[]{name,postal,province,Read("country_name")}.Where(x=>x.Length>0)),"",name,province,postal,Read("iso_code"),Read("region"));
    }
    public static async Task<AddressLookup.Reply> Local(AppDb db,AddressLookup.Query query,CancellationToken cancellation)
    {
        if(query.Field=="address") return new([],"");
        // strpos tratta %, _ e apici come dati, non come wildcard SQL.
        await using var cmd=await db.Command($"""
            SELECT json_build_object('name',c.name,'postal_code',c.postal_code,'province',c.province,
                'region',c.region,'iso_code',n.iso_code,'country_name',n.name)::text
            FROM foundation.city c JOIN foundation.country n ON n.id=c.country_id
            WHERE c.is_enabled AND n.is_enabled AND (@country='' OR n.iso_code=@country)
                AND (@city='' OR {FoldSearch("c.name")}={FoldSearch("@city")})
                AND (@province='' OR lower(coalesce(c.province,''))=lower(@province))
                AND strpos({FoldSearch("concat_ws(' ',c.name,c.postal_code,c.province,c.region)")},{FoldSearch("@text")})>0
            ORDER BY lower(c.name),c.postal_code,lower(coalesce(c.province,'')),n.iso_code,c.id LIMIT 5
            """,("country",query.CountryCode),("city",query.Field is "postal_code" or "province" ? query.City : ""),
            ("province",query.Field == "postal_code" ? query.Province : ""),("text",query.Text));
        await using var reader=await cmd.ExecuteReaderAsync(cancellation); var items=new List<AddressLookup.Item>();
        while(await reader.ReadAsync(cancellation)) items.Add(LocalItem(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0))));
        return new(items.ToArray(),"");
    }
    public static async Task<IResult> Countries(HttpContext ctx,AppDb db)
    {
        foreach(var pair in ctx.Request.Query) Check.Require(pair.Key=="tenantId" && pair.Value.Count==1);
        await AddressLookup.Authorize(ctx);
        Security.State(ctx).Tenant(ctx,"sites");
        var items=new List<object>();
        await using var cmd=await db.Command("SELECT iso_code,name FROM foundation.country WHERE is_enabled ORDER BY lower(name),iso_code,id");
        await using var reader=await cmd.ExecuteReaderAsync(ctx.RequestAborted);
        while(await reader.ReadAsync(ctx.RequestAborted)) items.Add(new {isoCode=reader.GetString(0),name=reader.GetString(1)});
        return Results.Ok(new {provider="catalog",items});
    }
    public static ImportRow[] ParseImport(JsonElement body)
    {
        Check.Require(body.ValueKind==JsonValueKind.Array && body.GetArrayLength() is >0 and <=100000);
        var result=new List<ImportRow>(); var technical=new HashSet<string>(StringComparer.Ordinal); var natural=new HashSet<string>(StringComparer.Ordinal);
        foreach(var item in body.EnumerateArray()) {
            Check.Require(item.ValueKind==JsonValueKind.Object);
            var fields=new Dictionary<string,string>(StringComparer.Ordinal);
            foreach(var prop in item.EnumerateObject()) {
                var key=ResourceCatalog.ReadName(prop);
                Check.Require(key is "name" or "postal_code" or "province" or "region" or "country_iso_code" or "istat_code");
                var value=ResourceCatalog.ReadString(prop.Value);
                Check.Require(fields.TryAdd(key,value) && value.Length<=500 && !string.IsNullOrWhiteSpace(value) && value==value.Trim() && !value.Any(char.IsControl));
                // Stessa validazione Unicode del CRUD prima di aprire la transazione.
                ResourceCatalog.Validate(ResourceCatalog.Get("cities"),JsonSerializer.SerializeToElement(new {name=value}),false);
            }
            Check.Require(fields.Count==6);
            var name=fields["name"]; var postal=fields["postal_code"]; var province=fields["province"]; var region=fields["region"]; var istat=fields["istat_code"];
            bool Digits(string value,int length)=>value.Length==length && value.All(c=>c is >= '0' and <= '9');
            Check.Require(fields["country_iso_code"]=="IT" && Digits(postal,5) && Digits(istat,6));
            string Normalize(string value)=>value.Normalize(NormalizationForm.FormC).ToLowerInvariant();
            Check.Require(technical.Add(istat+"\0"+postal) && natural.Add(Normalize(name)+"\0"+Normalize(province)+"\0"+postal));
            result.Add(new(name,postal,province,region,istat));
        }
        return result.ToArray();
    }
    public static async Task Import(IServiceProvider services,string path)
    {
        // Comando esplicito per operatore fidato: prima l'intero file, poi ogni DML.
        Check.Require(Path.IsPathFullyQualified(path));
        var file=new FileInfo(path); Check.Require(file.Exists && file.Length<=67108864);
        using var document=JsonDocument.Parse(await File.ReadAllTextAsync(path),new JsonDocumentOptions {MaxDepth=8});
        var rows=ParseImport(document.RootElement);
        using var scope=services.CreateScope(); var db=scope.ServiceProvider.GetRequiredService<AppDb>();
        await using var tx=await db.Database.BeginTransactionAsync(); await Security.Lock(db);
        var countries=await db.Execute("INSERT INTO foundation.country(name,iso_code) VALUES ('Italia','IT') ON CONFLICT(iso_code) DO NOTHING");
        var country=(Guid)(await db.Scalar("SELECT id FROM foundation.country WHERE iso_code='IT'"))!;
        var inserted=0;
        // Nessun aggiornamento: nomi, note e stato corretti manualmente rimangono invariati.
        await using var cmd=await db.Command("""
            INSERT INTO foundation.city(country_id,name,postal_code,province,region,istat_code)
            VALUES (@country,@name,@postal,@province,@region,@istat) ON CONFLICT DO NOTHING
            """,("country",country),("name",""),("postal",""),("province",""),("region",""),("istat",""));
        await cmd.PrepareAsync();
        foreach(var row in rows) {
            cmd.Parameters["name"].Value=row.Name;cmd.Parameters["postal"].Value=row.PostalCode;
            cmd.Parameters["province"].Value=row.Province;cmd.Parameters["region"].Value=row.Region;cmd.Parameters["istat"].Value=row.IstatCode;
            inserted+=await cmd.ExecuteNonQueryAsync();
        }
        await db.Audit(null,null,"import_geography","cities",null,new {countriesInserted=countries,citiesInserted=inserted,citiesSkipped=rows.Length-inserted,total=rows.Length});
        await tx.CommitAsync();
        Console.WriteLine(JsonSerializer.Serialize(new {countriesInserted=countries,citiesInserted=inserted,citiesSkipped=rows.Length-inserted,total=rows.Length}));
    }
    public static void Map(WebApplication app)=>app.MapGet(CountriesPath,Countries);
}
