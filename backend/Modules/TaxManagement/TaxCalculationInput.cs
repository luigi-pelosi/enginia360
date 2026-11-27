using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Enginia360.Shared.Validation;
namespace Enginia360.Modules.TaxManagement;

public sealed record TaxCalculationLineInput(Guid LineId, string Quantity, string UnitPrice,
    string PriceMode, IReadOnlyList<TaxAdjustment> Adjustments, TaxDeterminationRequest FiscalContext,
    string? DeductiblePercentage, string? Currency);
public sealed record TaxCalculationInputRequest(Guid CompanyId, string Currency, string OperationType,
    string Direction, IReadOnlyList<TaxCalculationLineInput> Lines,
    IReadOnlyList<TaxAdjustment> DocumentAdjustments);

/// <summary>Trasporto F5 rigoroso: nessuna coercizione numerica o autorità fiscale dal client.</summary>
public static class TaxCalculationInput
{
    public static (Guid CompanyId, string Currency) PolicyQuery(HttpContext ctx)
    {
        foreach (var parameter in ctx.Request.Query)
            Check((parameter.Key is "company_id" or "currency" or "tenantId") && parameter.Value.Count == 1,
                "tax_invalid_field", parameter.Key);
        if (ctx.Request.Query.TryGetValue("tenantId", out var tenant))
        {
            // Solo validazione della forma. L'autorità rimane TaxRuleReferences.Tenant/SessionState.Tenant.
            var text = tenant.ToString();
            Check(text.Length == 36 && Guid.TryParseExact(text, "D", out var id) && id != Guid.Empty,
                "tax_invalid_id", "tenantId");
        }
        var companyText = ctx.Request.Query["company_id"].ToString();
        Check(companyText.Length == 36 && Guid.TryParseExact(companyText, "D", out var companyId) && companyId != Guid.Empty,
            "tax_invalid_id", "company_id");
        var currency = ctx.Request.Query["currency"].ToString();
        Check(currency == "EUR", "tax_calculation_currency_not_supported", "currency");
        return (Guid.ParseExact(companyText, "D"), currency);
    }

    private static void Check(bool ok, string code, string field) =>
        TaxRuleInput.Require(ok, code, field: field);
    private static string Path(string parent, string key) => parent.Length == 0 ? key : parent + "." + key;

    private static Dictionary<string, JsonElement> Object(JsonElement raw, string path, params string[] allowed)
    {
        Check(raw.ValueKind == JsonValueKind.Object, "tax_invalid_payload", path);
        var result = new Dictionary<string, JsonElement>(StringComparer.Ordinal);
        foreach (var p in raw.EnumerateObject())
        {
            Check(allowed.Contains(p.Name, StringComparer.Ordinal), "tax_unknown_field", Path(path, p.Name));
            Check(result.TryAdd(p.Name, p.Value), "tax_duplicate_field", Path(path, p.Name));
        }
        return result;
    }
    private static JsonElement Required(Dictionary<string, JsonElement> o, string key, string path) =>
        o.TryGetValue(key, out var raw) ? raw : throw new ApiException(400, "tax_field_required", Path(path, key));
    private static string Text(Dictionary<string, JsonElement> o, string key, string path, int max = 60)
    {
        var raw = Required(o, key, path);
        try
        {
            var text = TaxRuleInput.Text(new() { [key] = raw }, key, max, true)!;
            Check(raw.GetString() == text, "tax_invalid_field", Path(path, key));
            return text;
        }
        catch (ApiException e) { throw new ApiException(e.Status, e.Code, Path(path, key)); }
    }
    private static Guid Id(Dictionary<string, JsonElement> o, string key, string path)
    {
        var text = Text(o, key, path, 36);
        Check(text.Length == 36 && Guid.TryParseExact(text, "D", out var id) && id != Guid.Empty,
            "tax_invalid_id", Path(path, key));
        return Guid.ParseExact(text, "D");
    }
    private static string Enum(Dictionary<string, JsonElement> o, string key, string path, params string[] values)
    {
        var text = Text(o, key, path);
        Check(values.Contains(text, StringComparer.Ordinal), "tax_invalid_field", Path(path, key));
        return text;
    }
    private static JsonElement[] Array(JsonElement raw, string field, int max, bool nonempty = false)
    {
        Check(raw.ValueKind == JsonValueKind.Array && raw.GetArrayLength() <= max &&
            (!nonempty || raw.GetArrayLength() > 0), "tax_calculation_invalid_array", field);
        return raw.EnumerateArray().ToArray();
    }
    private static string Decimal(Dictionary<string, JsonElement> o, string key, string path,
        int integers, int fractions, bool positive = false, decimal? max = null)
    {
        var text = Text(o, key, path, integers + fractions + 1);
        Check(Regex.IsMatch(text, @"\A(?:0|[1-9][0-9]{0," + (integers - 1) + @"})(?:\.[0-9]{1," + fractions + @"})?\z",
            RegexOptions.CultureInvariant), "tax_calculation_invalid_decimal", Path(path, key));
        Check(decimal.TryParse(text, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var number) &&
            (!positive || number > 0) && (max == null || number <= max),
            "tax_calculation_invalid_decimal", Path(path, key));
        return text;
    }

