using System.Globalization;
using System.Net.Http.Json;
using Enginia360.Inventory.Contracts;

namespace Enginia360.Integrations;

// R05.a.8/a.9 standalone type0 receipt. An acknowledgement is durably saved before any detail request.
internal sealed class GiobbyReceiptConnector(HttpClient http, GiobbyHost host, ConnectorOptions options)
{
    private readonly GiobbyWire wire = new(http, host, options);
    private static decimal Number(string value) => decimal.Parse(value, CultureInfo.InvariantCulture);
    internal static string Reference(ReceiptDispatchMessage m) => "E360-GR-" + m.ReceiptId.ToString("N");
    private string? Mapping(string key) => host.Value("Receipt:" + key);
    private object Payload(ReceiptDispatchMessage m) => new
    {
        idDocumentType = 0, idContact = (int?)null, docCurrency = "EUR", payments = Array.Empty<object>(), idVendor = m.VendorId, idBu = Mapping("BusinessUnit"),
        idNumerator = int.Parse(Mapping("Numerator")!, CultureInfo.InvariantCulture),
        docNumber = Reference(m), docDate = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString(CultureInfo.InvariantCulture),
        reference = Reference(m), rows = new[] { new {
            idMaterial = Mapping($"Materials:{m.CatalogItemId}"), idAttributeCombination = 0,
            idPosType = int.Parse(Mapping("PosType")!, CultureInfo.InvariantCulture), description = m.Description,
            quantity = Number(m.Quantity), price = Number(m.UnitPrice), idVat = Mapping("Vat"), idStorage = Mapping("Storage") } }
    };
    private ConnectorResult? Refusal(ReceiptDispatchMessage m) => !host.ReceiptMapped(m) ? new(ConnectorOutcome.NotSent, Code: "mapping_missing")
        : m.DestinationFingerprint != host.ReceiptFingerprint ? new(ConnectorOutcome.NotSent, Code: "destination_binding_mismatch") : null;
    public async Task<ConnectorResult> Submit(ReceiptDispatchMessage m, CancellationToken ct)
    {
        if (Refusal(m) is { } refusal) return refusal;
        var token = await wire.VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.NotSent, Code: "identity_unverified");
        var body = await wire.Send(new HttpRequestMessage(HttpMethod.Post, "purchases/goodsreceipt") { Content = JsonContent.Create(Payload(m)) }, token, ct);
        if (body is { } r && GiobbyWire.Success(r) && r.TryGetProperty("idDocument", out var value) && value.ValueKind == System.Text.Json.JsonValueKind.Number && value.TryGetInt32(out var id) && id > 0)
            return new(ConnectorOutcome.Failure, "GiobbyReceipt-" + id.ToString(CultureInfo.InvariantCulture), "ack_pending");
        return new(ConnectorOutcome.Failure, Code: "ack_unknown");
    }
    public async Task<ConnectorResult> Status(ReceiptDispatchMessage m, CancellationToken ct)
    {
        if (Refusal(m) is { } refusal) return refusal;
        var token = await wire.VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.NotSent, Code: "identity_unverified");
        if (m.KnownDocumentId is not > 0)
        {
            // Preregistered reference lookup is negative/unproved in R05.a.9. Even a synthetic positive does not establish safe recovery.
            await wire.Send(new HttpRequestMessage(HttpMethod.Get, $"purchases/goodsreceipt?offset=0&limit=5&freeText={Uri.EscapeDataString(Reference(m))}"), token, ct);
            return new(ConnectorOutcome.Failure, Code: "ack_unknown_hold");
        }
        var id = m.KnownDocumentId.Value;
        var body = await wire.Send(new HttpRequestMessage(HttpMethod.Get, $"purchases/{id}/goodsreceipt?onlyHeaderData=false"), token, ct);
        if (body is not { } root || !GiobbyWire.Success(root) || !root.TryGetProperty("document", out var d) || d.ValueKind != System.Text.Json.JsonValueKind.Object
            || !GiobbyWire.Amount(d,"id",id) || !GiobbyWire.Amount(d,"idDocumentType",0) || !GiobbyWire.Text(d,"reference",Reference(m))
            || !GiobbyWire.Text(d,"docNumber",Reference(m)) || !GiobbyWire.Text(d,"idVendor",m.VendorId) || !GiobbyWire.Text(d,"idBu",Mapping("BusinessUnit"))
            || !GiobbyWire.Amount(d,"idNumerator",int.Parse(Mapping("Numerator")!,CultureInfo.InvariantCulture))
            || !d.TryGetProperty("rows",out var rows) || rows.ValueKind != System.Text.Json.JsonValueKind.Array || rows.GetArrayLength()!=1)
            return new(ConnectorOutcome.Failure, Code:"readback_mismatch");
        var row=rows[0];
        if (row.ValueKind != System.Text.Json.JsonValueKind.Object || !GiobbyWire.Text(row,"description",m.Description)
            || !GiobbyWire.Amount(row,"quantity",Number(m.Quantity)) || !GiobbyWire.Amount(row,"price",Number(m.UnitPrice))
            || !GiobbyWire.Text(row,"idMaterial",Mapping($"Materials:{m.CatalogItemId}")) || !GiobbyWire.Text(row,"idStorage",Mapping("Storage"))
            || !GiobbyWire.Text(row,"idVat",Mapping("Vat")) || !GiobbyWire.Amount(row,"idPosType",int.Parse(Mapping("PosType")!,CultureInfo.InvariantCulture)))
            return new(ConnectorOutcome.Failure, Code:"readback_mismatch");
        return new(ConnectorOutcome.Completed,"GiobbyReceipt-"+id.ToString(CultureInfo.InvariantCulture));
    }
}
