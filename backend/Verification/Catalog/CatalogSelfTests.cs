using Enginia360.Modules.Catalog;
using Enginia360.Shared.Validation;

namespace Enginia360.Verification.Catalog;

public static class CatalogSelfTests
{
    public static void Run(Action<string,Action> test)
    {
        void Equal(string expected,string actual) {if(expected!=actual) throw new Exception($"Expected {expected}, got {actual}");}
        void Reject(Action action) {try {action();} catch(ApiException) {return;} throw new Exception("Expected refusal");}
        test("catalog decimal precision is invariant and bounded",()=>{
            Equal("1.000000000001",CatalogConversion.Parse("1.000000000001").ToString(System.Globalization.CultureInfo.InvariantCulture));
            foreach(var s in new[]{"1.0000000000001","1e3","1,5","NaN","10000000000000000"," 1","+1"}) Reject(()=>CatalogConversion.Parse(s));
            Reject(()=>CatalogConversion.Parse("0",true));Reject(()=>CatalogConversion.Parse("-1",true));
        });
        test("catalog conversion uses exact ratio and midpoint away from zero",()=>{
            Equal("1.01",CatalogConversion.Convert("1.005","1","1",2).Quantity);
            Equal("-1.01",CatalogConversion.Convert("-1.005","1","1",2).Quantity);
            Equal("0.33",CatalogConversion.Convert("1","1","3",2).Quantity);
            Equal("2",CatalogConversion.Convert("1.5","1","1",0).Quantity);
            Equal("-2",CatalogConversion.Convert("-1.5","1","1",0).Quantity);
            Equal("1.000000000001",CatalogConversion.Convert("1.000000000001","1","1",12).Quantity);
            Equal("1000",CatalogConversion.Convert("1","1","0.001",3).Quantity);
            Equal("0.000000000001",CatalogConversion.Convert("0.000000000001","9999999999999999","9999999999999999",12).Quantity);
            Equal("9999999999999999",CatalogConversion.Convert("9999999999999999","9999999999999999","9999999999999999",12).Quantity);
            Equal("0",CatalogConversion.Convert("0.000000000001","4999999999999999.499999999999","9999999999999999",12).Quantity);
            Equal("0.000000000001",CatalogConversion.Convert("0.000000000001","4999999999999999.500000000001","9999999999999999",12).Quantity);
            if(CatalogConversion.Convert("1","1","2",2).Rounded) throw new Exception("Exact conversion flagged");
            if(!CatalogConversion.Convert("1","1","3",2).Rounded) throw new Exception("Rounding omitted");
            Reject(()=>CatalogConversion.Convert("9999999999999999","60","1",2));
            Reject(()=>CatalogConversion.Convert("1","1","1",13));
        });
    }
}
