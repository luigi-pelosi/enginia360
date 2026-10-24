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

internal static class ReleaseEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/releases", Release);
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/reservations/{reservationId:guid}/releases", Read);
    }
    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid reservationId, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        var subject=user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var member=await workshop.ResolveMembership(subject,ct);
        if (member is null) return Results.NotFound();
        Reservation? reservation;
        ReleaseContract[] history;
        decimal released;
        bool picked, open;
        string profile;
        await using (var tx=await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead,ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)",ct);
            reservation=await db.Reservations.AsNoTracking().SingleOrDefaultAsync(x=>x.TenantId==member.TenantId && x.Id==reservationId && x.OrderId==orderId && x.LineId==lineId,ct);
            if (reservation is null) return Results.NotFound();
            var rows=await db.Releases.AsNoTracking().Where(x=>x.TenantId==member.TenantId && x.ReservationId==reservationId).OrderBy(x=>x.ReleasedAt).ThenBy(x=>x.Id).ToListAsync(ct);
            history=rows.Select(x=>x.Contract()).ToArray();
            released=rows.Sum(x=>x.Quantity);
            picked=await db.Picks.AnyAsync(x=>x.TenantId==member.TenantId && x.ReservationId==reservationId,ct);
            open=await db.Database.SqlQuery<ReservationLine>($"SELECT * FROM workshop.reservation_line({member.TenantId},{orderId},{lineId})").AnyAsync(ct);
            profile=await InventoryModule.StockProfile(db,member.TenantId,reservation.LegalEntityId,ct);
            await tx.CommitAsync(ct);
        }
        if (await workshop.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,"workshop.orders.read",false,ct) is null
            || !await access.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,reservation.WarehouseId,"inventory.reservations.read",false,ct)) return Results.NotFound();
        var remaining=picked ? 0 : reservation.Quantity-released;
        var canRelease=remaining>0 && open && profile=="local"
            && await workshop.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,"workshop.orders.read",true,ct) is not null
            && await access.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,reservation.WarehouseId,"inventory.reservations.release",true,ct);
        return Results.Ok(new ReleaseState(reservationId,InventoryModule.Value(reservation.Quantity),InventoryModule.Value(released),InventoryModule.Value(remaining),history,canRelease));
    }
    private static async Task<IResult> Release(Guid orderId, Guid lineId, Guid reservationId, ReleaseRequest request,
        ClaimsPrincipal user, IWorkshopAccess workshop, IInventoryAccess access, InventoryDbContext db, CancellationToken ct)
    {
        if (orderId == Guid.Empty || lineId == Guid.Empty || reservationId == Guid.Empty || request.Id == Guid.Empty
            || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity) || quantity <= 0)
            return Results.BadRequest();
        var subject = user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        Reservation? reservation;
        await using (var read = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)",ct);
            reservation = await db.Reservations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == reservationId && x.TenantId == member.TenantId && x.OrderId == orderId && x.LineId == lineId,ct);
            await read.CommitAsync(ct);
        }
        if (reservation is null) return Results.NotFound();
        // Replay still needs current exact authorization, but not a currently enabled write capability.
        if (await workshop.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,"workshop.orders.read",false,ct) is null
            || !await access.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,reservation.WarehouseId,"inventory.reservations.release",false,ct))
            return Results.StatusCode(403);
        var enabled = await workshop.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,"workshop.orders.read",true,ct) is not null
            && await access.Authorize(subject,reservation.LegalEntityId,reservation.SiteId,reservation.WarehouseId,"inventory.reservations.release",true,ct);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id',{member.TenantId.ToString()},true)",ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.identity_subject',{subject},true)",ct);
        async Task<bool> Authorized(bool write) => await db.Database.SqlQuery<bool>($"SELECT organization_access.inventory_release_authorized({member.TenantId},{member.MembershipId},{subject},{reservation.LegalEntityId},{reservation.SiteId},{reservation.WarehouseId},{write}) AS \"Value\"").SingleAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()},0))",ct);
        var existing = await db.Releases.AsNoTracking().SingleOrDefaultAsync(x=>x.Id==request.Id,ct);
        if (existing is not null)
        {
            if (!await Authorized(false)) return Results.StatusCode(403);
            return existing.ReservationId==reservationId && existing.OrderId==orderId && existing.LineId==lineId && existing.Quantity==quantity
                ? Results.Ok(existing.Contract()) : Results.Conflict();
        }
        if (!enabled) return Results.StatusCode(403);
        var profile = await InventoryModule.StockProfile(db,member.TenantId,reservation.LegalEntityId,ct);
        if (profile!="local") return Results.Conflict(new {code="stock_profile_"+profile});
        // Shared with closure/P2 first, then cumulative line, then stock. No nested module pool use.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({orderId.ToString()},0))",ct);
        var lineLock=$"inventory:line:{member.TenantId}:{lineId}";
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock},0))",ct);
        if (!await Authorized(true)) return Results.StatusCode(403);
        var line = await db.Database.SqlQuery<ReservationLine>($"SELECT * FROM workshop.reservation_line({member.TenantId},{orderId},{lineId})").SingleOrDefaultAsync(ct);
        if (line is null) return Results.Conflict(new {code="order_or_line_not_open"});
        await db.Database.SqlQuery<decimal>($"""
            SELECT "Physical" AS "Value" FROM inventory.stock
            WHERE "TenantId"={member.TenantId} AND "LegalEntityId"={reservation.LegalEntityId}
            AND "SiteId"={reservation.SiteId} AND "WarehouseId"={reservation.WarehouseId} AND "CatalogItemId"={reservation.CatalogItemId} FOR UPDATE
            """).ToListAsync(ct);
        if (await db.Picks.AnyAsync(x=>x.TenantId==member.TenantId && x.ReservationId==reservationId,ct))
            return Results.Conflict(new {code="reservation_already_picked"});
        var released=await db.Releases.Where(x=>x.TenantId==member.TenantId && x.ReservationId==reservationId).SumAsync(x=>x.Quantity,ct);
        if (quantity>reservation.Quantity-released) return Results.Conflict(new {code="exceeds_releasable"});
        var now=DateTimeOffset.UtcNow;
        var row=new ReservationRelease { Id=request.Id,TenantId=member.TenantId,ReservationId=reservationId,OrderId=orderId,LineId=lineId,
            WorkingGroupId=reservation.WorkingGroupId,LegalEntityId=reservation.LegalEntityId,SiteId=reservation.SiteId,WarehouseId=reservation.WarehouseId,
            CatalogItemId=reservation.CatalogItemId,CatalogVersion=reservation.CatalogVersion,Quantity=quantity,
            ReleasedAt=new DateTimeOffset(now.Ticks-now.Ticks%10,TimeSpan.Zero),OperatorId=Guid.Parse(subject) };
        var inserted=await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.reservation_releases ("Id","TenantId","ReservationId","OrderId","LineId","WorkingGroupId","LegalEntityId","SiteId","WarehouseId","CatalogItemId","CatalogVersion","Quantity","ReleasedAt","OperatorId")
            VALUES ({row.Id},{row.TenantId},{row.ReservationId},{row.OrderId},{row.LineId},{row.WorkingGroupId},{row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.CatalogVersion},{row.Quantity},{row.ReleasedAt},{row.OperatorId}) ON CONFLICT ("Id") DO NOTHING
            """,ct);
        if (inserted==0) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/inventory/orders/{orderId}/lines/{lineId}/reservations/{reservationId}/releases",row.Contract());
    }
}
internal sealed class ReservationRelease
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid ReservationId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LineId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int CatalogVersion { get; set; }
    public decimal Quantity { get; set; }
    public DateTimeOffset ReleasedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal ReleaseContract Contract()=>new(Id,ReservationId,OrderId,LineId,WorkingGroupId,WarehouseId,CatalogItemId,CatalogVersion,InventoryModule.Value(Quantity),ReleasedAt,OperatorId);
}
