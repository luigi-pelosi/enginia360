using System.Text.Json;

namespace Enginia360.Modules.TaxManagement;

public sealed record TaxRuleCondition(Guid Id, string Field, string Operator, JsonElement Value);
public sealed record TaxRuleVersion(Guid Id, int VersionNumber, Guid TaxCodeId, int Priority,
    string OperationType, string Status, string LegalReference, DateOnly ValidFrom, DateOnly? ValidTo,
    IReadOnlyList<TaxRuleCondition> Conditions);
public sealed record TaxRuleSnapshot(Guid Id, Guid TenantId, Guid? CompanyId, Guid CountryId,
    Guid TaxTypeId, string Code, long Revision, IReadOnlyList<TaxRuleVersion> Versions);
public sealed record TaxRuleCandidate(Guid RuleId, string RuleCode, long RuleRevision,
    Guid? CompanyId, TaxRuleVersion Version);
public sealed record DeterminationTaxCode(Guid CountryId, Guid TaxTypeId, string Code, TaxCode Aggregate);
public sealed record TaxRuleIssue(string Code, string? Field = null);
public sealed record TaxConditionField(string Key, string Type, IReadOnlyList<string> Operators,
    string? Reference, IReadOnlyList<string> Values, bool Available = true);
public sealed record TaxConditionMatch(Guid ConditionId, string Field, string Operator, string Result);
public sealed record TaxRuleMatch(string Result, IReadOnlyList<TaxConditionMatch> Conditions);

public sealed record TaxDeterminationContext
{
    public Guid TenantId { get; init; }
    public Guid CompanyId { get; init; }
    public Guid BusinessPartnerId { get; init; }
    public Guid ItemId { get; init; }
    public Guid TaxTypeId { get; init; }
    public Guid ItalyCountryId { get; init; }
    public DateOnly TaxDate { get; init; }
    public string OperationType { get; init; } = "";
    public string TaxTypeCode { get; init; } = "";
    public string ItemKind { get; init; } = "";
    public string CompanyRegimeCode { get; init; } = "";
    public Guid? CompanyTaxRegistrationId { get; init; }
    public IReadOnlyDictionary<string, JsonElement?> Fields { get; init; } = new Dictionary<string, JsonElement?>();
    public JsonElement Snapshot { get; init; }
}

public sealed record TaxTerritorialityOutcome(string Outcome, Guid? JurisdictionCountryId,
    Guid? PlaceOfSupplyCountryId, string? TerritorialScope, string? LegalReference,
    IReadOnlyList<string> MissingFields);
public sealed record TaxCandidateTrace(Guid RuleId, Guid VersionId, long RuleRevision, int Priority,
    string Status, string Result, IReadOnlyList<TaxConditionMatch> Conditions);
public sealed record TaxDeterminationTrace(DateOnly TaxDate, string OperationType,
    TaxTerritorialityOutcome Territoriality, IReadOnlyList<string> MissingFields,
    IReadOnlyList<TaxCandidateTrace> Candidates, JsonElement SourceSnapshot,
    Guid? TaxCodeId = null, long? TaxCodeRevision = null, Guid? TaxCodeVersionId = null);
public sealed record TaxDeterminationResult(Guid TaxRuleId, Guid TaxRuleVersionId, Guid TaxCodeId,
    Guid TaxCodeVersionId, Guid CompanyTaxRegistrationId, Guid TaxJurisdictionCountryId,
    string TaxType, string Treatment, string Rate, string? TaxNatureCode, string LiableParty,
    string CollectionMechanism, DateOnly TaxDate, string LegalReference,
    TaxDeterminationTrace DeterminationTrace);
public sealed record TaxDeterminationOutcome(string Outcome, TaxDeterminationResult? Result,
    TaxDeterminationTrace Trace, bool IsSimulation);
