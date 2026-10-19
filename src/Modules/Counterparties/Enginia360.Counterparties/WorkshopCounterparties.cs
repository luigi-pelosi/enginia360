using Enginia360.Counterparties.Contracts;
using Enginia360.Counterparties.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Counterparties;

internal sealed class WorkshopCounterparties(ICounterpartyAccess access, CounterpartiesDbContext db) : IWorkshopCounterparties
{
    public async Task<bool> CanUsePayer(string subject, Guid verifiedTenantId, Guid companyId, Guid counterpartyId, CancellationToken ct)
    {
        var grant = await access.Authorize(subject, companyId, "counterparties.read", ct);
        if (grant is null || grant.TenantId != verifiedTenantId) return false;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {grant.TenantId.ToString()}, true)", ct);
        var exists = await db.Counterparties.AnyAsync(x => x.Id == counterpartyId && x.TenantId == grant.TenantId, ct);
        await tx.CommitAsync(ct);
        return exists;
    }
}
