using System.Globalization;
using System.Security.Claims;
using System.Text.RegularExpressions;
using Enginia360.Workshop.Contracts;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Routing;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal static class InstallationEndpoints
{
    internal static void Map(RouteGroupBuilder routes)
    {
        routes.MapPost("/orders/{orderId:guid}/lines/{lineId:guid}/picks/{pickId:guid}/installations", Install);
        routes.MapGet("/orders/{orderId:guid}/lines/{lineId:guid}/picks/{pickId:guid}/installations", Read);
    }
    private static string Subject(ClaimsPrincipal user) => user.FindFirstValue(ClaimTypes.NameIdentifier) ?? "";
    internal static async Task SetTenant(WorkshopDbContext db, Guid tenant, CancellationToken ct) =>
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {tenant.ToString()}, true)", ct);
    private static async Task<IResult> Install(Guid orderId, Guid lineId, Guid pickId, InstallRequest request, ClaimsPrincipal user,
        IWorkshopAccess access, IWorkshopPickedParts picks, IInstallationStockEffects effects, WorkshopDbContext db, CancellationToken ct)
    {
        if (request.Id == Guid.Empty || request.Quantity is not { Length: > 0 and <= 13 }
            || !Regex.IsMatch(request.Quantity, @"^[0-9]{1,6}(?:\.[0-9]{1,6})?$", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)
            || !decimal.TryParse(request.Quantity, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var quantity)
            || quantity <= 0) return Results.BadRequest();
        var subject = Subject(user);
        // Public Inventory projection verifies exact resource, membership, stock action and capabilities.
        // No other module is called while a Workshop connection/transaction is held (pool-size one).
        var pick = await picks.Find(subject, orderId, lineId, pickId, true, ct);
        if (pick is null) return Results.NotFound();
        if (await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.installations.create", true, ct) is null)
            return Results.StatusCode(403);
        InstallationContract installation;
        var created = false;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, pick.TenantId, ct);
            await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({request.Id.ToString()}, 0))", ct);
            var existing = await db.Installations.AsNoTracking().SingleOrDefaultAsync(x => x.Id == request.Id, ct);
            if (existing is not null)
            {
                if (existing.PickId != pickId || existing.Quantity != quantity) return Results.Conflict();
                installation = existing.Contract();
            }
            else
            {
                var key = $"workshop:installation:{pick.TenantId}:{pickId}";
                await db.Database.ExecuteSqlInterpolatedAsync($"SELECT pg_advisory_xact_lock(hashtextextended({key}, 0))", ct);
                var installed = await db.Installations.Where(x => x.TenantId == pick.TenantId && x.PickId == pickId).SumAsync(x => x.Quantity, ct);
                if (quantity > pick.Quantity - installed)
                    return Results.Conflict(new { code = "exceeds_uninstalled", message = "Quantità superiore al prelevato non installato. Nessuna installazione registrata." });
                var order = await db.Orders.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == pick.TenantId && x.Id == orderId
                    && x.LegalEntityId == pick.LegalEntityId && x.SiteId == pick.SiteId, ct);
                if (order is null) return Results.NotFound();
                var now = DateTimeOffset.UtcNow;
                now = new DateTimeOffset(now.Ticks - now.Ticks % 10, TimeSpan.Zero);
                var row = new InstalledPart {
                    Id = request.Id, TenantId = pick.TenantId, PickId = pickId, ReservationId = pick.ReservationId,
                    OrderId = orderId, WorkingGroupId = pick.WorkingGroupId, LineId = lineId, LegalEntityId = pick.LegalEntityId,
                    SiteId = pick.SiteId, WarehouseId = pick.WarehouseId, CatalogItemId = pick.CatalogItemId,
                    CatalogVersion = pick.CatalogVersion, Quantity = quantity, PickingConfigurationVersion = pick.PickingConfigurationVersion,
                    DocumentTypeId = order.DocumentTypeId, ConfigurationVersion = order.ConfigurationVersion,
                    InstalledAt = now, OperatorId = Guid.Parse(subject)
                };
                var inserted = await db.Database.ExecuteSqlInterpolatedAsync($"""
                    INSERT INTO workshop.installations ("Id","TenantId","PickId","ReservationId","OrderId","WorkingGroupId","LineId",
                        "LegalEntityId","SiteId","WarehouseId","CatalogItemId","CatalogVersion","Quantity","PickingConfigurationVersion",
                        "DocumentTypeId","ConfigurationVersion","InstalledAt","OperatorId")
                    VALUES ({row.Id},{row.TenantId},{row.PickId},{row.ReservationId},{row.OrderId},{row.WorkingGroupId},{row.LineId},
                        {row.LegalEntityId},{row.SiteId},{row.WarehouseId},{row.CatalogItemId},{row.CatalogVersion},{row.Quantity},
                        {row.PickingConfigurationVersion},{row.DocumentTypeId},{row.ConfigurationVersion},{row.InstalledAt},{row.OperatorId})
                    ON CONFLICT ("Id") DO NOTHING
                    """, ct);
                if (inserted == 0) return Results.Conflict();
                installation = row.Contract();
                created = true;
            }
            await tx.CommitAsync(ct);
        }
        // The technical fact is now durable. A stock failure must not delete or compensate reality.
        ConsumptionContract? consumption;
        try { consumption = await effects.Consume(subject, installation.Id, ct); }
        catch (System.Data.Common.DbException) { consumption = null; }
        catch (TimeoutException) { consumption = null; }
        var result = new InstallationResult(installation, consumption is null ? "Pending" : "Consumed", consumption);
        if (consumption is null) return Results.Json(result, statusCode: 202);
        return created ? Results.Created($"/api/v1/workshop/orders/{orderId}/lines/{lineId}/picks/{pickId}/installations", result) : Results.Ok(result);
    }
    private static async Task<IResult> Read(Guid orderId, Guid lineId, Guid pickId, ClaimsPrincipal user,
        IWorkshopAccess access, IWorkshopPickedParts picks, IInstallationStockEffects effects, WorkshopDbContext db, CancellationToken ct)
    {
        var subject = Subject(user);
        var pick = await picks.Find(subject, orderId, lineId, pickId, false, ct);
        if (pick is null || await access.Authorize(subject, pick.LegalEntityId, pick.SiteId, "workshop.installations.read", false, ct) is null)
            return Results.NotFound();
        List<InstalledPart> rows;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await SetTenant(db, pick.TenantId, ct);
            rows = await db.Installations.AsNoTracking().Where(x => x.TenantId == pick.TenantId && x.PickId == pickId).OrderBy(x => x.Id).ToListAsync(ct);
            await tx.CommitAsync(ct);
        }
        var results = new List<InstallationResult>();
        foreach (var row in rows)
        {
            var effect = await effects.Read(subject, row.Id, ct);
            results.Add(new(row.Contract(), effect is null ? "Pending" : "Consumed", effect));
        }
        var installed = rows.Sum(x => x.Quantity);
        return Results.Ok(new InstallationState(pick.Quantity.ToString("0.######", CultureInfo.InvariantCulture),
            installed.ToString("0.######", CultureInfo.InvariantCulture), (pick.Quantity-installed).ToString("0.######", CultureInfo.InvariantCulture), results));
    }
}
internal sealed class WorkshopInstallations(WorkshopDbContext db, IWorkshopAccess access) : IWorkshopInstallations
{
    public async Task<InstallationContract?> Find(string subject, Guid installationId, bool write, CancellationToken ct)
    {
        var member = await access.ResolveMembership(subject, ct);
        if (member is null) return null;
        InstalledPart? row;
        await using (var tx = await db.Database.BeginTransactionAsync(ct))
        {
            await InstallationEndpoints.SetTenant(db, member.TenantId, ct);
            row = await db.Installations.AsNoTracking().SingleOrDefaultAsync(x => x.TenantId == member.TenantId && x.Id == installationId, ct);
            await tx.CommitAsync(ct);
        }
        return row is not null && await access.Authorize(subject, row.LegalEntityId, row.SiteId,
            write ? "workshop.installations.create" : "workshop.installations.read", write, ct) is not null ? row.Contract() : null;
    }
}
internal sealed class InstalledPart
{
    public Guid Id { get; set; }
    public Guid TenantId { get; set; }
    public Guid PickId { get; set; }
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
    public int PickingConfigurationVersion { get; set; }
    public Guid DocumentTypeId { get; set; }
    public int ConfigurationVersion { get; set; }
    public DateTimeOffset InstalledAt { get; set; }
    public Guid OperatorId { get; set; }
    internal InstallationContract Contract() => new(Id,TenantId,PickId,ReservationId,OrderId,WorkingGroupId,LineId,
        LegalEntityId,SiteId,WarehouseId,CatalogItemId,CatalogVersion,Quantity.ToString("0.######", CultureInfo.InvariantCulture),
        PickingConfigurationVersion,DocumentTypeId,ConfigurationVersion,InstalledAt,OperatorId);
}
