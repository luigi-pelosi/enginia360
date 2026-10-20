using Enginia360.Billing.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

internal sealed class BillingAccessAdapter(OrganizationAccessDbContext db) : IBillingAccess
{
    public async Task<BillingGrant?> ResolveMembership(string subject, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        await tx.CommitAsync(ct);
        return member is null ? null : new(member.TenantId, member.Id);
    }

    public async Task<BillingGrant?> Authorize(string subject, Guid legalEntityId, Guid siteId, string permission,
        bool requireCapability, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        if (member is null) return null;
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
        var allowed = await db.Database.SqlQuery<int>($"""
            SELECT 1 AS "Value" FROM organization_access.company_permissions p
            WHERE p."MembershipId"={member.Id} AND p."TenantId"={member.TenantId}
              AND p."LegalEntityId"={legalEntityId} AND p."Permission"={permission}
              AND p."WarehouseId" IS NULL AND (p."SiteId" IS NULL OR p."SiteId"={siteId})
            """).AnyAsync(ct);
        if (!allowed) return null;
        if (requireCapability && !await db.CapabilityActivations.AnyAsync(x => x.LegalEntityId == legalEntityId
            && x.Capability == "internal-billing" && x.Enabled, ct)) return null;
        await tx.CommitAsync(ct);
        return new(member.TenantId, member.Id);
    }
}
