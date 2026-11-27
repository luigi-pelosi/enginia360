using System.Text.Json;

namespace Enginia360.Modules.TaxManagement;

public static class TaxTerritorialityResolver
{
    public static readonly DateOnly SupportedFrom = new(2026, 11, 26);

    public static TaxTerritorialityOutcome Resolve(TaxDeterminationContext context)
    {
        var missing = new SortedSet<string>(StringComparer.Ordinal);
        var unsupported = false;
        void Text(string? actual, string key, params string[] allowed)
        {
            if (string.IsNullOrEmpty(actual)) missing.Add(key);
            else if (!allowed.Contains(actual, StringComparer.Ordinal)) unsupported = true;
        }
        JsonElement? Fact(string key)
        {
            return context.Fields.TryGetValue(key, out var value) && value.HasValue &&
                value.Value.ValueKind is not (JsonValueKind.Null or JsonValueKind.Undefined) ? value : null;
        }
        void EnumFact(string key, string expected)
        {
            var value = Fact(key);
            if (value == null || value.Value.ValueKind != JsonValueKind.String) missing.Add(key);
            else if (value.Value.GetString() != expected) unsupported = true;
        }
        void Country(string key)
        {
            var value = Fact(key);
            if (value == null || value.Value.ValueKind != JsonValueKind.String ||
                value.Value.GetString()?.Length != 36 ||
                !Guid.TryParseExact(value.Value.GetString(), "D", out var id) || id == Guid.Empty) missing.Add(key);
            else if (context.ItalyCountryId != Guid.Empty && id != context.ItalyCountryId) unsupported = true;
        }
        bool? Boolean(string key)
        {
            var value = Fact(key);
            if (value == null || value.Value.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
            { missing.Add(key); return null; }
            return value.Value.GetBoolean();
        }
        if (context.TaxDate < SupportedFrom) unsupported = true;
        if (context.ItalyCountryId == Guid.Empty) missing.Add("italyCountryId");
        Text(context.TaxTypeCode, "taxType", "VAT");
        Text(context.OperationType, "transaction.operationType", "SALE", "PURCHASE");
        Text(context.CompanyRegimeCode, "company.taxRegime", "ORDINARY");
        Text(context.ItemKind, "item.nature", "GOOD", "SERVICE");
        Country("company.establishmentCountry");
        Country("company.registrationCountry");
        Country("partner.establishmentCountry");
        var acting = Boolean("partner.actingAsTaxablePerson");
        if (context.OperationType == "PURCHASE" && acting == false) unsupported = true;
        if (Boolean("transaction.ordinaryVatTerritoryConfirmed") == false) unsupported = true;
        EnumFact("transaction.specialTaxTreatment", "NONE");
        if (context.ItemKind == "GOOD")
        {
            EnumFact("transaction.operationCategory", "ORDINARY_MOVABLE_GOODS");
            EnumFact("transaction.goodsCustomsStatus", "NATIONAL_OR_UNION");
            Country("transaction.goodsLocationCountry");
            Country("transaction.dispatchCountry");
            Country("transaction.destinationCountry");
        }
        else if (context.ItemKind == "SERVICE")
        {
            EnumFact("transaction.operationCategory", "GENERAL_SERVICES");
            Country("transaction.serviceLocationCountry");
        }
        // Un fatto positivamente fuori perimetro prevale sui fatti ancora mancanti.
        if (unsupported) return new("UNSUPPORTED_OPERATION", null, null, null, null, missing.ToArray());
        if (missing.Count > 0) return new("INCOMPLETE_CONTEXT", null, null, null, null, missing.ToArray());
        var article = context.ItemKind == "GOOD" ? "7-bis" : "7-ter";
        var legal = context.TaxDate < new DateOnly(2027, 1, 1)
            ? $"DPR 633/1972, art. {article}"
            : $"TU allegato al D.Lgs. 10/2026, art. {(context.ItemKind == "GOOD" ? "15" : "17")}";
        return new("SUCCESS", context.ItalyCountryId, context.ItalyCountryId, "DOMESTIC", legal, Array.Empty<string>());
    }
}
