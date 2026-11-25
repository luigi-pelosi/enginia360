using System.Globalization;
using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Payments;

public static class PaymentTermsEndpoints
{
    private const long MaxVersion = 9007199254740991L;
    private sealed record Row(int Sequence, decimal Percentage, int Months, int Days, string Rule, string Base, int? FixedDay, Guid? Method);
    private sealed record Term(string Code, string Name, Guid? Method, string Reference, bool Active, Row[] Rows, long? Expected);

    public static void Map(WebApplication app)
    {
        app.MapGet("/api/companies/{companyId:guid}/payment-terms", List);
        app.MapPost("/api/companies/{companyId:guid}/payment-terms", Create);
        app.MapPut("/api/companies/{companyId:guid}/payment-terms/{id:guid}", Update);
        app.MapPost("/api/companies/{companyId:guid}/payment-schedule/preview", Preview);
    }

    private static Guid? OptionalId(Dictionary<string,JsonElement> o,string key)
    {
        var text=PartnerInput.Text(o,key,36);
        if(text==null) return null;
        Check.Require(Guid.TryParseExact(text,"D",out var id) && id!=Guid.Empty);
        return Guid.ParseExact(text,"D");
    }
    private static decimal DecimalValue(JsonElement value)
    {
        decimal number=0;
        var ok=value.ValueKind==JsonValueKind.Number ? value.TryGetDecimal(out number) :
            value.ValueKind==JsonValueKind.String && decimal.TryParse(value.GetString(),NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out number);
        Check.Require(ok); return number;
    }
    private static Term Parse(JsonElement body,bool update,bool preview=false)
    {
        var o=PartnerInput.Object(body,"id","code","name","defaultMethodId","referenceDateType","isActive","version","expectedVersion","installments");
        var code=PartnerInput.Text(o,"code",30,!preview) ?? "";
        var name=PartnerInput.Text(o,"name",120,!preview) ?? "";
        var reference=PartnerInput.Choice(o,"referenceDateType","DOCUMENT_DATE","RECEIPT_DATE","CUSTOM_DATE");
        Check.Require(o.TryGetValue("isActive",out var active) && active.ValueKind is JsonValueKind.True or JsonValueKind.False);
        long? expected=update ? PartnerInput.Integer(o,"expectedVersion",1,MaxVersion) : null;
        Check.Require(o.TryGetValue("installments",out var array));
        var items=PartnerInput.Array(array,100); Check.Require(items.Length>0);
        var rows=new List<Row>();
        for(var i=0;i<items.Length;i++) {
            var r=PartnerInput.Object(items[i],"id","sequence","percentage","offsetMonths","offsetDays","dateRule","offsetBase","fixedDay","methodId");
            var sequence=r.ContainsKey("sequence") ? (int)PartnerInput.Integer(r,"sequence",1,100) : i+1;
            Check.Require(sequence==i+1);
            Check.Require(r.TryGetValue("percentage",out var raw));
            var pct=DecimalValue(raw); Check.Require(pct>0 && pct<=100 && decimal.Round(pct,4)==pct);
            var months=(int)PartnerInput.Integer(r,"offsetMonths",0,120000);
            var days=(int)PartnerInput.Integer(r,"offsetDays",0,3652058);
            var rule=PartnerInput.Choice(r,"dateRule","EXACT","END_OF_MONTH","FIXED_DAY");
            var basis=PartnerInput.Choice(r,"offsetBase","REFERENCE_DATE","REFERENCE_MONTH_END");
            int? fixedDay=null;
            if(r.TryGetValue("fixedDay",out var fixedRaw) && fixedRaw.ValueKind!=JsonValueKind.Null) fixedDay=(int)PartnerInput.Integer(r,"fixedDay",1,31);
            Check.Require((rule=="FIXED_DAY")==fixedDay.HasValue);
            rows.Add(new(sequence,pct,months,days,rule,basis,fixedDay,OptionalId(r,"methodId")));
        }
        Check.Require(rows.Sum(x=>x.Percentage)==100m);
        return new(code,name,OptionalId(o,"defaultMethodId"),reference,active.GetBoolean(),rows.ToArray(),expected);
    }
    private static async Task References(AppDb db,Guid tenant,Guid company,Term term)
    {
        var ids=term.Rows.Select(x=>x.Method).Append(term.Method).Where(x=>x.HasValue).Select(x=>x!.Value).Distinct().ToArray();
        if(ids.Length==0)return;
        var found=new List<Guid>();
        await using(var cmd=await db.Command("SELECT id FROM masterdata.payment_methods WHERE tenant_id=@t AND company_id=@c AND id=ANY(@ids::uuid[]) AND is_active ORDER BY id FOR SHARE",("t",tenant),("c",company),("ids",ids)))
        await using(var reader=await cmd.ExecuteReaderAsync()) while(await reader.ReadAsync()) found.Add(reader.GetGuid(0));
        Check.Require(found.Count==ids.Length);
    }
    private const string Projection="""
        jsonb_build_object('id',p.id,'code',p.code,'name',p.name,'defaultMethodId',p.default_method_id,
        'referenceDateType',p.reference_date_type,'isActive',p.is_active,'version',p.version,
        'installments',coalesce((SELECT jsonb_agg(jsonb_build_object('sequence',i.sequence,'percentage',i.percentage,
        'offsetMonths',i.offset_months,'offsetDays',i.offset_days,'dateRule',i.date_rule,'offsetBase',i.offset_base,
        'fixedDay',i.fixed_day,'methodId',i.method_id) ORDER BY i.sequence) FROM masterdata.payment_term_installments i
        WHERE i.tenant_id=p.tenant_id AND i.company_id=p.company_id AND i.payment_term_id=p.id),'[]'::jsonb))
        """;
    private static async Task<List<JsonElement>> Read(AppDb db,Guid tenant,Guid company,Guid? id=null)
    {
        await using var cmd=await db.Command("SELECT ("+Projection+")::text FROM masterdata.payment_terms p WHERE p.tenant_id=@t AND p.company_id=@c AND (@id::uuid IS NULL OR p.id=@id::uuid) ORDER BY lower(p.code),p.id",("t",tenant),("c",company),("id",id));
        await using var reader=await cmd.ExecuteReaderAsync(); var result=new List<JsonElement>();
        while(await reader.ReadAsync()) result.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));
        return result;
    }
    private static async Task<IResult> List(HttpContext ctx,AppDb db,Guid companyId)
    {
        var tenant=await PaymentAccess.Gate(ctx,db,companyId,"payment-terms.read");
        var items=await Read(db,tenant,companyId);
        // Method identifiers are independent master data and require their own read grant.
        if(items.Any(HasMethods)) await PaymentAccess.Gate(ctx,db,companyId,"payment-methods.read");
        return Results.Ok(new {items});
    }
    private static bool HasMethods(JsonElement term)=>term.GetProperty("defaultMethodId").ValueKind!=JsonValueKind.Null || term.GetProperty("installments").EnumerateArray().Any(x=>x.GetProperty("methodId").ValueKind!=JsonValueKind.Null);
    private static async Task<IResult> Create(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)
        =>await Save(ctx,db,companyId,null,body);
    private static async Task<IResult> Update(HttpContext ctx,AppDb db,Guid companyId,Guid id,JsonElement body)
        =>await Save(ctx,db,companyId,id,body);
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Guid company,Guid? id,JsonElement body)
    {
        var tenant=await PaymentAccess.Gate(ctx,db,company,id.HasValue ? "payment-terms.update" : "payment-terms.create");
        Check.Require(db.Database.CurrentTransaction!=null,500,"server_error");
        var term=Parse(body,id.HasValue); JsonElement? before=null;
        if(id.HasValue) {
            var version=await db.Scalar("SELECT version FROM masterdata.payment_terms WHERE tenant_id=@t AND company_id=@c AND id=@id FOR UPDATE",("t",tenant),("c",company),("id",id));
            Check.Require(version is long,404,"not_found");
            Check.Require((long)version! == term.Expected,409,"stale_version");
            Check.Require((long)version! < MaxVersion,409,"version_exhausted");
            before=(await Read(db,tenant,company,id))[0];
        }
        if(term.Method.HasValue || term.Rows.Any(x=>x.Method.HasValue) || (before.HasValue && HasMethods(before.Value)))
            await PaymentAccess.Gate(ctx,db,company,"payment-methods.read");
        await References(db,tenant,company,term);
        if(id.HasValue) {
            var ids=term.Rows.Select(x=>x.Method).Append(term.Method).Where(x=>x.HasValue).Select(x=>x!.Value).Distinct().ToArray();
            var incompatible=(bool)(await db.Scalar("""
                SELECT EXISTS (
                    SELECT 1 FROM masterdata.payment_methods m
                    WHERE m.tenant_id=@t AND m.company_id=@c AND m.id=ANY(@ids::uuid[])
                    AND ((m.direction NOT IN ('BOTH','INBOUND') AND (
                        EXISTS(SELECT 1 FROM masterdata.company_payment_settings s WHERE s.tenant_id=@t AND s.company_id=@c AND s.default_sales_term_id=@id) OR
                        EXISTS(SELECT 1 FROM masterdata.business_partner_payment_defaults d WHERE d.tenant_id=@t AND d.company_id=@c AND d.payment_term_id=@id AND d.role_code='CUSTOMER')))
                    OR (m.direction NOT IN ('BOTH','OUTBOUND') AND (
                        EXISTS(SELECT 1 FROM masterdata.company_payment_settings s WHERE s.tenant_id=@t AND s.company_id=@c AND s.default_purchase_term_id=@id) OR
                        EXISTS(SELECT 1 FROM masterdata.business_partner_payment_defaults d WHERE d.tenant_id=@t AND d.company_id=@c AND d.payment_term_id=@id AND d.role_code='SUPPLIER'))))
                )
                """,("t",tenant),("c",company),("id",id),("ids",ids)))!;
            Check.Require(!incompatible,400,"invalid_payment_reference");
        }
        var record=id ?? Guid.NewGuid();
        if(id.HasValue) {
            await db.Execute("UPDATE masterdata.payment_terms SET code=@code,name=@name,default_method_id=@method::uuid,reference_date_type=@reference,is_active=@active,version=version+1 WHERE tenant_id=@t AND company_id=@c AND id=@id",("code",term.Code),("name",term.Name),("method",term.Method),("reference",term.Reference),("active",term.Active),("t",tenant),("c",company),("id",record));
            await db.Execute("DELETE FROM masterdata.payment_term_installments WHERE tenant_id=@t AND company_id=@c AND payment_term_id=@id",("t",tenant),("c",company),("id",record));
        } else {
            await db.Execute("INSERT INTO masterdata.payment_terms(id,tenant_id,company_id,code,name,default_method_id,reference_date_type,is_active) VALUES(@id,@t,@c,@code,@name,@method::uuid,@reference,@active)",("id",record),("t",tenant),("c",company),("code",term.Code),("name",term.Name),("method",term.Method),("reference",term.Reference),("active",term.Active));
        }
        foreach(var row in term.Rows)
            await db.Execute("INSERT INTO masterdata.payment_term_installments(tenant_id,company_id,payment_term_id,sequence,percentage,offset_months,offset_days,date_rule,offset_base,fixed_day,method_id) VALUES(@t,@c,@id,@sequence,@percentage,@months,@days,@rule,@base,@fixed::integer,@method::uuid)",("t",tenant),("c",company),("id",record),("sequence",row.Sequence),("percentage",row.Percentage),("months",row.Months),("days",row.Days),("rule",row.Rule),("base",row.Base),("fixed",row.FixedDay),("method",row.Method));
        var after=(await Read(db,tenant,company,record))[0];
        await db.Audit(Security.State(ctx).User.Id,tenant,id.HasValue ? "update" : "create","payment-terms",record,new {before,after});
        return id.HasValue ? Results.Ok(after) : Results.Json(after,statusCode:201);
    }
    private static async Task<IResult> Preview(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)
    {
        var tenant=await PaymentAccess.Gate(ctx,db,companyId,"payment-schedule.preview");
        var o=PartnerInput.Object(body,"paymentTerm","amountDue","currency","referenceDate");
        Check.Require(o.TryGetValue("paymentTerm",out var rawTerm)); var term=Parse(rawTerm,false,true);
        if(term.Method.HasValue || term.Rows.Any(x=>x.Method.HasValue)) await PaymentAccess.Gate(ctx,db,companyId,"payment-methods.read");
        await References(db,tenant,companyId,term);
        Check.Require(o.TryGetValue("amountDue",out var rawAmount)); var amount=DecimalValue(rawAmount);
        var currency=PartnerInput.Text(o,"currency",3,true)!;
        Check.Require(System.Text.RegularExpressions.Regex.IsMatch(currency,"^[A-Z]{3}$"));
        var minorUnits=await db.Scalar("SELECT minor_units FROM foundation.currency WHERE code=@code AND is_enabled FOR SHARE",("code",currency));
        // Le unità N.A., le valute disabilitate e i codici sconosciuti non hanno precisione utilizzabile.
        Check.Require(minorUnits is int,400,"invalid_currency");
        var precision=(int)minorUnits!;
        var text=PartnerInput.Text(o,"referenceDate",10,true)!;
        Check.Require(DateOnly.TryParseExact(text,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out var date));
        var rows=term.Rows.Select(x=>new PaymentInstallment(x.Percentage,x.Months,x.Days,x.Base=="REFERENCE_MONTH_END",x.Rule switch {"EXACT"=>DueDateMode.Exact,"END_OF_MONTH"=>DueDateMode.EndOfMonth,_=>DueDateMode.FixedDay},x.FixedDay,x.Method?.ToString())).ToArray();
        IReadOnlyList<PaymentDue> schedule;
        try { schedule=PaymentSchedule.Calculate(date,amount,precision,rows,term.Method?.ToString()); }
        catch(OverflowException) { throw new ApiException(400,"validation_error"); }
        return Results.Ok(new {items=schedule.Select(x=>new {dueDate=x.DueDate,amount=x.Amount,methodId=x.Method})});
    }
}
