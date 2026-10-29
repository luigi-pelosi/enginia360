namespace Enginia360.Inventory.Contracts;

// Server-owned envelope from the Inventory purchase outbox: the only source of a purchase dispatcher's tenant/company context.
public sealed record PurchaseOutboxEnvelope(Guid TenantId, Guid LegalEntityId, Guid IntentId);

// Immutable frozen facts of one priced Held intent. UnitPrice is the accepted q6 purchase price (D91); never recalculated.
public sealed record PurchaseDispatchMessage(Guid TenantId, Guid LegalEntityId, Guid SiteId, Guid IntentId, Guid CatalogItemId,
    string Description, string Quantity, string UnitPrice, string VendorId, string VendorName, string DestinationFingerprint);

public sealed record PurchaseOutcome(string Status, string? ExternalReference, string? RejectionCode);

// Implemented by Inventory, owner of intents, prices and purchase outcomes; used by the purchase dispatcher.
public interface IPurchaseDispatchOutbox
{
    Task<IReadOnlyList<PurchaseOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct);
    Task<PurchaseDispatchMessage?> Read(PurchaseOutboxEnvelope envelope, CancellationToken ct);
    // Insert-only and idempotent: an identical outcome is accepted again, a different one is refused.
    Task<bool> Record(PurchaseOutboxEnvelope envelope, PurchaseOutcome outcome, CancellationToken ct);
}

// Technical delivery state owned by Integrations (Queued/Uncertain/Completed + bounded error code). Never a business outcome or stock authority.
public sealed record PurchaseDelivery(string State, string? LastError);

// Implemented by Integrations, the owner of purchase_dispatches; Inventory reads delivery state only through this contract, never the table.
public interface IPurchaseDeliveries
{
    Task<IReadOnlyDictionary<Guid, PurchaseDelivery>> Read(Guid verifiedTenantId, IReadOnlyCollection<Guid> intentIds, CancellationToken ct);
}
