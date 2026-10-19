using Enginia360.Inventory.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Api.OrganizationAccess;

// The finite reservation proof grants each exact action/company/site/warehouse separately.
internal sealed class InventoryAccessAdapter(OrganizationAccessDbContext db) : IInventoryAccess
{
    public async Task<bool> Authorize(string subject, Guid companyId, Guid siteId, Guid warehouseId,
        string permission, bool requireCapability, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        if (member is null) return false;
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
        var rows = await db.Database.SqlQuery<int>($"""
            SELECT 1 AS "Value" FROM organization_access.company_permissions p
            JOIN organization_access.warehouses w ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId"
                AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
            WHERE p."MembershipId"={member.Id} AND p."TenantId"={member.TenantId}
                AND p."LegalEntityId"={companyId} AND p."SiteId"={siteId} AND p."WarehouseId"={warehouseId}
                AND p."Permission"={permission}
            """).ToListAsync(ct);
        if (rows.Count == 0) return false;
        if (requireCapability && !await db.CapabilityActivations.AnyAsync(x => x.LegalEntityId == companyId
            && x.Capability == "inventory" && x.Enabled, ct)) return false;
        await tx.CommitAsync(ct);
        return true;
    }
    public async Task<IReadOnlyList<WarehouseChoice>> Warehouses(string subject, Guid companyId, Guid siteId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", ct);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, ct);
        if (member is null) return [];
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
        var rows = await db.Database.SqlQuery<WarehouseChoice>($"""
            SELECT DISTINCT w."Id",w."Name" FROM organization_access.warehouses w
            JOIN organization_access.company_permissions p ON w."Id"=p."WarehouseId" AND w."SiteId"=p."SiteId"
                AND w."LegalEntityId"=p."LegalEntityId" AND w."TenantId"=p."TenantId"
            WHERE p."MembershipId"={member.Id} AND w."TenantId"={member.TenantId}
                AND w."LegalEntityId"={companyId} AND w."SiteId"={siteId} AND p."Permission"='inventory.reservations.read'
            ORDER BY w."Id"
            """).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows;
    }
}
