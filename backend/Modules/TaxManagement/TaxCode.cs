namespace Enginia360.Modules.TaxManagement;

/// <summary>Identità fiscale stabile e confine delle proprie versioni temporali.</summary>
public sealed class TaxCode
{
    public Guid Id { get; }
    public Guid TenantId { get; }
    public long Revision { get; }
    public bool IsActive { get; }
    public bool IsTypeSupported { get; }
    public IReadOnlyList<TaxFiscalVersion> Versions { get; }

    public TaxCode(Guid id, Guid tenantId, long revision, bool isActive,
        bool isTypeSupported, IEnumerable<TaxFiscalVersion> versions)
    {
        TaxRules.Require(id != Guid.Empty && tenantId != Guid.Empty, "tax_invalid_id");
        TaxRules.Require(revision is >= 1 and <= TaxRules.MaxRevision, "tax_invalid_expected_version");
        var ordered = versions.OrderBy(v => v.ValidFrom).ToArray();
        TaxRules.Require(ordered.Length > 0, "tax_versions_required");
        for (var i = 0; i < ordered.Length; i++)
        {
            var current = ordered[i];
            TaxRules.Require(current.ValidTo == null || current.ValidTo >= current.ValidFrom, "tax_invalid_interval");
            if (i > 0)
                TaxRules.Require(!TaxRules.Overlaps(ordered[i - 1].ValidFrom, ordered[i - 1].ValidTo,
                    current.ValidFrom, current.ValidTo), "tax_version_overlap", 409);
        }
        Id = id;
        TenantId = tenantId;
        Revision = revision;
        IsActive = isActive;
        IsTypeSupported = isTypeSupported;
        Versions = Array.AsReadOnly(ordered);
    }

    public TaxFiscalVersion ResolveVersionAt(DateOnly taxDate, bool forNewUse = false)
    {
        if (forNewUse) RequireNewUse();
        var version = TaxRules.Resolve(Versions, taxDate);
        TaxRules.Require(version != null, "tax_version_not_found", 404);
        return version!;
    }

    // Il piano viene applicato dalla persistenza sotto lock nella stessa transazione.
    public TaxSchedulePlan PlanVersion(TaxFiscalVersion successor, long expectedRevision)
    {
        TaxRules.CheckRevision(expectedRevision, Revision);
        RequireNewUse();
        return TaxRules.Schedule(Versions, successor);
    }

    private void RequireNewUse()
    {
        TaxRules.Require(IsActive, "tax_inactive", 409);
        TaxRules.Require(IsTypeSupported, "tax_type_not_supported", 409);
    }
}
