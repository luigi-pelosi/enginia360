using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.BusinessPartners;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Payments;

// All handlers run inside the request transaction established by the API middleware.
public static class PaymentDefaultsEndpoints
{
    private const long MaxVersion = 9007199254740991;
    public sealed record Settings(Guid? DefaultSalesTermId, Guid? DefaultPurchaseTermId, Guid? DefaultSalesMethodId, Guid? DefaultPurchaseMethodId, long Version);
    public sealed record RoleDefaults(Guid? PaymentTermId, Guid? PaymentMethodId, long Version);
    public sealed record ResolvedValue(Guid? Id, string Source);
    public sealed record Resolution(ResolvedValue Term, ResolvedValue Method);

    public static void Map(WebApplication app)
    {
        app.MapGet("/api/companies/{companyId:guid}/payment-settings", async (HttpContext ctx, AppDb db, Guid companyId) => {
            var tenant=await PaymentAccess.Gate(ctx,db,companyId,"payment-settings.read");
            return Results.Ok(await ReadSettings(db,tenant,companyId));
        });
        app.MapPut("/api/companies/{companyId:guid}/payment-settings", PutSettings);
        app.MapGet("/api/companies/{companyId:guid}/business-partners/{bpId:guid}/payment-defaults/{role}", async (HttpContext ctx, AppDb db, Guid companyId, Guid bpId, string role) => {
            var tenant=await PaymentAccess.Gate(ctx,db,companyId,"payment-partner-defaults.read");
            var relation=await Partner(db,tenant,companyId,bpId,role,false);
            return Results.Ok(await ReadRole(db,tenant,companyId,relation,role));
        });
        app.MapPut("/api/companies/{companyId:guid}/business-partners/{bpId:guid}/payment-defaults/{role}", PutRole);
        app.MapPost("/api/companies/{companyId:guid}/business-partners/{bpId:guid}/payment-defaults/{role}/resolve", Resolve);
    }

