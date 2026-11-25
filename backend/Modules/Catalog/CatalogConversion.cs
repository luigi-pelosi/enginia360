using System.Globalization;
using System.Numerics;
using System.Text.RegularExpressions;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.Catalog;

public sealed record ConversionResult(string Quantity,string UnroundedQuantity,bool Rounded,int DecimalPlaces);
public static class CatalogConversion
{
    private static readonly Regex Pattern=new(@"^-?(?:0|[1-9][0-9]{0,15})(?:\.[0-9]{1,12})?$",RegexOptions.CultureInvariant);
    private static readonly BigInteger Limit=BigInteger.Pow(10,16);
    public static decimal Parse(string value,bool factor=false)
    {
        Check.Require(value.Length<=30 && Pattern.IsMatch(value),400,"invalid_catalog_decimal");
        Check.Require(decimal.TryParse(value,NumberStyles.AllowLeadingSign|NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out var result),400,"invalid_catalog_decimal");
        Check.Require(Math.Abs(result)<10000000000000000m && (!factor || result>0),400,"invalid_catalog_decimal");
        return result;
    }
    private static (BigInteger Value,BigInteger Scale) Rational(string text)
    {
        var dot=text.IndexOf('.');var places=dot<0?0:text.Length-dot-1;
        return (BigInteger.Parse(text.Replace(".",""),CultureInfo.InvariantCulture),BigInteger.Pow(10,places));
    }
    private static string Format(BigInteger integer,int places)
    {
        var negative=integer.Sign<0;var digits=BigInteger.Abs(integer).ToString(CultureInfo.InvariantCulture).PadLeft(places+1,'0');
        if(places>0) digits=(digits[..^places]+"."+digits[^places..]).TrimEnd('0').TrimEnd('.');
        return negative?"-"+digits:digits;
    }
    public static ConversionResult Convert(string quantity,string sourceFactor,string targetFactor,int decimalPlaces)
    {
        return ConvertRatios(quantity,sourceFactor,"1",targetFactor,"1",decimalPlaces);
    }
    // q * (origine numeratore/denominatore) / (destinazione numeratore/denominatore).
    // Tutti i prodotti restano interi arbitrari fino all'unico arrotondamento finale.
    public static ConversionResult ConvertRatios(string quantity,string sourceNumerator,string sourceDenominator,string targetNumerator,string targetDenominator,int decimalPlaces)
    {
        Parse(quantity);
        foreach(var factor in new[]{sourceNumerator,sourceDenominator,targetNumerator,targetDenominator}) Parse(factor,true);
        Check.Require(decimalPlaces is >=0 and <=12,400,"invalid_decimal_places");
        var q=Rational(quantity);var a=Rational(sourceNumerator);var b=Rational(sourceDenominator);
        var c=Rational(targetNumerator);var d=Rational(targetDenominator);
        var numerator=q.Value*a.Value*b.Scale*c.Scale*d.Value;
        var denominator=q.Scale*a.Scale*b.Value*c.Value*d.Scale;
        Check.Require(BigInteger.Abs(numerator)<Limit*denominator,400,"catalog_conversion_overflow");
        var absolute=BigInteger.Abs(numerator);var scaled=absolute*BigInteger.Pow(10,decimalPlaces);
        var whole=BigInteger.DivRem(scaled,denominator,out var remainder);
        if(remainder*2>=denominator) whole++;
        Check.Require(whole<Limit*BigInteger.Pow(10,decimalPlaces),400,"catalog_conversion_overflow");
        if(numerator.Sign<0) whole=-whole;
        // Espansione decimale limitata a 40 cifre per rapporti periodici; il flag e il
        // risultato arrotondato derivano dalla frazione esatta, mai da questa anteprima.
        var preview=absolute*BigInteger.Pow(10,40)/denominator;
        if(numerator.Sign<0) preview=-preview;
        return new(Format(whole,decimalPlaces),Format(preview,40),remainder!=0,decimalPlaces);
    }
}
