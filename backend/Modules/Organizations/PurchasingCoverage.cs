using Enginia360.Infrastructure.Persistence;
using Enginia360.Modules.Identity;
using Enginia360.Shared.Validation;
using ResourceCatalog = global::Enginia360.Api.Resources.Resources;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Enginia360.Modules.Organizations;

// Aggregato focalizzato: non è una relazione semplice e non attribuisce autorità RBAC.
public static class PurchasingCoverage
{
    public const string Permission="purchasing-organizations.assign_scope";
    public sealed record Entry(
        [property:JsonPropertyName("companyId")] Guid CompanyId,
        [property:JsonPropertyName("siteScope")] string SiteScope,
        [property:JsonPropertyName("siteIds")] Guid[] SiteIds);

    public static Entry[] Parse(JsonElement body)
    {
        Check.Require(body.ValueKind==JsonValueKind.Array && body.GetArrayLength()<=500);
        var companies=new HashSet<Guid>(); var totalSites=0; var entries=new List<Entry>();
        foreach(var element in body.EnumerateArray())
        {
            Check.Require(element.ValueKind==JsonValueKind.Object);
            var properties=new Dictionary<string,JsonElement>(StringComparer.Ordinal);
            foreach(var property in element.EnumerateObject()) {
                var name=ResourceCatalog.ReadName(property);
                Check.Require(name is "companyId" or "siteScope" or "siteIds" && properties.TryAdd(name,property.Value));
            }
            Check.Require(properties.Count==3);
            var company=ReadId(properties["companyId"]);
            Check.Require(companies.Add(company));
            var mode=ResourceCatalog.ReadString(properties["siteScope"]);
            Check.Require(mode is "all_sites" or "selected_sites");
            var list=properties["siteIds"];
            Check.Require(list.ValueKind==JsonValueKind.Array && list.GetArrayLength()<=500);
            var sites=new HashSet<Guid>();
            foreach(var item in list.EnumerateArray()) Check.Require(sites.Add(ReadId(item)));
            totalSites+=sites.Count;
            Check.Require(totalSites<=500 && (mode=="all_sites" ? sites.Count==0 : sites.Count>0));
            entries.Add(new Entry(company,mode,sites.Order().ToArray()));
        }
        return entries.OrderBy(e => e.CompanyId).ToArray();
    }
    private static Guid ReadId(JsonElement value)
    {
        Check.Require(Guid.TryParse(ResourceCatalog.ReadString(value),out var id) && id!=Guid.Empty);
        return id;
    }
    public static async Task<Entry[]> Read(AppDb db,Guid tenant,Guid owner)
    {
        var entries=new List<Entry>();
        await using var command=await db.Command("""
            SELECT c.company_id,c.site_scope,
                ARRAY(SELECT s.site_id FROM foundation.purchasing_organization_site s
                    WHERE s.tenant_id=c.tenant_id AND s.purchasing_organization_id=c.purchasing_organization_id
                      AND s.company_id=c.company_id ORDER BY s.site_id)
            FROM foundation.purchasing_organization_company c
            WHERE c.tenant_id=@tenant AND c.purchasing_organization_id=@owner ORDER BY c.company_id
            """,("tenant",tenant),("owner",owner));
        await using var reader=await command.ExecuteReaderAsync();
        while(await reader.ReadAsync()) entries.Add(new Entry(reader.GetGuid(0),reader.GetString(1),reader.GetFieldValue<Guid[]>(2)));
        return entries.ToArray();
    }
    public static async Task Replace(AppDb db,IdentityState state,Guid tenant,Guid owner,Entry[] entries)
    {
        await ResourceCatalog.EnsureRow(db,ResourceCatalog.Get("purchasing-organizations"),owner,tenant);
        // Le assegnazioni disabilitate restano configurabili; l'eleggibilità è distinta.
        foreach(var entry in entries) {
            Check.Require(await ResourceCatalog.Row(db,ResourceCatalog.Get("companies"),entry.CompanyId,tenant)!=null);
            foreach(var site in entry.SiteIds)
                Check.Require(await db.Scalar("SELECT id FROM foundation.site WHERE tenant_id=@t AND company_id=@c AND id=@s",("t",tenant),("c",entry.CompanyId),("s",site)) is Guid);
        }
        var before=await Read(db,tenant,owner);
        await Remove(db,tenant,owner);
        foreach(var entry in entries) {
            await db.Execute("INSERT INTO foundation.purchasing_organization_company(tenant_id,purchasing_organization_id,company_id,site_scope) VALUES(@t,@o,@c,@mode)",("t",tenant),("o",owner),("c",entry.CompanyId),("mode",entry.SiteScope));
            foreach(var site in entry.SiteIds)
                await db.Execute("INSERT INTO foundation.purchasing_organization_site(tenant_id,purchasing_organization_id,company_id,site_id) VALUES(@t,@o,@c,@s)",("t",tenant),("o",owner),("c",entry.CompanyId),("s",site));
        }
        await db.Audit(state.User.Id,tenant,"replace_coverage","purchasing-organization-coverage",owner,new {before,after=entries});
    }
    public static Task<int> Remove(AppDb db,Guid tenant,Guid owner) => db.Execute("""
        DELETE FROM foundation.purchasing_organization_site WHERE tenant_id=@t AND purchasing_organization_id=@o;
        DELETE FROM foundation.purchasing_organization_company WHERE tenant_id=@t AND purchasing_organization_id=@o
        """,("t",tenant),("o",owner));

    // Eleggibilità del contesto organizzativo; non sostituisce alcuna policy utente.
    internal static async Task<bool> IsApplicableToSite(AppDb db,Guid tenantId,Guid ownerId,Guid companyId,Guid siteId) =>
        (bool)(await db.Scalar("""
            SELECT EXISTS (
                SELECT 1 FROM foundation.tenant t
                JOIN foundation.purchasing_organization o ON o.tenant_id=t.id AND o.id=@o AND o.is_enabled
                JOIN foundation.purchasing_organization_company coverage
                    ON coverage.tenant_id=t.id AND coverage.purchasing_organization_id=o.id AND coverage.company_id=@c
                JOIN foundation.company c ON c.tenant_id=t.id AND c.id=coverage.company_id AND c.is_enabled
                JOIN foundation.site s ON s.tenant_id=t.id AND s.company_id=c.id AND s.id=@s AND s.is_enabled
                WHERE t.id=@t AND t.is_enabled AND (coverage.site_scope='all_sites' OR EXISTS (
                    SELECT 1 FROM foundation.purchasing_organization_site selected
                    WHERE selected.tenant_id=t.id AND selected.purchasing_organization_id=o.id
                      AND selected.company_id=c.id AND selected.site_id=s.id)))
            """,("t",tenantId),("o",ownerId),("c",companyId),("s",siteId)))!;
}
