using System.Text.Json;

namespace Enginia360.Modules.TaxManagement;

public static class TaxConditionFields
{
    private static readonly string[] SetOperators = ["EQUALS", "NOT_EQUALS", "IN", "NOT_IN"];
    private static readonly string[] BooleanOperators = ["EQUALS", "NOT_EQUALS", "IS_TRUE", "IS_FALSE"];
    public static IReadOnlyList<TaxConditionField> All { get; } = Array.AsReadOnly(new TaxConditionField[]
    {
        Reference("company.taxRegime", "regimes"),
        Reference("company.registrationCountry", "countries"),
        Reference("company.establishmentCountry", "countries"),
        Reference("partner.taxClassification", "partnerClassifications"),
        Reference("partner.taxIdentifierCountry", "countries"),
        Reference("item.taxClassification", "itemClassifications"),
        Reference("transaction.dispatchCountry", "countries"),
        Reference("transaction.destinationCountry", "countries"),
        Reference("transaction.serviceLocationCountry", "countries"),
        Reference("transaction.placeOfSupply", "countries"),
        Reference("partner.establishmentCountry", "countries"),
        Enum("item.nature", ["GOOD", "INTANGIBLE", "SERVICE", "CHARGE"]),
        Enum("transaction.operationType", ["SALE", "PURCHASE"]),
        Enum("transaction.territorialScope", ["DOMESTIC", "INTRA_EU", "EXTRA_EU"]),
        Enum("transaction.operationCategory", ["ORDINARY_MOVABLE_GOODS", "GENERAL_SERVICES"]),
        Enum("transaction.specialTaxTreatment", ["NONE", "REVERSE_CHARGE", "SPLIT_PAYMENT", "EXEMPT", "MARGIN", "OTHER"]),
        Enum("transaction.goodsCustomsStatus", ["NATIONAL_OR_UNION", "OTHER"]),
        new("partner.vatValidationStatus", "ENUM", Array.AsReadOnly(SetOperators), null,
            Array.AsReadOnly(new[] { "VALID", "INVALID" }), false),
        new("partner.actingAsTaxablePerson", "BOOLEAN", Array.AsReadOnly(BooleanOperators), null, Array.Empty<string>()),
        new("transaction.ordinaryVatTerritoryConfirmed", "BOOLEAN", Array.AsReadOnly(BooleanOperators), null, Array.Empty<string>())
    });
    public static TaxConditionField? Find(string key) => All.FirstOrDefault(x => x.Key == key);
    private static TaxConditionField Reference(string key, string reference) =>
        new(key, "REFERENCE", Array.AsReadOnly(SetOperators), reference, Array.Empty<string>());
    private static TaxConditionField Enum(string key, string[] values) =>
        new(key, "ENUM", Array.AsReadOnly(SetOperators), null, Array.AsReadOnly(values));
}

public static class TaxRuleMatcher
{
    public static TaxRuleMatch Match(TaxRuleVersion version, IReadOnlyDictionary<string, JsonElement?> fields)
    {
        var trace = version.Conditions.OrderBy(x => x.Id).ThenBy(x => x.Field, StringComparer.Ordinal)
            .ThenBy(x => x.Operator, StringComparer.Ordinal).Select(condition =>
            {
                var metadata = TaxConditionFields.Find(condition.Field);
                fields.TryGetValue(condition.Field, out var actual);
                var result = "UNKNOWN";
                if (metadata is { Available: true } && TaxConditionLogic.Valid(condition, metadata) &&
                    actual.HasValue && TaxConditionLogic.TryAtom(actual.Value, metadata, out var atom))
                    result = TaxConditionLogic.Accepts(condition, metadata, atom) ? "MATCH" : "NO_MATCH";
                return new TaxConditionMatch(condition.Id, condition.Field, condition.Operator, result);
            }).ToArray();
        // La falsità prevale anche quando un'altra condizione è sconosciuta.
        return new(trace.Any(x => x.Result == "NO_MATCH") ? "NO_MATCH" :
            trace.Any(x => x.Result == "UNKNOWN") ? "UNKNOWN" : "MATCH", trace);
    }
}

