using System.Numerics;
using System.Text.Json;
using static Enginia360.Modules.TaxManagement.TaxCalculationNumber;

namespace Enginia360.Modules.TaxManagement;

public static class TaxCalculationEngine
{
    private sealed class Work(TaxCalculationLine line, TaxCalculationNumber initial, TaxCalculationNumber rate)
    {
        internal TaxCalculationLine Line { get; } = line;
        internal TaxCalculationNumber Initial { get; } = initial;
        internal TaxCalculationNumber Current { get; set; } = initial;
        internal TaxCalculationNumber Rate { get; } = rate;
        internal TaxCalculationNumber Discount { get; set; } = Zero;
        internal TaxCalculationNumber Surcharge { get; set; } = Zero;
        internal bool Inclusive => Line.PriceMode == "TAX_INCLUSIVE";
        internal TaxCalculationNumber Factor => One + Rate / new TaxCalculationNumber(100, 1);
        internal TaxCalculationNumber Net(TaxCalculationNumber amount) => Inclusive ? amount / Factor : amount;
        internal TaxCalculationNumber ExactNet => Net(Current);
        internal TaxCalculationNumber ExactTax => Inclusive ? Current - ExactNet : Current * Rate / new TaxCalculationNumber(100, 1);
        internal BigInteger NetCents { get; set; }
        internal BigInteger TaxCents { get; set; }
        internal BigInteger GrossCents => NetCents + TaxCents;
    }
    private sealed record GroupKey(Guid Code, Guid Version, string Type, Guid Country,
        string Rate, string Treatment, string? Nature, string Liable, string Collection, string PriceMode);

