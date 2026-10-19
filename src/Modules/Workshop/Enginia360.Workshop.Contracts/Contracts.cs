namespace Enginia360.Workshop.Contracts;

public sealed record WorkshopGrant(Guid TenantId, Guid MembershipId);
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
