using System.Net.Http.Json;
using System.Globalization;
using System.Text.Json;
using Enginia360.Workshop.Contracts;

namespace Enginia360.Integrations;

// Only the sales-order surface; create acknowledgement is never a business outcome.
internal sealed class GiobbySalesOrderConnector(HttpClient http, GiobbyHost host, ConnectorOptions options) : IAdministrativeConnector
{
    private static decimal Number(string value) => decimal.Parse(value, CultureInfo.InvariantCulture);
    private object Payload(AdministrativeDispatchMessage message) => new
    {
        idDocumentType = 3, idCustomer = host.Value($"Customers:{message.Summary.PayerId}:Id"),
        idContact = int.Parse(host.Value($"Customers:{message.Summary.PayerId}:ContactId")!, CultureInfo.InvariantCulture), idVendor = (string?)null,
        idBu = host.Value("BusinessUnit"), idNumerator = int.Parse(host.Value("Numerator")!, CultureInfo.InvariantCulture),
        docDate = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString(CultureInfo.InvariantCulture), docCurrency = message.Summary.Currency,
        reference = "E360-" + message.RequestId.ToString("N"), payments = Array.Empty<object>(),
        rows = message.Summary.Lines.Select(x => new
        {
            idPosType = 1, idMaterial = host.Value($"Materials:{x.CatalogItemId}"), description = x.CatalogLabel,
            quantity = Number(x.Quantity), price = Number(x.UnitPrice), dsc1 = Number(x.DiscountPercent),
            idVat = host.Tax(x.TaxRate), idStorage = host.Value("Storage")
        }).ToArray()
    };
    public async Task<ConnectorResult> Submit(AdministrativeDispatchMessage message, CancellationToken ct)
    {
        if (!host.Mapped(message)) return new(ConnectorOutcome.Failure, Code: "mapping_missing");
        var token = await VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.Failure, Code: "identity_unverified");
        var body = await Send(new HttpRequestMessage(HttpMethod.Post, "sales/orders?simulation=false") { Content = JsonContent.Create(Payload(message)) }, token, ct);
        if (body is { } root && Success(root) && root.TryGetProperty("idDocument", out var value) && value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var id) && id > 0)
        {
            return await Readback(message, id, token, ct);
        }
        return new(ConnectorOutcome.Failure, Code: "readback_unverified");
    }
    private static string Reference(AdministrativeDispatchMessage m) => "E360-" + m.RequestId.ToString("N");
    private static bool Text(JsonElement root, string field, string? expected) => root.TryGetProperty(field, out var v) && v.ValueKind == JsonValueKind.String && v.GetString() == expected;
    private static bool Amount(JsonElement root, string field, decimal expected) => root.TryGetProperty(field, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetDecimal(out var n) && n == expected;
    private static bool Success(JsonElement root) => root.ValueKind == JsonValueKind.Object && Amount(root, "responseCode", 200) && Amount(root, "errorCode", 0);
    private async Task<ConnectorResult> Readback(AdministrativeDispatchMessage message, int id, string token, CancellationToken ct)
    {
        var body = await Send(new HttpRequestMessage(HttpMethod.Get, $"sales/{id}/orders"), token, ct);
        if (body is not { } root || !Success(root) || !root.TryGetProperty("document", out var d)
            || d.ValueKind != JsonValueKind.Object || !Amount(d, "id", id) || !Amount(d, "idDocumentType", 3)
            || !Text(d, "reference", Reference(message)) || !Text(d, "idCustomer", host.Value($"Customers:{message.Summary.PayerId}:Id"))
            || !Amount(d, "idContact", int.Parse(host.Value($"Customers:{message.Summary.PayerId}:ContactId")!, CultureInfo.InvariantCulture))
            || !Text(d, "docStatus", "CREATED") || !Amount(d, "totalAmount", Number(message.Summary.Total))
            || !d.TryGetProperty("rows", out var rows) || rows.ValueKind != JsonValueKind.Array || rows.GetArrayLength() != message.Summary.Lines.Count)
            return new(ConnectorOutcome.Failure, Code: "readback_mismatch");
        for (var i = 0; i < rows.GetArrayLength(); i++)
        {
            var row = rows[i]; var line = message.Summary.Lines[i];
            if (row.ValueKind != JsonValueKind.Object || !Amount(row, "idPosType", 1) || !Amount(row, "idPos", i + 1)
                || !Text(row, "idMaterial", host.Value($"Materials:{line.CatalogItemId}")) || !Text(row, "idStorage", host.Value("Storage"))
                || !Amount(row, "quantity", Number(line.Quantity)) || !Amount(row, "price", Number(line.UnitPrice))
                || (row.TryGetProperty("dsc1", out _) ? !Amount(row, "dsc1", Number(line.DiscountPercent)) : Number(line.DiscountPercent) != 0)
                || (row.TryGetProperty("idVat", out _) && !Text(row, "idVat", host.Tax(line.TaxRate))))
                return new(ConnectorOutcome.Failure, Code: "readback_mismatch");
        }
        return new(ConnectorOutcome.Completed, "GiobbyOrder-" + id.ToString(CultureInfo.InvariantCulture));
    }
    public async Task<ConnectorResult> Status(AdministrativeDispatchMessage message, CancellationToken ct)
    {
        if (!host.Mapped(message)) return new(ConnectorOutcome.Failure, Code: "mapping_missing");
        var token = await VerifyIdentity(ct);
        if (token is null) return new(ConnectorOutcome.Failure, Code: "identity_unverified");
        var name = Uri.EscapeDataString(host.Value($"Customers:{message.Summary.PayerId}:LookupName")!);
        var body = await Send(new HttpRequestMessage(HttpMethod.Get, $"sales/orders?offset=0&limit=5&freeText={name}&docStatus=CREATED"), token, ct);
        if (body is not { } root || !Success(root)
            || !root.TryGetProperty("documentsHeaders", out var headers) || headers.ValueKind != JsonValueKind.Array
            || !root.TryGetProperty("metadata", out var metadata) || metadata.ValueKind != JsonValueKind.Object
            || !Amount(metadata, "limit", 5) || !Amount(metadata, "offset", 0)
            || !metadata.TryGetProperty("totalCount", out var total) || total.ValueKind != JsonValueKind.Number || !total.TryGetInt32(out var count) || count < 0)
            return new(ConnectorOutcome.Failure, Code: "invalid_response");
        if (count != headers.GetArrayLength() || count >= 5) return new(ConnectorOutcome.Failure, Code: "lookup_truncated");
        var matches = headers.EnumerateArray().Where(h => h.ValueKind == JsonValueKind.Object && Amount(h, "idDocumentType", 3)
            && Text(h, "reference", Reference(message)) && Text(h, "idCustomer", host.Value($"Customers:{message.Summary.PayerId}:Id")) && Text(h, "docStatus", "CREATED")).ToArray();
        if (matches.Length != 1) return new(ConnectorOutcome.Failure, Code: matches.Length == 0 ? "lookup_empty" : "lookup_nonunique");
        if (!matches[0].TryGetProperty("id", out var value) || value.ValueKind != JsonValueKind.Number || !value.TryGetInt32(out var id) || id <= 0)
            return new(ConnectorOutcome.Failure, Code: "invalid_response");
        return await Readback(message, id, token, ct);
    }

    private async Task<string?> VerifyIdentity(CancellationToken ct)
    {
        if (host.BaseAddress is null || host.Token() is not { } token || !int.TryParse(host.Value("CompanyId"), out var company) || company <= 0 || string.IsNullOrEmpty(host.Value("Cid"))) return null;
        var identity = await Send(new HttpRequestMessage(HttpMethod.Get, "loggeduser"), token, ct);
        return identity is { ValueKind: JsonValueKind.Object } user && Amount(user, "idCompany", company) && Text(user, "cid", host.Value("Cid")) ? token : null;
    }

    private async Task<JsonElement?> Send(HttpRequestMessage request, string token, CancellationToken ct)
    {
        using (request)
        using (var deadline = CancellationTokenSource.CreateLinkedTokenSource(ct))
        {
            deadline.CancelAfter(options.Timeout);
            try
            {
                request.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", token);
                request.Headers.Add("X-Giobby-Realm", "api-server");
                request.Headers.Accept.ParseAdd("application/json");
                using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, deadline.Token);
                if (response.StatusCode != System.Net.HttpStatusCode.OK) return null;
                await using var stream = await response.Content.ReadAsStreamAsync(deadline.Token);
                var buffer = new byte[65537]; var length = 0;
                while (length < buffer.Length)
                {
                    var read = await stream.ReadAsync(buffer.AsMemory(length), deadline.Token);
                    if (read == 0) break;
                    length += read;
                }
                if (length > 65536) return null;
                using var json = JsonDocument.Parse(buffer.AsMemory(0, length));
                return json.RootElement.Clone();
            }
            catch (HttpRequestException) { return null; }
            catch (System.IO.IOException) { return null; }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested) { return null; }
            catch (JsonException) { return null; }
        }
    }
}
