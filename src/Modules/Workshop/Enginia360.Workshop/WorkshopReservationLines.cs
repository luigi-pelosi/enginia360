using Enginia360.Workshop.Contracts;
using Microsoft.EntityFrameworkCore;

namespace Enginia360.Workshop;

internal sealed class WorkshopReservationLines(WorkshopDbContext db) : IWorkshopReservationLines
{
    public async Task<ReservationLine?> Find(Guid verifiedTenantId, Guid orderId, Guid lineId, CancellationToken ct)
    {
        await using var tx = await db.Database.BeginTransactionAsync(ct);
        await db.Database.ExecuteSqlInterpolatedAsync($"SELECT set_config('app.tenant_id', {verifiedTenantId.ToString()}, true)", ct);
        var row = await (from order in db.Orders.AsNoTracking()
                         join line in db.Lines.AsNoTracking() on order.Id equals line.OrderId
                         where order.TenantId == verifiedTenantId && line.TenantId == verifiedTenantId
                             && order.Id == orderId && line.Id == lineId && line.State == "Active"
                         select new ReservationLine(order.Id, line.Id, order.LegalEntityId, order.SiteId,
                             line.CatalogItemId, line.CatalogVersion, line.Kind, line.Quantity, line.WorkingGroupId)).SingleOrDefaultAsync(ct);
        await tx.CommitAsync(ct);
        return row;
    }
}
