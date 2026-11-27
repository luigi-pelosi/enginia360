using System.Collections;
using System.Globalization;
using System.Numerics;
using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Modules.TaxManagement;
using Enginia360.Shared.Validation;

namespace Enginia360.Verification.TaxManagement;

public static class TaxCalculationSelfTests
{
    private static Guid Id(int n) => Guid.Parse($"00000000-0000-0000-0000-{n:000000000000}");
    private static TaxCalculationLine Line(int id, string price, string rate = "22", string mode = "TAX_EXCLUSIVE")
    {
        var date = new DateOnly(2026, 11, 27);
        var territory = new TaxTerritorialityOutcome("SUCCESS", Id(3), Id(3), "DOMESTIC", null, []);
        var snapshot = JsonSerializer.SerializeToElement(new { company = new { id = Id(2), registrationId = Id(9) } });
        var trace = new TaxDeterminationTrace(date, "SALE", territory, [],
            [new(Id(4), Id(5), 1, 100, "PUBLISHED", "MATCH", [])], snapshot, Id(6), 1, Id(7));
        var result = new TaxDeterminationResult(Id(4), Id(5), Id(6), Id(7), Id(9), Id(3),
            "VAT", "TAXABLE", rate, null, "SUPPLIER", "STANDARD", date, "fixture", trace);
        return new(Id(id), "1", price, mode, [], new(Id(1), Id(2), "SALE", result, false));
    }
    private static TaxCalculationRequest Request(params TaxCalculationLine[] lines) =>
        new(Id(1), Id(2), "EUR", "SALE", "NORMAL", lines, [], TaxCalculationPolicies.Standard);
    private static TaxAdjustment Adjustment(int id, string type, string mode, string value, int sequence = 1,
        IReadOnlyList<Guid>? targets = null) => new(Id(id), type, mode, value, sequence, targets);
    private static TaxCalculationLine Purchase(TaxCalculationLine line, string? percentage = null)
    {
        var d = line.Determination;
        var r = d.Result;
        return line with { DeductiblePercentage = percentage, Determination = d with
        {
            OperationType = "PURCHASE", Result = r with { DeterminationTrace = r.DeterminationTrace with { OperationType = "PURCHASE" } }
        } };
    }
    private static decimal Amount(string value) => decimal.Parse(value, CultureInfo.InvariantCulture);
    private static string Serialize(object value) => JsonSerializer.Serialize(value);
    private static int CheckAdjustmentErrorFields()
    {
        var failures = new List<string>();
        var assertions = 0;
        void RejectAt(TaxCalculationRequest request, string code, string field)
        {
            try
            {
                TaxCalculationEngine.Calculate(request);
                failures.Add($"{field}: request unexpectedly accepted");
            }
            catch (ApiException error)
            {
                if (error.Code != code || error.Field != field)
                    failures.Add($"expected {code} at {field}; actual {error.Code} at {error.Field}");
                assertions += 2;
            }
        }

        var later = Adjustment(1000, "SURCHARGE", "FIXED_AMOUNT", "0", 2);
        var first = Adjustment(1001, "DISCOUNT", "FIXED_AMOUNT", "100.01", 1);
        var cases = new (TaxAdjustment Adjustment, string Code, string Member)[]
        {
            (first, "tax_calculation_discount_exceeds_base", "value"),
            (first with { CalculationMode = "INVALID" }, "tax_calculation_invalid_adjustment_mode", "calculation_mode"),
            (first with { AdjustmentId = later.AdjustmentId }, "tax_calculation_duplicate_adjustment_id", "adjustment_id"),
            (first with { Sequence = later.Sequence }, "tax_calculation_invalid_sequence", "sequence"),
            (first with { Sequence = 0 }, "tax_calculation_invalid_sequence", "sequence"),
            (first with { Type = "INVALID" }, "tax_calculation_invalid_adjustment_type", "type"),
            (first with { Value = "bad" }, "tax_calculation_invalid_decimal", "value"),
            (first with { CalculationMode = "PERCENTAGE", Value = "100.000001" }, "tax_calculation_invalid_percentage", "value"),
            (first with { ApplicableLineIds = [Id(999)] }, "tax_calculation_invalid_applicable_lines", "applicable_line_ids")
        };
        foreach (var item in cases)
        {
            RejectAt(Request(Line(100, "100") with { Adjustments = [later, item.Adjustment] }),
                item.Code, "lines[0].adjustments[1]." + item.Member);
            RejectAt(Request(Line(100, "100")) with { DocumentAdjustments = [later, item.Adjustment] },
                item.Code, "document_adjustments[1]." + item.Member);
        }
        foreach (var targets in new IReadOnlyList<Guid>[] { [], [Id(100), Id(100)] })
            RejectAt(Request(Line(100, "100")) with
            {
                DocumentAdjustments = [later, first with { ApplicableLineIds = targets }]
            }, "tax_calculation_invalid_applicable_lines", "document_adjustments[1].applicable_line_ids");

        RejectAt(Request(Line(100, "100"), Line(101, "100", mode: "TAX_INCLUSIVE")) with
        {
            DocumentAdjustments =
            [
                later with { ApplicableLineIds = [Id(100)] },
                first with { Value = "1", ApplicableLineIds = [Id(100), Id(101)] }
            ]
        }, "tax_calculation_mixed_price_modes", "document_adjustments[1].applicable_line_ids");
        if (failures.Count != 0)
            throw new Exception("Tax calculation adjustment fields:\n" + string.Join("\n", failures));
        Console.WriteLine($"TaxCalculation adjustment input-index regression: {assertions} assertions passed");
        return assertions;
    }

