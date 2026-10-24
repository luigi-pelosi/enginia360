namespace Enginia360.Inventory.Contracts;

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record ReleaseRequest(Guid Id, string Quantity);
public sealed record ReleaseState(Guid ReservationId, string Reserved, string Released, string RemainingReleasable,
    IReadOnlyList<ReleaseContract> Releases, bool CanRelease);
public sealed record ReleaseContract(Guid Id, Guid ReservationId, Guid OrderId, Guid LineId, Guid WorkingGroupId,
    Guid WarehouseId, Guid CatalogItemId, int CatalogVersion, string Quantity, DateTimeOffset ReleasedAt, Guid OperatorId);
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
    string Reserved, string Remaining, IReadOnlyList<ReservationContract> Reservations, string ActiveCommitted, string Consumed, bool CanReserve = false, string StockProfile = "missing");

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record PickRequest(Guid Id, string Quantity);
public sealed record PickContract(Guid Id, Guid ReservationId, Guid OrderId, Guid WorkingGroupId, Guid LineId,
    Guid WarehouseId, Guid CatalogItemId, int CatalogVersion, string Quantity, int ConfigurationVersion,
    string OriginLocation, string? PlacementLocation, Guid PickingListId, DateTimeOffset PickedAt, Guid OperatorId);
public sealed record PickingState(Guid ReservationId, string Reserved, string Picked, string RemainingToPick,
    IReadOnlyList<PickContract> Picks, bool CanPick = false);

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record CarcassReturnRequest(Guid Id, Guid WarehouseId, string Quantity, string Description);
public sealed record CoveredInstallation(Guid InstallationId, string Quantity, int CarcassPolicyVersion);
public sealed record CarcassReturnContract(Guid Id, Guid OrderId, Guid WorkingGroupId, Guid LineId, Guid WarehouseId,
    Guid CatalogItemId, string Location, int LocationConfigurationVersion, string Description, string Quantity,
    IReadOnlyList<CoveredInstallation> Installations, DateTimeOffset ReceivedAt, Guid OperatorId);
public sealed record CarcassReturnState(Guid OrderId, Guid LineId, Guid WarehouseId, string RequiredInstalled, string Returned,
    string Outstanding, IReadOnlyList<CarcassReturnContract> Returns, bool CanReceiveCarcass = false);

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record NewPartReturnRequest(Guid Id, string Quantity);
public sealed record NewPartReturnState(Guid ReservationId, Guid PickId, string Picked, string Returned, string RemainingWithTechnician,
    IReadOnlyList<NewPartReturnContract> Returns, bool CanReturn, string Reason);
public sealed record NewPartReturnContract(Guid Id, Guid ReservationId, Guid PickId, Guid MembershipId, Guid OrderId, Guid LineId, Guid WorkingGroupId,
    Guid WarehouseId, Guid CatalogItemId, int CatalogVersion, string Quantity, DateTimeOffset ReturnedAt, Guid OperatorId);