    // Prima di delegare al parser F4, conserva indici, duplicati e UUID canonici anche negli oggetti annidati.
    private static void ValidateFiscalTree(JsonElement raw, string path, string? key = null)
    {
        if (key?.EndsWith("_id", StringComparison.Ordinal) == true &&
            (raw.ValueKind != JsonValueKind.Null || key == "draft_id"))
            Check(raw.ValueKind == JsonValueKind.String, "tax_invalid_id", path);
        if (raw.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in raw.EnumerateObject())
            {
                Check(names.Add(p.Name), "tax_duplicate_field", Path(path, p.Name));
                ValidateFiscalTree(p.Value, Path(path, p.Name), p.Name);
            }
        }
        else if (raw.ValueKind == JsonValueKind.Array)
        {
            if (key == "draft_version_ids")
                Check(raw.GetArrayLength() <= 20, "tax_calculation_invalid_array", path);
            var draftIds = new HashSet<Guid>();
            var i = 0;
            foreach (var entry in raw.EnumerateArray())
            {
                var entryPath = path + "[" + i++ + "]";
                ValidateFiscalTree(entry, entryPath, key == "draft_version_ids" ? "draft_id" : key);
                if (key == "draft_version_ids")
                    Check(draftIds.Add(Guid.ParseExact(entry.GetString()!, "D")), "tax_duplicate_field", entryPath);
            }
        }
        else if (raw.ValueKind == JsonValueKind.String)
        {
            try { _ = TaxRuleInput.Text(new() { ["value"] = raw }, "value", 1024); }
            catch (ApiException e) { throw new ApiException(e.Status, e.Code, path); }
            if (key?.EndsWith("_id", StringComparison.Ordinal) == true)
            {
                var text = raw.GetString()!;
                Check(text.Length == 36 && Guid.TryParseExact(text, "D", out var id) && id != Guid.Empty,
                    "tax_invalid_id", path);
            }
        }
    }

    public static TaxCalculationInputRequest Parse(JsonElement raw, bool simulation)
    {
        var o = Object(raw, "", "company_id", "currency", "operation_type", "direction", "lines", "document_adjustments");
        var company = Id(o, "company_id", "");
        var currency = Enum(o, "currency", "", "EUR");
        var operation = Enum(o, "operation_type", "", "SALE", "PURCHASE");
        var direction = Enum(o, "direction", "", "NORMAL", "REVERSAL");
        var rawLines = Array(Required(o, "lines", ""), "lines", 100, true);
        var lineIds = new HashSet<Guid>();
        var adjustmentIds = new HashSet<Guid>();
        var lines = new List<TaxCalculationLineInput>();
        Guid? type = null;
        for (var i = 0; i < rawLines.Length; i++)
        {
            var path = "lines[" + i + "]";
            var line = Object(rawLines[i], path, "line_id", "quantity", "unit_price", "price_mode", "adjustments",
                "deductible_percentage", "currency", "fiscal_context");
            var id = Id(line, "line_id", path);
            Check(lineIds.Add(id), "tax_calculation_duplicate_id", Path(path, "line_id"));
            var quantity = Decimal(line, "quantity", path, 14, 6, true);
            var price = Decimal(line, "unit_price", path, 12, 8, true);
            var mode = Enum(line, "price_mode", path, "TAX_EXCLUSIVE", "TAX_INCLUSIVE");
            string? deductible = null;
            if (line.TryGetValue("deductible_percentage", out var percentage) && percentage.ValueKind != JsonValueKind.Null)
            {
                Check(operation == "PURCHASE", "tax_calculation_deductibility_purchase_only", Path(path, "deductible_percentage"));
                deductible = Decimal(line, "deductible_percentage", path, 3, 6, max: 100);
            }
            string? lineCurrency = line.ContainsKey("currency") ? Enum(line, "currency", path, "EUR") : null;
            var fiscalPath = Path(path, "fiscal_context");
            var fiscalRaw = Required(line, "fiscal_context", path);
            Check(fiscalRaw.ValueKind == JsonValueKind.Object, "tax_invalid_payload", fiscalPath);
            Check(simulation || !fiscalRaw.TryGetProperty("draft_version_ids", out _),
                "tax_calculation_drafts_forbidden", fiscalPath + ".draft_version_ids");
            ValidateFiscalTree(fiscalRaw, fiscalPath);
            if (fiscalRaw.TryGetProperty("transaction_facts", out var factsRaw))
                _ = Object(factsRaw, fiscalPath + ".transaction_facts", "operation_category",
                    "partner_establishment_country_id", "ordinary_vat_territory_confirmed", "special_tax_treatment",
                    "goods_location_country_id", "goods_customs_status", "source_reference");
            TaxDeterminationRequest fiscal;
            try { fiscal = TaxDeterminationInput.Parse(fiscalRaw, simulation); }
            catch (ApiException e)
            {
                var field = e.Field;
                if (e.Code != "tax_unknown_field" && (field is "operation_category" or "partner_establishment_country_id" or "ordinary_vat_territory_confirmed"
                    or "special_tax_treatment" or "goods_location_country_id" or "goods_customs_status" or "source_reference"))
                    field = "transaction_facts." + field;
                throw new ApiException(e.Status, e.Code, field == null ? fiscalPath : Path(fiscalPath, field));
            }
            Check(fiscal.CompanyId == company, "tax_calculation_company_mismatch", fiscalPath + ".company_id");
            Check(fiscal.OperationType == operation, "tax_calculation_operation_mismatch", fiscalPath + ".operation_type");
            type ??= fiscal.TaxTypeId;
            Check(fiscal.TaxTypeId == type, "tax_calculation_type_mismatch", fiscalPath + ".tax_type_id");
            var adjustments = Adjustments(Required(line, "adjustments", path), Path(path, "adjustments"), false, adjustmentIds, lineIds);
            lines.Add(new(id, quantity, price, mode, adjustments, fiscal, deductible, lineCurrency));
        }
        var document = Adjustments(Required(o, "document_adjustments", ""), "document_adjustments", true, adjustmentIds, lineIds);
        return new(company, currency, operation, direction, lines.AsReadOnly(), document);
    }

    private static IReadOnlyList<TaxAdjustment> Adjustments(JsonElement raw, string path, bool document,
        HashSet<Guid> globalIds, HashSet<Guid> lineIds)
    {
        var entries = Array(raw, path, 20);
        var result = new List<TaxAdjustment>();
        var sequences = new HashSet<int>();
        for (var i = 0; i < entries.Length; i++)
        {
            var entryPath = path + "[" + i + "]";
            var o = Object(entries[i], entryPath, "adjustment_id", "type", "calculation_mode", "value", "sequence", "applicable_line_ids");
            var id = Id(o, "adjustment_id", entryPath);
            Check(globalIds.Add(id), "tax_calculation_duplicate_id", Path(entryPath, "adjustment_id"));
            var type = Enum(o, "type", entryPath, "DISCOUNT", "SURCHARGE");
            var mode = Enum(o, "calculation_mode", entryPath, "PERCENTAGE", "FIXED_AMOUNT");
            var value = mode == "FIXED_AMOUNT" ? Decimal(o, "value", entryPath, 16, 2)
                : Decimal(o, "value", entryPath, 3, 6, max: type == "DISCOUNT" ? 100 : 999.999999m);
            var sequenceRaw = Required(o, "sequence", entryPath);
            Check(sequenceRaw.ValueKind == JsonValueKind.Number && sequenceRaw.TryGetInt32(out var n) && n > 0,
                "tax_calculation_invalid_sequence", Path(entryPath, "sequence"));
            var sequence = sequenceRaw.GetInt32();
            Check(sequences.Add(sequence), "tax_calculation_duplicate_sequence", Path(entryPath, "sequence"));
            IReadOnlyList<Guid>? applicable = null;
            if (o.TryGetValue("applicable_line_ids", out var ids))
            {
                Check(document || ids.ValueKind == JsonValueKind.Null, "tax_calculation_line_scope_forbidden", Path(entryPath, "applicable_line_ids"));
                if (document)
                {
                    var values = Array(ids, Path(entryPath, "applicable_line_ids"), 100, true);
                    var unique = new HashSet<Guid>();
                    var selected = new List<Guid>();
                    for (var j = 0; j < values.Length; j++)
                    {
                        var field = Path(entryPath, "applicable_line_ids") + "[" + j + "]";
                        Guid selectedId;
                        try { selectedId = Id(new() { ["value"] = values[j] }, "value", ""); }
                        catch (ApiException e) { throw new ApiException(e.Status, e.Code, field); }
                        Check(unique.Add(selectedId), "tax_calculation_duplicate_id", field);
                        Check(lineIds.Contains(selectedId), "tax_calculation_unknown_line", field);
                        selected.Add(selectedId);
                    }
                    applicable = selected.AsReadOnly();
                }
            }
            result.Add(new(id, type, mode, value, sequence, applicable));
        }
        return result.AsReadOnly();
    }
}
