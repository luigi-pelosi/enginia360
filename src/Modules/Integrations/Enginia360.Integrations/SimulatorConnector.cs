using System.Net;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Workshop.Contracts;

namespace Enginia360.Integrations;

internal enum ConnectorOutcome { Completed, Received, Rejected, NotFound, Failure }
internal sealed record ConnectorResult(ConnectorOutcome Outcome, string? ExternalReference = null, string? Code = null);

// Anti-corruption layer for simulator contract v1. The domain never sees external fields or HTTP codes;
// an HTTP 200 alone is never a business confirmation (T07).
internal sealed partial class SimulatorConnector(HttpClient http)
{
    private const int MaxResponseBytes = 65536;
    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$", RegexOptions.CultureInvariant)]
    private static partial Regex Reference();
    [GeneratedRegex(@"^[a-z0-9_]{1,64}$", RegexOptions.CultureInvariant)]
    private static partial Regex Code();

    internal Task<ConnectorResult> Submit(AdministrativeDispatchMessage message, CancellationToken ct)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "v1/administrative-requests")
        {
            Content = new StringContent(JsonSerializer.Serialize(Payload(message)), Encoding.UTF8, "application/json")
        };
        // Receiver-side deduplication key: the stable owner-local request identifier.
        request.Headers.Add("Idempotency-Key", message.RequestId.ToString());
        return Send(request, message.RequestId, ct);
    }

    internal Task<ConnectorResult> Status(AdministrativeDispatchMessage message, CancellationToken ct) =>
        Send(new HttpRequestMessage(HttpMethod.Get, $"v1/administrative-requests/{message.RequestId}"), message.RequestId, ct);

    // Minimized technical payload: identifiers and amounts only; no names, labels, tenant or credentials (T11).
    private static object Payload(AdministrativeDispatchMessage m) => new
    {
        contractVersion = m.ContractVersion, requestId = m.RequestId, orderId = m.OrderId, companyId = m.LegalEntityId, siteId = m.SiteId,
        payerId = m.Summary.PayerId, currency = m.Summary.Currency, netAmount = m.Summary.NetAmount, taxAmount = m.Summary.TaxAmount,
        total = m.Summary.Total,
        lines = m.Summary.Lines.Select(x => new
        {
            lineId = x.Id, kind = x.Kind, catalogItemId = x.CatalogItemId, quantity = x.Quantity, unitPrice = x.UnitPrice,
            discountPercent = x.DiscountPercent, netAmount = x.NetAmount, taxRate = x.TaxRate, payerId = x.PayerId
        }).ToArray()
    };

    private async Task<ConnectorResult> Send(HttpRequestMessage request, Guid requestId, CancellationToken ct)
    {
        using (request)
        {
            try
            {
                using var response = await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, ct);
                await using var stream = await response.Content.ReadAsStreamAsync(ct);
                var buffer = new byte[MaxResponseBytes + 1];
                var length = 0;
                int read;
                while (length <= MaxResponseBytes && (read = await stream.ReadAsync(buffer.AsMemory(length), ct)) > 0) length += read;
                if (length > MaxResponseBytes) return new(ConnectorOutcome.Failure, Code: "invalid_response");
                return Interpret(response.StatusCode, buffer.AsSpan(0, length), requestId);
            }
            catch (HttpRequestException) { return new(ConnectorOutcome.Failure, Code: "connection"); }
            catch (TaskCanceledException) when (!ct.IsCancellationRequested) { return new(ConnectorOutcome.Failure, Code: "timeout"); }
        }
    }

    internal static ConnectorResult Interpret(HttpStatusCode status, ReadOnlySpan<byte> body, Guid requestId)
    {
        JsonElement root;
        try { root = JsonDocument.Parse(body.ToArray()).RootElement; }
        catch (JsonException) { return new(ConnectorOutcome.Failure, Code: (int)status >= 500 ? "unavailable" : "invalid_response"); }
        string? Text(string name) => root.ValueKind == JsonValueKind.Object && root.TryGetProperty(name, out var value)
            && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
        var echoed = Guid.TryParse(Text("requestId"), out var echo) && echo == requestId;
        var state = Text("status");
        if (status == HttpStatusCode.OK && echoed && state == "Completed" && Text("externalReference") is { } reference && Reference().IsMatch(reference))
            return new(ConnectorOutcome.Completed, reference);
        if (status == HttpStatusCode.Accepted && echoed && state == "Received") return new(ConnectorOutcome.Received);
        if (status == HttpStatusCode.UnprocessableEntity && echoed && state == "Rejected" && Text("code") is { } code && Code().IsMatch(code))
            return new(ConnectorOutcome.Rejected, Code: code);
        if (status == HttpStatusCode.NotFound && echoed && state == "NotFound") return new(ConnectorOutcome.NotFound);
        return new(ConnectorOutcome.Failure, Code: (int)status >= 500 ? "unavailable" : "invalid_response");
    }
}
