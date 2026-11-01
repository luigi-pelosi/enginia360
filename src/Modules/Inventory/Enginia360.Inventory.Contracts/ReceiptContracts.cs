namespace Enginia360.Inventory.Contracts;

public sealed record ReceiptIntentRequest(Guid Id, string Quantity);
public sealed record ReceiptDestinationBinding(string? Descriptor);
public sealed record ReceiptOutboxEnvelope(Guid TenantId, Guid LegalEntityId, Guid ReceiptId);
public sealed record ReceiptDispatchMessage(Guid TenantId, Guid LegalEntityId, Guid SiteId, Guid ReceiptId,
    Guid CatalogItemId, string Description, string Quantity, string UnitPrice, string VendorId, string VendorName,
    string DestinationFingerprint, int? KnownDocumentId = null);
public sealed record ReceiptDelivery(string State, string? LastError, int? KnownDocumentId);
public interface IReceiptDeliveries
{
    Task<IReadOnlyDictionary<Guid,ReceiptDelivery>> Read(Guid verifiedTenantId, IReadOnlyCollection<Guid> receiptIds, CancellationToken ct);
}
public static class ReceiptDispatchReadout
{
    public static void Apply(System.Text.Json.Nodes.JsonObject state,IReadOnlyDictionary<Guid,ReceiptDelivery> deliveries)
    {
        if (state["receipts"] is not System.Text.Json.Nodes.JsonArray receipts) return;
        foreach (var item in receipts)
        {
            if (item is not System.Text.Json.Nodes.JsonObject receipt || !Guid.TryParse(receipt["id"]?.GetValue<string>(),out var id)) continue;
            var delivery=deliveries.GetValueOrDefault(id) ?? new ReceiptDelivery("Queued",null,null);
            receipt["delivery"]=System.Text.Json.JsonSerializer.SerializeToNode(delivery,new System.Text.Json.JsonSerializerOptions { PropertyNamingPolicy=System.Text.Json.JsonNamingPolicy.CamelCase });
        }
    }
}
public interface IReceiptDispatchOutbox
{
    Task<IReadOnlyList<ReceiptOutboxEnvelope>> Pending(int limit, int offset, CancellationToken ct);
    Task<ReceiptDispatchMessage?> Read(ReceiptOutboxEnvelope envelope, CancellationToken ct);
    Task<bool> Record(ReceiptOutboxEnvelope envelope, string externalReference, CancellationToken ct);
}
