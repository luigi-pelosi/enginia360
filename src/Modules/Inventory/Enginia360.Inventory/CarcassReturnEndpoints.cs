using System.Globalization;
using System.Security.Claims;
using System.Text.RegularExpressions;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Enginia360.Inventory;

// D73: every carcass return covers exactly the whole outstanding residual of the part line.
// The carcass is never stock: no physical, availability or valuation effect (D35/D38).
internal static class CarcassReturnEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/carcass-returns", Receive);
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/carcass-returns", Read);
    }

    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";

    private static async Task SetTenant(InventoryDbContext db, Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);

    private static bool ValidDescription(string? text) =>
        text is { Length: > 0 and <= 200 } && text == text.Trim() && !text.Any(char.IsControl);

    private static async Task<IResult> Receive(Guid orderId, Guid lineId, CarcassReturnRequest request, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, IWorkshopReservationLines lines, IWorkshopInstallations installations,
        InventoryDbContext db, ILogger<CarcassReturn> logger, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.WarehouseId == Guid.Empty || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity)
            || quantity <= 0 || !ValidDescription(request.Description)) return Results.BadRequest();
        var subject = Subject(user);
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        var line = await lines.Find(member.TenantId, orderId, lineId, ct);
        if (line is null) return Results.NotFound();
        if (await workshop.Authorize(subject, line.LegalEntityId, line.SiteId, "workshop.orders.read", true, ct) is null
            || !await access.Authorize(subject, line.LegalEntityId, line.SiteId, request.WarehouseId, "inventory.carcass-returns.create", true, ct))
            return Results.StatusCode(403);
        if (line.Kind != "Part") return Results.BadRequest();
        // Immutable technical facts read before any Inventory transaction (shared pool may have one connection).
        // A later installation is simply not in this set and stays outstanding.
        var required = (await installations.RequiredCarcass(member.TenantId, orderId, ct)).Where(x => x.LineId == lineId).ToArray();
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await SetTenant(db, member.TenantId, ct);
        var stockProfile = await InventoryModule.StockProfile(db, member.TenantId, line.LegalEntityId, ct);
        if (stockProfile != "local") return Results.Conflict(new { code = "stock_profile_" + stockProfile });
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()}, 0))", ct);
        var existing = await db.CarcassReturns.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
        if (existing is not null)
        {
            var same = existing.OrderId == orderId && existing.LineId == lineId && existing.WarehouseId == request.WarehouseId
                && existing.Quantity == quantity && existing.Description == request.Description;
            if (!same) return Results.Conflict();
            var links = await db.CarcassReturnInstallations.AsNoTracking().Where(x => x.ReturnId == existing.Id).ToListAsync(ct);
            return Results.Ok(existing.Contract(links));
        }
        // Command lock -> line lock: one accepted return at a time per line, fresh committed snapshot afterwards.
        var lineLock = $"inventory:carcass:{member.TenantId}:{lineId}";
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({lineLock}, 0))", ct);
        var ids = required.Select(x => x.InstallationId).ToArray();
        var covered = await db.CarcassReturnInstallations.Where(x => x.TenantId == member.TenantId && ids.Contains(x.InstallationId))
            .Select(x => x.InstallationId).ToListAsync(ct);
        var outstanding = required.Where(x => !covered.Contains(x.InstallationId)).ToArray();
        var residual = outstanding.Sum(x => x.Quantity);
        if (outstanding.Length == 0)
            return Results.Conflict(new { code = "nothing_outstanding", outstanding = "0", message = "Nessun residuo carcassa da rientrare. Nessun rientro registrato." });
        if (quantity != residual)
            return Results.Conflict(new { code = "must_cover_outstanding", outstanding = InventoryModule.Value(residual),
                message = "Il rientro deve coprire esattamente tutto il residuo carcassa. Nessun rientro registrato." });
        var location = await db.CarcassLocations.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.LegalEntityId == line.LegalEntityId
            && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId).OrderByDescending(x => x.Version).FirstOrDefaultAsync(ct);
        var picking = await db.PickingLocations.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId
            && x.LegalEntityId == line.LegalEntityId && x.SiteId == line.SiteId && x.WarehouseId == request.WarehouseId, ct);
        // D38: a dedicated replaced-part location is required; never default to a new-part location.
        if (location is null || picking is null || location.Location == picking.OriginLocation || location.Location == picking.PreparationLocation)
            return Results.Conflict(new { code = "carcass_configuration_missing", message = "Ubicazione carcasse non configurata. Nessun rientro registrato." });
        var now = DateTimeOffset.UtcNow;
        now = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
        var row = new CarcassReturn
        {
            Id = request.Id, TenantId = member.TenantId, OrderId = orderId, WorkingGroupId = line.WorkingGroupId, LineId = lineId,
            LegalEntityId = line.LegalEntityId, SiteId = line.SiteId, WarehouseId = request.WarehouseId, CatalogItemId = line.CatalogItemId,
            Location = location.Location, LocationConfigurationVersion = location.Version, Description = request.Description,
            Quantity = quantity, ReceivedAt = now, OperatorId = Guid.Parse(subject)
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.carcass_returns ("Id","TenantId","OrderId","WorkingGroupId","LineId","LegalEntityId","SiteId","WarehouseId",
                "CatalogItemId","Location","LocationConfigurationVersion","Description","Quantity","ReceivedAt","OperatorId")
            VALUES ({row.Id},{row.TenantId},{row.OrderId},{row.WorkingGroupId},{row.LineId},{row.LegalEntityId},{row.SiteId},{row.WarehouseId},
                {row.CatalogItemId},{row.Location},{row.LocationConfigurationVersion},{row.Description},{row.Quantity},{row.ReceivedAt},{row.OperatorId})
            ON CONFLICT ("Id") DO NOTHING
            """, ct);
        if (inserted == 0) return Results.Conflict(); // Another tenant's invisible command ID; no disclosure.
        var created = outstanding.Select(x => new CarcassReturnInstallation { InstallationId = x.InstallationId, ReturnId = row.Id,
            TenantId = member.TenantId, Quantity = x.Quantity, CarcassPolicyVersion = x.CarcassPolicyVersion }).ToList();
        foreach (var link in created)
            await db.Database.ExecuteSqlInterpolatedAsync($"""
                INSERT INTO inventory.carcass_return_installations ("InstallationId","ReturnId","TenantId","Quantity","CarcassPolicyVersion")
                VALUES ({link.InstallationId},{link.ReturnId},{link.TenantId},{link.Quantity},{link.CarcassPolicyVersion})
                """, ct);
        await tx.CommitAsync(ct);
        logger.LogInformation(new EventId(609), "Inventory carcass return committed {ReturnId} {IdentityId}", row.Id, subject);
        return Results.Created($"/api/v1/inventory/orders/{orderId}/lines/{lineId}/carcass-returns?warehouseId={request.WarehouseId}", row.Contract(created));
    }

    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid warehouseId, ClaimsPrincipal user,
        IWorkshopAccess workshop, IInventoryAccess access, IWorkshopReservationLines lines, IWorkshopInstallations installations,
        InventoryDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return Results.NotFound();
        var line = await lines.Find(member.TenantId, orderId, lineId, ct);
        if (line is null) return Results.NotFound();
        if (await workshop.Authorize(subject, line.LegalEntityId, line.SiteId, "workshop.orders.read", false, ct) is null
            || !await access.Authorize(subject, line.LegalEntityId, line.SiteId, warehouseId, "inventory.carcass-returns.read", false, ct))
            return Results.NotFound();
        if (line.Kind != "Part") return Results.BadRequest();
        var required = (await installations.RequiredCarcass(member.TenantId, orderId, ct)).Where(x => x.LineId == lineId).ToArray();
        await using var tx = await db.Database.BeginTransactionAsync(System.Data.IsolationLevel.RepeatableRead, ct);
        await SetTenant(db, member.TenantId, ct);
        var rows = await db.CarcassReturns.AsNoTracking().Where(x => x.TenantId == member.TenantId && x.LineId == lineId)
            .OrderBy(x => x.ReceivedAt).ThenBy(x => x.Id).ToListAsync(ct);
        var returnIds = rows.Select(x => x.Id).ToArray();
        var links = await db.CarcassReturnInstallations.AsNoTracking().Where(x => returnIds.Contains(x.ReturnId)).ToListAsync(ct);
        var stockProfile = await InventoryModule.StockProfile(db, member.TenantId, line.LegalEntityId, ct);
        await tx.CommitAsync(ct);
        await tx.DisposeAsync();
        var canReceive = stockProfile == "local" && await workshop.Authorize(subject, line.LegalEntityId, line.SiteId, "workshop.orders.read", true, ct) is not null
            && await access.Authorize(subject, line.LegalEntityId, line.SiteId, warehouseId, "inventory.carcass-returns.create", true, ct);
        var total = required.Sum(x => x.Quantity);
        var returned = rows.Sum(x => x.Quantity);
        var covered = required.Where(x => links.Any(link => link.InstallationId == x.InstallationId)).Sum(x => x.Quantity);
        return Results.Ok(new CarcassReturnState(orderId, lineId, warehouseId, InventoryModule.Value(total), InventoryModule.Value(returned),
            InventoryModule.Value(total - covered), rows.Where(x => x.WarehouseId == warehouseId)
                .Select(x => x.Contract(links.Where(link => link.ReturnId == x.Id).ToList())).ToArray(), canReceive));
    }
}

// Tenant-verified projection for Workshop's closure gate; the caller has authorized the order read.
internal sealed class ReplacedPartReturns(InventoryDbContext db) : IReplacedPartReturns
{
    public async Task<IReadOnlyDictionary<Guid, decimal>> Covered(Guid verifiedTenantId, Guid orderId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var rows = await (from link in db.CarcassReturnInstallations.AsNoTracking()
                          join receipt in db.CarcassReturns.AsNoTracking() on link.ReturnId equals receipt.Id
                          where receipt.TenantId == verifiedTenantId && link.TenantId == verifiedTenantId && receipt.OrderId == orderId
                          select new { link.InstallationId, link.Quantity }).ToListAsync(ct);
        await tx.CommitAsync(ct);
        return rows.ToDictionary(x => x.InstallationId, x => x.Quantity);
    }
}

internal sealed class CarcassLocation
{
    public Guid TenantId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public int Version { get; set; }
    public required string Location { get; set; }
}

internal sealed class CarcassReturn
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid OrderId { get; set; }
    public Guid WorkingGroupId { get; set; }
    public Guid LineId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public required string Location { get; set; }
    public int LocationConfigurationVersion { get; set; }
    public required string Description { get; set; }
    public decimal Quantity { get; set; }
    public DateTimeOffset ReceivedAt { get; set; }
    public Guid OperatorId { get; set; }
    internal CarcassReturnContract Contract(IReadOnlyList<CarcassReturnInstallation> links) => new(Id, OrderId, WorkingGroupId, LineId,
        WarehouseId, CatalogItemId, Location, LocationConfigurationVersion, Description, InventoryModule.Value(Quantity),
        links.OrderBy(x => x.InstallationId).Select(x => new CoveredInstallation(x.InstallationId, InventoryModule.Value(x.Quantity), x.CarcassPolicyVersion)).ToArray(),
        ReceivedAt, OperatorId);
}

internal sealed class CarcassReturnInstallation
{
    public Guid InstallationId { get; set; }
    public Guid ReturnId { get; set; }
    public Guid TenantId { get; set; }
    public decimal Quantity { get; set; }
    public int CarcassPolicyVersion { get; set; }
}
