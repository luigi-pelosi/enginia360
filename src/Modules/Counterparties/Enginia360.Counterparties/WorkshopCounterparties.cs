using Enginia360.Counterparties.Contracts;
using Enginia360.Counterparties.Infrastructure;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Counterparties;

internal sealed class WorkshopCounterparties(ICounterpartyAccess access, CounterpartiesDbContext db) : IWorkshopCounterparties, IInvoiceCounterparties
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

    public async Task<InvoiceCounterparty?> Find(Guid verifiedTenantId, Guid counterpartyId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var row = await db.Counterparties.AsNoTracking().SingleOrDefaultAsync(x => x.Id == counterpartyId && x.TenantId == verifiedTenantId, ct);
        await tx.CommitAsync(ct);
        return row is null ? null : new(row.Id, row.LegalName, row.FiscalIdentifier, row.RegisteredOffice);
    }
}
