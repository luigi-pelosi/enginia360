namespace Enginia360.Workshop.Contracts;

public sealed record WorkshopGrant(Guid TenantId, Guid MembershipId);
// Persisted immutable projection: Inventory never accesses Workshop tables or DbContext.
public sealed record ReservationLine(Guid OrderId, Guid LineId, Guid LegalEntityId, Guid SiteId,
    Guid CatalogItemId, int CatalogVersion, string Kind, decimal Quantity);
public interface IWorkshopReservationLines
{
    Task<ReservationLine?> Find(Guid verifiedTenantId, Guid orderId, Guid lineId, CancellationToken ct);
}
public sealed record WorkshopContext(Guid LegalEntityId, string LegalEntityName, Guid SiteId, string SiteName);
public interface IWorkshopAccess
{
    Task<WorkshopGrant?> ResolveMembership(string subject, CancellationToken ct);
    Task<IReadOnlyList<WorkshopContext>> ListContexts(string subject, CancellationToken ct);
    Task<WorkshopGrant?> Authorize(string subject, Guid companyId, Guid siteId, string permission, bool requireCapability, CancellationToken ct);
}
public sealed record CreateOrderRequest(Guid Id, Guid LegalEntityId, Guid SiteId,
    Guid DocumentTypeId, int ConfigurationVersion, Guid PayerId, Guid VehicleId);
public sealed record OrderContract(Guid Id, Guid LegalEntityId, Guid SiteId,
    Guid DocumentTypeId, int ConfigurationVersion, Guid PayerId, Guid VehicleId,
    Guid VehicleHolderId, bool IsCustomerOrder);
public sealed record DocumentTypeContract(Guid Id, string Name, int Version, bool DirectCreationEnabled);

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record AddCaseLineRequest(Guid Id, Guid CatalogItemId, int CatalogVersion,
    int ConfigurationVersion, int ExpectedRevision, string Quantity, string UnitPrice, string DiscountPercent);
public sealed record LineContract(Guid Id, Guid OrderId, Guid CatalogItemId, int CatalogVersion,
    string CatalogLabel, string Kind, string Quantity, string UnitPrice, string DiscountPercent, string NetAmount,
    string TaxRate, Guid PayerId, Guid WorkingGroupId, int ConfigurationVersion);
public sealed record CommercialSummary(Guid OrderId, Guid PayerId, int Revision, IReadOnlyList<LineContract> Lines,
    string NetAmount, string TaxAmount, string Total, string Currency, string Policy);

[System.Text.Json.Serialization.JsonUnmappedMemberHandling(System.Text.Json.Serialization.JsonUnmappedMemberHandling.Disallow)]
public sealed record InstallRequest(Guid Id, string Quantity);
// Immutable cross-module projections, never ORM contexts or shared transactions.
public sealed record PickedInstallationSource(Guid PickId, Guid TenantId, Guid ReservationId, Guid OrderId,
    Guid WorkingGroupId, Guid LineId, Guid LegalEntityId, Guid SiteId, Guid WarehouseId,
    Guid CatalogItemId, int CatalogVersion, decimal Quantity, int PickingConfigurationVersion, DateTimeOffset PickedAt);
public interface IWorkshopPickedParts
{
    Task<PickedInstallationSource?> Find(string subject, Guid orderId, Guid lineId, Guid pickId, bool write, CancellationToken ct);
}
public sealed record InstallationContract(Guid Id, Guid TenantId, Guid PickId, Guid ReservationId, Guid OrderId,
    Guid WorkingGroupId, Guid LineId, Guid LegalEntityId, Guid SiteId, Guid WarehouseId, Guid CatalogItemId,
    int CatalogVersion, string Quantity, int PickingConfigurationVersion, Guid DocumentTypeId,
    int ConfigurationVersion, DateTimeOffset InstalledAt, Guid OperatorId);
public interface IWorkshopInstallations
{
    Task<InstallationContract?> Find(string subject, Guid installationId, bool write, CancellationToken ct);
}
public sealed record ConsumptionContract(Guid InstallationId, string Quantity, DateTimeOffset ConsumedAt);
public interface IInstallationStockEffects
{
    Task<ConsumptionContract?> Read(string subject, Guid installationId, CancellationToken ct);
    Task<ConsumptionContract?> Consume(string subject, Guid installationId, CancellationToken ct);
}
public sealed record InstallationResult(InstallationContract Installation, string StockEffect, ConsumptionContract? Consumption);
public sealed record InstallationState(string Picked, string Installed, string RemainingToInstall, IReadOnlyList<InstallationResult> Installations);
