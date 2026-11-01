using Enginia360.Inventory.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Enginia360.Integrations;

// One receipt dispatch cycle, isolated from the sales dispatcher: own table, own lease/claim, own worker. Never an exactly-once guarantee.
// A persisted attempt is never repeated as a POST: after any attempt the only further traffic is GET lookup/readback. Only a pre-flight
// refusal (NotSent) returns to Queued. Giobby never yields a conclusive business refusal here, so there is no Rejected path.
internal sealed class ReceiptDispatcher(IReceiptDispatchOutbox outbox, IntegrationsDbContext db, GiobbyReceiptConnector connector,
    ConnectorOptions options, ILogger<ReceiptDispatcher> logger)
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
        return batch.Count < 20 || offset > int.MaxValue - 20 ? 0 : offset + 20;
    }

    private async Task SetTenant(Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    // Short lease instead of a transaction held across the remote calls; an expired lease is safely re-claimed.
    private async Task<ReceiptDispatch?> Claim(ReceiptOutboxEnvelope envelope, CancellationToken ct)
    {
        var now = Now();
        var lease = now + options.Lease;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(envelope.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO integrations.receipt_dispatches ("ReceiptId","TenantId","LegalEntityId","State","Attempts","NextAttemptAt","UpdatedAt")
            VALUES ({envelope.ReceiptId},{envelope.TenantId},{envelope.LegalEntityId},'Queued',0,{now},{now}) ON CONFLICT DO NOTHING
            """, ct);
        var claimed = await db.ReceiptDispatches.FromSql($"""
            UPDATE integrations.receipt_dispatches SET "LeaseUntil"={lease}, "UpdatedAt"={now}
            WHERE "ReceiptId"={envelope.ReceiptId} AND "TenantId"={envelope.TenantId} AND "NextAttemptAt"<={now}
                AND ("LeaseUntil" IS NULL OR "LeaseUntil"<{now})
            RETURNING *
            """).AsNoTracking().ToListAsync(ct);
        await tx.CommitAsync(ct);
        return claimed.SingleOrDefault();
    }

    private async Task Process(ReceiptOutboxEnvelope envelope, ReceiptDispatch dispatch, CancellationToken ct)
    {
        // Final connector state already committed (crash before the Inventory outcome): finish, never resend.
        if (dispatch.State == "Completed")
        {
            await Finish(envelope, dispatch, ct);
            return;
        }
        var message = await outbox.Read(envelope, ct);
        if (message is null || message.TenantId != envelope.TenantId || message.ReceiptId != envelope.ReceiptId)
        {
            await Save(dispatch, dispatch.State, dispatch.Attempts, Now() + options.RetryDelay, "source_unavailable", ct);
            return;
        }
        // Binding frozen at creation (R05.b.0): a changed destination holds, never retargets or falls back.
        if (message.DestinationFingerprint != options.Giobby!.ReceiptFingerprint)
        {
            await Save(dispatch, dispatch.State, dispatch.Attempts, Now() + options.RetryDelay, "destination_binding_mismatch", ct);
            return;
        }
        var submitting = dispatch.State == "Queued";
        var attempts = dispatch.Attempts + (submitting ? 1 : 0);
        if (submitting)
        {
            // Persist uncertainty BEFORE crossing the process boundary: a crash after the remote commit restarts with a lookup, never a blind second POST.
            await using var intent = await db.Database.BeginTransactionAsync(ct);
            await SetTenant(envelope.TenantId, ct);
            var marked = await db.Database.ExecuteSqlInterpolatedAsync($"""
                UPDATE integrations.receipt_dispatches SET "State"='Uncertain', "Attempts"={attempts}, "LastAttemptAt"={Now()}
                WHERE "TenantId"={envelope.TenantId} AND "ReceiptId"={envelope.ReceiptId} AND "LeaseUntil"={dispatch.LeaseUntil}
                """, ct);
            if (marked != 1) return;
            await intent.CommitAsync(ct);
        }
        var result = submitting ? await connector.Submit(message, ct) : await connector.Status(message with { KnownDocumentId = dispatch.KnownDocumentId }, ct);
        var now = Now();
        dispatch.LastAttemptAt = now;
        // Persist the known ACK before a later cycle can issue detail GET; never derive absence or repost.
        if (result.Code == "ack_pending" && result.ExternalReference is { } ack && int.TryParse(ack.AsSpan("GiobbyReceipt-".Length), out var known) && known > 0)
        {
            dispatch.KnownDocumentId = known;
            await Save(dispatch, "Uncertain", attempts, now, "ack_pending", ct);
            return;
        }
        switch (result.Outcome)
        {
            case ConnectorOutcome.Completed:
                dispatch.ExternalReference = result.ExternalReference;
                if (await Save(dispatch, "Completed", attempts, now, null, ct)) await Finish(envelope, dispatch, ct);
                break;
            case ConnectorOutcome.NotSent when submitting:
                // Nothing left this process: the attempt did not happen, so the next cycle may submit.
                await Save(dispatch, "Queued", attempts - 1, now + options.RetryDelay, result.Code, ct);
                break;
            default:
                // A failed or unparseable response does not establish whether the receiver applied the request (T06): only GET afterwards.
                dispatch.Failures++;
                var next = now + TimeSpan.FromMilliseconds(Math.Min(300000, options.RetryDelay.TotalMilliseconds * Math.Pow(2, Math.Min(dispatch.Failures - 1, 16))));
                await Save(dispatch, "Uncertain", attempts, next, result.Code, ct);
                break;
        }
    }

    private async Task Finish(ReceiptOutboxEnvelope envelope, ReceiptDispatch dispatch, CancellationToken ct)
    {
        if (!await outbox.Record(envelope, dispatch.ExternalReference!, ct))
        {
            logger.LogWarning(new EventId(621), "Receipt outcome refused {ReceiptId}", envelope.ReceiptId);
            await Save(dispatch, dispatch.State, dispatch.Attempts, Now() + options.RetryDelay, "outcome_refused", ct);
        }
    }

    private async Task<bool> Save(ReceiptDispatch dispatch, string state, int attempts, DateTimeOffset next, string? error, CancellationToken ct)
    {
        dispatch.State = state;
        dispatch.Attempts = attempts;
        var now = Now();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(dispatch.TenantId, ct);
        var updated = await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE integrations.receipt_dispatches SET "State"={state}, "Attempts"={attempts}, "Failures"={dispatch.Failures}, "LastAttemptAt"={dispatch.LastAttemptAt},
                "KnownDocumentId"={dispatch.KnownDocumentId}, "NextAttemptAt"={next}, "LeaseUntil"=NULL, "ExternalReference"={dispatch.ExternalReference}, "LastError"={error}, "UpdatedAt"={now}
            WHERE "ReceiptId"={dispatch.ReceiptId} AND "TenantId"={dispatch.TenantId} AND "LeaseUntil"={dispatch.LeaseUntil}
            """, ct);
        await tx.CommitAsync(ct);
        if (updated != 1) return false; // Fencing: a stale worker cannot clear or overwrite a newer lease.
        logger.LogInformation(new EventId(620), "Receipt dispatch {ReceiptId} {State} {Attempts} {Error}", dispatch.ReceiptId, state, attempts, error);
        return true;
    }
}

internal sealed class ReceiptDispatchWorker(IServiceScopeFactory scopes, ConnectorOptions options, ILogger<ReceiptDispatchWorker> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var offset = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            var nextOffset = offset > int.MaxValue - 20 ? 0 : offset + 20;
            try
            {
                // Only the verified GiobbyV1 destination dispatches receipts; the simulator or an unknown protocol never claims an intent.
                if (options.ProtocolVerified && options.Kind == "GiobbyV1")
                {
                    await using var scope = scopes.CreateAsyncScope();
                    nextOffset = await scope.ServiceProvider.GetRequiredService<ReceiptDispatcher>().RunOnce(offset, stoppingToken);
                }
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested) { return; }
            catch (Exception error)
            {
                // Nothing is lost: the intent stays pending and any lease expires.
                logger.LogWarning(new EventId(622), "Receipt dispatch cycle failed {ErrorType}", error.GetType().Name);
            }
            offset = nextOffset;
            try { await Task.Delay(options.PollInterval, stoppingToken); }
            catch (OperationCanceledException) { return; }
        }
    }
}
