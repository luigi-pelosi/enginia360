using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal sealed class WorkshopBillingSources(WorkshopDbContext db) : IWorkshopBillingSources
{
    public async Task<WorkshopBillingSource?> Find(Guid verifiedTenantId, Guid orderId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, verifiedTenantId, ct);
        var source = await Read(verifiedTenantId, orderId, ct);
        await tx.CommitAsync(ct);
        return source;
    }

    public async Task<WorkshopBillingSource?> Allocate(Guid verifiedTenantId, Guid orderId, Guid invoiceId,
        int expectedRevision, CancellationToken ct)
    {
        if (invoiceId == Guid.Empty) return null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, verifiedTenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync(
            $"SELECT pg_advisory_xact_lock(hashtextextended({orderId.ToString()}, 0))", ct);
        var source = await Read(verifiedTenantId, orderId, ct);
        if (source is null || source.Revision != expectedRevision) return null;
        var replay = await db.InternalBillingClaims.AsNoTracking().SingleOrDefaultAsync(x => x.InvoiceId == invoiceId, ct);
        if (replay is not null)
            return replay.OrderId == orderId && replay.Revision == expectedRevision
                ? source with { DestinationVersion = replay.DestinationVersion } : null;
        if (await db.InternalBillingClaims.AnyAsync(x => x.OrderId == orderId, ct)
            || await db.AdministrativeRequests.AnyAsync(x => x.OrderId == orderId, ct)) return null;
        var destination = await db.AdministrativeDestinations.AsNoTracking()
            .Where(x => x.TenantId == verifiedTenantId && x.LegalEntityId == source.LegalEntityId)
            .OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);
        if (destination is not { Destination: "Internal" }) return null;
        var now = DateTimeOffset.UtcNow;
        now = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.internal_billing_claims ("InvoiceId","TenantId","OrderId","DestinationVersion","Revision","AllocatedAt")
            VALUES ({invoiceId},{verifiedTenantId},{orderId},{destination.Version},{expectedRevision},{now}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return null;
        await tx.CommitAsync(ct);
        return source with { DestinationVersion = destination.Version };
    }

    private async Task<WorkshopBillingSource?> Read(Guid tenantId, Guid orderId, CancellationToken ct)
    {
        var order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenantId && x.Id == orderId, ct);
        var closure = await db.TechnicalClosures.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenantId && x.OrderId == orderId, ct);
        if (order is null || closure is null) return null;
        var lines = await db.Lines.AsNoTracking().Where(x => x.OrderId == orderId).OrderBy(x => x.ExpectedRevision).ToListAsync(ct);
        var summary = CommercialEndpoints.Summarize(order, lines);
        return new(tenantId, orderId, order.LegalEntityId, order.SiteId, order.PayerId, closure.Revision, 0, summary);
    }
}

internal sealed class InternalBillingClaim
{
    public Guid InvoiceId { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public int DestinationVersion { get; set; }
    public int Revision { get; set; }
    public DateTimeOffset AllocatedAt { get; set; }
}
