using System.Text.Json.Serialization;
namespace Enginia360.Catalog.Contracts;

// New management vocabulary; legacy Part identity is retained, never duplicated.
[JsonConverter(typeof(JsonStringEnumConverter<CatalogKind>))]
public enum CatalogKind { Article, Service }
public static class CatalogKinds
{
    public static string ToStored(CatalogKind kind) => kind switch
    {
        CatalogKind.Article => "Part", CatalogKind.Service => "Service",
        _ => throw new ArgumentOutOfRangeException(nameof(kind)),
    };
    public static CatalogKind FromStored(string kind) => kind switch
    {
        "Part" => CatalogKind.Article, "Service" => CatalogKind.Service,
        _ => throw new ArgumentOutOfRangeException(nameof(kind)),
    };
}
public sealed record CatalogIdentity(Guid Id, CatalogKind Kind, string Label, int Revision);
[JsonUnmappedMemberHandling(JsonUnmappedMemberHandling.Disallow)]
public sealed record CatalogManagementCommand(Guid CommandId, string Operation, Guid? ItemId,
    int ExpectedRevision, int AuthorityVersion, CatalogKind Kind, string Label);
