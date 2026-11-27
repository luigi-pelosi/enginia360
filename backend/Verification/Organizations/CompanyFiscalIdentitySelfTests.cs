using Enginia360.Shared.Validation;
using System.Text.Json;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;

namespace Enginia360.Verification.Organizations;

public static class CompanyFiscalIdentitySelfTests
{
    static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }
    static void Reject(Action action)
    {
        try { action(); }
        catch (ApiException e) when (e.Status == 400 && e.Code == "validation_error") { return; }
        throw new Exception("Expected 400 validation_error.");
    }

    public static void Run(Action<string, Action> test)
    {
        var company = ResourceCatalog.Get("companies");
        var site = ResourceCatalog.Get("sites");
        test("company fiscal identity: general Company and Site contain no fiscal identifiers", () => {
            foreach (var resource in new[] { company, site }) foreach (var key in new[] { "vat_number", "tax_code" }) {
                Require(!resource.Fields.Any(f => f.Name == key), "General resource exposes fiscal metadata.");
                Require(!ResourceCatalog.Projection(resource).Contains(key), "General resource exposes fiscal projection.");
            }
        });
        test("company fiscal identity: Company create and update require no fiscal configuration", () => {
            foreach (var create in new[] { true, false }) {
                var values = ResourceCatalog.Validate(company, JsonSerializer.SerializeToElement(new { name = "Company" }), create);
                Require(values.Count == 1 && Equals(values["name"], "Company"), "General Company must save independently of fiscal state.");
            }
        });
        test("company fiscal identity: site create and patch need no fiscal identity", () => {
            var complete = new { name = "Site", company_id = Guid.NewGuid(), address = "Synthetic Road 42", city = "Synthetic City", province = "Synthetic Region", postal_code = "AB 12-X", country_code = "GB" };
            ResourceCatalog.Validate(site, JsonSerializer.SerializeToElement(complete), true);
            var values = ResourceCatalog.Validate(site, JsonSerializer.SerializeToElement(new { name = "Renamed Site" }), false);
            Require(values.Count == 1 && Equals(values["name"], "Renamed Site"), "Partial Site update must not require fiscal state.");
        });
        test("company fiscal identity: obsolete Company and Site fiscal fields rejected even when null", () => {
            foreach (var resource in new[] { company, site }) foreach (var create in new[] { true, false })
                foreach (var field in new[] { "vat_number", "tax_code" }) foreach (var value in new object?[] { null, "", "OLD-FISCAL" }) {
                    var payload = new Dictionary<string, object?> { ["name"] = "General record", [field] = value };
                    if (create && resource.Key == "sites") {
                        payload["company_id"] = Guid.NewGuid(); payload["address"] = "Synthetic Road 42"; payload["city"] = "Synthetic City";
                        payload["province"] = "Synthetic Region"; payload["postal_code"] = "AB 12-X"; payload["country_code"] = "GB";
                    }
                    Reject(() => ResourceCatalog.Validate(resource, JsonSerializer.SerializeToElement(payload), create));
                }
        });
    }
}