internal static class TaxConditionLogic
{
    internal static bool TryAtom(JsonElement value, TaxConditionField field, out string atom)
    {
        atom = "";
        if (field.Type == "BOOLEAN")
        {
            if (value.ValueKind is not (JsonValueKind.True or JsonValueKind.False)) return false;
            atom = value.GetBoolean() ? "true" : "false";
            return true;
        }
        if (value.ValueKind != JsonValueKind.String) return false;
        var text = value.GetString();
        if (field.Type == "REFERENCE")
        {
            if (text?.Length != 36 || !Guid.TryParseExact(text, "D", out var id) || id == Guid.Empty) return false;
            atom = id.ToString("D");
            return true;
        }
        if (text == null || !field.Values.Contains(text, StringComparer.Ordinal)) return false;
        atom = text;
        return true;
    }
    internal static bool Valid(TaxRuleCondition condition, TaxConditionField field)
    {
        if (!field.Operators.Contains(condition.Operator, StringComparer.Ordinal)) return false;
        if (condition.Operator is "IS_TRUE" or "IS_FALSE") return condition.Value.ValueKind == JsonValueKind.Null;
        if (condition.Operator is "IN" or "NOT_IN")
        {
            if (condition.Value.ValueKind != JsonValueKind.Array) return false;
            var values = condition.Value.EnumerateArray().ToArray();
            if (values.Length is < 1 or > 100) return false;
            var unique = new HashSet<string>(StringComparer.Ordinal);
            foreach (var value in values)
                if (!TryAtom(value, field, out var atom) || !unique.Add(atom)) return false;
            return true;
        }
        return TryAtom(condition.Value, field, out _);
    }
    internal static string[] Atoms(TaxRuleCondition condition, TaxConditionField field)
    {
        if (condition.Operator is "IS_TRUE" or "IS_FALSE") return [condition.Operator == "IS_TRUE" ? "true" : "false"];
        return (condition.Value.ValueKind == JsonValueKind.Array ? condition.Value.EnumerateArray().ToArray() : [condition.Value])
            .Select(v => { TryAtom(v, field, out var atom); return atom; }).ToArray();
    }
    internal static bool Accepts(TaxRuleCondition condition, TaxConditionField field, string atom)
    {
        var contains = Atoms(condition, field).Contains(atom, StringComparer.Ordinal);
        return condition.Operator is "NOT_EQUALS" or "NOT_IN" ? !contains : contains;
    }
    internal static bool Satisfiable(IEnumerable<TaxRuleCondition> conditions)
    {
        foreach (var group in conditions.GroupBy(x => x.Field, StringComparer.Ordinal))
        {
            var field = TaxConditionFields.Find(group.Key);
            // Metadati non conosciuti non dimostrano disgiunzione.
            if (field == null || group.Any(x => !Valid(x, field))) continue;
            HashSet<string>? allowed = field.Type switch
            {
                "BOOLEAN" => new(["true", "false"], StringComparer.Ordinal),
                "ENUM" => new(field.Values, StringComparer.Ordinal),
                _ => null
            };
            var excluded = new HashSet<string>(StringComparer.Ordinal);
            foreach (var condition in group)
            {
                var atoms = Atoms(condition, field);
                if (condition.Operator is "NOT_EQUALS" or "NOT_IN") excluded.UnionWith(atoms);
                else if (allowed == null) allowed = new(atoms, StringComparer.Ordinal);
                else allowed.IntersectWith(atoms);
            }
            if (allowed != null)
            {
                allowed.ExceptWith(excluded);
                if (allowed.Count == 0) return false;
            }
        }
        return true;
    }
    internal static string Identity(TaxRuleCondition condition, TaxConditionField field) =>
        condition.Field + ":" + condition.Operator + ":" + string.Join(",", Atoms(condition, field).Order(StringComparer.Ordinal));
}

public static class TaxRuleConflictDetector
{
    public static bool Overlaps(TaxRuleCandidate left, TaxRuleCandidate right)
    {
        if (left.Version.Priority != right.Version.Priority || left.Version.OperationType != right.Version.OperationType ||
            left.CompanyId.HasValue && right.CompanyId.HasValue && left.CompanyId != right.CompanyId ||
            !TaxRules.Overlaps(left.Version.ValidFrom, left.Version.ValidTo, right.Version.ValidFrom, right.Version.ValidTo)) return false;
        return TaxConditionLogic.Satisfiable(left.Version.Conditions.Concat(right.Version.Conditions));
    }
}
