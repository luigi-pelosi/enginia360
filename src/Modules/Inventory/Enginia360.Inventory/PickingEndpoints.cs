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

internal static class PickingEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/picks", Pick);
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/picks", Read);
    }

    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";

    private static async Task SetTenant(InventoryDbContext db, Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid reservationId, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        var member = await workshop.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        var reservation = await FindReservation(db, member.TenantId, orderId, lineId, reservationId, ct);
        if (reservation is null) return Results.NotFound();
        if (await workshop.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, "workshop.orders.read", false, ct) is null
            || !await access.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, reservation.WarehouseId,
                "inventory.picks.read", false, ct)) return Results.NotFound();
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await SetTenant(db, member.TenantId, ct);
        var picks = await db.Picks.AsNoTracking().Where(x => x.ReservationId == reservationId && x.TenantId == member.TenantId)
            .OrderBy(x => x.Id).ToListAsync(ct);
        var picked = picks.Sum(x => x.Quantity);
        var stockProfile = await InventoryModule.StockProfile(db, member.TenantId, reservation.LegalEntityId, ct);
        await tx.CommitAsync(ct);
        await tx.DisposeAsync();
        var canPick = stockProfile == "local" && await workshop.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, "workshop.orders.read", true, ct) is not null
            && await access.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, reservation.WarehouseId, "inventory.picks.create", true, ct);
        return Results.Ok(new PickingState(reservationId, InventoryModule.Value(reservation.Quantity), InventoryModule.Value(picked),
            InventoryModule.Value(reservation.Quantity - picked), picks.Select(x => x.Contract()).ToArray(), canPick));
    }

    private static async Task<IResult> Pick(Guid orderId, Guid lineId, Guid reservationId, PickRequest request, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        if (orderId == Guid.Empty || lineId == Guid.Empty || reservationId == Guid.Empty || request.Id == Guid.Empty
            || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity)
            || quantity <= 0) return Results.BadRequest();
        var member = await workshop.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        var reservation = await FindReservation(db, member.TenantId, orderId, lineId, reservationId, ct);
        if (reservation is null) return Results.NotFound();
        if (await workshop.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, "workshop.orders.read", true, ct) is null
            || !await access.Authorize(Subject(user), reservation.LegalEntityId, reservation.SiteId, reservation.WarehouseId,
                "inventory.picks.create", true, ct)) return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        var stockProfile = await InventoryModule.StockProfile(db, member.TenantId, reservation.LegalEntityId, ct);
        if (stockProfile != "local") return Results.Conflict(new { code = "stock_profile_" + stockProfile });
        // Global command lock, then reservation lock; one reservation per command.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()}, 0))", ct);
        var existing = await db.Picks.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
            return existing.ReservationId == reservationId && existing.Quantity == quantity
                ? Results.Ok(existing.Contract()) : Results.Conflict();
        var reservationLock = $"inventory:pick:{member.TenantId}:{reservationId}";
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({reservationLock}, 0))", ct);
        var picked = await db.Picks.Where(x => x.TenantId == member.TenantId && x.ReservationId == reservationId).SumAsync(x => x.Quantity, ct);
        if (quantity > reservation.Quantity - picked)
            return Results.Conflict(new { code = "exceeds_unpicked", message = "Quantità superiore al residuo prenotato da prelevare. Nessun prelievo eseguito." });
        var policy = await db.PickingPolicies.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
            && x.LegalEntityId == reservation.LegalEntityId, ct);
        var location = await db.PickingLocations.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
            && x.LegalEntityId == reservation.LegalEntityId && x.SiteId == reservation.SiteId && x.WarehouseId == reservation.WarehouseId, ct);
        // Missing configuration is not an implicit choice to bypass preparation.
        if (policy is null || location is null || (policy.PreparationEnabled && location.PreparationLocation is null))
            return Results.Conflict(new { code = "picking_configuration_missing", message = "Configurazione di prelievo non disponibile." });
        var row = new PickedPart
        {
            Id = request.Id, TenantId = member.TenantId, ReservationId = reservationId, OrderId = orderId,
            WorkingGroupId = reservation.WorkingGroupId, LineId = lineId, LegalEntityId = reservation.LegalEntityId, SiteId = reservation.SiteId,
            WarehouseId = reservation.WarehouseId, CatalogItemId = reservation.CatalogItemId, CatalogVersion = reservation.CatalogVersion,
            Quantity = quantity, ConfigurationVersion = policy.Version, OriginLocation = location.OriginLocation,
            PlacementLocation = policy.PreparationEnabled ? location.PreparationLocation : null,
            PickingListId = request.Id, PickedAt = PostgreSqlNow(), OperatorId = Guid.Parse(Subject(user))
        };
        // Conflict-safe global key also handles another tenant's invisible command ID.
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.picks ("Id","TenantId","ReservationId","OrderId","WorkingGroupId","LineId",
                "LegalEntityId","SiteId","WarehouseId","CatalogItemId","CatalogVersion","Quantity","ConfigurationVersion",
                "OriginLocation","PlacementLocation","PickingListId","PickedAt","OperatorId")
            VALUES ({row.Id},{row.TenantId},{row.ReservationId},{row.OrderId},{row.WorkingGroupId},{row.LineId},
                {row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.CatalogVersion},{row.Quantity},
                {row.ConfigurationVersion},{row.OriginLocation},{row.PlacementLocation},{row.PickingListId},{row.PickedAt},{row.OperatorId})
            ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/inventory/orders/{orderId}/lines/{lineId}/reservations/{reservationId}/picks", row.Contract());
    }

    // Release the Inventory connection before access adapters use the shared pool.
    // Reservations are immutable; authorization cannot race a relocation/update.
    private static async Task<Reservation?> FindReservation(InventoryDbContext db, Guid tenantId,
        Guid orderId, Guid lineId, Guid reservationId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, tenantId, ct);
        var reservation = await db.Reservations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == reservationId
            && x.TenantId == tenantId && x.OrderId == orderId && x.LineId == lineId, ct);
        await tx.CommitAsync(ct);
        return reservation;
    }

    private static DateTimeOffset PostgreSqlNow()
    {
        var now = DateTimeOffset.UtcNow;
        return new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
    }
}

internal sealed class PickedPart
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid ReservationId { get; set; }
    public Guid OrderId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public Guid LineId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int CatalogVersion { get; set; }
    public decimal Quantity { get; set; }
    public int ConfigurationVersion { get; set; }
    public required string OriginLocation { get; set; }
    public string? PlacementLocation { get; set; }
    public Guid PickingListId { get; set; }
    public DateTimeOffset PickedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal PickContract Contract() => new(Id, ReservationId, OrderId, WorkingGroupId, LineId, WarehouseId, CatalogItemId,
        CatalogVersion, InventoryModule.Value(Quantity), ConfigurationVersion, OriginLocation, PlacementLocation, PickingListId, PickedAt, OperatorId);
}

internal sealed class PickingPolicy
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public int Version { get; set; }
    public bool PreparationEnabled { get; set; }
}

internal sealed class PickingLocation
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public required string OriginLocation { get; set; }
    public string? PreparationLocation { get; set; }
}
