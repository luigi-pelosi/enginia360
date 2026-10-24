using System.Globalization;
using System.Security.Claims;
using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

// D37/D39/D40: technical closure, owner-local administrative request + outbox, administrative closure.
// Workshop owns the facts and the consequences of a business outcome; the connector owns transport.
internal static partial class AdministrativeEndpoints
{
    internal const int ContractVersion = 1;
    internal static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    private static readonly AdministrativeDelivery Queued = new("Queued", 0, null, null, null);

    internal static void MapClosure(RouteGroupBuilder routes) =>
        routes.MapPost("/orders/{id:guid}/technical-closure", CloseTechnically);
    internal static void MapExternal(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{id:guid}/administrative-requests", Request);
        routes.MapGet("/orders/{id:guid}/administrative-requests", History);
        routes.MapGet("/orders/{id:guid}/closure-state", State);
        routes.MapPost("/orders/{id:guid}/administrative-closure", CloseAdministratively);
        routes.MapPost("/orders/{id:guid}/administrative-requests/{requestId:guid}/reconciliation", Reconcile);
    }
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$", RegexOptions.CultureInvariant)]
    internal static partial Regex Reference();
    [GeneratedRegex(@"^[a-z0-9_]{1,64}$", RegexOptions.CultureInvariant)]
    internal static partial Regex Code();
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    // Server time at PostgreSQL precision; never a client value.
    private static DateTimeOffset Now()
    {
        var now = DateTimeOffset.UtcNow;
        return new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
    }
    // Same key as line additions and installations: one technical change of the order at a time.
    private static Task Lock(WorkshopDbContext db, Guid orderId, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({orderId.ToString()}, 0))", ct);

    private static async Task<(WorkshopGrant Member, WorkOrder Order)?> Find(Guid id, string subject, IWorkshopAccess access,
        WorkshopDbContext db, CancellationToken ct)
    {
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        var order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
        await tx.CommitAsync(ct);
        return order is null ? null : (member, order);
    }

