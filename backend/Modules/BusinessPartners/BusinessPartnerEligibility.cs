using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.BusinessPartners;

// L'eleggibilità risolve i record autorevoli per ID senza attribuire autorità all'operatore.
// I moduli chiamanti devono verificare anche use_customer/use_supplier per la precisa azienda.
public static class BusinessPartnerEligibility
{
    internal const string ActiveStates="t.is_enabled AND c.is_enabled AND b.status='ACTIVE' AND cbp.status='ACTIVE' AND cr.status='ACTIVE'";
    internal const string Joins="""
        FROM masterdata.company_business_partner cbp
        JOIN foundation.company c ON c.tenant_id=cbp.tenant_id AND c.id=cbp.company_id
        JOIN masterdata.business_partner b ON b.tenant_id=cbp.tenant_id AND b.id=cbp.business_partner_id
        JOIN foundation.tenant t ON t.id=cbp.tenant_id
        """;
    public static void ValidateRole(string role)=>Check.Require(role is "CUSTOMER" or "SUPPLIER");
    public static async Task<bool> IsEligible(AppDb db,Guid tenant,Guid company,Guid partner,string role)
    {
        ValidateRole(role);
        return (bool)(await db.Scalar("SELECT EXISTS(SELECT 1 "+Joins+" JOIN masterdata.company_business_partner_role cr ON cr.tenant_id=cbp.tenant_id AND cr.company_business_partner_id=cbp.id WHERE cbp.tenant_id=@t AND cbp.company_id=@c AND cbp.business_partner_id=@b AND cr.role_code=@role AND "+ActiveStates+")",("t",tenant),("c",company),("b",partner),("role",role)))!;
    }
}
