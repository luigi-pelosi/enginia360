using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Modules.Numbering;
using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;

namespace Enginia360.Modules.BusinessPartners;

public static class BusinessPartnerEndpoints
{
    private const string Root="/api/data/business-partners";
    public static void Map(WebApplication app)
    {
        app.MapPost(Root+"/save",(HttpContext ctx,AppDb db,JsonElement body)=>Save(ctx,db,null,body));
        app.MapPut(Root+"/{id:guid}/save",(HttpContext ctx,AppDb db,Guid id,JsonElement body)=>Save(ctx,db,id,body));
        app.MapPost(Root,()=>Results.Json(new{code="aggregate_save_required"},statusCode:405));
        app.MapPut(Root+"/{id:guid}",()=>Results.Json(new{code="aggregate_save_required"},statusCode:405));
        app.MapDelete(Root+"/{id:guid}",()=>Results.Json(new{code="business_partner_archival_required"},statusCode:409));
        app.MapGet(Root+"/{id:guid}",async(HttpContext ctx,AppDb db,Guid id)=>{
            await Security.Authorize(ctx,"business-partners.read");
            return Results.Ok(await Read(db,Security.State(ctx).Tenant(ctx,"business-partners")!.Value,id));
        });
        app.MapGet(Root,async(HttpContext ctx,AppDb db)=>{
            await Security.Authorize(ctx,"business-partners.read");var tenant=Security.State(ctx).Tenant(ctx,"business-partners")!.Value;
            int Page(string key,int fallback,int max) {
                var text=ctx.Request.Query[key].ToString();if(text.Length==0) return fallback;
                Check.Require(int.TryParse(text,out var n) && n>=1 && n<=max);return n;
            }
            var page=Page("page",1,100000);var pageSize=Page("pageSize",25,100);
            var search=ctx.Request.Query["search"].ToString();Check.Require(search.Length<=200 && !search.Any(char.IsControl));
            const string where="""
                b.tenant_id=@t AND (@search='' OR strpos(lower(concat_ws(' ',b.legal_name,b.first_name,b.last_name,b.code)),lower(@search))>0
                OR EXISTS(SELECT 1 FROM masterdata.business_partner_tax_identifier x WHERE x.tenant_id=b.tenant_id AND x.business_partner_id=b.id AND (strpos(lower(x.value),lower(@search))>0 OR strpos(lower(x.normalized_value),lower(@normalized))>0))
                OR EXISTS(SELECT 1 FROM masterdata.business_partner_contact_channel x WHERE x.tenant_id=b.tenant_id AND x.business_partner_id=b.id AND strpos(lower(x.value),lower(@search))>0))
                """;
            var normalized=PartnerInput.NormalizeTax(search);
            var total=(long)(await db.Scalar("SELECT count(*) FROM masterdata.business_partner b WHERE "+where,("t",tenant),("search",search),("normalized",normalized.Length==0 ? search : normalized)))!;
            await using var cmd=await db.Command("SELECT to_jsonb(b)::text FROM masterdata.business_partner b WHERE "+where+" ORDER BY b.created_at,b.id LIMIT @size OFFSET @offset",("t",tenant),("search",search),("normalized",normalized.Length==0 ? search : normalized),("size",pageSize),("offset",(page-1)*pageSize));
            await using var reader=await cmd.ExecuteReaderAsync();var items=new List<JsonElement>();
            while(await reader.ReadAsync()) items.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));
            return Results.Ok(new{items,total,page,pageSize});
        });
    }
    public static async Task<JsonElement> Read(AppDb db,Guid tenant,Guid id)
    {
        var result=await db.Scalar("""
            SELECT (to_jsonb(b)||jsonb_build_object(
                'tax_identifiers',COALESCE((SELECT jsonb_agg(to_jsonb(x)-'tenant_id'-'business_partner_id' ORDER BY x.id) FROM masterdata.business_partner_tax_identifier x WHERE x.tenant_id=b.tenant_id AND x.business_partner_id=b.id),'[]'::jsonb),
                'addresses',COALESCE((SELECT jsonb_agg(to_jsonb(a)-'tenant_id'-'business_partner_id'||jsonb_build_object('usages',COALESCE((SELECT jsonb_agg(jsonb_build_object('usage',u.usage,'is_default',u.is_default) ORDER BY u.usage) FROM masterdata.business_partner_address_usage u WHERE u.address_id=a.id),'[]'::jsonb)) ORDER BY a.id) FROM masterdata.business_partner_address a WHERE a.tenant_id=b.tenant_id AND a.business_partner_id=b.id),'[]'::jsonb),
                'contact_channels',COALESCE((SELECT jsonb_agg(to_jsonb(x)-'tenant_id'-'business_partner_id' ORDER BY x.id) FROM masterdata.business_partner_contact_channel x WHERE x.tenant_id=b.tenant_id AND x.business_partner_id=b.id),'[]'::jsonb)))::text
            FROM masterdata.business_partner b WHERE b.tenant_id=@t AND b.id=@id
            """,("t",tenant),("id",id));
        Check.Require(result is string,404,"not_found");return JsonSerializer.Deserialize<JsonElement>((string)result!);
    }
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Guid? id,JsonElement body)
    {
        await Security.Authorize(ctx,id.HasValue ? "business-partners.update" : "business-partners.create");
        var state=Security.State(ctx);var tenant=state.Tenant(ctx,"business-partners")!.Value;
        ClassificationTimeline.Require(!id.HasValue || body.ValueKind!=JsonValueKind.Object || !body.TryGetProperty("taxProfiles",out _),"tax_profile_initial_only",field:"taxProfiles");
        var input=PartnerInput.Object(body,"values","taxIdentifiers","addresses","contactChannels","expectedVersion","taxProfiles");
        Check.Require(input.TryGetValue("values",out var raw));
        var values=PartnerInput.Object(raw,"kind","legal_name","first_name","last_name","status","code");
        JsonElement? before=id.HasValue ? await Read(db,tenant,id.Value) : null;
        if(id.HasValue) {
            var expected=PartnerInput.Integer(input,"expectedVersion",1,9007199254740990L);
            Check.Require(expected==before!.Value.GetProperty("version").GetInt64(),409,"stale_version");
            if(values.ContainsKey("code")) Check.Require(PartnerInput.Text(values,"code",100)==before.Value.GetProperty("code").GetString(),409,"business_partner_code_immutable");
        } else Check.Require(!input.ContainsKey("expectedVersion"));
        string? Value(string key,int max=500)=>values.ContainsKey(key) ? PartnerInput.Text(values,key,max,field:"values."+key) : before.HasValue && before.Value.GetProperty(key).ValueKind==JsonValueKind.String ? before.Value.GetProperty(key).GetString() : null;
        var kind=values.ContainsKey("kind") ? PartnerInput.ChoiceAt(values,"kind","values.kind",["PERSON","ORGANIZATION"]) : before.HasValue ? before.Value.GetProperty("kind").GetString()! : throw new ApiException(400,"field_required","values.kind");
        var status=values.ContainsKey("status") ? PartnerInput.ChoiceAt(values,"status","values.status",["DRAFT","ACTIVE","BLOCKED","ARCHIVED"]) : before.HasValue ? before.Value.GetProperty("status").GetString()! : "DRAFT";
        var legal=Value("legal_name");var first=Value("first_name",200);var last=Value("last_name",200);
        ValidateNames(kind,status,legal,first,last);
        var record=id ?? Guid.NewGuid();
        if(!id.HasValue) {
            var code=await BusinessPartnerNumbering.Allocate(db,tenant,PartnerInput.Text(values,"code",100,field:"values.code"));
            await db.Execute("INSERT INTO masterdata.business_partner(id,tenant_id,kind,status,code,legal_name,first_name,last_name) VALUES(@id,@t,@kind,@status,@code,@legal,@first,@last)",("id",record),("t",tenant),("kind",kind),("status",status),("code",code),("legal",legal),("first",first),("last",last));
        } else {
            await db.Execute("UPDATE masterdata.business_partner SET kind=@kind,status=@status,legal_name=@legal,first_name=@first,last_name=@last,version=version+1 WHERE id=@id AND tenant_id=@t",("id",record),("t",tenant),("kind",kind),("status",status),("legal",legal),("first",first),("last",last));
        }
        await ReplaceChildren(db,tenant,record,input);
        if(!id.HasValue && input.TryGetValue("taxProfiles",out var taxProfiles))
            await TaxClassificationApplication.AssignInitial(ctx,db,ClassificationKind.Partner,tenant,record,taxProfiles);
        var after=await Read(db,tenant,record);
        await db.Audit(state.User.Id,tenant,id.HasValue ? "update" : "create","business-partners",record,new{before,after});
        return Results.Json(after,statusCode:id.HasValue ? 200 : 201);
    }
    private static void ValidateNames(string kind,string status,string? legal,string? first,string? last)
    {
        if(kind=="ORGANIZATION") {
            PartnerInput.Require(legal!=null,"business_partner_name_required","values.legal_name");
            PartnerInput.Require(first==null,"business_partner_names_mismatch","values.first_name");
            PartnerInput.Require(last==null,"business_partner_names_mismatch","values.last_name");
        } else {
            PartnerInput.Require(legal==null,"business_partner_names_mismatch","values.legal_name");
            PartnerInput.Require(first!=null || last!=null,"business_partner_name_required","values.first_name");
            PartnerInput.Require(status=="DRAFT" || first!=null,"business_partner_name_required","values.first_name");
            PartnerInput.Require(status=="DRAFT" || last!=null,"business_partner_name_required","values.last_name");
        }
    }
    private static void OptionalId(Dictionary<string,JsonElement> row)
    {
        if(row.TryGetValue("id",out var id)) Check.Require(id.ValueKind==JsonValueKind.String && id.TryGetGuid(out var parsed) && parsed!=Guid.Empty);
    }
    private static async Task ReplaceChildren(AppDb db,Guid tenant,Guid partner,Dictionary<string,JsonElement> input)
    {
        // Sostituzione completa dei soli insiemi presenti. Gli ID figli sono rigenerati, mai usati per riferimenti esterni.
        if(input.TryGetValue("taxIdentifiers",out var taxes)) {
            await db.Execute("DELETE FROM masterdata.business_partner_tax_identifier WHERE tenant_id=@t AND business_partner_id=@bp",("t",tenant),("bp",partner));
            var taxIndex=0;
            foreach(var item in PartnerInput.Array(taxes)) {
                var path=$"taxIdentifiers[{taxIndex++}]";
                var row=PartnerInput.Object(item,"id","country_code","identifier_type","value","normalized_value"); OptionalId(row);
                var country=PartnerInput.Country(row,path+".country_code","tax_identifier_required");
                var type=PartnerInput.ChoiceAt(row,"identifier_type",path+".identifier_type",["VAT","FISCAL_CODE","FOREIGN_TAX_ID"],"invalid_tax_identifier_type","tax_identifier_required");
                var value=PartnerInput.Text(row,"value",100,true,path+".value","tax_identifier_required")!;
                var normalized=PartnerInput.NormalizeTax(value);PartnerInput.Require(normalized.Length>0,"invalid_tax_identifier",path+".value");
                if(row.ContainsKey("normalized_value")) PartnerInput.Require(PartnerInput.Text(row,"normalized_value",100,true,path+".normalized_value")==normalized,"tax_identifier_normalization_mismatch",path+".normalized_value");
                // Sola sintassi sicura, senza certificare esistenza, checksum o titolarità fiscale.
                if(country=="IT" && type=="VAT" && !Regex.IsMatch(normalized,@"^[0-9]{11}$")) throw new ApiException(400,"invalid_italian_vat",path+".value");
                if(country=="IT" && type=="FISCAL_CODE") PartnerInput.Require(Regex.IsMatch(normalized,@"^(?:[0-9]{11}|[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])$"),"invalid_italian_fiscal_code",path+".value");
                var exists=(bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.business_partner_tax_identifier WHERE tenant_id=@t AND country_code=@country AND identifier_type=@type AND normalized_value=@normalized)",("t",tenant),("country",country),("type",type),("normalized",normalized)))!;
                PartnerInput.Require(!exists,"duplicate_tax_identifier",path+".value",409);
                try { await db.Execute("INSERT INTO masterdata.business_partner_tax_identifier(tenant_id,business_partner_id,country_code,identifier_type,value,normalized_value) VALUES(@t,@bp,@country,@type,@value,@normalized)",("t",tenant),("bp",partner),("country",country),("type",type),("value",value),("normalized",normalized)); }
                catch(PostgresException e) when(e.SqlState=="23505" && e.ConstraintName=="business_partner_tax_unique") {throw new ApiException(409,"duplicate_tax_identifier",path+".value");}
            }
        }
        if(input.TryGetValue("addresses",out var addresses)) {
            await db.Execute("DELETE FROM masterdata.business_partner_address WHERE tenant_id=@t AND business_partner_id=@bp",("t",tenant),("bp",partner));
            var defaults=new HashSet<string>(StringComparer.Ordinal);
            var addressIndex=0;
            foreach(var item in PartnerInput.Array(addresses)) {
                var path=$"addresses[{addressIndex++}]";
                var row=PartnerInput.Object(item,"id","label","street","street_number","postal_code","city","province","country_code","additional_info","usages");OptionalId(row);
                var address=Guid.NewGuid();
                await db.Execute("INSERT INTO masterdata.business_partner_address(id,tenant_id,business_partner_id,label,street,street_number,postal_code,city,province,country_code,additional_info) VALUES(@id,@t,@bp,@label,@street,@number,@postal,@city,@province,@country,@info)",
                    ("id",address),("t",tenant),("bp",partner),("label",PartnerInput.Text(row,"label",200,field:path+".label")),("street",PartnerInput.Text(row,"street",500,true,path+".street","business_partner_address_required")),("number",PartnerInput.Text(row,"street_number",50,field:path+".street_number")),("postal",PartnerInput.Text(row,"postal_code",30,true,path+".postal_code","business_partner_address_required")),("city",PartnerInput.Text(row,"city",200,true,path+".city","business_partner_address_required")),("province",PartnerInput.Text(row,"province",100,field:path+".province")),("country",PartnerInput.Country(row,path+".country_code","business_partner_address_required")),("info",PartnerInput.Text(row,"additional_info",1000,field:path+".additional_info")));
                var selected=new HashSet<string>(StringComparer.Ordinal);
                var usageIndex=0;
                if(row.TryGetValue("usages",out var usages)) foreach(var usage in PartnerInput.Array(usages,4)) {
                    var usagePath=$"{path}.usages[{usageIndex++}]";
                    var entry=PartnerInput.Object(usage,"usage","is_default");var type=PartnerInput.ChoiceAt(entry,"usage",usagePath+".usage",["REGISTERED","BILLING","SHIPPING","CORRESPONDENCE"]);var isDefault=PartnerInput.Flag(entry,"is_default",usagePath+".is_default");
                    PartnerInput.Require(selected.Add(type),"duplicate_address_usage",usagePath+".usage");
                    PartnerInput.Require(!isDefault || defaults.Add(type),"duplicate_default_address",usagePath+".is_default");
                    await db.Execute("INSERT INTO masterdata.business_partner_address_usage(tenant_id,business_partner_id,address_id,usage,is_default) VALUES(@t,@bp,@id,@usage,@default)",("t",tenant),("bp",partner),("id",address),("usage",type),("default",isDefault));
                }
            }
        }
        if(input.TryGetValue("contactChannels",out var contacts)) {
            await db.Execute("DELETE FROM masterdata.business_partner_contact_channel WHERE tenant_id=@t AND business_partner_id=@bp",("t",tenant),("bp",partner));
            var primary=new HashSet<string>(StringComparer.Ordinal);
            var contactIndex=0;
            foreach(var item in PartnerInput.Array(contacts)) {
                var path=$"contactChannels[{contactIndex++}]";
                var row=PartnerInput.Object(item,"id","channel_type","value","purpose","is_primary");OptionalId(row);
                var type=PartnerInput.ChoiceAt(row,"channel_type",path+".channel_type",["EMAIL","PHONE","MOBILE","PEC","WEBSITE"]);var value=PartnerInput.Text(row,"value",500,true,path+".value")!;var isPrimary=PartnerInput.Flag(row,"is_primary",path+".is_primary");
                PartnerInput.Require(!isPrimary || primary.Add(type),"duplicate_primary_contact",path+".is_primary");
                if(type is "EMAIL" or "PEC") PartnerInput.Require(value.Length<=254 && Regex.IsMatch(value,@"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$"),"invalid_contact_email",path+".value");
                if(type is "PHONE" or "MOBILE") PartnerInput.Require(value.Length<=50 && value.Any(char.IsAsciiDigit) && Regex.IsMatch(value,@"^[+0-9() .\-/#xXeEtT]+$"),"invalid_contact_phone",path+".value");
                if(type=="WEBSITE") PartnerInput.Require(Uri.TryCreate(value,UriKind.Absolute,out var uri) && uri.Scheme is "http" or "https" && uri.Host.Length>0 && uri.UserInfo.Length==0,"invalid_contact_website",path+".value");
                await db.Execute("INSERT INTO masterdata.business_partner_contact_channel(tenant_id,business_partner_id,channel_type,value,purpose,is_primary) VALUES(@t,@bp,@type,@value,@purpose,@primary)",("t",tenant),("bp",partner),("type",type),("value",value),("purpose",PartnerInput.Text(row,"purpose",200,field:path+".purpose")),("primary",isPrimary));
            }
        }
    }
}
