using System.Globalization;
using System.Security.Claims;
using System.Text.Json;
using System.Text.Json.Nodes;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal static class ActualTimeEndpoints
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapGet("/orders/{id:guid}/actual-time/own", Read);
        routes.MapPost("/orders/{id:guid}/actual-time/own", Record);
        routes.MapPost("/orders/{id:guid}/actual-time/own/{entryId:guid}/corrections", Correct);
        routes.MapGet("/orders/{id:guid}/actual-time/own/{entryId:guid}/history", History);
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    private static async Task Context(WorkshopDbContext db, WorkshopGrant member, CancellationToken ct)
    {
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.workshop_actor_membership_id',{member.MembershipId.ToString()},true)", ct);
    }
    private static async Task<(WorkshopGrant Member, WorkOrder Order)?> Find(Guid id, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        var member = await access.ResolveMembership(Subject(user), ct);
        if (member is null) return null;
        WorkOrder? order;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await Context(db, member, ct);
            order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            await tx.CommitAsync(ct);
        }
        if (order is null || await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null) return null;
        return (member, order);
    }
    private static async Task<int> Revision(WorkshopDbContext db, Guid id, CancellationToken ct) =>
        await db.Database.SqlQuery<int>($"SELECT \"Revision\" AS \"Value\" FROM workshop.own_actual_time_streams WHERE \"OrderId\"={id}").SingleOrDefaultAsync(ct);
    private static async Task<IResult> Read(Guid id, int? limit, Guid? after, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (limit is < 1 or > 50 || after == Guid.Empty) return Results.BadRequest();
        var found = await Find(id, user, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.read-own", false, ct) is null) return Results.StatusCode(403);
        // Authorization never nests another pooled connection inside the Workshop transaction.
        var canWrite = await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.write-own", true, ct) is not null;
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await Context(db, member, ct);
        var revision = await Revision(db, id, ct);
        var closed = await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct);
        var rows = await db.Database.SqlQuery<TimeRow>($"""
            SELECT e."Id" AS "EntryId",e."WorkingGroupId",v."Version",v."WorkDate",v."DurationSeconds",v."Note",v."RecordedAt"
            FROM workshop.own_actual_time_entries e JOIN workshop.own_actual_time_versions v ON v."EntryId"=e."Id"
            WHERE e."OrderId"={id} AND ({after}::uuid IS NULL OR e."Id">{after})
            AND NOT EXISTS (SELECT 1 FROM workshop.own_actual_time_versions n WHERE n."EntryId"=v."EntryId" AND n."Version">v."Version")
            ORDER BY e."Id" LIMIT {(limit ?? 20) + 1}
            """).ToListAsync(ct);
        await tx.CommitAsync(ct);
        var hasMore = rows.Count > (limit ?? 20); if (hasMore) rows.RemoveAt(rows.Count - 1);
        return Results.Ok(new OwnActualTimePage(id, revision, closed, canWrite && !closed, rows.Select(x => x.Contract()).ToArray(), hasMore ? rows[^1].EntryId : null));
    }
    private sealed class TimeRow
    {
        public Guid EntryId { get; set; }
        public Guid WorkingGroupId { get; set; }
        public int Version { get; set; }
        public DateOnly WorkDate { get; set; }
        public int DurationSeconds { get; set; }
        public string Note { get; set; } = "";
        public DateTimeOffset RecordedAt { get; set; }
        internal OwnActualTimeEntry Contract() => new(EntryId, WorkingGroupId, Version, WorkDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), DurationSeconds, Note, RecordedAt);
    }
    private static bool ValidText(string? text) => text is not null && text.Length <= 500 && !text.Any(char.IsControl);
    private sealed class EntryIdentity
    {
        public Guid Id { get; set; }
        public Guid WorkingGroupId { get; set; }
        public Guid InternalIdentityId { get; set; }
    }
    private static Task<EntryIdentity?> Entry(WorkshopDbContext db, Guid id, Guid entry, CancellationToken ct) =>
        db.Database.SqlQuery<EntryIdentity>($"SELECT \"Id\",\"WorkingGroupId\",\"InternalIdentityId\" FROM workshop.own_actual_time_entries WHERE \"OrderId\"={id} AND \"Id\"={entry}").SingleOrDefaultAsync(ct);
    private sealed class VersionRow
    {
        public int Version { get; set; }
        public DateOnly WorkDate { get; set; }
        public int DurationSeconds { get; set; }
        public string Note { get; set; } = "";
        public string? CorrectionNote { get; set; }
        public Guid InternalIdentityId { get; set; }
        public Guid MembershipId { get; set; }
        public Guid CommandId { get; set; }
        public int OwnRevision { get; set; }
        public DateTimeOffset RecordedAt { get; set; }
        internal OwnActualTimeVersion Contract() => new(Version, WorkDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture), DurationSeconds, Note, CorrectionNote, InternalIdentityId, MembershipId, CommandId, OwnRevision, RecordedAt);
    }
    private static async Task<IResult> History(Guid id, Guid entryId, int? limit, int? afterVersion, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (limit is < 1 or > 50 || afterVersion is < 0 || entryId == Guid.Empty) return Results.BadRequest();
        var found = await Find(id, user, access, db, ct); if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.read-own", false, ct) is null) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await Context(db, member, ct);
        var entry = await Entry(db, id, entryId, ct); if (entry is null) return Results.NotFound();
        var rows = await db.Database.SqlQuery<VersionRow>($"SELECT * FROM workshop.own_actual_time_versions WHERE \"OrderId\"={id} AND \"EntryId\"={entryId} AND \"Version\">{afterVersion ?? 0} ORDER BY \"Version\" LIMIT {(limit ?? 20) + 1}").ToListAsync(ct);
        await tx.CommitAsync(ct); var more = rows.Count > (limit ?? 20); if (more) rows.RemoveAt(rows.Count - 1);
        return Results.Ok(new OwnActualTimeHistory(id, entryId, entry.WorkingGroupId, rows.Select(x => x.Contract()).ToArray(), more ? rows[^1].Version : null));
    }
    private static async Task<IResult> Correct(Guid id, Guid entryId, CorrectOwnActualTimeCommand request, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (id == Guid.Empty || entryId == Guid.Empty || request.CommandId == Guid.Empty || request.ExpectedOwnRevision < 0 || request.ExpectedEntryVersion <= 0
            || request.DurationSeconds <= 0 || !ValidText(request.Note) || !ValidText(request.CorrectionNote)
            || !DateOnly.TryParseExact(request.WorkDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date)) return Results.BadRequest();
        if (!Guid.TryParse(Subject(user), out var identity) || identity == Guid.Empty) return Results.NotFound();
        var found = await Find(id, user, access, db, ct); if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.write-own", false, ct) is null) return Results.StatusCode(403);
        var canWrite = await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.write-own", true, ct) is not null;
        await using var tx = await db.Database.BeginTransactionAsync(ct); await Context(db, member, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()},0))", ct);
        var entry = await Entry(db, id, entryId, ct); if (entry is null || entry.InternalIdentityId != identity) return Results.NotFound();
        var replay = await Replay(db, id, entryId, identity, request.CommandId, request, ct); if (replay is not null) return replay;
        if (!canWrite) return Results.StatusCode(403);
        if (await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct)) return CommercialEndpoints.Closed();
        var revision = await Revision(db, id, ct); if (revision != request.ExpectedOwnRevision) return Conflict("actual_time_revision_changed");
        var old = await db.Database.SqlQuery<VersionRow>($"SELECT * FROM workshop.own_actual_time_versions WHERE \"EntryId\"={entryId} ORDER BY \"Version\" DESC LIMIT 1").SingleAsync(ct);
        if (old.Version != request.ExpectedEntryVersion) return Conflict("actual_time_entry_changed");
        if (revision == int.MaxValue || old.Version == int.MaxValue) return Conflict("actual_time_revision_limit");
        if (old.WorkDate == date && old.DurationSeconds == request.DurationSeconds && old.Note == request.Note) return Conflict("actual_time_no_change");
        var versionInserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_versions ("EntryId","Version","TenantId","OrderId","MembershipId","InternalIdentityId","WorkDate","DurationSeconds","Note","CorrectionNote","CommandId","OwnRevision")
            VALUES ({entryId},{old.Version + 1},{member.TenantId},{id},{member.MembershipId},{identity},CAST({request.WorkDate} AS date),{request.DurationSeconds},{request.Note},{request.CorrectionNote},{request.CommandId},{revision + 1})
            ON CONFLICT DO NOTHING
            """, ct);
        if (versionInserted == 0) return Conflict("actual_time_command_conflict");
        await db.Database.ExecuteSqlInterpolatedAsync($"UPDATE workshop.own_actual_time_streams SET \"Revision\"={revision + 1} WHERE \"OrderId\"={id}", ct);
        var receipt = new OwnActualTimeReceipt(request.CommandId, id, entryId, revision + 1, old.Version + 1, "Corrected");
        var stored = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_commands ("CommandId","TenantId","OrderId","MembershipId","InternalIdentityId","EntryId","Canonical","Receipt")
            VALUES ({request.CommandId},{member.TenantId},{id},{member.MembershipId},{identity},{entryId},CAST({JsonSerializer.Serialize(request, Json)} AS jsonb),CAST({JsonSerializer.Serialize(receipt, Json)} AS jsonb)) ON CONFLICT DO NOTHING
            """, ct);
        if (stored == 0) return Conflict("actual_time_command_conflict");
        await tx.CommitAsync(ct); return Results.Ok(receipt);
    }
    private static IResult Conflict(string code) => Results.Conflict(new { code });
    private sealed class CommandRow
    {
        public Guid OrderId { get; set; }
        public Guid EntryId { get; set; }
        public Guid InternalIdentityId { get; set; }
        public string Canonical { get; set; } = "";
        public string Receipt { get; set; } = "";
    }
    private static async Task<IResult?> Replay(WorkshopDbContext db, Guid order, Guid entry, Guid identity, Guid command, object request, CancellationToken ct)
    {
        var prior = await db.Database.SqlQuery<CommandRow>($"SELECT * FROM workshop.own_actual_time_commands WHERE \"CommandId\"={command}").SingleOrDefaultAsync(ct);
        if (prior is null) return null;
        return prior.OrderId == order && prior.EntryId == entry && prior.InternalIdentityId == identity
            && JsonNode.DeepEquals(JsonNode.Parse(prior.Canonical), JsonSerializer.SerializeToNode(request, Json))
            ? Results.Ok(JsonSerializer.Deserialize<OwnActualTimeReceipt>(prior.Receipt, Json)) : Conflict("actual_time_command_conflict");
    }
    private static async Task<IResult> Record(Guid id, RecordOwnActualTimeCommand request, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (id == Guid.Empty || request.CommandId == Guid.Empty || request.EntryId == Guid.Empty || request.WorkingGroupId == Guid.Empty
            || request.ExpectedOwnRevision < 0 || request.ExpectedGroupVersion <= 0 || request.DurationSeconds <= 0 || !ValidText(request.Note)
            || !DateOnly.TryParseExact(request.WorkDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var date)) return Results.BadRequest();
        if (!Guid.TryParse(Subject(user), out var identity) || identity == Guid.Empty) return Results.NotFound();
        var found = await Find(id, user, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        if (await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.write-own", false, ct) is null) return Results.StatusCode(403);
        var canWrite = await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.actual-time.write-own", true, ct) is not null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await Context(db, member, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()},0))", ct);
        var replay = await Replay(db, id, request.EntryId, identity, request.CommandId, request, ct); if (replay is not null) return replay;
        if (!canWrite) return Results.StatusCode(403);
        if (await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct)) return CommercialEndpoints.Closed();
        var revision = await Revision(db, id, ct);
        if (revision != request.ExpectedOwnRevision) return Conflict("actual_time_revision_changed");
        if (revision == int.MaxValue) return Conflict("actual_time_revision_limit");
        var group = await db.WorkingGroups.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.WorkingGroupId && x.OrderId == id && x.State == "Active", ct);
        if (group is null) return Results.NotFound();
        if (group.Version != request.ExpectedGroupVersion) return Conflict("actual_time_group_changed");
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_streams ("TenantId","OrderId","MembershipId","Revision") VALUES ({member.TenantId},{id},{member.MembershipId},0) ON CONFLICT DO NOTHING
            """, ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.actual_time_group_references ("TenantId","OrderId","WorkingGroupId") VALUES ({member.TenantId},{id},{group.Id}) ON CONFLICT DO NOTHING
            """, ct);
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_entries ("Id","TenantId","OrderId","MembershipId","InternalIdentityId","WorkingGroupId")
            VALUES ({request.EntryId},{member.TenantId},{id},{member.MembershipId},{identity},{group.Id}) ON CONFLICT DO NOTHING
            """, ct);
        if (inserted == 0) return Conflict("actual_time_identity_conflict");
        var versionInserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_versions ("EntryId","Version","TenantId","OrderId","MembershipId","InternalIdentityId","WorkDate","DurationSeconds","Note","CommandId","OwnRevision")
            VALUES ({request.EntryId},1,{member.TenantId},{id},{member.MembershipId},{identity},CAST({request.WorkDate} AS date),{request.DurationSeconds},{request.Note},{request.CommandId},{revision + 1})
            ON CONFLICT DO NOTHING
            """, ct);
        if (versionInserted == 0) return Conflict("actual_time_command_conflict");
        await db.Database.ExecuteSqlInterpolatedAsync($"UPDATE workshop.own_actual_time_streams SET \"Revision\"={revision + 1} WHERE \"OrderId\"={id}", ct);
        var receipt = new OwnActualTimeReceipt(request.CommandId, id, request.EntryId, revision + 1, 1, "Created");
        var stored = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.own_actual_time_commands ("CommandId","TenantId","OrderId","MembershipId","InternalIdentityId","EntryId","Canonical","Receipt")
            VALUES ({request.CommandId},{member.TenantId},{id},{member.MembershipId},{identity},{request.EntryId},CAST({JsonSerializer.Serialize(request, Json)} AS jsonb),CAST({JsonSerializer.Serialize(receipt, Json)} AS jsonb)) ON CONFLICT DO NOTHING
            """, ct);
        if (stored == 0) return Conflict("actual_time_command_conflict");
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/workshop/orders/{id}/actual-time/own", receipt);
    }
}
