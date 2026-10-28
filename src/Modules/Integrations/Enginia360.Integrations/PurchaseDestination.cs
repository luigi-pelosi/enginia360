using System.Text.Json;
using Enginia360.Workshop.Contracts;
using Microsoft.Extensions.Configuration;

namespace Enginia360.Integrations;

// Host-owned, non-secret Giobby purchasing destination, frozen into each intent. Not a connector.
// Only the verified GiobbyV1 binding is accepted; the fingerprint is the already-verified non-secret binding fingerprint.
internal static class PurchaseDestination
{
    public static string? Descriptor(AdministrativeConnectorBinding binding, IConfiguration giobby)
    {
        if (binding.Kind != "GiobbyV1" || binding.ProtocolVersion != 1 || binding.DestinationFingerprint.Length != 64) return null;
        if (!Guid.TryParse(giobby["PurchaseStockSourceId"], out var source) || source == Guid.Empty
            || !Guid.TryParse(giobby["PurchaseStockProfileId"], out var profile) || profile == Guid.Empty) return null;
        if (!Guid.TryParse(giobby["TenantId"], out var tenant) || !Guid.TryParse(giobby["LegalEntityId"], out var company) || !Guid.TryParse(giobby["SiteId"], out var site)) return null;
        return JsonSerializer.Serialize(new { kind = "GiobbyPurchaseV1", version = 1, fingerprint = binding.DestinationFingerprint,
            tenantId = tenant.ToString(), legalEntityId = company.ToString(), siteId = site.ToString(),
            stockSourceId = source.ToString(), stockProfileId = profile.ToString() });
    }
}
