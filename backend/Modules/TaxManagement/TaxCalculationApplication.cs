using Enginia360.Infrastructure.Persistence;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.TaxClassificationApplication;
using static Enginia360.Modules.TaxManagement.TaxRuleInput;
namespace Enginia360.Modules.TaxManagement;

public sealed record TaxCalculationApplicationOutcome(TaxCalculationResult? Result,
    TaxDeterminationOutcome? FiscalFailure, int? FailedLineIndex);

/// <summary>Acquisisce fonti trusted una sola volta per riga; il core successivo non legge il DB.</summary>
public static class TaxCalculationApplication
{
    public static async Task<TaxCalculationApplicationOutcome> Calculate(HttpContext ctx, AppDb db,
        Guid tenant, TaxCalculationInputRequest input, bool simulation)
    {
        var permission = "tax-calculation." + (simulation ? "simulate" : "calculate");
        await TaxRuleReferences.Action(ctx, db, tenant, input.CompanyId, permission);
        // Tutti i gate precedono anche la pianificazione: nessuna lettura fonti senza l'azione F4.
        await TaxContextResolver.GateSources(ctx, db, tenant, input.CompanyId, simulation ? "simulate" : "determine");
        var resolvedPolicy = await TaxCalculationPolicyResolver.Resolve(db, input.Currency);
        await Prelock(db, tenant, input);
        await TaxRuleReferences.Action(ctx, db, tenant, input.CompanyId, permission);
        var snapshots = new List<TaxCalculationLine>(input.Lines.Count);
        for (var i = 0; i < input.Lines.Count; i++)
        {
            var line = input.Lines[i];
            TaxDeterminationOutcome outcome;
            try
            {
                outcome = await TaxDeterminationApplication.Evaluate(ctx, db, tenant, line.FiscalContext, simulation);
            }
            catch (ApiException e)
            {
                throw new ApiException(e.Status, e.Code, "lines[" + i + "].fiscal_context" +
                    (e.Field == null ? "" : "." + e.Field));
            }
            if (outcome.Outcome != "SUCCESS" || outcome.Result == null)
                return new(null, outcome, i);
            var trusted = new TaxCalculationDetermination(tenant, input.CompanyId,
                input.OperationType, outcome.Result, outcome.IsSimulation);
            snapshots.Add(new(line.LineId, line.Quantity, line.UnitPrice, line.PriceMode,
                line.Adjustments, trusted, line.DeductiblePercentage, line.Currency));
        }
        var request = new TaxCalculationRequest(tenant, input.CompanyId, input.Currency,
            input.OperationType, input.Direction, snapshots.AsReadOnly(), input.DocumentAdjustments,
            resolvedPolicy.Policy);
        return new(TaxCalculationEngine.Calculate(request), null, null);
    }

