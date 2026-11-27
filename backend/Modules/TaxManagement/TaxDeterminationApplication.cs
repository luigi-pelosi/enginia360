using System.Text.Json;
using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

/// <summary>Orchestrazione F4 condivisa: snapshot trusted, una valutazione per chiamata.</summary>
public static class TaxDeterminationApplication
{
    public static async Task<TaxDeterminationOutcome> Evaluate(HttpContext ctx, AppDb db,
        Guid tenant, TaxDeterminationRequest request, bool simulation)
    {
        await TaxContextResolver.GateSources(ctx, db, tenant, request.CompanyId, simulation ? "simulate" : "determine");
        var resolution = await new TaxContextResolver(db).Resolve(ctx, tenant, request);
        var context = resolution.Context;
        var candidates = await Materialize(db, tenant, context.ItalyCountryId, request, simulation);
        var codes = await TaxRuleReferences.Codes(db, tenant, candidates.Select(c => c.Version.TaxCodeId),
            context.ItalyCountryId, request.TaxTypeId);
        var snapshot = context.Snapshot.EnumerateObject()
            .ToDictionary(p => p.Name, p => p.Value.Clone(), StringComparer.Ordinal);
        snapshot["rules"] = JsonSerializer.SerializeToElement(candidates.Select(c => new
        {
            ruleId = c.RuleId, ruleRevision = c.RuleRevision, versionId = c.Version.Id, status = c.Version.Status
        }));
        snapshot["taxCodes"] = JsonSerializer.SerializeToElement(codes.OrderBy(c => c.Key).Select(c => new
        {
            id = c.Key, revision = c.Value.Aggregate.Revision, versionIds = c.Value.Aggregate.Versions.Select(v => v.Id)
        }));
        context = context with { Snapshot = JsonSerializer.SerializeToElement(snapshot) };
        if (resolution.Outcome != null)
        {
            var territoriality = TaxTerritorialityResolver.Resolve(context);
            var failure = resolution.Outcome == "UNSUPPORTED_OPERATION" || territoriality.Outcome == "UNSUPPORTED_OPERATION"
                ? "UNSUPPORTED_OPERATION" : "INCOMPLETE_CONTEXT";
            var trace = new TaxDeterminationTrace(context.TaxDate, context.OperationType, territoriality,
                resolution.Issues.Concat(territoriality.MissingFields).Distinct().Order(StringComparer.Ordinal).ToArray(),
                System.Array.Empty<TaxCandidateTrace>(), context.Snapshot);
            return new TaxDeterminationOutcome(failure, null, trace, simulation);
        }
        var outcome = TaxDeterminationEngine.Determine(context, candidates, codes, simulation);
        return outcome;
    }

    private static async Task<List<TaxRuleCandidate>> Materialize(AppDb db, Guid tenant, Guid country,
        TaxDeterminationRequest request, bool simulation)
    {
        var requested = request.DraftVersionIds.ToArray();
        // Un solo ordine delle radici, comprese le bozze esplicitamente richieste.
        var ids = await Rows(db,
            "SELECT DISTINCT r.id FROM taxmanagement.tax_rules r " +
            "JOIN taxmanagement.tax_rule_versions v ON v.tenant_id=r.tenant_id AND v.tax_rule_id=r.id " +
            "WHERE r.tenant_id=@t AND ((r.country_id=@c AND r.tax_type_id=@type " +
            "AND (r.company_id IS NULL OR r.company_id=@company) AND v.operation_type=@op " +
            "AND v.status='PUBLISHED') OR v.id=ANY(@drafts::uuid[])) ORDER BY r.id",
            ("t", tenant), ("c", country), ("type", request.TaxTypeId), ("company", request.CompanyId),
            ("op", request.OperationType), ("drafts", requested));
        var roots = new List<TaxRuleSnapshot>();
        foreach (var id in ids)
            roots.Add(TaxRuleApplication.Snapshot(await TaxRuleApplication.Read(db, tenant, (Guid)id["id"]!, share: true)));
        var drafts = new Dictionary<Guid, TaxRuleVersion>();
        foreach (var id in requested)
        {
            var root = roots.SingleOrDefault(r => r.Versions.Any(v => v.Id == id))
                ?? throw new ApiException(404, "tax_rule_version_not_found", "draft_version_ids");
            var draft = root.Versions.Single(v => v.Id == id);
            Require(root.CountryId == country && root.TaxTypeId == request.TaxTypeId &&
                (root.CompanyId == null || root.CompanyId == request.CompanyId),
                "tax_rule_draft_scope_mismatch", field: "draft_version_ids");
            Require(simulation && draft.Status == "DRAFT" && draft.OperationType == request.OperationType,
                "tax_rule_draft_required", field: "draft_version_ids");
            Require(CompanyTaxConfiguration.Covers(draft.ValidFrom, draft.ValidTo, request.TaxDate),
                "tax_rule_draft_date_mismatch", field: "draft_version_ids");
            Require(drafts.TryAdd(root.Id, draft), "tax_rule_duplicate_draft_root", field: "draft_version_ids");
        }
        var candidates = new List<TaxRuleCandidate>();
        foreach (var root in roots)
        {
            if (drafts.TryGetValue(root.Id, out var draft))
            {
                candidates.Add(new(root.Id, root.Code, root.Revision, root.CompanyId, draft));
                continue;
            }
            candidates.AddRange(root.Versions.Where(v => v.Status == "PUBLISHED" &&
                v.OperationType == request.OperationType &&
                CompanyTaxConfiguration.Covers(v.ValidFrom, v.ValidTo, request.TaxDate))
                .Select(v => new TaxRuleCandidate(root.Id, root.Code, root.Revision, root.CompanyId, v)));
        }
        return candidates;
    }
}
