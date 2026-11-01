using System.Text.Json;
using Enginia360.Workshop.Contracts;
using Microsoft.Extensions.Configuration;

namespace Enginia360.Integrations;

// Non-secret receipt-specific mappings; independent of purchase/sales mapping changes.
internal static class ReceiptDestination
{
    internal static string Fingerprint(AdministrativeConnectorBinding binding, IEnumerable<KeyValuePair<string,string?>> values)
    {
        var mappings = new SortedDictionary<string,string?>(StringComparer.Ordinal);
        foreach (var pair in values.Where(p => p.Key.StartsWith("Receipt:",StringComparison.Ordinal) && p.Value is not null)) mappings[pair.Key]=pair.Value;
        return Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(
            "GiobbyReceiptV1\n1\n"+binding.DestinationFingerprint+"\n"+JsonSerializer.Serialize(mappings))));
    }
    internal static string? Descriptor(AdministrativeConnectorBinding binding, IConfiguration giobby)
    {
        var purchase = PurchaseDestination.Descriptor(binding,giobby);
        if (purchase is null) return null;
        var value = System.Text.Json.Nodes.JsonNode.Parse(purchase)!;
        value["kind"]="GiobbyReceiptV1";
        value["fingerprint"]=Fingerprint(binding,giobby.AsEnumerable(true));
        return value.ToJsonString();
    }
}
