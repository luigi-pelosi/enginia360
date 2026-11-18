using Enginia360.Api.Resources;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Reflection;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Enginia360.Verification.Organizations;

public static class SiteClassificationSelfTests
{
    static readonly string[] Legal = ["LEGAL", "LOCAL_UNIT", "SECONDARY"];
    static readonly string[] Functions = ["OPERATIONAL", "ADMINISTRATIVE", "COMMERCIAL", "PRODUCTION", "LOGISTICS", "WAREHOUSE", "TECHNICAL_SERVICE", "MANAGEMENT", "RETAIL"];
    static readonly Resource Site = ResourceCatalog.Get("sites");
    static Dictionary<string, object?> Values(object payload, bool create = false)
    {
        var values=JsonSerializer.SerializeToElement(payload).EnumerateObject().ToDictionary(p=>p.Name,p=>(object?)p.Value);
        if(create && !values.ContainsKey("vat_number") && !values.ContainsKey("tax_code")) values["tax_code"]="SYNTHETIC-TAX";
        if(create) {
            values.TryAdd("address","Synthetic Road 42"); values.TryAdd("city","Synthetic City");
            values.TryAdd("province","Synthetic Region"); values.TryAdd("postal_code","AB 12-X"); values.TryAdd("country_code","GB");
        }
        return ResourceCatalog.Validate(Site,JsonSerializer.SerializeToElement(values),create);
    }
    static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }

    public static void Run(Action<string, Action> test)
    {
        test("site classification: optional legal select metadata and supported payload", () => {
            var field = Site.Fields.Single(f => f.Name == "site_type");
            Require(field.Type == "select" && !field.Required && field.DefaultValue == null && field.Options != null && field.Options.SequenceEqual(Legal), "Tipologia giuridica deve essere select opzionale LEGAL/LOCAL_UNIT/SECONDARY senza default.");
            foreach (var value in Legal)
                Require(Equals(Values(new { name = "Sede", company_id = Guid.NewGuid(), site_type = value }, true)["site_type"], value), "Payload giuridico valido non accettato.");
        });
        test("site classification: valid functions payload supported with metadata projection and typed binding", () => {
            var values = Values(new { name = "Sede", company_id = Guid.NewGuid(), functions = new[] { "OPERATIONAL", "WAREHOUSE" } }, true);
            Require(values["functions"] is string[] array && array.SequenceEqual(new[] { "OPERATIONAL", "WAREHOUSE" }), "Functions deve produrre string[].");
            var field = Site.Fields.Single(f => f.Name == "functions");
            Require(field.Type == "multiselect" && !field.Required && field.Options != null && field.Options.SequenceEqual(Functions), "Metadata multiselect finiti mancanti.");
            Require(ResourceCatalog.Projection(Site).Contains("'functions',t.functions"), "Proiezione array mancante.");
            using var cmd = new NpgsqlCommand();
            typeof(DataEndpoints).GetMethod("AddValues", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, [cmd, Site, values]);
            Require(cmd.Parameters["functions"].NpgsqlDbType == (NpgsqlDbType.Array | NpgsqlDbType.Text), "Binding functions deve essere text[].");
            Require(cmd.Parameters["functions"].Value is string[], "Binding array trasformato in testo.");
        });
        test("site classification: functions null refused", () => Reject(new { functions = (object?)null }));
        test("site classification: unknown functions refused", () => {
            foreach (var value in new[] { "UNKNOWN", "operational", " OPERATIONAL ", "", "bad\0value" }) Reject(new { functions = new[] { value } });
        });
        test("site classification: duplicate functions refused", () => Reject(new { functions = new[] { "WAREHOUSE", "WAREHOUSE" } }));
        test("site classification: more than nine functions refused", () => Reject(new { functions = Enumerable.Repeat("OPERATIONAL", 10).ToArray() }));
        test("site classification: canonical option order", () => {
            foreach (var create in new[] { false, true }) {
                var values = Values(new { name = "Sede", company_id = Guid.NewGuid(), functions = Functions.Reverse().ToArray() }, create);
                Require(((string[])values["functions"]!).SequenceEqual(Functions), "Ordine canonico Options richiesto.");
            }
        });
        test("site classification: blank legal classification clears", () => {
            foreach (var blank in new[] { "", " \t\n ", "\u00a0\u2003" })
                Require(Values(new { site_type = blank })["site_type"] == null, "Tipologia giuridica blank deve diventare null.");
        });
        test("site classification: legal enum whitelist", () => {
            foreach (var value in new[] { "UNKNOWN", "legal", " LEGAL ", "OPERATIONAL" }) Reject(new { site_type = value });
        });
        test("site classification: sites audit snapshot enabled", () => {
            Require((bool)typeof(DataEndpoints).GetMethod("HasSnapshots", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, ["sites"])!, "Audit sites deve includere before/after.");
        });
        test("site classification: existing omission clear and fiscal scope regressions", () => {
            foreach (var create in new[] { false, true }) {
                var omitted = Values(new { name = "Sede", company_id = Guid.NewGuid() }, create);
                Require(!omitted.ContainsKey("functions") && !omitted.ContainsKey("site_type"), "Omissione deve preservare update/default DB create.");
                var cleared = Values(new { name = "Sede", company_id = Guid.NewGuid(), functions = Array.Empty<string>(), site_type = (string?)null }, create);
                Require(cleared["functions"] is string[] { Length: 0 } && cleared["site_type"] == null, "Clear array e null tipologia non preservati.");
            }
            var fiscal = Values(new { vat_number = " VAT ", tax_code = " TAX " });
            Require(Equals(fiscal["vat_number"], "VAT") && Equals(fiscal["tax_code"], "TAX"), "Campi fiscali alterati.");
            Require(ResourceCatalog.Scope(Site) == "tenant_id=@tenant::uuid", "Scope sedi alterato.");
            Reject(new { tenant_id = Guid.NewGuid(), functions = Array.Empty<string>() });
        });
        test("site classification: all finite subsets canonicalize and bind including empty", () => {
            for (var mask = 0; mask < (1 << Functions.Length); mask++) {
                var expected = Functions.Where((_, index) => (mask & (1 << index)) != 0).ToArray();
                var values = Values(new { functions = expected.Reverse().ToArray() });
                Require(((string[])values["functions"]!).SequenceEqual(expected), "Sottoinsieme non canonico.");
                using var cmd = new NpgsqlCommand();
                typeof(DataEndpoints).GetMethod("AddValues", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, [cmd, Site, values]);
                Require(cmd.Parameters["functions"].NpgsqlDbType == (NpgsqlDbType.Array | NpgsqlDbType.Text) && ((string[])cmd.Parameters["functions"].Value!).SequenceEqual(expected), "Binding sottoinsieme non preservato.");
            }
            using var legal = new NpgsqlCommand();
            typeof(DataEndpoints).GetMethod("AddValues", BindingFlags.NonPublic | BindingFlags.Static)!.Invoke(null, [legal, Site, Values(new { site_type = " " })]);
            Require(legal.Parameters["site_type"].NpgsqlDbType == NpgsqlDbType.Text && legal.Parameters["site_type"].Value == DBNull.Value, "Clear select deve usare null text tipizzato.");
        });
        test("site classification: existing malformed shapes and json regressions", () => {
            foreach (var value in new object[] { "WAREHOUSE", 1, true, new { value = "WAREHOUSE" }, new object?[] { null }, new object[] { 1 }, new object[] { new[] { "WAREHOUSE" } } }) Reject(new { functions = value });
            foreach (var value in new object[] { 1, true, new[] { "LEGAL" } }) Reject(new { site_type = value });
            foreach (var raw in new[] { "{\"functions\":[],\"functions\":[]}", "{\"functions\":[\"\\ud800\"]}" }) {
                try { ResourceCatalog.Validate(Site, JsonSerializer.Deserialize<JsonElement>(raw), false); }
                catch (ApiException e) when (e.Status == 400 && e.Code == "validation_error") { continue; }
                throw new Exception("JSON duplicato/Unicode invalido accettato.");
            }
            try { JsonSerializer.Deserialize<JsonElement>("{\"functions\":["); }
            catch (JsonException) { return; }
            throw new Exception("JSON malformato accettato.");
        });
    }

    static void Reject(object payload)
    {
        foreach (var create in new[] { false, true })
        {
            var fields = JsonSerializer.SerializeToElement(payload).EnumerateObject().ToDictionary(p => p.Name, p => (object?)p.Value);
            if (create) { fields["name"] = "Sede"; fields["company_id"] = Guid.NewGuid(); }
            try { Values(fields, create); }
            catch (ApiException e) when (e.Status == 400 && e.Code == "validation_error") { continue; }
            throw new Exception("Atteso 400 validation_error.");
        }
    }
}
