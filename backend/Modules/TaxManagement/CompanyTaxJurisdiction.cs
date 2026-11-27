using System.Text.RegularExpressions;
using static Enginia360.Modules.TaxManagement.CompanyTaxConfiguration;
namespace Enginia360.Modules.TaxManagement;

/// <summary>Policy finita, formale e dichiarativa: nessuna verifica checksum/VIES/idoneità legale.</summary>
public static class CompanyTaxJurisdiction
{
    public static readonly string[] SupportedCountries=["IT","DE","FR"];
    public static string[] RegistrationTypes(string country,string? establishment=null)
    {
        if(!SupportedCountries.Contains(country,StringComparer.Ordinal) || establishment!=null && !SupportedCountries.Contains(establishment,StringComparer.Ordinal))return [];
        if(establishment==country)return ["DOMESTIC"];
        if(establishment==null)return country=="IT"?["DOMESTIC","DIRECT_IDENTIFICATION","FISCAL_REPRESENTATIVE"]:["DOMESTIC","DIRECT_IDENTIFICATION"];
        return country=="IT"?["DIRECT_IDENTIFICATION","FISCAL_REPRESENTATIVE"]:["DIRECT_IDENTIFICATION"];
    }
    public static void RequireType(string country,string establishment,string type)
    {
        Require(SupportedCountries.Contains(country,StringComparer.Ordinal),"country_not_supported",field:"country_id");
        Require(RegistrationTypes(country,establishment).Contains(type,StringComparer.Ordinal),"registration_type_not_supported",field:"registration_type");
    }
    public static string ValidationLevel(string iso)=>SupportedCountries.Contains(iso,StringComparer.Ordinal)?"FORMAT_ONLY":"UNSUPPORTED";
    public static string CanonicalIdentifier(string country,string input)
    {
        Require(SupportedCountries.Contains(country,StringComparer.Ordinal),"country_not_supported",field:"country_id");
        // Il valore canonico è richiesto esattamente: niente case-fold, trim o prefissi inventati.
        var pattern=country switch {"IT"=>@"\AIT[0-9]{11}\z","DE"=>@"\ADE[0-9]{9}\z","FR"=>@"\AFR[0-9A-HJ-NP-Z]{2}[0-9]{9}\z",_=>@"\b\B"};
        Require(input.Length<=50 && Regex.IsMatch(input,pattern,RegexOptions.CultureInvariant),"invalid_identifier",field:"tax_identifier");
        return input;
    }
}
