using System.Globalization;
using System.Text.RegularExpressions;
using System.Security.Claims;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;

namespace Enginia360.Inventory;

public static class InventoryModule
{
    public static IServiceCollection AddInventory(this IServiceCollection services, string connection)
    {
        services.AddDbContext<InventoryDbContext>(o => o.UseNpgsql(connection));
        services.AddScoped<IWorkshopPickedParts, WorkshopPickedParts>();
        services.AddScoped<IInstallationStockEffects, InstallationStockEffects>();
        services.AddScoped<IReplacedPartReturns, ReplacedPartReturns>();
        services.AddScoped<IReceiptDispatchOutbox, ReceiptDispatchOutbox>();
        services.AddScoped<IPurchaseDispatchOutbox, PurchaseDispatchOutbox>();
        return services;
    }
    public static WebApplication MapInventory(this WebApplication app)
    {
        var routes = app.MapGroup("/api/v1/inventory").RequireAuthorization().AddEndpointFilter<TechnicalAuditFilter>();
        routes.MapGet("/warehouses", async (Guid legalEntityId, Guid siteId, ClaimsPrincipal user,
            IWorkshopAccess workshop, IInventoryAccess access, CancellationToken ct) =>
        {
            if (await workshop.Authorize(Subject(user), legalEntityId, siteId, "workshop.orders.read", false, ct) is null)
                return Results.NotFound();
            return Results.Ok(await access.Warehouses(Subject(user), legalEntityId, siteId, ct));
        });
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}", Read);
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/reservations", Reserve);
        ReceiptIntentEndpoints.Map(routes);
        PurchaseIntentEndpoints.Map(routes);
        PickingEndpoints.Map(routes);
        ReleaseEndpoints.Map(routes);
        NewPartReturnEndpoints.Map(routes);
        CarcassReturnEndpoints.Map(routes);
        return app;
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    internal static string Value(decimal value) => value.ToString("0.######", CultureInfo.InvariantCulture);
    // Public OrganizationAccess contract, on the caller's existing transaction/connection.
    internal static Task<string> StockProfile(InventoryDbContext db, Guid tenant, Guid company, CancellationToken ct) =>
        db.Database.SqlQuery<string>($"SELECT organization_access.company_stock_profile({tenant},{company}) AS \"Value\"").SingleAsync(ct);
    private static async Task SetTenant(InventoryDbContext db, Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);
    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid warehouseId, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, IWorkshopReservationLines lines, InventoryDbContext db, CancellationToken ct)
    {
        var member = await workshop.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        var line = await lines.Find(member.TenantId, orderId, lineId, ct);
        if (line is null) return Results.NotFound();
        if (await workshop.Authorize(Subject(user), line.LegalEntityId, line.SiteId, "workshop.orders.read", false, ct) is null
            || !await access.Authorize(Subject(user), line.LegalEntityId, line.SiteId, warehouseId, "inventory.reservations.read", false, ct))
            return Results.NotFound();
        if (line.Kind != "Part") return Results.BadRequest();
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await SetTenant(db, member.TenantId, ct);
        var physical = await db.Stock.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == warehouseId && x.CatalogItemId == line.CatalogItemId)
            .Select(x => x.Physical).SingleOrDefaultAsync(ct);
        var reservations = await db.Reservations.AsNoTracking().Where(x => x.LineId == lineId && x.TenantId == member.TenantId).OrderBy(x => x.Id).ToListAsync(ct);
        var committed = await db.Reservations.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == warehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var consumed = await db.Consumptions.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == warehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var reserved = reservations.Sum(x => x.Quantity);
        var released = await db.Releases.Where(x => x.TenantId == member.TenantId && x.LineId == lineId).SumAsync(x => x.Quantity, ct);
        var poolReleased = await db.Releases.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == warehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var returned = await db.NewPartReturns.Where(x => x.TenantId == member.TenantId && x.LineId == lineId).SumAsync(x => x.Quantity, ct);
        var poolReturned = await db.NewPartReturns.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == warehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var stockProfile = await StockProfile(db, member.TenantId, line.LegalEntityId, ct);
        await tx.CommitAsync(ct);
        // Release the read connection before authorization adapters (shared pool may be one).
        await tx.DisposeAsync();
        var canReserve = stockProfile == "local" && await workshop.Authorize(Subject(user), line.LegalEntityId, line.SiteId, "workshop.orders.read", true, ct) is not null
            && await access.Authorize(Subject(user), line.LegalEntityId, line.SiteId, warehouseId, "inventory.reservations.create", true, ct);
        return Results.Ok(new ReservationState(orderId, lineId, warehouseId, Value(physical), Value(physical - (committed-poolReleased-poolReturned-consumed)),
            Value(reserved-released-returned), Value(line.Quantity - reserved+released+returned), reservations.Where(x => x.WarehouseId == warehouseId).Select(x => x.Contract()).ToArray(), Value(committed-poolReleased-poolReturned-consumed), Value(consumed), canReserve, stockProfile));
    }
    private static async Task<IResult> Reserve(Guid orderId, Guid lineId, ReserveRequest request, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, IWorkshopReservationLines lines, InventoryDbContext db, CancellationToken ct)
    {
        if (orderId == Guid.Empty || lineId == Guid.Empty || request.Id == Guid.Empty || request.WarehouseId == Guid.Empty
            || request.CatalogVersion <= 0 || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity)
            || quantity <= 0) return Results.BadRequest();
        var member = await workshop.ResolveMembership(Subject(user), ct);
        if (member is null) return Results.NotFound();
        var line = await lines.Find(member.TenantId, orderId, lineId, ct);
        if (line is null) return Results.NotFound();
        if (await workshop.Authorize(Subject(user), line.LegalEntityId, line.SiteId, "workshop.orders.read", true, ct) is null
            || !await access.Authorize(Subject(user), line.LegalEntityId, line.SiteId, request.WarehouseId, "inventory.reservations.create", true, ct))
            return Results.StatusCode(403);
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        var stockProfile = await StockProfile(db, member.TenantId, line.LegalEntityId, ct);
        if (stockProfile != "local") return Results.Conflict(new { code = "stock_profile_" + stockProfile });
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()}, 0))", ct);
        var existing = await db.Reservations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
            return existing.OrderId == orderId && existing.LineId == lineId && existing.WarehouseId == request.WarehouseId
                && existing.CatalogVersion == request.CatalogVersion && existing.Quantity == quantity
                ? Results.Ok(existing.Contract()) : Results.Conflict();
        // Canonical command -> order -> line -> stock order also fences closure/P2.
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({orderId.ToString()}, 0))", ct);
        // Line lock deliberately excludes warehouse: partials across warehouses share one residual.
        var lineLock = $"inventory:line:{member.TenantId}:{lineId}";
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock}, 0))", ct);
        // Owning Workshop public SQL contract, evaluated AFTER the line lock on this
        // Inventory transaction/connection. Never open a nested pooled module connection.
        line = await db.Database.SqlQuery<ReservationLine>($"SELECT * FROM workshop.reservation_line({member.TenantId},{orderId},{lineId})").SingleOrDefaultAsync(ct);
        if (line is null) return Results.NotFound();
        if (line.Kind != "Part") return Results.BadRequest();
        if (request.CatalogVersion != line.CatalogVersion) return Results.Conflict();
        var reserved = await db.Reservations.Where(x => x.TenantId == member.TenantId && x.LineId == lineId).SumAsync(x => x.Quantity, ct);
        var released = await db.Releases.Where(x => x.TenantId == member.TenantId && x.LineId == lineId).SumAsync(x => x.Quantity, ct);
        var returned = await db.NewPartReturns.Where(x => x.TenantId == member.TenantId && x.LineId == lineId).SumAsync(x => x.Quantity, ct);
        // Consumption never restores commercial allocation; explicit compensation does.
        if (quantity > line.Quantity - reserved + released + returned)
            return Results.Conflict(new { code = "exceeds_remaining", message = "La quantità supera il residuo non prenotato della riga." });
        // Serialize all orders sharing this stock row. READ COMMITTED gives the
        // following aggregate a fresh snapshot after the previous holder commits.
        // One command locks one line, then one stock row: no reversed lock order.
        var stock = await db.Database.SqlQuery<decimal>($"""
            SELECT "Physical" AS "Value" FROM inventory.stock
            WHERE "TenantId"={member.TenantId} AND "LegalEntityId"={line.LegalEntityId}
                AND "SiteId"={line.SiteId} AND "WarehouseId"={request.WarehouseId}
                AND "CatalogItemId"={line.CatalogItemId}
            FOR UPDATE
            """).ToListAsync(ct);
        var physical = stock.SingleOrDefault();
        var committed = await db.Reservations.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var consumed = await db.Consumptions.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var poolReleased = await db.Releases.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        var poolReturned = await db.NewPartReturns.Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId && x.CatalogItemId == line.CatalogItemId).SumAsync(x => x.Quantity, ct);
        if (quantity > physical - (committed-poolReleased-poolReturned-consumed))
            return Results.Conflict(new { code = "insufficient_available", message = "Disponibilità insufficiente per la quantità richiesta. Nessuna prenotazione eseguita." });
        var row = new Reservation { Id = request.Id, TenantId = member.TenantId, OrderId = orderId, LineId = lineId,
            LegalEntityId = line.LegalEntityId, SiteId = line.SiteId, WarehouseId = request.WarehouseId,
            CatalogItemId = line.CatalogItemId, CatalogVersion = request.CatalogVersion, Quantity = quantity, WorkingGroupId = line.WorkingGroupId };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.reservations ("Id","TenantId","OrderId","LineId","LegalEntityId","SiteId","WarehouseId","CatalogItemId","CatalogVersion","Quantity","WorkingGroupId")
            VALUES ({row.Id},{row.TenantId},{row.OrderId},{row.LineId},{row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.CatalogVersion},{row.Quantity},{row.WorkingGroupId})
            ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict();
        await tx.CommitAsync(ct);
        return Results.Created($"/api/v1/inventory/orders/{orderId}/lines/{lineId}?warehouseId={request.WarehouseId}", row.Contract());
    }
}
internal sealed class InventoryDbContext(DbContextOptions<InventoryDbContext> options) : DbContext(options)
{
    internal DbSet<ConsumedPart> Consumptions => Set<ConsumedPart>();
    internal DbSet<Stock> Stock => Set<Stock>();
    internal DbSet<Reservation> Reservations => Set<Reservation>();
    internal DbSet<NewPartReturn> NewPartReturns => Set<NewPartReturn>();
    internal DbSet<ReservationRelease> Releases => Set<ReservationRelease>();
    internal DbSet<PickedPart> Picks => Set<PickedPart>();
    internal DbSet<PickingPolicy> PickingPolicies => Set<PickingPolicy>();
    internal DbSet<PickingLocation> PickingLocations => Set<PickingLocation>();
    internal DbSet<CarcassLocation> CarcassLocations => Set<CarcassLocation>();
    internal DbSet<CarcassReturn> CarcassReturns => Set<CarcassReturn>();
    internal DbSet<CarcassReturnInstallation> CarcassReturnInstallations => Set<CarcassReturnInstallation>();
    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<ConsumedPart>().ToTable("consumptions", "inventory").HasKey(x => x.InstallationId);
        b.Entity<ConsumedPart>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<Stock>().ToTable("stock", "inventory").HasKey(x => new { x.TenantId, x.LegalEntityId, x.SiteId, x.WarehouseId, x.CatalogItemId });
        b.Entity<Stock>().Property(x => x.Physical).HasPrecision(12, 6);
        b.Entity<Reservation>().ToTable("reservations", "inventory").HasKey(x => x.Id);
        b.Entity<Reservation>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<NewPartReturn>().ToTable("new_part_returns", "inventory").HasKey(x => x.Id);
        b.Entity<NewPartReturn>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<ReservationRelease>().ToTable("reservation_releases", "inventory").HasKey(x => x.Id);
        b.Entity<ReservationRelease>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<PickedPart>().ToTable("picks", "inventory").HasKey(x => x.Id);
        b.Entity<PickedPart>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<PickingPolicy>().ToTable("picking_policies", "inventory").HasKey(x => new { x.TenantId, x.LegalEntityId });
        b.Entity<CarcassLocation>().ToTable("carcass_locations", "inventory").HasKey(x => new { x.TenantId, x.LegalEntityId, x.SiteId, x.WarehouseId, x.Version });
        b.Entity<CarcassReturn>().ToTable("carcass_returns", "inventory").HasKey(x => x.Id);
        b.Entity<CarcassReturn>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<CarcassReturnInstallation>().ToTable("carcass_return_installations", "inventory").HasKey(x => x.InstallationId);
        b.Entity<CarcassReturnInstallation>().Property(x => x.Quantity).HasPrecision(12, 6);
        b.Entity<PickingLocation>().ToTable("picking_locations", "inventory").HasKey(x => new { x.TenantId, x.LegalEntityId, x.SiteId, x.WarehouseId });
    }
}
internal sealed class Stock
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public decimal Physical { get; set; }
}
internal sealed class Reservation
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid LineId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public int CatalogVersion { get; set; }
    public decimal Quantity { get; set; }
    public Guid WorkingGroupId { get; set; }
    internal ReservationContract Contract() => new(Id, OrderId, LineId, WarehouseId, InventoryModule.Value(Quantity), CatalogVersion);
}