    public static TaxCalculationResult Calculate(TaxCalculationRequest request)
    {
        Require(request != null, "tax_calculation_request_required");
        TaxRoundingService.ValidatePolicy(request!.Policy);
        Require(request.TenantId != Guid.Empty && request.CompanyId != Guid.Empty, "tax_calculation_invalid_id");
        Require(request.Currency == "EUR", "tax_calculation_unsupported_currency", "currency");
        Require(request.OperationType is "SALE" or "PURCHASE", "tax_calculation_invalid_operation", "operation_type");
        Require(request.Direction is "NORMAL" or "REVERSAL", "tax_calculation_invalid_direction", "direction");
        Require(request.Lines != null && request.Lines.Count is >= 1 and <= 100, "tax_calculation_line_limit", "lines");
        var input = request.Lines!.ToArray();
        Require(input.All(l => l != null && l.LineId != Guid.Empty) &&
            input.Select(l => l.LineId).Distinct().Count() == input.Length,
            "tax_calculation_duplicate_line_id", "lines");
        var lineIds = input.Select(l => l.LineId).ToHashSet();
        var adjustmentIds = new HashSet<Guid>();
        var traces = new List<TaxAdjustmentTrace>();
        var work = new List<Work>();
        var sign = request.Direction == "REVERSAL" ? -1 : 1;
        for (var i = 0; i < input.Length; i++)
        {
            var line = input[i];
            var field = $"lines[{i}]";
            ValidateDetermination(request, line, field);
            Require(line.PriceMode is "TAX_EXCLUSIVE" or "TAX_INCLUSIVE", "tax_calculation_invalid_price_mode", field + ".price_mode");
            Require(line.Currency == null || line.Currency == request.Currency, "tax_calculation_currency_mismatch", field + ".currency");
            var quantity = Parse(line.Quantity, 14, 6, field + ".quantity", true);
            var price = Parse(line.UnitPrice, 12, 8, field + ".unit_price", true);
            var initial = quantity * price;
            initial.CheckMoney(field + ".unit_price");
            if (line.DeductiblePercentage != null)
            {
                Require(request.OperationType == "PURCHASE", "tax_calculation_sale_deductibility_forbidden", field + ".deductible_percentage");
                var deductible = Parse(line.DeductiblePercentage, 3, 6, field + ".deductible_percentage");
                Require(deductible <= new TaxCalculationNumber(100, 1), "tax_calculation_invalid_percentage", field + ".deductible_percentage");
            }
            var rateText = TaxRules.RateText(TaxRules.ParseRate(line.Determination.Result.Rate));
            var current = new Work(line, initial, Parse(rateText, 3, 6, field + ".determination.rate"));
            var adjustments = TaxAdjustmentAllocationService.Validate(line.Adjustments, field + ".adjustments", false, adjustmentIds, lineIds);
            var originalIndices = OriginalAdjustmentIndices(line.Adjustments);
            foreach (var a in adjustments)
            {
                var adjustmentField = $"{field}.adjustments[{originalIndices[a.AdjustmentId]}]";
                var amount = TaxAdjustmentAllocationService.Amount(a, current.Current, adjustmentField);
                Apply(current, a.Type, amount, adjustmentField + ".value");
                traces.Add(new(a.AdjustmentId, "LINE", a.Type, a.CalculationMode, a.Sequence,
                    line.PriceMode, amount.Exact(sign), Array.AsReadOnly(new[] { new TaxAdjustmentAllocation(line.LineId, amount.Exact(sign)) })));
            }
            work.Add(current);
        }
        var document = TaxAdjustmentAllocationService.Validate(request.DocumentAdjustments, "document_adjustments", true, adjustmentIds, lineIds);
        var documentOriginalIndices = OriginalAdjustmentIndices(request.DocumentAdjustments);
        foreach (var a in document)
        {
            var adjustmentField = $"document_adjustments[{documentOriginalIndices[a.AdjustmentId]}]";
            var targets = work.Where(w => a.ApplicableLineIds == null || a.ApplicableLineIds.Contains(w.Line.LineId))
                .OrderBy(w => w.Line.LineId.ToString("D"), StringComparer.Ordinal).ToArray();
            Require(targets.Select(w => w.Line.PriceMode).Distinct().Count() == 1,
                "tax_calculation_mixed_price_modes", adjustmentField + ".applicable_line_ids");
            var total = Sum(targets.Select(w => w.Current));
            total.CheckMoney(adjustmentField + ".value");
            var amount = TaxAdjustmentAllocationService.Amount(a, total, adjustmentField);
            var shares = TaxAdjustmentAllocationService.Proportions(targets.Select(w => w.Current).ToArray(), amount, adjustmentField + ".value");
            for (var i = 0; i < targets.Length; i++) Apply(targets[i], a.Type, shares[i], adjustmentField + ".value");
            traces.Add(new(a.AdjustmentId, "DOCUMENT", a.Type, a.CalculationMode, a.Sequence,
                targets[0].Line.PriceMode, amount.Exact(sign), Array.AsReadOnly(targets.Select((w, i) =>
                    new TaxAdjustmentAllocation(w.Line.LineId, shares[i].Exact(sign))).ToArray())));
        }
        var ordered = work.OrderBy(w => w.Line.LineId.ToString("D"), StringComparer.Ordinal).ToArray();
        var summaries = new List<TaxSummary>();
        foreach (var group in ordered.GroupBy(Key))
        {
            var members = group.ToArray();
            RoundGroup(members);
            var k = group.Key;
            var net = members.Aggregate(BigInteger.Zero, (a, w) => a + w.NetCents);
            var tax = members.Aggregate(BigInteger.Zero, (a, w) => a + w.TaxCents);
            var netAdjustment = members.Aggregate(BigInteger.Zero, (a, w) => a + NetAdjustment(w));
            var taxAdjustment = members.Aggregate(BigInteger.Zero, (a, w) => a + TaxAdjustment(w));
            summaries.Add(new(k.Code, k.Version, k.Type, k.Country, k.Treatment, k.Rate, k.Nature,
                k.Liable, k.Collection, k.PriceMode, Money(net, sign), Money(net, sign), Money(tax, sign),
                Money(tax, sign), Money(net + tax, sign), Money(taxAdjustment, sign),
                Money(netAdjustment, sign), Money(taxAdjustment, sign)));
        }
        CheckTotals(ordered);
        var lines = ordered.Select(w => LineResult(w, request.Policy, sign)).ToArray();
        BigInteger Total(Func<Work, BigInteger> selector) => ordered.Aggregate(BigInteger.Zero, (a, w) => a + selector(w));
        var totalNet = Total(w => w.NetCents);
        var totalTax = Total(w => w.TaxCents);
        var totals = new TaxDocumentTotals(Money(Total(w => w.Net(w.Initial).RoundCents()), sign),
            Money(Total(w => w.Net(w.Discount).RoundCents()), sign), Money(Total(w => w.Net(w.Surcharge).RoundCents()), sign),
            Money(totalNet, sign), Money(totalNet, sign), "0.00", Money(totalTax, sign), Money(totalTax, sign),
            Money(totalNet + totalTax, sign), Money(totalNet + totalTax, sign), Money(Total(NetAdjustment), sign),
            Money(Total(TaxAdjustment), sign), Money(Total(TaxAdjustment), sign));
        var sources = ordered.Select(w =>
        {
            var d = w.Line.Determination;
            var r = d.Result;
            return new TaxCalculationSource(w.Line.LineId, r.TaxRuleId, r.TaxRuleVersionId, r.TaxCodeId,
                r.TaxCodeVersionId, r.CompanyTaxRegistrationId, r.TaxJurisdictionCountryId, r.TaxDate, d.IsSimulation);
        }).ToArray();
        var trace = new TaxCalculationTrace(request.Policy.Code, request.Policy.Version,
            "BOUNDED_BIG_INTEGER_RATIONAL; commercial allocations exact n/d; monetary residuals LARGEST_REMAINDER",
            Array.AsReadOnly(sources), Array.AsReadOnly(traces.OrderBy(t => t.Scope, StringComparer.Ordinal)
                .ThenBy(t => t.Scope == "LINE" ? t.Allocations[0].LineId.ToString("D") : "", StringComparer.Ordinal)
                .ThenBy(t => t.Sequence).ThenBy(t => t.AdjustmentId.ToString("D"), StringComparer.Ordinal).ToArray()));
        return new(request.Currency, request.Policy.Code, request.Policy.Version, Array.AsReadOnly(lines),
            Array.AsReadOnly(summaries.ToArray()), totals, trace);
    }

