using System.Text.Json;

namespace Enginia360.Integrations;

// Shared bounded Giobby transport: authenticated identity read, one frozen token per sequence, 64 KiB cap, no redirects.
internal sealed class GiobbyWire(HttpClient http, GiobbyHost host, ConnectorOptions options)
{
    internal static bool Text(JsonElement root, string field, string? expected) => root.TryGetProperty(field, out var v) && v.ValueKind == JsonValueKind.String && v.GetString() == expected;
    internal static bool Amount(JsonElement root, string field, decimal expected) => root.TryGetProperty(field, out var v) && v.ValueKind == JsonValueKind.Number && v.TryGetDecimal(out var n) && n == expected;
    internal static bool Success(JsonElement root) => root.ValueKind == JsonValueKind.Object && Amount(root, "responseCode", 200) && Amount(root, "errorCode", 0);

    internal async Task<string?> VerifyIdentity(CancellationToken ct)
    {
        if (host.BaseAddress is null || host.Token() is not { } token || !int.TryParse(host.Value("CompanyId"), out var company) || company <= 0 || string.IsNullOrEmpty(host.Value("Cid"))) return null;
        var identity = await Send(new HttpRequestMessage(HttpMethod.Get, "loggeduser"), token, ct);
        return identity is { ValueKind: JsonValueKind.Object } user && Amount(user, "idCompany", company) && Text(user, "cid", host.Value("Cid")) ? token : null;
    }

    internal async Task<JsonElement?> Send(HttpRequestMessage request, string token, CancellationToken ct)
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
