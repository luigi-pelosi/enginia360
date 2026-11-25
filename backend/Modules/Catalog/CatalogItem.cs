using System.Globalization;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Catalog;

// Invarianti pure dell'aggregato, condivise da handler e verifiche senza infrastruttura.
public static class CatalogItem
{
    public static void Require(bool valid,int status,string code,string? field=null)
    {
        if(!valid) throw new ApiException(status,code,field);
    }
    public const long MaxVersion=9007199254740991;
    public static readonly string[] IdentifierTypes=["GTIN","OEM","MPN","BARCODE","LEGACY"];

    public static void ValidateManualCode(string code)
        =>Require(code.Length is >=1 and <=40 && code.All(c=>c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9'),400,"catalog_item_manual_code_invalid","code");

    public static string NormalizeIdentifier(string type,string value)
    {
        Require(IdentifierTypes.Contains(type),400,"invalid_identifier_type","identifier_type");
        if(type!="GTIN") return value.ToUpperInvariant();
        Require(value.Length is 8 or 12 or 13 or 14 && value.All(c=>c is >= '0' and <= '9'),400,"invalid_gtin_format","value");
        var sum=0;
        for(var i=0;i<value.Length-1;i++) sum+=(value[i]-'0')*((value.Length-i)%2==0?3:1);
        Require((10-sum%10)%10==value[^1]-'0',400,"invalid_gtin_check_digit","value");
        return value.PadLeft(14,'0');
    }

    public static string TransitionPermission(string current,string next)
    {
        var valid=(current,next) switch {
            ("SUSPENDED","ACTIVE")=>true,
            ("ACTIVE","SUSPENDED")=>true,
            ("ACTIVE","ARCHIVED") or ("SUSPENDED","ARCHIVED")=>true,
            _=>false
        };
        Require(valid,409,"invalid_item_transition","status");
        return "catalog-items."+(next switch {"ACTIVE"=>"activate","SUSPENDED"=>"deactivate",_=>"archive"});
    }

    public static decimal NonNegative(string text,string field)
    {
        decimal number;
        try {number=CatalogConversion.Parse(text);}
        catch(ApiException) {throw new ApiException(400,"invalid_physical_decimal",field);}
        Require(number>=0,400,"invalid_physical_decimal",field);
        return number;
    }
    public static string Decimal(decimal value)=>value.ToString("0.############",CultureInfo.InvariantCulture);
}
