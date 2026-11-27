using System.Globalization;
using System.Text.RegularExpressions;
using Enginia360.Shared.Validation;

namespace Enginia360.Modules.TaxManagement;

public sealed record TaxNature(Guid Id,Guid CountryId,string Scheme,string Code,DateOnly ValidFrom,DateOnly? ValidTo);
public sealed record TaxFiscalVersion(Guid Id,decimal Rate,string Treatment,Guid? TaxNatureCodeId,string? LegalReference,DateOnly ValidFrom,DateOnly? ValidTo);
public sealed record TaxSchedulePlan(Guid? PredecessorId,DateOnly? PredecessorValidTo);

public static class TaxRules
{
    public const long MaxRevision=9007199254740991;
    public static readonly string[] Treatments=["TAXABLE","ZERO_RATED","OUT_OF_SCOPE","NON_TAXABLE","EXEMPT","REVERSE_CHARGE","EXCLUDED","MARGIN","OTHER_EU"];
    public static void Require(bool condition,string code,int status=400,string? field=null)
    { if(!condition) throw new ApiException(status,code,field); }
    public static decimal ParseRate(string value)
    {
        Require(value.Length<=20 && Regex.IsMatch(value,@"\A[0-9]+(?:\.[0-9]{1,6})?\z",RegexOptions.CultureInvariant) && decimal.TryParse(value,NumberStyles.AllowDecimalPoint,CultureInfo.InvariantCulture,out var parsed) && parsed<=999.999999m,"tax_invalid_rate");
        return decimal.Parse(value,CultureInfo.InvariantCulture);
    }
    public static string RateText(decimal rate)=>rate.ToString("0.000000",CultureInfo.InvariantCulture);
    public static DateOnly ParseDate(string value)
    {
        Require(DateOnly.TryParseExact(value,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out _),"tax_invalid_date");
        return DateOnly.ParseExact(value,"yyyy-MM-dd",CultureInfo.InvariantCulture);
    }
    public static void CheckRevision(long expected,long actual)
    {
        Require(expected==actual,"tax_stale_version",409);
        Require(actual<MaxRevision,"tax_version_exhausted",409);
    }
    public static bool Overlaps(DateOnly a,DateOnly? b,DateOnly c,DateOnly? d)=>a<=(d??DateOnly.MaxValue) && c<=(b??DateOnly.MaxValue);
    public static TaxFiscalVersion? Resolve(IEnumerable<TaxFiscalVersion> versions,DateOnly date)
        =>versions.SingleOrDefault(v=>v.ValidFrom<=date && (v.ValidTo==null || date<=v.ValidTo));
    public static void Validate(TaxFiscalVersion version,string isoCode,Guid country,TaxNature? nature)
    {
        Require(version.ValidTo==null || version.ValidTo>=version.ValidFrom,"tax_invalid_interval");
        Require(version.Rate>=0 && version.Rate<=999.999999m && decimal.Round(version.Rate,6)==version.Rate,"tax_invalid_rate");
        Require(Treatments.Contains(version.Treatment,StringComparer.Ordinal),"tax_invalid_treatment");
        Require(version.Treatment=="TAXABLE"?version.Rate>0:version.Rate==0,"tax_invalid_treatment_rate");
        Require(isoCode!="IT" || version.Treatment!="ZERO_RATED","tax_zero_rated_not_applicable");
        Require(version.TaxNatureCodeId==nature?.Id,"tax_invalid_nature");
        if(nature!=null) {
            Require(nature.CountryId==country,"tax_nature_country_mismatch");
            Require(nature.ValidFrom<=version.ValidFrom && (nature.ValidTo==null || version.ValidTo!=null && version.ValidTo<=nature.ValidTo),"tax_nature_validity_mismatch");
        }
        if(version.Treatment is "TAXABLE" or "ZERO_RATED") Require(nature==null,"tax_nature_forbidden");
        if(isoCode!="IT") return;
        var allowed=version.Treatment switch {
            "TAXABLE"=>nature==null,
            "OUT_OF_SCOPE"=>nature?.Code is "N2.1" or "N2.2",
            "NON_TAXABLE"=>nature?.Code is "N3.1" or "N3.2" or "N3.3" or "N3.4" or "N3.5" or "N3.6",
            "EXEMPT"=>nature?.Code=="N4", "EXCLUDED"=>nature?.Code=="N1", "MARGIN"=>nature?.Code=="N5", "OTHER_EU"=>nature?.Code=="N7",
            "REVERSE_CHARGE"=>nature?.Code is "N6.1" or "N6.2" or "N6.3" or "N6.4" or "N6.5" or "N6.6" or "N6.7" or "N6.8" or "N6.9", _=>false
        };
        Require(allowed && (version.Treatment=="TAXABLE" || nature?.Scheme=="FATTURAPA"),"tax_nature_treatment_mismatch");
    }
    // Il payload fiscale non cambia: si abbrevia soltanto il predecessore coprente.
    public static TaxSchedulePlan Schedule(IReadOnlyList<TaxFiscalVersion> existing,TaxFiscalVersion successor)
    {
        Require(successor.ValidTo==null || successor.ValidTo>=successor.ValidFrom,"tax_invalid_interval");
        var covering=existing.Where(v=>v.ValidFrom<successor.ValidFrom && (v.ValidTo==null || v.ValidTo>=successor.ValidFrom)).ToArray();
        Require(covering.Length<=1,"tax_version_overlap",409);
        var predecessor=covering.SingleOrDefault();
        foreach(var v in existing) if(v.Id!=predecessor?.Id)
            Require(!Overlaps(v.ValidFrom,v.ValidTo,successor.ValidFrom,successor.ValidTo),"tax_version_overlap",409);
        return new(predecessor?.Id,predecessor==null?null:successor.ValidFrom.AddDays(-1));
    }
}
