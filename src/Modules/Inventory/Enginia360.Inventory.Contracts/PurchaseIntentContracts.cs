using System.Text.Json.Serialization;
namespace Enginia360.Inventory.Contracts;

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record PurchaseIntentRequest(Guid Id, Guid WarehouseId, Guid SupplierId,
    int? SourceRevision, int? SupplierRevision, int? MappingRevision, string? Quantity);

[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record AcceptedPurchaseIntentRequest(Guid Id, Guid WarehouseId, Guid SupplierId,
    int? SourceRevision, int? SupplierRevision, int? MappingRevision, string? Quantity,
    int? QuoteRevision, int? CatalogVersion, int? AuthorityVersion, string? ManualUnitPurchasePrice);

// Host-owned immutable, non-secret destination. Not a purchase writer or browser input.
public sealed record PurchaseDestinationBinding(string Descriptor);
