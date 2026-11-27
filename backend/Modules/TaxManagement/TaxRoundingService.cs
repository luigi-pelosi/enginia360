using System.Numerics;
using static Enginia360.Modules.TaxManagement.TaxCalculationNumber;

namespace Enginia360.Modules.TaxManagement;

public static class TaxRoundingService
{
    public static void ValidatePolicy(TaxCalculationPolicy policy)
    {
        Require(policy == TaxCalculationPolicies.Standard, "tax_calculation_unsupported_policy", "policy");
    }
    public static string Round(string amount, TaxCalculationPolicy policy)
    {
        ValidatePolicy(policy);
        var value = Parse(amount, 16, 12, "amount");
        value.CheckMoney("amount");
        return Money(value.RoundCents());
    }
    // floor + un centesimo ai resti maggiori; il cap serve allo scorporo congiunto.
    internal static BigInteger[] Allocate(IReadOnlyList<Guid> ids,
        IReadOnlyList<TaxCalculationNumber> exact, BigInteger target, IReadOnlyList<BigInteger>? caps = null)
    {
        var amounts = exact.Select(x => x.FloorCents()).ToArray();
        Require(caps == null || amounts.Select((x, i) => x <= caps[i]).All(x => x),
            "tax_calculation_allocation_invariant");
        var remaining = target - amounts.Aggregate(BigInteger.Zero, (a, b) => a + b);
        var order = Enumerable.Range(0, ids.Count)
            .OrderByDescending(i => exact[i] - new TaxCalculationNumber(amounts[i], 100))
            .ThenBy(i => ids[i].ToString("D"), StringComparer.Ordinal);
        foreach (var i in order)
        {
            if (remaining == 0) break;
            if (caps != null && amounts[i] >= caps[i]) continue;
            amounts[i]++;
            remaining--;
        }
        Require(remaining == 0, "tax_calculation_allocation_invariant");
        return amounts;
    }
}

public static class TaxDeductibilityCalculator
{
    public static TaxDeductibilityResult Calculate(string taxAmount, string percentage,
        TaxCalculationPolicy policy)
    {
        TaxRoundingService.ValidatePolicy(policy);
        var negative = taxAmount.StartsWith('-');
        var tax = Parse(negative ? taxAmount[1..] : taxAmount, 16, 2, "tax_amount");
        tax.CheckMoney("tax_amount");
        var rate = Parse(percentage, 3, 6, "deductible_percentage");
        Require(rate <= new TaxCalculationNumber(100, 1), "tax_calculation_invalid_percentage", "deductible_percentage");
        var cents = tax.RoundCents();
        var deductible = (tax * rate / new TaxCalculationNumber(100, 1)).RoundCents();
        var sign = negative ? -1 : 1;
        return new(Money(cents, sign), Money(deductible, sign), Money(cents - deductible, sign));
    }
}
