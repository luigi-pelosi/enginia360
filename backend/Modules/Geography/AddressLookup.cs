using Enginia360.Api.Resources;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
namespace Enginia360.Modules.Geography;

public static class AddressLookup
{
    public const string Path="/api/addresses/autocomplete";
    public sealed record Query(string Field,string Text,string CountryCode,string City,string Province,string Language);
    public sealed record Item(string label,string address,string city,string province,string postalCode,string countryCode,string? region=null);
    public sealed record Reply(Item[] items,string attribution);

    public static Query ParseQuery(HttpContext ctx)
    {
        var allowed=new[]{"tenantId","field","text","countryCode","city","province","language"};
        foreach(var pair in ctx.Request.Query) Check.Require(allowed.Contains(pair.Key,StringComparer.Ordinal) && pair.Value.Count==1);
        string Read(string name,int max) {var text=ctx.Request.Query[name].ToString().Trim(); Check.Require(text.Length<=max && !text.Any(char.IsControl)); return text;}
        var field=Read("field",20); var text=Read("text",200); var country=Read("countryCode",2); var language=Read("language",2);
        Check.Require(field is "address" or "city" or "province" or "postal_code"); Check.Require(text.Length>=3);
        Check.Require(country.Length==0 || CountryCodes.All.Contains(country,StringComparer.Ordinal));
        Check.Require(language.Length==0 || language is "it" or "en");
        return new(field,text,country,Read("city",200),Read("province",200),language.Length==0?"it":language);
    }
    internal static async Task Authorize(HttpContext ctx)
    {
        var service=ctx.RequestServices.GetRequiredService<Microsoft.AspNetCore.Authorization.IAuthorizationService>();
        Check.Require((await service.AuthorizeAsync(ctx.User,ctx,"sites.create")).Succeeded || (await service.AuthorizeAsync(ctx.User,ctx,"sites.update")).Succeeded,403,"forbidden");
    }
    public static async Task Prepare(HttpContext ctx,AppDb db)
    {
        await Authorize(ctx);
        Security.State(ctx).Tenant(ctx,"sites");
        var query=ParseQuery(ctx);
        // La ricerca locale termina nella transazione autorizzata dal middleware.
        ctx.Items[typeof(Reply)]=await Geography.Local(db,query,ctx.RequestAborted);
    }
    public static Task<IResult> Handle(HttpContext ctx)
    {
        Check.Require(ctx.Items.Remove(typeof(Reply),out var value) && value is Reply,403,"forbidden");
        return Task.FromResult(Results.Ok((Reply)value!));
    }
    public static void Map(WebApplication app)=>app.MapGet(Path,(Delegate)Handle);
}
