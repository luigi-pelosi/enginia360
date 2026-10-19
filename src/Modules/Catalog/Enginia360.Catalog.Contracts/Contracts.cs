namespace Enginia360.Catalog.Contracts;

public sealed record CatalogChoice(Guid Id, string Kind, string Label, int Version);
// The caller supplies only a server-verified tenant, never a client tenant claim.
public interface IWorkshopCatalog
{
    Task<IReadOnlyList<CatalogChoice>> List(Guid verifiedTenantId, CancellationToken ct);
    Task<CatalogChoice?> Find(Guid verifiedTenantId, Guid itemId, CancellationToken ct);
}
