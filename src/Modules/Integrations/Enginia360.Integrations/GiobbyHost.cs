using Microsoft.Extensions.Configuration;
using Enginia360.Inventory.Contracts;
using Enginia360.Workshop.Contracts;
using System.Globalization;

namespace Enginia360.Integrations;

// Non-secret, host-owned mapping snapshot. Names are lookup hints, never authoritative IDs.
internal sealed class GiobbyHost(IConfiguration section)
{
    private readonly Dictionary<string, string?> values = section.AsEnumerable(true).ToDictionary(x => x.Key, x => x.Value);
    internal string? Value(string key) => values.GetValueOrDefault(key);
    internal string? Tax(string rate) => decimal.TryParse(rate, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var n)
        ? Value("Taxes:" + n.ToString("0.000000", CultureInfo.InvariantCulture)) : null;
    internal AdministrativeConnectorBinding Binding
    {
        get
        {
            if (BaseAddress is null || !Text("CompanyAlias") || !PositiveInt("CompanyId") || !Text("Cid") || !Guid.TryParse(Value("TenantId"), out _) || !Guid.TryParse(Value("LegalEntityId"), out _) || !Guid.TryParse(Value("SiteId"), out _))
                return new("Unavailable", 0, "");
            var descriptor = new SortedDictionary<string, string?>(StringComparer.Ordinal);
            foreach (var pair in values.Where(x => x.Key != "TokenFile" && !x.Key.StartsWith("PurchaseOrder:", StringComparison.Ordinal) && x.Value is not null)) descriptor[pair.Key] = pair.Value;
            descriptor["BaseUrl"] = BaseAddress.AbsoluteUri;
            descriptor["DocumentType"] = "sales-order:3";
            return new("GiobbyV1", 1, Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(
                System.Text.Encoding.UTF8.GetBytes("GiobbyV1\n1\n" + System.Text.Json.JsonSerializer.Serialize(descriptor)))));
        }
    }
    internal Uri? BaseAddress => Uri.TryCreate(Value("BaseUrl"), UriKind.Absolute, out var uri)
        && uri.Scheme == "https" && uri.Port is 443 or 8443 && uri.UserInfo.Length == 0 && uri.Query.Length == 0 && uri.Fragment.Length == 0
        && uri.AbsolutePath.EndsWith('/') && values.Any(x => x.Key.StartsWith("AllowedHosts:", StringComparison.Ordinal) && string.Equals(x.Value, uri.IdnHost, StringComparison.OrdinalIgnoreCase)) ? uri : null;

    // Host-mounted secret only: never configuration payload, database, response, log or command argument.
    // Token acquisition/refresh/discovery is deliberately outside this offline increment.
    internal string? Token()
    {
        var path = Value("TokenFile");
        if (path is null || !Path.IsPathFullyQualified(path)) return null;
        try
        {
            using var file = File.OpenRead(path);
            if (file.Length is < 1 or > 8192) return null;
            using var reader = new StreamReader(file);
            var token = reader.ReadToEnd().Trim();
            return token.Length > 0 && token.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_' or '.' or '~' or '+' or '/' or '=') ? token : null;
        }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }
    private bool Text(string key) => Value(key) is { Length: > 0 and <= 200 } text && !text.Any(char.IsControl);
    private bool Scope(string key, Guid id) => id != Guid.Empty && Guid.TryParse(Value(key), out var configured) && configured == id;
    private bool PositiveInt(string key) => int.TryParse(Value(key), out var id) && id > 0;
    internal bool Mapped(AdministrativeDispatchMessage m) => Scope("TenantId", m.TenantId) && Scope("LegalEntityId", m.LegalEntityId)
        && Scope("SiteId", m.SiteId) && m.ContractVersion == 1 && m.RequestId != Guid.Empty
        && Text($"Customers:{m.Summary.PayerId}:Id") && PositiveInt($"Customers:{m.Summary.PayerId}:ContactId")
        && Text($"Customers:{m.Summary.PayerId}:LookupName") && Text("Storage") && Text("BusinessUnit") && PositiveInt("Numerator")
        && m.Summary.Currency == "EUR" && m.Summary.Lines.Count is > 0 and <= 100
        && m.Summary.Lines.All(x => x.PayerId == m.Summary.PayerId && x.Kind is "Part" or "Service"
            && Text($"Materials:{x.CatalogItemId}") && Tax(x.TaxRate) is { Length: > 0 and <= 200 }
            && Numeric(x.Quantity, 0.000001m, 999999999m) && Numeric(x.UnitPrice, 0, 999999999m) && Numeric(x.DiscountPercent, 0, 100));
    // Purchase-order setup: every key is explicit host configuration; there are no invented defaults.
    internal string? Purchase(string key) => Value("PurchaseOrder:" + key);
    internal bool PurchaseMapped(PurchaseDispatchMessage m) => Scope("TenantId", m.TenantId) && Scope("LegalEntityId", m.LegalEntityId)
        && Scope("SiteId", m.SiteId) && m.IntentId != Guid.Empty
        && Purchase("DocumentType") == "2" && Purchase("OrderType") == "1" && Purchase("Currency") == "EUR" && Purchase("Payments") == "none"
        && PurchaseText("BusinessUnit") && PurchaseText("Vat") && PurchaseText("Storage") && PurchaseText($"Materials:{m.CatalogItemId}")
        && int.TryParse(Purchase("Numerator"), NumberStyles.None, CultureInfo.InvariantCulture, out var numerator) && numerator > 0
        && int.TryParse(Purchase("PosType"), NumberStyles.None, CultureInfo.InvariantCulture, out var pos) && pos > 0
        && PlainText(m.VendorId) && PlainText(m.VendorName) && PlainText(m.Description)
        && Numeric(m.Quantity, 0.000001m, 999999.999999m) && Numeric(m.UnitPrice, 0, 999999.999999m);
    private bool PurchaseText(string key) => Purchase(key) is { Length: > 0 and <= 200 } text && !text.Any(char.IsControl);
    private static bool PlainText(string value) => value is { Length: > 0 and <= 200 } && !value.Any(char.IsControl);
    private static bool Numeric(string value, decimal min, decimal max) => decimal.TryParse(value,
        NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var number) && number >= min && number <= max && decimal.Round(number, 6) == number;
}
