using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.AccessControl;
using Enginia360.Modules.Geography;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using System.Text.Json;
using NpgsqlTypes;

namespace Enginia360.Api.Resources;

public sealed record Field(string Name, string Type = "text", bool Required = false, string? Reference = null, string[]? Options = null, string? DefaultValue = null);
public sealed record Resource(string Key, string Table, Field[] Fields, bool ReadOnly = false);
public sealed record Relation(string Table, string OwnerColumn, string TargetColumn, string OwnerResource, string TargetResource, string Permission);
public static class Resources
{
    static Field Text(string name, bool required = false) => new(name, "text", required);
    static Field Ref(string name, string resource, bool required = true) => new(name, "reference", required, resource);
    static Field[] Named(bool description = false, bool codeRequired = false) => description
        ? [Text("name", true), Text("code", codeRequired), new("description", "textarea"), new("is_enabled", "boolean")]
        : [Text("name", true), Text("code", codeRequired), new("is_enabled", "boolean")];
    public static readonly Dictionary<string, Resource> All = new Resource[] {
        new("tenants", "tenant", Named(true, codeRequired: true)),
        new("currencies", "currency", [Text("name", true), Text("code", true), Text("numeric_code", true), new("minor_units", "integer"), new("is_enabled", "boolean")]),
        new("countries", "country", [Text("name", true), Text("iso_code", true), new("notes", "textarea"), new("is_enabled", "boolean")]),
        new("cities", "city", [Text("name", true), Text("postal_code", true), Text("province"), Text("region"), Ref("country_id", "countries"), new("notes", "textarea"), new("is_enabled", "boolean")]),
        new("business-partners", "business_partner", [Text("legal_name"), Text("first_name"), Text("last_name"), new("kind", "select", true, Options: ["PERSON", "ORGANIZATION"]), Text("code"), new("status", "select", Options: ["DRAFT", "ACTIVE", "BLOCKED", "ARCHIVED"], DefaultValue: "DRAFT")]),
        new("companies", "company", Named()),
        new("sales-organizations", "sales_organization", [Ref("company_id", "companies"), ..Named(true)]),
        new("purchasing-organizations", "purchasing_organization", Named(true)),
        new("sites", "site", [Ref("company_id", "companies"), Text("name", true), Text("code"), new("site_type", "select", Options: ["LEGAL", "LOCAL_UNIT", "SECONDARY"]), new("functions", "multiselect", Options: ["OPERATIONAL", "ADMINISTRATIVE", "COMMERCIAL", "PRODUCTION", "LOGISTICS", "WAREHOUSE", "TECHNICAL_SERVICE", "MANAGEMENT", "RETAIL"]), Text("address", true), Text("city", true), Text("province", true), Text("region"), Text("postal_code", true), new("country_code", "select", Required: true, Options: CountryCodes.All), new("is_enabled", "boolean")]),
        new("warehouse-types", "warehouse_type", Named()),
        new("warehouses", "warehouse", [Ref("site_id", "sites"), Ref("warehouse_type_id", "warehouse-types"), ..Named()]),
        new("warehouse-locations", "warehouse_location", [Ref("warehouse_id", "warehouses"), ..Named()]),

        new("users", "user", [Text("username", true), Text("first_name", true), Text("last_name", true), Text("email", true), new("date_of_birth", "date"), new("phone_number", "tel"), new("preferred_language", "select", Options: ["it", "en"], DefaultValue: "it"), new("is_enabled", "boolean")]),
        new("groups", "user_group", Named(true)),
        new("roles", "role", Named(true)),
        new("permissions", "permission", Named(true, codeRequired: true), ReadOnly: true)
    }.ToDictionary(r => r.Key, StringComparer.Ordinal);
    public static readonly Dictionary<string, Relation> Links = new() {
        ["user-roles"] = new("user_role", "user_id", "role_id", "users", "roles", "roles.assign"),
        ["group-users"] = new("user_group_member", "user_group_id", "user_id", "groups", "users", "groups.assign_users"),
        ["group-roles"] = new("user_group_role", "user_group_id", "role_id", "groups", "roles", "roles.assign"),
        ["role-permissions"] = new("role_permission", "role_id", "permission_id", "roles", "permissions", "roles.assign_permissions")
    };
    public static bool IsGlobalMaster(string key) => key is "countries" or "cities" or "currencies";
    public static bool MetaReadOnly(Resource r, User user) => r.ReadOnly || IsGlobalMaster(r.Key) && !(user.IsEnabled && user.IsSuperAdmin && user.TenantId == null);
    public static Resource Get(string key) => All.TryGetValue(key, out var r) ? r : throw new ApiException(404,"not_found");

