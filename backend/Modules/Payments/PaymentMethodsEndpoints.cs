using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using Npgsql;

namespace Enginia360.Modules.Payments;

public static class PaymentAccess
{
    public static readonly string[] Permissions = ["payment-methods.read","payment-methods.create","payment-methods.update","payment-terms.read","payment-terms.create","payment-terms.update","payment-settings.read","payment-settings.update","payment-partner-defaults.read","payment-partner-defaults.update","payment-schedule.preview","payment-resolution.read"];
    public static async Task<Dictionary<Guid,string[]>> Grants(HttpContext ctx,AppDb db)
    {
        Check.Require(db.Database.CurrentTransaction != null,500,"server_error");
        var state=Security.State(ctx);
        Check.Require(state != null && state.User.IsEnabled,403,"forbidden");
        var tenant=state!.Tenant(ctx,"business-partners");
        Check.Require(tenant.HasValue && tenant != Guid.Empty,403,"forbidden");
        var global=state.User.IsSuperAdmin && state.User.TenantId==null;
        Check.Require(global || !state.User.IsSuperAdmin && state.User.TenantId==tenant,403,"forbidden");
        var sql=global ? """
            SELECT c.id,p.code FROM foundation.company c JOIN foundation.tenant t ON t.id=c.tenant_id AND t.is_enabled
            CROSS JOIN unnest(@codes::text[]) AS p(code) WHERE c.tenant_id=@tenant
            """ : """
            SELECT DISTINCT rc.company_id,p.code FROM foundation.role_company rc
            JOIN foundation.company c ON c.tenant_id=rc.tenant_id AND c.id=rc.company_id
            JOIN foundation.role r ON r.tenant_id=rc.tenant_id AND r.id=rc.role_id AND r.is_enabled
            JOIN foundation.role_permission rp ON rp.tenant_id=r.tenant_id AND rp.role_id=r.id
            JOIN foundation.permission p ON p.tenant_id=rp.tenant_id AND p.id=rp.permission_id AND p.is_system AND p.is_enabled
            JOIN foundation."user" u ON u.tenant_id=r.tenant_id AND u.id=@user AND u.is_enabled AND NOT u.is_super_admin
            JOIN foundation.tenant t ON t.id=u.tenant_id AND t.is_enabled
            WHERE rc.tenant_id=@tenant AND p.code=ANY(@codes::text[]) AND
              (EXISTS(SELECT 1 FROM foundation.user_role ur WHERE ur.tenant_id=r.tenant_id AND ur.role_id=r.id AND ur.user_id=u.id)
               OR EXISTS(SELECT 1 FROM foundation.user_group_role gr
                  JOIN foundation.user_group g ON g.tenant_id=gr.tenant_id AND g.id=gr.user_group_id AND g.is_enabled
                  JOIN foundation.user_group_member gm ON gm.tenant_id=g.tenant_id AND gm.user_group_id=g.id AND gm.user_id=u.id
                  WHERE gr.tenant_id=r.tenant_id AND gr.role_id=r.id))
            """;
        var grants=new Dictionary<Guid,List<string>>();
        await using var cmd=await db.Command(sql,("tenant",tenant!.Value),("user",state.User.Id),("codes",Permissions));
        await using var reader=await cmd.ExecuteReaderAsync();
        while(await reader.ReadAsync()) {var id=reader.GetGuid(0);if(!grants.TryGetValue(id,out var values)) grants[id]=values=[];values.Add(reader.GetString(1));}
        return grants.ToDictionary(x=>x.Key,x=>Permissions.Where(x.Value.Contains).ToArray());
    }
    public static async Task<Guid> Gate(HttpContext ctx,AppDb db,Guid company,string permission)
    {
        Check.Require(Permissions.Contains(permission,StringComparer.Ordinal),403,"forbidden");
        var grants=await Grants(ctx,db);
        Check.Require(grants.TryGetValue(company,out var values) && values.Contains(permission,StringComparer.Ordinal),403,"forbidden");
        return Security.State(ctx).Tenant(ctx,"business-partners")!.Value;
    }
}

