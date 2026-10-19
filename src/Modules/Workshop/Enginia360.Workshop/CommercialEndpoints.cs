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
    private static string Value(decimal value) => value.ToString("0.######", CultureInfo.InvariantCulture);
    private static string Money(decimal value) => value.ToString("0.000000", CultureInfo.InvariantCulture);
    // D67 admits nonnegative values only; AwayFromZero is ROUND_HALF_UP in this domain.
    private static decimal RoundMoney(decimal value) => decimal.Round(value, 6, MidpointRounding.AwayFromZero);
    [GeneratedRegex(@"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex InvariantDecimal();
    private static bool Number(string? text, int scale, out decimal value)
    {
        // Storage/anti-overflow bound, not a commercial maximum: numeric(12,6).
        // At most two lines: exact decimal multiplication and aggregate totals fit decimal.
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
        if (item is null) return Results.NotFound();
        if (item.Version != request.CatalogVersion) return Results.Conflict();
        // Explicit caller values; never derive price or payer from catalog policy.
        if (item.Kind is not ("Service" or "Part")) return Results.BadRequest();
        var policy = await db.LinePolicies.AsNoTracking().Where(x => x.TenantId == member.TenantId
            && x.LegalEntityId == order.LegalEntityId && x.DocumentTypeId == order.DocumentTypeId)
            .OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);
        if (policy is null || policy.Version != request.ConfigurationVersion || !policy.SameWorkingGroup
            || policy.Policy != "Case001") return Results.Conflict();
        var count = await db.Lines.CountAsync(x => x.OrderId == id, ct);
        if (count != request.ExpectedRevision || await db.Lines.AnyAsync(x => x.OrderId == id && x.Kind == item.Kind, ct))
            return Results.Conflict();
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
            lines = await db.Lines.AsNoTracking().Where(x => x.OrderId == id).OrderBy(x => x.ExpectedRevision).ToListAsync(ct);
            await tx.CommitAsync(ct);
        }
        if (order is null || await access.Authorize(Subject(user), order.LegalEntityId, order.SiteId, "workshop.orders.read", false, ct) is null)
            return Results.NotFound();
        var net = lines.Sum(x => x.NetAmount);
        var tax = lines.GroupBy(x => new { x.PayerId, x.TaxRate })
            .Sum(group => RoundMoney(group.Sum(x => x.NetAmount) * group.Key.TaxRate / 100m));
        return Results.Ok(new CommercialSummary(id, order.PayerId, lines.Count, lines.Select(x => x.ToContract()).ToArray(),
            Money(net), Money(tax), Money(net + tax), "EUR", "Case001"));
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
}