    private static Dictionary<Guid, int> OriginalAdjustmentIndices(IReadOnlyList<TaxAdjustment> adjustments)
    {
        // Validate has already established non-null entries and unique IDs before sequence sorting.
        var indices = new Dictionary<Guid, int>(adjustments.Count);
        for (var i = 0; i < adjustments.Count; i++)
            indices.Add(adjustments[i].AdjustmentId, i);
        return indices;
    }

    private static void Apply(Work work, string type, TaxCalculationNumber amount, string field)
    {
        if (type == "DISCOUNT")
        {
            work.Discount += amount;
            work.Current -= amount;
        }
        else
        {
            work.Surcharge += amount;
            work.Current += amount;
        }
        work.Discount.CheckMoney(field);
        work.Surcharge.CheckMoney(field);
        work.Current.CheckMoney(field);
    }
    private static GroupKey Key(Work w)
    {
        var r = w.Line.Determination.Result;
        return new(r.TaxCodeId, r.TaxCodeVersionId, r.TaxType, r.TaxJurisdictionCountryId,
            TaxRules.RateText(TaxRules.ParseRate(r.Rate)), r.Treatment, r.TaxNatureCode,
            r.LiableParty, r.CollectionMechanism, w.Line.PriceMode);
    }
    private static void RoundGroup(Work[] group)
    {
        var ids = group.Select(w => w.Line.LineId).ToArray();
        var net = group.Select(w => w.ExactNet).ToArray();
        var tax = group.Select(w => w.ExactTax).ToArray();
        foreach (var value in net.Concat(tax)) value.CheckMoney("totals");
        var netTotal = Sum(net);
        var taxTotal = Sum(tax);
        netTotal.CheckMoney("totals");
        taxTotal.CheckMoney("totals");
        if (group[0].Inclusive)
        {
            var gross = group.Select(w => w.Current).ToArray();
            var grossCents = TaxRoundingService.Allocate(ids, gross, Sum(gross).RoundCents());
            var netCents = TaxRoundingService.Allocate(ids, net, netTotal.RoundCents(), grossCents);
            for (var i = 0; i < group.Length; i++)
            {
                group[i].NetCents = netCents[i];
                group[i].TaxCents = grossCents[i] - netCents[i];
            }
        }
        else
        {
            var netCents = TaxRoundingService.Allocate(ids, net, netTotal.RoundCents());
            var taxCents = TaxRoundingService.Allocate(ids, tax, taxTotal.RoundCents());
            for (var i = 0; i < group.Length; i++)
            {
                group[i].NetCents = netCents[i];
                group[i].TaxCents = taxCents[i];
            }
        }
    }
    private static BigInteger NetAdjustment(Work w) => w.NetCents -
        (w.Net(w.Initial).RoundCents() - w.Net(w.Discount).RoundCents() + w.Net(w.Surcharge).RoundCents());
    private static BigInteger TaxAdjustment(Work w) => w.TaxCents - w.ExactTax.RoundCents();
    private static TaxCalculationLineResult LineResult(Work w, TaxCalculationPolicy policy, int sign)
    {
        var r = w.Line.Determination.Result;
        var tax = Money(w.TaxCents, sign);
        var deductibility = w.Line.DeductiblePercentage == null ? null :
            TaxDeductibilityCalculator.Calculate(tax, w.Line.DeductiblePercentage, policy);
        return new(w.Line.LineId, r.TaxRuleVersionId, r.TaxCodeId, r.TaxCodeVersionId, w.Line.PriceMode,
            Money(w.Net(w.Initial).RoundCents(), sign), Money(w.Net(w.Discount).RoundCents(), sign),
            Money(w.Net(w.Surcharge).RoundCents(), sign), Money(w.NetCents, sign), Money(w.NetCents, sign),
            TaxRules.RateText(TaxRules.ParseRate(r.Rate)), tax, tax, Money(w.GrossCents, sign),
            Money(TaxAdjustment(w), sign), Money(NetAdjustment(w), sign), Money(TaxAdjustment(w), sign), deductibility);
    }
    private static void CheckTotals(Work[] work)
    {
        Sum(work.Select(w => w.Initial)).CheckMoney("totals");
        Sum(work.Select(w => w.Discount)).CheckMoney("totals");
        Sum(work.Select(w => w.Surcharge)).CheckMoney("totals");
        foreach (var cents in new[] { work.Aggregate(BigInteger.Zero, (a, w) => a + w.Net(w.Initial).RoundCents()),
            work.Aggregate(BigInteger.Zero, (a, w) => a + w.Net(w.Discount).RoundCents()),
            work.Aggregate(BigInteger.Zero, (a, w) => a + w.Net(w.Surcharge).RoundCents()),
            work.Aggregate(BigInteger.Zero, (a, w) => a + w.NetCents),
            work.Aggregate(BigInteger.Zero, (a, w) => a + w.TaxCents),
            work.Aggregate(BigInteger.Zero, (a, w) => a + w.GrossCents) })
        {
            new TaxCalculationNumber(cents, 100).CheckMoney("totals");
        }
    }
    private static bool CanonicalGuid(JsonElement value, out Guid id)
    {
        id = Guid.Empty;
        return value.ValueKind == JsonValueKind.String && value.GetString() is { Length: 36 } text &&
            Guid.TryParseExact(text, "D", out id) && id != Guid.Empty;
    }
    private static void ValidateDetermination(TaxCalculationRequest request, TaxCalculationLine line, string field)
    {
        var d = line.Determination;
        Require(d != null && d.Result != null, "tax_calculation_determination_required", field + ".determination");
        Require(d!.TenantId == request.TenantId && d.CompanyId == request.CompanyId && d.OperationType == request.OperationType,
            "tax_calculation_determination_scope_mismatch", field + ".determination");
        var r = d.Result!;
        var t = r.DeterminationTrace;
        // Il parser F4 resta l'autorità per l'aliquota; prima delimitiamo anche input interni malformati.
        Parse(r.Rate, 3, 6, field + ".determination.rate");
        Require(new[] { r.TaxRuleId, r.TaxRuleVersionId, r.TaxCodeId, r.TaxCodeVersionId,
            r.CompanyTaxRegistrationId, r.TaxJurisdictionCountryId }.All(x => x != Guid.Empty),
            "tax_calculation_invalid_snapshot", field + ".determination");
        Require(r.TaxType == "VAT" && r.Treatment == "TAXABLE" && r.TaxNatureCode == null &&
            r.LiableParty == "SUPPLIER" && r.CollectionMechanism == "STANDARD" &&
            TaxRules.ParseRate(r.Rate) > 0, "tax_calculation_unsupported_tax", field + ".determination");
        Require(t != null && t.TaxDate == r.TaxDate && r.TaxDate != DateOnly.MinValue &&
            t.OperationType == request.OperationType && t.TaxCodeId == r.TaxCodeId &&
            t.TaxCodeVersionId == r.TaxCodeVersionId && t.TaxCodeRevision is >= 1 and <= TaxRules.MaxRevision &&
            t.MissingFields != null && t.MissingFields.Count == 0 && t.Territoriality != null &&
            t.Territoriality.Outcome == "SUCCESS" && t.Territoriality.TerritorialScope == "DOMESTIC" &&
            t.Territoriality.JurisdictionCountryId == r.TaxJurisdictionCountryId &&
            t.Territoriality.PlaceOfSupplyCountryId == r.TaxJurisdictionCountryId &&
            t.Candidates != null && t.Candidates.Any(c => c.RuleId == r.TaxRuleId && c.VersionId == r.TaxRuleVersionId &&
                c.RuleRevision is >= 1 and <= TaxRules.MaxRevision && c.Result == "MATCH" &&
                (c.Status == "PUBLISHED" || d.IsSimulation && c.Status == "DRAFT")),
            "tax_calculation_invalid_snapshot", field + ".determination");
        var snapshot = t!.SourceSnapshot;
        Require(snapshot.ValueKind == JsonValueKind.Object &&
            snapshot.TryGetProperty("company", out var company) && company.ValueKind == JsonValueKind.Object &&
            company.TryGetProperty("id", out var companyId) && CanonicalGuid(companyId, out var parsedCompany) &&
            parsedCompany == request.CompanyId && company.TryGetProperty("registrationId", out var registrationId) &&
            CanonicalGuid(registrationId, out var parsedRegistration) && parsedRegistration == r.CompanyTaxRegistrationId,
            "tax_calculation_invalid_snapshot", field + ".determination");
    }
}