public static class PaymentMethodsEndpoints
{
    private const long MaxVersion=9007199254740991L;
    private sealed record Method(Guid id,string code,string name,string category,string? fatturapaCode,string direction,bool requiresBankAccount,bool isActive,int sortOrder,long version);
    public static void Map(WebApplication app)
    {
        app.MapGet("/api/payment-companies",async (HttpContext ctx,AppDb db)=> {
            var grants=await PaymentAccess.Grants(ctx,db);var tenant=Security.State(ctx).Tenant(ctx,"business-partners")!.Value;
            var items=new List<object>();
            await using var cmd=await db.Command("SELECT id,name,code FROM foundation.company WHERE tenant_id=@t AND id=ANY(@ids::uuid[]) ORDER BY lower(name),id",("t",tenant),("ids",grants.Keys.ToArray()));
            await using var rows=await cmd.ExecuteReaderAsync();while(await rows.ReadAsync()) {var id=rows.GetGuid(0);items.Add(new {id,name=rows.GetString(1),code=rows.IsDBNull(2)?null:rows.GetString(2),permissions=grants[id]});}
            return Results.Ok(new {items});
        });
        app.MapGet("/api/fatturapa-payment-codes",async (HttpContext ctx,AppDb db)=> {
            var grants=await PaymentAccess.Grants(ctx,db);
            Check.Require(grants.Values.Any(x=>x.Contains("payment-methods.read",StringComparer.Ordinal)),403,"forbidden");
            var items=new List<object>();await using var cmd=await db.Command("SELECT code,description FROM masterdata.fatturapa_payment_codes WHERE is_active ORDER BY code");
            await using var rows=await cmd.ExecuteReaderAsync();while(await rows.ReadAsync())items.Add(new {code=rows.GetString(0),description=rows.GetString(1)});
            return Results.Ok(new {items});
        });
        app.MapGet("/api/companies/{companyId:guid}/payment-methods",async (HttpContext ctx,AppDb db,Guid companyId)=> {
            var tenant=await PaymentAccess.Gate(ctx,db,companyId,"payment-methods.read");
            var items=new List<Method>();await using var cmd=await db.Command(Select+" WHERE tenant_id=@t AND company_id=@c ORDER BY sort_order,lower(code),id",("t",tenant),("c",companyId));
            await using var rows=await cmd.ExecuteReaderAsync();while(await rows.ReadAsync())items.Add(ReadRow(rows));return Results.Ok(new {items});
        });
        app.MapPost("/api/companies/{companyId:guid}/payment-methods",(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)=>Save(ctx,db,companyId,null,body));
        app.MapPatch("/api/companies/{companyId:guid}/payment-methods/{id:guid}",(HttpContext ctx,AppDb db,Guid companyId,Guid id,JsonElement body)=>Save(ctx,db,companyId,id,body));
    }
    private const string Select="SELECT id,code,name,category,fatturapa_code,direction,requires_bank_account,is_active,sort_order,version FROM masterdata.payment_methods";
    private static Method ReadRow(NpgsqlDataReader r)=>new(r.GetGuid(0),r.GetString(1),r.GetString(2),r.GetString(3),r.IsDBNull(4)?null:r.GetString(4),r.GetString(5),r.GetBoolean(6),r.GetBoolean(7),r.GetInt32(8),r.GetInt64(9));
    private static async Task<Method?> Read(AppDb db,Guid tenant,Guid company,Guid id,bool locked=false)
    {
        await using var cmd=await db.Command(Select+" WHERE tenant_id=@t AND company_id=@c AND id=@id"+(locked?" FOR UPDATE":""),("t",tenant),("c",company),("id",id));
        await using var reader=await cmd.ExecuteReaderAsync();return await reader.ReadAsync()?ReadRow(reader):null;
    }
    private static async Task<IResult> Save(HttpContext ctx,AppDb db,Guid company,Guid? id,JsonElement body)
    {
        var tenant=await PaymentAccess.Gate(ctx,db,company,id.HasValue?"payment-methods.update":"payment-methods.create");
        var input=PartnerInput.Object(body,"id","code","name","category","fatturapaCode","direction","requiresBankAccount","isActive","sortOrder","version","expectedVersion");
        Method? before=null;
        if(id.HasValue) {
            before=await Read(db,tenant,company,id.Value,true);Check.Require(before!=null,404,"not_found");
            var expected=PartnerInput.Integer(input,"expectedVersion",1,MaxVersion);Check.Require(expected==before!.version,409,"stale_version");Check.Require(expected<MaxVersion,409,"version_exhausted");
            if(input.TryGetValue("id",out var suppliedId)) Check.Require(suppliedId.ValueKind==JsonValueKind.String && Guid.TryParse(suppliedId.GetString(),out var parsed) && parsed==id);
        } else Check.Require(!input.ContainsKey("id") && !input.ContainsKey("version") && !input.ContainsKey("expectedVersion"));
        string Text(string key,int max,string? old)=>input.ContainsKey(key)?PartnerInput.Text(input,key,max,true)!:old ?? throw new ApiException(400,"validation_error");
        string Choice(string key,string? old,params string[] choices) {var value=Text(key,50,old);Check.Require(choices.Contains(value,StringComparer.Ordinal));return value;}
        bool Flag(string key,bool? old) {if(!input.TryGetValue(key,out var value)) {Check.Require(old.HasValue);return old!.Value;} Check.Require(value.ValueKind is JsonValueKind.True or JsonValueKind.False);return value.GetBoolean();}
        var code=Text("code",30,before?.code);var name=Text("name",100,before?.name);
        var category=Choice("category",before?.category,"BANK_TRANSFER","CASH","CARD","DIRECT_DEBIT","BANK_RECEIPT","CHEQUE","OTHER");
        var direction=Choice("direction",before?.direction,"INBOUND","OUTBOUND","BOTH");
        var fiscal=input.ContainsKey("fatturapaCode")?PartnerInput.Text(input,"fatturapaCode",4):before?.fatturapaCode;
        var bank=Flag("requiresBankAccount",before?.requiresBankAccount);var active=Flag("isActive",before?.isActive);
        var order=input.ContainsKey("sortOrder")?(int)PartnerInput.Integer(input,"sortOrder",int.MinValue,int.MaxValue):before?.sortOrder ?? throw new ApiException(400,"validation_error");
        if(fiscal!=null && fiscal!=before?.fatturapaCode) Check.Require((bool)(await db.Scalar("SELECT EXISTS(SELECT 1 FROM masterdata.fatturapa_payment_codes WHERE code=@code AND is_active)",("code",fiscal)))!);
        var record=id ?? Guid.NewGuid();
        // The method row is locked above. Term/default writers take a share lock on
        // referenced methods before committing, so this check observes a stable boundary.
        if(before!=null && direction!=before.direction) {
            var incompatible=(bool)(await db.Scalar("""
                SELECT EXISTS (
                    SELECT 1 FROM masterdata.payment_terms p
                    WHERE p.tenant_id=@t AND p.company_id=@c
                      AND (p.default_method_id=@id OR EXISTS (
                          SELECT 1 FROM masterdata.payment_term_installments i
                          WHERE i.tenant_id=p.tenant_id AND i.company_id=p.company_id
                            AND i.payment_term_id=p.id AND i.method_id=@id))
                      AND ((@direction='OUTBOUND' AND (
                          EXISTS (SELECT 1 FROM masterdata.company_payment_settings s WHERE s.tenant_id=@t AND s.company_id=@c AND s.default_sales_term_id=p.id)
                          OR EXISTS (SELECT 1 FROM masterdata.business_partner_payment_defaults d WHERE d.tenant_id=@t AND d.company_id=@c AND d.payment_term_id=p.id AND d.role_code='CUSTOMER')))
                        OR (@direction='INBOUND' AND (
                          EXISTS (SELECT 1 FROM masterdata.company_payment_settings s WHERE s.tenant_id=@t AND s.company_id=@c AND s.default_purchase_term_id=p.id)
                          OR EXISTS (SELECT 1 FROM masterdata.business_partner_payment_defaults d WHERE d.tenant_id=@t AND d.company_id=@c AND d.payment_term_id=p.id AND d.role_code='SUPPLIER'))))
                )
                """,("t",tenant),("c",company),("id",record),("direction",direction)))!;
            Check.Require(!incompatible,400,"invalid_payment_reference");
        }
        try {
            if(id==null) await db.Execute("INSERT INTO masterdata.payment_methods(id,tenant_id,company_id,code,name,category,fatturapa_code,direction,requires_bank_account,is_active,sort_order) VALUES(@id,@t,@c,@code,@name,@category,@fiscal::varchar,@direction,@bank,@active,@sort)",("id",record),("t",tenant),("c",company),("code",code),("name",name),("category",category),("fiscal",fiscal),("direction",direction),("bank",bank),("active",active),("sort",order));
            else await db.Execute("UPDATE masterdata.payment_methods SET code=@code,name=@name,category=@category,fatturapa_code=@fiscal::varchar,direction=@direction,requires_bank_account=@bank,is_active=@active,sort_order=@sort,version=version+1 WHERE tenant_id=@t AND company_id=@c AND id=@id",("id",record),("t",tenant),("c",company),("code",code),("name",name),("category",category),("fiscal",fiscal),("direction",direction),("bank",bank),("active",active),("sort",order));
        } catch(PostgresException e) when(e.SqlState=="23505" && e.ConstraintName=="payment_methods_code_unique") {throw new ApiException(409,"payment_method_code_exists");}
        catch(PostgresException e) when(e.SqlState=="23503") {throw new ApiException(409,"payment_method_in_use");}
        var after=await Read(db,tenant,company,record);await db.Audit(Security.State(ctx).User.Id,tenant,id.HasValue?"update":"create","payment-methods",record,new {before,after});
        return Results.Json(after,statusCode:id.HasValue?200:201);
    }
}
