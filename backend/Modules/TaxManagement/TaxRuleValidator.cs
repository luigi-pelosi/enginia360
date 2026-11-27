namespace Enginia360.Modules.TaxManagement;

public static class TaxRuleValidator
{
    // La validazione strutturale non consulta database né attribuisce esistenza ai riferimenti.
    public static IReadOnlyList<TaxRuleIssue> Validate(TaxRuleSnapshot rule, TaxRuleVersion version)
    {
        var issues = new List<TaxRuleIssue>();
        void Add(bool invalid, string code, string? field = null)
        { if (invalid) issues.Add(new(code, field)); }
        Add(rule.Id == Guid.Empty || rule.TenantId == Guid.Empty || rule.CountryId == Guid.Empty ||
            rule.TaxTypeId == Guid.Empty || rule.CompanyId == Guid.Empty || version.Id == Guid.Empty ||
            version.TaxCodeId == Guid.Empty, "tax_rule_invalid_id");
        Add(rule.Revision is < 1 or > TaxRules.MaxRevision, "tax_rule_invalid_revision");
        Add(string.IsNullOrWhiteSpace(rule.Code) || rule.Code.Length > 50, "tax_rule_invalid_code", "code");
        Add(version.VersionNumber < 1, "tax_rule_invalid_version", "version_number");
        Add(version.ValidTo < version.ValidFrom, "tax_rule_invalid_interval", "valid_to");
        Add(version.OperationType is not ("SALE" or "PURCHASE"), "tax_rule_invalid_operation", "operation_type");
        Add(version.Status is not ("DRAFT" or "PUBLISHED" or "WITHDRAWN"), "tax_rule_invalid_status", "status");
        Add(string.IsNullOrWhiteSpace(version.LegalReference) || version.LegalReference.Length > 255 ||
            version.LegalReference.Any(char.IsControl), "tax_rule_invalid_legal_reference", "legal_reference");
        Add(version.Conditions.Count > 100, "tax_rule_too_many_conditions", "conditions");
        var ids = new HashSet<Guid>();
        var identities = new HashSet<string>(StringComparer.Ordinal);
        var allValid = true;
        foreach (var condition in version.Conditions.OrderBy(c => c.Id))
        {
            Add(condition.Id == Guid.Empty || !ids.Add(condition.Id), "tax_rule_invalid_condition_id", "conditions");
            var metadata = TaxConditionFields.Find(condition.Field);
            if (metadata == null)
            {
                issues.Add(new("tax_rule_unknown_field", condition.Field)); allValid = false; continue;
            }
            Add(!metadata.Available, "tax_rule_field_unavailable", condition.Field);
            if (!metadata.Operators.Contains(condition.Operator, StringComparer.Ordinal))
            {
                issues.Add(new("tax_rule_invalid_operator", condition.Field)); allValid = false; continue;
            }
            if (!TaxConditionLogic.Valid(condition, metadata))
            {
                issues.Add(new("tax_rule_invalid_value", condition.Field)); allValid = false; continue;
            }
            Add(!identities.Add(TaxConditionLogic.Identity(condition, metadata)), "tax_rule_duplicate_condition", condition.Field);
        }
        if (allValid)
            foreach (var group in version.Conditions.GroupBy(x => x.Field, StringComparer.Ordinal).OrderBy(x => x.Key, StringComparer.Ordinal))
                Add(!TaxConditionLogic.Satisfiable(group), "tax_rule_contradictory_conditions", group.Key);
        return issues.Distinct().ToArray();
    }
}
