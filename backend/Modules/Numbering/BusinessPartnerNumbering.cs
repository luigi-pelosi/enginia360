using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Text.Json;

namespace Enginia360.Modules.Numbering;

public sealed record NumberingConfig(string Mode,string Prefix,int Padding,long NextNumber,long Version);
public static class BusinessPartnerNumbering
{
    public const long Maximum=NumberingKernel.Maximum;
    private const string Entity="BUSINESS_PARTNER";
    public static Task<NumberingConfig> Read(AppDb db,Guid tenant)=>NumberingKernel.Read(db,tenant,Entity);
    public static object Public(NumberingConfig c)=>new {mode=c.Mode,prefix=c.Prefix,padding=c.Padding,nextNumber=c.NextNumber,version=c.Version};
    public static Task<string> Allocate(AppDb db,Guid tenant,string? manual)=>NumberingKernel.Allocate(db,tenant,Entity,manual);
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/business-partner-numbering",async(HttpContext ctx,AppDb db)=>{
            await Security.Authorize(ctx,"business-partner-numbering.read");
            return Results.Ok(Public(await Read(db,Security.State(ctx).Tenant(ctx,"business-partners")!.Value)));
        });
        app.MapPut("/api/business-partner-numbering",async(HttpContext ctx,AppDb db,JsonElement body)=>{
            await Security.Authorize(ctx,"business-partner-numbering.update"); var state=Security.State(ctx);var tenant=state.Tenant(ctx,"business-partners")!.Value;
            var input=PartnerInput.Object(body,"mode","prefix","padding","nextNumber","version");
            var mode=PartnerInput.Choice(input,"mode","AUTO","MANUAL");
            Check.Require(input.TryGetValue("prefix",out var prefixValue) && prefixValue.ValueKind==JsonValueKind.String);
            var prefix=prefixValue.GetString()!; Check.Require(prefix.Length<=32 && prefix.All(c=>c is >= ' ' and <= '~'));
            var padding=(int)PartnerInput.Integer(input,"padding",1,15); var next=PartnerInput.Integer(input,"nextNumber",1,Maximum+1);
            var version=PartnerInput.Integer(input,"version",0,9007199254740990L);
            var before=await Read(db,tenant);
            var after=await NumberingKernel.Save(db,tenant,Entity,new(mode,prefix,padding,next,version));
            if(after!=before) await db.Audit(state.User.Id,tenant,"update","business-partner-numbering",null,new{before=Public(before),after=Public(after)});
            return Results.Ok(Public(after));
        });
    }
}