    private static Guid? Id(Dictionary<string,JsonElement> input,string name)
    {
        Check.Require(input.TryGetValue(name,out var v));
        if(v.ValueKind==JsonValueKind.Null) return null;
        Check.Require(v.ValueKind==JsonValueKind.String && Guid.TryParseExact(v.GetString(),"D",out var id) && id!=Guid.Empty);
        return Guid.Parse(v.GetString()!);
    }
    private static async Task<Settings> ReadSettings(AppDb db,Guid tenant,Guid company)
    {
        await using var cmd=await db.Command("SELECT default_sales_term_id,default_purchase_term_id,default_sales_method_id,default_purchase_method_id,version FROM masterdata.company_payment_settings WHERE tenant_id=@t AND company_id=@c",("t",tenant),("c",company));
        await using var r=await cmd.ExecuteReaderAsync();
        return await r.ReadAsync() ? new(r.IsDBNull(0)?null:r.GetGuid(0),r.IsDBNull(1)?null:r.GetGuid(1),r.IsDBNull(2)?null:r.GetGuid(2),r.IsDBNull(3)?null:r.GetGuid(3),r.GetInt64(4)) : new(null,null,null,null,0);
    }
    private static async Task<RoleDefaults> ReadRole(AppDb db,Guid tenant,Guid company,Guid relation,string role)
    {
        await using var cmd=await db.Command("SELECT payment_term_id,payment_method_id,version FROM masterdata.business_partner_payment_defaults WHERE tenant_id=@t AND company_id=@c AND company_business_partner_id=@p AND role_code=@r",("t",tenant),("c",company),("p",relation),("r",role));
        await using var r=await cmd.ExecuteReaderAsync();
        return await r.ReadAsync() ? new(r.IsDBNull(0)?null:r.GetGuid(0),r.IsDBNull(1)?null:r.GetGuid(1),r.GetInt64(2)) : new(null,null,0);
    }
    private static async Task<Guid> Partner(AppDb db,Guid tenant,Guid company,Guid bp,string role,bool write)
    {
        BusinessPartnerEligibility.ValidateRole(role);
        var sql="SELECT cbp.id FROM masterdata.company_business_partner cbp JOIN masterdata.company_business_partner_role cr ON cr.tenant_id=cbp.tenant_id AND cr.company_business_partner_id=cbp.id JOIN masterdata.business_partner b ON b.tenant_id=cbp.tenant_id AND b.id=cbp.business_partner_id WHERE cbp.tenant_id=@t AND cbp.company_id=@c AND cbp.business_partner_id=@b AND cr.role_code=@r AND cbp.status='ACTIVE' AND cr.status='ACTIVE' AND b.status='ACTIVE'"+(write?" FOR UPDATE OF cbp,cr,b":"");
        var value=await db.Scalar(sql,("t",tenant),("c",company),("b",bp),("r",role));
        Check.Require(value is Guid,404,"not_found"); return (Guid)value!;
    }
    // Lock referenced rows so concurrent edits cannot invalidate validation before commit.
    private static async Task<bool> ValidMethod(AppDb db,Guid tenant,Guid company,Guid? id,string direction,bool lockRow)
    {
        if(id==null)return true;
        var sql="SELECT id FROM masterdata.payment_methods WHERE tenant_id=@t AND company_id=@c AND id=@id AND is_active AND direction IN ('BOTH',@d)"+(lockRow?" FOR SHARE":"");
        return await db.Scalar(sql,("t",tenant),("c",company),("id",id),("d",direction)) is Guid;
    }
    private static async Task<bool> ValidTerm(AppDb db,Guid tenant,Guid company,Guid? id,string direction,bool lockRow)
    {
        if(id==null)return true;
        var sql="SELECT id FROM masterdata.payment_terms WHERE tenant_id=@t AND company_id=@c AND id=@id AND is_active"+(lockRow?" FOR SHARE":"");
        if(await db.Scalar(sql,("t",tenant),("c",company),("id",id)) is not Guid)return false;
        var methods=new List<Guid>();
        await using(var cmd=await db.Command("SELECT default_method_id FROM masterdata.payment_terms WHERE tenant_id=@t AND company_id=@c AND id=@id AND default_method_id IS NOT NULL UNION SELECT method_id FROM masterdata.payment_term_installments WHERE tenant_id=@t AND company_id=@c AND payment_term_id=@id AND method_id IS NOT NULL ORDER BY 1",("t",tenant),("c",company),("id",id)))
        await using(var r=await cmd.ExecuteReaderAsync()) while(await r.ReadAsync())methods.Add(r.GetGuid(0));
        foreach(var method in methods)if(!await ValidMethod(db,tenant,company,method,direction,lockRow))return false;
        return true;
    }
    private static async Task Validate(AppDb db,Guid t,Guid c,Guid? term,Guid? method,string direction)
    {
        Check.Require(await ValidTerm(db,t,c,term,direction,true) && await ValidMethod(db,t,c,method,direction,true),400,"invalid_payment_reference");
    }
    private static void Version(long expected,long actual)
    {
        Check.Require(expected==actual,409,"stale_version");
        Check.Require(actual<MaxVersion,409,"version_exhausted");
    }
    private static async Task<IResult> PutSettings(HttpContext ctx,AppDb db,Guid companyId,JsonElement body)
    {
        var t=await PaymentAccess.Gate(ctx,db,companyId,"payment-settings.update");
        var x=PartnerInput.Object(body,"defaultSalesTermId","defaultPurchaseTermId","defaultSalesMethodId","defaultPurchaseMethodId","expectedVersion","version");
        var st=Id(x,"defaultSalesTermId");var pt=Id(x,"defaultPurchaseTermId");var sm=Id(x,"defaultSalesMethodId");var pm=Id(x,"defaultPurchaseMethodId");var expected=PartnerInput.Integer(x,"expectedVersion",0,MaxVersion);
        Check.Require(await db.Scalar("SELECT id FROM foundation.company WHERE tenant_id=@t AND id=@c FOR UPDATE",("t",t),("c",companyId)) is Guid,404,"not_found");
        var before=await ReadSettings(db,t,companyId);Version(expected,before.Version);
        await Validate(db,t,companyId,st,sm,"INBOUND");await Validate(db,t,companyId,pt,pm,"OUTBOUND");
        await db.Execute("INSERT INTO masterdata.company_payment_settings(tenant_id,company_id,default_sales_term_id,default_purchase_term_id,default_sales_method_id,default_purchase_method_id) VALUES(@t,@c,@st::uuid,@pt::uuid,@sm::uuid,@pm::uuid) ON CONFLICT(tenant_id,company_id) DO UPDATE SET default_sales_term_id=EXCLUDED.default_sales_term_id,default_purchase_term_id=EXCLUDED.default_purchase_term_id,default_sales_method_id=EXCLUDED.default_sales_method_id,default_purchase_method_id=EXCLUDED.default_purchase_method_id,version=masterdata.company_payment_settings.version+1",("t",t),("c",companyId),("st",st),("pt",pt),("sm",sm),("pm",pm));
        var after=await ReadSettings(db,t,companyId);await db.Audit(Security.State(ctx).User.Id,t,"update","payment-settings",companyId,new{before,after});return Results.Ok(after);
    }
    private static async Task<IResult> PutRole(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,string role,JsonElement body)
    {
        var t=await PaymentAccess.Gate(ctx,db,companyId,"payment-partner-defaults.update");
        var x=PartnerInput.Object(body,"paymentTermId","paymentMethodId","expectedVersion","version");var term=Id(x,"paymentTermId");var method=Id(x,"paymentMethodId");var expected=PartnerInput.Integer(x,"expectedVersion",0,MaxVersion);
        var relation=await Partner(db,t,companyId,bpId,role,true);var before=await ReadRole(db,t,companyId,relation,role);Version(expected,before.Version);
        await Validate(db,t,companyId,term,method,role=="CUSTOMER"?"INBOUND":"OUTBOUND");
        await db.Execute("INSERT INTO masterdata.business_partner_payment_defaults(tenant_id,company_id,company_business_partner_id,role_code,payment_term_id,payment_method_id) VALUES(@t,@c,@p,@r,@term::uuid,@method::uuid) ON CONFLICT(tenant_id,company_business_partner_id,role_code) DO UPDATE SET payment_term_id=EXCLUDED.payment_term_id,payment_method_id=EXCLUDED.payment_method_id,version=masterdata.business_partner_payment_defaults.version+1",("t",t),("c",companyId),("p",relation),("r",role),("term",term),("method",method));
        var after=await ReadRole(db,t,companyId,relation,role);await db.Audit(Security.State(ctx).User.Id,t,"update","business-partner-payment-defaults",relation,new{roleCode=role,before,after});return Results.Ok(after);
    }
    private static async Task<IResult> Resolve(HttpContext ctx,AppDb db,Guid companyId,Guid bpId,string role,JsonElement body)
    {
        var t=await PaymentAccess.Gate(ctx,db,companyId,"payment-resolution.read");
        var x=PartnerInput.Object(body,"paymentTermId","paymentMethodId");var explicitTerm=Id(x,"paymentTermId");var explicitMethod=Id(x,"paymentMethodId");
        var relation=await Partner(db,t,companyId,bpId,role,false);var direction=role=="CUSTOMER"?"INBOUND":"OUTBOUND";
        await Validate(db,t,companyId,explicitTerm,explicitMethod,direction);
        var partner=await ReadRole(db,t,companyId,relation,role);var company=await ReadSettings(db,t,companyId);
        var companyTerm=role=="CUSTOMER"?company.DefaultSalesTermId:company.DefaultPurchaseTermId;var companyMethod=role=="CUSTOMER"?company.DefaultSalesMethodId:company.DefaultPurchaseMethodId;
        async Task<ResolvedValue> Pick(Guid? a,Guid? b,Guid? c,bool term) {
            foreach(var (id,source) in new[]{(a,"DOCUMENT"),(b,"BUSINESS_PARTNER"),(c,"COMPANY")})
                if(id!=null && (term ? await ValidTerm(db,t,companyId,id,direction,false) : await ValidMethod(db,t,companyId,id,direction,false)))return new(id,source);
            return new(null,"MANUAL");
        }
        return Results.Ok(new Resolution(await Pick(explicitTerm,partner.PaymentTermId,companyTerm,true),await Pick(explicitMethod,partner.PaymentMethodId,companyMethod,false)));
    }
}
