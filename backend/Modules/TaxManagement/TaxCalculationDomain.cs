namespace Enginia360.Modules.TaxManagement;

public sealed record TaxAdjustment(Guid AdjustmentId, string Type, string CalculationMode,
    string Value, int Sequence, IReadOnlyList<Guid>? ApplicableLineIds = null);
public sealed record TaxCalculationPolicy(string Code, int Version, string Currency,
    int CurrencyScale, int InternalScale, string RoundingMode, string RoundingScope,
    string ResidualAllocationMode);
public static class TaxCalculationPolicies
{
    public static TaxCalculationPolicy Standard { get; } = new(
        "IT_VAT_STANDARD_V1", 1, "EUR", 2, 12, "HALF_UP", "TAX_GROUP", "LARGEST_REMAINDER");
}
public sealed record TaxCalculationDetermination(Guid TenantId, Guid CompanyId,
    string OperationType, TaxDeterminationResult Result, bool IsSimulation);
public sealed record TaxCalculationLine(Guid LineId, string Quantity, string UnitPrice,
    string PriceMode, IReadOnlyList<TaxAdjustment> Adjustments,
    TaxCalculationDetermination Determination, string? DeductiblePercentage = null,
    string? Currency = null);
public sealed record TaxCalculationRequest(Guid TenantId, Guid CompanyId, string Currency,
    string OperationType, string Direction, IReadOnlyList<TaxCalculationLine> Lines,
    IReadOnlyList<TaxAdjustment> DocumentAdjustments, TaxCalculationPolicy Policy);

public sealed record TaxDeductibilityResult(string TaxAmount, string DeductibleAmount,
    string NonDeductibleAmount);
public sealed record TaxCalculationLineResult(Guid LineId, Guid TaxRuleVersionId,
    Guid TaxCodeId, Guid TaxCodeVersionId, string PriceMode, string NetBeforeAdjustments,
    string NetDiscountAmount, string NetSurchargeAmount, string NetAmount,
    string TaxableAmount, string TaxRate, string TaxAmount, string InvoiceTaxAmount,
    string GrossAmount, string RoundingAdjustment, string NetRoundingAdjustment,
    string TaxRoundingAdjustment, TaxDeductibilityResult? Deductibility);
public sealed record TaxSummary(Guid TaxCodeId, Guid TaxCodeVersionId, string TaxType,
    Guid JurisdictionCountryId, string Treatment, string Rate, string? NatureCode,
    string LiableParty, string CollectionMechanism, string PriceMode, string NetAmount,
    string TaxableAmount, string TaxAmount, string InvoiceTaxAmount, string GrossAmount,
    string RoundingAdjustment, string NetRoundingAdjustment, string TaxRoundingAdjustment);
public sealed record TaxDocumentTotals(string NetBeforeAdjustments, string NetDiscountAmount,
    string NetSurchargeAmount, string NetAmount, string TotalTaxableAmount,
    string TotalNonTaxableAmount, string TotalTaxAmount, string TotalInvoiceTaxAmount,
    string GrossAmount, string AmountPayable, string NetRoundingAdjustment,
    string TaxRoundingAdjustment, string RoundingAdjustment);
// Le frazioni di traccia sono esatte (numeratore/denominatore), non anteprime arrotondate.
public sealed record TaxAdjustmentAllocation(Guid LineId, string PriceBaseAmountExact);
public sealed record TaxAdjustmentTrace(Guid AdjustmentId, string Scope, string Type,
    string CalculationMode, int Sequence, string PriceMode, string PriceBaseAmountExact,
    IReadOnlyList<TaxAdjustmentAllocation> Allocations);
public sealed record TaxCalculationSource(Guid LineId, Guid TaxRuleId, Guid TaxRuleVersionId,
    Guid TaxCodeId, Guid TaxCodeVersionId, Guid CompanyTaxRegistrationId,
    Guid JurisdictionCountryId, DateOnly TaxDate, bool IsSimulation);
public sealed record TaxCalculationTrace(string PolicyCode, int PolicyVersion,
    string ExactArithmetic, IReadOnlyList<TaxCalculationSource> Sources,
    IReadOnlyList<TaxAdjustmentTrace> Adjustments);
public sealed record TaxCalculationResult(string Currency, string CalculationPolicyCode,
    int CalculationPolicyVersion, IReadOnlyList<TaxCalculationLineResult> Lines,
    IReadOnlyList<TaxSummary> Summaries, TaxDocumentTotals Totals,
    TaxCalculationTrace CalculationTrace);
