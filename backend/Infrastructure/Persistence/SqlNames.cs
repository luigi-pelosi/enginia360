namespace Enginia360.Infrastructure.Persistence;

// Gli identificatori provengono dai metadati statici, mai dai valori delle richieste.
public static class SqlNames
{
    public static string Identifier(string name)
    {
        ArgumentException.ThrowIfNullOrEmpty(name);
        if (name.Contains('\0')) throw new ArgumentException("Invalid SQL identifier.", nameof(name));
        return "\"" + name.Replace("\"", "\"\"") + "\"";
    }
    // Ambiti finiti: gli identificatori ricevuti non vengono separati né interpretati.
    public static string Table(string name) => Identifier(name is
        "business_partner" or "business_partner_tax_identifier" or "business_partner_address" or
        "business_partner_address_usage" or "business_partner_contact_channel" ? "masterdata" : "foundation")
        + "." + Identifier(name);
}

