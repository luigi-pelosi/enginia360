using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Enginia360.Integrations;

// One dispatch cycle. Delivery is at least once and never exactly once: the stable request ID lets the receiver
// deduplicate, Received is acquisition only (D40), and only Completed/Rejected become Workshop outcomes.
internal sealed class AdministrativeDispatcher(IWorkshopAdministrativeOutbox outbox, IntegrationsDbContext db,
    SimulatorConnector connector, ConnectorOptions options, ILogger<AdministrativeDispatcher> logger)
{
    private static DateTimeOffset Now()
    {
        var now = DateTimeOffset.UtcNow;
        return new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
    }

    internal async Task<int> RunOnce(int offset, CancellationToken ct)
    {
        var batch = await outbox.Pending(20, offset, ct);
        foreach (var envelope in batch)
        {
            var dispatch = await Claim(envelope, ct);
            if (dispatch is not null) await Process(envelope, dispatch, ct);
        }
        // A blocked old batch must not monopolize discovery. This is only a scan position, not business state;
        // a restart begins at zero, and every completed pass wraps back to cover rows removed during the scan.
        return batch.Count < 20 || offset > int.MaxValue - 20 ? 0 : offset + 20;
    }

    private async Task SetTenant(Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    // Short lease instead of a transaction held across the remote call; an expired lease is safely re-claimed.
    private async Task<Dispatch?> Claim(AdministrativeOutboxEnvelope envelope, CancellationToken ct)
    {
        var now = Now();
        var lease = now + options.Lease;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(envelope.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO integrations.administrative_dispatches ("RequestId","TenantId","State","Attempts","NextAttemptAt","UpdatedAt")
            VALUES ({envelope.RequestId},{envelope.TenantId},'Queued',0,{now},{now}) ON CONFLICT DO NOTHING
            """, ct);
        var claimed = await db.Dispatches.FromSql($"""
            UPDATE integrations.administrative_dispatches SET "LeaseUntil"={lease}, "UpdatedAt"={now}
            WHERE "RequestId"={envelope.RequestId} AND "TenantId"={envelope.TenantId} AND "NextAttemptAt"<={now}
                AND "State" <> 'NeedsReconciliation'
                AND ("LeaseUntil" IS NULL OR "LeaseUntil"<{now})
            RETURNING *
            """).AsNoTracking().ToListAsync(ct);
        await tx.CommitAsync(ct);
        return claimed.SingleOrDefault();
    }

    private async Task Process(AdministrativeOutboxEnvelope envelope, Dispatch dispatch, CancellationToken ct)
    {
        // Final connector state already committed (e.g. crash before the Workshop outcome): finish, never resend.
        if (dispatch.State is "Completed" or "Rejected")
        {
            await Finish(envelope, dispatch, ct);
            return;
        }
        var message = await outbox.Read(envelope, ct);
        if (message is null || message.TenantId != envelope.TenantId || message.RequestId != envelope.RequestId)
        {
            await Save(dispatch, dispatch.State, dispatch.Attempts, Now() + options.RetryDelay, "source_unavailable", ct);
            return;
        }
        var submitting = dispatch.State is not ("Received" or "Uncertain");
        var attempts = dispatch.Attempts + (submitting ? 1 : 0);
        if (submitting)
        {
            // Persist uncertainty BEFORE crossing the process boundary. A crash after remote commit but
            // before its response must restart with a status lookup, never a blind second submission.
            await using var intent = await db.Database.BeginTransactionAsync(ct);
            await SetTenant(envelope.TenantId, ct);
            var marked = await db.Database.ExecuteSqlInterpolatedAsync($"""
                UPDATE integrations.administrative_dispatches SET "State"='Uncertain', "Attempts"={attempts}, "LastAttemptAt"={Now()}
                WHERE "TenantId"={envelope.TenantId} AND "RequestId"={envelope.RequestId} AND "LeaseUntil"={dispatch.LeaseUntil}
                """, ct);
            if (marked != 1) return;
            await intent.CommitAsync(ct);
        }
        var result = submitting ? await connector.Submit(message, ct) : await connector.Status(message, ct);
        var now = Now();
        dispatch.LastAttemptAt = now;
        switch (result.Outcome)
        {
            case ConnectorOutcome.Completed:
                dispatch.ExternalReference = result.ExternalReference;
                if (await Save(dispatch, "Completed", attempts, now, null, ct)) await Finish(envelope, dispatch, ct);
                break;
            case ConnectorOutcome.Rejected:
                // Business refusal: final, visible, never retried.
                dispatch.RejectionCode = result.Code;
                if (await Save(dispatch, "Rejected", attempts, now, null, ct)) await Finish(envelope, dispatch, ct);
                break;
            case ConnectorOutcome.Received:
                await Save(dispatch, "Received", attempts, now + options.PollInterval, null, ct);
                break;
            case ConnectorOutcome.NotFound:
                await Save(dispatch, "Queued", attempts, now, "not_found", ct);
                break;
            default:
                // A failed response does not establish whether the receiver applied the request (T06).
                // Reconcile with GET; resubmit the stable ID only after an explicit matching NotFound.
                dispatch.Failures++;
                var next = now + TimeSpan.FromMilliseconds(Math.Min(300000, options.RetryDelay.TotalMilliseconds * Math.Pow(2, Math.Min(dispatch.Failures - 1, 16))));
                await Save(dispatch, dispatch.Failures >= 4 ? "NeedsReconciliation" : "Uncertain", attempts, next, result.Code, ct);
                break;
        }
    }

    private async Task Finish(AdministrativeOutboxEnvelope envelope, Dispatch dispatch, CancellationToken ct)
    {
        var outcome = dispatch.State == "Completed"
            ? new AdministrativeOutcome("Confirmed", dispatch.ExternalReference, null)
            : new AdministrativeOutcome("Rejected", null, dispatch.RejectionCode);
        if (!await outbox.Record(envelope, outcome, ct))
        {
            logger.LogWarning(new EventId(611), "Administrative outcome refused {RequestId}", envelope.RequestId);
            await Save(dispatch, dispatch.State, dispatch.Attempts, Now() + options.RetryDelay, "outcome_refused", ct);
        }
    }

    private async Task<bool> Save(Dispatch dispatch, string state, int attempts, DateTimeOffset next, string? error, CancellationToken ct)
    {
        dispatch.State = state;
        dispatch.Attempts = attempts;
        var now = Now();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(dispatch.TenantId, ct);
        var updated = await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE integrations.administrative_dispatches SET "State"={state}, "Attempts"={attempts}, "Failures"={dispatch.Failures}, "LastAttemptAt"={dispatch.LastAttemptAt},
                "NextAttemptAt"={next}, "LeaseUntil"=NULL, "ExternalReference"={dispatch.ExternalReference},
                "RejectionCode"={dispatch.RejectionCode}, "LastError"={error}, "UpdatedAt"={now}
            WHERE "RequestId"={dispatch.RequestId} AND "TenantId"={dispatch.TenantId} AND "LeaseUntil"={dispatch.LeaseUntil}
            """, ct);
        await tx.CommitAsync(ct);
        if (updated != 1) return false; // Fencing: a stale worker cannot clear or overwrite a newer lease.
        logger.LogInformation(new EventId(610), "Administrative dispatch {RequestId} {State} {Attempts} {Error}", dispatch.RequestId, state, attempts, error);
        return true;
    }
}

internal sealed class AdministrativeDispatchWorker(IServiceScopeFactory scopes, ConnectorOptions options,
    ILogger<AdministrativeDispatchWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var offset = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            var nextOffset = offset > int.MaxValue - 20 ? 0 : offset + 20;
            try
            {
                await using var scope = scopes.CreateAsyncScope();
                nextOffset = await scope.ServiceProvider.GetRequiredService<AdministrativeDispatcher>().RunOnce(offset, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception error)
            {
                // Nothing is lost: the outbox entry stays pending and any lease expires.
                logger.LogWarning(new EventId(612), "Administrative dispatch cycle failed {ErrorType}", error.GetType().Name);
            }
            offset = nextOffset;
            try { await Task.Delay(options.PollInterval, stoppingToken); }
            catch (OperationCanceledException) { return; }
        }
    }
}
