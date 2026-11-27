using System.Text.Json;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

public static class TaxDeterminationEngine
{
    public static TaxDeterminationOutcome Determine(TaxDeterminationContext context,
        IReadOnlyList<TaxRuleCandidate> candidates, IReadOnlyDictionary<Guid, DeterminationTaxCode> codes,
        bool simulation = false)
    {
        var territory = TaxTerritorialityResolver.Resolve(context);
        var missing = new SortedSet<string>(territory.MissingFields, StringComparer.Ordinal);
        var traces = new List<TaxCandidateTrace>();
        // Snapshot già minimizzato dall'adattatore: non riceve aggregati commerciali o identificativi fiscali grezzi.
        var snapshot = context.Snapshot.ValueKind == JsonValueKind.Undefined
            ? JsonSerializer.SerializeToElement<object?>(null) : CanonicalSnapshot(context.Snapshot);
        TaxDeterminationTrace Trace(Guid? codeId = null, long? revision = null, Guid? versionId = null) =>
            new(context.TaxDate, context.OperationType, territory, missing.ToArray(), traces.ToArray(), snapshot,
                codeId, revision, versionId);
        TaxDeterminationOutcome Fail(string outcome, Guid? codeId = null, long? revision = null, Guid? versionId = null) =>
            new(outcome, null, Trace(codeId, revision, versionId), simulation);
        if (territory.Outcome != "SUCCESS") return Fail(territory.Outcome);
        if (context.TenantId == Guid.Empty) missing.Add("tenantId");
        if (context.CompanyId == Guid.Empty) missing.Add("companyId");
        if (context.BusinessPartnerId == Guid.Empty) missing.Add("businessPartnerId");
        if (context.ItemId == Guid.Empty) missing.Add("itemId");
        if (context.TaxTypeId == Guid.Empty) missing.Add("taxTypeId");
        if (context.CompanyTaxRegistrationId is null || context.CompanyTaxRegistrationId == Guid.Empty)
            missing.Add("company.taxRegistration");
        foreach (var key in new[] { "item.taxClassification", "partner.taxClassification", "company.taxRegime" })
        {
            if (!context.Fields.TryGetValue(key, out var value) || !value.HasValue ||
                !TaxConditionLogic.TryAtom(value.Value, TaxConditionFields.Find(key)!, out _)) missing.Add(key);
        }
        if (missing.Count > 0) return Fail("INCOMPLETE_CONTEXT");
        var fields = new Dictionary<string, JsonElement?>(context.Fields, StringComparer.Ordinal)
        {
            ["item.nature"] = JsonSerializer.SerializeToElement(context.ItemKind),
            ["transaction.operationType"] = JsonSerializer.SerializeToElement(context.OperationType),
            ["transaction.placeOfSupply"] = JsonSerializer.SerializeToElement(territory.PlaceOfSupplyCountryId),
            ["transaction.territorialScope"] = JsonSerializer.SerializeToElement(territory.TerritorialScope),
            // In assenza di un provider non si accetta una validazione VIES inventata dal chiamante.
            ["partner.vatValidationStatus"] = null
        };
        var eligible = candidates.Where(c =>
                (c.CompanyId == null || c.CompanyId == context.CompanyId) &&
                c.Version.OperationType == context.OperationType &&
                c.Version.ValidFrom <= context.TaxDate && (c.Version.ValidTo == null || context.TaxDate <= c.Version.ValidTo) &&
                (c.Version.Status == "PUBLISHED" || simulation && c.Version.Status == "DRAFT"))
            .OrderByDescending(c => c.Version.Priority).ThenBy(c => c.RuleId).ThenBy(c => c.Version.Id).ToArray();
        var draftRoots = eligible.Where(c => c.Version.Status == "DRAFT").Select(c => c.RuleId).ToHashSet();
        var evaluated = new List<(TaxRuleCandidate Candidate, TaxRuleMatch Match)>();
        foreach (var candidate in eligible)
        {
            if (candidate.Version.Status == "PUBLISHED" && draftRoots.Contains(candidate.RuleId)) continue;
            var match = TaxRuleMatcher.Match(candidate.Version, fields);
            traces.Add(new(candidate.RuleId, candidate.Version.Id, candidate.RuleRevision, candidate.Version.Priority,
                candidate.Version.Status, match.Result, match.Conditions));
            evaluated.Add((candidate, match));
        }
        var potential = evaluated.Where(x => x.Match.Result != "NO_MATCH").ToArray();
        if (potential.Length == 0) return Fail("NO_MATCHING_RULE");
        var priority = potential.Max(x => x.Candidate.Version.Priority);
        var top = potential.Where(x => x.Candidate.Version.Priority == priority).ToArray();
        var matched = top.Where(x => x.Match.Result == "MATCH").ToArray();
        if (matched.Length > 1) return Fail("AMBIGUOUS_RULE");
        if (top.Any(x => x.Match.Result == "UNKNOWN"))
        {
            foreach (var condition in top.SelectMany(x => x.Match.Conditions).Where(x => x.Result == "UNKNOWN"))
                missing.Add(condition.Field);
            return Fail("INCOMPLETE_CONTEXT");
        }
        var winner = matched.Single().Candidate;
        var codeId = winner.Version.TaxCodeId;
        if (!codes.TryGetValue(codeId, out var code) || code.Aggregate.Id != codeId ||
            code.Aggregate.TenantId != context.TenantId || code.CountryId != context.ItalyCountryId || code.TaxTypeId != context.TaxTypeId)
            return Fail("TAX_CODE_UNAVAILABLE", codeId);
        TaxFiscalVersion fiscal;
        try { fiscal = code.Aggregate.ResolveVersionAt(context.TaxDate, true); }
        catch (ApiException) { return Fail("TAX_CODE_UNAVAILABLE", codeId, code.Aggregate.Revision); }
        if (fiscal.Treatment != "TAXABLE" || fiscal.Rate <= 0 || fiscal.TaxNatureCodeId != null)
            return Fail("UNSUPPORTED_OPERATION", codeId, code.Aggregate.Revision, fiscal.Id);
        var trace = Trace(codeId, code.Aggregate.Revision, fiscal.Id);
        var result = new TaxDeterminationResult(winner.RuleId, winner.Version.Id, codeId, fiscal.Id,
            context.CompanyTaxRegistrationId!.Value, context.ItalyCountryId, context.TaxTypeCode, fiscal.Treatment,
            TaxRules.RateText(fiscal.Rate), null, "SUPPLIER", "STANDARD", context.TaxDate,
            winner.Version.LegalReference, trace);
        return new("SUCCESS", result, trace, simulation);
    }

    private static JsonElement CanonicalSnapshot(JsonElement value)
    {
        // L'ordine delle proprietà non dipende dall'ordine di materializzazione delle righe.
        object? Normalize(JsonElement element) => element.ValueKind switch
        {
            JsonValueKind.Object => element.EnumerateObject().OrderBy(x => x.Name, StringComparer.Ordinal)
                .ToDictionary(x => x.Name, x => Normalize(x.Value), StringComparer.Ordinal),
            JsonValueKind.Array => element.EnumerateArray().Select(Normalize).ToArray(),
            JsonValueKind.Undefined or JsonValueKind.Null => null,
            _ => element.Clone()
        };
        return JsonSerializer.SerializeToElement(Normalize(value));
    }
}