    private static async Task<IResult> CloseTechnically(Guid id, TechnicalClosureRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, IReplacedPartReturns returns, WorkshopDbContext db, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.ExpectedRevision < 0) return Results.BadRequest();
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.orders.complete-technical", true, ct) is null)
            return Results.StatusCode(403);
        // Accepted carcass coverage is insert-only (D73): reading it first can only refuse spuriously, never clear wrongly.
        // Read before the Workshop transaction: no other module is called while a Workshop connection is held.
        var covered = await returns.Covered(member.TenantId, id, ct);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        await Lock(db, id, ct);
        var replay = await db.TechnicalClosures.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (replay is not null)
            return replay.OrderId == id && replay.Revision == request.ExpectedRevision ? Results.Ok(replay.Contract()) : Results.Conflict();
        if (await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct))
            return Results.Conflict(new { code = "already_closed", message = "Commessa già chiusa tecnicamente." });
        // Persisted lifecycle revision under the order lock shared with every editor command; never a row count.
        var revision = await db.Orders.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.Id == id).Select(x => x.CommercialRevision).SingleAsync(ct);
        if (revision != request.ExpectedRevision)
            return Results.Conflict(new { code = "revision_changed", revision, message = "Valori della commessa cambiati: rileggi prima di chiudere." });
        // Fresh committed installations under the order lock shared with RecordPartInstallation (D9 snapshots).
        var required = await db.Installations.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.OrderId == id
            && x.CarcassReturnRequired && x.CarcassPolicyVersion != null).OrderBy(x => x.Id)
            .Select(x => new CarcassInstallation(x.Id, x.LineId, x.CatalogItemId, x.Quantity, x.CarcassPolicyVersion!.Value, x.InstalledAt))
            .ToListAsync(ct);
        var gate = InstallationEndpoints.Gate(id, required, covered);
        if (gate.Status != "Clear")
            return Results.Conflict(new { code = "technical_requirements_pending", gate,
                message = "Chiusura tecnica rifiutata: carcassa da rientrare. Nessuna chiusura registrata." });
        var row = new TechnicalClosure { OrderId = id, Id = request.Id, TenantId = member.TenantId, Revision = revision,
            ClosedAt = Now(), OperatorId = Guid.Parse(subject) };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.technical_closures ("OrderId","Id","TenantId","Revision","ClosedAt","OperatorId")
            VALUES ({row.OrderId},{row.Id},{row.TenantId},{row.Revision},{row.ClosedAt},{row.OperatorId}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict(); // Foreign-tenant command collision, no disclosure.
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/workshop/orders/{id}/closure-state", row.Contract());
    }

    private static async Task<IResult> Request(Guid id, AdministrativeRequestCommand command, ClaimsPrincipal user,
        IWorkshopAccess access, IAdministrativeDeliveries deliveries, WorkshopDbContext db, CancellationToken ct)
    {
        if (command.Id == Guid.Empty || command.ExpectedRevision < 0) return Results.BadRequest();
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.administrative-requests.create", true, ct) is null
            || !await access.CapabilityEnabled(member.TenantId, order.LegalEntityId, "external-administration", ct))
            return Results.StatusCode(403);
        AdministrativeRequest row;
        var created = false;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
            await Lock(db, id, ct);
            var replay = await db.AdministrativeRequests.AsNoTracking().SingleOrDefaultAsync(x => x.Id == command.Id, ct);
            if (replay is not null)
            {
                if (replay.OrderId != id || replay.Revision != command.ExpectedRevision) return Results.Conflict();
                row = replay;
            }
            else
            {
                var closure = await db.TechnicalClosures.AsNoTracking().SingleOrDefaultAsync(x => x.OrderId == id, ct);
                if (closure is null)
                    return Results.Conflict(new { code = "technical_closure_required", message = "Chiudi tecnicamente la commessa prima della richiesta amministrativa." });
                if (closure.Revision != command.ExpectedRevision)
                    return Results.Conflict(new { code = "revision_changed", revision = closure.Revision, message = "Valori della commessa cambiati: rileggi." });
                if (await db.AdministrativeRequests.AnyAsync(x => x.OrderId == id, ct))
                    return Results.Conflict(new { code = "already_requested", message = "Richiesta amministrativa già registrata per la commessa." });
                if (await db.InternalBillingClaims.AnyAsync(x => x.OrderId == id, ct))
                    return Results.Conflict(new { code = "internal_invoice_already_allocated", message = "La commessa è già assegnata alla fatturazione interna." });
                var destination = await db.AdministrativeDestinations.AsNoTracking().Where(x => x.TenantId == member.TenantId
                    && x.LegalEntityId == order.LegalEntityId).OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);
                if (destination is not { Destination: "External" })
                    return Results.Conflict(new { code = "administrative_destination_missing", message = "Destinazione amministrativa della società non configurata. Nessuna richiesta registrata." });
                var lines = await db.Lines.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").OrderBy(x => x.ExpectedRevision).ToListAsync(ct);
                var summary = CommercialEndpoints.Summarize(order, lines, closure.Revision);
                row = new AdministrativeRequest
                {
                    Id = command.Id, TenantId = member.TenantId, OrderId = id, LegalEntityId = order.LegalEntityId, SiteId = order.SiteId,
                    Destination = destination.Destination, DestinationVersion = destination.Version, ContractVersion = ContractVersion,
                    Revision = closure.Revision, NetAmount = Amount(summary.NetAmount), TaxAmount = Amount(summary.TaxAmount),
                    Total = Amount(summary.Total), Currency = summary.Currency, Summary = JsonSerializer.Serialize(summary, Json),
                    RequestedAt = Now(), OperatorId = Guid.Parse(subject)
                };
                // Fact and outbox entry in the same owner-local transaction.
                var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.administrative_requests ("Id","TenantId","OrderId","LegalEntityId","SiteId","Destination","DestinationVersion",
                        "ContractVersion","Revision","NetAmount","TaxAmount","Total","Currency","Summary","RequestedAt","OperatorId")
                    VALUES ({row.Id},{row.TenantId},{row.OrderId},{row.LegalEntityId},{row.SiteId},{row.Destination},{row.DestinationVersion},
                        {row.ContractVersion},{row.Revision},{row.NetAmount},{row.TaxAmount},{row.Total},{row.Currency},CAST({row.Summary} AS jsonb),
                        {row.RequestedAt},{row.OperatorId}) ON CONFLICT DO NOTHING
                    """, ct);
                if (inserted == 0) return Results.Conflict(); // Foreign-tenant command collision, no disclosure.
                await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.administrative_outbox ("RequestId","TenantId","CreatedAt") VALUES ({row.Id},{row.TenantId},{row.RequestedAt})
                    """, ct);
                created = true;
            }
            await tx.CommitAsync(ct);
        }
        var view = (await View(member.TenantId, [row], deliveries, db, ct))[0];
        return created ? Results.Created($"/api/v1/workshop/orders/{id}/administrative-requests", view) : Results.Ok(view);
    }

    private static async Task<IResult> History(Guid id, ClaimsPrincipal user, IWorkshopAccess access,
        IAdministrativeDeliveries deliveries, WorkshopDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.administrative-requests.read", false, ct) is null)
            return Results.NotFound();
        List<AdministrativeRequest> rows;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
            rows = await db.AdministrativeRequests.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.OrderId == id)
                .OrderBy(x => x.RequestedAt).ThenBy(x => x.Id).ToListAsync(ct);
            await tx.CommitAsync(ct);
        }
        return Results.Ok(await View(member.TenantId, rows, deliveries, db, ct));
    }

    private static async Task<IResult> State(Guid id, ClaimsPrincipal user, IWorkshopAccess access,
        IAdministrativeDeliveries deliveries, WorkshopDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null
            || await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.administrative-requests.read", false, ct) is null)
            return Results.NotFound();
        var snapshot = await ReadSnapshot(db, member.TenantId, id, ct);
        var (technical, administrative) = (snapshot.Technical, snapshot.Administrative);
        // Delivery is a second, public observation taken after the Workshop connection is closed.
        var request = snapshot.Request is null ? null
            : (await Contracts([snapshot.Request], snapshot.Outcome is null ? [] : [snapshot.Outcome], member.TenantId, deliveries, ct))[0];
        var status = administrative is not null ? "AdministrativelyClosed"
            : technical is null ? "Open"
            : request is null ? "TechnicallyClosed"
            : request.Status switch { "Confirmed" => "AdministrativelyConfirmed", "Rejected" => "AdministrativeRejected", _ => "AwaitingAdministrativeConfirmation" };
        return Results.Ok(new OrderClosureState(id, status, technical?.Contract(), request, administrative?.Contract()));
    }

    private static async Task<IResult> CloseAdministratively(Guid id, AdministrativeClosureCommand command, ClaimsPrincipal user,
        IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (command.Id == Guid.Empty) return Results.BadRequest();
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.orders.complete-administrative", true, ct) is null)
            return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        await Lock(db, id, ct);
        var replay = await db.AdministrativeClosures.AsNoTracking().SingleOrDefaultAsync(x => x.Id == command.Id, ct);
        if (replay is not null) return replay.OrderId == id ? Results.Ok(replay.Contract()) : Results.Conflict();
        if (await db.AdministrativeClosures.AnyAsync(x => x.OrderId == id, ct))
            return Results.Conflict(new { code = "already_closed", message = "Commessa già chiusa amministrativamente." });
        var request = await db.AdministrativeRequests.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.OrderId == id, ct);
        var outcome = request is null ? null : await db.AdministrativeOutcomes.AsNoTracking().SingleOrDefaultAsync(x => x.RequestId == request.Id, ct);
        // D40: only completed processing with a stable external reference satisfies the external requirement.
        if (outcome is not { Status: "Confirmed", ExternalReference: not null })
            return Results.Conflict(new { code = "external_confirmation_required", status = outcome?.Status ?? (request is null ? "NotRequested" : "Pending"),
                message = "Chiusura amministrativa bloccata: manca la conferma di business del gestionale esterno." });
        var row = new AdministrativeClosure { OrderId = id, Id = command.Id, TenantId = member.TenantId, RequestId = outcome.RequestId,
            ExternalReference = outcome.ExternalReference, ClosedAt = Now(), OperatorId = Guid.Parse(subject) };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.administrative_closures ("OrderId","Id","TenantId","RequestId","ExternalReference","ClosedAt","OperatorId")
            VALUES ({row.OrderId},{row.Id},{row.TenantId},{row.RequestId},{row.ExternalReference},{row.ClosedAt},{row.OperatorId}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/workshop/orders/{id}/closure-state", row.Contract());
    }

    private static async Task<IResult> Reconcile(Guid id, Guid requestId, AdministrativeClosureCommand command,
        ClaimsPrincipal user, IWorkshopAccess access, IAdministrativeRecovery recovery, WorkshopDbContext db, CancellationToken ct)
    {
        if (command.Id == Guid.Empty || requestId == Guid.Empty) return Results.BadRequest();
        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.administrative-requests.reconcile", true, ct) is null
            || !await access.CapabilityEnabled(member.TenantId, order.LegalEntityId, "external-administration", ct)) return Results.StatusCode(403);
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
            if (!await db.AdministrativeRequests.AnyAsync(x => x.Id == requestId && x.TenantId == member.TenantId && x.OrderId == id, ct))
                return Results.NotFound();
            await tx.CommitAsync(ct);
        }
        var result = await recovery.Reconcile(member.TenantId, requestId, command.Id, Guid.Parse(subject), ct);
        if (result is null) return Results.Conflict(new { code = "reconciliation_not_available", message = "Riconciliazione non disponibile: rileggi lo stato. Nessun esito di business modificato." });
        return result.Replayed ? Results.Ok(result) : Results.Json(result, statusCode: 202);
    }

    // One RepeatableRead Workshop snapshot of the order's closure facts: never a mixture of commits.
    internal sealed record ClosureSnapshot(TechnicalClosure? Technical, AdministrativeClosure? Administrative,
        AdministrativeRequest? Request, AdministrativeOutcomeRow? Outcome);
    internal static async Task<ClosureSnapshot> ReadSnapshot(WorkshopDbContext db, Guid tenant, Guid orderId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await InstallationEndpoints.SetTenant(db, tenant, ct);
        var technical = await db.TechnicalClosures.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenant && x.OrderId == orderId, ct);
        var administrative = await db.AdministrativeClosures.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenant && x.OrderId == orderId, ct);
        var request = await db.AdministrativeRequests.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenant && x.OrderId == orderId, ct);
        var outcome = request is null ? null : await db.AdministrativeOutcomes.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == tenant && x.RequestId == request.Id, ct);
        await tx.CommitAsync(ct);
        return new(technical, administrative, request, outcome);
    }

    private static async Task<List<AdministrativeRequestContract>> Contracts(IReadOnlyList<AdministrativeRequest> rows,
        IReadOnlyList<AdministrativeOutcomeRow> outcomes, Guid tenant, IAdministrativeDeliveries deliveries, CancellationToken ct)
    {
        var delivered = await deliveries.Read(tenant, rows.Select(x => x.Id).ToArray(), ct);
        var byRequest = outcomes.ToDictionary(x => x.RequestId);
        return rows.Select(x => x.Contract(byRequest.GetValueOrDefault(x.Id), delivered.GetValueOrDefault(x.Id) ?? Queued)).ToList();
    }

    private static decimal Amount(string value) => decimal.Parse(value, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture);

    private static async Task<List<AdministrativeRequestContract>> View(Guid tenant, IReadOnlyList<AdministrativeRequest> rows,
        IAdministrativeDeliveries deliveries, WorkshopDbContext db, CancellationToken ct)
    {
        if (rows.Count == 0) return [];
        var ids = rows.Select(x => x.Id).ToArray();
        // Outcome first: the connector commits its Completed/Rejected state before Workshop records the outcome.
        Dictionary<Guid, AdministrativeOutcomeRow> outcomes;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, tenant, ct);
            outcomes = await db.AdministrativeOutcomes.AsNoTracking().Where(x => x.TenantId == tenant && ids.Contains(x.RequestId)).ToDictionaryAsync(x => x.RequestId, ct);
            await tx.CommitAsync(ct);
        }
        var delivered = await deliveries.Read(tenant, ids, ct);
        return rows.Select(x => x.Contract(outcomes.GetValueOrDefault(x.Id), delivered.GetValueOrDefault(x.Id) ?? Queued)).ToList();
    }
}

