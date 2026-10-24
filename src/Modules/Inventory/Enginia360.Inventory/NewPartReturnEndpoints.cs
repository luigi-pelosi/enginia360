using System.Globalization;
using System.Security.Claims;
using System.Text.RegularExpressions;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Inventory;

internal static class NewPartReturnEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/picks/{pickId:guid}/new-part-returns", Return);
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/picks/{pickId:guid}/new-part-returns", Read);
    }
    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid reservationId, Guid pickId, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        PickedPart? pick;
        NewPartReturnContract[] history;
        decimal returned, installedQuantity;
        bool open, installed;
        string profile;
        await using (var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)", ct);
            pick = await db.Picks.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == pickId && x.ReservationId == reservationId && x.OrderId == orderId && x.LineId == lineId, ct);
            if (pick is null) return Results.NotFound();
            var rows = await db.NewPartReturns.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.PickId == pickId).OrderBy(x => x.ReturnedAt).ThenBy(x => x.Id).ToListAsync(ct);
            history = rows.Select(x => x.Contract()).ToArray();
            returned = rows.Sum(x => x.Quantity);
            open = await db.Database.SqlQuery<ReservationLine>($"SELECT * FROM workshop.reservation_line({member.TenantId},{orderId},{lineId})").AnyAsync(ct);
            installedQuantity = await db.Database.SqlQuery<decimal>($"SELECT workshop.pick_installed_quantity({member.TenantId},{pickId}) AS \"Value\"").SingleAsync(ct);
            installed = await db.Database.SqlQuery<bool>($"SELECT workshop.pick_has_installations({member.TenantId},{pickId}) AS \"Value\"").SingleAsync(ct);
            profile = await InventoryModule.StockProfile(db, member.TenantId, pick.LegalEntityId, ct);
            await tx.CommitAsync(ct);
        }
        if (await workshop.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.orders.read", false, ct) is null
            || !await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, pick.WarehouseId, "inventory.reservations.read", false, ct)) return Results.NotFound();
        var remaining = pick.Quantity - returned - installedQuantity;
        var canReturn = !installed && remaining > 0 && open && profile == "local"
            && await workshop.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.orders.read", true, ct) is not null
            && await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, pick.WarehouseId, "inventory.new-part-returns.create", true, ct);
        var reason = installed ? "pick_has_installations" : !open ? "order_or_line_not_open" : remaining <= 0 ? "no_remaining"
            : profile != "local" ? "stock_profile_" + profile : !canReturn ? "permission_or_capability" : "ready";
        return Results.Ok(new NewPartReturnState(reservationId, pickId, InventoryModule.Value(pick.Quantity), InventoryModule.Value(returned), InventoryModule.Value(remaining), history, canReturn, reason));
    }
    private static async Task<IResult> Return(Guid orderId, Guid lineId, Guid reservationId, Guid pickId, NewPartReturnRequest request,
        ClaimsPrincipal user, IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        if (orderId == Guid.Empty || lineId == Guid.Empty || reservationId == Guid.Empty || pickId == Guid.Empty || request.Id == Guid.Empty
            || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity) || quantity <= 0)
            return Results.BadRequest();
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        PickedPart? pick;
        await using (var read = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)", ct);
            pick = await db.Picks.AsNoTracking().SingleOrDefaultAsync(x => x.Id == pickId && x.ReservationId == reservationId && x.TenantId == member.TenantId && x.OrderId == orderId && x.LineId == lineId, ct);
            await read.CommitAsync(ct);
        }
        if (pick is null) return Results.NotFound();
        // Replay still needs current exact authorization, but not a currently enabled write capability.
        if (await workshop.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.orders.read", false, ct) is null
            || !await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, pick.WarehouseId, "inventory.new-part-returns.create", false, ct))
            return Results.StatusCode(403);
        var enabled = await workshop.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.orders.read", true, ct) is not null
            && await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, pick.WarehouseId, "inventory.new-part-returns.create", true, ct);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)", ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject',{subject},true)", ct);
        async Task<bool> Authorized(bool write) => await db.Database.SqlQuery<bool>($"SELECT organization_access.inventory_new_return_authorized({member.TenantId},{member.MembershipId},{subject},{pick.LegalEntityId},{pick.SiteId},{pick.WarehouseId},{write}) AS \"Value\"").SingleAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()},0))", ct);
        var existing = await db.NewPartReturns.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
        {
            if (!await Authorized(false)) return Results.StatusCode(403);
            return existing.PickId == pickId && existing.ReservationId == reservationId && existing.OrderId == orderId && existing.LineId == lineId && existing.Quantity == quantity
                ? Results.Ok(existing.Contract()) : Results.Conflict();
        }
        if (!enabled) return Results.StatusCode(403);
        var profile = await InventoryModule.StockProfile(db, member.TenantId, pick.LegalEntityId, ct);
        if (profile != "local") return Results.Conflict(new { code = "stock_profile_" + profile });
        // Shared with closure/P2 first, then cumulative line, then stock. No nested module pool use.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({orderId.ToString()},0))", ct);
        var lineLock = $"inventory:line:{member.TenantId}:{lineId}";
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock},0))", ct);
        if (!await Authorized(true)) return Results.StatusCode(403);
        var line = await db.Database.SqlQuery<ReservationLine>($"SELECT * FROM workshop.reservation_line({member.TenantId},{orderId},{lineId})").SingleOrDefaultAsync(ct);
        if (line is null) return Results.Conflict(new { code = "order_or_line_not_open" });
        await db.Database.SqlQuery<decimal>($"""
            SELECT "Physical" AS "Value" FROM inventory.stock
            WHERE "TenantId"={member.TenantId} AND "LegalEntityId"={pick.LegalEntityId}
            AND "SiteId"={pick.SiteId} AND "WarehouseId"={pick.WarehouseId} AND "CatalogItemId"={pick.CatalogItemId} FOR UPDATE
            """).ToListAsync(ct);
        if (await db.Database.SqlQuery<bool>($"SELECT workshop.pick_has_installations({member.TenantId},{pickId}) AS \"Value\"").SingleAsync(ct))
            return Results.Conflict(new { code = "pick_has_installations" });
        var returned = await db.NewPartReturns.Where(x => x.TenantId == member.TenantId && x.PickId == pickId).SumAsync(x => x.Quantity, ct);
        if (quantity > pick.Quantity - returned) return Results.Conflict(new { code = "exceeds_returnable" });
        var now = DateTimeOffset.UtcNow;
        var row = new NewPartReturn
        {
            Id = request.Id,
            TenantId = member.TenantId,
            ReservationId = reservationId,
            PickId = pickId,
            MembershipId = member.MembershipId,
            OrderId = orderId,
            LineId = lineId,
            WorkingGroupId = pick.WorkingGroupId,
            LegalEntityId = pick.LegalEntityId,
            SiteId = pick.SiteId,
            WarehouseId = pick.WarehouseId,
            CatalogItemId = pick.CatalogItemId,
            CatalogVersion = pick.CatalogVersion,
            Quantity = quantity,
            ReturnedAt = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero),
            OperatorId = Guid.Parse(subject)
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.new_part_returns ("Id","TenantId","ReservationId","PickId","MembershipId","OrderId","LineId","WorkingGroupId","LegalEntityId","SiteId","WarehouseId","CatalogItemId","CatalogVersion","Quantity","ReturnedAt","OperatorId")
            VALUES ({row.Id},{row.TenantId},{row.ReservationId},{row.PickId},{row.MembershipId},{row.OrderId},{row.LineId},{row.WorkingGroupId},{row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.CatalogVersion},{row.Quantity},{row.ReturnedAt},{row.OperatorId}) ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/inventory/orders/{orderId}/lines/{lineId}/reservations/{reservationId}/picks/{pickId}/new-part-returns", row.Contract());
    }
}
internal sealed class NewPartReturn
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid ReservationId { get; set; }
    public Guid PickId { get; set; }
    public Guid MembershipId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LineId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int CatalogVersion { get; set; }
    public decimal Quantity { get; set; }
    public DateTimeOffset ReturnedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal NewPartReturnContract Contract() => new(Id, ReservationId, PickId, MembershipId, OrderId, LineId, WorkingGroupId, WarehouseId, CatalogItemId, CatalogVersion, InventoryModule.Value(Quantity), ReturnedAt, OperatorId);
}
