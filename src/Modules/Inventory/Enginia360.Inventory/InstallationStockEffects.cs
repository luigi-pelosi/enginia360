using System.Globalization;
using Enginia360.Workshop.Contracts;
using Enginia360.Inventory.Contracts;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;

namespace Enginia360.Inventory;

internal sealed class WorkshopPickedParts(InventoryDbContext db, IWorkshopAccess workshop, IInventoryAccess access) : IWorkshopPickedParts
{
    public async Task<PickedInstallationSource?> Find(string subject, Guid orderId, Guid lineId, Guid pickId, bool write, CancellationToken ct)
    {
        var member = await workshop.ResolveMembership(subject, ct);
        if (member is null) return null;
        PickedPart? row;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {member.TenantId.ToString()}, true)", ct);
            row = await db.Picks.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == pickId
                && x.OrderId == orderId && x.LineId == lineId, ct);
            if (write && row is not null && await InventoryModule.StockProfile(db, member.TenantId, row.LegalEntityId, ct) != "local") row = null;
            await tx.CommitAsync(ct);
        }
        if (row is null || await workshop.Authorize(subject, row.LegalEntityId, row.SiteId, "workshop.orders.read", write, ct) is null
            || !await access.Authorize(subject, row.LegalEntityId, row.SiteId, row.WarehouseId,
                write ? "inventory.consumptions.create" : "inventory.consumptions.read", write, ct)) return null;
        return new(row.Id,row.TenantId,row.ReservationId,row.OrderId,row.WorkingGroupId,row.LineId,row.LegalEntityId,row.SiteId,
            row.WarehouseId,row.CatalogItemId,row.CatalogVersion,row.Quantity,row.ConfigurationVersion,row.PickedAt);
    }
}
internal sealed class InstallationStockEffects(InventoryDbContext db, IWorkshopInstallations installations, IInventoryAccess access, ILogger<InstallationStockEffects> logger) : IInstallationStockEffects
{
    public Task<ConsumptionContract?> Read(string subject, Guid installationId, CancellationToken ct) => Execute(subject, installationId, false, ct);
    public Task<ConsumptionContract?> Consume(string subject, Guid installationId, CancellationToken ct) => Execute(subject, installationId, true, ct);
    private async Task<ConsumptionContract?> Execute(string subject, Guid id, bool write, CancellationToken ct)
    {
        var installation = await installations.Find(subject, id, write, ct);
        if (installation is null || !await access.Authorize(subject, installation.LegalEntityId, installation.SiteId, installation.WarehouseId,
            write ? "inventory.consumptions.create" : "inventory.consumptions.read", write, ct)) return null;
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {installation.TenantId.ToString()}, true)", ct);
        if (write) await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({id.ToString()}, 0))", ct);
        var existing = await db.Consumptions.AsNoTracking().SingleOrDefaultAsync(x => x.InstallationId == id, ct);
        if (existing is not null) return existing.Contract();
        if (!write) return null;
        if (await InventoryModule.StockProfile(db, installation.TenantId, installation.LegalEntityId, ct) != "local") return null;
        var pick = await db.Picks.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == installation.TenantId && x.Id == installation.PickId
            && x.ReservationId == installation.ReservationId && x.OrderId == installation.OrderId && x.LineId == installation.LineId
            && x.LegalEntityId == installation.LegalEntityId && x.SiteId == installation.SiteId && x.WarehouseId == installation.WarehouseId
            && x.CatalogItemId == installation.CatalogItemId && x.CatalogVersion == installation.CatalogVersion, ct);
        if (pick is null) return null;
        var quantity = decimal.Parse(installation.Quantity, CultureInfo.InvariantCulture);
        // Same stock-row lock as reservation: new commitment and discharge cannot overbook availability.
        var stock = await db.Database.SqlQuery<decimal>($"""
            SELECT "Physical" AS "Value" FROM inventory.stock
            WHERE "TenantId"={installation.TenantId} AND "LegalEntityId"={installation.LegalEntityId}
                AND "SiteId"={installation.SiteId} AND "WarehouseId"={installation.WarehouseId}
                AND "CatalogItemId"={installation.CatalogItemId} FOR UPDATE
            """).ToListAsync(ct);
        if (stock.Count != 1 || stock[0] < quantity) return null;
        var consumed = await db.Consumptions.Where(x => x.TenantId == installation.TenantId && x.PickId == pick.Id).SumAsync(x => x.Quantity, ct);
        if (quantity <= 0 || quantity > pick.Quantity-consumed) return null;
        var now = DateTimeOffset.UtcNow;
        now = new DateTimeOffset(now.Ticks-now.Ticks%10, TimeSpan.Zero);
        var row = new ConsumedPart {
            InstallationId = id, TenantId = installation.TenantId, PickId = pick.Id, ReservationId = pick.ReservationId,
            LegalEntityId = installation.LegalEntityId, SiteId = installation.SiteId, WarehouseId = installation.WarehouseId,
            CatalogItemId = installation.CatalogItemId, Quantity = quantity, ConsumedAt = now
        };
        var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
            INSERT INTO inventory.consumptions ("InstallationId","TenantId","PickId","ReservationId","LegalEntityId","SiteId","WarehouseId","CatalogItemId","Quantity","ConsumedAt")
            VALUES ({row.InstallationId},{row.TenantId},{row.PickId},{row.ReservationId},{row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.Quantity},{row.ConsumedAt})
            ON CONFLICT ("InstallationId") DO NOTHING
            """, ct);
        if (inserted != 1) return null;
        await db.Database.ExecuteSqlInterpolatedAsync($"""
            UPDATE inventory.stock SET "Physical"="Physical"-{quantity}
            WHERE "TenantId"={row.TenantId} AND "LegalEntityId"={row.LegalEntityId} AND "SiteId"={row.SiteId}
                AND "WarehouseId"={row.WarehouseId} AND "CatalogItemId"={row.CatalogItemId}
            """, ct);
        await tx.CommitAsync(ct);
        logger.LogInformation(new EventId(608), "Inventory consumption committed {InstallationId} {IdentityId}", id, subject);
        return row.Contract();
    }
}
internal sealed class ConsumedPart
{
    public Guid InstallationId { get; set; }
    public Guid TenantId { get; set; }
    public Guid PickId { get; set; }
    public Guid ReservationId { get; set; }
    public Guid LegalEntityId { get; set; }
    public Guid SiteId { get; set; }
    public Guid WarehouseId { get; set; }
    public Guid CatalogItemId { get; set; }
    public decimal Quantity { get; set; }
    public DateTimeOffset ConsumedAt { get; set; }
    internal ConsumptionContract Contract() => new(InstallationId, InventoryModule.Value(Quantity), ConsumedAt);
}