    public static Dictionary<string, object?> Validate(Resource resource, JsonElement body, bool create)
    {
        Check.Require(!resource.ReadOnly,403,"forbidden");
        Check.Require(body.ValueKind == JsonValueKind.Object);
        var values = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (var prop in body.EnumerateObject())
        {
            var name=ReadName(prop);
            var field = resource.Fields.SingleOrDefault(f => f.Name==name);
            Check.Require(field != null && !values.ContainsKey(name));
            var f = field!;
            object? value;
            if (prop.Value.ValueKind == JsonValueKind.Null)
            {
                Check.Require(!f.Required && f.Type is not ("boolean" or "multiselect") && f.Name != "preferred_language");
                value = null;
            }
            else if (f.Type == "integer")
            {
                Check.Require(prop.Value.ValueKind == JsonValueKind.Number && prop.Value.TryGetInt32(out var number) && number is >= 0 and <= 28);
                value = prop.Value.GetInt32();
            }
            else if (f.Type == "boolean")
            {
                Check.Require(prop.Value.ValueKind is JsonValueKind.True or JsonValueKind.False);
                value = prop.Value.GetBoolean();
            }
            else if (f.Type == "multiselect")
            {
                Check.Require(prop.Value.ValueKind == JsonValueKind.Array && prop.Value.GetArrayLength() <= f.Options!.Length);
                var selected = new HashSet<string>(StringComparer.Ordinal);
                foreach (var item in prop.Value.EnumerateArray())
                {
                    var option = ReadString(item);
                    Check.Require(f.Options!.Contains(option, StringComparer.Ordinal) && selected.Add(option));
                }
                value = f.Options!.Where(selected.Contains).ToArray();
            }
            else if (f.Type == "json") value = prop.Value.GetRawText();
            else
            {
                Check.Require(prop.Value.ValueKind == JsonValueKind.String);
                var text = ReadString(prop.Value);
                if(resource.Key == "users" && f.Name is "first_name" or "last_name" or "email")
                    text = System.Text.RegularExpressions.Regex.Replace(text.Trim(), @"\s+", " ");
                Check.Require(text.Length <= (f.Type == "textarea" ? 4000 : 500) && !text.Contains('\0') && (!f.Required || !string.IsNullOrWhiteSpace(text)));
                // PostgreSQL rifiuta surrogate isolate; validazione esplicita prima del driver.
                for (var i = 0; i < text.Length; i++)
                {
                    if (char.IsHighSurrogate(text[i])) { Check.Require(i + 1 < text.Length && char.IsLowSurrogate(text[i + 1])); i++; }
                    else Check.Require(!char.IsLowSurrogate(text[i]));
                }
                if(resource.Key == "users")
                {
                    if(f.Name is "first_name" or "last_name") Check.Require(text.Length <= 200);
                    if(f.Name == "email") Check.Require(text.Length <= 254 && System.Text.RegularExpressions.Regex.IsMatch(text, @"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$"));
                    if(f.Name == "phone_number") Check.Require(text.Length <= 50);
                    if(f.Name == "preferred_language") Check.Require(text is "it" or "en");
                }
                if (resource.Key == "currencies" && f.Name is "code" or "numeric_code")
                    Check.Require(System.Text.RegularExpressions.Regex.IsMatch(text, f.Name == "code" ? "^[A-Z]{3}$" : "^[0-9]{3}$"));
                if (resource.Key == "countries" && f.Name == "iso_code") Check.Require(CountryCodes.All.Contains(text, StringComparer.Ordinal));
                if (IsGlobalMaster(resource.Key)) text = text.Trim();
                if (f.Type == "reference") { Check.Require(Guid.TryParse(text, out var id) && id != Guid.Empty); value = id; }
                else if(f.Type == "date")
                {
                    Check.Require(DateOnly.TryParseExact(text,"yyyy-MM-dd",System.Globalization.CultureInfo.InvariantCulture,System.Globalization.DateTimeStyles.None,out var date)
                        && date <= DateOnly.FromDateTime(DateTime.UtcNow));
                    value = date;
                }
                else if (f.Type == "select")
                {
                    if (!f.Required && f.DefaultValue == null && string.IsNullOrWhiteSpace(text)) value = null;
                    else { Check.Require(f.Options!.Contains(text, StringComparer.Ordinal)); value = text; }
                }
                else if (f.Name == "code" && !f.Required)
                {
                    var code = text.Trim();
                    value = code.Length == 0 ? null : code;
                }
                else value = text;
            }
            values.Add(f.Name, value);
        }
        if (create) foreach (var field in resource.Fields.Where(f => f.Required)) Check.Require(values.ContainsKey(field.Name));

        Check.Require(values.Count > 0);
        return values;
    }

