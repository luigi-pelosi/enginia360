using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Integrations;

// Technical recovery schedules verification; it cannot overwrite a final business outcome.
internal sealed class AdministrativeRecovery(IntegrationsDbContext db) : IAdministrativeRecovery
{
    public async Task<AdministrativeReconciliation?> Reconcile(Guid verifiedTenantId, Guid requestId, Guid commandId, Guid operatorId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({commandId.ToString()}, 0))", ct);
        var prior = await db.Reconciliations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == commandId, ct);
        if (prior is not null)
            return prior.RequestId == requestId && prior.OperatorId == operatorId ? new(true) : null;
        var now = DateTimeOffset.UtcNow;
        var updated = await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE integrations.administrative_dispatches SET "State"='Uncertain', "Failures"=0, "NextAttemptAt"={now}, "LastError"=NULL, "UpdatedAt"={now}
            WHERE "TenantId"={verifiedTenantId} AND "RequestId"={requestId} AND "State"='NeedsReconciliation'
                AND ("LeaseUntil" IS NULL OR "LeaseUntil"<{now})
            """, ct);
        if (updated != 1) return null;
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO integrations.administrative_reconciliations ("Id","TenantId","RequestId","OperatorId","RequestedAt")
            VALUES ({commandId},{verifiedTenantId},{requestId},{operatorId},{now}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted != 1) return null; // A foreign-tenant command ID collision must not change any state.
        await tx.CommitAsync(ct);
        return new(false);
    }
}
internal sealed class Reconciliation
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid RequestId { get; set; }
    public Guid OperatorId { get; set; }
    public DateTimeOffset RequestedAt { get; set; }
}
