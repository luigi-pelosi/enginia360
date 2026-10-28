using System.Text.Json;
using Enginia360.Workshop.Contracts;
using Microsoft.Extensions.Configuration;

namespace Enginia360.Integrations;

// Host-owned, non-secret Giobby purchasing destination, frozen into each intent. Not a connector.
// Purchase mappings are bound at source creation, independently of the sales fingerprint. Old descriptors are never backfilled.
internal static class PurchaseDestination
{
    internal static string Fingerprint(AdministrativeConnectorBinding binding, IEnumerable<KeyValuePair<string, string?>> values)
    {
        var mappings = new SortedDictionary<string, string?>(StringComparer.Ordinal);
        foreach (var pair in values.Where(x => x.Key.StartsWith("PurchaseOrder:", StringComparison.Ordinal) && x.Value is not null)) mappings[pair.Key] = pair.Value;
        return Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(
            "GiobbyPurchaseV1\n1\n" + binding.DestinationFingerprint + "\n" + JsonSerializer.Serialize(mappings))));
    }
    public static string? Descriptor(AdministrativeConnectorBinding binding, IConfiguration giobby)
    {
        if (binding.Kind != "GiobbyV1" || binding.ProtocolVersion != 1 || binding.DestinationFingerprint.Length != 64) return null;
        if (!Guid.TryParse(giobby["PurchaseStockSourceId"], out var source) || source == Guid.Empty
            || !Guid.TryParse(giobby["PurchaseStockProfileId"], out var profile) || profile == Guid.Empty) return null;
        if (!Guid.TryParse(giobby["TenantId"], out var tenant) || !Guid.TryParse(giobby["LegalEntityId"], out var company) || !Guid.TryParse(giobby["SiteId"], out var site)) return null;
        return JsonSerializer.Serialize(new { kind = "GiobbyPurchaseV1", version = 1, fingerprint = Fingerprint(binding, giobby.AsEnumerable(true)),
            tenantId = tenant.ToString(), legalEntityId = company.ToString(), siteId = site.ToString(),
            stockSourceId = source.ToString(), stockProfileId = profile.ToString() });
    }
}
