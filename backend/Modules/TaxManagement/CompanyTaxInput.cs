using System.Globalization;
using System.Text.Json;
using Enginia360.Shared.Validation;
using static Enginia360.Modules.TaxManagement.CompanyTaxConfiguration;
namespace Enginia360.Modules.TaxManagement;

public sealed record CompanyTaxCreateInput(Guid TaxTypeId,Guid EstablishmentCountryId,IReadOnlyList<CompanyTaxRegistrationInput> Registrations,string? TaxCode=null);
public sealed record CompanyTaxRegistrationInput(Guid CountryId,string TaxIdentifier,string RegistrationType,DateOnly ValidFrom,DateOnly? ValidTo,string? Notes,IReadOnlyList<CompanyTaxRegimeProfile> Profiles);

public static class CompanyTaxInput
{
    private const string Prefix="company_tax";
    public static Dictionary<string,JsonElement> Object(JsonElement raw,params string[] names)=>ClassificationInput.Object(raw,Prefix,names);
    public static JsonElement Required(Dictionary<string,JsonElement> raw,string key)=>ClassificationInput.Required(raw,key,Prefix);
    public static Guid Id(Dictionary<string,JsonElement> raw,string key)=>ClassificationInput.Id(raw,key,Prefix);
    public static long Version(Dictionary<string,JsonElement> raw)=>ClassificationInput.Revision(raw,Prefix);
    public static string? Text(Dictionary<string,JsonElement> raw,string key,int max,bool required=false,bool preserve=false)
    {
        try {
            var result=TaxInput.Text(raw,key,max,required);
            if(preserve && raw.TryGetValue(key,out var v) && v.ValueKind==JsonValueKind.String)Require(v.GetString()==result,"invalid_field",field:key);
            return result;
        }catch(ApiException e) when(!e.Code.StartsWith(Prefix+"_",StringComparison.Ordinal)) {throw new ApiException(e.Status,Prefix+e.Code[3..],e.Field??key);}
        catch(InvalidOperationException){throw new ApiException(400,"company_tax_invalid_field",key);}
        catch(ArgumentException){throw new ApiException(400,"company_tax_invalid_field",key);}
    }
    public static DateOnly Date(string value,string field)
    {
        Require(DateOnly.TryParseExact(value,"yyyy-MM-dd",CultureInfo.InvariantCulture,DateTimeStyles.None,out var d),"invalid_date",field:field);return d;
    }
    public static DateOnly Date(Dictionary<string,JsonElement> raw,string key)
    {
        var v=Required(raw,key);Require(v.ValueKind==JsonValueKind.String,"invalid_date",field:key);return Date(v.GetString()!,key);
    }
    public static DateOnly? End(Dictionary<string,JsonElement> raw)=>raw.TryGetValue("valid_to",out var end) && end.ValueKind!=JsonValueKind.Null?Date(raw,"valid_to"):null;
    public static JsonElement[] Array(JsonElement raw,string field,int max=100)
    {
        Require(raw.ValueKind==JsonValueKind.Array && raw.GetArrayLength()<=max,"invalid_array",field:field);return raw.EnumerateArray().ToArray();
    }
    public static CompanyTaxRegimeProfile Profile(JsonElement raw)
    {
        var v=Object(raw,"tax_regime_id","valid_from","valid_to");var from=Date(v,"valid_from");var to=End(v);Interval(from,to);return new(Guid.NewGuid(),Id(v,"tax_regime_id"),from,to);
    }
    public static CompanyTaxRegistrationInput Registration(JsonElement raw)
    {
        var input=Object(raw,"values","profiles");var v=Object(Required(input,"values"),"country_id","tax_identifier","registration_type","valid_from","valid_to","notes");
        var from=Date(v,"valid_from");var to=End(v);Interval(from,to);
        Require(input.ContainsKey("profiles"),"initial_regime_required",field:"profiles");
        var profiles=Array(input["profiles"],"profiles").Select(Profile).ToArray();
        Require(profiles.Length>0,"initial_regime_required",field:"profiles");
        return new(Id(v,"country_id"),Text(v,"tax_identifier",50,true,true)!,Text(v,"registration_type",40,true,true)!,from,to,Text(v,"notes",10000),profiles);
    }
    public static CompanyTaxCreateInput Create(JsonElement raw)
    {
        var input=Object(raw,"values","registrations");var v=Object(Required(input,"values"),"tax_type_id","establishment_country_id","tax_code");
        Require(input.ContainsKey("registrations"),"initial_registration_required",field:"registrations");
        var registrations=Array(input["registrations"],"registrations").Select(Registration).ToArray();
        Require(registrations.Length>0,"initial_registration_required",field:"registrations");
        Require(registrations.All(r=>r.Profiles.Count>0),"initial_regime_required",field:"profiles");
        return new(Id(v,"tax_type_id"),Id(v,"establishment_country_id"),registrations,TaxCode(v));
    }
    public static string? TaxCode(Dictionary<string,JsonElement> values)
    {
        if(!values.TryGetValue("tax_code",out var raw) || raw.ValueKind==JsonValueKind.Null)return null;
        Require(raw.ValueKind==JsonValueKind.String,"invalid_field",field:"tax_code");
        try {return NormalizeTaxCode(raw.GetString());}
        catch(InvalidOperationException){throw new ApiException(400,"company_tax_invalid_field","tax_code");}
        catch(ArgumentException){throw new ApiException(400,"company_tax_invalid_field","tax_code");}
    }
    public static (string? TaxCode,long ExpectedVersion) Update(JsonElement raw)
    {
        var input=Object(raw,"values","expectedVersion");var values=Object(Required(input,"values"),"tax_code");
        Required(values,"tax_code");return (TaxCode(values),Version(input));
    }
}
