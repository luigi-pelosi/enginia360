namespace Enginia360.Workshop.Contracts;

public sealed record WorkshopGrant(Guid TenantId, Guid MembershipId);
// Persisted immutable projection: Inventory never accesses Workshop tables or DbContext.
public sealed record ReservationLine(Guid OrderId, Guid LineId, Guid LegalEntityId, Guid SiteId,
    Guid CatalogItemId, int CatalogVersion, string Kind, decimal Quantity, Guid WorkingGroupId);
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
    // Entitlement of a further company capability, e.g. the external administrative destination.
    Task<bool> CapabilityEnabled(Guid verifiedTenantId, Guid companyId, string capability, CancellationToken ct);
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
public sealed record WorkshopBillingSource(Guid TenantId, Guid OrderId, Guid LegalEntityId, Guid SiteId, Guid PayerId,
    int Revision, int DestinationVersion, CommercialSummary Summary);
public interface IWorkshopBillingSources
{
    Task<WorkshopBillingSource?> Find(Guid verifiedTenantId, Guid orderId, CancellationToken ct);
    Task<WorkshopBillingSource?> Allocate(Guid verifiedTenantId, Guid orderId, Guid invoiceId, int expectedRevision,
        CancellationToken ct);
}

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
    int ConfigurationVersion, DateTimeOffset InstalledAt, Guid OperatorId, int? CarcassPolicyVersion, bool CarcassReturnRequired);
// Immutable D9 snapshot of an installation whose carcass return is required (D39/D73).
public sealed record CarcassInstallation(Guid InstallationId, Guid LineId, Guid CatalogItemId, decimal Quantity,
    int CarcassPolicyVersion, DateTimeOffset InstalledAt);
public interface IWorkshopInstallations
{
    Task<InstallationContract?> Find(string subject, Guid installationId, bool write, CancellationToken ct);
    // Tenant-verified projection; the caller authorizes the order/action before using it.
    Task<IReadOnlyList<CarcassInstallation>> RequiredCarcass(Guid verifiedTenantId, Guid orderId, CancellationToken ct);
}
// Implemented by Inventory, owner of carcass receipts: installation IDs covered by accepted returns.
public interface IReplacedPartReturns
{
    Task<IReadOnlyDictionary<Guid, decimal>> Covered(Guid verifiedTenantId, Guid orderId, CancellationToken ct);
}
public sealed record CarcassRequirement(Guid LineId, Guid CatalogItemId, string RequiredInstalled, string Returned, string Outstanding);
public sealed record TechnicalClosureGate(Guid OrderId, string Status, IReadOnlyList<CarcassRequirement> Requirements);
public sealed record ConsumptionContract(Guid InstallationId, string Quantity, DateTimeOffset ConsumedAt);
public interface IInstallationStockEffects
{
    Task<ConsumptionContract?> Read(string subject, Guid installationId, CancellationToken ct);
    Task<ConsumptionContract?> Consume(string subject, Guid installationId, CancellationToken ct);
}
public sealed record InstallationResult(InstallationContract Installation, string StockEffect, ConsumptionContract? Consumption);
public sealed record InstallationState(string Picked, string Installed, string RemainingToInstall, IReadOnlyList<InstallationResult> Installations, bool CanInstall = false, bool CanRecoverConsumption = false);
