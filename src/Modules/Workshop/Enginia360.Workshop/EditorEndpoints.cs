using System.Security.Claims;
using System.Text.Json;
using System.Text.Json.Nodes;
using Enginia360.Catalog.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

// R03.a: order workspace. Workshop owns groups, rows, notes, revision and receipts; one local transaction per command.
internal static class EditorEndpoints
{
    // Server-owned workspace contract version (not the document, line-policy or catalog version).
    internal const int StructurePolicyVersion = 1;
    internal const int MaxActiveLines = 1000, MaxActiveGroups = 100, MaxActiveNotes = 1000, MaxDescription = 500;
    // Smallest downstream bound: numeric(18,6) of the administrative request and invoice snapshot.
    private const decimal StoredLimit = 999999999999.999999m;
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    private static readonly string[] Commands = ["AddGroup", "RenameGroup", "RemoveEmptyGroup", "AddCommercialLine", "AddNote", "EditCommercialLine", "EditNote", "RemoveLine"];

    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapGet("/orders", List);
        routes.MapGet("/orders/{id:guid}/line-policy", ReadPolicy);
        routes.MapGet("/orders/{id:guid}/editor", ReadEditor);
        routes.MapPost("/orders/{id:guid}/editor/commands", Command);
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";

    internal static bool ExceedsSummaryLimit(IReadOnlyList<CommercialLine> active)
    {
        var net = active.Sum(x => x.NetAmount);
        var tax = active.GroupBy(x => new { x.PayerId, x.TaxRate }).Sum(g => CommercialEndpoints.RoundAmount(g.Sum(x => x.NetAmount) * g.Key.TaxRate / 100m));
        return net > StoredLimit || tax > StoredLimit || net + tax > StoredLimit;
    }
    internal static IResult SummaryLimit() => Results.Conflict(new { code = "commercial_summary_limit",
        message = "Il totale supera il limite tecnico di importo. Nessuna modifica registrata." });
    internal static async Task<bool> Advance(WorkshopDbContext db, Guid tenant, Guid orderId, int expected, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE workshop.orders SET "CommercialRevision"="CommercialRevision"+1
            WHERE "Id"={orderId} AND "TenantId"={tenant} AND "CommercialRevision"={expected}
            """, ct) == 1;
    internal static Task History(WorkshopDbContext db, string kind, Guid target, int version, Guid tenant, Guid orderId, int revision,
        string operation, Guid? command, object snapshot, CancellationToken ct) =>
        db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.workspace_history ("TargetKind","TargetId","Version","TenantId","OrderId","Revision","Operation","CommandId","Snapshot")
            VALUES ({kind},{target},{version},{tenant},{orderId},{revision},{operation},{command},CAST({JsonSerializer.Serialize(snapshot, Json)} AS jsonb))
            """, ct);
    internal static object LineSnapshot(CommercialLine x) => new { x.Id, x.Kind, x.WorkingGroupId, x.CatalogItemId, x.CatalogVersion, x.CatalogLabel,
        quantity = CommercialEndpoints.Value(x.Quantity), unitPrice = CommercialEndpoints.Value(x.UnitPrice), discountPercent = CommercialEndpoints.Value(x.DiscountPercent),
        netAmount = CommercialEndpoints.Money(x.NetAmount), x.Description, x.State, x.Version };

