namespace Enginia360.Modules.Catalog;

public static class CatalogItemKind
{
    public static bool SupportsStock(string? kind)=>kind=="GOOD";
    public static bool SupportsPhysicalData(string? kind)=>kind=="GOOD";
}