    internal static string ReadName(JsonProperty property)
    {
        try {return property.Name;}
        catch(InvalidOperationException) {throw new ApiException(400,"validation_error");}
    }

    internal static string ReadString(JsonElement value)
    {
        Check.Require(value.ValueKind==JsonValueKind.String);
        // GetString può fallire prima dei controlli Unicode su escape UTF-16 incompleti.
        try {return value.GetString()!;}
        catch(InvalidOperationException) {throw new ApiException(400,"validation_error");}
    }

    // I campi di sicurezza non entrano mai nella proiezione pubblica, nemmeno dopo estensioni dello schema.
    public static string Projection(Resource r)
    {
        var fields = new[] { "id" }.Concat(r.Key == "tenants" || IsGlobalMaster(r.Key) ? [] : new[] { "tenant_id" })
            .Concat(r.Fields.Select(f => f.Name)).Concat(r.Key == "currencies" ? new[] { "version" } : []).Concat(new[] { "created_at", "updated_at" });
        return "json_build_object(" + string.Join(',',fields.Select(f => $"'{f}',t.{f}")) + ")::text";
    }
    public static string Scope(Resource r) => r.Key == "tenants" || IsGlobalMaster(r.Key) ? "true"
        : r.Key == "users" ? "tenant_id=@tenant::uuid AND NOT is_super_admin"

        : r.Key == "permissions" ? "tenant_id=@tenant::uuid AND is_system AND code IN ("+string.Join(',',PermissionCatalog.Codes.Select(c => "'"+c+"'"))+")" : "tenant_id=@tenant::uuid";

    // La visibilità della propria utenza globale non estende mutazioni o associazioni tenant.
    public static string ListScope(Resource r, User viewer) => r.Key == "users" && viewer.IsSuperAdmin && viewer.TenantId == null
        ? $"(({Scope(r)}) OR (tenant_id IS NULL AND is_super_admin AND id=@viewer::uuid))"
        : Scope(r);

    public static async Task<JsonElement?> Row(AppDb db, Resource r, Guid id, Guid? tenant)
    {
        var text = await db.Scalar($"SELECT {Projection(r)} FROM {SqlNames.Table(r.Table)} t WHERE id=@id AND {Scope(r)}", ("id",id),("tenant",tenant));
        return text is string s ? JsonSerializer.Deserialize<JsonElement>(s) : null;
    }
    public static async Task EnsureRow(AppDb db, Resource r, Guid id, Guid? tenant)
    {
        if (await Row(db,r,id,tenant) == null) throw new ApiException(404,"not_found");
    }
    public static async Task ValidateReferences(AppDb db, Resource r, Dictionary<string,object?> values, Guid? tenant)
    {
        foreach (var f in r.Fields.Where(f => f.Reference != null))
            if (values.TryGetValue(f.Name, out var value) && value is Guid id)
                Check.Require(await Row(db,Get(f.Reference!),id,tenant) != null);
    }
}
