using System.Globalization;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Numbering;

// Nucleo indipendente dal dominio: nessun endpoint di allocazione senza entita persistita.
public static class NumberingKernel
{
    public const long Maximum=999999999999999;
    public const long MaxVersion=9007199254740991;
    public static string Prefix(string entity)=>entity switch {"BUSINESS_PARTNER"=>"BP-","CATALOG_GOOD"=>"ART-","CATALOG_INTANGIBLE"=>"IMM-","CATALOG_SERVICE"=>"SRV-","CATALOG_CHARGE"=>"ONR-",_=>throw new ApiException(400,"invalid_numbering_kind")};
    private static async Task Gate(AppDb db,string entity)
    {
        _=Prefix(entity);
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        await Security.Lock(db);
    }
    public static async Task<NumberingConfig> Read(AppDb db,Guid tenant,string entity)
    {
        var prefix=Prefix(entity);
        await using var cmd=await db.Command("SELECT s.mode,s.prefix,s.padding,c.next_number,s.version FROM foundation.numbering_series s JOIN foundation.numbering_counter c ON c.tenant_id=s.tenant_id AND c.series_id=s.id WHERE s.tenant_id=@t AND s.entity_type=@entity",("t",tenant),("entity",entity));
        await using var r=await cmd.ExecuteReaderAsync();
        return await r.ReadAsync()?new(r.GetString(0),r.GetString(1),r.GetInt32(2),r.GetInt64(3),r.GetInt64(4)):new("AUTO",prefix,6,1,0);
    }
    private static async Task Ensure(AppDb db,Guid tenant,string entity,NumberingConfig config)
    {
        await db.Execute("""
            WITH series AS (
                INSERT INTO foundation.numbering_series(tenant_id,entity_type,mode,prefix,padding)
                VALUES(@t,@entity,@mode,@prefix,@padding)
                ON CONFLICT(tenant_id,entity_type) DO NOTHING RETURNING id
            ) INSERT INTO foundation.numbering_counter(tenant_id,series_id,next_number) SELECT @t,id,@next FROM series
            """,("t",tenant),("entity",entity),("mode",config.Mode),("prefix",config.Prefix),("padding",config.Padding),("next",config.NextNumber));
    }
    public static async Task<NumberingConfig> Save(AppDb db,Guid tenant,string entity,NumberingConfig desired)
    {
        await Gate(db,entity);
        Check.Require(desired.Mode is "AUTO" or "MANUAL");
        Check.Require(desired.Prefix.Length<=32 && desired.Prefix.All(c=>c is >= ' ' and <= '~'));
        Check.Require(desired.Padding is >=1 and <=15 && desired.NextNumber is >=1 and <=Maximum+1 && desired.Version is >=0 and <MaxVersion);
        var before=await Read(db,tenant,entity);
        Check.Require(desired.Version==before.Version,409,"stale_version");
        var used=(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM foundation.numbering_counter c JOIN foundation.numbering_series s ON s.tenant_id=c.tenant_id AND s.id=c.series_id WHERE s.tenant_id=@t AND s.entity_type=@entity AND c.used)",("t",tenant),("entity",entity)))!;
        var same=desired.Mode==before.Mode && desired.Prefix==before.Prefix && desired.Padding==before.Padding && desired.NextNumber==before.NextNumber;
        Check.Require(!used || same,409,"numbering_in_use");
        if(used) return before;
        await Ensure(db,tenant,entity,desired);
        if(before.Version>0) await db.Execute("UPDATE foundation.numbering_series SET mode=@mode,prefix=@prefix,padding=@padding,version=version+1 WHERE tenant_id=@t AND entity_type=@entity",("mode",desired.Mode),("prefix",desired.Prefix),("padding",desired.Padding),("t",tenant),("entity",entity));
        await db.Execute("UPDATE foundation.numbering_counter c SET next_number=@next FROM foundation.numbering_series s WHERE s.id=c.series_id AND s.tenant_id=c.tenant_id AND s.tenant_id=@t AND s.entity_type=@entity",("next",desired.NextNumber),("t",tenant),("entity",entity));
        return await Read(db,tenant,entity);
    }
    public static async Task<string> Allocate(AppDb db,Guid tenant,string entity,string? manual)
    {
        await Gate(db,entity);
        var config=await Read(db,tenant,entity);
        Check.Require(config.Mode!="MANUAL" || !string.IsNullOrWhiteSpace(manual),400,entity=="BUSINESS_PARTNER"?"business_partner_code_required":"catalog_code_required");
        Check.Require(config.Mode!="AUTO" || manual==null);
        Check.Require(config.Mode!="AUTO" || config.NextNumber<=Maximum,409,"numbering_exhausted");
        Check.Require(config.Version<MaxVersion,409,"numbering_exhausted");
        await Ensure(db,tenant,entity,config);
        await db.Execute("UPDATE foundation.numbering_counter c SET used=true,next_number=next_number+@step FROM foundation.numbering_series s WHERE s.id=c.series_id AND s.tenant_id=c.tenant_id AND s.tenant_id=@t AND s.entity_type=@entity",("step",config.Mode=="AUTO"?1:0),("t",tenant),("entity",entity));
        await db.Execute("UPDATE foundation.numbering_series SET version=version+1 WHERE tenant_id=@t AND entity_type=@entity",("t",tenant),("entity",entity));
        return config.Mode=="MANUAL"?manual!:config.Prefix+config.NextNumber.ToString(CultureInfo.InvariantCulture).PadLeft(config.Padding,'0');
    }
}
