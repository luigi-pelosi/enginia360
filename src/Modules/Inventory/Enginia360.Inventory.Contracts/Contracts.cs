namespace Enginia360.Inventory.Contracts;

public sealed record WarehouseChoice(Guid Id, string Name);
public interface IInventoryAccess
{
    Task<bool> Authorize(string subject, Guid companyId, Guid siteId, Guid warehouseId, string permission, bool requireCapability, CancellationToken ct);
    Task<IReadOnlyList<WarehouseChoice>> Warehouses(string subject, Guid companyId, Guid siteId, CancellationToken ct);
}
[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record ReserveRequest(Guid Id, Guid WarehouseId, string Quantity, int CatalogVersion);
public sealed record ReservationContract(Guid Id, Guid OrderId, Guid LineId, Guid WarehouseId, string Quantity, int CatalogVersion);
public sealed record ReservationState(Guid OrderId, Guid LineId, Guid WarehouseId, string Physical, string Available,
    string Reserved, string Remaining, IReadOnlyList<ReservationContract> Reservations);
