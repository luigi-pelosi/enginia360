using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Globalization;
using System.Text.Json;

namespace Enginia360.Modules.Numbering;

public sealed record NumberingConfig(string Mode,string Prefix,int Padding,long NextNumber,long Version);
public static class BusinessPartnerNumbering
{
    public const long Maximum=999999999999999;
    public static async Task<NumberingConfig> Read(AppDb db,Guid tenant)
    {
        await using var cmd=await db.Command("SELECT s.mode,s.prefix,s.padding,c.next_number,s.version FROM foundation.numbering_series s JOIN foundation.numbering_counter c ON c.series_id=s.id WHERE s.tenant_id=@t",("t",tenant));
        await using var reader=await cmd.ExecuteReaderAsync();
        return await reader.ReadAsync() ? new(reader.GetString(0),reader.GetString(1),reader.GetInt32(2),reader.GetInt64(3),reader.GetInt64(4)) : new("AUTO","BP-",6,1,0);
    }
    public static object Public(NumberingConfig c)=>new {mode=c.Mode,prefix=c.Prefix,padding=c.Padding,nextNumber=c.NextNumber,version=c.Version};
    private static async Task Ensure(AppDb db,Guid tenant,NumberingConfig c)
    {
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        await db.Execute("""
            WITH series AS (
                INSERT INTO foundation.numbering_series(tenant_id,mode,prefix,padding) VALUES(@t,@mode,@prefix,@padding)
                ON CONFLICT(tenant_id,entity_type) DO NOTHING RETURNING id
            ) INSERT INTO foundation.numbering_counter(tenant_id,series_id,next_number) SELECT @t,id,@next FROM series
            """,("t",tenant),("mode",c.Mode),("prefix",c.Prefix),("padding",c.Padding),("next",c.NextNumber));
    }
    public static async Task<string> Allocate(AppDb db,Guid tenant,string? manual)
    {
        var config=await Read(db,tenant);
        if(config.Mode=="MANUAL") Check.Require(!string.IsNullOrWhiteSpace(manual),400,"business_partner_code_required");
        else Check.Require(manual==null,400,"validation_error");
        Check.Require(config.Mode!="AUTO" || config.NextNumber<=Maximum,409,"numbering_exhausted");
        Check.Require(config.Version<9007199254740991L,409,"numbering_exhausted");
        await Ensure(db,tenant,config);
        // Il lock transazionale comune serializza anche il primo utilizzo e il salvataggio configurazione.
        await db.Execute("UPDATE foundation.numbering_counter SET used=true,next_number=next_number+@step WHERE tenant_id=@t",("step",config.Mode=="AUTO" ? 1 : 0),("t",tenant));
        await db.Execute("UPDATE foundation.numbering_series SET version=version+1 WHERE tenant_id=@t",("t",tenant));
        return config.Mode=="MANUAL" ? manual! : config.Prefix+config.NextNumber.ToString(CultureInfo.InvariantCulture).PadLeft(config.Padding,'0');
    }
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
            var before=await Read(db,tenant); Check.Require(version==before.Version,409,"stale_version");
            var used=(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.numbering_counter WHERE tenant_id=@t AND used)",("t",tenant)))!;
            var same=mode==before.Mode && prefix==before.Prefix && padding==before.Padding && next==before.NextNumber;
            Check.Require(!used || same,409,"numbering_in_use");
            if(!used) {
                var desired=new NumberingConfig(mode,prefix,padding,next,version);
                await Ensure(db,tenant,desired);
                if(version>0) await db.Execute("UPDATE foundation.numbering_series SET mode=@mode,prefix=@prefix,padding=@padding,version=version+1 WHERE tenant_id=@t",("mode",mode),("prefix",prefix),("padding",padding),("t",tenant));
                await db.Execute("UPDATE foundation.numbering_counter SET next_number=@next WHERE tenant_id=@t",("next",next),("t",tenant));
                await db.Audit(state.User.Id,tenant,"update","business-partner-numbering",null,new{before=Public(before),after=Public(await Read(db,tenant))});
            }
            return Results.Ok(Public(await Read(db,tenant)));
        });
    }
}
