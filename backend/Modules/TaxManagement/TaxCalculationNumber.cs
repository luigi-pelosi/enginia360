using System.Globalization;
using System.Numerics;
using System.Text.RegularExpressions;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

// Primitivo locale: frazioni ridotte esatte, con budget esplicito di bit e importi.
// Nessuna arrotondatura interna: InternalScale descrive soltanto la precisione minima della policy.
internal readonly struct TaxCalculationNumber : IComparable<TaxCalculationNumber>
{
    internal BigInteger Numerator { get; }
    internal BigInteger Denominator { get; }
    internal static TaxCalculationNumber Zero => new(0, 1);
    internal static TaxCalculationNumber One => new(1, 1);
    internal TaxCalculationNumber(BigInteger numerator, BigInteger denominator)
    {
        if (denominator <= 0) throw new ArgumentOutOfRangeException(nameof(denominator));
        var gcd = BigInteger.GreatestCommonDivisor(BigInteger.Abs(numerator), denominator);
        Numerator = numerator / gcd;
        Denominator = denominator / gcd;
        Require(Numerator.GetBitLength() <= 65536 && Denominator.GetBitLength() <= 65536,
            "tax_calculation_precision_exhausted");
    }
    internal static void Require(bool condition, string code, string? field = null)
    {
        if (!condition) throw new ApiException(422, code, field);
    }
    internal static TaxCalculationNumber Parse(string? text, int integerDigits, int fractionDigits,
        string field, bool positive = false)
    {
        Require(text != null && text.Length <= integerDigits + fractionDigits + 1 &&
            Regex.IsMatch(text, @"\A(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\z", RegexOptions.CultureInvariant),
            "tax_calculation_invalid_decimal", field);
        var parts = text!.Split('.');
        Require(parts[0].Length <= integerDigits && (parts.Length == 1 || parts[1].Length <= fractionDigits),
            "tax_calculation_invalid_decimal", field);
        var digits = parts.Length == 1 ? 0 : parts[1].Length;
        var result = new TaxCalculationNumber(BigInteger.Parse(string.Concat(parts), CultureInfo.InvariantCulture),
            BigInteger.Pow(10, digits));
        Require(!positive || result > Zero, "tax_calculation_positive_required", field);
        return result;
    }
    internal void CheckMoney(string field)
    {
        Require(this >= Zero && this < new TaxCalculationNumber(BigInteger.Pow(10, 16), 1),
            "tax_calculation_amount_out_of_range", field);
    }
    internal BigInteger FloorCents() => Numerator * 100 / Denominator;
    internal BigInteger RoundCents()
    {
        var absolute = BigInteger.Abs(Numerator) * 100;
        var quotient = BigInteger.DivRem(absolute, Denominator, out var remainder);
        if (remainder * 2 >= Denominator) quotient++;
        return Numerator.Sign < 0 ? -quotient : quotient;
    }
    internal string Exact(int sign = 1) =>
        (Numerator * sign).ToString(CultureInfo.InvariantCulture) + "/" + Denominator.ToString(CultureInfo.InvariantCulture);
    internal static string Money(BigInteger cents, int sign = 1)
    {
        cents *= sign;
        var absolute = BigInteger.Abs(cents);
        return (cents.Sign < 0 ? "-" : "") + (absolute / 100).ToString(CultureInfo.InvariantCulture) +
            "." + (absolute % 100).ToString("00", CultureInfo.InvariantCulture);
    }
    public int CompareTo(TaxCalculationNumber other) =>
        (Numerator * other.Denominator).CompareTo(other.Numerator * Denominator);
    public static TaxCalculationNumber operator +(TaxCalculationNumber a, TaxCalculationNumber b) =>
        new(a.Numerator * b.Denominator + b.Numerator * a.Denominator, a.Denominator * b.Denominator);
    public static TaxCalculationNumber operator -(TaxCalculationNumber a, TaxCalculationNumber b) =>
        new(a.Numerator * b.Denominator - b.Numerator * a.Denominator, a.Denominator * b.Denominator);
    public static TaxCalculationNumber operator *(TaxCalculationNumber a, TaxCalculationNumber b) =>
        new(a.Numerator * b.Numerator, a.Denominator * b.Denominator);
    public static TaxCalculationNumber operator /(TaxCalculationNumber a, TaxCalculationNumber b) =>
        new(a.Numerator * b.Denominator, a.Denominator * b.Numerator);
    public static bool operator <(TaxCalculationNumber a, TaxCalculationNumber b) => a.CompareTo(b) < 0;
    public static bool operator >(TaxCalculationNumber a, TaxCalculationNumber b) => a.CompareTo(b) > 0;
    public static bool operator <=(TaxCalculationNumber a, TaxCalculationNumber b) => a.CompareTo(b) <= 0;
    public static bool operator >=(TaxCalculationNumber a, TaxCalculationNumber b) => a.CompareTo(b) >= 0;
    internal static TaxCalculationNumber Sum(IEnumerable<TaxCalculationNumber> values) =>
        values.Aggregate(Zero, (a, b) => a + b);
}
