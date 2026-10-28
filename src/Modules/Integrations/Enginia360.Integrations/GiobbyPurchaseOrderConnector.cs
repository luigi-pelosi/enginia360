using System.Globalization;
using System.Net.Http.Json;
using System.Text.Json;
using Enginia360.Inventory.Contracts;

namespace Enginia360.Integrations;

// Purchase order only (document type 2). The acknowledgement is a receipt, never a completion.
internal sealed class GiobbyPurchaseOrderConnector(HttpClient http, GiobbyHost host, ConnectorOptions options) : IPurchaseConnector
{
    private readonly GiobbyWire wire = new(http, host, options);
    private static decimal Number(string value) => decimal.Parse(value, CultureInfo.InvariantCulture);
    internal static string Reference(PurchaseDispatchMessage m) => "E360-PO-" + m.IntentId.ToString("N");
    private object Payload(PurchaseDispatchMessage m) => new
    {
        idDocumentType = 2, idOrderType = 1, idContact = (int?)null, idVendor = m.VendorId, idBu = host.Purchase("BusinessUnit"),
        idNumerator = int.Parse(host.Purchase("Numerator")!, CultureInfo.InvariantCulture),
        docDate = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString(CultureInfo.InvariantCulture), docCurrency = "EUR",
        reference = Reference(m), payments = Array.Empty<object>(),
        rows = new[]
        {
            new
            {
                idMaterial = host.Purchase($"Materials:{m.CatalogItemId}"), idAttributeCombination = 0,
                idPosType = int.Parse(host.Purchase("PosType")!, CultureInfo.InvariantCulture), description = m.Description,
                quantity = Number(m.Quantity), price = Number(m.UnitPrice), idVat = host.Purchase("Vat"), idStorage = host.Purchase("Storage")
            }
        }
    };
    // Fail closed before any HTTP: explicit setup, then the destination frozen with the intent must equal this host's binding (R05.b.0).
    private ConnectorResult? Refusal(PurchaseDispatchMessage m) => !host.PurchaseMapped(m) ? new(ConnectorOutcome.NotSent, Code: "mapping_missing")
        : m.DestinationFingerprint != host.PurchaseFingerprint ? new(ConnectorOutcome.NotSent, Code: "destination_binding_mismatch") : null;
    public async Task<ConnectorResult> Submit(PurchaseDispatchMessage message, CancellationToken ct)
    {
        if (Refusal(message) is { } refusal) return refusal;
        var token = await wire.VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.NotSent, Code: "identity_unverified");
        var body = await wire.Send(new HttpRequestMessage(HttpMethod.Post, "purchases/orders?simulation=false") { Content = JsonContent.Create(Payload(message)) }, token, ct);
        if (body is { } root && GiobbyWire.Success(root) && root.TryGetProperty("idDocument", out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var id) && id > 0)
            return await Readback(message, id, token, ct);
        return new(ConnectorOutcome.Failure, Code: "readback_unverified");
    }
    // Lost-response recovery is GET only: the vendor's name plus CREATED, newest first, then an exact client-side reference filter (R05.a.7 §5).
    // totalCount is not a completeness signal; an empty, full-without-match or ambiguous page is held, never "absent" and never a replay.
    public async Task<ConnectorResult> Status(PurchaseDispatchMessage message, CancellationToken ct)
    {
        if (Refusal(message) is { } refusal) return refusal;
        var token = await wire.VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.NotSent, Code: "identity_unverified");
        var name = Uri.EscapeDataString(message.VendorName);
        var body = await wire.Send(new HttpRequestMessage(HttpMethod.Get, $"purchases/orders?offset=0&limit=5&freeText={name}&docStatus=CREATED"), token, ct);
        if (body is not { } root || !GiobbyWire.Success(root)
            || !root.TryGetProperty("documentsHeaders", out var headers) || headers.ValueKind != JsonValueKind.Array || headers.GetArrayLength() > 5)
            return new(ConnectorOutcome.Failure, Code: "invalid_response");
        if (headers.GetArrayLength() == 5) return new(ConnectorOutcome.Failure, Code: "lookup_truncated");
        var matches = headers.EnumerateArray().Where(h => h.ValueKind == JsonValueKind.Object && GiobbyWire.Amount(h, "idDocumentType", 2)
            && GiobbyWire.Text(h, "reference", Reference(message)) && GiobbyWire.Text(h, "idVendor", message.VendorId) && GiobbyWire.Text(h, "docStatus", "CREATED")).ToArray();
        if (matches.Length == 0) return new(ConnectorOutcome.Failure, Code: headers.GetArrayLength() >= 5 ? "lookup_truncated" : "lookup_empty");
        if (matches.Length > 1) return new(ConnectorOutcome.Failure, Code: "lookup_nonunique");
        if (!matches[0].TryGetProperty("id", out var value) || value.ValueKind != JsonValueKind.Number || !value.TryGetInt32(out var id) || id <= 0)
            return new(ConnectorOutcome.Failure, Code: "invalid_response");
        return await Readback(message, id, token, ct);
    }

    // Exact row facts only. The header total is rounded to two decimals by the provider and is deliberately not compared (R05.a.7).
    private async Task<ConnectorResult> Readback(PurchaseDispatchMessage m, int id, string token, CancellationToken ct)
    {
        var body = await wire.Send(new HttpRequestMessage(HttpMethod.Get, $"purchases/{id}/orders"), token, ct);
        if (body is not { } root || !GiobbyWire.Success(root) || !root.TryGetProperty("document", out var d) || d.ValueKind != JsonValueKind.Object
            || !GiobbyWire.Amount(d, "id", id) || !GiobbyWire.Amount(d, "idDocumentType", 2) || !GiobbyWire.Text(d, "reference", Reference(m))
            || !GiobbyWire.Text(d, "idVendor", m.VendorId) || !GiobbyWire.Text(d, "docStatus", "CREATED")
            || !d.TryGetProperty("rows", out var rows) || rows.ValueKind != JsonValueKind.Array || rows.GetArrayLength() != 1)
            return new(ConnectorOutcome.Failure, Code: "readback_mismatch");
        var row = rows[0];
        if (row.ValueKind != JsonValueKind.Object || !GiobbyWire.Text(row, "description", m.Description) || !GiobbyWire.Amount(row, "quantity", Number(m.Quantity))
            || !GiobbyWire.Amount(row, "price", Number(m.UnitPrice)) || !GiobbyWire.Text(row, "idMaterial", host.Purchase($"Materials:{m.CatalogItemId}"))
            || !GiobbyWire.Text(row, "idStorage", host.Purchase("Storage")) || !GiobbyWire.Text(row, "idVat", host.Purchase("Vat"))
            || !GiobbyWire.Amount(row, "idPosType", int.Parse(host.Purchase("PosType")!, CultureInfo.InvariantCulture)))
            return new(ConnectorOutcome.Failure, Code: "readback_mismatch");
        return new(ConnectorOutcome.Completed, "GiobbyPurchaseOrder-" + id.ToString(CultureInfo.InvariantCulture));
    }
}
