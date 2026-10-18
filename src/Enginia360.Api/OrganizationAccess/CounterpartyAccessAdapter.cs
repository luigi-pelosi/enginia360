using Enginia360.Counterparties.Contracts;
using Microsoft.EntityFrameworkCore;
namespace Enginia360.Api.OrganizationAccess;

internal sealed class CounterpartyAccessAdapter(OrganizationAccessDbContext db) : ICounterpartyAccess
{
    public async Task<IReadOnlyList<CounterpartyCompany>> ListCompanies(string subject, CancellationToken cancellationToken)
    {
        await using var tx = await db.Database.BeginTransactionAsync(cancellationToken);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", cancellationToken);
        var member = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, cancellationToken);
        if (member is null) return [];
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", cancellationToken);
        var companies = await db.Database.SqlQuery<CounterpartyCompany>($"SELECT DISTINCT le.\"Id\" AS \"LegalEntityId\", le.\"Name\" AS \"LegalEntityName\" FROM organization_access.company_permissions p JOIN organization_access.legal_entities le ON le.\"Id\"=p.\"LegalEntityId\" AND le.\"TenantId\"=p.\"TenantId\" WHERE p.\"MembershipId\"={member.Id} AND p.\"Permission\"='counterparties.read' AND p.\"SiteId\" IS NULL AND p.\"WarehouseId\" IS NULL ORDER BY le.\"Id\"").ToListAsync(cancellationToken);
        await tx.CommitAsync(cancellationToken);
        return companies;
    }
    public async Task<CounterpartyAccess?> Authorize(string subject, Guid legalEntityId, string permission, CancellationToken cancellationToken)
    {
        await using var tx = await db.Database.BeginTransactionAsync(cancellationToken);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject', {subject}, true)", cancellationToken);
        var membership = await db.Memberships.AsNoTracking().SingleOrDefaultAsync(x => x.IdentitySubject == subject, cancellationToken);
        if (membership is null) return null;
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {membership.TenantId.ToString()}, true)", cancellationToken);
        var grants = await db.Database.SqlQuery<int>($"SELECT 1 AS \"Value\" FROM organization_access.company_permissions WHERE \"MembershipId\"={membership.Id} AND \"TenantId\"={membership.TenantId} AND \"LegalEntityId\"={legalEntityId} AND \"Permission\"={permission} AND \"SiteId\" IS NULL AND \"WarehouseId\" IS NULL").ToListAsync(cancellationToken);
        if (permission == "counterparties.common.edit")
        {
            grants = await db.Database.SqlQuery<int>($"SELECT 1 AS \"Value\" FROM organization_access.common_edit_permissions WHERE \"MembershipId\"={membership.Id} AND \"TenantId\"={membership.TenantId}").ToListAsync(cancellationToken);
            var canRead = await db.Database.SqlQuery<int>($"SELECT 1 AS \"Value\" FROM organization_access.company_permissions WHERE \"MembershipId\"={membership.Id} AND \"TenantId\"={membership.TenantId} AND \"LegalEntityId\"={legalEntityId} AND \"Permission\"='counterparties.read' AND \"SiteId\" IS NULL AND \"WarehouseId\" IS NULL").ToListAsync(cancellationToken);
            if (canRead.Count == 0) return null;
        }
        await tx.CommitAsync(cancellationToken);
        return grants.Count == 0 ? null : new(membership.TenantId, membership.Id);
    }
}