    private static async Task<(WorkshopGrant Member, WorkOrder Order)?> Find(Guid id, string subject, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        var order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
        await tx.CommitAsync(ct);
        return order is null ? null : (member, order);
    }
    private static LinePolicyContract PolicyContract(WorkOrder order, LinePolicy? policy) => new(order.Id, policy is null ? "line_policy_missing" : "ready",
        order.DocumentTypeId, order.ConfigurationVersion, policy?.Version, policy?.Policy, policy?.MultipleWorkingGroups ?? false, StructurePolicyVersion,
        new WorkspaceLimits(MaxActiveLines, MaxActiveGroups, MaxActiveNotes, MaxDescription), Commands);
    private static Task<LinePolicy?> LatestPolicy(WorkshopDbContext db, WorkOrder order, CancellationToken ct) =>
        db.LinePolicies.AsNoTracking().Where(x => x.TenantId == order.TenantId && x.LegalEntityId == order.LegalEntityId && x.DocumentTypeId == order.DocumentTypeId)
            .OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);

    private static async Task<IResult> ReadPolicy(Guid id, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        var found = await Find(id, Subject(user), access, db, ct);
        if (found is null || await access.Authorize(Subject(user), found.Value.Order.LegalEntityId, found.Value.Order.SiteId, "workshop.orders.read", false, ct) is null)
            return Results.NotFound();
        LinePolicy? policy;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, found.Value.Member.TenantId, ct);
            policy = await LatestPolicy(db, found.Value.Order, ct);
            await tx.CommitAsync(ct);
        }
        return Results.Ok(PolicyContract(found.Value.Order, policy));
    }

    private static async Task<IResult> List(Guid legalEntityId, Guid siteId, int? limit, Guid? after, ClaimsPrincipal user,
        IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        if (legalEntityId == Guid.Empty || siteId == Guid.Empty || limit is < 1 or > 50) return Results.BadRequest();
        var grant = await access.Authorize(Subject(user), legalEntityId, siteId, "workshop.orders.read", false, ct);
        if (grant is null) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, grant.TenantId, ct);
        var rows = await db.Orders.AsNoTracking().Where(x => x.TenantId == grant.TenantId && x.LegalEntityId == legalEntityId && x.SiteId == siteId
                && (after == null || x.Id.CompareTo(after.Value) > 0))
            .OrderBy(x => x.Id).Take(limit ?? 20)
            .Select(x => new WorkshopOrderListItem(x.Id, x.DocumentTypeId, x.ConfigurationVersion, x.PayerId, x.VehicleId, x.CommercialRevision,
                db.TechnicalClosures.Any(c => c.OrderId == x.Id))).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return Results.Ok(rows);
    }

    private static async Task<IResult> ReadEditor(Guid id, ClaimsPrincipal user, IWorkshopAccess access, WorkshopDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        WorkOrder? order; LinePolicy? policy; List<WorkingGroup> groups; List<CommercialLine> lines; List<OrderNote> notes; bool closed;
        // One RepeatableRead snapshot: header, policy, rows and revision come from the same commit.
        await using (var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct))
        {
            await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
            order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == id, ct);
            if (order is null) return Results.NotFound();
            policy = await LatestPolicy(db, order, ct);
            groups = await db.WorkingGroups.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").OrderBy(x => x.CreatedRevision).ToListAsync(ct);
            lines = await db.Lines.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").OrderBy(x => x.ExpectedRevision).ToListAsync(ct);
            notes = await db.Notes.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").OrderBy(x => x.CreatedRevision).ToListAsync(ct);
            closed = await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct);
            await tx.CommitAsync(ct);
        }
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null) return Results.NotFound();
        async Task<bool> Can(string action) => !closed && await access.Authorize(subject, order.LegalEntityId, order.SiteId, action, true, ct) is not null;
        var capabilities = new EditorCapabilities(closed, await Can("workshop.lines.add"), await Can("workshop.lines.edit"), await Can("workshop.lines.remove"),
            await Can("workshop.notes.write"), await Can("workshop.groups.write"), await Can("workshop.lines.edit") || await Can("workshop.lines.remove"),
            "Quantità, articolo, lavorazione e rimozione solo senza impegni logistici attivi; controllo server al salvataggio.");
        var rows = lines.Select(x => new EditorRow(x.Id, x.Kind, x.WorkingGroupId, x.ExpectedRevision, x.Version, x.Description, x.ToContract()))
            .Concat(notes.Select(x => new EditorRow(x.Id, "Note", x.WorkingGroupId, x.CreatedRevision, x.Version, x.Description, null)))
            .OrderBy(x => x.Sequence).ToArray();
        return Results.Ok(new WorkshopEditorContract(order.ToContract(), order.CommercialRevision, PolicyContract(order, policy),
            groups.Select(x => new WorkingGroupContract(x.Id, x.Title, x.Version, x.CreatedRevision)).ToArray(), rows,
            CommercialEndpoints.Summarize(order, lines, order.CommercialRevision), capabilities));
    }

    private sealed record Shape(string[] Required, string[] Optional, string Action);
    private static readonly Dictionary<string, Shape> Shapes = new()
    {
        ["AddGroup"] = new(["groupId", "title"], [], "workshop.groups.write"),
        ["RenameGroup"] = new(["groupId", "title"], [], "workshop.groups.write"),
        ["RemoveEmptyGroup"] = new(["groupId"], [], "workshop.groups.write"),
        ["AddCommercialLine"] = new(["lineId", "groupId", "catalogItemId", "catalogVersion", "quantity", "unitPrice", "discountPercent"], ["description"], "workshop.lines.add"),
        ["AddNote"] = new(["lineId", "groupId", "description"], [], "workshop.notes.write"),
        ["EditCommercialLine"] = new(["lineId"], ["quantity", "unitPrice", "discountPercent", "description", "groupId", "catalogItemId", "catalogVersion"], "workshop.lines.edit"),
        ["EditNote"] = new(["lineId", "description"], [], "workshop.notes.write"),
        ["RemoveLine"] = new(["lineId"], [], ""),
    };
    private static bool ValidText(string? text, int min) => text is not null && text.Length <= MaxDescription && text.Trim().Length >= min && !text.Any(char.IsControl);

    private static async Task<IResult> Command(Guid id, EditorCommand request, ClaimsPrincipal user, IWorkshopAccess access,
        IWorkshopCatalog catalog, WorkshopDbContext db, CancellationToken ct)
    {
        if (id == Guid.Empty || request.CommandId == Guid.Empty || request.ExpectedRevision < 0 || request.ExpectedStructurePolicyVersion <= 0
            || request.ExpectedLinePolicyVersion is not > 0 || request.Type is null || !Shapes.TryGetValue(request.Type, out var shape)) return Results.BadRequest();
        var present = new Dictionary<string, bool>
        {
            ["groupId"] = request.GroupId is not null, ["lineId"] = request.LineId is not null, ["title"] = request.Title is not null,
            ["description"] = request.Description is not null, ["catalogItemId"] = request.CatalogItemId is not null, ["catalogVersion"] = request.CatalogVersion is not null,
            ["quantity"] = request.Quantity is not null, ["unitPrice"] = request.UnitPrice is not null, ["discountPercent"] = request.DiscountPercent is not null,
        };
        if (shape.Required.Any(x => !present[x]) || present.Any(p => p.Value && !shape.Required.Contains(p.Key) && !shape.Optional.Contains(p.Key))) return Results.BadRequest();
        if (request.GroupId == Guid.Empty || request.LineId == Guid.Empty || request.CatalogItemId == Guid.Empty || request.CatalogVersion <= 0) return Results.BadRequest();
        if (request.Title is not null && !ValidText(request.Title, 1) || request.Title is { Length: > 100 }) return Results.BadRequest();
        if (request.Description is not null && !ValidText(request.Description, request.Type is "AddNote" or "EditNote" ? 1 : 0)) return Results.BadRequest();
        decimal quantity = 0, price = 0, discount = 0;
        if (request.Quantity is not null && (!CommercialEndpoints.Number(request.Quantity, 6, out quantity) || quantity <= 0)) return Results.BadRequest();
        if (request.UnitPrice is not null && !CommercialEndpoints.Number(request.UnitPrice, 6, out price)) return Results.BadRequest();
        if (request.DiscountPercent is not null && (!CommercialEndpoints.Number(request.DiscountPercent, 2, out discount) || discount > 100)) return Results.BadRequest();
        if (request.Type == "EditCommercialLine" && (!shape.Optional.Any(x => present[x])
            || (request.CatalogItemId is null) != (request.CatalogVersion is null))) return Results.BadRequest();
        var canonical = JsonSerializer.Serialize(new
        {
            type = request.Type, expectedRevision = request.ExpectedRevision, linePolicy = request.ExpectedLinePolicyVersion,
            structurePolicy = request.ExpectedStructurePolicyVersion, request.GroupId, request.LineId, title = request.Title?.Trim(), request.Description,
            request.CatalogItemId, request.CatalogVersion, quantity = request.Quantity is null ? null : CommercialEndpoints.Value(quantity),
            unitPrice = request.UnitPrice is null ? null : CommercialEndpoints.Value(price), discount = request.DiscountPercent is null ? null : CommercialEndpoints.Value(discount),
        }, Json);

        var subject = Subject(user);
        var found = await Find(id, subject, access, db, ct);
        if (found is null) return Results.NotFound();
        var (member, order) = found.Value;
        var action = shape.Action;
        if (request.Type == "RemoveLine")
        {
            // The exact action follows the saved target kind: removing a Note is a Note action, removing a row is a row-removal action.
            string? kind;
            await using (var lookup = await db.Database.BeginTransactionAsync(ct))
            {
                await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
                kind = await db.Notes.AnyAsync(x => x.OrderId == id && x.Id == request.LineId, ct) ? "Note"
                    : await db.Lines.AnyAsync(x => x.OrderId == id && x.Id == request.LineId, ct) ? "Line" : null;
                await lookup.CommitAsync(ct);
            }
            if (kind == "Note") action = "workshop.notes.write";
            else if (kind == "Line") action = "workshop.lines.remove";
            else if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.lines.remove", true, ct) is null
                && await access.Authorize(subject, order.LegalEntityId, order.SiteId, "workshop.notes.write", true, ct) is null) return Results.StatusCode(403);
            else return Results.NotFound(new { code = "line_not_found" });
        }
        if (await access.Authorize(subject, order.LegalEntityId, order.SiteId, action, true, ct) is null) return Results.StatusCode(403);
        CatalogChoice? item = null;
        if (request.Type == "AddCommercialLine" || request.Type == "EditCommercialLine" && request.CatalogItemId is not null) item = await catalog.Find(member.TenantId, request.CatalogItemId!.Value, ct);

        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
        // Same order lock as legacy additions, closure, installation and billing allocation.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()}, 0))", ct);
        var replay = await db.EditorCommands.AsNoTracking().SingleOrDefaultAsync(x => x.CommandId == request.CommandId, ct);
        if (replay is not null)
            return replay.OrderId == id && replay.Type == request.Type && JsonNode.DeepEquals(JsonNode.Parse(replay.Canonical), JsonNode.Parse(canonical))
                ? Results.Ok(replay.Receipt()) : Results.Conflict();
        if (await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct)) return CommercialEndpoints.Closed();
        var revision = await db.Orders.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.Id == id).Select(x => x.CommercialRevision).SingleAsync(ct);
        var policy = await LatestPolicy(db, order, ct);
        if (policy is null) return Results.Conflict(new { code = "line_policy_missing", message = "Policy righe non configurata per il tipo documento. Nessuna modifica registrata." });
        if (request.ExpectedStructurePolicyVersion != StructurePolicyVersion)
            return Results.Conflict(new { code = "structure_policy_changed", structurePolicyVersion = StructurePolicyVersion, message = "Struttura editor cambiata: rileggi." });
        if (request.ExpectedLinePolicyVersion != policy.Version || policy.Policy != "Case001")
            return Results.Conflict(new { code = "line_policy_changed", currentLinePolicyVersion = policy.Version, message = "Policy righe cambiata: rileggi." });
        if (request.ExpectedRevision != revision)
            return Results.Conflict(new { code = "revision_changed", revision, message = "Valori della commessa cambiati: rileggi." });
        if (revision == int.MaxValue) return Results.Conflict(new { code = "revision_limit", message = "Limite revisioni raggiunto." });
        var next = revision + 1;
        string resultKind; Guid target;

        async Task<WorkingGroup?> ActiveGroup(Guid groupId) =>
            await db.WorkingGroups.AsNoTracking().SingleOrDefaultAsync(x => x.OrderId == id && x.Id == groupId && x.State == "Active", ct);
        IResult NotFound(string code) => Results.NotFound(new { code });
        IResult NoChange() => Results.Conflict(new { code = "no_change", message = "Nessuna differenza da registrare." });
        var activeLines = await db.Lines.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").ToListAsync(ct);

        switch (request.Type)
        {
            case "AddGroup":
            {
                var groups = await db.WorkingGroups.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").CountAsync(ct);
                if (groups >= MaxActiveGroups) return Results.Conflict(new { code = "workspace_limit" });
                if (groups > 0 && !policy.MultipleWorkingGroups) return Results.Conflict(new { code = "multiple_groups_not_enabled", message = "Il profilo documento ammette una sola lavorazione." });
                var title = request.Title!.Trim(); target = request.GroupId!.Value; resultKind = "Created";
                var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.working_groups ("Id","TenantId","OrderId","Title","State","Version","CreatedRevision")
                    VALUES ({target},{member.TenantId},{id},{title},'Active',1,{next}) ON CONFLICT DO NOTHING
                    """, ct);
                if (inserted == 0) return Results.Conflict();
                await History(db, "Group", target, 1, member.TenantId, id, next, "Created", request.CommandId, new { id = target, title, state = "Active", version = 1 }, ct);
                break;
            }
            case "RenameGroup":
            {
                var group = await ActiveGroup(request.GroupId!.Value);
                if (group is null) return NotFound("group_not_found");
                var title = request.Title!.Trim();
                if (title == group.Title) return NoChange();
                target = group.Id; resultKind = "Updated";
                await db.Database.ExecuteSqlInterpolatedAsync($"""UPDATE workshop.working_groups SET "Title"={title},"Version"={group.Version + 1} WHERE "Id"={target}""", ct);
                await History(db, "Group", target, group.Version + 1, member.TenantId, id, next, "Updated", request.CommandId, new { id = target, title, state = "Active", version = group.Version + 1 }, ct);
                break;
            }
            case "RemoveEmptyGroup":
            {
                var group = await ActiveGroup(request.GroupId!.Value);
                if (group is null) return NotFound("group_not_found");
                if (activeLines.Any(x => x.WorkingGroupId == group.Id) || await db.Notes.AnyAsync(x => x.WorkingGroupId == group.Id && x.State == "Active", ct))
                    return Results.Conflict(new { code = "group_not_empty", message = "La lavorazione contiene righe o note: nessuna cascata." });
                target = group.Id; resultKind = "Removed";
                await db.Database.ExecuteSqlInterpolatedAsync($"""UPDATE workshop.working_groups SET "State"='Removed',"Version"={group.Version + 1} WHERE "Id"={target}""", ct);
                await History(db, "Group", target, group.Version + 1, member.TenantId, id, next, "Removed", request.CommandId, new { id = target, title = group.Title, state = "Removed", version = group.Version + 1 }, ct);
                break;
            }
            case "AddCommercialLine":
            {
                if (await ActiveGroup(request.GroupId!.Value) is null) return NotFound("group_not_found");
                if (item is null) return NotFound("catalog_item_not_found");
                if (item.Version != request.CatalogVersion) return Results.Conflict(new { code = "catalog_version_changed" });
                if (item.Kind is not ("Service" or "Part")) return Results.BadRequest();
                if (activeLines.Count >= MaxActiveLines) return Results.Conflict(new { code = "workspace_limit" });
                target = request.LineId!.Value; resultKind = "Created";
                if (await db.Notes.AnyAsync(x => x.Id == target, ct)) return Results.Conflict();
                var line = new CommercialLine
                {
                    Id = target, TenantId = member.TenantId, OrderId = id, CatalogItemId = item.Id, CatalogVersion = item.Version, CatalogLabel = item.Label, Kind = item.Kind,
                    Quantity = quantity, UnitPrice = price, DiscountPercent = discount, NetAmount = CommercialEndpoints.RoundAmount(quantity * price * (1 - discount / 100m)),
                    TaxRate = 22m, PayerId = order.PayerId, WorkingGroupId = request.GroupId.Value, ConfigurationVersion = policy.Version, ExpectedRevision = revision,
                    Description = string.IsNullOrWhiteSpace(request.Description) ? null : request.Description, State = "Active", Version = 1,
                };
                var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.commercial_lines ("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice",
                        "DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision","Description","State","Version")
                    VALUES ({line.Id},{line.TenantId},{line.OrderId},{line.CatalogItemId},{line.CatalogVersion},{line.CatalogLabel},{line.Kind},{line.Quantity},{line.UnitPrice},
                        {line.DiscountPercent},{line.NetAmount},{line.TaxRate},{line.PayerId},{line.WorkingGroupId},{line.ConfigurationVersion},{line.ExpectedRevision},{line.Description},'Active',1)
                    ON CONFLICT ("Id") DO NOTHING
                    """, ct);
                if (inserted == 0) return Results.Conflict();
                activeLines.Add(line);
                await History(db, "Line", target, 1, member.TenantId, id, next, "Created", request.CommandId, LineSnapshot(line), ct);
                break;
            }
            case "EditCommercialLine":
            {
                var line = activeLines.SingleOrDefault(x => x.Id == request.LineId);
                if (line is null) return NotFound("line_not_found");
                if (request.GroupId is not null && await ActiveGroup(request.GroupId.Value) is null) return NotFound("group_not_found");
                if (request.CatalogItemId is not null)
                {
                    if (item is null) return NotFound("catalog_item_not_found");
                    if (item.Version != request.CatalogVersion) return Results.Conflict(new { code = "catalog_version_changed" });
                    if (item.Kind != line.Kind) return Results.BadRequest();
                }
                var group = request.GroupId ?? line.WorkingGroupId;
                var catalogId = item?.Id ?? line.CatalogItemId;
                var catalogVersion = item?.Version ?? line.CatalogVersion;
                var catalogLabel = item?.Label ?? line.CatalogLabel;
                var structural = request.Quantity is not null && quantity != line.Quantity || group != line.WorkingGroupId
                    || catalogId != line.CatalogItemId || catalogVersion != line.CatalogVersion || catalogLabel != line.CatalogLabel;
                if (line.Kind == "Part" && structural)
                {
                    var lineLock = $"inventory:line:{member.TenantId}:{line.Id}";
                    await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock}, 0))", ct);
                    if (await db.Database.SqlQuery<bool>($"SELECT inventory.line_has_commitments({member.TenantId},{line.Id}) AS \"Value\"").SingleAsync(ct))
                        return Results.Conflict(new { code = "active_material_commitments", message = "Impegni logistici attivi: sono modificabili solo prezzo, sconto e descrizione." });
                }
                var q = request.Quantity is null ? line.Quantity : quantity;
                var p = request.UnitPrice is null ? line.UnitPrice : price;
                var d = request.DiscountPercent is null ? line.DiscountPercent : discount;
                var text = request.Description is null ? line.Description : string.IsNullOrWhiteSpace(request.Description) ? null : request.Description;
                if (!structural && q == line.Quantity && p == line.UnitPrice && d == line.DiscountPercent && text == line.Description) return NoChange();
                var netAmount = CommercialEndpoints.RoundAmount(q * p * (1 - d / 100m));
                target = line.Id; resultKind = "Updated";
                await db.Database.ExecuteSqlInterpolatedAsync($"""
                    UPDATE workshop.commercial_lines SET "Quantity"={q},"UnitPrice"={p},"DiscountPercent"={d},"NetAmount"={netAmount},"Description"={text},"Version"={line.Version + 1},
                        "WorkingGroupId"={group},"CatalogItemId"={catalogId},"CatalogVersion"={catalogVersion},"CatalogLabel"={catalogLabel}
                    WHERE "Id"={target}
                    """, ct);
                line.WorkingGroupId = group; line.CatalogItemId = catalogId; line.CatalogVersion = catalogVersion; line.CatalogLabel = catalogLabel;
                line.Quantity = q; line.UnitPrice = p; line.DiscountPercent = d; line.NetAmount = netAmount; line.Description = text; line.Version++;
                await History(db, "Line", target, line.Version, member.TenantId, id, next, "Updated", request.CommandId, LineSnapshot(line), ct);
                break;
            }
            case "AddNote":
            {
                if (await ActiveGroup(request.GroupId!.Value) is null) return NotFound("group_not_found");
                if (await db.Notes.CountAsync(x => x.OrderId == id && x.State == "Active", ct) >= MaxActiveNotes) return Results.Conflict(new { code = "workspace_limit" });
                target = request.LineId!.Value; resultKind = "Created";
                if (await db.Lines.AnyAsync(x => x.Id == target, ct)) return Results.Conflict();
                var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.order_notes ("Id","TenantId","OrderId","WorkingGroupId","Description","State","Version","CreatedRevision")
                    VALUES ({target},{member.TenantId},{id},{request.GroupId.Value},{request.Description},'Active',1,{revision}) ON CONFLICT DO NOTHING
                    """, ct);
                if (inserted == 0) return Results.Conflict();
                await History(db, "Note", target, 1, member.TenantId, id, next, "Created", request.CommandId,
                    new { id = target, groupId = request.GroupId, description = request.Description, state = "Active", version = 1 }, ct);
                break;
            }
            case "EditNote":
            {
                var note = await db.Notes.AsNoTracking().SingleOrDefaultAsync(x => x.OrderId == id && x.Id == request.LineId && x.State == "Active", ct);
                if (note is null) return NotFound("line_not_found");
                if (note.Description == request.Description) return NoChange();
                target = note.Id; resultKind = "Updated";
                await db.Database.ExecuteSqlInterpolatedAsync($"""UPDATE workshop.order_notes SET "Description"={request.Description},"Version"={note.Version + 1} WHERE "Id"={target}""", ct);
                await History(db, "Note", target, note.Version + 1, member.TenantId, id, next, "Updated", request.CommandId,
                    new { id = target, groupId = note.WorkingGroupId, description = request.Description, state = "Active", version = note.Version + 1 }, ct);
                break;
            }
            default: // RemoveLine
            {
                var line = activeLines.SingleOrDefault(x => x.Id == request.LineId);
                var note = line is null ? await db.Notes.AsNoTracking().SingleOrDefaultAsync(x => x.OrderId == id && x.Id == request.LineId && x.State == "Active", ct) : null;
                if (line is null && note is null) return NotFound("line_not_found");
                target = request.LineId!.Value; resultKind = "Removed";
                if (line is not null)
                {
                    if (line.Kind == "Part")
                    {
                        var lineLock = $"inventory:line:{member.TenantId}:{line.Id}";
                        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock}, 0))", ct);
                        if (await db.Database.SqlQuery<bool>($"SELECT inventory.line_has_commitments({member.TenantId},{line.Id}) AS \"Value\"").SingleAsync(ct))
                            return Results.Conflict(new { code = "active_material_commitments", message = "Impegni logistici attivi: rimozione non consentita." });
                    }
                    await db.Database.ExecuteSqlInterpolatedAsync($"""UPDATE workshop.commercial_lines SET "State"='Removed',"Version"={line.Version + 1} WHERE "Id"={target}""", ct);
                    activeLines.Remove(line); line.State = "Removed"; line.Version++;
                    await History(db, "Line", target, line.Version, member.TenantId, id, next, "Removed", request.CommandId, LineSnapshot(line), ct);
                }
                else
                {
                    await db.Database.ExecuteSqlInterpolatedAsync($"""UPDATE workshop.order_notes SET "State"='Removed',"Version"={note!.Version + 1} WHERE "Id"={target}""", ct);
                    await History(db, "Note", target, note.Version + 1, member.TenantId, id, next, "Removed", request.CommandId,
                        new { id = target, groupId = note.WorkingGroupId, description = note.Description, state = "Removed", version = note.Version + 1 }, ct);
                }
                break;
            }
        }
        if (ExceedsSummaryLimit(activeLines)) return SummaryLimit();
        if (!await Advance(db, member.TenantId, id, revision, ct)) return Results.Conflict(new { code = "revision_changed", message = "Valori della commessa cambiati: rileggi." });
        var receipt = new EditorCommandReceipt { CommandId = request.CommandId, TenantId = member.TenantId, OrderId = id, Type = request.Type, Canonical = canonical,
            TargetId = target, InitialRevision = revision, AppliedRevision = next, ResultKind = resultKind, LinePolicyVersion = policy.Version, StructurePolicyVersion = StructurePolicyVersion };
        var stored = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.editor_commands ("CommandId","TenantId","OrderId","Type","Canonical","TargetId","InitialRevision","AppliedRevision","ResultKind","LinePolicyVersion","StructurePolicyVersion")
            VALUES ({receipt.CommandId},{receipt.TenantId},{receipt.OrderId},{receipt.Type},CAST({receipt.Canonical} AS jsonb),{receipt.TargetId},{receipt.InitialRevision},
                {receipt.AppliedRevision},{receipt.ResultKind},{receipt.LinePolicyVersion},{receipt.StructurePolicyVersion}) ON CONFLICT DO NOTHING
            """, ct);
        if (stored == 0) return Results.Conflict(); // Foreign-tenant command collision, no disclosure.
        await tx.CommitAsync(ct);
        return resultKind == "Created" ? Results.Created($"/api/v1/workshop/orders/{id}/editor", receipt.Receipt()) : Results.Ok(receipt.Receipt());
    }
}