    public static void Run()
    {
        var assertions = CheckAdjustmentErrorFields();
        var references = 0;
        void Check(bool condition, string label)
        {
            if (!condition) throw new Exception("Tax calculation: " + label);
            assertions++;
        }
        void Equal(string actual, string expected, string label) => Check(actual == expected, label + ": expected " + expected + ", actual " + actual);
        void Ref(bool condition, string label) { Check(condition, label); references++; }
        void Reject(TaxCalculationRequest request, string code, string label)
        {
            try { TaxCalculationEngine.Calculate(request); }
            catch (ApiException e) { Equal(e.Code, code, label); return; }
            throw new Exception("Tax calculation accepted invalid request: " + label);
        }
        TaxCalculationResult Calculate(TaxCalculationRequest request) => TaxCalculationEngine.Calculate(request);
        var basic = Request(Line(100, "100"));
        var result = Calculate(basic);
        Ref(result.Totals.AmountPayable == "122.00", "reference1 exclusive100 VAT22");
        var inclusive = Calculate(Request(Line(100, "122", mode: "TAX_INCLUSIVE")));
        Ref(inclusive.Totals.NetAmount == "100.00" && inclusive.Totals.TotalTaxAmount == "22.00", "reference2 inclusive122");
        var discounted = Line(100, "100") with { Adjustments = [Adjustment(1000, "DISCOUNT", "PERCENTAGE", "10")] };
        result = Calculate(Request(discounted));
        Ref(result.Totals.NetAmount == "90.00" && result.Totals.TotalTaxAmount == "19.80", "reference3 discount10");
        var sequential = discounted with { Adjustments = [discounted.Adjustments[0], Adjustment(1001, "DISCOUNT", "PERCENTAGE", "5", 2)] };
        Ref(Calculate(Request(sequential)).Totals.NetAmount == "85.50", "reference4 sequential discounts");
        var multirate = Request(Line(100, "100"), Line(101, "50", "10"));
        Ref(Calculate(multirate).Totals.AmountPayable == "177.00", "reference5 multiple rates");
        var doc = multirate with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "FIXED_AMOUNT", "15")] };
        result = Calculate(doc);
        Ref(result.Totals.AmountPayable == "159.30" && result.Lines[0].NetDiscountAmount == "10.00" &&
            result.Lines[1].NetDiscountAmount == "5.00", "reference6 document discount");
        var cents = Request(Line(100, "0.03"), Line(101, "0.03"), Line(102, "0.03"));
        result = Calculate(cents);
        Ref(result.Totals.TotalTaxAmount == "0.02" && result.Lines.Select(l => l.TaxAmount).SequenceEqual(["0.01", "0.01", "0.00"]), "reference7 group rounding stable tie");
        var purchase = Request(Purchase(Line(100, "1000"), "40")) with { OperationType = "PURCHASE" };
        result = Calculate(purchase);
        Ref(result.Lines[0].Deductibility is { DeductibleAmount: "88.00", NonDeductibleAmount: "132.00" } &&
            result.Totals.AmountPayable == "1220.00", "reference8 purchase deductibility");
        Ref(Calculate(basic with { Direction = "REVERSAL" }).Totals.AmountPayable == "-122.00", "reference9 reversal");
        Reject(Request(Line(100, "100") with { Currency = "USD" }), "tax_calculation_currency_mismatch", "reference10 currency"); references++;
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "FIXED_AMOUNT", "100.01")] },
            "tax_calculation_discount_exceeds_base", "reference11 excess discount"); references++;
        var unsupported = basic.Lines[0] with { Determination = basic.Lines[0].Determination with
        { Result = basic.Lines[0].Determination.Result with { Treatment = "REVERSE_CHARGE" } } };
        Reject(Request(unsupported), "tax_calculation_unsupported_tax", "reference12 unsupported"); references++;
        Reject(Request(basic.Lines[0] with { Determination = basic.Lines[0].Determination with { TenantId = Id(999) } }),
            "tax_calculation_determination_scope_mismatch", "reference13 foreign tenant"); references++;
        Check(references == 13, "exact reference count");

        void Reconciles(TaxCalculationResult r)
        {
            foreach (var line in r.Lines)
            {
                Check(Amount(line.NetAmount) + Amount(line.TaxAmount) == Amount(line.GrossAmount), "line net+tax=gross");
                Check(Amount(line.NetBeforeAdjustments) - Amount(line.NetDiscountAmount) + Amount(line.NetSurchargeAmount) +
                    Amount(line.NetRoundingAdjustment) == Amount(line.NetAmount), "line monetary components reconcile");
                Equal(line.TaxAmount, line.InvoiceTaxAmount, "invoice tax ordinary");
                if (line.Deductibility is { } d)
                    Check(Amount(d.DeductibleAmount) + Amount(d.NonDeductibleAmount) == Amount(line.TaxAmount), "deductibility final tax");
            }
            Check(r.Lines.Sum(l => Amount(l.NetAmount)) == Amount(r.Totals.NetAmount), "line net totals");
            Check(r.Lines.Sum(l => Amount(l.TaxAmount)) == Amount(r.Totals.TotalTaxAmount), "line tax totals");
            Check(r.Lines.Sum(l => Amount(l.GrossAmount)) == Amount(r.Totals.GrossAmount), "line gross totals");
            Check(r.Summaries.Sum(s => Amount(s.NetAmount)) == Amount(r.Totals.NetAmount), "summary net totals");
            Check(r.Summaries.Sum(s => Amount(s.TaxAmount)) == Amount(r.Totals.TotalTaxAmount), "summary tax totals");
            Check(r.Summaries.Sum(s => Amount(s.GrossAmount)) == Amount(r.Totals.GrossAmount), "summary gross totals");
            Check(Amount(r.Totals.NetBeforeAdjustments) - Amount(r.Totals.NetDiscountAmount) + Amount(r.Totals.NetSurchargeAmount) +
                Amount(r.Totals.NetRoundingAdjustment) == Amount(r.Totals.NetAmount), "totals components reconcile");
            foreach (var s in r.Summaries)
            {
                var members = r.Lines.Where(l => l.TaxCodeId == s.TaxCodeId && l.TaxCodeVersionId == s.TaxCodeVersionId &&
                    l.TaxRate == s.Rate && l.PriceMode == s.PriceMode).ToArray();
                Check(members.Sum(l => Amount(l.NetAmount)) == Amount(s.NetAmount), "each group net");
                Check(members.Sum(l => Amount(l.TaxAmount)) == Amount(s.TaxAmount), "each group tax");
                Check(members.Sum(l => Amount(l.NetRoundingAdjustment)) == Amount(s.NetRoundingAdjustment), "each group net rounding");
                Check(members.Sum(l => Amount(l.TaxRoundingAdjustment)) == Amount(s.TaxRoundingAdjustment), "each group tax rounding");
            }
            foreach (var a in r.CalculationTrace.Adjustments)
            {
                static TaxCalculationNumber Fraction(string text)
                {
                    var p = text.Split('/');
                    return new(BigInteger.Parse(p[0], CultureInfo.InvariantCulture), BigInteger.Parse(p[1], CultureInfo.InvariantCulture));
                }
                Check(TaxCalculationNumber.Sum(a.Allocations.Select(l => Fraction(l.PriceBaseAmountExact)))
                    .CompareTo(Fraction(a.PriceBaseAmountExact)) == 0, "exact adjustment allocation sum");
            }
            Check(!Serialize(r).Contains("-0.00\"", StringComparison.Ordinal), "no negative zero");
        }
        void Reversal(JsonElement normal, JsonElement reverse)
        {
            if (normal.ValueKind == JsonValueKind.Object)
            {
                foreach (var p in normal.EnumerateObject()) Reversal(p.Value, reverse.GetProperty(p.Name));
            }
            else if (normal.ValueKind == JsonValueKind.Array)
            {
                Check(normal.GetArrayLength() == reverse.GetArrayLength(), "reversal same collection length");
                for (var i = 0; i < normal.GetArrayLength(); i++) Reversal(normal[i], reverse[i]);
            }
            else if (normal.ValueKind == JsonValueKind.String && normal.GetString() is { } text &&
                (Regex.IsMatch(text, @"\A-?[0-9]+\.[0-9]{2}\z") || Regex.IsMatch(text, @"\A-?[0-9]+/[0-9]+\z")))
            {
                var zero = text == "0.00" || text == "0/1";
                var expected = zero ? text : text.StartsWith('-') ? text[1..] : "-" + text;
                Equal(reverse.GetString()!, expected, "every monetary and exact allocation field reverses");
            }
            else Equal(reverse.GetRawText(), normal.GetRawText(), "reversal nonmonetary unchanged");
        }
        var fraction = Request(Line(100, "0.004"), Line(101, "0.006")) with
        { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "PERCENTAGE", "100")] };
        result = Calculate(fraction);
        Equal(result.Totals.AmountPayable, "0.00", "fractional bases 100 percent discount");
        Reconciles(result);
        result = Calculate(Request(Line(100, "100") with { Adjustments =
            [Adjustment(1001, "SURCHARGE", "FIXED_AMOUNT", "20"), Adjustment(1002, "DISCOUNT", "PERCENTAGE", "100", 2)] }));
        Equal(result.Totals.NetDiscountAmount, "120.00", "discount after surcharge uses current base");
        Equal(result.Totals.AmountPayable, "0.00", "discount after surcharge zero");
        Reconciles(result);
        var zeroRequest = fraction with { DocumentAdjustments = [fraction.DocumentAdjustments[0], Adjustment(2001, "SURCHARGE", "PERCENTAGE", "10", 2)] };
        Equal(Calculate(zeroRequest).Totals.AmountPayable, "0.00", "zero weight zero target allowed");
        Reject(zeroRequest with { DocumentAdjustments = [fraction.DocumentAdjustments[0], Adjustment(2001, "SURCHARGE", "FIXED_AMOUNT", "1", 2)] },
            "tax_calculation_zero_allocation_base", "zero weights nonzero target rejected");
        Reject(Request(Line(100, "1"), Line(101, "1", mode: "TAX_INCLUSIVE")) with
        { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "PERCENTAGE", "10")] }, "tax_calculation_mixed_price_modes", "mixed mode targets rejected");
        Check(Calculate(Request(Line(100, "1"), Line(101, "1", mode: "TAX_INCLUSIVE"))).Summaries.Count == 2, "group key includes price mode");
        foreach (var mode in new[] { "TAX_INCLUSIVE", "TAX_EXCLUSIVE" })
        {
            var tiny = Request(Enumerable.Range(0, 100).Select(i => Line(100 + i, "0.004", "22", mode)).ToArray());
            result = Calculate(tiny);
            Reconciles(result);
            if (mode == "TAX_INCLUSIVE") Equal(result.Totals.GrossAmount, "0.40", "inclusive joint allocation caps preserves gross");
        }
        Equal(Calculate(purchase with { Lines = [Purchase(Line(100, "1000"))] }).Lines[0].Deductibility == null ? "null" : "value", "null", "unknown deductibility remains null");
        foreach (var percentage in new[] { "0", "40", "100" })
        {
            var p = purchase with { Lines = [Purchase(Line(100, "0.03"), percentage), Purchase(Line(101, "0.03"), percentage), Purchase(Line(102, "0.03"), percentage)] };
            var pResult = Calculate(p);
            Reconciles(pResult);
            var reversed = Calculate(p with { Direction = "REVERSAL" });
            Reversal(JsonSerializer.SerializeToElement(pResult), JsonSerializer.SerializeToElement(reversed));
        }
        foreach (var invalid in new[] { "-1", "+1", "1e2", "1,2", "1\0", "\ud800", " 1", "01", "1.", "1000000000000", "0.123456789" })
            Reject(Request(Line(100, invalid)), "tax_calculation_invalid_decimal", "invalid unit price");
        Reject(Request(Line(100, "0")), "tax_calculation_positive_required", "zero input price rejected");
        Reject(basic with { Lines = [basic.Lines[0], basic.Lines[0]] }, "tax_calculation_duplicate_line_id", "duplicate lines");
        Reject(basic with { Policy = basic.Policy with { CurrencyScale = 3 } }, "tax_calculation_unsupported_policy", "policy scale unsupported");
        Reject(basic with { Currency = "USD" }, "tax_calculation_unsupported_currency", "foreign currency");
        Reject(basic with { Lines = Enumerable.Range(0, 101).Select(i => Line(100 + i, "1")).ToArray() }, "tax_calculation_line_limit", "101 lines");
        Reject(Request(Line(100, "999999999999") with { Quantity = "100000" }), "tax_calculation_amount_out_of_range", "bounded intermediate");
        Reject(basic with { Lines = [basic.Lines[0] with { Determination = basic.Lines[0].Determination with { CompanyId = Id(999) } }] },
            "tax_calculation_determination_scope_mismatch", "foreign company");
        var originalDetermination = basic.Lines[0].Determination;
        var originalResult = originalDetermination.Result;
        var originalTrace = originalResult.DeterminationTrace;
        foreach (var snapshot in new[]
        {
            JsonSerializer.SerializeToElement(new { company = new { id = 42, registrationId = Id(9) } }),
            JsonSerializer.SerializeToElement(new { company = new { id = " " + Id(2).ToString("D"), registrationId = Id(9) } }),
            JsonSerializer.SerializeToElement(new { company = new { id = Id(999), registrationId = Id(9) } }),
            JsonSerializer.SerializeToElement(new { company = new { id = Id(2), registrationId = Guid.Empty } })
        }) Reject(Request(basic.Lines[0] with { Determination = originalDetermination with { Result = originalResult with
            { DeterminationTrace = originalTrace with { SourceSnapshot = snapshot } } } }), "tax_calculation_invalid_snapshot", "invalid source identity snapshot");
        foreach (var revision in new long?[] { null, 0, -1 })
            Reject(Request(basic.Lines[0] with { Determination = originalDetermination with { Result = originalResult with
                { DeterminationTrace = originalTrace with { TaxCodeRevision = revision } } } }), "tax_calculation_invalid_snapshot", "positive code revision required");
        Reject(Request(basic.Lines[0] with { Determination = originalDetermination with { Result = originalResult with { TaxRuleVersionId = Guid.Empty } } }),
            "tax_calculation_invalid_snapshot", "positive source ID required");
        Reject(Request(basic.Lines[0] with { DeductiblePercentage = "40" }), "tax_calculation_sale_deductibility_forbidden", "sale deductibility");
        foreach (var a in new[]
        {
            Adjustment(2000, "DISCOUNT", "PERCENTAGE", "100.000001"),
            Adjustment(2000, "SURCHARGE", "PERCENTAGE", "1000")
        }) Reject(basic with { DocumentAdjustments = [a] }, a.Value == "1000" ? "tax_calculation_invalid_decimal" : "tax_calculation_invalid_percentage", "percentage caps");
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "REBATE", "PERCENTAGE", "1")] }, "tax_calculation_invalid_adjustment_type", "enum type");
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "OTHER", "1")] }, "tax_calculation_invalid_adjustment_mode", "enum mode");
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "FIXED_AMOUNT", "0", targets: [])] }, "tax_calculation_invalid_applicable_lines", "empty target list");
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "FIXED_AMOUNT", "0", targets: [Id(999)])] }, "tax_calculation_invalid_applicable_lines", "unknown target list");
        Reject(basic with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "PERCENTAGE", "1"), Adjustment(2001, "DISCOUNT", "PERCENTAGE", "1")] },
            "tax_calculation_invalid_sequence", "duplicate sequence");
        Reject(basic with { DocumentAdjustments = Enumerable.Range(0, 21).Select(i => Adjustment(2000 + i, "DISCOUNT", "PERCENTAGE", "0", i + 1)).ToArray() },
            "tax_calculation_adjustment_limit", "21 adjustments");

        foreach (var rate in new string?[] { null, "bad", "1e2", "1000" })
            Reject(Request(basic.Lines[0] with { Determination = originalDetermination with { Result = originalResult with { Rate = rate! } } }),
                "tax_calculation_invalid_decimal", "malformed trusted rate is controlled");
        Reject(Request(Line(100, "999999999999.99999999") with { Quantity = "10000",
            Adjustments = [Adjustment(2000, "DISCOUNT", "PERCENTAGE", "100")] }),
            "tax_calculation_amount_out_of_range", "rounded component reaches forbidden monetary bound");
        Equal(TaxRoundingService.Round("2.005", TaxCalculationPolicies.Standard), "2.01", "HALF_UP exact midpoint");
        Equal(TaxDeductibilityCalculator.Calculate("-0.01", "40", TaxCalculationPolicies.Standard).NonDeductibleAmount,
            "-0.01", "standalone deductibility negative final tax");
        var subset = Request(Line(100, "100"), Line(101, "50", mode: "TAX_INCLUSIVE")) with
        { DocumentAdjustments = [Adjustment(2000, "SURCHARGE", "FIXED_AMOUNT", "10", targets: [Id(100)])] };
        result = Calculate(subset);
        Equal(result.Lines[0].NetSurchargeAmount, "10.00", "targeted ordinary common charge follows principal");
        Equal(result.Lines[1].GrossAmount, "50.00", "untargeted inclusive line unaffected");
        Reconciles(result);
        var fixedFraction = fraction with { DocumentAdjustments = [Adjustment(2000, "DISCOUNT", "FIXED_AMOUNT", "0.01")] };
        result = Calculate(fixedFraction);
        Equal(result.Totals.AmountPayable, "0.00", "fixed fractional full-capacity discount");
        Reconciles(result);
        var maximum = Request(Enumerable.Range(0, 100).Select(i => Line(100 + i, "0.004006", "999.999999") with
        { Adjustments = Enumerable.Range(0, 20).Select(j => Adjustment(10000 + i * 20 + j,
            j % 2 == 0 ? "SURCHARGE" : "DISCOUNT", "PERCENTAGE", "0.123456", j + 1)).ToArray() }).ToArray()) with
        { DocumentAdjustments = Enumerable.Range(0, 20).Select(j => Adjustment(20000 + j,
            j % 2 == 0 ? "SURCHARGE" : "DISCOUNT", "PERCENTAGE", "0.123456", j + 1)).ToArray() };
        Reconciles(Calculate(maximum));
        var generatedLines = 0;
        const int batches = 120;
        for (var batch = 0; batch < batches; batch++)
        {
            var mode = batch % 2 == 0 ? "TAX_INCLUSIVE" : "TAX_EXCLUSIVE";
            var generated = Enumerable.Range(0, 1 + batch % 100).Select(i =>
            {
                var line = Line(100 + i, ((batch * 31 + i * 17 + 1) % 999 + 1).ToString(CultureInfo.InvariantCulture) + ".004006",
                    new[] { "4", "5", "10", "22" }[(batch + i) % 4], mode) with
                {
                    Quantity = "0.123456", Adjustments = [Adjustment(3000 + i * 2, "SURCHARGE", "FIXED_AMOUNT", "0.01"),
                        Adjustment(3001 + i * 2, "DISCOUNT", "PERCENTAGE", "5", 2)]
                };
                return batch % 3 == 0 ? Purchase(line, "40") : line;
            }).ToArray();
            generatedLines += generated.Length;
            var request = Request(generated) with { OperationType = batch % 3 == 0 ? "PURCHASE" : "SALE",
                DocumentAdjustments = [Adjustment(9000, "SURCHARGE", "PERCENTAGE", "3"), Adjustment(9001, "DISCOUNT", "PERCENTAGE", "10", 2)] };
            var normal = Calculate(request);
            Reconciles(normal);
            var reversed = Calculate(request with { Direction = "REVERSAL" });
            Reconciles(reversed);
            Reversal(JsonSerializer.SerializeToElement(normal), JsonSerializer.SerializeToElement(reversed));
            var permuted = request with { Lines = Array.AsReadOnly(generated.Reverse().Select(l => l with { Adjustments = l.Adjustments.Reverse().ToArray() }).ToArray()),
                DocumentAdjustments = request.DocumentAdjustments.Reverse().ToArray() };
            Equal(Serialize(Calculate(permuted)), Serialize(normal), "shuffle lines and adjustments stable IDs");
            var expectedCurrent = generated.Select(l => (Amount(l.UnitPrice) * Amount(l.Quantity) + 0.01m) * 0.95m * 1.03m * 0.90m).ToArray();
            if (mode == "TAX_INCLUSIVE")
            {
                var expectedGross = generated.Select((l, i) => new { l.Determination.Result.Rate, Value = expectedCurrent[i] })
                    .GroupBy(x => x.Rate).Sum(g => decimal.Round(g.Sum(x => x.Value), 2, MidpointRounding.AwayFromZero));
                Check(expectedGross == Amount(normal.Totals.GrossAmount), "independent inclusive gross group target");
            }
            else
            {
                var expectedNet = generated.Select((l, i) => new { l.Determination.Result.Rate, Value = expectedCurrent[i] }).GroupBy(x => x.Rate)
                    .Sum(g => decimal.Round(g.Sum(x => x.Value), 2, MidpointRounding.AwayFromZero));
                var expectedTax = generated.Select((l, i) => new { Rate = Amount(l.Determination.Result.Rate), Value = expectedCurrent[i] }).GroupBy(x => x.Rate)
                    .Sum(g => decimal.Round(g.Sum(x => x.Value * x.Rate / 100m), 2, MidpointRounding.AwayFromZero));
                Check(expectedNet == Amount(normal.Totals.NetAmount) && expectedTax == Amount(normal.Totals.TotalTaxAmount), "independent exclusive group targets");
            }
        }
        var mutable = new List<TaxCalculationLine> { discounted };
        var immutable = Calculate(basic with { Lines = mutable });
        var frozen = Serialize(immutable);
        mutable.Clear();
        Equal(Serialize(immutable), frozen, "input collections not retained");
        foreach (var list in new IList[] { (IList)immutable.Lines, (IList)immutable.Summaries, (IList)immutable.CalculationTrace.Sources,
            (IList)immutable.CalculationTrace.Adjustments, (IList)immutable.CalculationTrace.Adjustments[0].Allocations })
        {
            Check(list.IsReadOnly, "all output collections readonly");
            try { list.Clear(); throw new Exception("mutable output list"); } catch (NotSupportedException) { assertions++; }
        }
        Console.WriteLine($"TaxCalculation: {references} references, {batches} deterministic batches, {generatedLines} generated lines, {assertions} assertions passed");
    }
}
