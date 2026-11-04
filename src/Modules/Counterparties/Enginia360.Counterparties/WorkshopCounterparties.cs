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
        await using var tx = await db.BeginUserOperation(grant.TenantId, companyId, ct);
        var exists = await db.Counterparties.AnyAsync(x => x.Id == counterpartyId && x.TenantId == grant.TenantId, ct);
        await tx.CommitAsync(ct);
        return exists;
    }

    public async Task<InvoiceCounterparty?> Find(Guid verifiedTenantId, Guid counterpartyId, CancellationToken ct)
    {
        // Billing.Confirm creates new user-derived work; this is not an outbox
        // consumer and a tenant UUID alone must never serve as authentication.
        await using var tx = await db.BeginUserOperation(verifiedTenantId, null, ct);
        var row = await db.Counterparties.AsNoTracking().SingleOrDefaultAsync(x => x.Id == counterpartyId && x.TenantId == verifiedTenantId, ct);
        await tx.CommitAsync(ct);
        // Preserve the old recipient-port shape guaranteed by 0003 before MVP04:
        // a minimally registered identity is not a completed legacy recipient.
        // This is no fiscal validation and does not make these fields mandatory
        // for shared-master creation, payer selection or the new management UI.
        return row is null || row.FiscalIdentifier.Trim(' ').Length == 0 || row.RegisteredOffice.Trim(' ').Length == 0
            ? null : new(row.Id, row.LegalName, row.FiscalIdentifier, row.RegisteredOffice);
    }
}
