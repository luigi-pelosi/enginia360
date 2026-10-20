using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

internal sealed class WorkshopAccessAdapter(OrganizationAccessDbContext db) : IWorkshopAccess
{
    public async Task<WorkshopGrant?> ResolveMembership(string subject, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        await tx.CommitAsync(ct);
        return member is null ? null : new(member.TenantId, member.Id);
    }

    public async Task<IReadOnlyList<WorkshopContext>> ListContexts(string subject, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        if (member is null) return [];
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
        var rows = await db.Database.SqlQuery<WorkshopContext>($"""
            SELECT DISTINCT le."Id" AS "LegalEntityId", le."Name" AS "LegalEntityName",
                s."Id" AS "SiteId", s."Name" AS "SiteName"
            FROM organization_access.company_permissions p
            JOIN organization_access.legal_entities le ON le."Id" = p."LegalEntityId" AND le."TenantId" = p."TenantId"
            JOIN organization_access.sites s ON s."LegalEntityId" = le."Id" AND s."TenantId" = le."TenantId"
            JOIN organization_access.capability_activations a ON a."LegalEntityId" = le."Id"
            WHERE p."MembershipId" = {member.Id} AND p."Permission" = 'workshop.orders.create'
                AND p."WarehouseId" IS NULL AND (p."SiteId" IS NULL OR p."SiteId" = s."Id")
                AND a."Capability" = 'workshop' AND a."Enabled"
            ORDER BY le."Id", s."Id"
            """).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows;
    }

    public async Task<WorkshopGrant?> Authorize(string subject, Guid companyId, Guid siteId,
        string permission, bool requireCapability, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        if (member is null) return null;
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
        var rows = await db.Database.SqlQuery<int>($"""
            SELECT 1 AS "Value" FROM organization_access.company_permissions p
            JOIN organization_access.sites s ON s."LegalEntityId" = p."LegalEntityId" AND s."TenantId" = p."TenantId"
            WHERE p."MembershipId" = {member.Id} AND p."TenantId" = {member.TenantId}
                AND p."LegalEntityId" = {companyId} AND s."Id" = {siteId}
                AND p."Permission" = {permission} AND p."WarehouseId" IS NULL
                AND (p."SiteId" IS NULL OR p."SiteId" = s."Id")
            """).ToListAsync(ct);
        if (rows.Count == 0) return null;
        if (requireCapability && !await db.CapabilityActivations.AnyAsync(x => x.LegalEntityId == companyId && x.Capability == "workshop" && x.Enabled, ct))
            return null;
        await tx.CommitAsync(ct);
        return new(member.TenantId, member.Id);
    }

    public async Task<bool> CapabilityEnabled(Guid verifiedTenantId, Guid companyId, string capability, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var enabled = await db.CapabilityActivations.AnyAsync(x => x.LegalEntityId == companyId && x.Capability == capability && x.Enabled, ct);
        await tx.CommitAsync(ct);
        return enabled;
    }
}
