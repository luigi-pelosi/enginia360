using System.Globalization;
using System.Security.Claims;
using System.Text.RegularExpressions;
using Enginia360.Catalog.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal static partial class CommercialEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{id:guid}/lines", Add);
        routes.MapGet("/orders/{id:guid}/commercial-summary", Read);
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    internal static string Value(decimal value) => value.ToString("0.######", CultureInfo.InvariantCulture);
    internal static string Money(decimal value) => value.ToString("0.000000", CultureInfo.InvariantCulture);
    // D67 admits nonnegative values only; AwayFromZero is ROUND_HALF_UP in this domain.
    private static decimal RoundMoney(decimal value) => decimal.Round(value, 6, MidpointRounding.AwayFromZero);
    [GeneratedRegex(@"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex InvariantDecimal();
    internal static bool Number(string? text, int scale, out decimal value)
    {
        // Storage/anti-overflow bound, not a commercial maximum: numeric(12,6).
        // Exact decimal multiplication fits decimal for any capped line count; aggregates are bounded by the summary-limit guard.
        value = 0;
        return text is { Length: > 0 and <= 13 } && InvariantDecimal().IsMatch(text)
            && (!text.Contains('.') || text.Length - text.IndexOf('.') - 1 <= scale)
            && decimal.TryParse(text, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out value);
    }
    private static async Task SetTenant(WorkshopDbContext db, Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    private static async Task<IResult> Add(Guid id, AddCaseLineRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, IWorkshopCatalog catalog, WorkshopDbContext db, CancellationToken ct)
    {
        if (id == Guid.Empty || request.Id == Guid.Empty || request.CatalogItemId == Guid.Empty
            || request.CatalogVersion <= 0 || request.ConfigurationVersion <= 0 || request.ExpectedRevision < 0
            || !Number(request.Quantity, 6, out var quantity) || quantity <= 0
            || !Number(request.UnitPrice, 6, out var price)
            || !Number(request.DiscountPercent, 2, out var discount) || discount > 100) return Results.BadRequest();
        var member = await access.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        // Resolve the actual order scope first; no client company/site/tenant is trusted.
        WorkOrder? order;
        await using (var lookup = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.Id == id && x.TenantId == member.TenantId, ct);
            await lookup.CommitAsync(ct);
        }
        if (order is null) return Results.NotFound();
        if (await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.lines.add", true, ct) is null)
            return Results.StatusCode(403);
        var item = await catalog.Find(member.TenantId, request.CatalogItemId, ct);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        // Serialize distinct and repeated commands for this resource, even with a multi-connection pool.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()}, 0))", ct);
        var existing = await db.Lines.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
            return existing.OrderId == id && existing.CatalogItemId == request.CatalogItemId && existing.CatalogVersion == request.CatalogVersion
                && existing.ConfigurationVersion == request.ConfigurationVersion && existing.ExpectedRevision == request.ExpectedRevision
                && existing.Quantity == quantity && existing.UnitPrice == price && existing.DiscountPercent == discount
                ? Results.Ok(existing.ToContract()) : Results.Conflict();
        // A technical closure freezes the commercial source of the administrative request (no reopening implemented).
        if (await db.TechnicalClosures.AnyAsync(x => x.OrderId == id, ct)) return Closed();
        if (item is null) return Results.NotFound();
        if (item.Version != request.CatalogVersion) return Results.Conflict();
        // Explicit caller values; never derive price or payer from catalog policy.
        if (item.Kind is not ("Service" or "Part")) return Results.BadRequest();
        var policy = await db.LinePolicies.AsNoTracking().Where(x => x.TenantId == member.TenantId
            && x.LegalEntityId == order.LegalEntityId && x.DocumentTypeId == order.DocumentTypeId)
            .OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);
        if (policy is null || policy.Version != request.ConfigurationVersion || !policy.SameWorkingGroup
            || policy.Policy != "Case001") return Results.Conflict();
        // The persisted lifecycle revision (never a row count) is read under the order lock.
        var revision = await db.Orders.AsNoTracking().Where(x => x.Id == id && x.TenantId == member.TenantId).Select(x => x.CommercialRevision).SingleAsync(ct);
        if (revision != request.ExpectedRevision || await db.Lines.AnyAsync(x => x.OrderId == id && x.Kind == item.Kind && x.State == "Active", ct))
            return Results.Conflict();
        // The legacy single-group path owns only the implicit group Id=OrderId; a multi-group order uses the editor commands.
        if (await db.WorkingGroups.AnyAsync(x => x.OrderId == id && x.Id != id, ct))
            return Results.Conflict(new { code = "legacy_line_requires_editor", message = "La commessa usa più lavorazioni: usa i comandi dell'editor." });
        var legacyGroup = await db.WorkingGroups.AsNoTracking().SingleOrDefaultAsync(x => x.Id == id, ct);
        if (legacyGroup is { State: not "Active" }) return Results.Conflict();
        if (revision == int.MaxValue) return Results.Conflict(new { code = "revision_limit", message = "Limite revisioni raggiunto." });
        var line = new CommercialLine
        {
            Id = request.Id, TenantId = member.TenantId, OrderId = id, CatalogItemId = item.Id,
            CatalogVersion = item.Version, CatalogLabel = item.Label, Kind = item.Kind, Quantity = quantity,
            UnitPrice = price, DiscountPercent = discount, NetAmount = RoundMoney(quantity * price * (1 - discount / 100m)),
            TaxRate = 22m, PayerId = order.PayerId, WorkingGroupId = id,
            ConfigurationVersion = policy.Version, ExpectedRevision = request.ExpectedRevision
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO workshop.commercial_lines ("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel",
                "Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision")
            VALUES ({line.Id},{line.TenantId},{line.OrderId},{line.CatalogItemId},{line.CatalogVersion},{line.CatalogLabel},
                {line.Kind},{line.Quantity},{line.UnitPrice},{line.DiscountPercent},{line.NetAmount},{line.TaxRate},
                {line.PayerId},{line.WorkingGroupId},{line.ConfigurationVersion},{line.ExpectedRevision})
            ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict(); // Foreign-tenant command collision, no disclosure.
        var active = await db.Lines.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").ToListAsync(ct);
        if (EditorEndpoints.ExceedsSummaryLimit(active)) return EditorEndpoints.SummaryLimit();
        if (legacyGroup is null)
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                INSERT INTO workshop.working_groups ("Id","TenantId","OrderId","Title","State","Version","CreatedRevision")
                VALUES ({id},{member.TenantId},{id},'Lavorazione','Active',1,{revision})
                """, ct);
            await EditorEndpoints.History(db, "Group", id, 1, member.TenantId, id, revision + 1, "Created", null,
                new { id, title = "Lavorazione", state = "Active", version = 1 }, ct);
        }
        await EditorEndpoints.History(db, "Line", line.Id, 1, member.TenantId, id, revision + 1, "Created", null, EditorEndpoints.LineSnapshot(line), ct);
        if (!await EditorEndpoints.Advance(db, member.TenantId, id, revision, ct)) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/workshop/orders/{id}/commercial-summary", line.ToContract());
    }
    private static async Task<IResult> Read(Guid id, ClaimsPrincipal user, IWorkshopAccess access,
        WorkshopDbContext db, CancellationToken ct)
    {
        var member = await access.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        WorkOrder? order;
        List<CommercialLine> lines;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, member.TenantId, ct);
            order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.Id == id && x.TenantId == member.TenantId, ct);
            lines = await db.Lines.AsNoTracking().Where(x => x.OrderId == id && x.State == "Active").OrderBy(x => x.ExpectedRevision).ToListAsync(ct);
            await tx.CommitAsync(ct);
        }
        if (order is null || await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null)
            return Results.NotFound();
        return Results.Ok(Summarize(order, lines, order.CommercialRevision));
    }
    internal static IResult Closed() => Results.Conflict(new { code = "order_technically_closed",
        message = "Commessa chiusa tecnicamente: nessuna modifica registrata." });
    internal static decimal RoundAmount(decimal value) => RoundMoney(value);
    internal static string Quantity(decimal value) => Value(value);
    internal static CommercialSummary Summarize(WorkOrder order, IReadOnlyList<CommercialLine> lines, int revision)
    {
        var net = lines.Sum(x => x.NetAmount);
        var tax = lines.GroupBy(x => new { x.PayerId, x.TaxRate })
            .Sum(group => RoundMoney(group.Sum(x => x.NetAmount) * group.Key.TaxRate / 100m));
        return new CommercialSummary(order.Id, order.PayerId, revision, lines.Select(x => x.ToContract()).ToArray(),
            Money(net), Money(tax), Money(net + tax), "EUR", "Case001");
    }
    internal static LineContract Contract(CommercialLine x) => new(x.Id, x.OrderId, x.CatalogItemId, x.CatalogVersion,
        x.CatalogLabel, x.Kind, Value(x.Quantity), Value(x.UnitPrice), Value(x.DiscountPercent), Money(x.NetAmount),
        Value(x.TaxRate), x.PayerId, x.WorkingGroupId, x.ConfigurationVersion);
}
internal sealed class CommercialLine
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int CatalogVersion { get; set; }
    public required string CatalogLabel { get; set; }
    public required string Kind { get; set; }
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal DiscountPercent { get; set; }
    public decimal NetAmount { get; set; }
    public decimal TaxRate { get; set; }
    public Guid PayerId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public int ConfigurationVersion { get; set; }
    public int ExpectedRevision { get; set; }
    public string? Description { get; set; }
    public string State { get; set; } = "Active";
    public int Version { get; set; } = 1;
    internal LineContract ToContract() => CommercialEndpoints.Contract(this);
}
internal sealed class LinePolicy
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid DocumentTypeId { get; set; }
    public int Version { get; set; }
    public required string Policy { get; set; }
    public bool SameWorkingGroup { get; set; }
    public bool MultipleWorkingGroups { get; set; }
}
