using Enginia360.Modules.Catalog;
using Enginia360.Shared.Validation;

namespace Enginia360.Verification.Catalog;

public static class CatalogItemSelfTests
{
    public static void Run(Action<string,Action> test)
    {
        void Equal(string expected,string actual) {if(expected!=actual) throw new Exception($"Expected {expected}, got {actual}");}
        void Reject(Action action) {try {action();} catch(ApiException) {return;} throw new Exception("Expected refusal");}
        test("catalog item GTIN validates lengths check digit and canonical fourteen digits",()=>{
            Equal("00000096385074",CatalogItem.NormalizeIdentifier("GTIN","96385074"));
            Equal("00036000291452",CatalogItem.NormalizeIdentifier("GTIN","036000291452"));
            Equal("04006381333931",CatalogItem.NormalizeIdentifier("GTIN","4006381333931"));
            Equal("04006381333931",CatalogItem.NormalizeIdentifier("GTIN","04006381333931"));
            foreach(var value in new[]{"96385075","123","abcdefgh","9638507 ","123456789012345","４００６３８１３３３９３１"}) Reject(()=>CatalogItem.NormalizeIdentifier("GTIN",value));
            Equal("AB-12. X",CatalogItem.NormalizeIdentifier("OEM","Ab-12. x"));
            Equal("AB/12",CatalogItem.NormalizeIdentifier("MPN","ab/12"));
            Reject(()=>CatalogItem.NormalizeIdentifier("UNKNOWN","x"));
        });
        test("catalog item status has exact actions and archived is terminal",()=>{
            Equal("catalog-items.activate",CatalogItem.TransitionPermission("SUSPENDED","ACTIVE"));
            Equal("catalog-items.deactivate",CatalogItem.TransitionPermission("ACTIVE","SUSPENDED"));
            foreach(var status in new[]{"ACTIVE","SUSPENDED"}) Equal("catalog-items.archive",CatalogItem.TransitionPermission(status,"ARCHIVED"));
            foreach(var status in new[]{"ACTIVE","SUSPENDED","ARCHIVED"}) Reject(()=>CatalogItem.TransitionPermission("ARCHIVED",status));
            foreach(var legacy in new[]{"DRAFT","INACTIVE"}) {
                Reject(()=>CatalogItem.TransitionPermission("ACTIVE",legacy));
                Reject(()=>CatalogItem.TransitionPermission(legacy,"ACTIVE"));
            }
            Reject(()=>CatalogItem.TransitionPermission("ACTIVE","ACTIVE"));
        });
        test("catalog item contextual ratios never round intermediate divisions",()=>{
            Equal("2",CatalogConversion.ConvertRatios("1","2","3","1","3",12).Quantity);
            Equal("0.67",CatalogConversion.ConvertRatios("1","1","3","1","2",2).Quantity);
            Equal("-0.67",CatalogConversion.ConvertRatios("-1","1","3","1","2",2).Quantity);
            Equal("0.000000000001",CatalogConversion.ConvertRatios("0.000000000001","9999999999999999","9999999999999999","9999999999999999","9999999999999999",12).Quantity);
            Equal("9999999999999999",CatalogConversion.ConvertRatios("9999999999999999","9999999999999999","9999999999999999","9999999999999999","9999999999999999",12).Quantity);
            Reject(()=>CatalogConversion.ConvertRatios("1","1","0","1","1",2));
        });
        test("catalog item physical decimals nonnegative exact and finite",()=>{
            Equal("0",CatalogItem.Decimal(CatalogItem.NonNegative("0","net_weight")));
            Equal("1.000000000001",CatalogItem.Decimal(CatalogItem.NonNegative("1.000000000001","net_weight")));
            foreach(var value in new[]{"-1","NaN","1e1","0.0000000000001"}) Reject(()=>CatalogItem.NonNegative(value,"net_weight"));
        });
    }
}
