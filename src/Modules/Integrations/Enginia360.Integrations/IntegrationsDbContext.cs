using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Integrations;

internal sealed class IntegrationsDbContext(DbContextOptions<IntegrationsDbContext> options) : DbContext(options)
{
    internal DbSet<Dispatch> Dispatches => Set<Dispatch>();
    internal DbSet<Reconciliation> Reconciliations => Set<Reconciliation>();
    internal DbSet<PurchaseDispatch> PurchaseDispatches => Set<PurchaseDispatch>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Dispatch>().ToTable("administrative_dispatches", "integrations").HasKey(x => x.RequestId);
        b.Entity<PurchaseDispatch>().ToTable("purchase_dispatches", "integrations").HasKey(x => x.IntentId);
        b.Entity<Reconciliation>().ToTable("administrative_reconciliations", "integrations").HasKey(x => x.Id);
    }
}
// Technical delivery state of one request; never a business outcome by itself.
internal sealed class Dispatch
{
    public Guid RequestId { get; set; }
    public Guid TenantId { get; set; }
    public required string State { get; set; }
    public int Attempts { get; set; }
    public int Failures { get; set; }
    public DateTimeOffset? LastAttemptAt { get; set; }
    public DateTimeOffset NextAttemptAt { get; set; }
    public DateTimeOffset? LeaseUntil { get; set; }
    public string? ExternalReference { get; set; }
    public string? RejectionCode { get; set; }
    public string? LastError { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
internal sealed class AdministrativeDeliveries(IntegrationsDbContext db) : IAdministrativeDeliveries
{
    public async Task<IReadOnlyDictionary<Guid, AdministrativeDelivery>> Read(Guid verifiedTenantId, IReadOnlyCollection<Guid> requestIds, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var rows = await db.Dispatches.AsNoTracking().Where(x => x.TenantId == verifiedTenantId && requestIds.Contains(x.RequestId)).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows.ToDictionary(x => x.RequestId, x => new AdministrativeDelivery(x.State, x.Attempts, x.LastAttemptAt,
            x.State is "Completed" or "Rejected" or "NeedsReconciliation" ? null : x.NextAttemptAt, x.LastError, x.Failures));
    }
}
// Integrations owns purchase_dispatches: Inventory reads the technical state only through IPurchaseDeliveries (tenant-scoped, RLS-bound).
internal sealed class PurchaseDeliveries(IntegrationsDbContext db) : IPurchaseDeliveries
{
    public async Task<IReadOnlyDictionary<Guid, PurchaseDelivery>> Read(Guid verifiedTenantId, IReadOnlyCollection<Guid> intentIds, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var rows = await db.PurchaseDispatches.AsNoTracking().Where(x => x.TenantId == verifiedTenantId && intentIds.Contains(x.IntentId)).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows.ToDictionary(x => x.IntentId, x => new PurchaseDelivery(x.State, x.LastError));
    }
}
// Technical delivery state of one purchase intent; never a business outcome by itself.
internal sealed class PurchaseDispatch
{
    public Guid IntentId { get; set; }
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public required string State { get; set; }
    public int Attempts { get; set; }
    public int Failures { get; set; }
    public DateTimeOffset? LastAttemptAt { get; set; }
    public DateTimeOffset NextAttemptAt { get; set; }
    public DateTimeOffset? LeaseUntil { get; set; }
    public string? ExternalReference { get; set; }
    public string? LastError { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
}
