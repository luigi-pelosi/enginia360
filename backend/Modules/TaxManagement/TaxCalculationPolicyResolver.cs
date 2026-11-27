using Enginia360.Infrastructure.Persistence;
using System.Text.Json.Serialization;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public sealed record TaxCalculationCurrency(Guid Id, string Code,
    [property: JsonPropertyName("minor_units")] int MinorUnits, long Version);
public sealed record TaxCalculationResolvedPolicy(TaxCalculationPolicy Policy, TaxCalculationCurrency Currency);

/// <summary>Policy tecnica server-side; il catalogo valute rimane in sola lettura, senza row lock.</summary>
public static class TaxCalculationPolicyResolver
{
    public static async Task<TaxCalculationResolvedPolicy> Resolve(AppDb db, string currency)
    {
        Require(currency == "EUR", "tax_calculation_currency_not_supported", field: "currency");
        var row = (await Rows(db,
            "SELECT id,code,minor_units,version,is_enabled FROM foundation.currency WHERE code=@code",
            ("code", currency))).SingleOrDefault();
        Require(row != null && row["is_enabled"] is true,
            "tax_calculation_currency_unavailable", 422, "currency");
        Require(row!["minor_units"] is int scale && scale == 2,
            "tax_calculation_currency_scale_not_supported", 422, "currency");
        return new(TaxCalculationPolicies.Standard, new((Guid)row["id"]!,
            (string)row["code"]!, 2, Convert.ToInt64(row["version"])));
    }
}
