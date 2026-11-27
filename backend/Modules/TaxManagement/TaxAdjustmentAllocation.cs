using static Enginia360.Modules.TaxManagement.TaxCalculationNumber;

namespace Enginia360.Modules.TaxManagement;

internal static class TaxAdjustmentAllocationService
{
    internal static TaxAdjustment[] Validate(IReadOnlyList<TaxAdjustment> adjustments, string field,
        bool document, HashSet<Guid> allIds, IReadOnlySet<Guid> lineIds)
    {
        Require(adjustments != null && adjustments.Count <= 20, "tax_calculation_adjustment_limit", field);
        var sequences = new HashSet<int>();
        for (var i = 0; i < adjustments!.Count; i++)
        {
            var a = adjustments[i];
            var adjustmentField = $"{field}[{i}]";
            Require(a != null, "tax_calculation_invalid_adjustment", adjustmentField);
            Require(a!.AdjustmentId != Guid.Empty && allIds.Add(a.AdjustmentId),
                "tax_calculation_duplicate_adjustment_id", adjustmentField + ".adjustment_id");
            Require(a.Sequence > 0 && sequences.Add(a.Sequence),
                "tax_calculation_invalid_sequence", adjustmentField + ".sequence");
            Require(a.Type is "DISCOUNT" or "SURCHARGE",
                "tax_calculation_invalid_adjustment_type", adjustmentField + ".type");
            Require(a.CalculationMode is "PERCENTAGE" or "FIXED_AMOUNT",
                "tax_calculation_invalid_adjustment_mode", adjustmentField + ".calculation_mode");
            var value = Value(a, adjustmentField);
            if (a.CalculationMode == "PERCENTAGE")
                Require(value <= new TaxCalculationNumber(a.Type == "DISCOUNT" ? 100 : 999, 1) +
                    (a.Type == "SURCHARGE" ? new TaxCalculationNumber(999999, 1000000) : Zero),
                    "tax_calculation_invalid_percentage", adjustmentField + ".value");
            if (a.ApplicableLineIds != null)
            {
                Require(document && a.ApplicableLineIds.Count is >= 1 and <= 100 &&
                    a.ApplicableLineIds.Distinct().Count() == a.ApplicableLineIds.Count &&
                    a.ApplicableLineIds.All(lineIds.Contains), "tax_calculation_invalid_applicable_lines",
                    adjustmentField + ".applicable_line_ids");
            }
        }
        return adjustments!.OrderBy(a => a.Sequence).Select(a => a with
        {
            ApplicableLineIds = a.ApplicableLineIds == null ? null :
                Array.AsReadOnly(a.ApplicableLineIds.OrderBy(x => x.ToString("D"), StringComparer.Ordinal).ToArray())
        }).ToArray();
    }
    private static TaxCalculationNumber Value(TaxAdjustment a, string field) =>
        a.CalculationMode == "PERCENTAGE" ? Parse(a.Value, 3, 6, field + ".value") :
            Parse(a.Value, 16, 2, field + ".value");
    internal static TaxCalculationNumber Amount(TaxAdjustment a, TaxCalculationNumber current, string field)
    {
        var value = Value(a, field);
        var amount = a.CalculationMode == "PERCENTAGE" ? current * value / new TaxCalculationNumber(100, 1) : value;
        amount.CheckMoney(field + ".value");
        Require(a.Type != "DISCOUNT" || amount <= current,
            "tax_calculation_discount_exceeds_base", field + ".value");
        return amount;
    }
    // Quote razionali esatte: anche 0.004 + 0.006 scontate al 100% diventano zero.
    // Nessun centesimo intermedio può superare la capienza frazionaria della riga.
    internal static TaxCalculationNumber[] Proportions(IReadOnlyList<TaxCalculationNumber> bases,
        TaxCalculationNumber amount, string field)
    {
        var total = Sum(bases);
        Require(total > Zero || amount.CompareTo(Zero) == 0, "tax_calculation_zero_allocation_base", field);
        return bases.Select(b => total > Zero ? amount * b / total : Zero).ToArray();
    }
}