internal sealed class WorkshopAdministrativeOutbox(WorkshopDbContext db, IWorkshopAccess access) : IWorkshopAdministrativeOutbox
{
    public async Task<IReadOnlyList<AdministrativeOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct) =>
        await db.Database.SqlQuery<AdministrativeOutboxEnvelope>($"""
            SELECT "TenantId", "RequestId" FROM workshop.pending_administrative_outbox({limit}, {offset})
            """).ToListAsync(ct);

    public async Task<AdministrativeDispatchMessage?> Read(AdministrativeOutboxEnvelope envelope, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, envelope.TenantId, ct);
        var row = await db.AdministrativeRequests.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == envelope.TenantId && x.Id == envelope.RequestId, ct);
        await tx.CommitAsync(ct);
        // Disabling a capability pauses new worker uses as well as API writes; history stays readable.
        // The envelope supplies tenant scope, never client input. A paused request remains in the durable outbox.
        if (row is null || !await access.CapabilityEnabled(envelope.TenantId, row.LegalEntityId, "external-administration", ct)
            || !await access.CapabilityEnabled(envelope.TenantId, row.LegalEntityId, "workshop", ct)) return null;
        return new(row.TenantId, row.Id, row.OrderId, row.LegalEntityId, row.SiteId, row.ContractVersion, row.SummaryContract());
    }

    public async Task<bool> Record(AdministrativeOutboxEnvelope envelope, AdministrativeOutcome outcome, CancellationToken ct)
    {
        var valid = outcome is { Status: "Confirmed", RejectionCode: null, ExternalReference: { } reference } && AdministrativeEndpoints.Reference().IsMatch(reference)
            || outcome is { Status: "Rejected", ExternalReference: null, RejectionCode: { } code } && AdministrativeEndpoints.Code().IsMatch(code);
        if (!valid) return false;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, envelope.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({envelope.RequestId.ToString()}, 0))", ct);
        if (!await db.AdministrativeRequests.AnyAsync(x => x.TenantId == envelope.TenantId && x.Id == envelope.RequestId, ct)) return false;
        var existing = await db.AdministrativeOutcomes.AsNoTracking().SingleOrDefaultAsync(x => x.RequestId == envelope.RequestId, ct);
        if (existing is not null)
            return existing.Status == outcome.Status && existing.ExternalReference == outcome.ExternalReference && existing.RejectionCode == outcome.RejectionCode;
        var now = DateTimeOffset.UtcNow;
        now = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.administrative_outcomes ("RequestId","TenantId","Status","ExternalReference","RejectionCode","RecordedAt")
            VALUES ({envelope.RequestId},{envelope.TenantId},{outcome.Status},{outcome.ExternalReference},{outcome.RejectionCode},{now}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return false; // The stable reference already confirms another request of the tenant.
        await tx.CommitAsync(ct);
        return true;
    }
}