    /// <summary>
    /// Ordine globale F4: ruleset, company, BP, item/tipi, stream profili, configurazioni,
    /// identità classificazioni, regole, codici. Tutte le radici dell'intero batch prima del loop.
    /// I lock riacquisiti da Evaluate sono già detenuti dalla transazione della richiesta.
    /// </summary>
    private static async Task Prelock(AppDb db, Guid tenant, TaxCalculationInputRequest input)
    {
        var first = input.Lines[0].FiscalContext;
        var italy = await db.Scalar("SELECT id FROM foundation.country WHERE iso_code='IT' AND is_enabled");
        Require(italy is Guid, "tax_country_not_found", 404, "lines[0].fiscal_context.country_id");
        var country = (Guid)italy!;
        await TaxRuleReferences.RulesetLock(db, tenant, country, first.TaxTypeId, input.OperationType);
        await CompanyTaxApplication.Lock(db, tenant, false);
        await CompanyTaxApplication.Company(db, tenant, input.CompanyId, false);

        var partners = input.Lines.Select(l => l.FiscalContext.BusinessPartnerId).Distinct().Order().ToArray();
        var items = input.Lines.Select(l => l.FiscalContext.ItemId).Distinct().Order().ToArray();
        var lockedPartners = await Rows(db, "SELECT id FROM masterdata.business_partner WHERE tenant_id=@t AND id=ANY(@ids::uuid[]) ORDER BY id FOR SHARE",
            ("t", tenant), ("ids", partners));
        var knownPartners = lockedPartners.Select(r => (Guid)r["id"]!).ToHashSet();
        for (var i = 0; i < input.Lines.Count; i++)
            Require(knownPartners.Contains(input.Lines[i].FiscalContext.BusinessPartnerId),
                "tax_partner_not_found", 404, "lines[" + i + "].fiscal_context.business_partner_id");
        var lockedItems = await Rows(db, "SELECT id FROM masterdata.catalog_item WHERE tenant_id=@t AND id=ANY(@ids::uuid[]) ORDER BY id FOR SHARE",
            ("t", tenant), ("ids", items));
        var knownItems = lockedItems.Select(r => (Guid)r["id"]!).ToHashSet();
        for (var i = 0; i < input.Lines.Count; i++)
            Require(knownItems.Contains(input.Lines[i].FiscalContext.ItemId),
                "tax_item_not_found", 404, "lines[" + i + "].fiscal_context.item_id");
        await Rows(db, "SELECT id FROM masterdata.catalog_item_type WHERE tenant_id=@t AND id IN (SELECT item_type_id FROM masterdata.catalog_item WHERE tenant_id=@t AND id=ANY(@ids::uuid[])) ORDER BY id FOR SHARE",
            ("t", tenant), ("ids", items));

        var streams = items.Select(id => (Kind: ClassificationKind.Item, Subject: id))
            .Concat(partners.Select(id => (Kind: ClassificationKind.Partner, Subject: id)))
            .OrderBy(x => "tax-profile:" + x.Kind.Name + ":" + tenant.ToString("D") + ":" + x.Subject.ToString("D"), StringComparer.Ordinal);
        foreach (var stream in streams)
            await TaxClassificationApplication.Lock(db, stream.Kind, tenant, stream.Subject, false);

        await Rows(db, "SELECT id FROM taxmanagement.company_tax_configurations WHERE tenant_id=@t AND company_id=@company ORDER BY id FOR SHARE",
            ("t", tenant), ("company", input.CompanyId));
        foreach (var kind in new[] { ClassificationKind.Item, ClassificationKind.Partner })
        {
            var subjects = kind.Name == "item" ? items : partners;
            await Rows(db, "SELECT c.id FROM taxmanagement." + kind.ClassificationTable +
                " c WHERE c.tenant_id=@t AND c.id IN (SELECT p." + kind.ClassificationColumn +
                " FROM taxmanagement." + kind.ProfileTable + " p WHERE p.tenant_id=@t AND p." +
                kind.SubjectColumn + "=ANY(@subjects::uuid[]) AND p.country_id=@country AND p.tax_type_id=@type) ORDER BY c.id FOR SHARE OF c",
                ("t", tenant), ("subjects", subjects), ("country", country), ("type", first.TaxTypeId));
        }
        var drafts = input.Lines.SelectMany(l => l.FiscalContext.DraftVersionIds).Distinct().Order().ToArray();
        // Stesso insieme conservativo di Materialize F4, comprese le bozze esplicitamente selezionate.
        var ruleIds = await Rows(db,
            "SELECT r.id FROM taxmanagement.tax_rules r WHERE r.tenant_id=@t AND EXISTS (SELECT 1 FROM taxmanagement.tax_rule_versions v WHERE v.tenant_id=r.tenant_id AND v.tax_rule_id=r.id AND ((r.country_id=@country AND r.tax_type_id=@type AND (r.company_id IS NULL OR r.company_id=@company) AND v.operation_type=@operation AND v.status='PUBLISHED') OR v.id=ANY(@drafts::uuid[]))) ORDER BY r.id FOR SHARE OF r",
            ("t", tenant), ("country", country), ("type", first.TaxTypeId),
            ("company", input.CompanyId), ("operation", input.OperationType), ("drafts", drafts));
        var roots = ruleIds.Select(r => (Guid)r["id"]!).ToArray();
        var knownDraftRows = await Rows(db,
            "SELECT id FROM taxmanagement.tax_rule_versions WHERE tenant_id=@t AND tax_rule_id=ANY(@roots::uuid[]) AND id=ANY(@drafts::uuid[])",
            ("t", tenant), ("roots", roots), ("drafts", drafts));
        var knownDrafts = knownDraftRows.Select(r => (Guid)r["id"]!).ToHashSet();
        for (var i = 0; i < input.Lines.Count; i++)
            for (var j = 0; j < input.Lines[i].FiscalContext.DraftVersionIds.Count; j++)
                Require(knownDrafts.Contains(input.Lines[i].FiscalContext.DraftVersionIds[j]),
                    "tax_rule_version_not_found", 404,
                    "lines[" + i + "].fiscal_context.draft_version_ids[" + j + "]");
        // I draft non possono cambiare codice dopo il lock della loro radice. Nessun lock cataloghi readonly.
        await Rows(db,
            "SELECT c.id FROM taxmanagement.tax_codes c WHERE c.tenant_id=@t AND c.id IN (SELECT v.tax_code_id FROM taxmanagement.tax_rule_versions v WHERE v.tenant_id=@t AND v.tax_rule_id=ANY(@roots::uuid[]) AND (v.status='PUBLISHED' OR v.id=ANY(@drafts::uuid[]))) ORDER BY c.id FOR SHARE OF c",
            ("t", tenant), ("roots", roots), ("drafts", drafts));
    }
}
