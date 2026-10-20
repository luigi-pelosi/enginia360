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

    internal async Task RunOnce(CancellationToken ct)
    {
        foreach (var envelope in await outbox.Pending(20, ct))
        {
            var dispatch = await Claim(envelope, ct);
            if (dispatch is not null) await Process(envelope, dispatch, ct);
        }
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
        var submitting = dispatch.State is not "Received";
        var result = submitting ? await connector.Submit(message, ct) : await connector.Status(message, ct);
        var attempts = dispatch.Attempts + (submitting ? 1 : 0);
        var now = Now();
        dispatch.LastAttemptAt = now;
        switch (result.Outcome)
        {
            case ConnectorOutcome.Completed:
                dispatch.ExternalReference = result.ExternalReference;
                await Save(dispatch, "Completed", attempts, now, null, ct);
                await Finish(envelope, dispatch, ct);
                break;
            case ConnectorOutcome.Rejected:
                // Business refusal: final, visible, never retried.
                dispatch.RejectionCode = result.Code;
                await Save(dispatch, "Rejected", attempts, now, null, ct);
                await Finish(envelope, dispatch, ct);
                break;
            case ConnectorOutcome.Received:
                await Save(dispatch, "Received", attempts, now + options.PollInterval, null, ct);
                break;
            case ConnectorOutcome.NotFound:
                await Save(dispatch, "Queued", attempts, now, "not_found", ct);
                break;
            default:
                await Save(dispatch, submitting ? "Retrying" : dispatch.State, attempts, now + options.RetryDelay, result.Code, ct);
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

    private async Task Save(Dispatch dispatch, string state, int attempts, DateTimeOffset next, string? error, CancellationToken ct)
    {
        dispatch.State = state;
        dispatch.Attempts = attempts;
        var now = Now();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(dispatch.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE integrations.administrative_dispatches SET "State"={state}, "Attempts"={attempts}, "LastAttemptAt"={dispatch.LastAttemptAt},
                "NextAttemptAt"={next}, "LeaseUntil"=NULL, "ExternalReference"={dispatch.ExternalReference},
                "RejectionCode"={dispatch.RejectionCode}, "LastError"={error}, "UpdatedAt"={now}
            WHERE "RequestId"={dispatch.RequestId} AND "TenantId"={dispatch.TenantId}
            """, ct);
        await tx.CommitAsync(ct);
        logger.LogInformation(new EventId(610), "Administrative dispatch {RequestId} {State} {Attempts} {Error}", dispatch.RequestId, state, attempts, error);
    }
}

internal sealed class AdministrativeDispatchWorker(IServiceScopeFactory scopes, ConnectorOptions options,
    ILogger<AdministrativeDispatchWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await using var scope = scopes.CreateAsyncScope();
                await scope.ServiceProvider.GetRequiredService<AdministrativeDispatcher>().RunOnce(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception error)
            {
                // Nothing is lost: the outbox entry stays pending and any lease expires.
                logger.LogWarning(new EventId(612), "Administrative dispatch cycle failed {ErrorType}", error.GetType().Name);
            }
            try { await Task.Delay(options.PollInterval, stoppingToken); }
            catch (OperationCanceledException) { return; }
        }
    }
}