internal sealed class TechnicalClosure
{
    public Guid OrderId { get; set; }
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public int Revision { get; set; }
    public DateTimeOffset ClosedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal TechnicalClosureContract Contract() => new(Id, OrderId, Revision, ClosedAt, OperatorId);
}
internal sealed class AdministrativeDestination
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public int Version { get; set; }
    public required string Destination { get; set; }
}
internal sealed class AdministrativeRequest
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public required string Destination { get; set; }
    public int DestinationVersion { get; set; }
    public int ContractVersion { get; set; }
    public int Revision { get; set; }
    public decimal NetAmount { get; set; }
    public decimal TaxAmount { get; set; }
    public decimal Total { get; set; }
    public required string Currency { get; set; }
    public required string Summary { get; set; }
    public DateTimeOffset RequestedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal CommercialSummary SummaryContract() =>
        JsonSerializer.Deserialize<CommercialSummary>(Summary, AdministrativeEndpoints.Json) ?? throw new InvalidOperationException("Corrupt request snapshot.");
    internal AdministrativeRequestContract Contract(AdministrativeOutcomeRow? outcome, AdministrativeDelivery delivery) =>
        new(Id, OrderId, LegalEntityId, SiteId, Destination, DestinationVersion, ContractVersion, SummaryContract(), RequestedAt, OperatorId,
            outcome?.Status ?? "Pending", outcome?.ExternalReference, outcome?.RejectionCode, outcome?.RecordedAt, delivery);
}
internal sealed class AdministrativeOutcomeRow
{
    public Guid RequestId { get; set; }
    public Guid TenantId { get; set; }
    public required string Status { get; set; }
    public string? ExternalReference { get; set; }
    public string? RejectionCode { get; set; }
    public DateTimeOffset RecordedAt { get; set; }
}
internal sealed class AdministrativeClosure
{
    public Guid OrderId { get; set; }
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid RequestId { get; set; }
    public required string ExternalReference { get; set; }
    public DateTimeOffset ClosedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal AdministrativeClosureContract Contract() => new(Id, OrderId, RequestId, ExternalReference, ClosedAt, OperatorId);
}
